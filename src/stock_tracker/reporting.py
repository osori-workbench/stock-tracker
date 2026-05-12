from __future__ import annotations

from stock_tracker.models import BriefingData, ExchangeRateSnapshot, IndexSnapshot, InvestorSnapshot, TopStock

MODE_TITLES = {
    "open": "국장 오픈 10분",
    "noon": "국장 장중 정오 리뷰",
    "close": "국장 마감 리뷰",
}

NAVER_ITEM_URL = "https://finance.naver.com/item/main.naver?code={code}"
NAVER_INDEX_URL = "https://finance.naver.com/sise/sise_index.naver"
NAVER_USD_KRW_URL = "https://finance.naver.com/marketindex/exchangeDetail.naver?marketindexCd=FX_USDKRW"


def format_eok_to_jo(value: int) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value / 10000:.2f}조"


def format_index_line(index: IndexSnapshot) -> str:
    return f"*{index.name}* {index.value:,.2f} ({index.change_percent:+.2f}%, {index.change_value:+,.2f})"


def format_exchange_rate_line(rate: ExchangeRateSnapshot) -> str:
    return f"<{NAVER_USD_KRW_URL}|{rate.name}> {rate.value:,.2f}원 ({rate.direction} {rate.change_value:.2f})"


def build_stock_link(stock: TopStock) -> str:
    return f"<{NAVER_ITEM_URL.format(code=stock.code)}|{stock.name}>"


def build_summary_text(data: BriefingData) -> str:
    title = MODE_TITLES[data.mode]
    return f"[{title} | {data.now.strftime('%Y-%m-%d %H:%M')} KST]"


def infer_market_temperature(data: BriefingData) -> str:
    avg_drop = sum(index.change_percent for index in data.indices) / max(len(data.indices), 1)
    has_inverse_leaders = any("인버스" in stock.name for stock in data.leaders)
    investor = data.investors

    if avg_drop <= -1.5 and has_inverse_leaders:
        return "단순 과열보다는 하락 방어·헤지 성격이 강합니다."
    if avg_drop >= 1.5 and investor.foreign > 0 and investor.institution > 0:
        return "단기 과열 가능성은 있지만 외국인·기관 동행이라 추세형 강세에 가깝습니다."
    if investor.individual > 0 and investor.foreign < 0 and investor.institution < 0:
        return "개인 저가매수와 기관·외국인 차익실현이 충돌하는 구간입니다."
    return "추세가 한쪽으로 강하게 기울지 않아 추가 확인이 필요한 장세입니다."


def build_review_points(data: BriefingData) -> list[str]:
    investor = data.investors
    points: list[str] = []

    if investor.individual > 0 and investor.foreign < 0 and investor.institution < 0:
        points.append("외국인·기관이 함께 매도하고 개인만 크게 받아낸 날입니다.")
    elif investor.foreign > 0 and investor.institution > 0:
        points.append("외국인과 기관이 동반 순매수해 수급 질이 비교적 좋은 편입니다.")
    elif investor.foreign < 0 and investor.institution < 0:
        points.append("외국인·기관 동반 매도로 지수 반등 신뢰도는 낮아 보입니다.")

    if any("인버스" in stock.name for stock in data.leaders):
        points.append("인버스 ETF가 거래 상위에 올라 하락 방어·헤지 수요가 강하게 붙었습니다.")
    elif any(stock.change_percent >= 8 for stock in data.leaders):
        points.append("상승률이 큰 종목으로 거래가 쏠려 단기 과열 심리가 일부 반영됐습니다.")

    biggest_drop = min((index.change_percent for index in data.indices), default=0)
    if biggest_drop <= -2:
        points.append("지수 낙폭이 커서 공격적 추격매수보다 변동성 관리가 우선인 흐름입니다.")
    elif biggest_drop >= 1:
        points.append("지수 강세가 이어져 추격매수보다 주도주 지속성 확인이 중요합니다.")

    points.append(infer_market_temperature(data))
    return points[:4]


def build_market_overview_block(data: BriefingData) -> dict:
    investor = data.investors
    index_lines = "\n".join(
        f"• {format_index_line(index)}" for index in data.indices
    )
    rate_line = format_exchange_rate_line(data.exchange_rate) if data.exchange_rate else "집계 실패"
    fields = [
        {"type": "mrkdwn", "text": f"*시장 상태*\n{data.market_label}"},
        {"type": "mrkdwn", "text": f"*수급*\n개인 {format_eok_to_jo(investor.individual)} / 외국인 {format_eok_to_jo(investor.foreign)} / 기관 {format_eok_to_jo(investor.institution)}"},
        {"type": "mrkdwn", "text": f"*지수*\n{index_lines}"},
        {"type": "mrkdwn", "text": f"*환율*\n{rate_line}"},
        {"type": "mrkdwn", "text": f"*기관 세부*\n금융투자 {format_eok_to_jo(investor.financial_investment)}\n보험 {format_eok_to_jo(investor.insurance)}\n투신(사모) {format_eok_to_jo(investor.trust_private)}\n연기금 {format_eok_to_jo(investor.pension)}"},
    ]
    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*시장 한눈에 보기*\n<{NAVER_INDEX_URL}|네이버 증권 지수 페이지> 기준입니다."},
        "fields": fields,
    }


def build_leaders_block(data: BriefingData) -> dict | None:
    if not data.leaders:
        return None
    lines = [
        f"• {build_stock_link(stock)} · {stock.price:,.0f}원 · {stock.change_percent:+.2f}%"
        for stock in data.leaders
    ]
    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text": "*거래 상위 관심종목*\n" + "\n".join(lines)},
    }


def build_review_block(data: BriefingData, review_points: list[str] | None = None) -> dict:
    points = review_points or build_review_points(data)
    lines = [f"• {point}" for point in points]
    if data.notes:
        lines.append(f"• 참고: {' / '.join(data.notes)}")
    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text": "*종합 리뷰*\n" + "\n".join(lines)},
    }


def build_briefing_payload(data: BriefingData, review_points: list[str] | None = None) -> dict:
    summary = build_summary_text(data)
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": summary, "emoji": True}},
        build_market_overview_block(data),
    ]
    leaders_block = build_leaders_block(data)
    if leaders_block is not None:
        blocks.append(leaders_block)
    blocks.extend(
        [
            build_review_block(data, review_points=review_points),
            {"type": "divider"},
        ]
    )
    return {"text": summary, "blocks": blocks}
