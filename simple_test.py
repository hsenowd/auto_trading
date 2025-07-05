#!/usr/bin/env python3
"""
한국투자 Open API 표준화 시스템 간단 테스트
외부 의존성 없이 핵심 기능만 테스트
"""

import sys
import os
from datetime import datetime

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_standards_system():
    """표준화 시스템 테스트"""
    print("🧪 한국투자 Open API 표준화 시스템 테스트")
    print("=" * 60)
    
    test_results = {
        "passed": 0,
        "failed": 0,
        "errors": []
    }
    
    try:
        # 1. 기본 import 테스트
        print("📦 모듈 import 테스트...")
        
        from utils.kis_api_standards import (
            TRCode,
            MarketCode,
            OrderSide,
            OrderType,
            APIRequest,
            APIResponse,
            StockInfo,
            create_stock_price_request,
            get_kis_standards
        )
        print("  ✅ utils.kis_api_standards 모듈 import 성공")
        test_results["passed"] += 1
        
        from utils.api_debugger import (
            get_api_debugger,
            LogLevel,
            APIDebugger
        )
        print("  ✅ utils.api_debugger 모듈 import 성공")
        test_results["passed"] += 1
        
    except Exception as e:
        print(f"  ❌ 모듈 import 실패: {e}")
        test_results["failed"] += 1
        test_results["errors"].append(f"Import error: {e}")
        return test_results
    
    # 2. TR 코드 표준화 테스트
    print("\n🔍 TR 코드 표준화 테스트...")
    try:
        # TR 코드 확인
        assert TRCode.OVERSEAS_STOCK_PRICE.value == "HHDFS00000300"
        assert TRCode.OVERSEAS_STOCK_ORDER.value == "HTRFB_JTTT1002U"
        assert TRCode.OVERSEAS_STOCK_BALANCE.value == "HTRFB_FTRG3210U"
        print("  ✅ TR 코드 값 검증 성공")
        test_results["passed"] += 1
        
        # 마켓 코드 확인
        assert MarketCode.NASDAQ.value == "NAS"
        assert MarketCode.NYSE.value == "NYS"
        assert MarketCode.AMEX.value == "AMS"
        print("  ✅ 마켓 코드 값 검증 성공")
        test_results["passed"] += 1
        
        # 주문 코드 확인
        assert OrderSide.BUY.value == "02"
        assert OrderSide.SELL.value == "01"
        print("  ✅ 주문 코드 값 검증 성공")
        test_results["passed"] += 1
        
    except Exception as e:
        print(f"  ❌ TR 코드 테스트 실패: {e}")
        test_results["failed"] += 1
        test_results["errors"].append(f"TR code test error: {e}")
    
    # 3. 요청 생성 테스트
    print("\n📝 요청 생성 테스트...")
    try:
        # 주식 현재가 요청 생성
        request = create_stock_price_request("AAPL", "NAS")
        assert request.tr_id == TRCode.OVERSEAS_STOCK_PRICE.value
        assert request.params["SYMB"] == "AAPL"
        assert request.params["EXCD"] == "NAS"
        print("  ✅ 주식 현재가 요청 생성 성공")
        test_results["passed"] += 1
        
        # APIRequest 객체 생성
        api_request = APIRequest(tr_id="TEST_TR", params={"test": "value"})
        assert api_request.tr_id == "TEST_TR"
        assert api_request.params["test"] == "value"
        print("  ✅ APIRequest 객체 생성 성공")
        test_results["passed"] += 1
        
    except Exception as e:
        print(f"  ❌ 요청 생성 테스트 실패: {e}")
        test_results["failed"] += 1
        test_results["errors"].append(f"Request creation error: {e}")
    
    # 4. 파라미터 검증 테스트
    print("\n🔧 파라미터 검증 테스트...")
    try:
        standards = get_kis_standards()
        
        # 유효한 파라미터 테스트
        valid_request = standards.create_request(
            TRCode.OVERSEAS_STOCK_PRICE,
            SYMB="AAPL",
            EXCD="NAS"
        )
        assert valid_request.tr_id == TRCode.OVERSEAS_STOCK_PRICE.value
        print("  ✅ 유효한 파라미터 검증 성공")
        test_results["passed"] += 1
        
        # 무효한 파라미터 테스트 (필수 파라미터 누락)
        try:
            invalid_request = standards.create_request(
                TRCode.OVERSEAS_STOCK_PRICE,
                SYMB="AAPL"
                # EXCD 누락
            )
            print("  ❌ 무효한 파라미터 검증 실패 (예외가 발생해야 함)")
            test_results["failed"] += 1
        except ValueError:
            print("  ✅ 무효한 파라미터 검증 성공 (예상된 예외 발생)")
            test_results["passed"] += 1
        
    except Exception as e:
        print(f"  ❌ 파라미터 검증 테스트 실패: {e}")
        test_results["failed"] += 1
        test_results["errors"].append(f"Parameter validation error: {e}")
    
    # 5. 응답 파싱 테스트
    print("\n📊 응답 파싱 테스트...")
    try:
        # 모의 응답 데이터
        mock_response = {
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
        
        response = standards.parse_response(TRCode.OVERSEAS_STOCK_PRICE, mock_response)
        assert response.rt_cd == "0"
        assert response.msg_cd == "200000"
        
        stock_info = response.output
        assert stock_info.symbol == "AAPL"
        assert stock_info.current_price == 150.25
        assert stock_info.market == MarketCode.NASDAQ
        
        print("  ✅ 응답 파싱 성공")
        test_results["passed"] += 1
        
    except Exception as e:
        print(f"  ❌ 응답 파싱 테스트 실패: {e}")
        test_results["failed"] += 1
        test_results["errors"].append(f"Response parsing error: {e}")
    
    # 6. 디버깅 시스템 테스트
    print("\n🔍 디버깅 시스템 테스트...")
    try:
        debugger = get_api_debugger()
        
        # 초기 상태 확인
        initial_calls = debugger.performance_metrics.total_calls
        
        # 테스트 API 호출 시뮬레이션
        test_request = APIRequest(tr_id="TEST_TR")
        call_id = debugger.start_api_call("TEST_TR", test_request, "http://test.com")
        
        assert call_id != ""
        assert len(debugger.call_records) > initial_calls
        print("  ✅ API 호출 기록 시작 성공")
        test_results["passed"] += 1
        
        # API 호출 완료
        debugger.end_api_call(
            call_id=call_id,
            response_status=200,
            response_headers={"content-type": "application/json"},
            response_body={"rt_cd": "0"},
            response_time_ms=150.0
        )
        
        # 성능 요약 확인
        summary = debugger.get_performance_summary()
        assert "total_calls" in summary
        assert summary["total_calls"] > initial_calls
        print("  ✅ 성능 지표 수집 성공")
        test_results["passed"] += 1
        
    except Exception as e:
        print(f"  ❌ 디버깅 시스템 테스트 실패: {e}")
        test_results["failed"] += 1
        test_results["errors"].append(f"Debugging system error: {e}")
    
    return test_results


def main():
    """메인 함수"""
    print(f"🚀 테스트 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 테스트 실행
    results = test_standards_system()
    
    # 결과 출력
    total_tests = results["passed"] + results["failed"]
    success_rate = (results["passed"] / total_tests) * 100 if total_tests > 0 else 0
    
    print("\n" + "=" * 60)
    print("🎯 테스트 결과 요약")
    print("=" * 60)
    print(f"✅ 성공: {results['passed']}개")
    print(f"❌ 실패: {results['failed']}개")
    print(f"📊 성공률: {success_rate:.1f}% ({results['passed']}/{total_tests})")
    
    if results["errors"]:
        print(f"\n❗ 오류 목록:")
        for i, error in enumerate(results["errors"], 1):
            print(f"  {i}. {error}")
    
    if success_rate >= 90:
        print("\n🎉 우수: API 표준화 시스템이 정상적으로 작동합니다!")
        status = "EXCELLENT"
    elif success_rate >= 70:
        print("\n✅ 양호: 시스템이 잘 작동하고 있습니다.")
        status = "GOOD"
    elif success_rate >= 50:
        print("\n⚠️ 주의: 일부 문제가 있습니다.")
        status = "WARNING"
    else:
        print("\n❌ 위험: 심각한 문제가 있습니다.")
        status = "CRITICAL"
    
    print(f"\n📅 테스트 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 결과를 파일에 저장
    try:
        os.makedirs("logs", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        with open(f"logs/simple_test_result_{timestamp}.txt", "w", encoding="utf-8") as f:
            f.write(f"한국투자 Open API 표준화 시스템 테스트 결과\n")
            f.write(f"테스트 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"성공: {results['passed']}개\n")
            f.write(f"실패: {results['failed']}개\n")
            f.write(f"성공률: {success_rate:.1f}%\n")
            f.write(f"상태: {status}\n")
            
            if results["errors"]:
                f.write(f"\n오류 목록:\n")
                for error in results["errors"]:
                    f.write(f"- {error}\n")
        
        print(f"\n📄 테스트 결과가 저장되었습니다: logs/simple_test_result_{timestamp}.txt")
        
    except Exception as e:
        print(f"⚠️ 결과 파일 저장 실패: {e}")
    
    return success_rate >= 70


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)