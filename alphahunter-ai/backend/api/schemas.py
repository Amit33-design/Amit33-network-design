"""Pydantic request/response models for the REST API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ScanQuery(BaseModel):
    require_all: bool = True
    limit: int | None = Field(default=None, ge=1, le=5000)
    tickers: list[str] | None = None


class PositionIn(BaseModel):
    ticker: str
    quantity: float = Field(gt=0)
    cost_basis: float = Field(ge=0)


class PortfolioIn(BaseModel):
    positions: list[PositionIn]


class QueryIn(BaseModel):
    query: str
    limit: int | None = Field(default=200, ge=1, le=5000)
