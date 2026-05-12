from __future__ import annotations

from stock_tracker.models import BriefingData, ExchangeRateSnapshot, IndexSnapshot, InvestorSnapshot, TopStock

MODE_TITLES = {
    "morning": "장 시작 전 브리핑",
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
    if investor is None:
        return infer_morning_temperature(data)

    if avg_drop <= -1.5 and has_inverse_leaders:
        return "단순 과열보다는 하락 방어·헤지 성격이 강합니다."
    if avg_drop >= 1.5 and investor.foreign > 0 and investor.institution > 0:
        return "단기 과열 가능성은 있지만 외국인·기관 동행이라 추세형 강세에 가깝습니다."
    if investor.individual > 0 and investor.foreign < 0 and investor.institution < 0:
        return "개인 저가매수와 기관·외국인 차익실현이 충돌하는 구간입니다."
    return "추세가 한쪽으로 강하게 기울지 않아 추가 확인이 필요한 장세입니다."


def infer_morning_temperature(data: BriefingData) -> str:
    nasdaq = next((item for item in data.global_markets if item.name == "NASDAQ"), None)
    sox = next((item for item in data.global_markets if item.name == "SOX"), None)
    us10y = next((item for item in data.global_markets if item.name == "미국 10년물"), None)
    dxy = next((item for item in data.global_markets if item.name == "달러인덱스"), None)

    if nasdaq and sox and us10y and nasdaq.change_percent < 0 and sox.change_percent < 0 and us10y.change_value > 0:
        return "기술주와 금리가 동시에 부담을 줘 국장 성장주에는 보수적 접근이 유리해 보입니다."
    if nasdaq and dxy and nasdaq.change_percent > 0 and dxy.change_percent <= 0:
        return "위험선호가 살아 있어도 환율이 안정돼야 국내 반등 기대가 더 힘을 받을 수 있습니다."
    if dxy and dxy.change_percent > 0.3:
        return "달러 강세가 이어지면 지수 반등이 나와도 외국인 수급은 보수적으로 붙을 수 있습니다."
    return "밤사이 변수는 혼조라 장 초반에는 환율과 반도체 수급 확인이 특히 중요해 보입니다."


def build_review_points(data: BriefingData) -> list[str]:
    if data.mode == "morning":
        return build_morning_review_points(data)

    investor = data.investors
    if investor is None:
        return [infer_market_temperature(data)]

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


def build_morning_review_points(data: BriefingData) -> list[str]:
    points: list[str] = []
    nasdaq = next((item for item in data.global_markets if item.name == "NASDAQ"), None)
    sox = next((item for item in data.global_markets if item.name == "SOX"), None)
    us10y = next((item for item in data.global_markets if item.name == "미국 10년물"), None)

    if nasdaq and nasdaq.change_percent <= -1:
        points.append("나스닥 약세가 뚜렷해 오늘 국장에서는 성장주와 반도체 변동성 확대를 먼저 경계할 필요가 있습니다.")
    if sox and sox.change_percent <= -1:
        points.append("미국 반도체 약세가 이어졌다면 국내 대형 반도체가 지수 하방 압력을 먼저 받을 가능성을 봐야 합니다.")
    if us10y and us10y.change_value > 0:
        points.append("미국 금리가 다시 올라오면 밸류에이션 부담이 큰 종목군은 장 초반 매물이 나올 수 있습니다.")
    if data.exchange_rate and data.exchange_rate.direction == "상승":
        points.append("원달러 환율 상승이 이어지면 외국인 수급은 방어적으로 붙을 가능성이 높습니다.")

    points.append(infer_market_temperature(data))
    return points[:4]


def build_market_overview_block(data: BriefingData) -> dict:
    investor = data.investors
    if investor is None:
        raise ValueError("market overview block requires investor data")
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


def build_morning_domestic_block(data: BriefingData) -> dict:
    index_lines = "\n".join(f"• {format_index_line(index)}" for index in data.indices)
    rate_line = format_exchange_rate_line(data.exchange_rate) if data.exchange_rate else "집계 실패"
    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*국내 기준선*\n<{NAVER_INDEX_URL}|전일 국내 지수>와 환율 기준선입니다."},
        "fields": [
            {"type": "mrkdwn", "text": f"*전일 지수*\n{index_lines}"},
            {"type": "mrkdwn", "text": f"*환율*\n{rate_line}"},
        ],
    }


def build_global_markets_block(data: BriefingData) -> dict | None:
    if not data.global_markets:
        return None
    lines = "\n".join(f"• {format_index_line(item)}" for item in data.global_markets)
    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text": "*밤사이 미장 체크*\n" + lines},
    }


def build_headlines_block(title: str, headlines: list[str]) -> dict | None:
    if not headlines:
        return None
    lines = "\n".join(f"• {headline}" for headline in headlines)
    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*{title}*\n" + lines},
    }


def build_oil_block(data: BriefingData) -> dict | None:
    if not data.oil_markets and not data.oil_headlines:
        return None
    parts: list[str] = []
    if data.oil_markets:
        parts.extend(f"• {format_index_line(item)}" for item in data.oil_markets)
    if data.oil_headlines:
        parts.extend(f"• {headline}" for headline in data.oil_headlines)
    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text": "*원유 추가 브리핑*\n" + "\n".join(parts)},
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


def build_review_block(
    data: BriefingData,
    review_points: list[str] | None = None,
    fallback_notice: str | None = None,
    title: str = "종합 리뷰",
) -> dict:
    points = review_points or build_review_points(data)
    lines: list[str] = []
    if fallback_notice:
        lines.append(f"• {fallback_notice}")
    lines.extend(f"• {point}" for point in points)
    if data.notes:
        lines.append(f"• 참고: {' / '.join(data.notes)}")
    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*{title}*\n" + "\n".join(lines)},
    }


def build_strategy_block(strategy: str | None) -> dict | None:
    if not strategy:
        return None
    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text": "*한줄 전략*\n• " + strategy},
    }


def build_morning_briefing_payload(
    data: BriefingData,
    review_points: list[str] | None = None,
    strategy: str | None = None,
    fallback_notice: str | None = None,
) -> dict:
    summary = build_summary_text(data)
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": summary, "emoji": True}},
        build_morning_domestic_block(data),
    ]
    for block in [
        build_global_markets_block(data),
        build_headlines_block("핵심 뉴스", data.headlines),
        build_review_block(data, review_points=review_points, fallback_notice=fallback_notice, title="오늘 국내장 예상"),
        build_oil_block(data),
        build_strategy_block(strategy),
    ]:
        if block is not None:
            blocks.append(block)
    blocks.append({"type": "divider"})
    return {"text": summary, "blocks": blocks}


def build_briefing_payload(
    data: BriefingData,
    review_points: list[str] | None = None,
    strategy: str | None = None,
    fallback_notice: str | None = None,
) -> dict:
    if data.mode == "morning":
        return build_morning_briefing_payload(data, review_points=review_points, strategy=strategy, fallback_notice=fallback_notice)

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
            build_review_block(data, review_points=review_points, fallback_notice=fallback_notice),
        ]
    )
    strategy_block = build_strategy_block(strategy)
    if strategy_block is not None:
        blocks.append(strategy_block)
    blocks.append({"type": "divider"})
    return {"text": summary, "blocks": blocks}
