from __future__ import annotations

import json
import os
import re
from difflib import SequenceMatcher, get_close_matches
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

SEC_TICKERS_URL = "https://www.sec.gov/plan-b/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

SEC_HEADERS = {
    "User-Agent": os.getenv("SEC_USER_AGENT", "AIStockResearchAgent your@email.com"),
    "Accept-Encoding": "gzip, deflate",
    "Accept": "application/json",
}

MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

PREFERRED_CONCEPTS = {
    "Revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "Revenues",
    ],
    "Net Income": ["NetIncomeLoss"],
    "Assets": ["Assets"],
    "Liabilities": ["Liabilities"],
    "Cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "EPS Basic": ["EarningsPerShareBasic"],
}

STOPWORDS = {
    "inc",
    "incorporated",
    "corp",
    "corporation",
    "co",
    "company",
    "ltd",
    "limited",
    "plc",
    "holdings",
    "holding",
    "class",
    "common",
    "stock",
    "shares",
    "share",
    "the",
}


def _request_json(url: str) -> Dict[str, Any]:
    response = requests.get(url, headers=SEC_HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


def _normalize_text(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    tokens = [token for token in value.split() if token not in STOPWORDS]
    return " ".join(tokens)


def _safe_cik_for_url(cik: str) -> str:
    try:
        return str(int(str(cik)))
    except Exception:
        cleaned = str(cik).lstrip("0")
        return cleaned or str(cik)


@lru_cache(maxsize=1)
def load_ticker_map() -> Dict[str, Dict[str, Any]]:
    raw = _request_json(SEC_TICKERS_URL)
    ticker_map: Dict[str, Dict[str, Any]] = {}

    for item in raw.values():
        ticker = str(item["ticker"]).upper().strip()
        company_name = str(item["title"]).strip()
        cik = str(item["cik_str"]).zfill(10)

        ticker_map[ticker] = {
            "ticker": ticker,
            "company_name": company_name,
            "cik": cik,
            "normalized_company_name": _normalize_text(company_name),
        }

    return ticker_map


def suggest_matches(user_input: str, limit: int = 5) -> List[str]:
    ticker_map = load_ticker_map()
    normalized_input = _normalize_text(user_input)

    normalized_to_meta = {
        meta["normalized_company_name"]: meta for meta in ticker_map.values()
    }

    close_names = get_close_matches(
        normalized_input,
        list(normalized_to_meta.keys()),
        n=limit,
        cutoff=0.55,
    )

    suggestions: List[str] = []
    for name in close_names:
        meta = normalized_to_meta[name]
        suggestions.append(f"{meta['ticker']} ({meta['company_name']})")

    if not suggestions:
        for symbol in list(ticker_map.keys())[:limit]:
            meta = ticker_map[symbol]
            suggestions.append(f"{meta['ticker']} ({meta['company_name']})")

    return suggestions[:limit]


def resolve_company_input(user_input: str) -> Dict[str, Any]:
    if not user_input or not user_input.strip():
        raise ValueError("Please enter a ticker symbol or company name.")

    ticker_map = load_ticker_map()
    cleaned = user_input.strip().upper()

    if cleaned in ticker_map:
        meta = dict(ticker_map[cleaned])
        meta["matched_by"] = "ticker"
        meta["user_input"] = user_input
        return meta

    normalized_input = _normalize_text(user_input)
    if not normalized_input:
        raise ValueError("Please enter a valid ticker symbol or company name.")

    exact_matches: List[Dict[str, Any]] = []
    partial_matches: List[Tuple[float, Dict[str, Any]]] = []

    for meta in ticker_map.values():
        normalized_name = meta["normalized_company_name"]

        if normalized_name == normalized_input:
            exact_matches.append(meta)
            continue

        if normalized_input in normalized_name or normalized_name in normalized_input:
            similarity = SequenceMatcher(None, normalized_input, normalized_name).ratio()
            partial_matches.append((similarity, meta))

    if exact_matches:
        meta = dict(sorted(exact_matches, key=lambda x: len(x["company_name"]))[0])
        meta["matched_by"] = "company name"
        meta["user_input"] = user_input
        return meta

    if partial_matches:
        partial_matches.sort(
            key=lambda item: (item[0], -len(item[1]["company_name"])),
            reverse=True,
        )
        meta = dict(partial_matches[0][1])
        meta["matched_by"] = "company name"
        meta["user_input"] = user_input
        return meta

    suggestions = suggest_matches(user_input)
    raise ValueError(
        f"Could not resolve '{user_input}' to a SEC ticker. "
        f"Try one of these: {', '.join(suggestions)}"
    )


@retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3))
def get_submissions(cik: str) -> Dict[str, Any]:
    return _request_json(SEC_SUBMISSIONS_URL.format(cik=cik))


@retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3))
def get_companyfacts(cik: str) -> Dict[str, Any]:
    return _request_json(SEC_COMPANYFACTS_URL.format(cik=cik))


def latest_fact_from_concepts(
    companyfacts: Dict[str, Any],
    candidate_concepts: List[str],
    preferred_units: Tuple[str, ...] = ("USD", "USD/shares", "shares", "pure"),
) -> Optional[Dict[str, Any]]:
    facts_root = companyfacts.get("facts", {}).get("us-gaap", {})

    for concept in candidate_concepts:
        block = facts_root.get(concept)
        if not block:
            continue

        units = block.get("units", {})
        for unit in preferred_units:
            items = units.get(unit, [])
            usable = [x for x in items if "val" in x]
            if not usable:
                continue

            usable.sort(key=lambda x: (x.get("end", ""), x.get("filed", "")))
            fact = usable[-1]
            return {
                "concept": concept,
                "label": concept,
                "value": fact.get("val"),
                "unit": unit,
                "end": fact.get("end"),
                "filed": fact.get("filed"),
                "form": fact.get("form"),
            }

        for unit, items in units.items():
            usable = [x for x in items if "val" in x]
            if not usable:
                continue

            usable.sort(key=lambda x: (x.get("end", ""), x.get("filed", "")))
            fact = usable[-1]
            return {
                "concept": concept,
                "label": concept,
                "value": fact.get("val"),
                "unit": unit,
                "end": fact.get("end"),
                "filed": fact.get("filed"),
                "form": fact.get("form"),
            }

    return None


def extract_financial_summary(companyfacts: Dict[str, Any]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for friendly_name, concepts in PREFERRED_CONCEPTS.items():
        summary[friendly_name] = latest_fact_from_concepts(companyfacts, concepts)
    return summary


def get_recent_filings(
    submissions: Dict[str, Any],
    cik: str,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])
    accession_numbers = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    report_dates = recent.get("reportDate", [])

    wanted = {"10-K", "10-Q", "8-K", "20-F", "40-F", "6-K"}
    rows: List[Dict[str, Any]] = []

    cik_for_url = _safe_cik_for_url(cik)

    total = min(len(forms), len(filing_dates), len(accession_numbers), len(primary_docs))
    for i in range(total):
        form = forms[i]
        if form not in wanted:
            continue

        accession = accession_numbers[i]
        primary = primary_docs[i]

        filing_url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{cik_for_url}/{accession.replace('-', '')}/{primary}"
        )

        rows.append(
            {
                "form": form,
                "filing_date": filing_dates[i],
                "report_date": report_dates[i] if i < len(report_dates) else None,
                "accession": accession,
                "primary_document": primary,
                "url": filing_url,
            }
        )

        if len(rows) >= limit:
            break

    return rows


