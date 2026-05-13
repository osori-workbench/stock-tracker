from stock_tracker.naver import (
    parse_domestic_top_stock,
    parse_marketindex_quote,
    parse_stock_indicator,
    parse_stock_investor_snapshot,
)


def test_parse_stock_indicator_uses_stock_naver_indicator_payload() -> None:
    payload = {
        "stockName": "코스피",
        "currentPrice": "7,708.13",
        "fluctuations": "64.98",
        "fluctuationsType": "RISING",
        "fluctuationsRatio": "0.85",
    }

    snapshot = parse_stock_indicator(payload, "KOSPI")

    assert snapshot.name == "KOSPI"
    assert snapshot.value == 7708.13
    assert snapshot.change_value == 64.98
    assert snapshot.change_percent == 0.85


def test_parse_marketindex_quote_uses_stock_naver_marketindex_payload() -> None:
    payload = {
        "name": "달러인덱스",
        "closePrice": "98.31",
        "fluctuations": "0.01",
        "fluctuationsRatio": "0.01",
        "fluctuationsType": {"name": "RISING", "text": "상승"},
    }

    snapshot = parse_marketindex_quote(payload, "달러인덱스")

    assert snapshot.name == "달러인덱스"
    assert snapshot.value == 98.31
    assert snapshot.change_value == 0.01
    assert snapshot.change_percent == 0.01


def test_parse_stock_investor_snapshot_falls_back_when_detail_fields_missing() -> None:
    payload = {
        "dealTrendInfo": {
            "bizdate": "20260513",
            "personalValue": "+16,709",
            "foreignValue": "-21,564",
            "institutionalValue": "+4,011",
        }
    }

    snapshot = parse_stock_investor_snapshot(payload)

    assert snapshot.basis_label == "20260513"
    assert snapshot.individual == 16709
    assert snapshot.foreign == -21564
    assert snapshot.institution == 4011
    assert snapshot.financial_investment == 0
    assert snapshot.pension == 0


def test_parse_domestic_top_stock_uses_stock_naver_market_payload() -> None:
    payload = {
        "itemcode": "900300",
        "itemname": "오가닉티코스메틱",
        "nowPrice": "125",
        "prevChangeRate": "3.31",
    }

    stock = parse_domestic_top_stock(payload)

    assert stock.code == "900300"
    assert stock.name == "오가닉티코스메틱"
    assert stock.price == 125.0
    assert stock.change_percent == 3.31
