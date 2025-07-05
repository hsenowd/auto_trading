#!/usr/bin/env python3
"""
한국투자 Open API 표준화/디버깅 시스템 종합 실행 스크립트
- 파라미터 값과 함수 API 함수 및 TR 표준화
- 디버깅 시스템 테스트 및 검증
- 성능 모니터링 및 분석
- 실제 API 호출 테스트 (선택사항)
"""

import sys
import os
import json
import time
from datetime import datetime
from typing import Dict, List, Any

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.kis_api_standards import (
    get_kis_standards,
    TRCode,
    MarketCode,
    create_stock_price_request,
    create_order_request,
    create_balance_request
)
from utils.api_debugger import get_api_debugger, LogLevel
from utils.api_client import KISAPIClient
from utils.simple_logger import get_logger

logger = get_logger()


class APIStandardsValidator:
    """API 표준화 시스템 검증 클래스"""
    
    def __init__(self):
        self.standards = get_kis_standards()
        self.debugger = get_api_debugger()
        self.client = KISAPIClient()
        
    def validate_tr_codes(self) -> Dict[str, Any]:
        """TR 코드 표준화 검증"""
        print("🔍 TR 코드 표준화 검증 중...")
        
        results = {
            "total_tr_codes": 0,
            "valid_tr_codes": 0,
            "tr_code_details": {},
            "validation_errors": []
        }
        
        try:
            # 모든 TR 코드 확인
            all_codes = self.standards.get_all_tr_codes()
            results["total_tr_codes"] = len(all_codes)
            
            for tr_code in [TRCode.OVERSEAS_STOCK_PRICE, TRCode.OVERSEAS_STOCK_ORDER, TRCode.OVERSEAS_STOCK_BALANCE]:
                tr_name = tr_code.name
                tr_value = tr_code.value
                
                # 파라미터 정보 조회
                param_info = self.standards.get_parameter_info(tr_code)
                
                if param_info:
                    results["valid_tr_codes"] += 1
                    results["tr_code_details"][tr_name] = {
                        "code": tr_value,
                        "required_params": param_info.get("required", []),
                        "optional_params": param_info.get("optional", []),
                        "validation_rules": len(param_info.get("validation", {}))
                    }
                    print(f"  ✅ {tr_name}: {tr_value}")
                else:
                    results["validation_errors"].append(f"No parameter info for {tr_name}")
                    print(f"  ❌ {tr_name}: 파라미터 정보 없음")
            
        except Exception as e:
            results["validation_errors"].append(f"TR 코드 검증 오류: {str(e)}")
            logger.error(f"TR 코드 검증 실패: {e}")
        
        return results
    
    def validate_parameter_system(self) -> Dict[str, Any]:
        """파라미터 검증 시스템 테스트"""
        print("🔍 파라미터 검증 시스템 테스트 중...")
        
        results = {
            "parameter_tests": [],
            "validation_success": 0,
            "validation_errors": 0
        }
        
        # 테스트 케이스들
        test_cases = [
            {
                "name": "주식 현재가 조회 - 유효한 파라미터",
                "tr_code": TRCode.OVERSEAS_STOCK_PRICE,
                "params": {"SYMB": "AAPL", "EXCD": "NAS"},
                "should_pass": True
            },
            {
                "name": "주식 현재가 조회 - 필수 파라미터 누락",
                "tr_code": TRCode.OVERSEAS_STOCK_PRICE,
                "params": {"SYMB": "AAPL"},  # EXCD 누락
                "should_pass": False
            },
            {
                "name": "주식 현재가 조회 - 잘못된 거래소 코드",
                "tr_code": TRCode.OVERSEAS_STOCK_PRICE,
                "params": {"SYMB": "AAPL", "EXCD": "INVALID"},
                "should_pass": False
            },
            {
                "name": "주문 요청 - 유효한 파라미터",
                "tr_code": TRCode.OVERSEAS_STOCK_ORDER,
                "params": {
                    "CANO": "12345678",
                    "ACNT_PRDT_CD": "01",
                    "OVRS_EXCG_CD": "NASD",
                    "PDNO": "AAPL",
                    "ORD_QTY": 100,
                    "OVRS_ORD_UNPR": 150.0,
                    "ORD_SVR_DVSN_CD": "0",
                    "SLL_BUY_DVSN_CD": "02"
                },
                "should_pass": True
            }
        ]
        
        for test_case in test_cases:
            try:
                request = self.standards.create_request(
                    test_case["tr_code"],
                    **test_case["params"]
                )
                
                if test_case["should_pass"]:
                    results["validation_success"] += 1
                    print(f"  ✅ {test_case['name']}")
                    results["parameter_tests"].append({
                        "name": test_case["name"],
                        "status": "PASS",
                        "message": "파라미터 검증 성공"
                    })
                else:
                    results["validation_errors"] += 1
                    print(f"  ❌ {test_case['name']}: 실패해야 하는데 성공함")
                    results["parameter_tests"].append({
                        "name": test_case["name"],
                        "status": "FAIL",
                        "message": "예상과 다른 결과"
                    })
                    
            except Exception as e:
                if not test_case["should_pass"]:
                    results["validation_success"] += 1
                    print(f"  ✅ {test_case['name']}: 예상된 오류 발생")
                    results["parameter_tests"].append({
                        "name": test_case["name"],
                        "status": "PASS",
                        "message": f"예상된 오류: {str(e)}"
                    })
                else:
                    results["validation_errors"] += 1
                    print(f"  ❌ {test_case['name']}: {str(e)}")
                    results["parameter_tests"].append({
                        "name": test_case["name"],
                        "status": "FAIL",
                        "message": f"예상치 못한 오류: {str(e)}"
                    })
        
        return results
    
    def test_request_creation(self) -> Dict[str, Any]:
        """표준화된 요청 생성 테스트"""
        print("🔍 표준화된 요청 생성 테스트 중...")
        
        results = {
            "request_tests": [],
            "successful_requests": 0,
            "failed_requests": 0
        }
        
        # 편의 함수 테스트
        test_functions = [
            {
                "name": "주식 현재가 요청 생성",
                "function": lambda: create_stock_price_request("AAPL", "NAS"),
                "expected_tr": TRCode.OVERSEAS_STOCK_PRICE.value
            },
            {
                "name": "주문 요청 생성",
                "function": lambda: create_order_request(
                    account_no="12345678",
                    symbol="AAPL",
                    quantity=100,
                    price=150.0,
                    side="02",
                    market="NASD"
                ),
                "expected_tr": TRCode.OVERSEAS_STOCK_ORDER.value
            },
            {
                "name": "잔고 조회 요청 생성",
                "function": lambda: create_balance_request("12345678", "NASD"),
                "expected_tr": TRCode.OVERSEAS_STOCK_BALANCE.value
            }
        ]
        
        for test in test_functions:
            try:
                request = test["function"]()
                
                if request.tr_id == test["expected_tr"]:
                    results["successful_requests"] += 1
                    print(f"  ✅ {test['name']}")
                    results["request_tests"].append({
                        "name": test["name"],
                        "status": "PASS",
                        "tr_id": request.tr_id,
                        "param_count": len(request.params),
                        "body_count": len(request.body)
                    })
                else:
                    results["failed_requests"] += 1
                    print(f"  ❌ {test['name']}: TR ID 불일치")
                    results["request_tests"].append({
                        "name": test["name"],
                        "status": "FAIL",
                        "message": f"Expected {test['expected_tr']}, got {request.tr_id}"
                    })
                    
            except Exception as e:
                results["failed_requests"] += 1
                print(f"  ❌ {test['name']}: {str(e)}")
                results["request_tests"].append({
                    "name": test["name"],
                    "status": "ERROR",
                    "message": str(e)
                })
        
        return results
    
    def test_debugging_system(self) -> Dict[str, Any]:
        """디버깅 시스템 테스트"""
        print("🔍 디버깅 시스템 테스트 중...")
        
        results = {
            "debug_tests": [],
            "performance_metrics": {},
            "debug_features": []
        }
        
        try:
            # 초기 상태 확인
            initial_calls = self.debugger.performance_metrics.total_calls
            
            # 테스트 API 호출 시뮬레이션
            for i in range(5):
                request = create_stock_price_request(f"TEST{i}", "NAS")
                
                # 디버깅 시작
                call_id = self.debugger.start_api_call(request.tr_id, request, "http://test.api")
                
                # 시뮬레이션 응답 시간
                time.sleep(0.01)  # 10ms
                
                # 성공/실패 랜덤
                status = 200 if i % 2 == 0 else 500
                error_msg = "" if i % 2 == 0 else f"Test error {i}"
                
                # 디버깅 종료
                self.debugger.end_api_call(
                    call_id=call_id,
                    response_status=status,
                    response_headers={"content-type": "application/json"},
                    response_body={"rt_cd": "0" if i % 2 == 0 else "1"},
                    response_time_ms=10.0 + i,
                    error_message=error_msg
                )
            
            # 성능 지표 확인
            metrics = self.debugger.get_performance_summary()
            results["performance_metrics"] = {
                "total_calls": metrics.get("total_calls", 0) - initial_calls,
                "success_rate": metrics.get("success_rate", 0),
                "avg_response_time": metrics.get("avg_response_time_ms", 0)
            }
            
            # 최근 호출 기록 확인
            recent_calls = self.debugger.get_recent_calls(3)
            results["debug_tests"].append({
                "name": "API 호출 기록",
                "status": "PASS" if len(recent_calls) > 0 else "FAIL",
                "recent_call_count": len(recent_calls)
            })
            
            # 실패 분석 확인
            failure_analysis = self.debugger.analyze_failures(1)
            results["debug_tests"].append({
                "name": "실패 분석",
                "status": "PASS" if "total_failures" in failure_analysis else "FAIL",
                "failure_count": failure_analysis.get("total_failures", 0)
            })
            
            # 디버그 리포트 생성
            report = self.debugger.generate_debug_report()
            results["debug_tests"].append({
                "name": "디버그 리포트 생성",
                "status": "PASS" if "한국투자 Open API" in report else "FAIL",
                "report_length": len(report)
            })
            
            print(f"  ✅ 디버깅 시스템 기본 기능 확인")
            print(f"  ✅ 성능 지표 수집: {results['performance_metrics']['total_calls']}회 호출")
            print(f"  ✅ 실패 분석: {failure_analysis.get('total_failures', 0)}회 실패")
            
        except Exception as e:
            results["debug_tests"].append({
                "name": "디버깅 시스템 전체",
                "status": "ERROR",
                "message": str(e)
            })
            print(f"  ❌ 디버깅 시스템 테스트 실패: {str(e)}")
        
        return results
    
    def test_api_client_integration(self) -> Dict[str, Any]:
        """API 클라이언트 통합 테스트"""
        print("🔍 API 클라이언트 통합 테스트 중...")
        
        results = {
            "client_tests": [],
            "integration_status": "UNKNOWN"
        }
        
        try:
            # 파라미터 템플릿 조회
            template = self.client.get_parameter_template("HHDFS00000300")
            
            if template and "required" in template:
                results["client_tests"].append({
                    "name": "파라미터 템플릿 조회",
                    "status": "PASS",
                    "template_keys": list(template.keys())
                })
                print(f"  ✅ 파라미터 템플릿 조회")
            else:
                results["client_tests"].append({
                    "name": "파라미터 템플릿 조회",
                    "status": "FAIL",
                    "message": "템플릿 정보 없음"
                })
                print(f"  ❌ 파라미터 템플릿 조회 실패")
            
            # 파라미터 검증
            valid_result = self.client.validate_request_parameters(
                "HHDFS00000300",
                SYMB="AAPL",
                EXCD="NAS"
            )
            
            invalid_result = self.client.validate_request_parameters(
                "HHDFS00000300",
                SYMB="AAPL"
                # EXCD 누락
            )
            
            if valid_result and not invalid_result:
                results["client_tests"].append({
                    "name": "파라미터 검증",
                    "status": "PASS",
                    "valid_test": valid_result,
                    "invalid_test": invalid_result
                })
                print(f"  ✅ 파라미터 검증")
            else:
                results["client_tests"].append({
                    "name": "파라미터 검증",
                    "status": "FAIL",
                    "message": f"Valid: {valid_result}, Invalid: {invalid_result}"
                })
                print(f"  ❌ 파라미터 검증 실패")
            
            # 전체 통합 상태 결정
            passed_tests = sum(1 for test in results["client_tests"] if test["status"] == "PASS")
            total_tests = len(results["client_tests"])
            
            if passed_tests == total_tests:
                results["integration_status"] = "PASS"
            elif passed_tests > 0:
                results["integration_status"] = "PARTIAL"
            else:
                results["integration_status"] = "FAIL"
                
        except Exception as e:
            results["client_tests"].append({
                "name": "API 클라이언트 통합",
                "status": "ERROR",
                "message": str(e)
            })
            results["integration_status"] = "ERROR"
            print(f"  ❌ API 클라이언트 통합 테스트 실패: {str(e)}")
        
        return results


