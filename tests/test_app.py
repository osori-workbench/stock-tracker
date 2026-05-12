from datetime import datetime
from zoneinfo import ZoneInfo

from stock_tracker.app import run_mode
from stock_tracker.llm import ReviewResult
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


class FakeReviewer:
    def __init__(self, result: ReviewResult) -> None:
        self.result = result
        self.calls: list[BriefingData] = []

    def generate(self, data: BriefingData) -> ReviewResult:
        self.calls.append(data)
        return self.result


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


def make_morning_payload() -> BriefingData:
    return BriefingData(
        mode="morning",
        now=datetime(2026, 5, 13, 8, 0, tzinfo=KST),
        market_label="장 시작 전",
        indices=[
            IndexSnapshot(name="KOSPI", value=2625.4, change_value=-12.5, change_percent=-0.47),
            IndexSnapshot(name="KOSDAQ", value=845.2, change_value=-3.1, change_percent=-0.37),
        ],
        exchange_rate=ExchangeRateSnapshot(name="USD/KRW", value=1396.2, change_value=5.2, direction="상승", source="하나은행"),
        investors=None,
        leaders=[],
        notes=["미국장은 전일 마감 기준입니다."],
        sources=["test"],
        global_markets=[
            IndexSnapshot(name="S&P 500", value=5234.2, change_value=-42.1, change_percent=-0.80),
            IndexSnapshot(name="NASDAQ", value=16320.4, change_value=-210.3, change_percent=-1.27),
            IndexSnapshot(name="미국 10년물", value=4.48, change_value=0.07, change_percent=1.59),
        ],
        headlines=[
            "미 연준 인사 발언 이후 금리 인하 기대가 후퇴했습니다.",
            "미 반도체주가 약세를 보이며 나스닥 변동성이 확대됐습니다.",
        ],
        oil_markets=[
            IndexSnapshot(name="WTI", value=77.2, change_value=1.4, change_percent=1.85),
            IndexSnapshot(name="브렌트", value=81.6, change_value=1.1, change_percent=1.37),
        ],
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


def test_run_mode_uses_reviewer_output_when_provided() -> None:
    collector = FakeCollector(make_payload())
    slack = FakeSlack()
    reviewer = FakeReviewer(
        ReviewResult(
            points=[
                "외국인 매수 우위가 지수 방어에 기여했습니다.",
                "환율 부담은 있지만 급격한 리스크오프 해석까지는 아닙니다.",
            ],
            strategy="제 기준이면 오늘은 관망 후 눌림에서만 소액 분할 매수를 보겠습니다.",
            fallback_notice=None,
        )
    )

    sent = run_mode(
        mode="open",
        now=datetime(2026, 5, 12, 9, 10, tzinfo=KST),
        collector=collector,
        slack=slack,
        reviewer=reviewer,
    )

    assert sent is True
    assert len(reviewer.calls) == 1
    review_block_text = slack.messages[0]["blocks"][-3]["text"]["text"]
    assert "외국인 매수 우위가 지수 방어에 기여했습니다." in review_block_text
    assert "환율 부담은 있지만 급격한 리스크오프 해석까지는 아닙니다." in review_block_text
    strategy_block_text = slack.messages[0]["blocks"][-2]["text"]["text"]
    assert "*한줄 전략*" in strategy_block_text
    assert "제 기준이면 오늘은 관망 후 눌림에서만 소액 분할 매수를 보겠습니다." in strategy_block_text


def test_run_mode_shows_fallback_notice_when_reviewer_fails() -> None:
    collector = FakeCollector(make_payload())
    slack = FakeSlack()
    reviewer = FakeReviewer(
        ReviewResult(
            points=[],
            fallback_notice="추론이 실패해서 규칙기반으로 나온 리뷰입니다.",
        )
    )

    sent = run_mode(
        mode="open",
        now=datetime(2026, 5, 12, 9, 10, tzinfo=KST),
        collector=collector,
        slack=slack,
        reviewer=reviewer,
    )

    assert sent is True
    review_block_text = slack.messages[0]["blocks"][-2]["text"]["text"]
    assert "추론이 실패해서 규칙기반으로 나온 리뷰입니다." in review_block_text
    assert "개인 저가매수와 기관·외국인 차익실현이 충돌하는 구간입니다." in review_block_text


def test_run_mode_sends_morning_briefing_before_market_open() -> None:
    collector = FakeCollector(make_morning_payload())
    slack = FakeSlack()
    reviewer = FakeReviewer(
        ReviewResult(
            points=[
                "미국 기술주 약세와 금리 상승이 겹쳐 오늘 국장 대형주에는 부담이 예상됩니다.",
                "환율까지 오르면 외국인 수급이 보수적으로 움직일 가능성을 봐야 합니다.",
            ],
            fallback_notice=None,
        )
    )

    sent = run_mode(
        mode="morning",
        now=datetime(2026, 5, 13, 8, 0, tzinfo=KST),
        collector=collector,
        slack=slack,
        reviewer=reviewer,
    )

    assert sent is True
    assert len(slack.messages) == 1
    assert "장 시작 전 브리핑" in slack.messages[0]["text"]
    blocks_text = "\n".join(
        item["text"]
        for block in slack.messages[0]["blocks"]
        for item in block.get("fields", []) + ([block["text"]] if "text" in block else [])
        if isinstance(item, dict) and item.get("type") == "mrkdwn"
    )
    assert "*밤사이 미장 체크*" in blocks_text
    assert "*오늘 국내장 예상*" in blocks_text
    assert "*원유 추가 브리핑*" in blocks_text
    assert "미국 기술주 약세와 금리 상승이 겹쳐 오늘 국장 대형주에는 부담이 예상됩니다." in blocks_text
