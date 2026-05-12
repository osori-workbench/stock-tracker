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


def make_morning_data() -> BriefingData:
    return BriefingData(
        mode="morning",
        now=datetime(2026, 5, 13, 8, 0, tzinfo=KST),
        market_label="장 시작 전",
        indices=[
            IndexSnapshot(name="KOSPI", value=2625.40, change_value=-12.50, change_percent=-0.47),
            IndexSnapshot(name="KOSDAQ", value=845.20, change_value=-3.10, change_percent=-0.37),
        ],
        exchange_rate=ExchangeRateSnapshot(name="USD/KRW", value=1396.20, change_value=5.20, direction="상승", source="하나은행"),
        investors=None,
        leaders=[],
        notes=["미국장은 전일 마감 기준입니다."],
        sources=["Yahoo Finance chart API", "Google News RSS", "Naver marketindex"],
        global_markets=[
            IndexSnapshot(name="S&P 500", value=5234.2, change_value=-42.1, change_percent=-0.80),
            IndexSnapshot(name="NASDAQ", value=16320.4, change_value=-210.3, change_percent=-1.27),
            IndexSnapshot(name="SOX", value=4782.1, change_value=-115.4, change_percent=-2.36),
            IndexSnapshot(name="미국 10년물", value=4.48, change_value=0.07, change_percent=1.59),
            IndexSnapshot(name="달러인덱스", value=105.2, change_value=0.6, change_percent=0.57),
        ],
        headlines=[
            "미 연준 인사 발언 이후 금리 인하 기대가 후퇴했습니다.",
            "미 반도체주 약세로 나스닥 변동성이 확대됐습니다.",
            "달러 강세가 이어지며 신흥국 증시 부담이 커졌습니다.",
        ],
        oil_markets=[
            IndexSnapshot(name="WTI", value=77.2, change_value=1.4, change_percent=1.85),
            IndexSnapshot(name="브렌트", value=81.6, change_value=1.1, change_percent=1.37),
        ],
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


def test_build_briefing_payload_shows_fallback_notice_when_present() -> None:
    payload = build_briefing_payload(
        make_data(),
        review_points=["외국인과 기관 동반 매도가 이어졌습니다."],
        fallback_notice="추론이 실패해서 규칙기반으로 나온 리뷰입니다.",
    )
    blocks_text = "\n".join(
        item["text"]
        for block in payload["blocks"]
        for item in block.get("fields", []) + ([block["text"]] if "text" in block else [])
        if isinstance(item, dict) and item.get("type") == "mrkdwn"
    )

    assert "추론이 실패해서 규칙기반으로 나온 리뷰입니다." in blocks_text
    assert "외국인과 기관 동반 매도가 이어졌습니다." in blocks_text


def test_build_morning_briefing_payload_groups_overnight_news_and_oil() -> None:
    payload = build_briefing_payload(
        make_morning_data(),
        review_points=[
            "미국 기술주 약세와 금리 상승이 겹쳐 오늘 국장 대형주에는 부담이 예상됩니다.",
            "환율까지 오르면 외국인 수급이 보수적으로 움직일 가능성을 봐야 합니다.",
        ],
        strategy="오늘은 관망 위주로 보되 눌림이 와도 소액 분할만 고려하겠습니다.",
    )
    blocks_text = "\n".join(
        item["text"]
        for block in payload["blocks"]
        for item in block.get("fields", []) + ([block["text"]] if "text" in block else [])
        if isinstance(item, dict) and item.get("type") == "mrkdwn"
    )

    assert payload["text"].startswith("[장 시작 전 브리핑 | 2026-05-13 08:00 KST]")
    assert "*밤사이 미장 체크*" in blocks_text
    assert "*핵심 뉴스*" in blocks_text
    assert "*오늘 국내장 예상*" in blocks_text
    assert "*원유 추가 브리핑*" in blocks_text
    assert "S&P 500" in blocks_text
    assert "미 연준 인사 발언 이후 금리 인하 기대가 후퇴했습니다." in blocks_text
    assert "WTI" in blocks_text
    assert "브렌트" in blocks_text
    assert "미국 기술주 약세와 금리 상승이 겹쳐 오늘 국장 대형주에는 부담이 예상됩니다." in blocks_text
    assert "*한줄 전략*" in blocks_text
    assert "관망" in blocks_text
