"""
한국투자 Open API 표준화 시스템 테스트
- TR 코드 및 파라미터 검증 테스트
- API 요청/응답 표준화 테스트
- 디버깅 시스템 테스트
- 성능 모니터링 테스트
"""

import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import unittest

# 테스트 대상 모듈 import
from utils.kis_api_standards import (
    KISAPIStandards,
    TRCode,
    MarketCode,
    OrderSide,
    OrderType,
    APIRequest,
    APIResponse,
    StockInfo,
    OrderInfo,
    BalanceInfo,
    create_stock_price_request,
    create_order_request,
    create_balance_request,
    get_kis_standards
)

from utils.api_debugger import (
    APIDebugger,
    LogLevel,
    APICallStatus,
    APICallRecord,
    get_api_debugger,
    debug_api_call
)

from utils.api_client import KISAPIClient, OpenAIClient


class TestKISAPIStandards:
    """KIS API 표준화 시스템 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.standards = KISAPIStandards()
    
    def test_tr_code_enum(self):
        """TR 코드 Enum 테스트"""
        # 해외주식 현재가 TR 코드 확인
        assert TRCode.OVERSEAS_STOCK_PRICE.value == "HHDFS00000300"
        assert TRCode.OVERSEAS_STOCK_ORDER.value == "HTRFB_JTTT1002U"
        assert TRCode.OVERSEAS_STOCK_BALANCE.value == "HTRFB_FTRG3210U"
        
        # 모든 TR 코드 조회
        all_codes = self.standards.get_all_tr_codes()
        assert len(all_codes) > 0
        assert "HHDFS00000300" in all_codes
    
    def test_market_code_enum(self):
        """마켓 코드 Enum 테스트"""
        assert MarketCode.NASDAQ.value == "NAS"
        assert MarketCode.NYSE.value == "NYS"
        assert MarketCode.AMEX.value == "AMS"
    
    def test_order_enums(self):
        """주문 관련 Enum 테스트"""
        assert OrderSide.BUY.value == "02"
        assert OrderSide.SELL.value == "01"
        
        assert OrderType.MARKET.value == "00"
        assert OrderType.LIMIT.value == "01"
    
    def test_create_stock_price_request(self):
        """주식 현재가 요청 생성 테스트"""
        request = create_stock_price_request("AAPL", "NAS")
        
        assert request.tr_id == TRCode.OVERSEAS_STOCK_PRICE.value
        assert request.params["SYMB"] == "AAPL"
        assert request.params["EXCD"] == "NAS"
        assert "content-type" in request.headers
        assert request.headers["tr_id"] == TRCode.OVERSEAS_STOCK_PRICE.value
    
    def test_create_order_request(self):
        """주문 요청 생성 테스트"""
        request = create_order_request(
            account_no="12345678",
            symbol="AAPL",
            quantity=100,
            price=150.0,
            side="02",
            market="NASD"
        )
        
        assert request.tr_id == TRCode.OVERSEAS_STOCK_ORDER.value
        assert request.body["CANO"] == "12345678"
        assert request.body["PDNO"] == "AAPL"
        assert request.body["ORD_QTY"] == 100
        assert request.body["OVRS_ORD_UNPR"] == 150.0
    
    def test_create_balance_request(self):
        """잔고 조회 요청 생성 테스트"""
        request = create_balance_request("12345678", "NASD")
        
        assert request.tr_id == TRCode.OVERSEAS_STOCK_BALANCE.value
        assert request.params["CANO"] == "12345678"
        assert request.params["OVRS_EXCG_CD"] == "NASD"
        assert request.params["TR_CRCY_CD"] == "USD"
    
    def test_parameter_validation_success(self):
        """파라미터 검증 성공 테스트"""
        # 유효한 파라미터로 요청 생성
        request = self.standards.create_request(
            TRCode.OVERSEAS_STOCK_PRICE,
            SYMB="AAPL",
            EXCD="NAS"
        )
        
        assert request.tr_id == TRCode.OVERSEAS_STOCK_PRICE.value
        assert request.params["SYMB"] == "AAPL"
        assert request.params["EXCD"] == "NAS"
    
    def test_parameter_validation_failure(self):
        """파라미터 검증 실패 테스트"""
        # 필수 파라미터 누락
        try:
            self.standards.create_request(
                TRCode.OVERSEAS_STOCK_PRICE,
                SYMB="AAPL"
                # EXCD 누락
            )
            assert False, "Expected ValueError for missing required parameters"
        except ValueError as e:
            assert "Missing required parameters" in str(e)
        
        # 유효하지 않은 거래소 코드
        try:
            self.standards.create_request(
                TRCode.OVERSEAS_STOCK_PRICE,
                SYMB="AAPL",
                EXCD="INVALID"
            )
            assert False, "Expected ValueError for invalid exchange code"
        except ValueError as e:
            assert "Invalid value" in str(e)
    
    def test_response_parsing_stock_price(self):
        """주식 현재가 응답 파싱 테스트"""
        raw_response = {
            "rt_cd": "0",
            "msg_cd": "200000",
            "msg1": "SUCCESS",
            "output": {
                "symb": "AAPL",
                "name": "Apple Inc",
                "excd": "NAS",
                "last": "150.25",
                "diff": "2.50",
                "rate": "1.69",
                "tvol": "45000000",
                "tamt": "6750000000",
                "high": "151.00",
                "low": "148.50",
                "open": "149.00",
                "base": "147.75"
            }
        }
        
        response = self.standards.parse_response(TRCode.OVERSEAS_STOCK_PRICE, raw_response)
        
        assert response.rt_cd == "0"
        assert response.msg_cd == "200000"
        assert isinstance(response.output, StockInfo)
        
        stock_info = response.output
        assert stock_info.symbol == "AAPL"
        assert stock_info.name == "Apple Inc"
        assert stock_info.current_price == 150.25
        assert stock_info.daily_change == 2.50
        assert stock_info.daily_change_rate == 1.69
        assert stock_info.volume == 45000000
        assert stock_info.market == MarketCode.NASDAQ
    
    def test_response_parsing_error(self):
        """에러 응답 파싱 테스트"""
        raw_response = {
            "rt_cd": "1",
            "msg_cd": "400001",
            "msg1": "Invalid parameter",
            "output": {}
        }
        
        response = self.standards.parse_response(TRCode.OVERSEAS_STOCK_PRICE, raw_response)
        
        assert response.rt_cd == "1"
        assert response.msg_cd == "400001"
        assert response.msg1 == "Invalid parameter"
    
    def test_symbol_validation(self):
        """종목코드 유효성 검증 테스트"""
        # 유효한 종목코드
        assert self.standards.validate_symbol("AAPL", MarketCode.NASDAQ) == True
        assert self.standards.validate_symbol("MSFT", MarketCode.NASDAQ) == True
        assert self.standards.validate_symbol("TSLA", MarketCode.NASDAQ) == True
        
        # 유효하지 않은 종목코드
        assert self.standards.validate_symbol("", MarketCode.NASDAQ) == False
        assert self.standards.validate_symbol("A" * 20, MarketCode.NASDAQ) == False
    
    def test_parameter_info(self):
        """파라미터 정보 조회 테스트"""
        info = self.standards.get_parameter_info(TRCode.OVERSEAS_STOCK_PRICE)
        
        assert "required" in info
        assert "optional" in info
        assert "defaults" in info
        assert "validation" in info
        
        assert "SYMB" in info["required"]
        assert "EXCD" in info["required"]


class TestAPIDebugger:
    """API 디버깅 시스템 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.debugger = APIDebugger(LogLevel.DEBUG)
    
    def test_debugger_initialization(self):
        """디버거 초기화 테스트"""
        assert self.debugger.debug_level == LogLevel.DEBUG
        assert len(self.debugger.call_records) == 0
        assert self.debugger.performance_metrics.total_calls == 0
    
    def test_api_call_recording(self):
        """API 호출 기록 테스트"""
        # 더미 요청 생성
        request = APIRequest(tr_id="TEST_TR")
        
        # API 호출 시작
        call_id = self.debugger.start_api_call("TEST_TR", request, "http://test.com")
        
        assert call_id != ""
        assert len(self.debugger.call_records) == 1
        
        record = self.debugger.call_records[0]
        assert record.call_id == call_id
        assert record.tr_code == "TEST_TR"
        assert record.status == APICallStatus.PENDING
    
    def test_api_call_completion(self):
        """API 호출 완료 기록 테스트"""
        # API 호출 시작
        request = APIRequest(tr_id="TEST_TR")
        call_id = self.debugger.start_api_call("TEST_TR", request, "http://test.com")
        
        # API 호출 완료
        response_body = {"rt_cd": "0", "msg1": "Success"}
        self.debugger.end_api_call(
            call_id=call_id,
            response_status=200,
            response_headers={"content-type": "application/json"},
            response_body=response_body,
            response_time_ms=250.5
        )
        
        record = self.debugger.call_records[0]
        assert record.status == APICallStatus.SUCCESS
        assert record.response_status == 200
        assert record.response_time_ms == 250.5
        assert record.response_body == response_body
    
    def test_performance_metrics(self):
        """성능 지표 테스트"""
        # 여러 API 호출 시뮬레이션
        for i in range(5):
            request = APIRequest(tr_id=f"TEST_TR_{i}")
            call_id = self.debugger.start_api_call(f"TEST_TR_{i}", request, "http://test.com")
            
            # 성공과 실패를 섞어서 테스트
            status = 200 if i % 2 == 0 else 500
            error_msg = "" if i % 2 == 0 else "Test error"
            
            self.debugger.end_api_call(
                call_id=call_id,
                response_status=status,
                response_headers={},
                response_body={"rt_cd": "0" if i % 2 == 0 else "1"},
                response_time_ms=100.0 + i * 50,
                error_message=error_msg
            )
        
        # 성능 지표 확인
        metrics = self.debugger.performance_metrics
        assert metrics.total_calls == 5
        assert metrics.successful_calls == 3  # 0, 2, 4번째
        assert metrics.failed_calls == 2      # 1, 3번째
        
        # 성능 요약 확인
        summary = self.debugger.get_performance_summary()
        assert summary["total_calls"] == 5
        assert summary["success_rate"] == 60.0  # 3/5 * 100
        assert "avg_response_time_ms" in summary
    
    def test_failure_analysis(self):
        """실패 분석 테스트"""
        # 실패 케이스 추가
        request = APIRequest(tr_id="FAIL_TR")
        call_id = self.debugger.start_api_call("FAIL_TR", request, "http://test.com")
        
        self.debugger.end_api_call(
            call_id=call_id,
            response_status=500,
            response_headers={},
            response_body={},
            response_time_ms=1000.0,
            error_message="Server error occurred"
        )
        
        # 실패 분석
        analysis = self.debugger.analyze_failures(24)
        
        assert analysis["total_failures"] >= 1
        assert "failure_rate" in analysis
        assert "top_failure_reasons" in analysis
    
    def test_debug_report_generation(self):
        """디버그 리포트 생성 테스트"""
        # 몇 개의 API 호출 추가
        for i in range(3):
            request = APIRequest(tr_id=f"REPORT_TR_{i}")
            call_id = self.debugger.start_api_call(f"REPORT_TR_{i}", request, "http://test.com")
            
            self.debugger.end_api_call(
                call_id=call_id,
                response_status=200,
                response_headers={},
                response_body={"rt_cd": "0"},
                response_time_ms=150.0
            )
        
        # 리포트 생성
        report = self.debugger.generate_debug_report()
        
        assert "한국투자 Open API 디버그 리포트" in report
        assert "성능 요약" in report
        assert "총 호출 수" in report
    
    def test_debug_decorator(self):
        """디버깅 데코레이터 테스트"""
        @debug_api_call("DECORATOR_TR")
        def test_function():
            time.sleep(0.1)  # 100ms 대기
            return {"result": "success"}
        
        # 함수 실행
        result = test_function()
        
        assert result["result"] == "success"
        
        # 디버거에 기록되었는지 확인
        records = self.debugger.get_recent_calls(1)
        assert len(records) >= 1
        
        # 최근 기록 확인
        recent_record = records[0]
        assert recent_record["tr_code"] == "DECORATOR_TR"
        assert recent_record["status"] == "success"
        assert recent_record["response_time_ms"] >= 100