def get_price_history(
    ticker: str,
    period: str = "1y",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    try:
        hist = yf.Ticker(ticker).history(
            period=period,
            auto_adjust=True,
            actions=False,
        )
        if hist.empty:
            return [], {"price_error": "No price history returned by yfinance."}

        hist = hist.reset_index()
        hist.columns = [str(c).lower().replace(" ", "_") for c in hist.columns]

        if "date" not in hist.columns:
            if "datetime" in hist.columns:
                hist = hist.rename(columns={"datetime": "date"})
            else:
                hist = hist.rename(columns={hist.columns[0]: "date"})

        hist["date"] = pd.to_datetime(hist["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        for col in ["open", "high", "low", "close", "volume"]:
            if col in hist.columns:
                hist[col] = pd.to_numeric(hist[col], errors="coerce")

        close = hist["close"].dropna().astype(float)
        if close.empty:
            return [], {"price_error": "Close prices were empty."}

        def pct_change_from_n_days_ago(n: int) -> Optional[float]:
            if len(close) <= n:
                return None
            old = float(close.iloc[-(n + 1)])
            now = float(close.iloc[-1])
            return round(((now / old) - 1) * 100, 2)

        stats = {
            "last_close": round(float(close.iloc[-1]), 2),
            "52w_high": round(float(close.max()), 2),
            "52w_low": round(float(close.min()), 2),
            "1m_return_pct": pct_change_from_n_days_ago(21),
            "3m_return_pct": pct_change_from_n_days_ago(63),
            "6m_return_pct": pct_change_from_n_days_ago(126),
            "1y_return_pct": pct_change_from_n_days_ago(252),
        }

        return hist.to_dict(orient="records"), stats

    except Exception as exc:
        return [], {"price_error": str(exc)}


def build_research_bundle(user_input: str) -> Dict[str, Any]:
    meta = resolve_company_input(user_input)
    submissions = get_submissions(meta["cik"])
    companyfacts = get_companyfacts(meta["cik"])
    price_records, price_stats = get_price_history(meta["ticker"])
    financials = extract_financial_summary(companyfacts)
    filings = get_recent_filings(submissions, meta["cik"])

    return {
        "query": user_input,
        "meta": meta,
        "price_records": price_records,
        "price_stats": price_stats,
        "financials": financials,
        "filings": filings,
    }


def build_context(user_input: str) -> Dict[str, Any]:
    return build_research_bundle(user_input)


def _safe_json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def generate_report(context: Dict[str, Any]) -> str:
    memory = {
        "query": context.get("query", ""),
        "plan": {
            "companies": [context.get("meta", {}).get("ticker", "")],
            "comparison": False,
            "focus": "single company research",
        },
        "bundles": [context],
    }
    return generate_report_from_memory(memory)


def generate_report_from_memory(memory: Dict[str, Any]) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing.")

    client = Groq(api_key=api_key)

    compact_bundles: List[Dict[str, Any]] = []
    for bundle in memory.get("bundles", []):
        compact_bundles.append(
            {
                "query": bundle.get("query"),
                "meta": bundle.get("meta"),
                "price_stats": bundle.get("price_stats"),
                "financials": bundle.get("financials"),
                "filings": bundle.get("filings", [])[:5],
            }
        )

    system_prompt = (
        "You are a careful stock research assistant.\n"
        "Use only the provided data.\n"
        "Do not invent numbers.\n"
        "Do not tell the user to buy or sell.\n"
        "If data is missing, say so plainly.\n"
        "Write a Markdown report with these sections:\n"
        "1. Company overview\n"
        "2. Price action\n"
        "3. Financial snapshot\n"
        "4. Recent SEC filings\n"
        "5. Bull case\n"
        "6. Bear case\n"
        "7. Questions to research next\n"
        "8. Bottom line\n"
    )

    user_prompt = f"""
User request:
{memory.get("query", "")}

Plan:
{_safe_json(memory.get("plan", {}))}

Research bundles:
{_safe_json(compact_bundles)}

Write a concise, useful research note based only on the data above.
If there are multiple companies, compare them clearly.
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content or "No response returned by the model."