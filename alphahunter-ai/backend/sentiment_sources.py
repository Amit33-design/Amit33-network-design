"""Multi-source sentiment — the signal with the best evidence, widened.

`analyze_signals.py` measured every sub-score against realized forward returns
across 1,845 samples. Sentiment was the strongest single predictor found
(r = +0.216), well ahead of momentum, which was slightly negative. That is the
justification for this module: the best-performing input in the system was
being computed from exactly two fields of one source — the analyst consensus
rating and the mean price target — while everything else about how the market
feels about a name went unused.

Five independent sources, each scored on its own and each explaining itself:

  1. CONSENSUS      what analysts rate it, weighted by how many are covering.
  2. REVISIONS      whether those ratings are being RAISED or CUT. Revision
                    direction is a different signal from revision level, and
                    historically the more useful of the two — a stock being
                    upgraded from Hold is a different animal from one being
                    quietly cut from Strong Buy to Buy.
  3. TARGETS        whether the price target itself is moving up or down.
  4. INSIDERS       whether the people who run the company are buying it.
  5. SHORT INTEREST how crowded the bearish side is, and which way it's moving.
  6. NEWS TONE      the language of recent headlines.

Everything here is a pure function over already-fetched data, so the whole
engine is testable offline. Fetching lives in `backend/utils/market_data.py`
and the serverless functions.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Signal:
    """One sentiment source's read: a -100..+100 tilt plus why."""
    name: str
    score: float                      # -100 (max bearish) .. +100 (max bullish)
    confidence: float                 # 0..1 — how much data was behind it
    factors: list[str] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return self.confidence > 0


