from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date

import requests
from bs4 import BeautifulSoup

from stock_tracker.models import ExchangeRateSnapshot, IndexSnapshot, InvestorSnapshot, TopStock

STOCK_NAVER_BASE = "https://stock.naver.com"
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
DOMESTIC_INDEX_BASIC_URL = f"{STOCK_NAVER_BASE}/api/securityFe/api/index/{{code}}/basic"
DOMESTIC_TOP_STOCKS_URL = f"{STOCK_NAVER_BASE}/api/domestic/market/stock/default"
DOMESTIC_INDEX_INTEGRATION_URL = f"{STOCK_NAVER_BASE}/api/securityFe/api/index/{{code}}/integration"
WORLD_INDEX_POLLING_URL = f"{STOCK_NAVER_BASE}/api/polling/worldstock/index"
MARKETINDEX_MAJORS_RPC_URL = f"{STOCK_NAVER_BASE}/api/securityService/marketindex/majors/rpc"
MARKETINDEX_MAJORS_BOND_URL = f"{STOCK_NAVER_BASE}/api/securityService/marketindex/majors/bond"
MARKETINDEX_ENERGY_URL = f"{STOCK_NAVER_BASE}/api/securityService/marketindex/energy"
GLOBAL_MARKET_CODES = [
    (".INX", "S&P 500"),
    (".IXIC", "NASDAQ"),
    (".SOX", "SOX"),
]
OIL_MARKET_CODES = [
    ("CLcv1", "WTI"),
    ("LCOcv1", "브렌트"),
]
GLOBAL_NEWS_QUERY = 'when:1d (Nasdaq OR "S&P 500" OR semiconductors OR "Treasury yields" OR "Federal Reserve" OR inflation OR dollar OR futures)'
OIL_NEWS_QUERY = 'when:1d ("crude oil" OR OPEC OR WTI OR "Brent crude" OR gasoline OR inventory OR refinery)'
GLOBAL_NEWS_KEYWORDS = {
    "nasdaq",
    "s&p 500",
    "treasury",
    "federal reserve",
    "fed",
    "inflation",
    "cpi",
    "ppi",
    "dollar",
    "yield",
    "wall street",
    "semiconductor",
    "chip",
    "stocks",
    "futures",
}
GLOBAL_NEWS_EXCLUDE_KEYWORDS = {"etf", "closing bell", "athletics", "sports", "wedding", "obituary", "bagel", "journal", "leak investigation"}
OIL_NEWS_KEYWORDS = {
    "crude",
    "oil",
    "opec",
    "wti",
    "brent crude",
    "gasoline",
    "inventory",
    "refinery",
    "energy",
}
OIL_NEWS_EXCLUDE_KEYWORDS = {"athletics", "sports", "wedding", "obituary"}


