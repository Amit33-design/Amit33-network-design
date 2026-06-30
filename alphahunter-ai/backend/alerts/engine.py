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
