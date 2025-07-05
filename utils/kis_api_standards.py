"""
한국투자 Open API 표준화 시스템
- TR 코드 및 파라미터 표준화
- API 함수 표준화
- 응답 데이터 표준화
- 디버깅 및 로깅 시스템
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import json
import time
from datetime import datetime

from utils.simple_logger import get_logger, log_error

logger = get_logger()


class TRCode(Enum):
    """한국투자 Open API TR 코드 표준화"""
    
    # === 해외주식 현재가 ===
    OVERSEAS_STOCK_PRICE = "HHDFS00000300"          # 해외주식 현재가
    OVERSEAS_STOCK_DETAIL = "HHDFS76240000"         # 해외주식 상세정보
    
    # === 해외주식 주문 ===
    OVERSEAS_STOCK_ORDER = "HTRFB_JTTT1002U"        # 해외주식 주문
    OVERSEAS_STOCK_ORDER_CANCEL = "HTRFB_JTTT1006U" # 해외주식 주문취소
    OVERSEAS_STOCK_ORDER_MODIFY = "HTRFB_JTTT1004U" # 해외주식 주문정정
    
    # === 해외주식 잔고 ===
    OVERSEAS_STOCK_BALANCE = "HTRFB_FTRG3210U"      # 해외주식 잔고조회
    OVERSEAS_STOCK_ORDERS = "HTRFB_FTRG3220U"       # 해외주식 주문내역
    
    # === 해외주식 시세 ===
    OVERSEAS_STOCK_SEARCH = "HHDFS76410000"         # 해외주식 검색
    OVERSEAS_STOCK_CHART = "HHDFS76950000"          # 해외주식 차트
    
    # === 인증 ===
    OAUTH_TOKEN = "/oauth2/tokenP"                   # 접근토큰발급
    OAUTH_REVOKE = "/oauth2/revokeP"                # 접근토큰폐기


class MarketCode(Enum):
    """해외 시장 코드"""
    NASDAQ = "NAS"      # 나스닥
    NYSE = "NYS"        # 뉴욕거래소
    AMEX = "AMS"        # 아멕스
    
    
class OrderSide(Enum):
    """주문 구분"""
    BUY = "02"          # 매수
    SELL = "01"         # 매도
    

class OrderType(Enum):
    """주문 유형"""
    MARKET = "00"       # 시장가
    LIMIT = "01"        # 지정가
    STOP = "02"         # 스톱
    STOP_LIMIT = "03"   # 스톱리밋


@dataclass
class APIRequest:
    """API 요청 표준 형식"""
    tr_id: str
    tr_cont: str = ""
    custtype: str = "P"  # 개인: P, 법인: B
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    body: Dict[str, Any] = field(default_factory=dict)
    

@dataclass
class APIResponse:
    """API 응답 표준 형식"""
    rt_cd: str          # 성공실패구분 (0: 성공, 그 외: 실패)
    msg_cd: str         # 응답코드
    msg1: str           # 응답메세지
    output: Any = None  # 응답 데이터
    tr_id: str = ""     # TR ID
    tr_cont: str = ""   # 연속조회키
    gt_uid: str = ""    # Global UID
    

@dataclass
class StockInfo:
    """주식 정보 표준 형식"""
    symbol: str                 # 종목코드
    name: str                   # 종목명
    market: MarketCode          # 시장구분
    current_price: float        # 현재가
    daily_change: float         # 전일대비
    daily_change_rate: float    # 전일대비율
    volume: int                 # 거래량
    volume_value: float         # 거래대금
    high_price: float           # 고가
    low_price: float            # 저가
    open_price: float           # 시가
    prev_close: float           # 전일종가
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class OrderInfo:
    """주문 정보 표준 형식"""
    order_id: str               # 주문번호
    symbol: str                 # 종목코드
    side: OrderSide             # 매수/매도 구분
    order_type: OrderType       # 주문유형
    quantity: int               # 주문수량
    price: float                # 주문가격
    market: MarketCode          # 시장구분
    order_time: datetime = field(default_factory=datetime.now)
    status: str = "접수"        # 주문상태
    

@dataclass
class BalanceInfo:
    """잔고 정보 표준 형식"""
    symbol: str                 # 종목코드
    name: str                   # 종목명
    quantity: int               # 보유수량
    avg_price: float            # 평균매입가
    current_price: float        # 현재가
    eval_amount: float          # 평가금액
    profit_loss: float          # 평가손익
    profit_loss_rate: float     # 수익률
    market: MarketCode          # 시장구분


class KISAPIStandards:
    """한국투자 Open API 표준화 클래스"""
    
    def __init__(self):
        self.logger = get_logger()
        
        # API 요청 파라미터 템플릿
        self.parameter_templates = {
            # 해외주식 현재가 조회
            TRCode.OVERSEAS_STOCK_PRICE: {
                "required": ["SYMB", "EXCD"],
                "optional": [],
                "defaults": {},
                "validation": {
                    "SYMB": {"type": str, "max_length": 12},
                    "EXCD": {"type": str, "allowed": ["NAS", "NYS", "AMS"]}
                }
            },
            
            # 해외주식 주문
            TRCode.OVERSEAS_STOCK_ORDER: {
                "required": ["CANO", "ACNT_PRDT_CD", "OVRS_EXCG_CD", "PDNO", 
                           "ORD_QTY", "OVRS_ORD_UNPR", "ORD_SVR_DVSN_CD"],
                "optional": ["CTAC_TLNO", "MGCO_APTM_ODNO", "ORD_ORGNO"],
                "defaults": {
                    "ORD_SVR_DVSN_CD": "0",  # 0: 현금, 1: 융자
                    "CTAC_TLNO": "",
                    "MGCO_APTM_ODNO": "",
                    "ORD_ORGNO": ""
                },
                "validation": {
                    "CANO": {"type": str, "length": 8},
                    "ACNT_PRDT_CD": {"type": str, "length": 2},
                    "OVRS_EXCG_CD": {"type": str, "allowed": ["NASD", "NYSE", "AMEX"]},
                    "PDNO": {"type": str, "max_length": 12},
                    "ORD_QTY": {"type": int, "min": 1, "max": 999999},
                    "OVRS_ORD_UNPR": {"type": float, "min": 0}
                }
            },
            
            # 해외주식 잔고조회
            TRCode.OVERSEAS_STOCK_BALANCE: {
                "required": ["CANO", "ACNT_PRDT_CD", "OVRS_EXCG_CD", "TR_CRCY_CD"],
                "optional": ["CTX_AREA_FK200", "CTX_AREA_NK200"],
                "defaults": {
                    "CTX_AREA_FK200": "",
                    "CTX_AREA_NK200": ""
                },
                "validation": {
                    "CANO": {"type": str, "length": 8},
                    "ACNT_PRDT_CD": {"type": str, "length": 2},
                    "OVRS_EXCG_CD": {"type": str, "allowed": ["NASD", "NYSE", "AMEX"]},
                    "TR_CRCY_CD": {"type": str, "allowed": ["USD"]}
                }
            }
        }
        
        # 응답 데이터 매핑
        self.response_mappings = {
            TRCode.OVERSEAS_STOCK_PRICE: {
                "symbol": "symb",
                "current_price": "last",
                "daily_change": "diff",
                "daily_change_rate": "rate",
                "volume": "tvol",
                "high_price": "high",
                "low_price": "low",
                "open_price": "open",
                "prev_close": "base"
            }
        }
        
        logger.info("KIS API Standards initialized")
    
    def create_request(self, tr_code: TRCode, **kwargs) -> APIRequest:
        """표준화된 API 요청 생성"""
        try:
            if tr_code not in self.parameter_templates:
                raise ValueError(f"Unsupported TR code: {tr_code}")
            
            template = self.parameter_templates[tr_code]
            
            # 기본값 적용
            params = template["defaults"].copy()
            
            # 입력 파라미터 추가
            params.update(kwargs)
            
            # 필수 파라미터 검증
            self._validate_required_parameters(tr_code, params)
            
            # 파라미터 타입 및 값 검증
            self._validate_parameters(tr_code, params)
            
            # 요청 객체 생성
            request = APIRequest(
                tr_id=tr_code.value,
                params=params
            )
            
            # TR별 특별 처리
            self._apply_special_processing(tr_code, request)
            
            logger.debug(f"Created standardized request for {tr_code.name}")
            return request
            
        except Exception as e:
            log_error("API_REQUEST_CREATE_ERROR", f"Failed to create request for {tr_code}", e)
            raise
    
    def _validate_required_parameters(self, tr_code: TRCode, params: Dict[str, Any]):
        """필수 파라미터 검증"""
        template = self.parameter_templates[tr_code]
        required = template["required"]
        
        missing = [param for param in required if param not in params or params[param] is None]
        
        if missing:
            raise ValueError(f"Missing required parameters for {tr_code.name}: {missing}")
    
    def _validate_parameters(self, tr_code: TRCode, params: Dict[str, Any]):
        """파라미터 타입 및 값 검증"""
        template = self.parameter_templates[tr_code]
        validation = template.get("validation", {})
        
        for param, value in params.items():
            if param not in validation:
                continue
                
            rules = validation[param]
            
            # 타입 검증
            if "type" in rules and not isinstance(value, rules["type"]):
                try:
                    # 타입 변환 시도
                    params[param] = rules["type"](value)
                except (ValueError, TypeError):
                    raise ValueError(f"Invalid type for {param}: expected {rules['type'].__name__}, got {type(value).__name__}")
            
            # 길이 검증
            if "length" in rules:
                if len(str(value)) != rules["length"]:
                    raise ValueError(f"Invalid length for {param}: expected {rules['length']}, got {len(str(value))}")
            
            if "max_length" in rules:
                if len(str(value)) > rules["max_length"]:
                    raise ValueError(f"Value too long for {param}: max {rules['max_length']}, got {len(str(value))}")
            
            # 값 범위 검증
            if "min" in rules:
                if value < rules["min"]:
                    raise ValueError(f"Value too small for {param}: min {rules['min']}, got {value}")
            
            if "max" in rules:
                if value > rules["max"]:
                    raise ValueError(f"Value too large for {param}: max {rules['max']}, got {value}")
            
            # 허용값 검증
            if "allowed" in rules:
                if value not in rules["allowed"]:
                    raise ValueError(f"Invalid value for {param}: allowed {rules['allowed']}, got {value}")
    
    def _apply_special_processing(self, tr_code: TRCode, request: APIRequest):
        """TR별 특별 처리"""
        
        # 해외주식 현재가 조회
        if tr_code == TRCode.OVERSEAS_STOCK_PRICE:
            # 헤더 설정
            request.headers = {
                "content-type": "application/json; charset=utf-8",
                "tr_id": tr_code.value,
                "custtype": "P"
            }
        
        # 해외주식 주문
        elif tr_code == TRCode.OVERSEAS_STOCK_ORDER:
            request.headers = {
                "content-type": "application/json; charset=utf-8",
                "tr_id": tr_code.value,
                "custtype": "P"
            }
            # body로 파라미터 이동
            request.body = request.params.copy()
            request.params = {}
        
        # 해외주식 잔고조회
        elif tr_code == TRCode.OVERSEAS_STOCK_BALANCE:
            request.headers = {
                "content-type": "application/json; charset=utf-8",
                "tr_id": tr_code.value,
                "custtype": "P"
            }
    
    def parse_response(self, tr_code: TRCode, raw_response: Dict[str, Any]) -> APIResponse:
        """표준화된 응답 파싱"""
        try:
            # 기본 응답 구조 파싱
            response = APIResponse(
                rt_cd=raw_response.get("rt_cd", ""),
                msg_cd=raw_response.get("msg_cd", ""),
                msg1=raw_response.get("msg1", ""),
                tr_id=tr_code.value
            )
            
            # 성공 여부 확인
            if response.rt_cd != "0":
                logger.warning(f"API error: {response.msg_cd} - {response.msg1}")
            
            # TR별 특별 파싱
            if tr_code == TRCode.OVERSEAS_STOCK_PRICE:
                response.output = self._parse_stock_price_response(raw_response)
            elif tr_code == TRCode.OVERSEAS_STOCK_ORDER:
                response.output = self._parse_order_response(raw_response)
            elif tr_code == TRCode.OVERSEAS_STOCK_BALANCE:
                response.output = self._parse_balance_response(raw_response)
            else:
                response.output = raw_response.get("output", {})
            
            logger.debug(f"Parsed response for {tr_code.name}")
            return response
            
        except Exception as e:
            log_error("API_RESPONSE_PARSE_ERROR", f"Failed to parse response for {tr_code}", e)
            raise
    
    def _parse_stock_price_response(self, raw_response: Dict[str, Any]) -> Optional[StockInfo]:
        """주식 현재가 응답 파싱"""
        try:
            output = raw_response.get("output", {})
            if not output:
                return None
            
            return StockInfo(
                symbol=output.get("symb", ""),
                name=output.get("name", ""),
                market=self._get_market_from_code(output.get("excd", "")),
                current_price=float(output.get("last", "0") or "0"),
                daily_change=float(output.get("diff", "0") or "0"),
                daily_change_rate=float(output.get("rate", "0") or "0"),
                volume=int(output.get("tvol", "0") or "0"),
                volume_value=float(output.get("tamt", "0") or "0"),
                high_price=float(output.get("high", "0") or "0"),
                low_price=float(output.get("low", "0") or "0"),
                open_price=float(output.get("open", "0") or "0"),
                prev_close=float(output.get("base", "0") or "0")
            )
            
        except Exception as e:
            log_error("STOCK_PRICE_PARSE_ERROR", "Failed to parse stock price response", e)
            return None
    
    def _parse_order_response(self, raw_response: Dict[str, Any]) -> Optional[OrderInfo]:
        """주문 응답 파싱"""
        try:
            output = raw_response.get("output", {})
            if not output:
                return None
            
            return OrderInfo(
                order_id=output.get("ODNO", ""),
                symbol=output.get("PDNO", ""),
                side=OrderSide.BUY if output.get("SLL_BUY_DVSN_CD") == "02" else OrderSide.SELL,
                order_type=OrderType.LIMIT,  # 기본값
                quantity=int(output.get("ORD_QTY", "0") or "0"),
                price=float(output.get("OVRS_ORD_UNPR", "0") or "0"),
                market=self._get_market_from_exchange_code(output.get("OVRS_EXCG_CD", ""))
            )
            
        except Exception as e:
            log_error("ORDER_PARSE_ERROR", "Failed to parse order response", e)
            return None
    
    def _parse_balance_response(self, raw_response: Dict[str, Any]) -> List[BalanceInfo]:
        """잔고 응답 파싱"""
        try:
            output = raw_response.get("output", [])
            if not isinstance(output, list):
                return []
            
            balances = []
            for item in output:
                balance = BalanceInfo(
                    symbol=item.get("ovrs_pdno", ""),
                    name=item.get("ovrs_item_name", ""),
                    quantity=int(item.get("ovrs_cblc_qty", "0") or "0"),
                    avg_price=float(item.get("pchs_avg_pric", "0") or "0"),
                    current_price=float(item.get("ovrs_stck_pric", "0") or "0"),
                    eval_amount=float(item.get("ovrs_stck_evlu_amt", "0") or "0"),
                    profit_loss=float(item.get("evlu_pfls_amt", "0") or "0"),
                    profit_loss_rate=float(item.get("evlu_pfls_rt", "0") or "0"),
                    market=self._get_market_from_exchange_code(item.get("ovrs_excg_cd", ""))
                )
                balances.append(balance)
            
            return balances
            
        except Exception as e:
            log_error("BALANCE_PARSE_ERROR", "Failed to parse balance response", e)
            return []
    
    def _get_market_from_code(self, code: str) -> MarketCode:
        """거래소 코드를 MarketCode로 변환"""
        mapping = {
            "NAS": MarketCode.NASDAQ,
            "NYS": MarketCode.NYSE,
            "AMS": MarketCode.AMEX
        }
        return mapping.get(code, MarketCode.NASDAQ)
    
    def _get_market_from_exchange_code(self, code: str) -> MarketCode:
        """거래소 코드를 MarketCode로 변환 (주문/잔고용)"""
        mapping = {
            "NASD": MarketCode.NASDAQ,
            "NYSE": MarketCode.NYSE,
            "AMEX": MarketCode.AMEX
        }
        return mapping.get(code, MarketCode.NASDAQ)
    
    def validate_symbol(self, symbol: str, market: MarketCode) -> bool:
        """종목코드 유효성 검증"""
        try:
            if not symbol or len(symbol) > 12:
                return False
            
            # 기본 형식 검증
            if not symbol.replace(".", "").replace("-", "").isalnum():
                return False
            
            return True
            
        except Exception:
            return False
    
    def get_parameter_info(self, tr_code: TRCode) -> Dict[str, Any]:
        """TR 코드별 파라미터 정보 반환"""
        if tr_code in self.parameter_templates:
            return self.parameter_templates[tr_code].copy()
        return {}
    
    def get_all_tr_codes(self) -> List[str]:
        """모든 지원되는 TR 코드 반환"""
        return [tr.value for tr in TRCode]


# 전역 표준화 인스턴스
kis_standards = KISAPIStandards()


def get_kis_standards() -> KISAPIStandards:
    """KIS API 표준화 인스턴스 반환"""
    return kis_standards


# 편의 함수들
def create_stock_price_request(symbol: str, market: str = "NAS") -> APIRequest:
    """주식 현재가 조회 요청 생성"""
    return kis_standards.create_request(
        TRCode.OVERSEAS_STOCK_PRICE,
        SYMB=symbol,
        EXCD=market
    )


def create_order_request(account_no: str, symbol: str, quantity: int, 
                        price: float, side: str, market: str = "NASD") -> APIRequest:
    """주식 주문 요청 생성"""
    return kis_standards.create_request(
        TRCode.OVERSEAS_STOCK_ORDER,
        CANO=account_no,
        ACNT_PRDT_CD="01",
        OVRS_EXCG_CD=market,
        PDNO=symbol,
        ORD_QTY=quantity,
        OVRS_ORD_UNPR=price,
        SLL_BUY_DVSN_CD=side
    )


def create_balance_request(account_no: str, market: str = "NASD") -> APIRequest:
    """잔고 조회 요청 생성"""
    return kis_standards.create_request(
        TRCode.OVERSEAS_STOCK_BALANCE,
        CANO=account_no,
        ACNT_PRDT_CD="01",
        OVRS_EXCG_CD=market,
        TR_CRCY_CD="USD"
    )


# 실행 예시
if __name__ == "__main__":
    print("=== 한국투자 Open API 표준화 시스템 테스트 ===")
    
    standards = KISAPIStandards()
    
    # 주식 현재가 요청 생성
    request = create_stock_price_request("AAPL", "NAS")
    print(f"현재가 요청: {request.tr_id}")
    print(f"파라미터: {request.params}")
    
    # 파라미터 정보 조회
    info = standards.get_parameter_info(TRCode.OVERSEAS_STOCK_PRICE)
    print(f"필수 파라미터: {info.get('required', [])}")
    
    print("\n한국투자 Open API 표준화 시스템 테스트 완료!")