from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Protocol

from stock_tracker.models import BriefingData

DEFAULT_CODEX_MODEL = "gpt-5-codex"
DEFAULT_FALLBACK_NOTICE = "추론이 실패해서 규칙기반으로 나온 리뷰입니다."
SYSTEM_PROMPT = """당신은 한국 주식시장 브리핑 애널리스트입니다.
숫자를 반복하지 말고, 주어진 데이터만 근거로 시장을 해석하세요.
반드시 한국어 존댓말로 답하세요.
출력은 3~4개의 bullet line만 작성하세요.
각 줄은 '- '로 시작하고 70자 안팎으로 간결하게 쓰세요.
근거 없는 거시이슈나 뉴스 추측은 금지합니다.
수급, 지수 방향, 환율, 거래 상위 종목의 성격을 연결해 해석하세요.
마지막 줄은 가능하면 오늘 장세의 핵심 결론이나 체크포인트를 담으세요.
"""
DEFAULT_CODEX_BIN_CANDIDATES = [
    "/Applications/Codex.app/Contents/Resources/codex",
    shutil.which("codex") or "codex",
]


@dataclass(slots=True, eq=True)
class ReviewResult:
    points: list[str]
    fallback_notice: str | None = None


class Runner(Protocol):
    def __call__(
        self,
        command: list[str],
        *,
        input: str,
        text: bool,
        capture_output: bool,
        timeout: int,
        check: bool,
    ) -> subprocess.CompletedProcess[str]: ...


class CodexCliReviewGenerator:
    def __init__(
        self,
        codex_bin: str | None = None,
        runner: Runner | None = None,
        model: str = DEFAULT_CODEX_MODEL,
        timeout: int = 90,
    ) -> None:
        self.codex_bin = codex_bin or self._resolve_codex_bin()
        self.runner = runner or subprocess.run
        self.model = model
        self.timeout = timeout

    def generate(self, data: BriefingData) -> ReviewResult:
        try:
            completed = self.runner(
                [
                    self.codex_bin,
                    "exec",
                    "--skip-git-repo-check",
                    "-m",
                    self.model,
                    "-",
                ],
                input=self._build_full_prompt(data),
                text=True,
                capture_output=True,
                timeout=self.timeout,
                check=False,
            )
        except Exception:
            return ReviewResult(points=[], fallback_notice=DEFAULT_FALLBACK_NOTICE)

        if completed.returncode != 0:
            return ReviewResult(points=[], fallback_notice=DEFAULT_FALLBACK_NOTICE)

        points = parse_review_lines(completed.stdout)
        if not points:
            return ReviewResult(points=[], fallback_notice=DEFAULT_FALLBACK_NOTICE)
        return ReviewResult(points=points, fallback_notice=None)

    @staticmethod
    def _resolve_codex_bin() -> str:
        for candidate in DEFAULT_CODEX_BIN_CANDIDATES:
            if candidate and Path(candidate).exists():
                return candidate
        return "codex"

    def _build_full_prompt(self, data: BriefingData) -> str:
        return SYSTEM_PROMPT + "\n\n" + build_user_prompt(data)


def build_user_prompt(data: BriefingData) -> str:
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


def parse_review_lines(content: str) -> list[str]:
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
