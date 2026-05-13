# stock-tracker

네이버 증권 `stock.naver.com` API/페이지와 Google News RSS를 조합해 한국 주식시장 브리핑을 Slack webhook으로 보내는 자동화 프로젝트입니다.
주요 목적은 **장전 / 개장 직후 / 장중 / 마감 후**에 읽기 쉬운 Slack Block Kit 브리핑을 보내는 것입니다.

## 브리핑 스케줄
- 장전 브리핑: 평일 **08:00 KST**
- 장 오픈 10분: 평일 **09:10 KST**
- 장중 정오 리뷰: 평일 **12:00 KST**
- 장 마감 리뷰: 평일 **15:40 KST**
- 단, KRX 휴장일/주말에는 보내지 않습니다.

## 현재 사용 중인 데이터 소스 / API / 페이지

### 1) 국내 지수: stock.naver.com index basic API
- 목적: KOSPI / KOSDAQ 지수
- 엔드포인트:
  - `https://stock.naver.com/api/securityFe/api/index/KOSPI/basic`
  - `https://stock.naver.com/api/securityFe/api/index/KOSDAQ/basic`
- 코드 위치: `src/stock_tracker/naver.py::fetch_index()`
- 사용 필드:
  - `closePrice`
  - `compareToPreviousClosePrice`
  - `compareToPreviousPrice`
  - `fluctuationsRatio`

### 2) 환율: stock.naver.com marketindex majors RPC
- 목적: USD/KRW 환율
- 엔드포인트:
  - `https://stock.naver.com/api/securityService/marketindex/majors/rpc`
- 코드 위치: `src/stock_tracker/naver.py::fetch_exchange_rate()`
- 선택 기준:
  - `reutersCode == "FX_USDKRW"`
- 사용 필드:
  - `calcPrice`
  - `fluctuations`
  - `fluctuationsType.text`
  - `stockExchangeType.nameKor`
- Slack 링크:
  - `https://stock.naver.com/marketindex/exchange/FX_USDKRW/price`

### 3) 투자자 수급: stock.naver.com index integration API
- 목적: 외국인/기관/개인 수급
- 엔드포인트:
  - `https://stock.naver.com/api/securityFe/api/index/KOSPI/integration`
- 코드 위치: `src/stock_tracker/naver.py::fetch_investors()`
- 사용 필드:
  - `dealTrendInfo.bizdate`
  - `dealTrendInfo.personalValue`
  - `dealTrendInfo.foreignValue`
  - `dealTrendInfo.institutionalValue`
- 현재 제한:
  - 구형 `finance.naver.com` 투자자별 매매동향 표에 있던 기관 세부 항목(금융투자/보험/투신/연기금 등)은
    신형 API에서 바로 주지 않아 현재는 `0`으로 채웁니다.
  - 따라서 Slack 메시지에서도 세부 값이 없으면 `기관 세부` 블록을 숨깁니다.

### 4) 거래량 상위: stock.naver.com domestic market stock API
- 목적: 장중/종가 기준 거래 상위 관심 종목
- 엔드포인트:
  - `https://stock.naver.com/api/domestic/market/stock/default?tradeType=KRX&marketType=ALL&orderType=quantTop&startIdx=0&pageSize=10`
- 코드 위치: `src/stock_tracker/naver.py::fetch_top_volume()`
- 사용 필드:
  - `itemcode`
  - `itemname`
  - `nowPrice`
  - `prevChangeRate`
- Slack 종목 링크:
  - `https://stock.naver.com/domestic/stock/{code}/price`

### 5) 해외 지수: stock.naver.com worldstock polling API
- 목적: 장전 브리핑용 밤사이 미국장 기준선
- 엔드포인트:
  - `https://stock.naver.com/api/polling/worldstock/index?reutersCodes=.INX,.IXIC,.SOX`
- 코드 위치: `src/stock_tracker/naver.py::fetch_global_markets()`
- 실제 사용 심볼:
  - `.INX` → S&P 500
  - `.IXIC` → NASDAQ
  - `.SOX` → SOX
- 사용 필드:
  - `closePrice`
  - `compareToPreviousClosePrice`
  - `fluctuationsRatio`
  - `marketStatus`
  - `localTradedAt`

### 6) 미국 10년물 / 달러인덱스 / 원유: stock.naver.com marketindex API
- 목적: 장전 브리핑용 거시 기준선
- 엔드포인트:
  - 미국 10년물: `https://stock.naver.com/api/securityService/marketindex/majors/bond`
  - 달러인덱스/원달러: `https://stock.naver.com/api/securityService/marketindex/majors/rpc`
  - 원유: `https://stock.naver.com/api/securityService/marketindex/energy`
