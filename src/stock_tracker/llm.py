from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from stock_tracker.models import BriefingData

DEFAULT_HERMES_MODEL: str | None = None  # None -> Hermes 기본 모델 사용
DEFAULT_FALLBACK_NOTICE = "추론이 실패해서 규칙기반으로 나온 리뷰입니다."
DEFAULT_STRATEGY_FALLBACK = "전략 추론이 실패해 한줄 전략은 이번 브리핑에서 생략하겠습니다."
SYSTEM_PROMPT = """당신은 한국 주식시장 브리핑 애널리스트입니다.
숫자를 반복하지 말고, 주어진 데이터만 근거로 시장을 해석하세요.
반드시 한국어 존댓말로 답하세요.
출력 형식은 반드시 아래를 지키세요.
- 해석 bullet 3~4개: 각 줄은 '- '로 시작
- 그 다음 1줄은 반드시 '판정:'으로 시작하고 값은 상방 우위 / 중립 / 하방 우위 중 하나여야 합니다.
- 그 다음 1줄은 반드시 '행동:'으로 시작해야 합니다.
- 그 다음 1줄은 반드시 '확신도:'로 시작하고 1/5~5/5 형식을 지켜야 합니다.
- 마지막 1줄은 반드시 '전략:'으로 시작해야 합니다.
근거 없는 거시이슈나 뉴스 추측은 금지합니다.
'morning' 모드에서는 밤사이 미국시장/뉴스/환율을 바탕으로 오늘 국내장의 부담과 체크포인트를 추론하세요.
원유 평가는 별도 블록으로 내려가므로 morning 모드 리뷰에서는 국내장 해석에 집중하세요.
'open'/'noon'/'close' 모드에서는 수급, 지수 방향, 환율, 거래 상위 종목의 성격을 연결해 해석하세요.
먼저 방향을 판정하고, 그 다음 행동과 확신도를 정하세요.
'관망'은 신호 충돌이 크거나 확신도가 1~2일 때만 쓰세요. 한쪽 신호가 우세하면 관망 대신 더 구체적인 행동을 제시하세요.
'전략:' 줄에는 당신이라면 오늘 어떻게 대응할지 한 문장으로 짧게 쓰세요.
표현은 자연스럽게 쓰되 과한 단정은 피하세요.
"""
DEFAULT_HERMES_BIN_CANDIDATES = [
    shutil.which("hermes"),
    str(Path.home() / ".local" / "bin" / "hermes"),
    "hermes",
]


@dataclass(slots=True, eq=True)
class ReviewResult:
    points: list[str]
    bias: str | None = None
    action: str | None = None
    confidence: int | None = None
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
        model: str | None = DEFAULT_HERMES_MODEL,
        timeout: int = 120,
    ) -> None:
        self.hermes_bin = hermes_bin or self._resolve_hermes_bin()
        self.runner = runner or subprocess.run
        self.model = model
        self.timeout = timeout

    def generate(self, data: BriefingData) -> ReviewResult:
        prompt = self._build_full_prompt(data)
        try:
            command = [self.hermes_bin, "chat", "-q", prompt, "--quiet"]
            if self.model:
                command += ["-m", self.model]
            completed = self.runner(
                command,
                text=True,
                capture_output=True,
                timeout=self.timeout,
                check=False,
            )
        except Exception:
            return ReviewResult(points=[], strategy=DEFAULT_STRATEGY_FALLBACK, fallback_notice=DEFAULT_FALLBACK_NOTICE)

        if completed.returncode != 0:
            return ReviewResult(points=[], strategy=DEFAULT_STRATEGY_FALLBACK, fallback_notice=DEFAULT_FALLBACK_NOTICE)

        points, bias, action, confidence, strategy = parse_review_output(completed.stdout)
        if not points:
            return ReviewResult(points=[], strategy=DEFAULT_STRATEGY_FALLBACK, fallback_notice=DEFAULT_FALLBACK_NOTICE)
        return ReviewResult(
            points=points,
            bias=bias,
            action=action,
            confidence=confidence,
            strategy=strategy or DEFAULT_STRATEGY_FALLBACK,
            fallback_notice=None,
        )

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
        "raw_snapshot": {
            "indices": [asdict(index) for index in data.indices],
            "exchange_rate": asdict(data.exchange_rate) if data.exchange_rate else None,
            "investors": asdict(data.investors) if data.investors else None,
            "leaders": [asdict(stock) for stock in data.leaders],
            "notes": data.notes,
            "global_markets": [asdict(index) for index in data.global_markets],
            "headlines": data.headlines,
            "oil_markets": [asdict(index) for index in data.oil_markets],
            "oil_headlines": data.oil_headlines,
        },
        "decision_framework": build_decision_framework(data),
        "output_contract": {
            "review_bullets": "3~4 lines, each prefixed with '- '",
            "bias": ["상방 우위", "중립", "하방 우위"],
            "action_line_prefix": "행동:",
            "confidence_format": "확신도: N/5",
            "strategy_line_prefix": "전략:",
        },
    }
    return (
        "아래 JSON 데이터만 근거로 국장 브리핑용 종합 리뷰를 작성해주세요.\n"
        "너무 뻔한 숫자 나열은 피하고, 데이터 사이의 연결관계를 해석해주세요.\n"
        "morning 모드면 오늘 국내장 예상과 체크포인트를, 그 외 모드면 수급/지수/환율/거래 상위 종목 해석을 중심으로 써주세요.\n"
        "decision_framework의 힌트를 참고하되 그대로 복창하지 말고 종합 판단하세요.\n"
        "JSON 데이터:\n"
        f"{json.dumps(serialized, ensure_ascii=False, indent=2)}"
    )


