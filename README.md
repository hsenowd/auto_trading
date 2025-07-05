# 🚀 미국 주식 초단타 스캘핑 자동매매 시스템

## 📋 프로젝트 개요

GPT API를 활용한 미국 주식 초단타 스캘핑 자동매매 시스템입니다.

### 주요 기능
- 🔍 급등주 조건검색 (갭상승, 거래대금 필터링)
- 🤖 GPT 기반 실시간 분석 (체결강도, 호가 스프레드)
- 📈 자동 매수/매도 주문 실행
- 🛡️ 리스크 제어 및 재시도 로직
- 📊 백테스트 및 성과 리포트

### 기술 스택
- **Trading API**: Alpaca Trading API
- **AI 분석**: OpenAI GPT API
- **언어**: Python 3.8+
- **주요 라이브러리**: alpaca-trade-api, openai, pandas, numpy

## 🏗️ 시스템 아키텍처

```
src/
├── screener/          # 급등주 조건검색
├── analyzer/          # GPT 분석 엔진
├── trader/            # 주문 실행
├── utils/             # 공통 함수
├── report/            # 리포트 생성
├── config/            # 환경 설정
└── tests/             # 테스트 코드
```

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일을 열어서 API 키들을 설정하세요
```

### 2. API 키 설정

`.env` 파일에 다음 API 키들을 설정하세요:

- **Alpaca Trading API**: https://alpaca.markets/에서 발급
- **OpenAI GPT API**: https://platform.openai.com/에서 발급
- **Slack Webhook** (선택사항): 알림용

### 3. 실행 모드

#### 기본 모드 (자동 거래)
```bash
python main.py
```

#### 수동 모드 (분석만)
```bash
python main.py --manual
```

#### 테스트 모드 (시스템 점검)
```bash
python main.py --test
```

#### 유닛 테스트
```bash
python tests/test_scalping_system.py
```

## 📊 주요 기능 설명

### 🔍 급등주 스크리너
- **갭 상승**: 전일 대비 3% 이상 갭 상승
- **거래량 급증**: 평균 거래량 대비 2배 이상
- **가격 범위**: $5 ~ $500
- **최소 거래량**: 100만주 이상

### 🤖 GPT 분석 엔진
- **실시간 분석**: 체결강도, 호가 스프레드, 거래량 분석
- **매수/매도 시그널**: 1-10점 점수 기반 판단
- **신뢰도 분류**: HIGH/MEDIUM/LOW/VERY_LOW

### 📈 자동 거래 시스템
- **포지션 관리**: 최대 5개 동시 포지션
- **리스크 제어**: 익절 0.5%, 손절 0.3%
- **시간 제한**: 최대 5분 보유
- **서킷 브레이커**: 일일 손실 $1,000 제한

### 📊 성과 분석
- **일일 리포트**: 승률, 수익률, 샤프 비율
- **거래 차트**: 누적 손익, 거래별 성과
- **리스크 지표**: 최대 낙폭, 수익 팩터

## 🏗️ 상세 아키텍처

```
📦 프로젝트 구조
├── 📄 main.py                    # 메인 실행 파일
├── 📁 config/                    # 환경 설정
│   └── 📄 config.py             # 시스템 설정
├── 📁 utils/                     # 공통 유틸리티
│   ├── 📄 logger.py             # 로깅 시스템
│   └── 📄 api_client.py         # API 클라이언트
├── 📁 screener/                  # 급등주 스크리너
│   └── 📄 stock_screener.py     # 조건 검색
├── 📁 analyzer/                  # GPT 분석 엔진
│   └── 📄 gpt_analyzer.py       # 실시간 분석
├── 📁 trader/                    # 자동 거래
│   └── 📄 scalping_trader.py    # 스캘핑 트레이더
├── 📁 report/                    # 성과 리포트
│   └── 📄 performance_report.py # 성과 분석
└── 📁 tests/                     # 테스트 코드
    └── 📄 test_scalping_system.py
