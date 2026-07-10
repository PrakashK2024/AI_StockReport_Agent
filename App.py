from __future__ import annotations

import json
import os

import pandas as pd
import streamlit as st

from agent import run_research_agent

st.set_page_config(
    page_title="AI Stock Research Agent",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(59, 130, 246, 0.18), transparent 28%),
                radial-gradient(circle at top right, rgba(16, 185, 129, 0.12), transparent 24%),
                linear-gradient(180deg, #0b1020 0%, #111827 100%);
            color: #f8fafc;
        }

        .hero-card {
            padding: 24px 26px;
            border-radius: 22px;
            background: rgba(15, 23, 42, 0.76);
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 18px 50px rgba(0, 0, 0, 0.35);
            margin-bottom: 18px;
        }

        .hero-title {
            font-size: 2.2rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            margin-bottom: 6px;
            color: #ffffff;
        }

        .hero-subtitle {
            font-size: 1rem;
            color: #cbd5e1;
            line-height: 1.7;
        }

        .chip {
            display: inline-block;
            padding: 6px 12px;
            margin: 4px 6px 4px 0;
            border-radius: 999px;
            background: rgba(59, 130, 246, 0.16);
            color: #bfdbfe;
            border: 1px solid rgba(59, 130, 246, 0.22);
            font-size: 0.84rem;
            font-weight: 600;
        }

        .section-card {
            padding: 18px 18px 10px 18px;
            border-radius: 18px;
            background: rgba(15, 23, 42, 0.74);
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.22);
            margin-bottom: 16px;
        }

        div[data-testid="stSidebar"] {
            background: linear-gradient(180deg, rgba(15, 23, 42, 0.98), rgba(17, 24, 39, 0.98));
            border-right: 1px solid rgba(255, 255, 255, 0.06);
        }

        .stMetric {
            background: rgba(15, 23, 42, 0.75);
            border: 1px solid rgba(255, 255, 255, 0.08);
            padding: 14px 14px 10px 14px;
            border-radius: 16px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

POPULAR_TICKERS = [
    ("AAPL", "Apple"),
    ("MSFT", "Microsoft"),
    ("NVDA", "NVIDIA"),
    ("TSLA", "Tesla"),
    ("AMZN", "Amazon"),
    ("GOOGL", "Google"),
    ("META", "Meta"),
    ("NFLX", "Netflix"),
]

st.session_state.setdefault("query", "NVDA")


def set_query(value: str) -> None:
    st.session_state.query = value


st.markdown(
    """
    <div class="hero-card">
        <div class="hero-title">AI Stock Research Agent</div>
        <div class="hero-subtitle">
            Type a ticker symbol or company name, then get an AI-written research brief,
            SEC filing highlights, and price context. Built for research only, not financial advice.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    "".join(
        f'<span class="chip">{symbol} • {name}</span>' for symbol, name in POPULAR_TICKERS
    ),
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("## Search")
    st.caption("Enter a ticker like NVDA or a company name like NVIDIA.")

    query = st.text_input(
        "Ticker or company name",
        key="query",
        placeholder="Example: NVDA, NVIDIA, Apple",
    ).strip()

    st.markdown("### Quick examples")
    top_row = st.columns(2)
    mid_row = st.columns(2)
    bottom_row = st.columns(2)
    button_rows = [top_row, mid_row, bottom_row, bottom_row]

    for idx, (symbol, name) in enumerate(POPULAR_TICKERS):
        row = button_rows[idx // 2]
        with row[idx % 2]:
            st.button(
                symbol,
                use_container_width=True,
                key=f"quick_{symbol}",
                on_click=set_query,
                args=(symbol,),
            )

    run_button = st.button("Run research", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("### What this app uses")
    st.write("Groq for the LLM")
    st.write("SEC public company data")
    st.write("yfinance for price history fallback")

if run_button:
    if not query:
        st.error("Please enter a ticker symbol or company name.")
        st.stop()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        st.error("GROQ_API_KEY is missing. Add it to your .env file.")
        st.stop()

    with st.spinner("Agent is researching..."):
        try:
            model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
            memory = run_research_agent(
                user_input=query,
                model=model,
                api_key=api_key,
            )
            st.session_state["memory"] = memory
            st.session_state["report"] = memory["final_report"]
        except Exception as exc:
            st.error(f"Could not run research for {query}: {exc}")
            st.info("Try a real ticker like NVDA or a company name like NVIDIA.")
            st.stop()


def render_bundle(bundle: dict) -> None:
    meta = bundle["meta"]
    price_stats = bundle["price_stats"]
    financials = bundle["financials"]
    filings = bundle["filings"]
    price_records = bundle["price_records"]

    st.markdown(
        f"""
        <div class="section-card">
            <h2 style="margin-bottom: 4px; color: white;">{meta["company_name"]} ({meta["ticker"]})</h2>
            <p style="color: #cbd5e1; margin-bottom: 0;">
                Matched by <strong>{meta.get("matched_by", "unknown")}</strong>.
                This dashboard combines SEC filings, price context, and an AI-written summary.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Last close", price_stats.get("last_close", "N/A"))
    c2.metric("52W high", price_stats.get("52w_high", "N/A"))
    c3.metric("52W low", price_stats.get("52w_low", "N/A"))
    c4.metric("1Y return %", price_stats.get("1y_return_pct", "N/A"))

    left, right = st.columns([1.15, 0.85])

    with left:
        st.markdown("### Price trend")
        if price_records:
            price_df = pd.DataFrame(price_records)
            if "date" in price_df.columns and "close" in price_df.columns:
                chart_df = price_df[["date", "close"]].copy()
                chart_df["date"] = pd.to_datetime(chart_df["date"], errors="coerce")
                chart_df = chart_df.dropna(subset=["date"])
                chart_df = chart_df.set_index("date")
                st.line_chart(chart_df, height=340)
            else:
                st.info("Price chart data is incomplete.")
        else:
            st.info("No price history available.")

    with right:
        st.markdown("### Quick insights")
        st.write(f"**Ticker:** {meta['ticker']}")
        st.write(f"**Company:** {meta['company_name']}")
        st.write(f"**Matched by:** {meta.get('matched_by', 'unknown')}")
        st.write(f"**1M return:** {price_stats.get('1m_return_pct', 'N/A')}")
        st.write(f"**3M return:** {price_stats.get('3m_return_pct', 'N/A')}")
        st.write(f"**6M return:** {price_stats.get('6m_return_pct', 'N/A')}")

    left2, right2 = st.columns(2)

    with left2:
        st.markdown("### Financial snapshot")
        if financials:
            for name, fact in financials.items():
                if fact:
                    st.write(
                        f"**{name}**: {fact['value']} {fact['unit']} "
                        f"(form {fact.get('form')}, filed {fact.get('filed')}, end {fact.get('end')})"
                    )
                else:
                    st.write(f"**{name}**: not found")
        else:
            st.info("No financial facts available.")

    with right2:
        st.markdown("### Recent SEC filings")
        if filings:
            filing_df = pd.DataFrame(filings)
            st.dataframe(filing_df, use_container_width=True, hide_index=True)
        else:
            st.info("No recent filings were returned.")


if "memory" in st.session_state:
    memory = st.session_state["memory"]
    report = st.session_state["report"]
    bundles = memory.get("bundles", [])

    st.markdown(
        f"""
        <div class="section-card">
            <h2 style="margin-bottom: 4px; color: white;">Agent Output</h2>
            <p style="color: #cbd5e1; margin-bottom: 0;">
                Plan: {json.dumps(memory.get("plan", {}), default=str)}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Agent steps")
    for step in memory.get("steps", []):
        with st.expander(step.get("tool", "step")):
            st.code(json.dumps(step, indent=2, default=str), language="json")

    if len(bundles) == 1:
        render_bundle(bundles[0])
    elif len(bundles) > 1:
        tab_names = [b["meta"]["ticker"] for b in bundles]
        tabs = st.tabs(tab_names)
        for tab, bundle in zip(tabs, bundles):
            with tab:
                render_bundle(bundle)

    st.markdown("### AI research report")
    st.markdown(report)

    st.markdown("### Raw context")
    with st.expander("Show JSON", expanded=False):
        st.code(json.dumps(memory, indent=2, default=str), language="json")
else:
    st.markdown("## Try one of these")
    st.write("A good first test is NVDA, AAPL, MSFT, or TSLA.")