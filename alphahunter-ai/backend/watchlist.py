"""Curated multi-domain dashboard watchlist.

20 marquee names across the sectors people actually track, scored daily and
shown on the Dashboard grouped by domain. This is separate from the oversold
scanner — it's a "how do the leaders look today" board, not a crash screen.
"""
from __future__ import annotations

# Ordered so the dashboard renders domains in a sensible sequence.
DOMAINS: dict[str, list[str]] = {
    "AI": ["NVDA", "PLTR", "AI"],
    "Semiconductors": ["AMD", "AVGO", "TSM", "MU"],
    "FAANG / Mega-cap": ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
    "Energy": ["XOM", "CVX", "FSLR"],
    "EV / Auto": ["TSLA"],
    "Fintech / Crypto": ["COIN", "HOOD"],
    "Enterprise Software": ["CRM", "NOW"],
}


def all_tickers() -> list[str]:
    return [t for tickers in DOMAINS.values() for t in tickers]
