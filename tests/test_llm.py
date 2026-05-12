from datetime import datetime
from zoneinfo import ZoneInfo

from stock_tracker.llm import OpenAIReviewGenerator
from stock_tracker.models import BriefingData, ExchangeRateSnapshot, IndexSnapshot, InvestorSnapshot, TopStock


KST = ZoneInfo("Asia/Seoul")


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def post(self, url: str, *, headers: dict, json: dict, timeout: int) -> FakeResponse:
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse(self.payload)


def make_data() -> BriefingData:
    return BriefingData(
        mode="close",
        now=datetime(2026, 5, 12, 15, 40, tzinfo=KST),
        market_label="마감 후",
        indices=[
            IndexSnapshot(name="KOSPI", value=2640.15, change_value=-11.09, change_percent=-0.42),
            IndexSnapshot(name="KOSDAQ", value=845.29, change_value=2.05, change_percent=0.24),
        ],
        exchange_rate=ExchangeRateSnapshot(name="USD/KRW", value=1388.70, change_value=3.7, direction="상승", source="하나은행"),
        investors=InvestorSnapshot(
            basis_label="15:40",
            individual=-1200,
            foreign=900,
            institution=300,
            financial_investment=100,
            insurance=50,
            trust_private=25,
            bank=10,
            other_financial=5,
            pension=80,
            other_corporation=-20,
        ),
        leaders=[
            TopStock(code="005930", name="삼성전자", price=81200.0, change_percent=1.22),
            TopStock(code="000660", name="SK하이닉스", price=213500.0, change_percent=2.81),
        ],
    )


def test_openai_review_generator_parses_bullets_and_builds_prompt() -> None:
    session = FakeSession(
        {
            "choices": [
                {
                    "message": {
                        "content": "- 외국인과 기관이 동반 순매수라 수급의 질이 괜찮습니다.\n- 환율 상승은 부담이지만 반도체 대형주가 지수를 지지합니다.\n- 추격매수보다 주도주 지속성 확인이 더 중요합니다."
                    }
                }
            ]
        }
    )
    generator = OpenAIReviewGenerator(api_key="test-key", session=session, model="gpt-4.1-mini")

    review = generator.generate(make_data())

    assert review == [
        "외국인과 기관이 동반 순매수라 수급의 질이 괜찮습니다.",
        "환율 상승은 부담이지만 반도체 대형주가 지수를 지지합니다.",
        "추격매수보다 주도주 지속성 확인이 더 중요합니다.",
    ]
    assert session.calls[0]["url"] == "https://api.openai.com/v1/chat/completions"
    assert session.calls[0]["headers"]["Authorization"] == "Bearer test-key"
    user_prompt = session.calls[0]["json"]["messages"][1]["content"]
    assert "KOSPI" in user_prompt
    assert "삼성전자" in user_prompt
    assert "JSON 데이터" in user_prompt
