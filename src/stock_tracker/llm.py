from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from stock_tracker.models import BriefingData

DEFAULT_HERMES_MODEL = "gpt-5.4"
DEFAULT_FALLBACK_NOTICE = "추론이 실패해서 규칙기반으로 나온 리뷰입니다."
DEFAULT_STRATEGY_FALLBACK = "전략 추론이 실패해 한줄 전략은 이번 브리핑에서 생략하겠습니다."
SYSTEM_PROMPT = """당신은 한국 주식시장 브리핑 애널리스트입니다.
숫자를 반복하지 말고, 주어진 데이터만 근거로 시장을 해석하세요.
반드시 한국어 존댓말로 답하세요.
출력 형식은 반드시 아래를 지키세요.
- 해석 bullet 3~4개: 각 줄은 '- '로 시작
- 마지막 1줄은 반드시 '전략:'으로 시작
근거 없는 거시이슈나 뉴스 추측은 금지합니다.
'morning' 모드에서는 밤사이 미국시장/뉴스/환율을 바탕으로 오늘 국내장의 부담과 체크포인트를 추론하세요.
원유 평가는 별도 블록으로 내려가므로 morning 모드 리뷰에서는 국내장 해석에 집중하세요.
'open'/'noon'/'close' 모드에서는 수급, 지수 방향, 환율, 거래 상위 종목의 성격을 연결해 해석하세요.
'전략:' 줄에는 당신이라면 오늘 어떻게 대응할지 한 문장으로 짧게 쓰세요.
표현은 예시처럼 자연스럽게 쓰되, 과한 단정은 피하세요: 관망, 소액 분할 매수, 지수 추가 매수, 비중 축소, 인버스 유지 등.
"""
DEFAULT_HERMES_BIN_CANDIDATES = [
    shutil.which("hermes"),
    str(Path.home() / ".local" / "bin" / "hermes"),
    "hermes",
]


@dataclass(slots=True, eq=True)
class ReviewResult:
    points: list[str]
    strategy: str | None = None
    fallback_notice: str | None = None


class Runner(Protocol):
    def __call__(
        self,
        command: list[str],
        *,
        text: bool,
        capture_output: bool,
        timeout: int,
        check: bool,
    ) -> subprocess.CompletedProcess[str]: ...


class HermesCliReviewGenerator:
    def __init__(
        self,
        hermes_bin: str | None = None,
        runner: Runner | None = None,
        model: str = DEFAULT_HERMES_MODEL,
        timeout: int = 120,
    ) -> None:
        self.hermes_bin = hermes_bin or self._resolve_hermes_bin()
        self.runner = runner or subprocess.run
        self.model = model
        self.timeout = timeout

    def generate(self, data: BriefingData) -> ReviewResult:
        prompt = self._build_full_prompt(data)
        try:
            completed = self.runner(
                [
                    self.hermes_bin,
                    "chat",
                    "-q",
                    prompt,
                    "--quiet",
                    "-m",
                    self.model,
                ],
                text=True,
                capture_output=True,
                timeout=self.timeout,
                check=False,
            )
        except Exception:
            return ReviewResult(points=[], strategy=DEFAULT_STRATEGY_FALLBACK, fallback_notice=DEFAULT_FALLBACK_NOTICE)

        if completed.returncode != 0:
            return ReviewResult(points=[], strategy=DEFAULT_STRATEGY_FALLBACK, fallback_notice=DEFAULT_FALLBACK_NOTICE)

        points, strategy = parse_review_output(completed.stdout)
        if not points:
            return ReviewResult(points=[], strategy=DEFAULT_STRATEGY_FALLBACK, fallback_notice=DEFAULT_FALLBACK_NOTICE)
        return ReviewResult(points=points, strategy=strategy or DEFAULT_STRATEGY_FALLBACK, fallback_notice=None)

    @staticmethod
    def _resolve_hermes_bin() -> str:
        for candidate in DEFAULT_HERMES_BIN_CANDIDATES:
            if candidate and Path(candidate).exists():
                return candidate
        return "hermes"

    def _build_full_prompt(self, data: BriefingData) -> str:
        return SYSTEM_PROMPT + "\n\n" + build_user_prompt(data)


def build_user_prompt(data: BriefingData) -> str:
    serialized = {
        "mode": data.mode,
        "timestamp_kst": data.now.isoformat(),
        "market_label": data.market_label,
        "indices": [asdict(index) for index in data.indices],
        "exchange_rate": asdict(data.exchange_rate) if data.exchange_rate else None,
        "investors": asdict(data.investors) if data.investors else None,
        "leaders": [asdict(stock) for stock in data.leaders],
        "notes": data.notes,
        "global_markets": [asdict(index) for index in data.global_markets],
        "headlines": data.headlines,
        "oil_markets": [asdict(index) for index in data.oil_markets],
        "oil_headlines": data.oil_headlines,
    }
    return (
        "아래 JSON 데이터만 근거로 국장 브리핑용 종합 리뷰를 작성해주세요.\n"
        "너무 뻔한 숫자 나열은 피하고, 데이터 사이의 연결관계를 해석해주세요.\n"
        "morning 모드면 오늘 국내장 예상과 체크포인트를, 그 외 모드면 수급/지수/환율/거래 상위 종목 해석을 중심으로 써주세요.\n"
        "마지막 줄은 반드시 '전략:'으로 시작하는 한 문장 전략 요약이어야 합니다.\n"
        "JSON 데이터:\n"
        f"{json.dumps(serialized, ensure_ascii=False, indent=2)}"
    )


def parse_review_output(content: str) -> tuple[list[str], str | None]:
    points: list[str] = []
    strategy: str | None = None
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("session_id:"):
            continue
        if line.startswith("전략:"):
            strategy = line.split("전략:", 1)[1].strip()
            continue
        for prefix in ("- ", "• ", "* "):
            if line.startswith(prefix):
                line = line[len(prefix):].strip()
                break
        if line:
            points.append(line)
    return points[:4], strategy
