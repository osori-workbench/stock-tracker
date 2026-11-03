from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from stock_tracker.calendar import KST, describe_option_expiry, is_market_session_open
from stock_tracker.history import HistoryService
from stock_tracker.llm import ReviewResult
from stock_tracker.models import BriefingData
from stock_tracker.naver import NaverClient
from stock_tracker.reporting import build_briefing_payload
from stock_tracker.slack import SlackWebhookClient

MODE_LABELS = {
    "morning": "장 시작 전",
    "open": "개장 직후",
    "noon": "개장 중",
    "close": "마감 후",
    "review": "월간 종합",
}


class ReviewGenerator(Protocol):
    def generate(self, data: BriefingData) -> ReviewResult: ...


@dataclass(slots=True)
class Collector:
    client: NaverClient

    def collect(self, mode: str, now: datetime) -> BriefingData:
        option_expiry = describe_option_expiry(now.date())
        if mode == "morning":
            return BriefingData(
                mode=mode,
                now=now,
                market_label=MODE_LABELS[mode],
                indices=[
                    self.client.fetch_index("KOSPI"),
                    self.client.fetch_index("KOSDAQ"),
                ],
                exchange_rate=self.client.fetch_exchange_rate(),
                investors=None,
                leaders=[],
                option_expiry=option_expiry,
                notes=["미국장은 전일 마감 기준입니다."],
                sources=[
                    "Yahoo Finance chart API",
                    "Google News RSS",
                    "Naver Finance marketindex",
                    "Naver Finance polling API",
                ],
                global_markets=self.client.fetch_global_markets(),
                headlines=self.client.fetch_global_headlines(limit=4),
                oil_markets=self.client.fetch_oil_markets(),
                oil_headlines=self.client.fetch_oil_headlines(limit=2),
            )

        if mode == "review":
            return BriefingData(
                mode=mode,
                now=now,
                market_label=MODE_LABELS[mode],
                indices=[
                    self.client.fetch_index("KOSPI"),
                    self.client.fetch_index("KOSDAQ"),
                ],
                exchange_rate=self.client.fetch_exchange_rate(),
                investors=None,
                option_expiry=option_expiry,
                sources=["Naver Finance index chart", "Naver Finance FX prices", "stock_tracker.db"],
            )

        intraday = mode in {"open", "noon"}
        return BriefingData(
            mode=mode,
            now=now,
            market_label=MODE_LABELS[mode],
            indices=[
                self.client.fetch_index("KOSPI"),
                self.client.fetch_index("KOSDAQ"),
            ],
            exchange_rate=self.client.fetch_exchange_rate(),
            investors=self.client.fetch_investors(now.date(), intraday=intraday),
            leaders=self.client.fetch_top_volume(limit=5),
            option_expiry=option_expiry,
            notes=["장중 수치는 잠정치일 수 있습니다."] if intraday else [],
            sources=[
                "Naver Finance polling API",
                "Naver Finance investorDealTrendTime" if intraday else "Naver Finance investorDealTrendDay",
                "Naver Finance sise_quant",
            ],
        )


def run_mode(
    mode: str,
    now: datetime | None = None,
    collector: Collector | None = None,
    slack: SlackWebhookClient | None = None,
    reviewer: ReviewGenerator | None = None,
    history: HistoryService | None = None,
) -> bool:
    current = now or datetime.now(tz=KST)
    if current.tzinfo is None:
        current = current.replace(tzinfo=ZoneInfo("Asia/Seoul"))
    if not is_market_session_open(current):
        return False

    if collector is None or slack is None:
        raise ValueError('collector and slack must be provided')

    briefing = collector.collect(mode, current)
    if history is not None:
        attach_monthly_context(briefing, history, mode, current)
    review_result = reviewer.generate(briefing) if reviewer is not None else None
    payload = build_briefing_payload(
        briefing,
        review_points=review_result.points if review_result is not None and review_result.points else None,
        strategy=review_result.strategy if review_result is not None else None,
        strategy_bias=review_result.bias if review_result is not None else None,
        strategy_action=review_result.action if review_result is not None else None,
        strategy_confidence=review_result.confidence if review_result is not None else None,
        fallback_notice=review_result.fallback_notice if review_result is not None else None,
    )
    slack.send(payload)
    if history is not None:
        _save_review_safely(history, mode, current, review_result)
    return True


def attach_monthly_context(briefing: BriefingData, history: HistoryService, mode: str, now: datetime) -> None:
    """일봉을 DB에 동기화하고 1개월 지표를 붙인다. 실패해도 브리핑은 계속 보낸다."""
    try:
        history.sync(mode, now.date())
        if mode == "close":
            history.record_close(now.date(), briefing.investors)
        briefing.monthly, briefing.monthly_flows = history.monthly(now.date())
        if briefing.monthly:
            briefing.sources.append("stock_tracker.db(1개월 일봉)")
    except Exception as exc:  # noqa: BLE001
        print(f"[history] skipped: {type(exc).__name__}: {exc}", flush=True)


def _save_review_safely(history: HistoryService, mode: str, now: datetime, result: ReviewResult | None) -> None:
    if result is None or not result.points:
        return
    try:
        history.store.save_review(now.strftime("%Y%m%d"), mode, "\n".join(result.points))
    except Exception as exc:  # noqa: BLE001
        print(f"[history] review save skipped: {type(exc).__name__}: {exc}", flush=True)