class NaverClient:
    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def fetch_index(self, code: str) -> IndexSnapshot:
        response = self.session.get(
            DOMESTIC_INDEX_BASIC_URL.format(code=code),
            timeout=20,
        )
        response.raise_for_status()
        return parse_marketindex_quote(response.json(), code)

    def fetch_exchange_rate(self) -> ExchangeRateSnapshot:
        response = self.session.get(MARKETINDEX_MAJORS_RPC_URL, timeout=20)
        response.raise_for_status()
        for item in response.json():
            if item.get("reutersCode") == "FX_USDKRW":
                return parse_stock_exchange_rate(item)
        raise ValueError("USD/KRW quote not found in stock.naver majors RPC")

    def fetch_investors(self, target_date: date, intraday: bool) -> InvestorSnapshot:
        del target_date, intraday
        response = self.session.get(DOMESTIC_INDEX_INTEGRATION_URL.format(code="KOSPI"), timeout=20)
        response.raise_for_status()
        return parse_stock_investor_snapshot(response.json())

    def fetch_top_volume(self, limit: int = 5) -> list[TopStock]:
        response = self.session.get(
            DOMESTIC_TOP_STOCKS_URL,
            params={
                "tradeType": "KRX",
                "marketType": "ALL",
                "orderType": "quantTop",
                "startIdx": 0,
                "pageSize": limit,
            },
            timeout=20,
        )
        response.raise_for_status()
        return [parse_domestic_top_stock(item) for item in response.json()[:limit]]

    def fetch_global_markets(self) -> list[IndexSnapshot]:
        snapshots: list[IndexSnapshot] = []
        response = self.session.get(
            WORLD_INDEX_POLLING_URL,
            params=[("reutersCodes", ",".join(code for code, _ in GLOBAL_MARKET_CODES))],
            timeout=20,
        )
        response.raise_for_status()
        payloads = {item["reutersCode"]: item for item in response.json().get("datas", [])}
        for code, label in GLOBAL_MARKET_CODES:
            payload = payloads.get(code)
            if payload is not None:
                snapshots.append(parse_marketindex_quote(payload, label))

        bond_response = self.session.get(MARKETINDEX_MAJORS_BOND_URL, timeout=20)
        bond_response.raise_for_status()
        for item in bond_response.json():
            if item.get("reutersCode") == "US10YT=RR":
                snapshots.append(parse_marketindex_quote(item, "미국 10년물"))
                break

        majors_response = self.session.get(MARKETINDEX_MAJORS_RPC_URL, timeout=20)
        majors_response.raise_for_status()
        for item in majors_response.json():
            if item.get("reutersCode") == ".DXY":
                snapshots.append(parse_marketindex_quote(item, "달러인덱스"))
                break
        return snapshots

    def fetch_oil_markets(self) -> list[IndexSnapshot]:
        response = self.session.get(MARKETINDEX_ENERGY_URL, timeout=20)
        response.raise_for_status()
        payloads = {item["reutersCode"]: item for item in response.json()}
        snapshots: list[IndexSnapshot] = []
        for code, label in OIL_MARKET_CODES:
            payload = payloads.get(code)
            if payload is not None:
                snapshots.append(parse_marketindex_quote(payload, label))
        return snapshots

    def fetch_global_headlines(self, limit: int = 4) -> list[str]:
        return self._fetch_google_news_headlines(
            GLOBAL_NEWS_QUERY,
            limit=limit,
            include_keywords=GLOBAL_NEWS_KEYWORDS,
            exclude_keywords=GLOBAL_NEWS_EXCLUDE_KEYWORDS,
        )

    def fetch_oil_headlines(self, limit: int = 2) -> list[str]:
        return self._fetch_google_news_headlines(
            OIL_NEWS_QUERY,
            limit=limit,
            include_keywords=OIL_NEWS_KEYWORDS,
            exclude_keywords=OIL_NEWS_EXCLUDE_KEYWORDS,
        )

    def _fetch_google_news_headlines(
        self,
        query: str,
        limit: int,
        include_keywords: set[str],
        exclude_keywords: set[str],
    ) -> list[str]:
        response = self.session.get(
            GOOGLE_NEWS_RSS_URL,
            params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
            timeout=20,
        )
        response.raise_for_status()
        return parse_google_news_rss(
            response.text,
            limit=limit,
            include_keywords=include_keywords,
            exclude_keywords=exclude_keywords,
        )


def _to_int(text: str) -> int:
    text = text.replace(',', '').strip()
    if not text:
        return 0
    return int(text)


def _to_float(text: str) -> float:
    return float(text.replace(',', '').replace('%', '').strip())


def parse_stock_indicator(payload: dict, label: str) -> IndexSnapshot:
    return IndexSnapshot(
        name=label,
        value=_to_float(payload["currentPrice"]),
        change_value=_to_signed_float(payload["fluctuations"], payload.get("fluctuationsType")),
        change_percent=_to_signed_float(payload["fluctuationsRatio"], payload.get("fluctuationsType")),
    )


def parse_marketindex_quote(payload: dict, label: str) -> IndexSnapshot:
    change_type = payload.get("fluctuationsType") or payload.get("compareToPreviousPrice")
    if isinstance(change_type, dict):
        change_type = change_type.get("name") or change_type.get("text") or change_type.get("code")
    return IndexSnapshot(
        name=label,
        value=_to_float(payload["closePrice"]),
        change_value=_to_signed_float(payload.get("fluctuations") or payload.get("compareToPreviousClosePrice"), change_type),
        change_percent=_to_signed_float(payload["fluctuationsRatio"], change_type),
    )


def parse_stock_exchange_rate(payload: dict) -> ExchangeRateSnapshot:
    source = payload.get("stockExchangeType", {}).get("nameKor") or payload.get("description") or "stock.naver"
    change_type = payload.get("fluctuationsType", {}).get("text", "보합")
    return ExchangeRateSnapshot(
        name="USD/KRW",
        value=_to_float(payload.get("calcPrice") or payload["closePrice"]),
        change_value=abs(_to_float(payload["fluctuations"])),
        direction=change_type,
        source=source,
    )


def parse_stock_investor_snapshot(payload: dict) -> InvestorSnapshot:
    trend = payload.get("dealTrendInfo") or {}
    return InvestorSnapshot(
        basis_label=trend.get("bizdate", ""),
        individual=_to_int(trend.get("personalValue", "0")),
        foreign=_to_int(trend.get("foreignValue", "0")),
        institution=_to_int(trend.get("institutionalValue", "0")),
        financial_investment=0,
        insurance=0,
        trust_private=0,
        bank=0,
        other_financial=0,
        pension=0,
        other_corporation=0,
    )