- 코드 위치:
  - `src/stock_tracker/naver.py::fetch_global_markets()`
  - `src/stock_tracker/naver.py::fetch_oil_markets()`
- 선택 기준:
  - 미국 10년물: `reutersCode == "US10YT=RR"`
  - 달러인덱스: `reutersCode == ".DXY"`
  - WTI: `reutersCode == "CLcv1"`
  - 브렌트: `reutersCode == "LCOcv1"`
- 중요한 점:
  - 장전 브리핑은 이제 Yahoo 보정 로직 대신,
    **stock.naver.com 이 제공하는 직전 미국장 종가/전일 대비 값**을 직접 사용합니다.
  - 따라서 오전 8시 브리핑은 구형 Naver/별도 Yahoo 보정 대신 신형 Naver 증권 기준선으로 계산됩니다.

### 7) 해외/원유 뉴스: Google News RSS
- 목적: 장전 브리핑용 핵심 헤드라인
- 엔드포인트:
  - `https://news.google.com/rss/search`
- 코드 위치:
  - `src/stock_tracker/naver.py::fetch_global_headlines()`
  - `src/stock_tracker/naver.py::fetch_oil_headlines()`
- 현재 쿼리:
  - 글로벌 뉴스:
    - `when:1d (Nasdaq OR "S&P 500" OR semiconductors OR "Treasury yields" OR "Federal Reserve" OR inflation OR dollar OR futures)`
  - 원유 뉴스:
    - `when:1d ("crude oil" OR OPEC OR WTI OR "Brent crude" OR gasoline OR inventory OR refinery)`
- 후처리:
  - include / exclude keyword 필터를 적용해 잡음을 줄입니다.

### 8) 휴장일 판정: exchange_calendars
- 목적: 주말/휴장일 발송 방지
- 코드 위치: `src/stock_tracker/calendar.py`
- 사용 캘린더: `XKRX`

### 9) 전송 대상: Slack Incoming Webhook
- 목적: 브리핑 전송
- 환경변수:
  - `SLACK_WEBHOOK_URL`
- 코드 위치: `src/stock_tracker/slack.py`
- 현재 동작:
  - `text` fallback + `blocks` Block Kit payload 전송
  - 전송 성공 시 로그에 다음과 같은 요약이 남습니다.
    - HTTP status
    - response body
    - masked webhook URL
    - block count

## 실행 모드별 수집 기준
- `morning`
  - 국내 기준선: 전일 국내 지수 + 현재 USD/KRW
  - 해외 기준선: 밤사이 미국장 / 미국 10년물 / 달러인덱스 / 원유 / 관련 뉴스
- `open`
  - 국내 지수 실시간 + 장중 수급 + 거래량 상위
- `noon`
  - 국내 지수 실시간 + 장중 수급 + 거래량 상위
- `close`
  - 국내 지수 종가 성격 + 일간 수급 + 거래량 상위

## 로컬 실행
```bash
cp .env.example .env
# .env 에 Slack webhook URL 입력
chmod +x scripts/run_briefing.sh scripts/install_launchd.sh scripts/uninstall_launchd.sh
uv sync --group dev

uv run stock-tracker morning
uv run stock-tracker open
uv run stock-tracker noon
uv run stock-tracker close
```

배치와 동일한 CLI 경로를 직접 검증하려면:

```bash
source .venv/bin/activate
export PYTHONPATH="$PWD/src"
set -a
source .env
set +a
python -m stock_tracker.cli morning --at 2026-05-13T08:00:00+09:00
```

기본적으로 마지막 *종합 리뷰*는 Hermes one-shot 추론으로 생성됩니다.
Hermes 추론 호출이 실패하면 규칙 기반 리뷰로 자동 fallback 되고,
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
launchctl print gui/$(id -u)/com.osori.stock-tracker.morning | head -40
launchctl print gui/$(id -u)/com.osori.stock-tracker.open | head -40
```

제거:

```bash
./scripts/uninstall_launchd.sh
```

로그:
- `logs/cron.log`
- `logs/launchd-morning.log`
- `logs/launchd-open.log`
- `logs/launchd-noon.log`
- `logs/launchd-close.log`

## cron 등록 (보조 옵션)
Hermes 터미널에서는 `crontab` 등록이 macOS에서 멈출 수 있어, 설치 스크립트를 함께 제공합니다.

```bash
chmod +x scripts/run_briefing.sh scripts/install_cron.sh
./scripts/install_cron.sh
crontab -l
```

로그는 `logs/cron.log` 에 쌓입니다.
