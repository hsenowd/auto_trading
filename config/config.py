"""
환경 설정 파일
미국 주식 초단타 스캘핑 자동매매 시스템의 모든 설정을 관리합니다.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# API 설정
# =============================================================================

# Alpaca Trading API (미국 주식 거래)
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
ALPACA_BASE_URL = "https://paper-api.alpaca.markets"  # 실제 거래시 https://api.alpaca.markets

# OpenAI GPT API (실시간 분석)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# =============================================================================
# 거래 설정
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
    "min_price": 5.0,            # 최소 주가
    "max_price": 500.0,          # 최대 주가
    "gap_threshold": 0.03,       # 갭 상승 임계값 (3%)
    "volume_spike": 2.0,         # 거래량 급증 배수
}

# =============================================================================
# GPT 분석 설정
# =============================================================================

GPT_CONFIG = {
    "model": "gpt-4-turbo-preview",
    "temperature": 0.3,
    "max_tokens": 1000,
    "timeout": 30,
}

# GPT 분석 프롬프트 템플릿
GPT_PROMPTS = {
    "entry_signal": """
    다음 주식 데이터를 분석하여 매수 시점인지 판단해주세요:
    
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
        "action": "BUY/HOLD/SELL"
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
        "action": "HOLD/SELL"
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

# 슬랙 알림 설정
SLACK_CONFIG = {
    "webhook_url": os.getenv("SLACK_WEBHOOK_URL", ""),
    "channel": "#trading-alerts",
    "username": "ScalpingBot",
}

# =============================================================================
# 거래 시간 설정
# =============================================================================

# 미국 주식 거래 시간 (ET)
TRADING_HOURS = {
    "market_open": "09:30",
    "market_close": "16:00",
    "pre_market_start": "04:00",
    "after_market_end": "20:00",
}

# 스캘핑 활성 시간 (변동성이 높은 시간대)
SCALPING_ACTIVE_HOURS = [
    ("09:30", "10:30"),  # 장 시작 1시간
    ("14:00", "16:00"),  # 장 마감 2시간
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