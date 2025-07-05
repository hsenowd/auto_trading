"""
환경 설정 파일
한국투자 Open API 기반 미국 주식 초단타 스캘핑 자동매매 시스템의 모든 설정을 관리합니다.
"""

import os
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# 한국투자 Open API 설정
# =============================================================================

# 한국투자 API 설정
KIS_CONFIG = {
    # 실전투자 앱키/앱시크리트
    "app_key": os.getenv("KIS_APP_KEY", ""),
    "app_secret": os.getenv("KIS_APP_SECRET", ""),
    
    # 모의투자 앱키/앱시크리트 (테스트용)
    "paper_app_key": os.getenv("KIS_PAPER_APP_KEY", ""),
    "paper_app_secret": os.getenv("KIS_PAPER_APP_SECRET", ""),
    
    # 계좌 정보
    "account_no": os.getenv("KIS_ACCOUNT_NO", ""),  # 계좌번호 8자리
    "product_code": os.getenv("KIS_PRODUCT_CODE", "01"),  # 계좌상품코드 (01: 주식, 03: 선물옵션)
    
    # 서버 URL
    "prod_url": "https://openapi.koreainvestment.com:9443",  # 실전투자
    "vps_url": "https://openapivts.koreainvestment.com:29443",  # 모의투자
    
    # 기본 설정
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "is_paper_trading": True,  # 모의투자 여부 (실전투자 시 False)
    "token_file_path": "config/kis_token.yaml",  # 토큰 저장 경로
}

# OpenAI GPT API (실시간 분석)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# =============================================================================
# 거래 설정 (한국투자 미국주식 기준)
# =============================================================================

# 스캘핑 전략 설정
SCALPING_CONFIG = {
    "max_position_size": 10000,  # 최대 포지션 크기 (USD)
    "max_positions": 5,          # 최대 동시 포지션 수
    "profit_target": 0.005,      # 익절 목표 (0.5%)
    "stop_loss": 0.003,          # 손절 기준 (0.3%)
    "holding_time_limit": 300,   # 최대 보유 시간 (초)
}

# 급등주 스크리닝 조건
SCREENING_CONFIG = {
    "min_volume": 1000000,       # 최소 거래량
    "min_price": 5.0,            # 최소 주가 (USD)
    "max_price": 500.0,          # 최대 주가 (USD)
    "gap_threshold": 0.03,       # 갭 상승 임계값 (3%)
    "volume_spike": 2.0,         # 거래량 급증 배수
}

# =============================================================================
# GPT 분석 설정
# =============================================================================

GPT_CONFIG = {
    "model": "gpt-4-turbo",
    "temperature": 0.3,
    "max_tokens": 1000,
    "timeout": 30,
}

# GPT 분석 프롬프트 템플릿
GPT_PROMPTS = {
    "entry_signal": """
    다음 미국 주식 데이터를 분석하여 매수 시점인지 판단해주세요:
    
    종목: {symbol}
    현재가: ${current_price}
    체결강도: {volume_intensity}
    호가 스프레드: {bid_ask_spread}
    1분봉 거래량: {volume_1m}
    5분봉 거래량: {volume_5m}
    전일 대비 등락률: {daily_change}%
    
    질문:
    1. 현재 체결강도가 돌파 신호인가요?
    2. 호가 스프레드가 좁아지는 추세인가요?
    3. 거래량이 급증하고 있나요?
    4. 매수 신호인지 1-10점으로 평가해주세요.
    
    답변 형식: {{
        "signal_score": 점수,
        "reasoning": "분석 근거",
        "action": "BUY/HOLD/SELL",
        "confidence": "HIGH/MEDIUM/LOW"
    }}
    """,
    
    "exit_signal": """
    다음 포지션의 청산 시점을 판단해주세요:
    
    종목: {symbol}
    매수가: ${entry_price}
    현재가: ${current_price}
    수익률: {profit_loss}%
    보유 시간: {holding_time}초
    현재 거래량: {current_volume}
    
    질문:
    1. 추가 상승 여력이 있나요?
    2. 이익 실현 시점인가요?
    3. 손절 필요성이 있나요?
    
    답변 형식: {{
        "exit_score": 점수,
        "reasoning": "분석 근거",
        "action": "HOLD/SELL",
        "confidence": "HIGH/MEDIUM/LOW"
    }}
    """
}

# =============================================================================
# 로깅 및 모니터링 설정
# =============================================================================

LOGGING_CONFIG = {
    "level": "INFO",
    "format": "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}",
    "rotation": "1 day",
    "retention": "30 days",
    "log_file": "logs/trading.log",
}

