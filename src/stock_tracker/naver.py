from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date

import requests
from bs4 import BeautifulSoup

from stock_tracker.models import ExchangeRateSnapshot, IndexSnapshot, InvestorSnapshot, TopStock

POLLING_URL = "https://polling.finance.naver.com/api/realtime"
NAVER_BASE = "https://finance.naver.com"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
GLOBAL_MARKET_SPECS = [
    ("%5EGSPC", "S&P 500"),
    ("%5EIXIC", "NASDAQ"),
    ("%5ESOX", "SOX"),
    ("%5ETNX", "미국 10년물"),
    ("DX-Y.NYB", "달러인덱스"),
]
OIL_MARKET_SPECS = [
    ("CL%3DF", "WTI"),
    ("BZ%3DF", "브렌트"),
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
            POLLING_URL,
            params={"query": f"SERVICE_INDEX:{code}"},
            headers={"Referer": f"{NAVER_BASE}/sise/sise_index.naver"},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()["result"]["areas"][0]["datas"][0]
        return IndexSnapshot(
            name=payload["cd"],
            value=payload["nv"] / 100,
            change_value=payload["cv"] / 100,
            change_percent=float(payload["cr"]),
        )

    def fetch_exchange_rate(self) -> ExchangeRateSnapshot:
        response = self.session.get(f"{NAVER_BASE}/marketindex/", timeout=20)
        response.raise_for_status()
        return parse_exchange_rate(response.text)

    def fetch_investors(self, target_date: date, intraday: bool) -> InvestorSnapshot:
        path = "investorDealTrendTime.naver" if intraday else "investorDealTrendDay.naver"
        response = self.session.get(
            f"{NAVER_BASE}/sise/{path}",
            params={"bizdate": target_date.strftime('%Y%m%d')},
            timeout=20,
        )
        response.raise_for_status()
        return parse_investor_rows(response.text)

    def fetch_top_volume(self, limit: int = 5) -> list[TopStock]:
        response = self.session.get(f"{NAVER_BASE}/sise/sise_quant.naver", timeout=20)
        response.raise_for_status()
        return parse_top_volume_rows(response.text, limit=limit)

    def fetch_global_markets(self) -> list[IndexSnapshot]:
        snapshots: list[IndexSnapshot] = []
        for symbol, label in GLOBAL_MARKET_SPECS:
            snapshot = self._try_fetch_yahoo_snapshot(symbol, label)
            if snapshot is not None:
                snapshots.append(snapshot)
        return snapshots

    def fetch_oil_markets(self) -> list[IndexSnapshot]:
        snapshots: list[IndexSnapshot] = []
        for symbol, label in OIL_MARKET_SPECS:
            snapshot = self._try_fetch_yahoo_snapshot(symbol, label)
            if snapshot is not None:
                snapshots.append(snapshot)
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

    def _try_fetch_yahoo_snapshot(self, symbol: str, label: str) -> IndexSnapshot | None:
        try:
            return self.fetch_yahoo_snapshot(symbol, label)
        except Exception:
            return None

    def fetch_yahoo_snapshot(self, symbol: str, label: str) -> IndexSnapshot:
        response = self.session.get(
            YAHOO_CHART_URL.format(symbol=symbol),
            params={"interval": "1d", "range": "5d"},
            timeout=20,
        )
        response.raise_for_status()
        return parse_yahoo_chart_snapshot(response.json(), label)

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


def parse_yahoo_chart_snapshot(payload: dict, label: str) -> IndexSnapshot:
    result = payload["chart"]["result"][0]
    meta = result["meta"]
    closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
    valid_closes = [float(close) for close in closes if close is not None]

    if len(valid_closes) >= 2:
        previous = valid_closes[-2]
        current = valid_closes[-1]
    else:
        current = float(meta["regularMarketPrice"])
        previous = float(meta["chartPreviousClose"])

    change_value = current - previous
    change_percent = (change_value / previous) * 100 if previous else 0.0
    return IndexSnapshot(
        name=label,
        value=current,
        change_value=change_value,
        change_percent=change_percent,
    )


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
