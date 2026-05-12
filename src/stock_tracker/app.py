from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from stock_tracker.calendar import KST, is_market_session_open
from stock_tracker.models import BriefingData
from stock_tracker.naver import NaverClient
from stock_tracker.reporting import build_briefing_payload
from stock_tracker.slack import SlackWebhookClient

MODE_LABELS = {
    "open": "개장 직후",
    "noon": "개장 중",
    "close": "마감 후",
}


@dataclass(slots=True)
class Collector:
    client: NaverClient

    def collect(self, mode: str, now: datetime) -> BriefingData:
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
) -> bool:
    current = now or datetime.now(tz=KST)
    if current.tzinfo is None:
        current = current.replace(tzinfo=ZoneInfo("Asia/Seoul"))
    if not is_market_session_open(current):
        return False

    if collector is None or slack is None:
        raise ValueError('collector and slack must be provided')

    briefing = collector.collect(mode, current)
    payload = build_briefing_payload(briefing)
    slack.send(payload)
    return True
