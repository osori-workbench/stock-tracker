from stock_tracker.naver import parse_yahoo_chart_snapshot


def test_parse_yahoo_chart_snapshot_uses_last_two_completed_closes() -> None:
    payload = {
        "chart": {
            "result": [
                {
                    "meta": {
                        "regularMarketPrice": 7400.96,
                        "chartPreviousClose": 7259.22,
                    },
                    "timestamp": [1, 2, 3],
                    "indicators": {
                        "quote": [
                            {
                                "close": [7398.93, 7412.84, 7400.96],
                            }
                        ]
                    },
                }
            ]
        }
    }

    snapshot = parse_yahoo_chart_snapshot(payload, "S&P 500")

    assert snapshot.value == 7400.96
    assert round(snapshot.change_value, 2) == -11.88
    assert round(snapshot.change_percent, 2) == -0.16


def test_parse_yahoo_chart_snapshot_falls_back_to_meta_when_close_history_missing() -> None:
    payload = {
        "chart": {
            "result": [
                {
                    "meta": {
                        "regularMarketPrice": 105.2,
                        "chartPreviousClose": 104.6,
                    },
                    "indicators": {
                        "quote": [
                            {
                                "close": [None],
                            }
                        ]
                    },
                }
            ]
        }
    }

    snapshot = parse_yahoo_chart_snapshot(payload, "달러인덱스")

    assert snapshot.value == 105.2
    assert round(snapshot.change_value, 2) == 0.6
    assert round(snapshot.change_percent, 2) == 0.57
