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
chmod +x scripts/run_briefing.sh
uv sync --group dev
uv run stock-tracker open
uv run stock-tracker noon
uv run stock-tracker close
```

## 테스트
```bash
uv run --group dev pytest -q
```

## cron 등록
```bash
chmod +x scripts/run_briefing.sh
crontab /Users/osori/workbench/stock-tracker/deploy/stock-tracker.crontab
crontab -l
```

로그는 `logs/cron.log` 에 쌓입니다.
