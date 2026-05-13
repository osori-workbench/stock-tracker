from stock_tracker.slack import SlackWebhookClient


class DummyResponse:
    status_code = 200
    text = "ok"

    def raise_for_status(self) -> None:
        return None


class DummySession:
    def __init__(self) -> None:
        self.calls = []

    def post(self, url: str, json: dict, timeout: int) -> DummyResponse:
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return DummyResponse()


def test_slack_webhook_client_sends_block_payload() -> None:
    session = DummySession()
    client = SlackWebhookClient("https://hooks.slack.test/example", session=session)

    client.send({"text": "fallback", "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "*hello*"}}]})

    assert session.calls[0]["json"]["text"] == "fallback"
    assert session.calls[0]["json"]["blocks"][0]["type"] == "section"
