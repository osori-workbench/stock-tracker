from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import requests

from stock_tracker.models import BriefingData

OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
SYSTEM_PROMPT = """당신은 한국 주식시장 브리핑 애널리스트입니다.
숫자를 반복하지 말고, 주어진 데이터만 근거로 시장을 해석하세요.
반드시 한국어 존댓말로 답하세요.
출력은 3~4개의 bullet line만 작성하세요.
각 줄은 '- '로 시작하고 70자 안팎으로 간결하게 쓰세요.
근거 없는 거시이슈나 뉴스 추측은 금지합니다.
수급, 지수 방향, 환율, 거래 상위 종목의 성격을 연결해 해석하세요.
마지막 줄은 가능하면 오늘 장세의 핵심 결론이나 체크포인트를 담으세요.
"""


class OpenAIReviewGenerator:
    def __init__(
        self,
        api_key: str,
        session: requests.Session | None = None,
        model: str = DEFAULT_OPENAI_MODEL,
        api_url: str = OPENAI_CHAT_COMPLETIONS_URL,
    ) -> None:
        self.api_key = api_key
        self.session = session or requests.Session()
        self.model = model
        self.api_url = api_url

    def generate(self, data: BriefingData) -> list[str]:
        payload = {
            "model": self.model,
            "temperature": 0.4,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": self._build_user_prompt(data)},
            ],
        }
        response = self.session.post(
            self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        return self._parse_review_lines(content)

    def _build_user_prompt(self, data: BriefingData) -> str:
        serialized = {
            "mode": data.mode,
            "timestamp_kst": data.now.isoformat(),
            "market_label": data.market_label,
            "indices": [asdict(index) for index in data.indices],
            "exchange_rate": asdict(data.exchange_rate) if data.exchange_rate else None,
            "investors": asdict(data.investors),
            "leaders": [asdict(stock) for stock in data.leaders],
            "notes": data.notes,
        }
        return (
            "아래 JSON 데이터만 근거로 국장 브리핑용 종합 리뷰를 작성해주세요.\n"
            "너무 뻔한 숫자 나열은 피하고, 수급/지수/환율/거래 상위 종목의 성격을 엮어 해석해주세요.\n"
            "JSON 데이터:\n"
            f"{json.dumps(serialized, ensure_ascii=False, indent=2)}"
        )

    @staticmethod
    def _parse_review_lines(content: str) -> list[str]:
        lines = []
        for raw in content.splitlines():
            line = raw.strip()
            if not line:
                continue
            for prefix in ("- ", "• ", "* "):
                if line.startswith(prefix):
                    line = line[len(prefix):].strip()
                    break
            if line:
                lines.append(line)
        if lines:
            return lines[:4]
        compact = content.strip()
        return [compact] if compact else []
