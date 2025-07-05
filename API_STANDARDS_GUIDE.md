# 🎯 한국투자 Open API 표준화/디버깅 시스템 가이드

> **파라미터 값과 함수 API 함수 및 TR 표준화/디버깅 완벽 가이드**

## 📋 목차

1. [시스템 개요](#-시스템-개요)
2. [핵심 구성 요소](#-핵심-구성-요소)
3. [설치 및 설정](#-설치-및-설정)
4. [사용법](#-사용법)
5. [API 표준화](#-api-표준화)
6. [디버깅 시스템](#-디버깅-시스템)
7. [테스트 및 검증](#-테스트-및-검증)
8. [실제 사용 예시](#-실제-사용-예시)
9. [문제 해결](#-문제-해결)

---

## 🎯 시스템 개요

한국투자 Open API의 **파라미터 표준화**, **API 함수 표준화**, **TR 코드 표준화** 및 **디버깅**을 위한 종합 시스템입니다.

### 🌟 주요 기능

- ✅ **TR 코드 표준화**: 모든 한국투자 API TR 코드를 Enum으로 관리
- ✅ **파라미터 검증**: 요청 파라미터 자동 검증 및 타입 변환
- ✅ **응답 표준화**: API 응답을 표준 데이터 클래스로 파싱
- ✅ **디버깅 시스템**: API 호출 추적, 성능 모니터링, 오류 분석
- ✅ **테스트 지원**: 포괄적인 단위 테스트 및 통합 테스트
- ✅ **실시간 모니터링**: API 성능 지표 및 장애 감지

---

## 🔧 핵심 구성 요소

### 1. **API 표준화 시스템** (`utils/kis_api_standards.py`)

```python
from utils.kis_api_standards import (
    TRCode,                     # TR 코드 표준화
    MarketCode,                # 시장 코드 표준화
    OrderSide, OrderType,      # 주문 관련 표준화
    create_stock_price_request, # 편의 함수들
    get_kis_standards          # 표준화 인스턴스
)
```

### 2. **디버깅 시스템** (`utils/api_debugger.py`)

```python
from utils.api_debugger import (
    get_api_debugger,          # 디버거 인스턴스
    LogLevel,                  # 로그 레벨
    debug_api_call,           # 데코레이터
    APICallStatus             # 호출 상태
)
```

### 3. **통합 API 클라이언트** (`utils/api_client.py`)

```python
from utils.api_client import KISAPIClient

client = KISAPIClient()
# 표준화 + 디버깅이 통합된 클라이언트
```

---

## ⚙️ 설치 및 설정

### 1. **의존성 설치**

```bash
pip install -r requirements.txt
```

### 2. **환경 설정**

`.env` 파일에 한국투자 API 키 설정:

```env
# 한국투자 Open API 설정
KIS_APP_KEY=your_app_key
KIS_APP_SECRET=your_app_secret
KIS_ACCOUNT_NO=your_account_number
```

### 3. **디렉토리 구조**

```
프로젝트/
├── utils/
│   ├── kis_api_standards.py    # API 표준화 시스템
│   ├── api_debugger.py         # 디버깅 시스템
│   └── api_client.py           # 통합 클라이언트
├── tests/
│   └── test_api_standards.py   # 테스트 코드
├── debug_and_test.py           # 종합 검증 스크립트
├── logs/                       # 로그 파일들
├── data/                       # 데이터 파일들
└── API_STANDARDS_GUIDE.md      # 이 가이드
```

---

## 🚀 사용법

### 빠른 시작

```python
from utils.kis_api_standards import create_stock_price_request, get_kis_standards
from utils.api_client import KISAPIClient

# 1. 표준화된 요청 생성
request = create_stock_price_request("AAPL", "NAS")

# 2. API 클라이언트로 호출 (자동 디버깅 포함)
client = KISAPIClient()
result = client.get_overseas_stock_price("AAPL")

# 3. 디버깅 정보 확인
from utils.api_debugger import get_api_debugger
debugger = get_api_debugger()
summary = debugger.get_performance_summary()
print(f"총 API 호출: {summary['total_calls']}회")
```

### 전체 시스템 검증

```bash
python debug_and_test.py
```

---

## 📝 API 표준화

### 1. **TR 코드 표준화**

```python
from utils.kis_api_standards import TRCode

# 표준화된 TR 코드 사용
print(TRCode.OVERSEAS_STOCK_PRICE.value)  # "HHDFS00000300"
print(TRCode.OVERSEAS_STOCK_ORDER.value)  # "HTRFB_JTTT1002U"
print(TRCode.OVERSEAS_STOCK_BALANCE.value) # "HTRFB_FTRG3210U"
```

### 2. **파라미터 검증**

```python
from utils.kis_api_standards import get_kis_standards

standards = get_kis_standards()

# 자동 파라미터 검증
try:
    request = standards.create_request(
        TRCode.OVERSEAS_STOCK_PRICE,
        SYMB="AAPL",
        EXCD="NAS"  # 필수 파라미터
    )
    print("✅ 파라미터 검증 성공")
except ValueError as e:
    print(f"❌ 파라미터 오류: {e}")
```

### 3. **응답 표준화**

```python
# API 응답을 표준 형식으로 파싱
raw_response = {"rt_cd": "0", "output": {...}}
response = standards.parse_response(TRCode.OVERSEAS_STOCK_PRICE, raw_response)

if response.rt_cd == "0":
    stock_info = response.output  # StockInfo 객체
    print(f"종목: {stock_info.symbol}")
    print(f"현재가: ${stock_info.current_price}")
```

### 4. **편의 함수 활용**

```python
from utils.kis_api_standards import (
    create_stock_price_request,
    create_order_request,
    create_balance_request
)

# 주식 현재가 조회 요청
price_request = create_stock_price_request("AAPL", "NAS")

# 주문 요청
order_request = create_order_request(
    account_no="12345678",
    symbol="AAPL",
    quantity=100,
    price=150.0,
    side="02",  # 매수
    market="NASD"
)

# 잔고 조회 요청
balance_request = create_balance_request("12345678", "NASD")
```

---

## 🔍 디버깅 시스템

### 1. **자동 API 호출 추적**

```python
from utils.api_debugger import get_api_debugger

debugger = get_api_debugger()

# API 호출 자동 추적 (KISAPIClient 사용시)
client = KISAPIClient()
result = client.get_overseas_stock_price("AAPL")

# 최근 호출 기록 확인
recent_calls = debugger.get_recent_calls(5)
for call in recent_calls:
    print(f"{call['tr_code']}: {call['status']} ({call['response_time_ms']:.1f}ms)")
```

### 2. **성능 모니터링**

```python
# 성능 요약 조회
summary = debugger.get_performance_summary()
print(f"""
📊 API 성능 요약:
- 총 호출 수: {summary['total_calls']:,}회
- 성공률: {summary['success_rate']:.1f}%
- 평균 응답시간: {summary['avg_response_time_ms']:.1f}ms
- 최소 응답시간: {summary['min_response_time_ms']:.1f}ms
- 최대 응답시간: {summary['max_response_time_ms']:.1f}ms
""")

# TR별 통계
for tr_code, stats in summary['tr_code_stats'].items():
    print(f"{tr_code}: {stats['total']}회 (성공률: {stats['success']/stats['total']*100:.1f}%)")
```

### 3. **실패 분석**

```python
# 최근 24시간 실패 분석
failures = debugger.analyze_failures(24)
print(f"""
❌ 실패 분석 (최근 24시간):
- 총 실패: {failures['total_failures']}회
- 실패율: {failures['failure_rate']:.1f}%
""")

# 주요 실패 원인
for reason, count in failures['top_failure_reasons'].items():
    print(f"- {reason}: {count}회")
```

### 4. **디버그 리포트 생성**

```python
# 종합 디버그 리포트 생성
report = debugger.generate_debug_report()
print(report)

# 파일로 저장
with open("debug_report.txt", "w", encoding="utf-8") as f:
    f.write(report)
```

### 5. **함수 데코레이터 사용**

```python
from utils.api_debugger import debug_api_call

@debug_api_call("CUSTOM_FUNCTION")
def my_api_function():
    # 자동으로 실행 시간과 성공/실패가 기록됨
    time.sleep(0.1)
    return {"result": "success"}

result = my_api_function()
```

---

## 🧪 테스트 및 검증

### 1. **종합 검증 실행**

```bash
python debug_and_test.py
```

### 2. **개별 테스트 실행**

```bash
python tests/test_api_standards.py
```

### 3. **검증 항목**

- ✅ TR 코드 표준화 검증
- ✅ 파라미터 검증 시스템 테스트
- ✅ 요청 생성 테스트
- ✅ 응답 파싱 테스트
- ✅ 디버깅 시스템 테스트
- ✅ API 클라이언트 통합 테스트

---

## 💡 실제 사용 예시

### 예시 1: 주식 현재가 조회 with 디버깅

```python
from utils.api_client import KISAPIClient
from utils.api_debugger import get_api_debugger

# 클라이언트 초기화 (자동으로 디버깅 활성화)
client = KISAPIClient()

# 주식 현재가 조회
stock_data = client.get_overseas_stock_price("AAPL", "NAS")

if stock_data:
    print(f"""
📈 {stock_data['symbol']} ({stock_data['name']})
- 현재가: ${stock_data['current_price']:.2f}
- 전일대비: {stock_data['daily_change']:+.2f} ({stock_data['daily_change_rate']:+.2f}%)
- 거래량: {stock_data['volume']:,}
- 호가강도: {stock_data['volume_intensity']:.2f}
""")

# 디버깅 정보 확인
debugger = get_api_debugger()
recent = debugger.get_recent_calls(1)[0]
print(f"🔍 API 호출 정보: {recent['status']} ({recent['response_time_ms']:.1f}ms)")
```

### 예시 2: 파라미터 검증 및 오류 처리

```python
from utils.kis_api_standards import get_kis_standards, TRCode

standards = get_kis_standards()

def safe_create_request(symbol, market):
    """안전한 요청 생성 with 검증"""
    try:
        # 파라미터 검증
        request = standards.create_request(
            TRCode.OVERSEAS_STOCK_PRICE,
            SYMB=symbol,
            EXCD=market
        )
        print(f"✅ 요청 생성 성공: {symbol}")
        return request
        
    except ValueError as e:
        print(f"❌ 파라미터 오류: {e}")
        return None

# 올바른 사용
request1 = safe_create_request("AAPL", "NAS")  # ✅ 성공

# 잘못된 사용
request2 = safe_create_request("AAPL", "INVALID")  # ❌ 실패
```

### 예시 3: 성능 모니터링 대시보드

```python
import time
from utils.api_debugger import get_api_debugger

def performance_dashboard():
    """실시간 성능 대시보드"""
    debugger = get_api_debugger()
    
    while True:
        summary = debugger.get_performance_summary()
        failures = debugger.analyze_failures(1)  # 최근 1시간
        
        print("\033[2J\033[H")  # 화면 지우기
        print("🔍 한국투자 API 성능 대시보드")
        print("=" * 50)
        print(f"총 호출: {summary['total_calls']:,}회")
        print(f"성공률: {summary['success_rate']:.1f}%")
        print(f"평균 응답시간: {summary['avg_response_time_ms']:.1f}ms")
        print(f"최근 1시간 실패: {failures.get('total_failures', 0)}회")
        
        # TR별 성능
        print("\n📊 TR별 성능:")
        for tr_code, stats in summary['tr_code_stats'].items():
            success_rate = (stats['success'] / stats['total']) * 100
            print(f"  {tr_code}: {stats['total']}회 ({success_rate:.1f}%)")
        
        print(f"\n🕒 업데이트: {time.strftime('%H:%M:%S')}")
        time.sleep(10)  # 10초마다 업데이트

# 백그라운드에서 실행
# performance_dashboard()
```

---

## ❗ 문제 해결

### 1. **일반적인 오류**

#### 파라미터 검증 실패

```
ValueError: Missing required parameters for OVERSEAS_STOCK_PRICE: ['EXCD']
```

**해결방법**: 필수 파라미터를 모두 제공하세요.

```python
# ❌ 잘못된 사용
request = create_stock_price_request("AAPL")  # EXCD 누락

# ✅ 올바른 사용
request = create_stock_price_request("AAPL", "NAS")
```

#### 잘못된 거래소 코드

```
ValueError: Invalid value for EXCD: allowed ['NAS', 'NYS', 'AMS'], got INVALID
```

**해결방법**: 올바른 거래소 코드를 사용하세요.

```python
# 올바른 거래소 코드들
MarketCode.NASDAQ.value  # "NAS"
MarketCode.NYSE.value    # "NYS"
MarketCode.AMEX.value    # "AMS"
```

### 2. **디버깅 이슈**

#### 디버깅 로그가 표시되지 않음

```python
from utils.api_debugger import get_api_debugger, LogLevel

# 디버그 레벨을 TRACE로 설정
debugger = get_api_debugger()
debugger.debug_level = LogLevel.TRACE
```

#### 성능 지표가 0으로 표시됨

```python
# API 호출이 실제로 이루어져야 지표가 수집됩니다
client = KISAPIClient()
client.get_overseas_stock_price("AAPL")  # 실제 호출 후 확인
```

### 3. **API 인증 문제**

#### 토큰 발급 실패

```python
# 환경 변수 확인
import os
print("APP_KEY:", os.getenv("KIS_APP_KEY", "NOT_SET"))
print("APP_SECRET:", os.getenv("KIS_APP_SECRET", "NOT_SET"))
```

---

## 📚 추가 자료

### API 템플릿 정보 조회

```python
from utils.kis_api_standards import get_kis_standards, TRCode

standards = get_kis_standards()

# TR 코드별 파라미터 정보
info = standards.get_parameter_info(TRCode.OVERSEAS_STOCK_PRICE)
print("필수 파라미터:", info['required'])
print("선택 파라미터:", info['optional'])
print("검증 규칙:", info['validation'])
```

### 모든 지원 TR 코드 확인

```python
all_codes = standards.get_all_tr_codes()
print("지원되는 TR 코드들:")
for code in all_codes:
    print(f"  - {code}")
```

### 실시간 로그 확인

```bash
# 실시간 API 디버그 로그 확인
tail -f logs/api_debug.log

# 특정 TR 코드만 필터링
tail -f logs/api_debug.log | grep "HHDFS00000300"
```

---

## 🔄 업데이트 및 확장

### 새로운 TR 코드 추가

1. `utils/kis_api_standards.py`의 `TRCode` Enum에 추가
2. `parameter_templates`에 검증 규칙 추가
3. 필요시 파싱 로직 추가

### 커스텀 디버깅 기능 추가

```python
from utils.api_debugger import get_api_debugger

debugger = get_api_debugger()

# 커스텀 메트릭 추가
def add_custom_metric(metric_name, value):
    # 커스텀 메트릭 로직 구현
    pass
```

---

## 🎯 결론

이 표준화/디버깅 시스템을 통해:

- ✅ **안정적인 API 호출**: 파라미터 검증으로 오류 방지
- ✅ **효율적인 디버깅**: 자동 추적 및 성능 모니터링
- ✅ **코드 품질 향상**: 표준화된 구조로 유지보수성 증대
- ✅ **문제 해결 가속화**: 상세한 로그 및 분석 도구

**문의사항이나 개선사항이 있으시면 언제든 연락주세요!** 🚀