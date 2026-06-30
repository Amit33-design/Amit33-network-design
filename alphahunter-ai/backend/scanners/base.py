"""Scanner abstractions.

A scanner turns a ``StockSnapshot`` into an optional ``ScanHit`` — a dict of
metrics plus a list of which named criteria passed/failed. Keeping the
pass/fail breakdown is what makes every recommendation explainable downstream.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from backend.utils.market_data import StockSnapshot


@dataclass
class Criterion:
    name: str
    passed: bool
    detail: str


@dataclass
class ScanHit:
    ticker: str
    metrics: dict
    criteria: list[Criterion] = field(default_factory=list)

    @property
    def passed_all(self) -> bool:
        return all(c.passed for c in self.criteria)

    @property
    def passed_names(self) -> list[str]:
        return [c.name for c in self.criteria if c.passed]

    @property
    def failed_names(self) -> list[str]:
        return [c.name for c in self.criteria if not c.passed]


class Scanner(Protocol):
    name: str

    def evaluate(self, snap: StockSnapshot) -> ScanHit | None:
        ...
