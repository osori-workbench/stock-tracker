# stock-tracker

네이버 증권과 Yahoo/Google News 데이터를 조합해 한국 주식시장 브리핑을 Slack webhook으로 보내는 자동화 프로젝트입니다.
주요 목적은 **장전 / 개장 직후 / 장중 / 마감 후**에 읽기 쉬운 Slack Block Kit 브리핑을 보내는 것입니다.

## 브리핑 스케줄
- 장전 브리핑: 평일 **08:00 KST**
- 장 오픈 10분: 평일 **09:10 KST**
- 장중 정오 리뷰: 평일 **12:00 KST**
- 장 마감 리뷰: 평일 **15:40 KST**
- 단, KRX 휴장일/주말에는 보내지 않습니다.

## 현재 사용 중인 데이터 소스 / API / 페이지

### 1) 국내 지수: Naver Finance polling API
- 목적: KOSPI / KOSDAQ 지수
- 엔드포인트:
  - `https://polling.finance.naver.com/api/realtime?query=SERVICE_INDEX:KOSPI`
  - `https://polling.finance.naver.com/api/realtime?query=SERVICE_INDEX:KOSDAQ`
- 코드 위치: `src/stock_tracker/naver.py::fetch_index()`
- 사용 필드:
  - `cd`: 지수명
  - `nv`: 현재값 (`/100` 스케일 보정)
  - `cv`: 전일 대비 (`/100` 스케일 보정)
  - `cr`: 등락률

### 2) 환율: Naver Finance marketindex HTML
- 목적: USD/KRW 환율
- 페이지:
  - `https://finance.naver.com/marketindex/`
- 코드 위치: `src/stock_tracker/naver.py::fetch_exchange_rate()`
- 주요 selector:
  - `#exchangeList li.on`
  - `span.value`
  - `span.change`
  - `div.head_info span.blind`
  - `.graph_info .source`
- Slack 링크에 사용하는 상세 페이지:
  - `https://finance.naver.com/marketindex/exchangeDetail.naver?marketindexCd=FX_USDKRW`

### 3) 투자자 수급: Naver Finance 투자자별 매매동향 HTML
- 목적: 외국인/기관/개인 수급
- 페이지:
  - 장중: `https://finance.naver.com/sise/investorDealTrendTime.naver?bizdate=YYYYMMDD`
  - 마감: `https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate=YYYYMMDD`
- 코드 위치: `src/stock_tracker/naver.py::fetch_investors()`
- 주의:
  - `bizdate` 없이 호출하면 빈 표가 나올 수 있습니다.
  - `open`/`noon` 모드는 intraday 페이지, `close` 모드는 daily 페이지를 사용합니다.

### 4) 거래량 상위: Naver Finance 거래량 페이지
- 목적: 장중/종가 기준 거래 상위 관심 종목
- 페이지:
  - `https://finance.naver.com/sise/sise_quant.naver`
- 코드 위치: `src/stock_tracker/naver.py::fetch_top_volume()`
- 파싱 포인트:
  - `table.type_2`
  - `a.tltle`
  - 종목 링크의 `code=` 파라미터

### 5) 해외 지수 / 금리 / 달러 / 원유: Yahoo Finance chart API
- 목적: 장전 브리핑용 밤사이 미국장 및 거시 기준선
- 기본 엔드포인트 패턴:
  - `https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d`
- 실제 사용 심볼:
  - `^GSPC` → S&P 500
  - `^IXIC` → NASDAQ
  - `^SOX` → SOX
  - `^TNX` → 미국 10년물
  - `DX-Y.NYB` → 달러인덱스
  - `CL=F` → WTI
  - `BZ=F` → 브렌트
- 코드 위치:
  - `src/stock_tracker/naver.py::fetch_global_markets()`
  - `src/stock_tracker/naver.py::fetch_oil_markets()`
  - `src/stock_tracker/naver.py::parse_yahoo_chart_snapshot()`
- **중요한 현재 기준**:
  - 장전 브리핑에서는 `meta.chartPreviousClose`를 직접 신뢰하지 않습니다.
  - Yahoo 응답의 `indicators.quote[0].close` 배열에서 `null`을 제거한 뒤,
    **가장 최근 2개의 확정 종가**를 `(전일 종가, 당일 종가)`로 사용합니다.
  - 따라서 오전 8시 장전 브리핑은 사실상 **미국장 오전 6시 종가 기준**으로 계산됩니다.
  - close 히스토리가 비어 있을 때만 예외적으로 `regularMarketPrice` / `chartPreviousClose`로 fallback 합니다.

### 6) 해외/원유 뉴스: Google News RSS
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

### 7) 휴장일 판정: exchange_calendars
- 목적: 주말/휴장일 발송 방지
- 코드 위치: `src/stock_tracker/calendar.py`
- 사용 캘린더: `XKRX`

### 8) 전송 대상: Slack Incoming Webhook
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