def build_decision_framework(data: BriefingData) -> dict:
    indices = [index.change_percent for index in data.indices]
    avg_index_change = round(sum(indices) / len(indices), 2) if indices else 0.0
    foreign = data.investors.foreign if data.investors else 0
    institution = data.investors.institution if data.investors else 0
    individual = data.investors.individual if data.investors else 0
    leader_names = [stock.name for stock in data.leaders]
    has_inverse_leaders = any("인버스" in name for name in leader_names)
    strong_leaders = [stock.name for stock in data.leaders if stock.change_percent >= 5]
    weak_global_markets = [item.name for item in data.global_markets if item.change_percent <= -1]
    strong_global_markets = [item.name for item in data.global_markets if item.change_percent >= 1]
    conflict_flags: list[str] = []
    if data.exchange_rate and data.exchange_rate.direction == "상승" and foreign > 0:
        conflict_flags.append("원달러 상승 vs 외국인 순매수")
    if avg_index_change > 0 and has_inverse_leaders:
        conflict_flags.append("지수 상승 vs 인버스 거래 상위")
    if avg_index_change < 0 and foreign > 0 and institution > 0:
        conflict_flags.append("지수 약세 vs 외국인·기관 동반 순매수")

    return {
        "market_bias_hint": infer_market_bias_hint(data, avg_index_change),
        "action_bias_hint": infer_action_bias_hint(data, avg_index_change, has_inverse_leaders),
        "confidence_hint": infer_confidence_hint(conflict_flags, avg_index_change, foreign, institution),
        "signals": {
            "avg_index_change_percent": avg_index_change,
            "foreign_flow_eok": foreign,
            "institution_flow_eok": institution,
            "individual_flow_eok": individual,
            "fx_direction": data.exchange_rate.direction if data.exchange_rate else None,
            "has_inverse_leaders": has_inverse_leaders,
            "strong_leaders": strong_leaders,
            "weak_global_markets": weak_global_markets,
            "strong_global_markets": strong_global_markets,
        },
        "conflict_flags": conflict_flags,
        "missing_signals": build_missing_signals(data),
    }


def infer_market_bias_hint(data: BriefingData, avg_index_change: float) -> str:
    if data.mode == "morning":
        negative = sum(1 for item in data.global_markets if item.change_percent <= -1)
        if negative >= 2 or (data.exchange_rate and data.exchange_rate.direction == "상승"):
            return "하방 우위 가능성"
        if any(item.change_percent >= 1 for item in data.global_markets):
            return "상방 우위 가능성"
        return "중립 가능성"

    if data.investors is None:
        return "중립 가능성"
    if avg_index_change >= 0.8 and data.investors.foreign > 0 and data.investors.institution > 0:
        return "상방 우위 가능성"
    if avg_index_change <= -0.8 and data.investors.foreign < 0 and data.investors.institution < 0:
        return "하방 우위 가능성"
    return "중립 가능성"


def infer_action_bias_hint(data: BriefingData, avg_index_change: float, has_inverse_leaders: bool) -> str:
    if data.mode == "morning":
        if data.exchange_rate and data.exchange_rate.direction == "상승":
            return "시가 추격보다 관망 후 눌림 확인"
        return "주도 섹터 확인 뒤 분할 접근"

    if data.investors is None:
        return "추가 확인 필요"
    if avg_index_change >= 0.8 and data.investors.foreign > 0:
        return "주도주 눌림 분할 매수"
    if avg_index_change <= -0.8 and (data.investors.foreign < 0 or has_inverse_leaders):
        return "비중 축소 또는 방어 유지"
    return "신호 확인 전까지 선별 접근"


def infer_confidence_hint(conflict_flags: list[str], avg_index_change: float, foreign: int, institution: int) -> str:
    if len(conflict_flags) >= 2:
        return "2/5"
    if abs(avg_index_change) >= 1.5 and ((foreign > 0 and institution > 0) or (foreign < 0 and institution < 0)):
        return "4/5"
    if abs(avg_index_change) >= 0.8:
        return "3/5"
    return "2/5"


def build_missing_signals(data: BriefingData) -> list[str]:
    missing = [
        "업종별 강세/약세",
        "상승·하락 종목 수",
        "외국인 선물 수급",
        "프로그램 매매",
    ]
    if not data.leaders:
        missing.append("거래 상위 종목")
    if data.mode == "morning" and not data.global_markets:
        missing.append("미국 시장 컨텍스트")
    return missing


def parse_review_output(content: str) -> tuple[list[str], str | None, str | None, int | None, str | None]:
    points: list[str] = []
    bias: str | None = None
    action: str | None = None
    confidence: int | None = None
    strategy: str | None = None
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("session_id:"):
            continue
        if line.startswith("판정:"):
            bias = line.split("판정:", 1)[1].strip()
            continue
        if line.startswith("행동:"):
            action = line.split("행동:", 1)[1].strip()
            continue
        if line.startswith("확신도:"):
            confidence_text = line.split("확신도:", 1)[1].strip()
            numerator = confidence_text.split("/", 1)[0].strip()
            confidence = int(numerator) if numerator.isdigit() else None
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
    return points[:4], bias, action, confidence, strategy
