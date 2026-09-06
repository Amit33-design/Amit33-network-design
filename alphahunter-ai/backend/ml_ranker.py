#!/usr/bin/env python3
"""Learned ranker — does a fitted model beat the hand-tuned score?

`analyze_signals.py` reweighted the composite score one feature at a time,
using each feature's own correlation with forward returns. That ignores how
features interact and how they overlap: two correlated signals both get full
credit. A fitted model handles both.

Two rules govern this module, and they are the point of it:

1. **Nothing ships on faith.** The model is trained on the EARLIER half of the
   scan history and scored on the LATER half it has never seen, against the
   existing rule-based score on those same rows. If it does not win
   out-of-sample it does not ship, and `evaluate()` says so.
2. **Nothing ships opaque.** CODE.md forbids adding a signal a user cannot
   see the reasoning for. So the model is a ridge regression on standardized
   features, where a prediction decomposes exactly into per-feature
   contributions (coefficient x standardized value). `explain()` turns those
   into the plain-English "what the model liked and disliked" lines the rest
   of the product already promises. A gradient-boosted model is fitted too,
   but only as a yardstick: if the trees beat the linear model by a wide
   margin, that is evidence worth reporting, not a reason to ship a black box.

    python -m backend.ml_ranker

Reads only committed scan history — no network.
"""
from __future__ import annotations

import json
import os

from .analyze_signals import load_samples

FEATURES = (
    "technical", "fundamental", "options", "momentum", "sentiment",
    "expected_gain_%",
)
MIN_SAMPLES = 60          # below this, any "finding" is noise
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_matrix(
    samples: list[dict],
) -> tuple[list[list[float]], list[float], list[str], list[int]]:
    """Feature matrix, labels, row dates, and the indices of the samples kept.

    The kept indices matter: rows are dropped when a feature is missing, so the
    baseline score has to be gathered through the same filter or the comparison
    silently misaligns (it did, on the first run — the baseline came back None).
    """
    X, y, dates, keep = [], [], [], []
    for idx, s in enumerate(samples):
        subs = s.get("subscores") or {}
        row, ok = [], True
        for f in FEATURES:
            v = s.get(f) if f not in subs else subs.get(f)
            if v is None:
                ok = False
                break
            row.append(float(v))
        if ok and s.get("forward_%") is not None and s.get("date"):
            X.append(row)
            y.append(float(s["forward_%"]))
            dates.append(s["date"])
            keep.append(idx)
    return X, y, dates, keep