# 텔레그램 알림 설정
TELEGRAM_CONFIG = {
    "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
    "chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
    "enabled": bool(os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"),
}

# =============================================================================
# 미국 주식 거래 시간 설정 (한국 시간 기준, 썸머타임 자동 적용)
# =============================================================================

def is_dst_active(date=None):
    """미국 동부시간 썸머타임 적용 여부 확인"""
    if date is None:
        date = datetime.now()
    
    year = date.year
    
    # DST 시작: 3월 둘째 주 일요일 2:00 AM
    march_second_sunday = datetime(year, 3, 8)
    while march_second_sunday.weekday() != 6:  # 일요일: 6
        march_second_sunday += timedelta(days=1)
    dst_start = march_second_sunday
    
    # DST 종료: 11월 첫째 주 일요일 2:00 AM
    november_first_sunday = datetime(year, 11, 1)
    while november_first_sunday.weekday() != 6:  # 일요일: 6
        november_first_sunday += timedelta(days=1)
    dst_end = november_first_sunday
    
    return dst_start <= date < dst_end

def get_us_market_hours_kr():
    """한국 시간 기준 미국 시장 시간 반환"""
    dst_active = is_dst_active()
    
    if dst_active:  # 썸머타임 (EDT, UTC-4)
        # 미국 시간 + 13시간 = 한국 시간
        return {
            "pre_market_start": "17:00",    # 4:00 AM EDT = 17:00 KST
            "market_open": "22:30",         # 9:30 AM EDT = 22:30 KST
            "market_close": "05:00",        # 4:00 PM EDT = 05:00 KST (다음날)
            "after_market_end": "09:00",    # 8:00 PM EDT = 09:00 KST (다음날)
        }
    else:  # 표준시 (EST, UTC-5)
        # 미국 시간 + 14시간 = 한국 시간
        return {
            "pre_market_start": "18:00",    # 4:00 AM EST = 18:00 KST
            "market_open": "23:30",         # 9:30 AM EST = 23:30 KST
            "market_close": "06:00",        # 4:00 PM EST = 06:00 KST (다음날)
            "after_market_end": "10:00",    # 8:00 PM EST = 10:00 KST (다음날)
        }

# 동적으로 시장 시간 설정
TRADING_HOURS = get_us_market_hours_kr()

# 스캘핑 활성 시간 (변동성이 높은 시간대, 한국 시간 기준)
def get_scalping_active_hours():
    """스캘핑 활성 시간 반환 (프리마켓 + 정규시장 + 애프터마켓 포함)"""
    hours = get_us_market_hours_kr()
    
    return [
        # 프리마켓 (변동성 높은 시간)
        (hours["pre_market_start"], hours["market_open"]),
        
        # 정규 시장 (오픈 1시간 - 높은 변동성)
        (hours["market_open"], "23:30" if is_dst_active() else "00:30"),
        
        # 정규 시장 (마감 2시간 - 높은 변동성) 
        ("03:00" if is_dst_active() else "04:00", hours["market_close"]),
        
        # 애프터마켓 (첫 1시간 - 실적 발표 등)
        (hours["market_close"], "06:00" if is_dst_active() else "07:00"),
    ]

SCALPING_ACTIVE_HOURS = get_scalping_active_hours()

# 미국 시장 휴장일 확인을 위한 설정
US_MARKET_HOLIDAYS = [
    "New Year's Day",
    "Martin Luther King Jr. Day", 
    "Presidents' Day",
    "Good Friday",
    "Memorial Day",
    "Juneteenth",
    "Independence Day",
    "Labor Day",
    "Thanksgiving",
    "Christmas Day"
]

# =============================================================================
# 리스크 관리 설정
# =============================================================================

RISK_MANAGEMENT = {
    "max_daily_loss": 1000,      # 일일 최대 손실 (USD)
    "max_drawdown": 0.05,        # 최대 낙폭 (5%)
    "circuit_breaker": True,     # 서킷 브레이커 활성화
    "position_sizing": "fixed",  # 포지션 사이징 방식
}

# =============================================================================
# 백테스트 설정
# =============================================================================

BACKTEST_CONFIG = {
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "initial_capital": 10000,
    "commission": 0.001,  # 0.1%
    "slippage": 0.0005,   # 0.05%
}

# =============================================================================
# 시장 시간 유틸리티 함수
# =============================================================================

def is_market_session(time_str=None):
    """현재 시간이 거래 세션 중인지 확인"""
    if time_str is None:
        now = datetime.now()
        time_str = now.strftime("%H:%M")
    
    hours = get_us_market_hours_kr()
    
    # 프리마켓부터 애프터마켓까지 전체 시간
    start_time = hours["pre_market_start"]
    end_time = hours["after_market_end"]
    
    # 시간 비교 (다음날로 넘어가는 경우 고려)
    if start_time <= end_time:
        return start_time <= time_str <= end_time
    else:
        # 자정을 넘어가는 경우
        return time_str >= start_time or time_str <= end_time

def get_current_market_session():
    """현재 시장 세션 반환"""
    now = datetime.now()
    time_str = now.strftime("%H:%M")
    hours = get_us_market_hours_kr()
    
    if hours["pre_market_start"] <= time_str < hours["market_open"]:
        return "PRE_MARKET"
    elif hours["market_open"] <= time_str < hours["market_close"]:
        return "REGULAR_MARKET"
    elif hours["market_close"] <= time_str < hours["after_market_end"]:
        return "AFTER_MARKET"
    else:
        return "CLOSED"