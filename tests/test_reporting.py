from datetime import datetime
from zoneinfo import ZoneInfo

from stock_tracker.models import BriefingData, IndexSnapshot, InvestorSnapshot, TopStock
from stock_tracker.reporting import build_briefing_text


KST = ZoneInfo("Asia/Seoul")


def test_build_briefing_text_renders_mode_and_key_sections() -> None:
    data = BriefingData(
        mode="noon",
        now=datetime(2026, 5, 12, 12, 0, tzinfo=KST),
        market_label="개장 중",
        indices=[
            IndexSnapshot(name="KOSPI", value=2601.25, change_value=15.12, change_percent=0.58),
            IndexSnapshot(name="KOSDAQ", value=845.77, change_value=-3.4, change_percent=-0.4),
        ],
        investors=InvestorSnapshot(
            basis_label="12:00",
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
            TopStock(code="005930", name="삼성전자", price=71200, change_percent=1.24),
            TopStock(code="000660", name="SK하이닉스", price=201500, change_percent=2.10),
        ],
        notes=["장중 수치는 잠정치일 수 있습니다."],
        sources=["Naver Finance polling API", "Naver Finance investorDealTrendTime"],
    )

    text = build_briefing_text(data)

    assert "[국장 장중 정오 리뷰 | 2026-05-12 12:00 KST]" in text
    assert "- 시장 상태: 개장 중" in text
    assert "- KOSPI: 2,601.25 (+0.58%" in text
    assert "- 수급: 개인 +6.68조 / 외국인 -5.61조 / 기관 -1.21조" in text
    assert "- 기관 세부: 금융투자 -0.62조" in text
    assert "- 거래 상위 관심종목: 삼성전자(+1.24%), SK하이닉스(+2.10%)" in text
    assert "- 참고: 장중 수치는 잠정치일 수 있습니다." in text
    assert "- 출처: Naver Finance polling API, Naver Finance investorDealTrendTime" in text
