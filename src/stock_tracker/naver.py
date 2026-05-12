from __future__ import annotations

import re
from datetime import date

import requests
from bs4 import BeautifulSoup

from stock_tracker.models import ExchangeRateSnapshot, IndexSnapshot, InvestorSnapshot, TopStock

POLLING_URL = "https://polling.finance.naver.com/api/realtime"
NAVER_BASE = "https://finance.naver.com"


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


def _to_int(text: str) -> int:
    text = text.replace(',', '').strip()
    if not text:
        return 0
    return int(text)


def _to_float(text: str) -> float:
    return float(text.replace(',', '').replace('%', '').strip())


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
