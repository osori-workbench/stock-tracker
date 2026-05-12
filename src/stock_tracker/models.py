from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class IndexSnapshot:
    name: str
    value: float
    change_value: float
    change_percent: float


@dataclass(slots=True)
class ExchangeRateSnapshot:
    name: str
    value: float
    change_value: float
    direction: str
    source: str


@dataclass(slots=True)
class InvestorSnapshot:
    basis_label: str
    individual: int
    foreign: int
    institution: int
    financial_investment: int
    insurance: int
    trust_private: int
    bank: int
    other_financial: int
    pension: int
    other_corporation: int


@dataclass(slots=True)
class TopStock:
    code: str
    name: str
    price: float
    change_percent: float


@dataclass(slots=True)
class BriefingData:
    mode: str
    now: datetime
    market_label: str
    indices: list[IndexSnapshot]
    exchange_rate: ExchangeRateSnapshot | None
    investors: InvestorSnapshot
    leaders: list[TopStock] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