```

## 💡 사용 예시

### 급등주 스크리닝
```python
from screener.stock_screener import get_stock_screener

screener = get_stock_screener()
top_stocks = screener.get_top_stocks(10)
print(f"상위 급등주: {top_stocks[0]['symbol']}")
```

### GPT 분석
```python
from analyzer.gpt_analyzer import analyze_entry_signal

analysis = analyze_entry_signal("TSLA")
print(f"시그널: {analysis['action']}, 점수: {analysis['signal_score']}")
```

### 개별 거래
```python
from trader.scalping_trader import trade_symbol

success = trade_symbol("NVDA")
print(f"거래 결과: {'성공' if success else '실패'}")
```

## 🔧 고급 설정

### 거래 파라미터 조정
`config/config.py`에서 다음 설정들을 조정할 수 있습니다:

```python
SCALPING_CONFIG = {
    "max_position_size": 10000,  # 최대 포지션 크기
    "max_positions": 5,          # 최대 동시 포지션
    "profit_target": 0.005,      # 익절 목표 (0.5%)
    "stop_loss": 0.003,          # 손절 기준 (0.3%)
    "holding_time_limit": 300,   # 최대 보유 시간 (초)
}
```

### GPT 프롬프트 커스터마이징
`config/config.py`의 `GPT_PROMPTS`에서 분석 프롬프트를 수정할 수 있습니다.

### 로그 설정
`config/config.py`의 `LOGGING_CONFIG`에서 로그 레벨과 보관 기간을 설정할 수 있습니다.

## 📈 백테스트

백테스트 기능을 통해 전략을 검증할 수 있습니다:

```python
from tests.test_scalping_system import TestBacktesting

# 간단한 백테스트 실행
test = TestBacktesting()
test.setUp()
test.test_simple_strategy_backtest()
```

## 🔍 모니터링

### 실시간 로그
```bash
tail -f logs/trading.log
```

### 거래 로그
```bash
tail -f logs/trades.log
```

### 성과 리포트
- 일일 리포트: `reports/daily_report_YYYYMMDD.json`
- 성과 차트: `reports/performance_chart_YYYYMMDD.png`

## ⚠️ 주의사항 및 리스크

### 🚨 중요한 경고
- **실제 거래 전 반드시 시뮬레이션 모드로 충분히 테스트하세요**
- **초기에는 작은 금액으로 시작하세요**
- **시장 변동성으로 인한 손실 위험을 항상 고려하세요**
- **API 키는 절대 공개하지 마세요**

### 💰 리스크 관리
- 일일 최대 손실 한도 설정
- 포지션 사이즈 제한
- 서킷 브레이커 활용
- 정기적인 성과 검토

### 🛠️ 기술적 고려사항
- **API 호출 제한**: Alpaca와 OpenAI API 호출 한도 확인
- **네트워크 지연**: 실시간 거래에서 지연 시간 고려
- **시장 시간**: 미국 동부시간 기준 거래 시간 확인

## 🤝 기여하기

1. Fork 프로젝트
2. 기능 브랜치 생성: `git checkout -b feature/AmazingFeature`
3. 변경사항 커밋: `git commit -m 'Add some AmazingFeature'`
4. 브랜치에 Push: `git push origin feature/AmazingFeature`
5. Pull Request 생성

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 있습니다. 자세한 내용은 `LICENSE` 파일을 참조하세요.

## 📞 지원

- 버그 리포트: [Issues](https://github.com/your-repo/issues)
- 기능 요청: [Discussions](https://github.com/your-repo/discussions)
- 이메일: your-email@example.com

---

**⚠️ 투자 책임 고지**: 이 소프트웨어는 교육 및 연구 목적으로 제공됩니다. 실제 투자 결정에 사용할 때는 충분한 검토와 테스트를 거쳐야 하며, 모든 투자 손실에 대한 책임은 사용자에게 있습니다.
