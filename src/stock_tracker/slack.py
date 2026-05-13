from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import requests


class SlackWebhookClient:
    def __init__(self, webhook_url: str, session: requests.Session | None = None) -> None:
        self.webhook_url = webhook_url
        self.session = session or requests.Session()

    def send(self, payload: dict[str, Any]) -> None:
        response = self.session.post(self.webhook_url, json=payload, timeout=20)
        response.raise_for_status()
        print(
            f"[slack] delivered status={response.status_code} body={response.text!r} webhook={self._mask_webhook_url()} blocks={len(payload.get('blocks', []))}",
            flush=True,
        )

    def _mask_webhook_url(self) -> str:
        parsed = urlparse(self.webhook_url)
        parts = [part for part in parsed.path.split('/') if part]
        if len(parts) >= 3:
            masked_tail = '/'.join(parts[:-1] + ['***'])
        else:
            masked_tail = parsed.path
        return f"{parsed.scheme}://{parsed.netloc}/{masked_tail.lstrip('/')}"
