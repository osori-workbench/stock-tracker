from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


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
class OptionExpiryInfo:
    next_expiry: date
    days_until: int
    is_today: bool
    is_this_week: bool
    is_quarterly_witching: bool
    label: str


@dataclass(slots=True)
class DailyBar:
    date: str  # YYYYMMDD
    open: float | None
    high: float | None
    low: float | None
    close: float
    volume: float | None = None


@dataclass(slots=True)
class MonthlySummary:
    symbol: str
    start_date: str
    end_date: str
    days: int
    start_close: float
    end_close: float
    return_pct: float
    high: float
    low: float
    from_high_pct: float
    from_low_pct: float
    range_position_pct: float
    volatility_pct: float
    max_drawdown_pct: float
    up_days: int
    down_days: int
    vs_ma5_pct: float
    vs_ma20_pct: float
    recent_volume_vs_avg_pct: float | None
    last_day_change_pct: float
    trend_label: str


@dataclass(slots=True)
class MonthlyFlows:
    days: int
    start_date: str
    end_date: str
    individual: int
    foreign: int
    institution: int
    foreign_buy_days: int


@dataclass(slots=True)
class BriefingData:
    mode: str
    now: datetime
    market_label: str
    indices: list[IndexSnapshot]
    exchange_rate: ExchangeRateSnapshot | None
    investors: InvestorSnapshot | None = None
    leaders: list[TopStock] = field(default_factory=list)
    option_expiry: OptionExpiryInfo | None = None
    notes: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    global_markets: list[IndexSnapshot] = field(default_factory=list)
    headlines: list[str] = field(default_factory=list)
    oil_markets: list[IndexSnapshot] = field(default_factory=list)
    oil_headlines: list[str] = field(default_factory=list)
    monthly: list[MonthlySummary] = field(default_factory=list)
    monthly_flows: MonthlyFlows | None = None
