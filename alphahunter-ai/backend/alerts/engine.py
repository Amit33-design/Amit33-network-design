"""Alert engine.

Dispatches alerts to configured channels (Slack / Discord webhooks, email,
push). Channels are optional: if a webhook isn't configured the alert is logged
and skipped rather than failing. Keeps a clean interface the scheduler calls.
"""
from __future__ import annotations

import json
import logging
from typing import Iterable

import requests

from backend.config import settings

log = logging.getLogger("alphahunter.alerts")

ALERT_TYPES = {
    "breakout", "oversold", "gap", "golden_cross", "iv_spike",
    "earnings_tomorrow", "covered_call", "cash_secured_put",
}


def _post(url: str, payload: dict) -> bool:
    try:
        resp = requests.post(url, data=json.dumps(payload),
                             headers={"Content-Type": "application/json"}, timeout=10)
        return resp.status_code < 300
    except Exception as e:  # pragma: no cover - network
        log.warning("alert post failed: %s", e)
        return False


def send_alert(alert_type: str, title: str, message: str,
               tickers: Iterable[str] | None = None) -> dict:
    tickers = list(tickers or [])
    text = f"*{title}*\n{message}" + (f"\nTickers: {', '.join(tickers)}" if tickers else "")
    delivered = []

    if settings.slack_webhook_url:
        if _post(settings.slack_webhook_url, {"text": text}):
            delivered.append("slack")
    if settings.discord_webhook_url:
        if _post(settings.discord_webhook_url, {"content": text}):
            delivered.append("discord")

    if not delivered:
        log.info("[ALERT:%s] %s — %s", alert_type, title, message)
        delivered.append("log")

    return {"type": alert_type, "delivered_to": delivered, "tickers": tickers}


def select_alert_worthy(recs: list[dict], limit: int = 5) -> list[dict]:
    """The subset of a scan worth pushing, chosen from realized ALPHA vs SPY.

    Two lessons from the track record are baked in here.

    1. Gate on what predicts returns. The original A/B-grade +
       High/Medium-confidence filter selected on attributes that don't:
       grade B was the worst cohort and confidence was inverted (Low beat
       High). Score is the predictive variable, so it gates; confidence
       doesn't gate at all.

    2. Tune the gate against the cohort it ACTUALLY selects. The 70+ score
       band looks bad on its own (-1.7% alpha) but that marginal mixes
       grades. Since grade A is also required, the real cohort is A · 70+:
       +0.5% alpha over 149 picks. A · 80+ is stronger still (+18.2%) but
       only 12 picks, so it is used as a conviction LABEL rather than a gate.

    Pure and offline so it stays unit-testable.
    """
    def ok(r: dict) -> bool:
        if (r.get("score") or 0) < settings.alert_min_score:
            return False
        if r.get("quality_grade") != "A":
            return False
        if r.get("rr_pass") is False:
            return False
        return True

    worthy = [r for r in recs if ok(r)]
    worthy.sort(key=lambda r: (r.get("score") or 0, r.get("expected_gain_%") or 0),
                reverse=True)
    return worthy[:limit]


def format_digest(date: str, picks: list[dict]) -> str:
    """Human-readable morning digest of the top setups (plain text / Slack md)."""
    if not picks:
        return f"AlphaHunter {date}: no A-grade setups above the score gate today."
    lines = [f"*AlphaHunter — top {len(picks)} setups for {date}*"]
    for i, r in enumerate(picks, 1):
        gain = r.get("expected_gain_%")
        gain_s = f"+{gain}% exp" if gain is not None else "—"
        csp = " 💰CSP" if (r.get("csp_signal") or {}).get("active") else ""
        # Flag the band with far stronger realized alpha so the reader can tell
        # a standout from a merely-qualifying pick at a glance.
        tier = ("⭐ HIGH CONVICTION "
                if (r.get("score") or 0) >= settings.alert_high_conviction_score else "")
        lines.append(
            f"{i}. {tier}{r['ticker']} — score {r.get('score')} · {r.get('quality_grade')} · "
            f"{r.get('action')} · {gain_s}{csp}"
        )
    return "\n".join(lines)


def send_scan_digest(date: str, recs: list[dict], limit: int = 5) -> dict:
    """Push the day's best setups to the configured channels (or log)."""
    picks = select_alert_worthy(recs, limit=limit)
    message = format_digest(date, picks)
    return send_alert(
        "scan_digest",
        f"AlphaHunter top setups — {date}",
        message,
        tickers=[r["ticker"] for r in picks],
    )

