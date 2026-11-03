from datetime import date, datetime
from zoneinfo import ZoneInfo

from stock_tracker.app import Collector, run_mode
from stock_tracker.history import HistoryService, HistoryStore, summarize_bars
from stock_tracker.llm import ReviewResult, build_user_prompt
from stock_tracker.models import BriefingData, DailyBar, ExchangeRateSnapshot, IndexSnapshot
from stock_tracker.naver import parse_fx_prices, parse_index_chart


def make_bars(closes, start=1):
    return [
        DailyBar(date=f"202610{start + i:02d}", open=c, high=c * 1.01, low=c * 0.99, close=c, volume=1000 + i)
        for i, c in enumerate(closes)
    ]


def test_summarize_bars_detects_pullback_in_uptrend():
    closes = [100 + i * 2 for i in range(15)] + [124, 120, 116, 113, 112]
    summary = summarize_bars("KOSPI", make_bars(closes))
    assert summary is not None
    assert summary.return_pct == 12.0
    assert summary.from_high_pct < -5
    assert summary.trend_label == "한 달 상승 추세 속 고점 대비 조정 구간"
    assert summary.up_days + summary.down_days == 19


def test_summarize_bars_requires_minimum_history():
    assert summarize_bars("KOSPI", make_bars([1, 2, 3])) is None


def test_store_upsert_is_idempotent_and_ordered():
    store = HistoryStore(":memory:")
    store.upsert_prices("KOSPI", make_bars([10, 11, 12]))
    store.upsert_prices("KOSPI", make_bars([10, 11, 13]))
    bars = store.get_bars("KOSPI")
    assert [b.close for b in bars] == [10, 11, 13]


def test_parsers():
    bars = parse_index_chart({"priceInfos": [{"localDate": "20261001", "closePrice": 1.5, "openPrice": 1, "highPrice": 2, "lowPrice": 1, "accumulatedTradingVolume": 5}]})
    assert bars[0].date == "20261001" and bars[0].volume == 5
    fx = parse_fx_prices([{"localTradedAt": "2026-11-03", "closePrice": "1,341.10"}])
    assert fx[0].date == "20261103" and fx[0].close == 1341.10


class FakeClient:
    def fetch_index_history(self, code):
        return make_bars([100 + i for i in range(10)], start=1)

    def fetch_fx_history(self, pages=2):
        return make_bars([1300 + i for i in range(10)], start=1)

    def fetch_index(self, code):
        return IndexSnapshot(name=code, value=110.0, change_value=1.0, change_percent=0.9)

    def fetch_exchange_rate(self):
        return ExchangeRateSnapshot(name="USD/KRW", value=1300.0, change_value=1.0, direction="상승", source="x")


class FakeSlack:
    def __init__(self):
        self.messages = []

    def send(self, payload):
        self.messages.append(payload)


class FakeReviewer:
    def __init__(self):
        self.seen = []

    def generate(self, data):
        self.seen.append(data)
        return ReviewResult(points=["한 달 상승 추세입니다."], bias="상방 우위", action="보유", confidence=3, strategy="유지")


def test_review_mode_syncs_history_and_prompts_with_monthly_context():
    client = FakeClient()
    history = HistoryService(store=HistoryStore(":memory:"), client=client)
    slack, reviewer = FakeSlack(), FakeReviewer()
    now = datetime(2026, 10, 12, 16, 30, tzinfo=ZoneInfo("Asia/Seoul"))
    assert run_mode("review", now=now, collector=Collector(client=client), slack=slack, reviewer=reviewer, history=history)
    data = reviewer.seen[0]
    assert {s.symbol for s in data.monthly} == {"KOSPI", "KOSDAQ", "USDKRW"}
    assert "monthly_context" in build_user_prompt(data)
    assert "한 달 종합 리뷰" in str(slack.messages[0])
    assert history.store.conn.execute("SELECT count(*) FROM reviews").fetchone()[0] == 1


def test_history_failure_does_not_block_briefing():
    class Broken(FakeClient):
        def fetch_index_history(self, code):
            raise RuntimeError("boom")

    history = HistoryService(store=HistoryStore(":memory:"), client=Broken())
    slack = FakeSlack()
    now = datetime(2026, 10, 12, 16, 30, tzinfo=ZoneInfo("Asia/Seoul"))
    assert run_mode("review", now=now, collector=Collector(client=FakeClient()), slack=slack, reviewer=FakeReviewer(), history=history)
    assert slack.messages
