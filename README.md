# stock-tracker

네이버 증권 실시간/테이블 데이터를 우선 활용해 한국 주식시장 브리핑을 Slack webhook으로 보내는 자동화 프로젝트입니다.

## 브리핑 스케줄
- 장 오픈 10분: 평일 09:10 KST
- 장중 정오 리뷰: 평일 12:00 KST
- 장 마감 리뷰: 평일 15:40 KST
- 단, KRX 휴장일/주말에는 보내지 않습니다.

## 데이터 소스
- Naver Finance polling API (`SERVICE_INDEX:KOSPI`, `SERVICE_INDEX:KOSDAQ`)
- Naver Finance 투자자별 매매동향 (`investorDealTrendTime.naver`, `investorDealTrendDay.naver`)
- Naver Finance 거래량 상위 (`sise_quant.naver`)

## 로컬 실행
```bash
cp .env.example .env
# .env 에 Slack webhook URL 입력
chmod +x scripts/run_briefing.sh scripts/install_launchd.sh scripts/uninstall_launchd.sh
uv sync --group dev
uv run stock-tracker open
uv run stock-tracker noon
uv run stock-tracker close
```

기본적으로 마지막 *종합 리뷰*는 Codex CLI 자유서술 추론으로 생성됩니다.
Codex 실행이 실패하면 규칙 기반 리뷰로 자동 fallback 되고,
메시지 안에 `추론이 실패해서 규칙기반으로 나온 리뷰입니다.` 안내가 표시됩니다.

## 테스트
```bash
uv run --group dev pytest -q
```

## launchd 등록 (권장)
macOS에서는 `launchd`가 `cron`보다 정시성이 좋고, Hermes 세션의 `crontab` hang도 피할 수 있습니다.

```bash
chmod +x scripts/run_briefing.sh scripts/install_launchd.sh scripts/uninstall_launchd.sh
./scripts/install_launchd.sh
launchctl print gui/$(id -u)/com.osori.stock-tracker.open | head -40
```

제거:

```bash
./scripts/uninstall_launchd.sh
```

로그는 `logs/cron.log` 와 `logs/launchd-*.log` 에 쌓입니다.

## cron 등록 (보조 옵션)
Hermes 터미널에서는 `crontab` 등록이 macOS에서 멈출 수 있어, 설치 스크립트를 함께 제공합니다.

```bash
chmod +x scripts/run_briefing.sh scripts/install_cron.sh
./scripts/install_cron.sh
crontab -l
```

로그는 `logs/cron.log` 에 쌓입니다.