def _split(dates: list[str]) -> tuple[list[int], list[int]]:
    """Chronological halves. Time-series data must never be split randomly —
    a random split leaks the future into training via same-day rows."""
    uniq = sorted(set(dates))
    if len(uniq) < 4:
        return [], []
    cut = uniq[len(uniq) // 2]
    train = [i for i, d in enumerate(dates) if d < cut]
    test = [i for i, d in enumerate(dates) if d >= cut]
    return train, test


def _rank_ic(pred: list[float], actual: list[float]) -> float | None:
    """Spearman rank correlation — the right metric for a *ranker*, which only
    has to order names correctly, not predict the return itself."""
    from scipy.stats import spearmanr

    if len(pred) < 3:
        return None
    r = spearmanr(pred, actual).statistic
    return None if r != r else round(float(r), 4)  # NaN-safe


def evaluate(samples: list[dict]) -> dict:
    """Fit on the earlier half, score on the later half, compare to the score."""
    import numpy as np
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.linear_model import RidgeCV
    from sklearn.preprocessing import StandardScaler

    X, y, dates, keep = build_matrix(samples)
    if len(X) < MIN_SAMPLES:
        return {"error": f"only {len(X)} usable samples, need {MIN_SAMPLES}"}
    tr, te = _split(dates)
    if not tr or not te:
        return {"error": "not enough distinct scan dates to split chronologically"}

    Xa, ya = np.array(X, dtype=float), np.array(y, dtype=float)
    scaler = StandardScaler().fit(Xa[tr])
    Xtr, Xte = scaler.transform(Xa[tr]), scaler.transform(Xa[te])

    ridge = RidgeCV(alphas=(0.1, 1.0, 10.0, 100.0)).fit(Xtr, ya[tr])
    gbm = GradientBoostingRegressor(
        n_estimators=150, max_depth=2, learning_rate=0.05, random_state=0
    ).fit(Xtr, ya[tr])

    # The incumbent: the shipped composite score, on exactly the held-out rows
    # the model was scored on (gathered through `keep`, so it stays aligned).
    baseline = [samples[keep[i]].get("score") for i in range(len(X))]
    base_ic = (None if any(b is None for b in baseline)
               else _rank_ic([baseline[i] for i in te], list(ya[te])))

    ridge_ic = _rank_ic(list(ridge.predict(Xte)), list(ya[te]))
    gbm_ic = _rank_ic(list(gbm.predict(Xte)), list(ya[te]))

    coefs = {f: round(float(c), 4) for f, c in zip(FEATURES, ridge.coef_)}

    # A rank IC has a standard error of roughly 1/sqrt(n-1). On ~900 rows that
    # is about 0.033, so anything inside +/-0.067 is indistinguishable from
    # noise no matter how suggestive the sign looks. The first version of this
    # gate only asked "does the model beat the baseline?", which would have
    # shipped a model whose own IC was NEGATIVE simply because the incumbent
    # was more negative. Being less wrong than a broken ruler is not an edge.
    se = round(1.0 / ((len(te) - 1) ** 0.5), 4) if len(te) > 2 else None
    noise_floor = round(2 * se, 4) if se else None

    def significant(ic: float | None) -> bool:
        return ic is not None and noise_floor is not None and abs(ic) > noise_floor

    beats = bool(
        ridge_ic is not None
        and ridge_ic > 0                 # must actually rank the right way up
        and significant(ridge_ic)        # must be beyond the noise floor
        # ...and must not be worse than the incumbent. An unmeasurable
        # baseline (a constant score) can't veto a genuine edge, but it
        # can't excuse a weak one either — the two checks above still apply.
        and (base_ic is None or ridge_ic > base_ic)
    )

    return {
        "samples": len(X), "train": len(tr), "test": len(te),
        "split_date": sorted(set(dates))[len(set(dates)) // 2],
        "baseline_rank_ic": base_ic,
        "ridge_rank_ic": ridge_ic,
        "gbm_rank_ic": gbm_ic,
        "ridge_coefficients": coefs,
        "ridge_intercept": round(float(ridge.intercept_), 4),
        "feature_means": {f: round(float(m), 4) for f, m in zip(FEATURES, scaler.mean_)},
        "feature_scales": {f: round(float(s), 4) for f, s in zip(FEATURES, scaler.scale_)},
        "rank_ic_standard_error": se,
        "noise_floor": noise_floor,
        "baseline_significant": significant(base_ic),
        "ridge_significant": significant(ridge_ic),
        "gbm_significant": significant(gbm_ic),
        # The verdict. Everything above is evidence for this one boolean.
        "ships": beats,
        "verdict": (
            f"ridge ranks correctly and beyond the noise floor out-of-sample "
            f"(IC {ridge_ic} vs composite {base_ic}, floor +/-{noise_floor}) — worth blending"
            if beats else
            f"nothing ships: on {len(te)} held-out rows the composite scores "
            f"IC {base_ic}, ridge {ridge_ic}, GBM {gbm_ic} — all inside the "
            f"+/-{noise_floor} noise floor, so none of them demonstrably ranks "
            f"future returns on this window"
        ),
        "caveat": (
            "Forward returns are reconstructed from re-appearances in the scan "
            "history, so the horizon varies per row and the sample is biased "
            "toward names that keep screening. Treat these ICs as a filter for "
            "obviously-bad ideas, not as a measurement of live performance."
        ),
    }


def explain(model: dict, subscores: dict, expected_gain: float | None,
            top: int = 3) -> list[str]:
    """Plain-English per-pick reasons: the largest signed contributions.

    A ridge prediction is exactly the sum of coefficient x standardized
    feature, so these lines are the model's actual arithmetic, not a
    post-hoc story about it.
    """
    coefs = model.get("ridge_coefficients") or {}
    means, scales = model.get("feature_means") or {}, model.get("feature_scales") or {}
    parts = []
    for f in FEATURES:
        raw = subscores.get(f) if f in subscores else (
            expected_gain if f == "expected_gain_%" else None)
        c, m, sc = coefs.get(f), means.get(f), scales.get(f)
        if raw is None or c is None or m is None or not sc:
            continue
        parts.append((c * ((float(raw) - m) / sc), f, float(raw)))
    parts.sort(key=lambda p: -abs(p[0]))
    label = {"expected_gain_%": "expected gain"}
    return [
        f"{'+' if v > 0 else '−'} {label.get(f, f)} at {raw:.1f} "
        f"({'helps' if v > 0 else 'hurts'} the ranking)"
        for v, f, raw in parts[:top] if abs(v) > 1e-9
    ]


def main() -> None:  # pragma: no cover - manual entrypoint
    out = evaluate(load_samples())
    print(json.dumps(out, indent=2))
    path = os.path.join(_ROOT, "results", "ml_ranker_eval.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote {path}")


if __name__ == "__main__":  # pragma: no cover
    main()