class TestKISAPIClient:
    """KIS API 클라이언트 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.client = KISAPIClient()
    
    @patch('requests.post')
    def test_authentication(self, mock_post):
        """인증 테스트"""
        # Mock 인증 응답
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "test_token_12345",
            "token_type": "Bearer"
        }
        mock_post.return_value = mock_response
        
        # 인증 실행
        result = self.client.authenticate()
        
        assert result == True
        assert self.client.token == "test_token_12345"
        assert self.client.token_expires is not None
    
    @patch('utils.api_client.KISAPIClient._make_api_call')
    def test_get_stock_price(self, mock_api_call):
        """주식 현재가 조회 테스트"""
        # Mock API 응답
        mock_api_call.return_value = {
            "rt_cd": "0",
            "msg_cd": "200000",
            "msg1": "SUCCESS",
            "output": {
                "symb": "AAPL",
                "name": "Apple Inc",
                "excd": "NAS",
                "last": "150.25",
                "diff": "2.50",
                "rate": "1.69",
                "tvol": "45000000",
                "high": "151.00",
                "low": "148.50",
                "open": "149.00",
                "base": "147.75"
            }
        }
        
        # 주식 현재가 조회
        result = self.client.get_overseas_stock_price("AAPL")
        
        assert result is not None
        assert result["symbol"] == "AAPL"
        assert result["current_price"] == 150.25
        assert result["daily_change"] == 2.50
        assert result["market"] == "NAS"
    
    def test_parameter_template_retrieval(self):
        """파라미터 템플릿 조회 테스트"""
        template = self.client.get_parameter_template("HHDFS00000300")
        
        assert "required" in template
        assert "optional" in template
        assert "validation" in template
    
    def test_parameter_validation(self):
        """파라미터 검증 테스트"""
        # 유효한 파라미터
        result = self.client.validate_request_parameters(
            "HHDFS00000300",
            SYMB="AAPL",
            EXCD="NAS"
        )
        assert result == True
        
        # 유효하지 않은 파라미터
        result = self.client.validate_request_parameters(
            "HHDFS00000300",
            SYMB="AAPL"
            # EXCD 누락
        )
        assert result == False


class TestIntegration:
    """통합 테스트"""
    
    def test_standards_and_debugger_integration(self):
        """표준화 시스템과 디버거 통합 테스트"""
        standards = get_kis_standards()
        debugger = get_api_debugger()
        
        # 요청 생성
        request = create_stock_price_request("AAPL", "NAS")
        
        # 디버깅 시작
        call_id = debugger.start_api_call(request.tr_id, request, "http://test.com")
        
        # 요청 검증
        assert request.tr_id == TRCode.OVERSEAS_STOCK_PRICE.value
        assert call_id != ""
        
        # 디버깅 종료
        debugger.end_api_call(
            call_id=call_id,
            response_status=200,
            response_headers={},
            response_body={"rt_cd": "0"},
            response_time_ms=150.0
        )
        
        # 결과 확인
        records = debugger.get_recent_calls(1)
        assert len(records) == 1
        assert records[0]["tr_code"] == TRCode.OVERSEAS_STOCK_PRICE.value
    
    def test_end_to_end_flow(self):
        """종단간 플로우 테스트"""
        # 1. 표준화된 요청 생성
        request = create_stock_price_request("MSFT", "NAS")
        
        # 2. 파라미터 검증
        standards = get_kis_standards()
        template = standards.get_parameter_info(TRCode.OVERSEAS_STOCK_PRICE)
        assert "SYMB" in template["required"]
        
        # 3. 응답 파싱 테스트
        mock_response = {
            "rt_cd": "0",
            "output": {
                "symb": "MSFT",
                "name": "Microsoft Corp",
                "last": "300.50",
                "excd": "NAS"
            }
        }
        
        parsed = standards.parse_response(TRCode.OVERSEAS_STOCK_PRICE, mock_response)
        assert parsed.rt_cd == "0"
        assert isinstance(parsed.output, StockInfo)
        assert parsed.output.symbol == "MSFT"


# 테스트 실행을 위한 메인 함수
def run_comprehensive_tests():
    """포괄적인 테스트 실행"""
    print("🧪 한국투자 Open API 표준화 시스템 테스트 시작")
    print("=" * 60)
    
    # 각 테스트 클래스별 실행
    test_classes = [
        TestKISAPIStandards,
        TestAPIDebugger,
        TestKISAPIClient,
        TestIntegration
    ]
    
    total_tests = 0
    passed_tests = 0
    
    for test_class in test_classes:
        print(f"\n📋 {test_class.__name__} 테스트 실행중...")
        
        instance = test_class()
        if hasattr(instance, 'setup_method'):
            instance.setup_method()
        
        # 테스트 메서드 실행
        for method_name in dir(instance):
            if method_name.startswith('test_'):
                total_tests += 1
                try:
                    method = getattr(instance, method_name)
                    method()
                    print(f"  ✅ {method_name}")
                    passed_tests += 1
                except Exception as e:
                    print(f"  ❌ {method_name}: {str(e)}")
    
    print("\n" + "=" * 60)
    print(f"🎯 테스트 결과: {passed_tests}/{total_tests} 통과 ({passed_tests/total_tests*100:.1f}%)")
    
    if passed_tests == total_tests:
        print("🎉 모든 테스트 통과! 시스템이 정상적으로 작동합니다.")
    else:
        print(f"⚠️ {total_tests - passed_tests}개 테스트 실패")
    
    return passed_tests == total_tests


if __name__ == "__main__":
    # pytest 대신 직접 실행할 수 있도록
    success = run_comprehensive_tests()
    exit(0 if success else 1)