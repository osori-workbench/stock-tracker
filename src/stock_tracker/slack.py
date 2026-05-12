from __future__ import annotations

import requests


class SlackWebhookClient:
    def __init__(self, webhook_url: str, session: requests.Session | None = None) -> None:
        self.webhook_url = webhook_url
        self.session = session or requests.Session()

    def send(self, text: str) -> None:
        response = self.session.post(self.webhook_url, json={"text": text}, timeout=20)
        response.raise_for_status()
