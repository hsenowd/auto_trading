"""
한국투자 Open API 클라이언트 유틸리티 모듈
한국투자 Open API와 OpenAI API 연동을 관리합니다.
"""

import time
import json
import copy
import requests
import yaml
import hashlib
import hmac
from typing import Dict, List, Optional, Any
from functools import wraps
from datetime import datetime, timedelta
from collections import namedtuple
from openai import OpenAI
import os
import threading

from config.config import KIS_CONFIG, OPENAI_API_KEY, GPT_CONFIG
from utils.simple_logger import get_logger, log_error
from utils.kis_api_standards import (
    get_kis_standards, 
    TRCode, 
    MarketCode, 
    OrderSide, 
    APIRequest, 
    APIResponse,
    create_stock_price_request,
    create_order_request, 
    create_balance_request
)
from utils.api_debugger import get_api_debugger, LogLevel

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


class KISAPIClient:
    """한국투자 Open API 클라이언트 (표준화 적용)"""
    
    def __init__(self):
        self.config = KIS_CONFIG
        self.standards = get_kis_standards()
        self.base_url = self.config["vps_url"] if self.config["is_paper_trading"] else self.config["prod_url"]
        self.token = None
        self.token_expires = None
        self.lock = threading.Lock()
        
        logger.info(f"KIS API Client initialized (Mode: {'Paper' if self.config['is_paper_trading'] else 'Live'})")
    
    def _is_token_valid(self) -> bool:
        """토큰 유효성 확인"""
        if not self.token or not self.token_expires:
            return False
        
        # 토큰 만료 10분 전에 재발급
        now = datetime.now()
        expiry_buffer = self.token_expires - timedelta(minutes=10)
        
        return now < expiry_buffer
    
    def authenticate(self) -> bool:
        """토큰 발급/갱신 (표준화 적용)"""
        try:
            with self.lock:
                # 기존 토큰 유효성 확인
                if self._is_token_valid():
                    return True
                
                # 표준화된 인증 요청
                auth_data = {
                    "grant_type": "client_credentials",
                    "appkey": self.config["app_key"],
                    "appsecret": self.config["app_secret"]
                }
                
                url = f"{self.base_url}{TRCode.OAUTH_TOKEN.value}"
                
                response = requests.post(
                    url,
                    json=auth_data,
                    headers={"content-type": "application/json"},
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.token = data.get("access_token")
                    
                    # 토큰 만료 시간 설정 (24시간)
                    self.token_expires = datetime.now() + timedelta(hours=24)
                    
                    logger.info("🔑 KIS API authentication successful")
                    return True
                else:
                    log_error("AUTH_ERROR", f"Authentication failed: {response.status_code}", 
                             Exception(response.text))
                    return False
                    
        except Exception as e:
            log_error("AUTH_EXCEPTION", "Authentication exception occurred", e)
            return False
    
    def get_overseas_stock_price(self, symbol: str, market: str = "NAS") -> Optional[Dict]:
        """해외주식 현재가 조회 (표준화 적용)"""
        try:
            if not self.authenticate():
                return None
            
            # 표준화된 요청 생성
            request = create_stock_price_request(symbol, market)
            
            # API 호출
            raw_response = self._make_api_call(request)
            if not raw_response:
                return None
            
            # 표준화된 응답 파싱
            response = self.standards.parse_response(TRCode.OVERSEAS_STOCK_PRICE, raw_response)
            
            if response.rt_cd == "0" and response.output:
                stock_info = response.output
                return {
                    'symbol': stock_info.symbol,
                    'name': stock_info.name,
                    'current_price': stock_info.current_price,
                    'daily_change': stock_info.daily_change,
                    'daily_change_rate': stock_info.daily_change_rate,
                    'volume': stock_info.volume,
                    'volume_intensity': stock_info.volume / 1000000 if stock_info.volume > 0 else 0,
                    'high_price': stock_info.high_price,
                    'low_price': stock_info.low_price,
                    'open_price': stock_info.open_price,
                    'prev_close': stock_info.prev_close,
                    'market': stock_info.market.value
                }
            else:
                logger.warning(f"Stock price query failed: {response.msg1}")
                return None
                
        except Exception as e:
            log_error("STOCK_PRICE_ERROR", f"Failed to get stock price for {symbol}", e)
            return None
    
    def place_overseas_order(self, symbol: str, quantity: int, price: float, 
                           side: str = "buy", order_type: str = "limit", 
                           market: str = "NASD") -> Optional[Dict]:
        """해외주식 주문 (표준화 적용)"""
        try:
            if not self.authenticate():
                return None
            
            # 주문 구분 코드 변환
            side_code = OrderSide.BUY.value if side.lower() == "buy" else OrderSide.SELL.value
            
            # 표준화된 주문 요청 생성
            request = create_order_request(
                account_no=self.config["account_no"],
                symbol=symbol,
                quantity=quantity,
                price=price,
                side=side_code,
                market=market
            )
            
            # API 호출
            raw_response = self._make_api_call(request)
            if not raw_response:
                return None
            
            # 표준화된 응답 파싱
            response = self.standards.parse_response(TRCode.OVERSEAS_STOCK_ORDER, raw_response)
            
            if response.rt_cd == "0" and response.output:
                order_info = response.output
                return {
                    'order_id': order_info.order_id,
                    'symbol': order_info.symbol,
                    'side': side,
                    'quantity': order_info.quantity,
                    'price': order_info.price,
                    'status': 'submitted',
                    'timestamp': order_info.order_time.isoformat()
                }
            else:
                logger.error(f"Order failed: {response.msg1}")
                return None
                
        except Exception as e:
            log_error("ORDER_ERROR", f"Failed to place order for {symbol}", e)
            return None
    
    def get_overseas_stock_balance(self, market: str = "NASD") -> List[Dict]:
        """해외주식 잔고조회 (표준화 적용)"""
        try:
            if not self.authenticate():
                return []
            
            # 표준화된 잔고 요청 생성
            request = create_balance_request(
                account_no=self.config["account_no"],
                market=market
            )
            
            # API 호출
            raw_response = self._make_api_call(request)
            if not raw_response:
                return []
            
            # 표준화된 응답 파싱
            response = self.standards.parse_response(TRCode.OVERSEAS_STOCK_BALANCE, raw_response)
            
            if response.rt_cd == "0" and response.output:
                balances = []
                for balance_info in response.output:
                    if balance_info.quantity > 0:  # 보유 수량이 있는 것만
                        balances.append({
                            'symbol': balance_info.symbol,
                            'name': balance_info.name,
                            'quantity': balance_info.quantity,
                            'avg_price': balance_info.avg_price,
                            'current_price': balance_info.current_price,
                            'market_value': balance_info.eval_amount,
                            'unrealized_pnl': balance_info.profit_loss,
                            'unrealized_pnl_pct': balance_info.profit_loss_rate,
                            'market': balance_info.market.value
                        })
                return balances
            else:
                logger.warning(f"Balance query failed: {response.msg1}")
                return []
                
        except Exception as e:
            log_error("BALANCE_ERROR", "Failed to get stock balance", e)
            return []
    
    def _make_api_call(self, request: APIRequest) -> Optional[Dict]:
        """표준화된 API 호출 (디버깅 통합)"""
        debugger = get_api_debugger()
        call_id = ""
        start_time = time.time()
        
        try:
            # 헤더에 인증 토큰 추가
            headers = request.headers.copy()
            headers["authorization"] = f"Bearer {self.token}"
            headers["appkey"] = self.config["app_key"]
            headers["appsecret"] = self.config["app_secret"]
            
            # URL 구성
            url = f"{self.base_url}/uapi/overseas-price/v1/quotations/price"
            
            if request.tr_id == TRCode.OVERSEAS_STOCK_ORDER.value:
                url = f"{self.base_url}/uapi/overseas-stock/v1/trading/order"
            elif request.tr_id == TRCode.OVERSEAS_STOCK_BALANCE.value:
                url = f"{self.base_url}/uapi/overseas-stock/v1/trading/inquire-balance"
            
            # 디버깅 시작
            call_id = debugger.start_api_call(request.tr_id, request, url)
            
            # HTTP 요청 실행
            if request.body:
                # POST 요청 (주문 등)
                response = requests.post(
                    url,
                    json=request.body,
                    headers=headers,
                    params=request.params,
                    timeout=30
                )
            else:
                # GET 요청 (시세 조회 등)
                response = requests.get(
                    url,
                    headers=headers,
                    params=request.params,
                    timeout=30
                )
            
            response_time_ms = (time.time() - start_time) * 1000
            
            # 디버깅 종료
            debugger.end_api_call(
                call_id=call_id,
                response_status=response.status_code,
                response_headers=dict(response.headers),
                response_body=response.json() if response.status_code == 200 else {},
                response_time_ms=response_time_ms
            )
            
            # 디버깅 로그
            logger.debug(f"API Call: {request.tr_id} -> Status: {response.status_code} ({response_time_ms:.1f}ms)")
            
            if response.status_code == 200:
                return response.json()
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                log_error("API_CALL_ERROR", f"API call failed: {response.status_code}", 
                         Exception(error_msg))
                return None
                
        except requests.exceptions.Timeout as e:
            response_time_ms = (time.time() - start_time) * 1000
            error_msg = f"Request timeout after 30 seconds"
            
            if call_id:
                debugger.end_api_call(
                    call_id=call_id,
                    response_status=408,
                    response_headers={},
                    response_body={},
                    response_time_ms=response_time_ms,
                    error_message=error_msg
                )
            
            log_error("API_TIMEOUT_ERROR", f"API timeout: {request.tr_id}", e)
            return None
            
        except requests.exceptions.ConnectionError as e:
            response_time_ms = (time.time() - start_time) * 1000
            error_msg = f"Connection error: {str(e)}"
            
            if call_id:
                debugger.end_api_call(
                    call_id=call_id,
                    response_status=0,
                    response_headers={},
                    response_body={},
                    response_time_ms=response_time_ms,
                    error_message=error_msg
                )
            
            log_error("API_CONNECTION_ERROR", f"Connection error: {request.tr_id}", e)
            return None
            
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            error_msg = f"Unexpected error: {str(e)}"
            
            if call_id:
                debugger.end_api_call(
                    call_id=call_id,
                    response_status=500,
                    response_headers={},
                    response_body={},
                    response_time_ms=response_time_ms,
                    error_message=error_msg
                )
            
            log_error("API_CALL_EXCEPTION", f"API call exception: {request.tr_id}", e)
            return None
    
    def cancel_overseas_order(self, order_id: str, symbol: str, quantity: int, 
                            market: str = "NASD") -> bool:
        """해외주식 주문취소 (표준화 적용)"""
        try:
            if not self.authenticate():
                return False
            
            # 표준화된 취소 요청 생성
            request = self.standards.create_request(
                TRCode.OVERSEAS_STOCK_ORDER_CANCEL,
                CANO=self.config["account_no"],
                ACNT_PRDT_CD="01",
                OVRS_EXCG_CD=market,
                PDNO=symbol,
                ORGN_ODNO=order_id,
                ORD_QTY=quantity
            )
            
            # API 호출
            raw_response = self._make_api_call(request)
            if not raw_response:
                return False
            
            # 응답 파싱
            response = self.standards.parse_response(TRCode.OVERSEAS_STOCK_ORDER_CANCEL, raw_response)
            
            if response.rt_cd == "0":
                logger.info(f"Order cancelled successfully: {order_id}")
                return True
            else:
                logger.error(f"Order cancellation failed: {response.msg1}")
                return False
                
        except Exception as e:
            log_error("CANCEL_ORDER_ERROR", f"Failed to cancel order {order_id}", e)
            return False
    
    def get_parameter_template(self, tr_code: str) -> Dict:
        """TR 코드별 파라미터 템플릿 조회"""
        try:
            tr_enum = TRCode(tr_code)
            return self.standards.get_parameter_info(tr_enum)
        except ValueError:
            logger.warning(f"Unknown TR code: {tr_code}")
            return {}
    
    def validate_request_parameters(self, tr_code: str, **params) -> bool:
        """요청 파라미터 유효성 검증"""
        try:
            tr_enum = TRCode(tr_code)
            # 실제 요청 생성을 통해 검증
            self.standards.create_request(tr_enum, **params)
            return True
        except Exception as e:
            logger.warning(f"Parameter validation failed: {e}")
            return False


class OpenAIClient:
    """OpenAI GPT API 클라이언트 (최신 API 사용)"""
    
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("OpenAI API client initialized")
    
    @retry_on_failure(max_retries=3, delay=2.0)
    def analyze_signal(self, prompt: str) -> Dict:
        """GPT를 사용한 시그널 분석"""
        try:
            response = self.client.chat.completions.create(
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
                    "action": "HOLD",
                    "confidence": "MEDIUM"
                }
                
        except Exception as e:
            log_error("GPT_ANALYSIS_FAILED", "Failed to analyze signal with GPT", e)
            raise e
    
    @retry_on_failure(max_retries=3, delay=2.0)
    def analyze_entry_signal(self, symbol: str, market_data: Dict) -> Dict:
        """매수 시그널 분석"""
        prompt = f"""
        다음 미국 주식 데이터를 분석하여 매수 시점인지 판단해주세요:
        
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
            "action": "BUY/HOLD/SELL",
            "confidence": "HIGH/MEDIUM/LOW"
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
            "action": "HOLD/SELL",
            "confidence": "HIGH/MEDIUM/LOW"
        }}
        """
        
        return self.analyze_signal(prompt)


# 전역 클라이언트 인스턴스
kis_client = KISAPIClient()
openai_client = OpenAIClient()


def get_kis_client() -> KISAPIClient:
    """KIS API 클라이언트 인스턴스 반환"""
    return kis_client


def get_openai_client() -> OpenAIClient:
    """OpenAI 클라이언트 인스턴스 반환"""
    return openai_client


# 호환성을 위한 별명
get_alpaca_client = get_kis_client