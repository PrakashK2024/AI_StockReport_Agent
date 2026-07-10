from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from groq import Groq

from Stock_Agent import build_research_bundle, generate_report_from_memory


def _extract_json(text: str) -> Dict[str, Any]:
    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError("The planner did not return valid JSON.")


def _plan_research(client: Groq, model: str, user_input: str) -> Dict[str, Any]:
    messages = [
        {
            "role": "system",
            "content": (
                "You are a planning agent for a stock research app.\n"
                "Return JSON only, no markdown, no explanation.\n"
                "Schema:\n"
                '{ "companies": ["NVDA"], "comparison": false, "focus": "fundamentals", "notes": "short note" }\n'
                "Rules:\n"
                "- companies must contain 1 or 2 company names or ticker symbols.\n"
                "- If the user asks to compare, set comparison true and include both companies.\n"
                "- If only one company is implied, include one company.\n"
                "- If the user input is ambiguous, choose the most likely company.\n"
            ),
        },
        {
            "role": "user",
            "content": f"Plan a research workflow for this request: {user_input}",
        },
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.1,
    )

    raw = response.choices[0].message.content or ""
    return _extract_json(raw)


def run_research_agent(
    user_input: str,
    model: str,
    api_key: str,
) -> Dict[str, Any]:
    client = Groq(api_key=api_key)

    plan = _plan_research(client, model, user_input)
    companies = plan.get("companies") or [user_input]

    cleaned_companies: List[str] = []
    for item in companies:
        if isinstance(item, str) and item.strip():
            cleaned_companies.append(item.strip())

    if not cleaned_companies:
        cleaned_companies = [user_input]

    cleaned_companies = cleaned_companies[:2]

    memory: Dict[str, Any] = {
        "query": user_input,
        "plan": plan,
        "steps": [
            {
                "tool": "planner",
                "output": plan,
            }
        ],
        "bundles": [],
    }

    for item in cleaned_companies:
        try:
            bundle = build_research_bundle(item)
            memory["bundles"].append(bundle)
            memory["steps"].append(
                {
                    "tool": "build_research_bundle",
                    "input": item,
                    "output": {
                        "ticker": bundle["meta"]["ticker"],
                        "company_name": bundle["meta"]["company_name"],
                        "matched_by": bundle["meta"].get("matched_by"),
                    },
                }
            )
        except Exception as exc:
            memory["steps"].append(
                {
                    "tool": "build_research_bundle",
                    "input": item,
                    "error": str(exc),
                }
            )

    if not memory["bundles"]:
        raise RuntimeError("The agent could not build any research bundles.")

    memory["final_report"] = generate_report_from_memory(memory)
    return memory