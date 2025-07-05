"""
API 클라이언트 유틸리티 모듈
Alpaca API와 OpenAI API 연동을 관리합니다.
"""

import time
import json
import openai
import alpaca_trade_api as tradeapi
from typing import Dict, List, Optional, Any
from functools import wraps
from datetime import datetime, timedelta

from config.config import (
    ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL,
    OPENAI_API_KEY, GPT_CONFIG
)
from utils.logger import get_logger, log_error

logger = get_logger()


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """API 호출 실패 시 재시도 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        log_error("API_RETRY_FAILED", f"Function {func.__name__} failed after {max_retries} attempts", e)
                        raise e
                    logger.warning(f"API call failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
                    time.sleep(delay * (2 ** attempt))  # 지수 백오프
            return None
        return wrapper
    return decorator


class AlpacaClient:
    """Alpaca Trading API 클라이언트"""
    
    def __init__(self):
        self.api = tradeapi.REST(
            ALPACA_API_KEY,
            ALPACA_SECRET_KEY,
            ALPACA_BASE_URL,
            api_version='v2'
        )
        self.data_api = tradeapi.REST(
            ALPACA_API_KEY,
            ALPACA_SECRET_KEY,
            ALPACA_BASE_URL,
            api_version='v2'
        )
        logger.info("Alpaca API client initialized")
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def get_account(self) -> Dict:
        """계좌 정보 조회"""
        return self.api.get_account()._raw
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def get_positions(self) -> List[Dict]:
        """포지션 정보 조회"""
        positions = self.api.list_positions()
        return [pos._raw for pos in positions]
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def get_orders(self, status: str = "open") -> List[Dict]:
        """주문 내역 조회"""
        orders = self.api.list_orders(status=status)
        return [order._raw for order in orders]
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def place_order(self, symbol: str, qty: int, side: str, 
                   type: str = "market", time_in_force: str = "gtc",
                   limit_price: Optional[float] = None) -> Dict:
        """주문 실행"""
        order = self.api.submit_order(
            symbol=symbol,
            qty=qty,
            side=side,
            type=type,
            time_in_force=time_in_force,
            limit_price=limit_price
        )
        return order._raw
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def cancel_order(self, order_id: str) -> bool:
        """주문 취소"""
        try:
            self.api.cancel_order(order_id)
            return True
        except Exception as e:
            log_error("ORDER_CANCEL_FAILED", f"Failed to cancel order {order_id}", e)
            return False
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def get_latest_bars(self, symbols: List[str], timeframe: str = "1Min") -> Dict:
        """최신 바 데이터 조회"""
        bars = self.data_api.get_bars(
            symbols,
            timeframe,
            start=datetime.now() - timedelta(days=1),
            end=datetime.now(),
            asof=None,
            feed=None,
            page_token=None,
            limit=100
        )
        return bars.df.to_dict()
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def get_latest_quotes(self, symbols: List[str]) -> Dict:
        """최신 호가 데이터 조회"""
        quotes = self.data_api.get_latest_quotes(symbols)
        return {symbol: quote._raw for symbol, quote in quotes.items()}
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def get_latest_trades(self, symbols: List[str]) -> Dict:
        """최신 체결 데이터 조회"""
        trades = self.data_api.get_latest_trades(symbols)
        return {symbol: trade._raw for symbol, trade in trades.items()}
    
    def is_market_open(self) -> bool:
        """시장 오픈 여부 확인"""
        try:
            clock = self.api.get_clock()
            return clock.is_open
        except Exception as e:
            log_error("MARKET_STATUS_CHECK_FAILED", "Failed to check market status", e)
            return False


class OpenAIClient:
    """OpenAI GPT API 클라이언트"""
    
    def __init__(self):
        openai.api_key = OPENAI_API_KEY
        logger.info("OpenAI API client initialized")
    
    @retry_on_failure(max_retries=3, delay=2.0)
    def analyze_signal(self, prompt: str) -> Dict:
        """GPT를 사용한 시그널 분석"""
        try:
            response = openai.ChatCompletion.create(
                model=GPT_CONFIG["model"],
                messages=[
                    {"role": "system", "content": "당신은 전문적인 주식 분석가입니다. 데이터를 기반으로 객관적인 분석을 제공하세요."},
                    {"role": "user", "content": prompt}
                ],
                temperature=GPT_CONFIG["temperature"],
                max_tokens=GPT_CONFIG["max_tokens"],
                timeout=GPT_CONFIG["timeout"]
            )
            
            content = response.choices[0].message.content
            
            # JSON 형식으로 파싱 시도
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 기본 형태로 반환
                return {
                    "signal_score": 5,
                    "reasoning": content,
                    "action": "HOLD"
                }
                
        except Exception as e:
            log_error("GPT_ANALYSIS_FAILED", "Failed to analyze signal with GPT", e)
            raise e
    
    @retry_on_failure(max_retries=3, delay=2.0)
    def analyze_entry_signal(self, symbol: str, market_data: Dict) -> Dict:
        """매수 시그널 분석"""
        prompt = f"""
        다음 주식 데이터를 분석하여 매수 시점인지 판단해주세요:
        
        종목: {symbol}
        현재가: ${market_data.get('current_price', 0):.2f}
        체결강도: {market_data.get('volume_intensity', 0):.2f}
        호가 스프레드: {market_data.get('bid_ask_spread', 0):.4f}
        1분봉 거래량: {market_data.get('volume_1m', 0)}
        5분봉 거래량: {market_data.get('volume_5m', 0)}
        전일 대비 등락률: {market_data.get('daily_change', 0):.2f}%
        
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
        """
        
        return self.analyze_signal(prompt)
    
    @retry_on_failure(max_retries=3, delay=2.0)
    def analyze_exit_signal(self, symbol: str, position_data: Dict) -> Dict:
        """매도 시그널 분석"""
        prompt = f"""
        다음 포지션의 청산 시점을 판단해주세요:
        
        종목: {symbol}
        매수가: ${position_data.get('entry_price', 0):.2f}
        현재가: ${position_data.get('current_price', 0):.2f}
        수익률: {position_data.get('profit_loss', 0):.2f}%
        보유 시간: {position_data.get('holding_time', 0)}초
        현재 거래량: {position_data.get('current_volume', 0)}
        
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
        
        return self.analyze_signal(prompt)


# 전역 클라이언트 인스턴스
alpaca_client = AlpacaClient()
openai_client = OpenAIClient()


def get_alpaca_client() -> AlpacaClient:
    """Alpaca 클라이언트 인스턴스 반환"""
    return alpaca_client


def get_openai_client() -> OpenAIClient:
    """OpenAI 클라이언트 인스턴스 반환"""
    return openai_client