def _clamp(v: float, lo: float = -100.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _none(name: str, why: str) -> Signal:
    return Signal(name, 0.0, 0.0, [why])


# --------------------------------------------------------------------------
# 1. Analyst consensus
# --------------------------------------------------------------------------
def consensus_signal(info: dict) -> Signal:
    """Rating level, discounted when barely anyone covers the name.

    A 1.5 "strong buy" from two analysts is not the same evidence as a 1.5
    from thirty, and treating them alike is how thinly-covered microcaps end
    up looking like high-conviction ideas.
    """
    rec = info.get("recommendationMean")
    if rec is None:
        return _none("consensus", "no analyst consensus published")
    n = info.get("numberOfAnalystOpinions") or 0

    # Map 1 (strong buy) .. 5 (sell) onto +100 .. -100, centred on 3 = hold.
    score = _clamp((3.0 - float(rec)) / 2.0 * 100.0)
    # Full weight around 15+ analysts, heavily discounted below 5.
    confidence = min(1.0, (float(n) / 15.0) ** 0.5) if n else 0.35

    label = ("strong buy" if rec <= 1.8 else "buy" if rec <= 2.5
             else "hold" if rec < 3.5 else "sell")
    detail = f"{label} consensus ({rec:.2f})"
    detail += f" from {int(n)} analysts" if n else " (coverage count unknown)"
    if n and n < 5:
        detail += " — thin coverage, discounted"
    return Signal("consensus", score, confidence, [detail])


# --------------------------------------------------------------------------
# 2. Revision momentum
# --------------------------------------------------------------------------
def revision_signal(periods: list[dict]) -> Signal:
    """Which way ratings are MOVING, from the ratings-breakdown history.

    ``periods`` is Yahoo's recommendation summary: one row per period
    ("0m" = current month, "-1m", "-2m", "-3m") with strongBuy/buy/hold/
    sell/strongSell counts. Direction is the point — the level is already
    covered by `consensus_signal`, and double-counting it would just weight
    the same opinion twice.
    """
    def mean_rating(row: dict) -> float | None:
        w = {"strongBuy": 1, "buy": 2, "hold": 3, "sell": 4, "strongSell": 5}
        total = sum(float(row.get(k) or 0) for k in w)
        if total <= 0:
            return None
        return sum(float(row.get(k) or 0) * v for k, v in w.items()) / total

    rows = {str(r.get("period", "")).lower(): r for r in (periods or [])}
    now, then = rows.get("0m"), rows.get("-3m") or rows.get("-2m") or rows.get("-1m")
    if not now or not then:
        return _none("revisions", "no ratings history to compare")

    a, b = mean_rating(now), mean_rating(then)
    if a is None or b is None:
        return _none("revisions", "ratings history has no counts")

    # A FALLING mean rating means upgrades (1 is best), so flip the sign.
    delta = b - a
    score = _clamp(delta * 200.0)          # 0.5 of a notch ⇒ ±100
    confidence = min(1.0, sum(float(now.get(k) or 0) for k in
                              ("strongBuy", "buy", "hold", "sell", "strongSell")) / 10.0)
    if abs(delta) < 0.02:
        return Signal("revisions", 0.0, confidence,
                      [f"ratings steady at {a:.2f}"])
    direction = "upgraded" if delta > 0 else "cut"
    return Signal("revisions", score, confidence,
                  [f"ratings {direction}: {b:.2f} → {a:.2f} over the last quarter"])


# --------------------------------------------------------------------------
# 3. Price-target drift
# --------------------------------------------------------------------------
def target_signal(info: dict, last_price: float | None) -> Signal:
    """Upside to target, sanity-checked against the spread of targets.

    Trading ABOVE the mean target was the single worst cohort in the realized
    track record (-16.9% vs -5.2%), so it is scored as a genuine negative
    rather than a shrug.
    """
    target = info.get("targetMeanPrice")
    if not target or not last_price:
        return _none("targets", "no price target published")

    upside = (float(target) - last_price) / last_price * 100.0
    # 40% upside ⇒ roughly full marks; above target ⇒ negative.
    score = _clamp(upside / 40.0 * 100.0)
    factors = [f"{upside:+.0f}% to the ${float(target):.2f} mean target"]

    lo, hi = info.get("targetLowPrice"), info.get("targetHighPrice")
    confidence = 0.6
    if lo and hi and float(hi) > float(lo) and last_price:
        spread = (float(hi) - float(lo)) / last_price * 100.0
        # A 200%-wide spread means the analysts do not agree on anything.
        confidence = max(0.2, min(1.0, 1.0 - spread / 200.0))
        if spread > 120:
            factors.append(f"but targets range ${float(lo):.0f}–${float(hi):.0f} — little agreement")
    if upside < 0:
        factors.append("already above the mean target — historically the worst cohort")
    return Signal("targets", score, confidence, factors)


# --------------------------------------------------------------------------
# 4. Insider activity
# --------------------------------------------------------------------------
def insider_signal(purchases: dict | None) -> Signal:
    """Net insider buying over the recent window.

    Insider BUYING is the informative half. Selling happens for tax,
    diversification and scheduled-plan reasons that have nothing to do with
    the outlook, so it is treated as weak evidence rather than a mirror image.
    """
    if not purchases:
        return _none("insiders", "no insider data")
    bought = float(purchases.get("bought_shares") or 0)
    sold = float(purchases.get("sold_shares") or 0)
    if bought <= 0 and sold <= 0:
        return _none("insiders", "no insider transactions on file")

    net = bought - sold
    total = bought + sold
    ratio = net / total if total else 0.0
    # Buying counts full; selling is damped to a third.
    score = _clamp(ratio * 100.0 if ratio > 0 else ratio * 33.0)
    confidence = min(1.0, total / 200_000.0)
    if net > 0:
        detail = f"insiders net buyers ({bought:,.0f} bought vs {sold:,.0f} sold)"
    else:
        detail = f"insiders net sellers ({sold:,.0f} sold vs {bought:,.0f} bought) — weak evidence, selling has many innocent reasons"
    return Signal("insiders", score, confidence, [detail])


# --------------------------------------------------------------------------
# 5. Short interest
# --------------------------------------------------------------------------
def short_interest_signal(info: dict) -> Signal:
    """How crowded the bearish side is, and which way it is moving.

    Deliberately two-sided. A heavily shorted name is under real pressure, but
    it is also fuel — so the LEVEL is scored mildly negative while a falling
    short base (shorts covering) is scored positive.
    """
    pct = info.get("shortPercentOfFloat")
    now = info.get("sharesShort")
    prior = info.get("sharesShortPriorMonth")
    if pct is None and now is None:
        return _none("short_interest", "no short-interest data")

    factors, score, confidence = [], 0.0, 0.5
    if pct is not None:
        p = float(pct) * 100.0
        score -= _clamp(max(0.0, p - 5.0) / 20.0 * 60.0, 0, 60)
        factors.append(f"{p:.1f}% of float short")
        confidence = 0.8

    if now and prior and float(prior) > 0:
        change = (float(now) - float(prior)) / float(prior) * 100.0
        score += _clamp(-change / 25.0 * 40.0, -40, 40)
        if abs(change) >= 5:
            factors.append(
                f"short base {'shrank' if change < 0 else 'grew'} {abs(change):.0f}% month over month")
    return Signal("short_interest", _clamp(score), confidence,
                  factors or ["short interest flat"])


# --------------------------------------------------------------------------
# 6. News tone
# --------------------------------------------------------------------------
# A small finance-specific lexicon. General-purpose sentiment word lists are
# actively wrong on markets: "cut" is bad, "beat" is good, and "liability" is
# neutral accounting rather than a threat.
_POS = {
    "beat", "beats", "surge", "surges", "surged", "soar", "soars", "rally",
    "rallies", "upgrade", "upgrades", "upgraded", "raise", "raises", "raised",
    "record", "outperform", "strong", "growth", "wins", "win", "awarded",
    "contract", "approval", "approved", "expands", "expansion", "profit",
    "profitable", "buyback", "dividend", "partnership", "breakthrough", "tops",
}
_NEG = {
    "miss", "misses", "missed", "plunge", "plunges", "plunged", "slump",
    "slumps", "downgrade", "downgrades", "downgraded", "cut", "cuts", "slash",
    "slashes", "warns", "warning", "probe", "investigation", "lawsuit", "sues",
    "recall", "delay", "delays", "delayed", "halt", "halted", "bankruptcy",
    "layoffs", "fraud", "scandal", "weak", "loss", "losses", "resigns",
    "resignation", "dilution", "offering", "short-seller", "subpoena",
}


def news_tone_signal(headlines: list[str]) -> Signal:
    """Lexicon tone over recent headlines.

    Blunt on purpose: headline counting cannot read nuance, so it is reported
    with modest confidence and never dominates. Its job is to catch the case
    where the tape and the analysts disagree with what is actually being
    written about a company.
    """
    heads = [h for h in (headlines or []) if h and isinstance(h, str)]
    if not heads:
        return _none("news", "no recent headlines")

    pos = neg = 0
    hit_examples: list[str] = []
    for h in heads:
        words = {w.strip(".,:;!?()[]\"'").lower() for w in h.split()}
        p, n = len(words & _POS), len(words & _NEG)
        pos += p
        neg += n
        if (p or n) and len(hit_examples) < 2:
            hit_examples.append(h[:70])

    total = pos + neg
    if total == 0:
        return Signal("news", 0.0, 0.25, [f"{len(heads)} headlines, none with clear tone"])

    score = _clamp((pos - neg) / total * 100.0)
    # Confidence grows with how many headlines carried any tone at all.
    confidence = min(0.7, total / 12.0)
    lean = "positive" if score > 15 else "negative" if score < -15 else "mixed"
    factors = [f"{len(heads)} recent headlines lean {lean} ({pos} positive / {neg} negative words)"]
    factors += [f"e.g. \"{e}\"" for e in hit_examples[:1]]
    return Signal("news", score, confidence, factors)


# --------------------------------------------------------------------------
# Composite
# --------------------------------------------------------------------------
# How much each source is trusted. Consensus and revisions lead because the
# analyst channel is what the +0.216 correlation was actually measuring;
# news tone is deliberately small because a lexicon cannot read nuance.
SOURCE_WEIGHTS = {
    "consensus": 0.26,
    "revisions": 0.24,
    "targets": 0.20,
    "insiders": 0.13,
    "short_interest": 0.10,
    "news": 0.07,
}


def composite_sentiment(signals: list[Signal]) -> dict:
    """Blend the available sources into a 0..100 score.

    Weights are re-normalised over whatever is actually available, so a name
    with no insider data is not silently pushed toward neutral by a missing
    input — a common way for multi-source scores to quietly become mush.
    """
    present = [s for s in signals if s.available]
    if not present:
        return {
            "score": 50.0, "tilt": 0.0, "coverage": 0.0,
            "sources": {}, "factors": ["no sentiment data available"],
        }

    total_w = sum(SOURCE_WEIGHTS.get(s.name, 0.0) * s.confidence for s in present)
    if total_w <= 0:
        return {"score": 50.0, "tilt": 0.0, "coverage": 0.0, "sources": {},
                "factors": ["sentiment sources present but carry no confidence"]}

    tilt = sum(s.score * SOURCE_WEIGHTS.get(s.name, 0.0) * s.confidence
               for s in present) / total_w

    factors: list[str] = []
    for s in sorted(present, key=lambda x: -abs(x.score * x.confidence)):
        factors += s.factors[:1]

    return {
        # -100..+100 tilt mapped onto the 0..100 the scoring layer expects.
        "score": round(_clamp(50.0 + tilt / 2.0, 0.0, 100.0), 1),
        "tilt": round(tilt, 1),
        # How much of the possible evidence we actually had.
        "coverage": round(total_w / sum(SOURCE_WEIGHTS.values()), 2),
        "sources": {s.name: {"score": round(s.score, 1),
                             "confidence": round(s.confidence, 2),
                             "why": s.factors} for s in signals},
        "factors": factors[:5],
    }
