# SthocWin 시스템 아키텍처 및 기능 명세서

**문서 작성일:** 2026-05-04
**프로젝트명:** SthocWin (파이썬 퀀트 투자 대시보드 & 자동매매 시스템)

---

## 1. 개요 (Overview)

SthocWin은 기존의 단순한 주가 조회 웹 애플리케이션을 넘어, 개인 투자자가 수십 종목에 대한 **초고속 벡터 연산 백테스트**를 수행하고, 이 검증된 전략을 바탕으로 한국투자증권 API를 통해 **실전 매매 및 다중 채널 알림**을 수행할 수 있는 올인원(All-in-One) 퀀트 트레이딩 플랫폼입니다.

---

## 2. 주요 기능 및 아키텍처 (Key Features & Architecture)

시스템은 크게 두 가지 모드(UI 탭)로 분리되어 작동합니다.

### 2.1. 📊 백테스트 모드 (Backtest Simulator)
과거 데이터를 기반으로 나의 투자 전략이 얼마나 수익을 거둘 수 있었는지 통계적으로 검증하는 엔진입니다.

*   **유니버스 동적 추출 기능:**
    *   한국 주식 시장 대표 지수(KOSPI 200 / KOSDAQ 150) 또는 전체 시가총액 상위 100개 풀을 기반으로 분석할 유니버스를 선택합니다.
    *   선택된 풀 내에서 사용자가 지정한 기준(거래대금, 거래량, 시가총액, 등락률)에 따라 1개~50개까지 타겟 종목을 동적으로 필터링합니다.
*   **다중 지표(Multi-Indicators) 지원:**
    *   **이동평균선 (MA):** 단기/장기 골든크로스 로직. (예: 5/20일선)
    *   **RSI (상대강도지수):** 과매도 구간(예: 30) 이탈 시 매수, 과매수 구간(예: 70) 도달 시 매도.
    *   **MACD:** MACD 선이 Signal 선을 상향 돌파 시 매수, 하향 돌파 시 매도.
*   **복합 시그널 엔진:**
    *   사용자가 체크한 여러 지표들이 **동시에 만족할 때만 진입(AND)** 할지, **하나라도 만족하면 진입(OR)** 할지를 유연하게 선택할 수 있습니다.
*   **VectorBT 초고속 연산:**
    *   느린 For-loop 연산을 버리고 Pandas-TA 및 VectorBT를 활용한 행렬 연산을 도입하여 50개 종목에 대한 복잡한 연산도 1~2초 내외로 완료합니다.
*   **시각화 (Data Visualization):**
    *   Plotly 기반의 종목별 수익률 Bar Chart 지원.
    *   Bar Chart의 특정 종목 클릭 시, 해당 종목의 주가 및 선택된 지표(RSI 커브, MACD 히스토그램)가 오버레이된 Subplot 차트를 렌더링합니다.

### 2.2. 🤖 실전 투자 봇 모드 (Live Trading)
백테스트로 검증한 전략을 매일 실제 시장(또는 모의 계좌)에서 구동하는 운영 파이프라인입니다.

*   **한국투자증권 API 연동 (`broker_kis.py`):**
    *   OAuth2 기반 토큰 자동 발급 및 갱신.
    *   `KIS_MODE` 환경 변수 설정을 통해 안전한 **VIRTUAL(모의투자)** 환경과 **REAL(실전투자)** 환경을 코드 수정 없이 전환 가능.
    *   계좌 잔고 조회(`get_balance`) 및 실제 시장가/지정가 주문 전송(`create_order`).
*   **다중 채널 알림 라우터 (`notifier.py`):**
    *   `NOTIFICATION_CHANNELS` 설정에 따라 동시에 여러 메신저로 알림을 라우팅합니다.
    *   지원 채널: **Discord** (웹훅), **Slack** (웹훅), **Line Notify** (토큰), **Kakao** (REST API 나에게 보내기)
*   **종가 매매 전략 봇 (`bot_engine.py`):**
    *   장 마감 직전(15:20 경)에 당일 종가 데이터를 기반으로 시그널을 연산하여 "매수/매도 대상 종목"을 색출합니다.
    *   `AUTO_TRADING=True` 설정 시 자동으로 HTS를 거치지 않고 증권사 API를 통해 매매(현금 확보를 위해 선 매도, 후 매수)를 진행합니다.
*   **일일 장 마감 리포트 봇:**
    *   장 종료 후, 현재 내 계좌의 총 자산, 예수금, 주식 평가금액 및 개별 종목 수익률을 예쁘게 포맷팅하여 메신저로 일일 리포트를 전송합니다.

---

## 3. 핵심 모듈 구성 (Module Structure)

*   **`app.py`**: Streamlit 기반의 프론트엔드 UI 엔트리포인트. 백테스트 시뮬레이션 및 봇 설정 수동 제어 역할을 수행.
*   **`core_engine.py`**: VectorBT 기반의 대규모 병렬 백테스트 연산 처리.
*   **`data_pipeline.py`**: ThreadPoolExecutor와 FileLock, DuckDB를 활용한 캐시 스탬피드 방지 및 초고속 일봉/메타데이터 다운로드 관리.
*   **`src/broker_kis.py`**: 한국투자증권 오픈 API 명세가 구현된 매매 브로커.
*   **`src/bot_engine.py`**: `run_daily_bot()` (매매) 및 `run_daily_report()` (리포트) 등 봇의 실질적 두뇌 역할.
*   **`src/notifier.py`**: Slack, Discord, Line, Kakao 등 알림 플랫폼 통신망.
*   **`src/config.py`**: `.env` 파일과 시스템을 연결하는 환경 변수 바인딩 스크립트.

---

## 4. 실행 및 배포 (Run & Deploy)

### 4.1. 보안 설정 (.env)
시스템 루트 폴더에 `.env` 파일을 생성하고 아래 값들을 기입하여 구동합니다. UI 탭에서 [기본 `.env` 파일 생성] 버튼을 통해 쉽게 양식을 만들 수 있습니다.

```env
KIS_MODE=VIRTUAL
AUTO_TRADING=True
NOTIFICATION_CHANNELS=DISCORD,SLACK
```

### 4.2. 데몬 스케줄러 등록 (Crontab)
실전 모드 시, 리눅스 서버에서 다음과 같이 크론탭을 등록하여 매일 정해진 시간에 완전 무인(Unmanned) 자동화 운영을 달성할 수 있습니다.

```bash
# 매주 평일 오후 3시 20분에 봇 가동 (당일 시그널 포착 및 매매)
20 15 * * 1-5 cd /SthocWin && source .venv/bin/activate && python run_bot.py

# 매주 평일 오후 3시 40분에 장 마감 리포트 알림 전송
40 15 * * 1-5 cd /SthocWin && source .venv/bin/activate && python run_report.py
```