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

from config.config import KIS_CONFIG, OPENAI_API_KEY, GPT_CONFIG
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


class KISAPIClient:
    """한국투자 Open API 클라이언트"""
    
    def __init__(self):
        self.config = KIS_CONFIG
        self.base_url = self.config["vps_url"] if self.config["is_paper_trading"] else self.config["prod_url"]
        self.app_key = self.config["paper_app_key"] if self.config["is_paper_trading"] else self.config["app_key"]
        self.app_secret = self.config["paper_app_secret"] if self.config["is_paper_trading"] else self.config["app_secret"]
        self.account_no = self.config["account_no"]
        self.product_code = self.config["product_code"]
        
        # 토큰 관리
        self.token = None
        self.token_expired = None
        self.last_auth_time = None
        
        # 기본 헤더
        self.base_headers = {
            "Content-Type": "application/json",
            "Accept": "text/plain",
            "charset": "UTF-8",
            "User-Agent": self.config["user_agent"]
        }
        
        logger.info("KIS API client initialized")
    
    def save_token(self, token: str, expired: str):
        """토큰을 파일에 저장"""
        try:
            valid_date = datetime.strptime(expired, '%Y-%m-%d %H:%M:%S')
            token_data = {
                'token': token,
                'valid-date': valid_date
            }
            
            os.makedirs(os.path.dirname(self.config["token_file_path"]), exist_ok=True)
            with open(self.config["token_file_path"], 'w', encoding='utf-8') as f:
                yaml.dump(token_data, f, default_flow_style=False, allow_unicode=True)
                
        except Exception as e:
            logger.error(f"Failed to save token: {e}")
    
    def read_token(self) -> Optional[str]:
        """저장된 토큰 읽기"""
        try:
            if not os.path.exists(self.config["token_file_path"]):
                return None
            
            with open(self.config["token_file_path"], encoding='UTF-8') as f:
                token_data = yaml.load(f, Loader=yaml.FullLoader)
            
            if not token_data:
                return None
                
            # 토큰 만료 시간 확인
            exp_dt = datetime.strftime(token_data['valid-date'], '%Y-%m-%d %H:%M:%S')
            now_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if exp_dt > now_dt:
                return token_data['token']
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to read token: {e}")
            return None
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def authenticate(self) -> bool:
        """토큰 발급 및 인증"""
        try:
            # 기존 토큰 확인
            saved_token = self.read_token()
            if saved_token:
                self.token = saved_token
                self.setup_headers()
                logger.info("Using saved token")
                return True
            
            # 새 토큰 발급
            url = f"{self.base_url}/oauth2/tokenP"
            data = {
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "appsecret": self.app_secret
            }
            
            response = requests.post(url, data=json.dumps(data), headers=self.base_headers)
            
            if response.status_code == 200:
                result = response.json()
                self.token = result['access_token']
                self.token_expired = result['access_token_token_expired']
                
                # 토큰 저장
                self.save_token(self.token, self.token_expired)
                
                # 헤더 설정
                self.setup_headers()
                
                self.last_auth_time = datetime.now()
                logger.info("Token authentication successful")
                return True
            else:
                logger.error(f"Token authentication failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    def setup_headers(self):
        """인증 헤더 설정"""
        self.base_headers["authorization"] = f"Bearer {self.token}"
        self.base_headers["appkey"] = self.app_key
        self.base_headers["appsecret"] = self.app_secret
    
    def get_hashkey(self, params: Dict) -> str:
        """해시키 생성"""
        try:
            url = f"{self.base_url}/uapi/hashkey"
            headers = copy.deepcopy(self.base_headers)
            
            response = requests.post(url, data=json.dumps(params), headers=headers)
            
            if response.status_code == 200:
                return response.json()['HASH']
            else:
                logger.error(f"Failed to get hashkey: {response.status_code}")
                return ""
                
        except Exception as e:
            logger.error(f"Hashkey generation error: {e}")
            return ""
    
    def api_call(self, endpoint: str, tr_id: str, params: Optional[Dict] = None, method: str = "GET") -> Dict:
        """API 호출 공통 메서드"""
        try:
            # 인증 확인
            if not self.token:
                if not self.authenticate():
                    raise Exception("Authentication failed")
            
            url = f"{self.base_url}{endpoint}"
            headers = copy.deepcopy(self.base_headers)
            
            # TR ID 설정 (모의투자일 경우 변환)
            if tr_id[0] in ('T', 'J', 'C') and self.config["is_paper_trading"]:
                tr_id = 'V' + tr_id[1:]
            
            headers["tr_id"] = tr_id
            headers["custtype"] = "P"
            
            # API 호출
            if method == "POST":
                request_data = json.dumps(params) if params else "{}"
                response = requests.post(url, headers=headers, data=request_data)
            else:
                response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"API call failed: {response.status_code}, {response.text}")
                return {}
                
        except Exception as e:
            logger.error(f"API call error: {e}")
            return {}
    
    # =============================================================================
    # 해외주식 관련 API
    # =============================================================================
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def get_overseas_stock_price(self, symbol: str, exchange: str = "NASD") -> Dict:
        """해외주식 현재가 조회"""
        endpoint = "/uapi/overseas-price/v1/quotations/price"
        tr_id = "HHDFS00000300"
        
        params = {
            "AUTH": "",
            "EXCD": exchange,  # NASD: 나스닥, NYSE: 뉴욕증권거래소
            "SYMB": symbol
        }
        
        return self.api_call(endpoint, tr_id, params)
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def get_overseas_stock_balance(self) -> Dict:
        """해외주식 잔고 조회"""
        endpoint = "/uapi/overseas-stock/v1/trading/inquire-balance"
        tr_id = "TTTS3012R"
        
        params = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": self.product_code,
            "OVRS_EXCG_CD": "NASD",  # 나스닥
            "TR_CRCY_CD": "USD",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": ""
        }
        
        return self.api_call(endpoint, tr_id, params)
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def place_overseas_order(self, symbol: str, qty: int, side: str, price: Optional[float] = None, 
                            exchange: str = "NASD", order_type: str = "00") -> Dict:
        """해외주식 주문"""
        endpoint = "/uapi/overseas-stock/v1/trading/order"
        tr_id = "TTTT1002U"  # 해외주식 주문
        
        params = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": self.product_code,
            "OVRS_EXCG_CD": exchange,
            "PDNO": symbol,
            "ORD_QTY": str(qty),
            "OVRS_ORD_UNPR": str(price) if price is not None else "0",
            "ORD_SVR_DVSN_CD": "0",
            "SLL_TYPE": "00" if side == "buy" else "01",
            "ORD_DVSN": order_type,  # 00: 지정가, 01: 시장가
            "CTAC_TLNO": "",
            "MGCO_APTM_ODNO": "",
            "ORD_SVR_DVSN_CD": "0"
        }
        
        # 해시키 생성
        hashkey = self.get_hashkey(params)
        headers = copy.deepcopy(self.base_headers)
        headers["hashkey"] = hashkey
        
        return self.api_call(endpoint, tr_id, params, method="POST")
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def cancel_overseas_order(self, order_id: str, symbol: str, qty: int, exchange: str = "NASD") -> Dict:
        """해외주식 주문 취소"""
        endpoint = "/uapi/overseas-stock/v1/trading/order-rvsecncl"
        tr_id = "TTTT1004U"
        
        params = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": self.product_code,
            "OVRS_EXCG_CD": exchange,
            "PDNO": symbol,
            "ORGN_ODNO": order_id,
            "ORD_QTY": str(qty),
            "RVSE_CNCL_DVSN_CD": "02",  # 취소
            "ORD_UNPR": "0",
            "CTAC_TLNO": "",
            "MGCO_APTM_ODNO": ""
        }
        
        return self.api_call(endpoint, tr_id, params, method="POST")
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def get_overseas_orders(self) -> Dict:
        """해외주식 미체결 주문 조회"""
        endpoint = "/uapi/overseas-stock/v1/trading/inquire-nccs"
        tr_id = "TTTS3018R"
        
        params = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": self.product_code,
            "OVRS_EXCG_CD": "NASD",
            "SORT_SQN": "DS",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": ""
        }
        
        return self.api_call(endpoint, tr_id, params)
    
    def is_market_open(self) -> bool:
        """시장 오픈 여부 확인 (간단한 시간 체크)"""
        try:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            
            # 한국 시간 기준 미국 시장 시간 (대략적)
            if "23:30" <= current_time <= "23:59" or "00:00" <= current_time <= "06:00":
                return True
            return False
            
        except Exception as e:
            logger.error(f"Market status check failed: {e}")
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