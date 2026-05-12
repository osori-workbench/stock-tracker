from datetime import datetime
from zoneinfo import ZoneInfo

from stock_tracker.models import BriefingData, ExchangeRateSnapshot, IndexSnapshot, InvestorSnapshot, TopStock
from stock_tracker.reporting import build_briefing_payload


KST = ZoneInfo("Asia/Seoul")


def make_data() -> BriefingData:
    return BriefingData(
        mode="close",
        now=datetime(2026, 5, 12, 15, 40, tzinfo=KST),
        market_label="마감 후",
        indices=[
            IndexSnapshot(name="KOSPI", value=7643.15, change_value=-179.09, change_percent=-2.29),
            IndexSnapshot(name="KOSDAQ", value=1179.29, change_value=-28.05, change_percent=-2.32),
        ],
        exchange_rate=ExchangeRateSnapshot(name="USD/KRW", value=1488.70, change_value=13.70, direction="상승", source="하나은행"),
        investors=InvestorSnapshot(
            basis_label="15:58",
            individual=66821,
            foreign=-56092,
            institution=-12138,
            financial_investment=-6206,
            insurance=-1420,
            trust_private=-2476,
            bank=-110,
            other_financial=-70,
            pension=-1857,
            other_corporation=1409,
        ),
        leaders=[
            TopStock(code="252670", name="KODEX 200선물인버스2X", price=115.0, change_percent=4.55),
            TopStock(code="114800", name="KODEX 인버스", price=1121.0, change_percent=2.37),
            TopStock(code="003280", name="흥아해운", price=2780.0, change_percent=4.12),
        ],
        notes=["장중 수치는 잠정치일 수 있습니다."],
        sources=["Naver Finance polling API", "Naver Finance investorDealTrendTime"],
    )


def test_build_briefing_payload_uses_blocks_and_links() -> None:
    payload = build_briefing_payload(make_data())

    assert payload["text"].startswith("[국장 마감 리뷰 | 2026-05-12 15:40 KST]")
    assert payload["blocks"][0]["type"] == "header"
    assert payload["blocks"][1]["type"] == "section"

    blocks_text = "\n".join(
        item["text"]
        for block in payload["blocks"]
        for item in block.get("fields", []) + ([block["text"]] if "text" in block else [])
        if isinstance(item, dict) and item.get("type") == "mrkdwn"
    )
    assert "*시장 한눈에 보기*" in blocks_text
    assert "*종합 리뷰*" in blocks_text
    assert "*거래 상위 관심종목*" in blocks_text
    assert "<https://finance.naver.com/item/main.naver?code=252670|KODEX 200선물인버스2X>" in blocks_text
    assert "• <https://finance.naver.com/item/main.naver?code=003280|흥아해운>" in blocks_text


def test_build_briefing_payload_contains_interpretive_review_not_sources() -> None:
    payload = build_briefing_payload(make_data())
    blocks_text = "\n".join(
        item["text"]
        for block in payload["blocks"]
        for item in block.get("fields", []) + ([block["text"]] if "text" in block else [])
        if isinstance(item, dict) and item.get("type") == "mrkdwn"
    )

    assert "외국인·기관이 함께 매도하고 개인만 크게 받아낸 날" in blocks_text
    assert "인버스 ETF가 거래 상위" in blocks_text
    assert "단순 과열보다는 하락 방어·헤지 성격이 강합니다." in blocks_text
    assert "출처:" not in blocks_text


def test_build_briefing_payload_includes_exchange_rate_in_overview() -> None:
    payload = build_briefing_payload(make_data())
    blocks_text = "\n".join(
        item["text"]
        for block in payload["blocks"]
        for item in block.get("fields", []) + ([block["text"]] if "text" in block else [])
        if isinstance(item, dict) and item.get("type") == "mrkdwn"
    )

    assert "*환율*" in blocks_text
    assert "<https://finance.naver.com/marketindex/exchangeDetail.naver?marketindexCd=FX_USDKRW|USD/KRW> 1,488.70원 (상승 13.70)" in blocks_text


def test_build_briefing_payload_prefers_llm_review_points_when_provided() -> None:
    payload = build_briefing_payload(
        make_data(),
        review_points=[
            "외국인 중심 수급이 지수를 버티게 했습니다.",
            "환율 상승 부담은 남아 있어도 투매 해석까지는 아닙니다.",
        ],
    )
    blocks_text = "\n".join(
        item["text"]
        for block in payload["blocks"]
        for item in block.get("fields", []) + ([block["text"]] if "text" in block else [])
        if isinstance(item, dict) and item.get("type") == "mrkdwn"
    )

    assert "외국인 중심 수급이 지수를 버티게 했습니다." in blocks_text
    assert "환율 상승 부담은 남아 있어도 투매 해석까지는 아닙니다." in blocks_text
    assert "외국인·기관이 함께 매도하고 개인만 크게 받아낸 날" not in blocks_text
