from datetime import datetime
from zoneinfo import ZoneInfo

from stock_tracker.app import run_mode
from stock_tracker.models import BriefingData, ExchangeRateSnapshot, IndexSnapshot, InvestorSnapshot


KST = ZoneInfo("Asia/Seoul")


class FakeCollector:
    def __init__(self, payload: BriefingData):
        self.payload = payload
        self.calls = []

    def collect(self, mode: str, now: datetime) -> BriefingData:
        self.calls.append((mode, now))
        return self.payload


class FakeSlack:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    def send(self, payload: dict) -> None:
        self.messages.append(payload)


def make_payload() -> BriefingData:
    return BriefingData(
        mode="open",
        now=datetime(2026, 5, 12, 9, 10, tzinfo=KST),
        market_label="개장 직후",
        indices=[IndexSnapshot(name="KOSPI", value=2600.0, change_value=5.0, change_percent=0.19)],
        exchange_rate=ExchangeRateSnapshot(name="USD/KRW", value=1400.5, change_value=4.2, direction="상승", source="하나은행"),
        investors=InvestorSnapshot(
            basis_label="09:10",
            individual=1200,
            foreign=-900,
            institution=-200,
            financial_investment=-100,
            insurance=-50,
            trust_private=-25,
            bank=0,
            other_financial=-5,
            pension=-20,
            other_corporation=-100,
        ),
        leaders=[],
        notes=[],
        sources=["test"],
    )


def test_run_mode_skips_when_market_closed() -> None:
    collector = FakeCollector(make_payload())
    slack = FakeSlack()

    sent = run_mode(
        mode="open",
        now=datetime(2026, 5, 10, 9, 10, tzinfo=KST),
        collector=collector,
        slack=slack,
    )

    assert sent is False
    assert collector.calls == []
    assert slack.messages == []


def test_run_mode_sends_message_when_market_open() -> None:
    collector = FakeCollector(make_payload())
    slack = FakeSlack()

    sent = run_mode(
        mode="open",
        now=datetime(2026, 5, 12, 9, 10, tzinfo=KST),
        collector=collector,
        slack=slack,
    )

    assert sent is True
    assert len(collector.calls) == 1
    assert len(slack.messages) == 1
    assert "국장 오픈 10분" in slack.messages[0]["text"]
    assert slack.messages[0]["blocks"][0]["type"] == "header"
