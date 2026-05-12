from __future__ import annotations

from stock_tracker.models import BriefingData

MODE_TITLES = {
    "open": "국장 오픈 10분",
    "noon": "국장 장중 정오 리뷰",
    "close": "국장 마감 리뷰",
}


def format_eok_to_jo(value: int) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value / 10000:.2f}조"


def build_briefing_text(data: BriefingData) -> str:
    title = MODE_TITLES[data.mode]
    lines = [f"[{title} | {data.now.strftime('%Y-%m-%d %H:%M')} KST]"]
    lines.append(f"- 시장 상태: {data.market_label}")
    for index in data.indices:
        lines.append(
            f"- {index.name}: {index.value:,.2f} ({index.change_percent:+.2f}%, {index.change_value:+,.2f})"
        )

    investor = data.investors
    lines.append(
        "- 수급: "
        f"개인 {format_eok_to_jo(investor.individual)} / "
        f"외국인 {format_eok_to_jo(investor.foreign)} / "
        f"기관 {format_eok_to_jo(investor.institution)}"
    )
    lines.append(
        "- 기관 세부: "
        f"금융투자 {format_eok_to_jo(investor.financial_investment)}, "
        f"보험 {format_eok_to_jo(investor.insurance)}, "
        f"투신(사모) {format_eok_to_jo(investor.trust_private)}, "
        f"연기금 {format_eok_to_jo(investor.pension)}"
    )
    if data.leaders:
        summary = ", ".join(
            f"{stock.name}({stock.change_percent:+.2f}%)" for stock in data.leaders
        )
        lines.append(f"- 거래 상위 관심종목: {summary}")
    if data.notes:
        lines.append(f"- 참고: {' / '.join(data.notes)}")
    if data.sources:
        lines.append(f"- 출처: {', '.join(data.sources)}")
    return '\n'.join(lines)
