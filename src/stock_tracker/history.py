from __future__ import annotations

import sqlite3
import statistics
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

from stock_tracker.calendar import KST
from stock_tracker.models import DailyBar, InvestorSnapshot, MonthlyFlows, MonthlySummary

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "stock_tracker.db"
MONTH_TRADING_DAYS = 21  # 종가 21개 = 약 20거래일 수익률
MIN_DAYS_FOR_SUMMARY = 5

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_prices (
    date TEXT NOT NULL, symbol TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL NOT NULL, volume REAL,
    PRIMARY KEY (date, symbol)
);
CREATE TABLE IF NOT EXISTS investor_flows (
    date TEXT NOT NULL, market TEXT NOT NULL,
    individual INTEGER, foreign_ INTEGER, institution INTEGER,
    PRIMARY KEY (date, market)
);
CREATE TABLE IF NOT EXISTS reviews (
    date TEXT NOT NULL, mode TEXT NOT NULL, text TEXT NOT NULL,
    PRIMARY KEY (date, mode)
);
"""


class HistoryClient(Protocol):
    def fetch_index_history(self, code: str) -> list[DailyBar]: ...
    def fetch_fx_history(self, pages: int = 2) -> list[DailyBar]: ...


class HistoryStore:
    def __init__(self, path: str | Path = DEFAULT_DB_PATH) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.executescript(SCHEMA)

    def upsert_prices(self, symbol: str, bars: list[DailyBar]) -> None:
        self.conn.executemany(
            "INSERT OR REPLACE INTO daily_prices(date, symbol, open, high, low, close, volume) VALUES (?,?,?,?,?,?,?)",
            [(b.date, symbol, b.open, b.high, b.low, b.close, b.volume) for b in bars],
        )
        self.conn.commit()

    def get_bars(self, symbol: str, limit: int = MONTH_TRADING_DAYS, until: str | None = None) -> list[DailyBar]:
        query = "SELECT date, open, high, low, close, volume FROM daily_prices WHERE symbol=?"
        params: list = [symbol]
        if until:
            query += " AND date<=?"
            params.append(until)
        query += " ORDER BY date DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [DailyBar(*row) for row in reversed(rows)]

    def upsert_flow(self, day: str, market: str, investor: InvestorSnapshot) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO investor_flows(date, market, individual, foreign_, institution) VALUES (?,?,?,?,?)",
            (day, market, investor.individual, investor.foreign, investor.institution),
        )
        self.conn.commit()

    def get_flows(self, market: str, limit: int = MONTH_TRADING_DAYS) -> list[tuple[str, int, int, int]]:
        rows = self.conn.execute(
            "SELECT date, individual, foreign_, institution FROM investor_flows WHERE market=? ORDER BY date DESC LIMIT ?",
            (market, limit),
        ).fetchall()
        return list(reversed(rows))

    def save_review(self, day: str, mode: str, text: str) -> None:
        self.conn.execute("INSERT OR REPLACE INTO reviews(date, mode, text) VALUES (?,?,?)", (day, mode, text))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()


def summarize_bars(symbol: str, bars: list[DailyBar]) -> MonthlySummary | None:
    """최근 약 1개월 일봉으로 월간 지표를 계산한다."""
    if len(bars) < MIN_DAYS_FOR_SUMMARY:
        return None
    closes = [b.close for b in bars]
    first, last = closes[0], closes[-1]
    highs = [b.high if b.high is not None else b.close for b in bars]
    lows = [b.low if b.low is not None else b.close for b in bars]
    high, low = max(highs), min(lows)
    returns = [(closes[i] / closes[i - 1] - 1) * 100 for i in range(1, len(closes))]
    peak, max_dd = closes[0], 0.0
    for price in closes:
        peak = max(peak, price)
        max_dd = min(max_dd, (price / peak - 1) * 100)
    ma5 = sum(closes[-5:]) / min(5, len(closes))
    ma20 = sum(closes[-20:]) / min(20, len(closes))
    volumes = [b.volume for b in bars if b.volume]
    volume_ratio = None
    if len(volumes) >= 10:
        recent = sum(volumes[-5:]) / 5
        volume_ratio = round((recent / (sum(volumes) / len(volumes)) - 1) * 100, 1)
    range_span = high - low
    summary = MonthlySummary(
        symbol=symbol,
        start_date=bars[0].date,
        end_date=bars[-1].date,
        days=len(bars),
        start_close=first,
        end_close=last,
        return_pct=round((last / first - 1) * 100, 2),
        high=high,
        low=low,
        from_high_pct=round((last / high - 1) * 100, 2),
        from_low_pct=round((last / low - 1) * 100, 2),
        range_position_pct=round((last - low) / range_span * 100, 1) if range_span else 50.0,
        volatility_pct=round(statistics.pstdev(returns), 2) if len(returns) >= 2 else 0.0,
        max_drawdown_pct=round(max_dd, 2),
        up_days=sum(1 for r in returns if r > 0),
        down_days=sum(1 for r in returns if r < 0),
        vs_ma5_pct=round((last / ma5 - 1) * 100, 2),
        vs_ma20_pct=round((last / ma20 - 1) * 100, 2),
        recent_volume_vs_avg_pct=volume_ratio,
        last_day_change_pct=round(returns[-1], 2),
        trend_label="",
    )
    summary.trend_label = classify_trend(summary)
    return summary


def classify_trend(s: MonthlySummary) -> str:
    """월간 흐름을 한 줄 라벨로 분류한다(해석의 출발점일 뿐 최종 판단은 리뷰 생성기가 한다)."""
    if s.return_pct >= 3:
        if s.from_high_pct <= -5:
            return "한 달 상승 추세 속 고점 대비 조정 구간"
        return "한 달 상승 추세 지속"
    if s.return_pct <= -3:
        if s.from_low_pct >= 5:
            return "한 달 하락 추세 속 저점 대비 기술적 반등 구간"
        return "한 달 하락 추세 지속"
    if s.volatility_pct >= 1.5:
        return "방향 없이 변동성만 큰 박스권"
    return "한 달 횡보 구간"


def summarize_flows(rows: list[tuple[str, int, int, int]]) -> MonthlyFlows | None:
    if len(rows) < 2:
        return None
    return MonthlyFlows(
        days=len(rows),
        start_date=rows[0][0],
        end_date=rows[-1][0],
        individual=sum(r[1] for r in rows),
        foreign=sum(r[2] for r in rows),
        institution=sum(r[3] for r in rows),
        foreign_buy_days=sum(1 for r in rows if r[2] > 0),
    )


@dataclass(slots=True)
class HistoryService:
    store: HistoryStore
    client: HistoryClient

    SYMBOLS = ("KOSPI", "KOSDAQ", "USDKRW")

    def sync(self, mode: str, today: date) -> None:
        """일봉을 DB에 upsert한다. 마감 전 모드에서는 미확정인 오늘 봉을 저장하지 않는다."""
        today_key = today.strftime("%Y%m%d")
        final_today = mode == "close" or (mode == "review" and datetime.now(KST).hour >= 16)
        for code in ("KOSPI", "KOSDAQ"):
            self.store.upsert_prices(code, self._filter(self.client.fetch_index_history(code), today_key, final_today))
        self.store.upsert_prices("USDKRW", self._filter(self.client.fetch_fx_history(), today_key, final_today))

    @staticmethod
    def _filter(bars: list[DailyBar], today_key: str, final_today: bool) -> list[DailyBar]:
        return [b for b in bars if b.date < today_key or (final_today and b.date == today_key)]

    def record_close(self, day: date, investor: InvestorSnapshot | None) -> None:
        if investor is not None:
            self.store.upsert_flow(day.strftime("%Y%m%d"), "KOSPI", investor)

    def monthly(self, today: date) -> tuple[list[MonthlySummary], MonthlyFlows | None]:
        until = today.strftime("%Y%m%d")
        summaries = []
        for symbol in self.SYMBOLS:
            summary = summarize_bars(symbol, self.store.get_bars(symbol, until=until))
            if summary is not None:
                summaries.append(summary)
        return summaries, summarize_flows(self.store.get_flows("KOSPI"))
