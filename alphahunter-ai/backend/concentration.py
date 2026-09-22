"""How many independent bets is a list of picks, really?

A board of eight names looks diversified. If five of them are semiconductors
it is closer to two positions, and the day the sector sells off they all go
together. Nothing in this product has ever said so — every screen ranks names
on their own merits and presents the result as a list, which quietly implies
the entries are independent.

The headline is the EFFECTIVE NUMBER OF BETS: the inverse Herfindahl index
over sector weights, 1 / Σ(wᵢ²). It is the standard measure and it answers the
question directly — eight picks that are 62% one sector score about 2.3, and
"eight names, but really about two bets" is a sentence a reader can act on in
a way that "62% technology" is not.

Deliberately NOT a filter. A concentrated list can be exactly right when one
sector is where the opportunity is; the failure is not knowing. So this
reports and flags, and never drops a pick.

Pure functions over (ticker, sector) pairs. No network.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

# Above this share of a list, one sector dominates it.
CONCENTRATED_SHARE = 0.40
# Below this many effective bets, the list is not the diversification it looks.
LOW_EFFECTIVE_BETS = 3.0
UNKNOWN = "Unclassified"


@dataclass
class Concentration:
    count: int
    effective_bets: float
    top_sector: str | None
    top_sector_share: float
    by_sector: list[dict] = field(default_factory=list)
    concentrated: bool = False
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "effective_bets": self.effective_bets,
            "top_sector": self.top_sector,
            "top_sector_share": self.top_sector_share,
            "by_sector": self.by_sector,
            "concentrated": self.concentrated,
            "note": self.note,
        }


def analyse(picks: list[tuple[str, str | None]]) -> Concentration:
    """``picks`` is (ticker, sector) pairs. Duplicate tickers count once."""
    seen: dict[str, str] = {}
    for ticker, sector in picks:
        if not ticker:
            continue
        seen.setdefault(ticker.upper(), (sector or UNKNOWN).strip() or UNKNOWN)

    n = len(seen)
    if n == 0:
        return Concentration(0, 0.0, None, 0.0, note="no picks to analyse")
    if n == 1:
        only = next(iter(seen.values()))
        return Concentration(1, 1.0, only, 1.0,
                             [{"sector": only, "count": 1, "share": 1.0}],
                             True, "A single pick is a single bet.")

    counts = Counter(seen.values())
    by_sector = [
        {"sector": s, "count": c, "share": round(c / n, 3)}
        for s, c in counts.most_common()
    ]
    # Inverse Herfindahl over sector weights.
    hhi = sum((c / n) ** 2 for c in counts.values())
    effective = round(1 / hhi, 2) if hhi > 0 else float(n)
    top_sector, top_count = counts.most_common(1)[0]
    top_share = round(top_count / n, 3)

    concentrated = top_share >= CONCENTRATED_SHARE or effective < LOW_EFFECTIVE_BETS

    if not concentrated:
        note = (f"{n} picks spread across {len(counts)} sectors — about "
                f"{effective:g} independent bets.")
    elif top_sector == UNKNOWN:
        # Being unable to classify is not the same as being concentrated, and
        # saying "62% Unclassified" as though it were a sector is nonsense.
        note = (f"{top_count} of {n} picks could not be classified, so how "
                f"concentrated this list is cannot be judged.")
    else:
        note = (f"{n} picks, but {top_count} of them are {top_sector} "
                f"({top_share * 100:.0f}%) — about {effective:g} independent bets. "
                f"If {top_sector} sells off, most of this list goes together.")

    return Concentration(n, effective, top_sector, top_share, by_sector,
                         concentrated, note)


def from_records(records: list[dict], sectors: dict[str, dict]) -> Concentration:
    """Convenience: pull sectors out of a profiles map for a list of picks."""
    pairs = []
    for r in records or []:
        t = (r.get("ticker") or "").upper()
        if not t:
            continue
        prof = sectors.get(t) or {}
        # The scan's own rel_strength carries a sector too; either will do.
        sector = prof.get("sector") or (r.get("rel_strength") or {}).get("sector")
        pairs.append((t, sector))
    return analyse(pairs)