def parse_domestic_top_stock(payload: dict) -> TopStock:
    return TopStock(
        code=str(payload["itemcode"]),
        name=payload["itemname"],
        price=_to_float(payload["nowPrice"]),
        change_percent=_to_float(payload["prevChangeRate"]),
    )


def _to_signed_float(text: str, direction: str | None) -> float:
    value = abs(_to_float(text))
    if direction in {"FALLING", "하락", "5"}:
        return -value
    return value


def parse_google_news_rss(
    xml_text: str,
    limit: int = 4,
    include_keywords: set[str] | None = None,
    exclude_keywords: set[str] | None = None,
) -> list[str]:
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        return []

    headlines: list[str] = []
    seen: set[str] = set()
    for item in channel.findall("item"):
        title_text = (item.findtext("title") or "").strip()
        if not title_text:
            continue
        source_text = ""
        source = item.find("source")
        if source is not None and source.text:
            source_text = source.text.strip()
        headline = normalize_google_news_title(title_text, source_text)
        if not headline or headline in seen:
            continue
        if not is_relevant_headline(headline, include_keywords=include_keywords, exclude_keywords=exclude_keywords):
            continue
        seen.add(headline)
        headlines.append(headline)
        if len(headlines) >= limit:
            break
    return headlines


def is_relevant_headline(
    headline: str,
    include_keywords: set[str] | None = None,
    exclude_keywords: set[str] | None = None,
) -> bool:
    lowered = headline.lower()
    if exclude_keywords and any(keyword in lowered for keyword in exclude_keywords):
        return False
    if include_keywords and not any(keyword in lowered for keyword in include_keywords):
        return False
    return True


def normalize_google_news_title(title: str, source: str = "") -> str:
    cleaned = title.replace("&#39;", "'").strip()
    if cleaned.endswith(f" - {source}") and source:
        cleaned = cleaned[: -(len(source) + 3)].strip()
    if source:
        return f"{cleaned} ({source})"
    return cleaned


def parse_exchange_rate(html: str) -> ExchangeRateSnapshot:
    soup = BeautifulSoup(html, 'html.parser')
    usd = soup.select_one('#exchangeList li.on')
    if usd is None:
        raise ValueError('USD/KRW exchange rate row not found')

    label = usd.select_one('h3 .blind')
    value = usd.select_one('span.value')
    change = usd.select_one('span.change')
    direction = usd.select('div.head_info span.blind')[-1] if usd.select('div.head_info span.blind') else None
    source = usd.select_one('.graph_info .source')
    if not all([label, value, change, direction, source]):
        raise ValueError('Incomplete USD/KRW exchange rate row')

    return ExchangeRateSnapshot(
        name='USD/KRW',
        value=_to_float(value.get_text(strip=True)),
        change_value=_to_float(change.get_text(strip=True)),
        direction=direction.get_text(strip=True),
        source=source.get_text(' ', strip=True).replace(' 기준', ''),
    )


def parse_investor_rows(html: str) -> InvestorSnapshot:
    soup = BeautifulSoup(html, 'html.parser')
    for tr in soup.select('table.type_1 tr'):
        cells = [cell.get_text(' ', strip=True) for cell in tr.find_all('td')]
        if len(cells) == 11 and re.match(r'^(\d{2}:\d{2}|\d{2}\.\d{2}\.\d{2})$', cells[0]):
            return InvestorSnapshot(
                basis_label=cells[0],
                individual=_to_int(cells[1]),
                foreign=_to_int(cells[2]),
                institution=_to_int(cells[3]),
                financial_investment=_to_int(cells[4]),
                insurance=_to_int(cells[5]),
                trust_private=_to_int(cells[6]),
                bank=_to_int(cells[7]),
                other_financial=_to_int(cells[8]),
                pension=_to_int(cells[9]),
                other_corporation=_to_int(cells[10]),
            )
    raise ValueError('No investor rows found')


def parse_top_volume_rows(html: str, limit: int = 5) -> list[TopStock]:
    soup = BeautifulSoup(html, 'html.parser')
    stocks: list[TopStock] = []
    for tr in soup.select('table.type_2 tr'):
        link = tr.select_one('a.tltle')
        if link is None:
            continue
        cells = [cell.get_text(' ', strip=True) for cell in tr.find_all('td')]
        if len(cells) < 5:
            continue
        match = re.search(r'code=(\d+)', link.get('href', ''))
        if match is None:
            continue
        stocks.append(
            TopStock(
                code=match.group(1),
                name=link.get_text(strip=True),
                price=float(cells[2].replace(',', '')),
                change_percent=_to_float(cells[4]),
            )
        )
        if len(stocks) >= limit:
            break
    return stocks
