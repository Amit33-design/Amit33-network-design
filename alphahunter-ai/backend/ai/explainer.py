"""Natural-language explanation layer.

The composite engine already produces a transparent, rule-based explanation.
This module optionally polishes it into prose via the OpenAI API when
OPENAI_API_KEY is set — and answers the spec's free-text queries
("What should I buy today?", "Explain why this stock scored 94.").

Without a key it returns the deterministic rule-based text, so the platform is
fully functional offline.
"""
from __future__ import annotations

from backend.config import settings


def explain_recommendation(rec: dict) -> str:
    base = rec.get("reasoning", "")
    if not settings.openai_api_key:
        return base
    try:  # pragma: no cover - external API
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        prompt = (
            "You are a trading assistant. In 3-4 sentences, explain this "
            "screening result to a retail investor. Be specific about the "
            "numbers and end with the single biggest risk. Do not give "
            f"financial advice.\n\nData:\n{rec}"
        )
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return base


def answer_query(query: str, results: list[dict]) -> dict:
    """Tiny intent router over an already-computed result set (spec Future AI)."""
    q = query.lower()
    if "covered call" in q:
        picks = [r for r in results if r.get("covered_call")][:5]
    elif "csp" in q or "cash secured put" in q:
        picks = sorted(
            [r for r in results if r.get("cash_secured_put")],
            key=lambda r: r["subscores"].get("options", 0), reverse=True,
        )[:5]
    elif "oversold" in q:
        picks = [r for r in results if (r["metrics"].get("rsi") or 100) < 35][:5]
    elif "buy" in q:
        picks = [r for r in results if r["action"] in ("Buy", "Accumulate")][:5]
    else:
        picks = results[:5]
    return {"query": query, "matches": picks}
