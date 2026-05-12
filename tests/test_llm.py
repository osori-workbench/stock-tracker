from datetime import datetime
from zoneinfo import ZoneInfo

from stock_tracker.llm import CodexCliReviewGenerator, ReviewResult
from stock_tracker.models import BriefingData, ExchangeRateSnapshot, IndexSnapshot, InvestorSnapshot, TopStock


KST = ZoneInfo("Asia/Seoul")


class FakeCompletedProcess:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = "") -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


class FakeRunner:
    def __init__(self, result: FakeCompletedProcess | Exception) -> None:
        self.result = result
        self.calls: list[dict] = []

    def __call__(self, command: list[str], *, input: str, text: bool, capture_output: bool, timeout: int, check: bool) -> FakeCompletedProcess:
        self.calls.append(
            {
                "command": command,
                "input": input,
                "text": text,
                "capture_output": capture_output,
                "timeout": timeout,
                "check": check,
            }
        )
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def make_data() -> BriefingData:
    return BriefingData(
        mode="close",
        now=datetime(2026, 5, 12, 15, 40, tzinfo=KST),
        market_label="마감 후",
        indices=[
            IndexSnapshot(name="KOSPI", value=2640.15, change_value=-11.09, change_percent=-0.42),
            IndexSnapshot(name="KOSDAQ", value=845.29, change_value=2.05, change_percent=0.24),
        ],
        exchange_rate=ExchangeRateSnapshot(name="USD/KRW", value=1388.70, change_value=3.7, direction="상승", source="하나은행"),
        investors=InvestorSnapshot(
            basis_label="15:40",
            individual=-1200,
            foreign=900,
            institution=300,
            financial_investment=100,
            insurance=50,
            trust_private=25,
            bank=10,
            other_financial=5,
            pension=80,
            other_corporation=-20,
        ),
        leaders=[
            TopStock(code="005930", name="삼성전자", price=81200.0, change_percent=1.22),
            TopStock(code="000660", name="SK하이닉스", price=213500.0, change_percent=2.81),
        ],
    )


def test_codex_cli_review_generator_parses_bullets_and_builds_prompt() -> None:
    runner = FakeRunner(
        FakeCompletedProcess(
            stdout="- 외국인과 기관이 동반 순매수라 수급의 질이 괜찮습니다.\n- 환율 상승은 부담이지만 반도체 대형주가 지수를 지지합니다.\n- 추격매수보다 주도주 지속성 확인이 더 중요합니다.\n"
        )
    )
    generator = CodexCliReviewGenerator(codex_bin="/Applications/Codex.app/Contents/Resources/codex", runner=runner)

    result = generator.generate(make_data())

    assert result == ReviewResult(
        points=[
            "외국인과 기관이 동반 순매수라 수급의 질이 괜찮습니다.",
            "환율 상승은 부담이지만 반도체 대형주가 지수를 지지합니다.",
            "추격매수보다 주도주 지속성 확인이 더 중요합니다.",
        ],
        fallback_notice=None,
    )
    assert runner.calls[0]["command"] == [
        "/Applications/Codex.app/Contents/Resources/codex",
        "exec",
        "--skip-git-repo-check",
        "-m",
        "gpt-5-codex",
        "-",
    ]
    assert "KOSPI" in runner.calls[0]["input"]
    assert "삼성전자" in runner.calls[0]["input"]
    assert "JSON 데이터" in runner.calls[0]["input"]


def test_codex_cli_review_generator_returns_fallback_notice_when_command_fails() -> None:
    runner = FakeRunner(RuntimeError("codex failed"))
    generator = CodexCliReviewGenerator(codex_bin="codex", runner=runner)

    result = generator.generate(make_data())

    assert result.points == []
    assert result.fallback_notice == "추론이 실패해서 규칙기반으로 나온 리뷰입니다."