def generate_comprehensive_report(validation_results: Dict[str, Any]) -> str:
    """종합 검증 리포트 생성"""
    report_lines = []
    
    report_lines.append("=" * 80)
    report_lines.append("🎯 한국투자 Open API 표준화/디버깅 시스템 종합 검증 리포트")
    report_lines.append("=" * 80)
    report_lines.append(f"📅 생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # TR 코드 검증 결과
    tr_results = validation_results.get("tr_codes", {})
    report_lines.append(f"\n📋 TR 코드 표준화 검증:")
    report_lines.append(f"   총 TR 코드: {tr_results.get('total_tr_codes', 0)}개")
    report_lines.append(f"   유효한 TR 코드: {tr_results.get('valid_tr_codes', 0)}개")
    
    if tr_results.get("validation_errors"):
        report_lines.append("   ❌ 오류:")
        for error in tr_results["validation_errors"]:
            report_lines.append(f"     - {error}")
    
    # 파라미터 검증 결과
    param_results = validation_results.get("parameters", {})
    report_lines.append(f"\n🔍 파라미터 검증 시스템:")
    report_lines.append(f"   성공: {param_results.get('validation_success', 0)}개")
    report_lines.append(f"   실패: {param_results.get('validation_errors', 0)}개")
    
    # 요청 생성 결과
    request_results = validation_results.get("requests", {})
    report_lines.append(f"\n📝 요청 생성 테스트:")
    report_lines.append(f"   성공: {request_results.get('successful_requests', 0)}개")
    report_lines.append(f"   실패: {request_results.get('failed_requests', 0)}개")
    
    # 디버깅 시스템 결과
    debug_results = validation_results.get("debugging", {})
    debug_metrics = debug_results.get("performance_metrics", {})
    report_lines.append(f"\n🔧 디버깅 시스템:")
    report_lines.append(f"   테스트 API 호출: {debug_metrics.get('total_calls', 0)}회")
    report_lines.append(f"   성공률: {debug_metrics.get('success_rate', 0):.1f}%")
    report_lines.append(f"   평균 응답시간: {debug_metrics.get('avg_response_time', 0):.1f}ms")
    
    # API 클라이언트 통합 결과
    client_results = validation_results.get("client", {})
    integration_status = client_results.get("integration_status", "UNKNOWN")
    status_emoji = {"PASS": "✅", "PARTIAL": "⚠️", "FAIL": "❌", "ERROR": "💥"}.get(integration_status, "❓")
    report_lines.append(f"\n🔗 API 클라이언트 통합:")
    report_lines.append(f"   상태: {status_emoji} {integration_status}")
    
    # 전체 평가
    report_lines.append(f"\n🎯 전체 평가:")
    
    total_success = (
        tr_results.get('valid_tr_codes', 0) +
        param_results.get('validation_success', 0) +
        request_results.get('successful_requests', 0)
    )
    
    total_tests = (
        tr_results.get('total_tr_codes', 0) +
        len(param_results.get('parameter_tests', [])) +
        len(request_results.get('request_tests', []))
    )
    
    if total_tests > 0:
        success_rate = (total_success / total_tests) * 100
        report_lines.append(f"   전체 성공률: {success_rate:.1f}% ({total_success}/{total_tests})")
        
        if success_rate >= 90:
            report_lines.append("   🎉 우수: 시스템이 매우 안정적으로 작동합니다!")
        elif success_rate >= 70:
            report_lines.append("   ✅ 양호: 시스템이 정상적으로 작동합니다.")
        elif success_rate >= 50:
            report_lines.append("   ⚠️ 주의: 일부 문제가 있습니다. 검토가 필요합니다.")
        else:
            report_lines.append("   ❌ 위험: 심각한 문제가 있습니다. 즉시 수정이 필요합니다.")
    
    # 권장사항
    report_lines.append(f"\n💡 권장사항:")
    
    if tr_results.get("validation_errors"):
        report_lines.append("   - TR 코드 검증 오류를 수정하세요")
    
    if param_results.get("validation_errors", 0) > 0:
        report_lines.append("   - 파라미터 검증 규칙을 점검하세요")
    
    if debug_metrics.get("total_calls", 0) == 0:
        report_lines.append("   - 디버깅 시스템 실제 사용을 확인하세요")
    
    if integration_status != "PASS":
        report_lines.append("   - API 클라이언트 통합 문제를 해결하세요")
    
    report_lines.append("\n" + "=" * 80)
    
    return "\n".join(report_lines)


def main():
    """메인 실행 함수"""
    print("🚀 한국투자 Open API 표준화/디버깅 시스템 종합 검증 시작")
    print("=" * 80)
    
    validator = APIStandardsValidator()
    validation_results = {}
    
    try:
        # 1. TR 코드 표준화 검증
        validation_results["tr_codes"] = validator.validate_tr_codes()
        
        # 2. 파라미터 검증 시스템 테스트
        validation_results["parameters"] = validator.validate_parameter_system()
        
        # 3. 요청 생성 테스트
        validation_results["requests"] = validator.test_request_creation()
        
        # 4. 디버깅 시스템 테스트
        validation_results["debugging"] = validator.test_debugging_system()
        
        # 5. API 클라이언트 통합 테스트
        validation_results["client"] = validator.test_api_client_integration()
        
        # 종합 리포트 생성
        report = generate_comprehensive_report(validation_results)
        print("\n" + report)
        
        # 결과를 파일에 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"logs/api_standards_validation_{timestamp}.txt"
        
        os.makedirs("logs", exist_ok=True)
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)
        
        print(f"\n📄 상세 리포트가 저장되었습니다: {report_file}")
        
        # JSON 결과도 저장
        json_file = f"data/validation_results_{timestamp}.json"
        os.makedirs("data", exist_ok=True)
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(validation_results, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"📊 JSON 결과가 저장되었습니다: {json_file}")
        
    except Exception as e:
        print(f"❌ 검증 과정에서 오류 발생: {str(e)}")
        logger.error(f"Validation process failed: {e}")
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)