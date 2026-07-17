"""Curated multi-domain dashboard watchlist.

20 marquee names across the sectors people actually track, scored daily and
shown on the Dashboard grouped by domain. This is separate from the oversold
scanner — it's a "how do the leaders look today" board, not a crash screen.
"""
from __future__ import annotations

# Ordered so the dashboard renders domains in a sensible sequence.
DOMAINS: dict[str, list[str]] = {
    "AI": ["NVDA", "PLTR", "AI", "SMCI", "ARM"],
    "Semiconductors": ["AMD", "AVGO", "TSM", "MU", "QCOM", "LRCX"],
    "FAANG / Mega-cap": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NFLX"],
    "Energy": ["XOM", "CVX", "FSLR", "ENPH"],
    "EV / Auto": ["TSLA", "RIVN"],
    "Fintech / Crypto": ["COIN", "HOOD", "XYZ", "PYPL"],  # XYZ = Block (ex-SQ)
    "Enterprise Software": ["CRM", "NOW", "SNOW", "PANW"],
    "Healthcare / Pharma": ["LLY", "UNH", "JNJ", "PFE"],
    "Defense / Aerospace": ["LMT", "RTX", "NOC"],
    "Retail / Consumer": ["WMT", "COST", "TGT"],
}


def all_tickers() -> list[str]:
    return [t for tickers in DOMAINS.values() for t in tickers]
