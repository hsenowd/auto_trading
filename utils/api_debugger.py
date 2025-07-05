"""
한국투자 Open API 고도화된 디버깅 및 로깅 시스템
- API 요청/응답 상세 로깅
- 파라미터 검증 및 오류 분석
- 성능 모니터링 및 지표 추적
- 디버깅 유틸리티 및 테스트 도구
"""

import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading
import traceback
import os

from utils.simple_logger import get_logger, log_error
from utils.kis_api_standards import TRCode, APIRequest, APIResponse

logger = get_logger()


class LogLevel(Enum):
    """로그 레벨"""
    TRACE = "TRACE"      # 모든 세부사항
    DEBUG = "DEBUG"      # 디버깅 정보
    INFO = "INFO"        # 일반 정보
    WARN = "WARN"        # 경고
    ERROR = "ERROR"      # 오류
    CRITICAL = "CRITICAL" # 치명적 오류


class APICallStatus(Enum):
    """API 호출 상태"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RETRYING = "retrying"


@dataclass
class APICallRecord:
    """API 호출 기록"""
    call_id: str
    tr_code: str
    timestamp: datetime
    
    # 요청 정보
    request_url: str
    request_headers: Dict[str, str]
    request_params: Dict[str, Any]
    request_body: Dict[str, Any]
    
    # 응답 정보
    response_status: int = 0
    response_headers: Dict[str, str] = field(default_factory=dict)
    response_body: Dict[str, Any] = field(default_factory=dict)
    response_time_ms: float = 0.0
    
    # 상태 및 오류
    status: APICallStatus = APICallStatus.PENDING
    error_message: str = ""
    error_code: str = ""
    retry_count: int = 0
    
    # 검증 결과
    parameter_validation: Dict[str, Any] = field(default_factory=dict)
    response_validation: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """성능 지표"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    avg_response_time: float = 0.0
    min_response_time: float = float('inf')
    max_response_time: float = 0.0
    
    # TR별 통계
    tr_code_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # 시간대별 통계
    hourly_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    # 에러 통계
    error_stats: Dict[str, int] = field(default_factory=dict)


class APIDebugger:
    """API 디버깅 시스템"""
    
    def __init__(self, debug_level: LogLevel = LogLevel.INFO):
        self.debug_level = debug_level
        self.call_records: List[APICallRecord] = []
        self.performance_metrics = PerformanceMetrics()
        self.lock = threading.Lock()
        
        # 설정
        self.max_records = 1000  # 최대 기록 수
        self.log_sensitive_data = False  # 민감 데이터 로깅 여부
        self.save_to_file = True  # 파일 저장 여부
        
        # 파일 경로
        self.debug_log_path = "logs/api_debug.log"
        self.call_records_path = "data/api_call_records.json"
        
        # 디렉토리 생성
        os.makedirs("logs", exist_ok=True)
        os.makedirs("data", exist_ok=True)
        
        logger.info(f"API Debugger initialized (Level: {debug_level.value})")
    
    def start_api_call(self, tr_code: str, request: APIRequest, url: str) -> str:
        """API 호출 시작 기록"""
        try:
            with self.lock:
                # 고유 호출 ID 생성
                call_id = self._generate_call_id(tr_code)
                
                # 호출 기록 생성
                record = APICallRecord(
                    call_id=call_id,
                    tr_code=tr_code,
                    timestamp=datetime.now(),
                    request_url=url,
                    request_headers=self._sanitize_headers(request.headers),
                    request_params=request.params,
                    request_body=request.body,
                    status=APICallStatus.PENDING
                )
                
                # 파라미터 검증
                record.parameter_validation = self._validate_request_parameters(request)
                
                self.call_records.append(record)
                
                # 기록 수 제한
                if len(self.call_records) > self.max_records:
                    self.call_records = self.call_records[-self.max_records:]
                
                # 로깅
                if self.debug_level.value in ["TRACE", "DEBUG"]:
                    self._log_api_call_start(record)
                
                return call_id
                
        except Exception as e:
            log_error("DEBUG_START_ERROR", f"Failed to start API call debug for {tr_code}", e)
            return ""
    
    def end_api_call(self, call_id: str, response_status: int, 
                    response_headers: Dict[str, str], response_body: Dict[str, Any], 
                    response_time_ms: float, error_message: str = "") -> None:
        """API 호출 종료 기록"""
        try:
            with self.lock:
                record = self._find_record_by_id(call_id)
                if not record:
                    logger.warning(f"API call record not found: {call_id}")
                    return
                
                # 응답 정보 업데이트
                record.response_status = response_status
                record.response_headers = self._sanitize_headers(response_headers)
                record.response_body = response_body
                record.response_time_ms = response_time_ms
                record.error_message = error_message
                
                # 상태 결정
                if response_status == 200 and not error_message:
                    record.status = APICallStatus.SUCCESS
                else:
                    record.status = APICallStatus.FAILED
                    if "timeout" in error_message.lower():
                        record.status = APICallStatus.TIMEOUT
                
                # 응답 검증
                record.response_validation = self._validate_response(record)
                
                # 성능 지표 업데이트
                self._update_performance_metrics(record)
                
                # 로깅
                self._log_api_call_end(record)
                
                # 파일 저장
                if self.save_to_file:
                    self._save_record_to_file(record)
                    
        except Exception as e:
            log_error("DEBUG_END_ERROR", f"Failed to end API call debug for {call_id}", e)
    
    def _generate_call_id(self, tr_code: str) -> str:
        """고유 호출 ID 생성"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        call_data = f"{tr_code}_{timestamp}_{threading.current_thread().ident}"
        return hashlib.md5(call_data.encode()).hexdigest()[:16]
    
    def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """헤더에서 민감 정보 제거"""
        sanitized = headers.copy()
        
        if not self.log_sensitive_data:
            sensitive_keys = ['authorization', 'appkey', 'appsecret', 'token']
            for key in sensitive_keys:
                if key in sanitized:
                    if key == 'authorization':
                        sanitized[key] = "Bearer ****"
                    else:
                        sanitized[key] = "****"
        
        return sanitized
    
    def _validate_request_parameters(self, request: APIRequest) -> Dict[str, Any]:
        """요청 파라미터 검증"""
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "param_count": len(request.params),
            "body_size": len(json.dumps(request.body)) if request.body else 0
        }
        
        try:
            # 기본 검증
            if not request.tr_id:
                validation_result["errors"].append("Missing TR ID")
                validation_result["is_valid"] = False
            
            # 헤더 검증
            required_headers = ["content-type", "tr_id"]
            for header in required_headers:
                if header not in request.headers:
                    validation_result["errors"].append(f"Missing required header: {header}")
                    validation_result["is_valid"] = False
            
            # 파라미터 타입 검증
            for key, value in request.params.items():
                if value is None:
                    validation_result["warnings"].append(f"Null parameter: {key}")
                elif isinstance(value, str) and len(value) == 0:
                    validation_result["warnings"].append(f"Empty parameter: {key}")
            
        except Exception as e:
            validation_result["errors"].append(f"Validation exception: {str(e)}")
            validation_result["is_valid"] = False
        
        return validation_result
    
    def _validate_response(self, record: APICallRecord) -> Dict[str, Any]:
        """응답 검증"""
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "response_size": len(json.dumps(record.response_body)) if record.response_body else 0,
            "has_error_code": False,
            "kis_rt_cd": ""
        }
        
        try:
            # HTTP 상태 코드 검증
            if record.response_status != 200:
                validation_result["errors"].append(f"HTTP error: {record.response_status}")
                validation_result["is_valid"] = False
            
            # KIS API 응답 구조 검증
            if record.response_body:
                rt_cd = record.response_body.get("rt_cd", "")
                validation_result["kis_rt_cd"] = rt_cd
                
                if rt_cd != "0":
                    msg_cd = record.response_body.get("msg_cd", "")
                    msg1 = record.response_body.get("msg1", "")
                    validation_result["errors"].append(f"KIS API error: {msg_cd} - {msg1}")
                    validation_result["has_error_code"] = True
                    validation_result["is_valid"] = False
                
                # output 필드 검증
                if "output" not in record.response_body:
                    validation_result["warnings"].append("No output field in response")
            else:
                validation_result["errors"].append("Empty response body")
                validation_result["is_valid"] = False
        
        except Exception as e:
            validation_result["errors"].append(f"Response validation exception: {str(e)}")
            validation_result["is_valid"] = False
        
        return validation_result
    
    def _update_performance_metrics(self, record: APICallRecord):
        """성능 지표 업데이트"""
        try:
            metrics = self.performance_metrics
            
            # 전체 통계
            metrics.total_calls += 1
            
            if record.status == APICallStatus.SUCCESS:
                metrics.successful_calls += 1
            else:
                metrics.failed_calls += 1
                
                # 에러 통계
                error_key = record.error_message[:50] if record.error_message else "Unknown"
                metrics.error_stats[error_key] = metrics.error_stats.get(error_key, 0) + 1
            
            # 응답 시간 통계
            if record.response_time_ms > 0:
                metrics.min_response_time = min(metrics.min_response_time, record.response_time_ms)
                metrics.max_response_time = max(metrics.max_response_time, record.response_time_ms)
                
                # 평균 응답 시간 계산
                total_time = metrics.avg_response_time * (metrics.total_calls - 1) + record.response_time_ms
                metrics.avg_response_time = total_time / metrics.total_calls
            
            # TR별 통계
            tr_code = record.tr_code
            if tr_code not in metrics.tr_code_stats:
                metrics.tr_code_stats[tr_code] = {
                    "total": 0,
                    "success": 0,
                    "failed": 0,
                    "avg_time": 0.0
                }
            
            tr_stats = metrics.tr_code_stats[tr_code]
            tr_stats["total"] += 1
            
            if record.status == APICallStatus.SUCCESS:
                tr_stats["success"] += 1
            else:
                tr_stats["failed"] += 1
            
            if record.response_time_ms > 0:
                total_tr_time = tr_stats["avg_time"] * (tr_stats["total"] - 1) + record.response_time_ms
                tr_stats["avg_time"] = total_tr_time / tr_stats["total"]
            
            # 시간대별 통계
            hour_key = record.timestamp.strftime("%Y-%m-%d_%H")
            if hour_key not in metrics.hourly_stats:
                metrics.hourly_stats[hour_key] = {"total": 0, "success": 0, "failed": 0}
            
            hour_stats = metrics.hourly_stats[hour_key]
            hour_stats["total"] += 1
            
            if record.status == APICallStatus.SUCCESS:
                hour_stats["success"] += 1
            else:
                hour_stats["failed"] += 1
                
        except Exception as e:
            log_error("METRICS_UPDATE_ERROR", "Failed to update performance metrics", e)
    
    def _find_record_by_id(self, call_id: str) -> Optional[APICallRecord]:
        """호출 ID로 기록 찾기"""
        for record in reversed(self.call_records):  # 최신 기록부터 검색
            if record.call_id == call_id:
                return record
        return None
    
    def _log_api_call_start(self, record: APICallRecord):
        """API 호출 시작 로깅"""
        try:
            if self.debug_level == LogLevel.TRACE:
                logger.debug(f"🚀 API Call Start [{record.call_id[:8]}]")
                logger.debug(f"   TR: {record.tr_code}")
                logger.debug(f"   URL: {record.request_url}")
                logger.debug(f"   Headers: {json.dumps(record.request_headers, indent=2)}")
                logger.debug(f"   Params: {json.dumps(record.request_params, indent=2)}")
                if record.request_body:
                    logger.debug(f"   Body: {json.dumps(record.request_body, indent=2)}")
            elif self.debug_level == LogLevel.DEBUG:
                logger.debug(f"🚀 API Call: {record.tr_code} [{record.call_id[:8]}]")
                
        except Exception as e:
            log_error("LOG_START_ERROR", "Failed to log API call start", e)
    
    def _log_api_call_end(self, record: APICallRecord):
        """API 호출 종료 로깅"""
        try:
            status_emoji = "✅" if record.status == APICallStatus.SUCCESS else "❌"
            
            if self.debug_level == LogLevel.TRACE:
                logger.debug(f"{status_emoji} API Call End [{record.call_id[:8]}]")
                logger.debug(f"   Status: {record.response_status}")
                logger.debug(f"   Time: {record.response_time_ms:.1f}ms")
                logger.debug(f"   Response: {json.dumps(record.response_body, indent=2)}")
                if record.error_message:
                    logger.debug(f"   Error: {record.error_message}")
                    
            elif self.debug_level == LogLevel.DEBUG:
                logger.debug(f"{status_emoji} API Result: {record.tr_code} "
                           f"({record.response_time_ms:.1f}ms) [{record.call_id[:8]}]")
                if record.error_message:
                    logger.debug(f"   Error: {record.error_message}")
            
            elif self.debug_level == LogLevel.INFO:
                if record.status != APICallStatus.SUCCESS:
                    logger.info(f"❌ API Failed: {record.tr_code} - {record.error_message}")
                    
        except Exception as e:
            log_error("LOG_END_ERROR", "Failed to log API call end", e)
    
    def _save_record_to_file(self, record: APICallRecord):
        """기록을 파일에 저장"""
        try:
            # 디버그 로그 파일에 추가
            log_entry = {
                "timestamp": record.timestamp.isoformat(),
                "call_id": record.call_id,
                "tr_code": record.tr_code,
                "status": record.status.value,
                "response_time_ms": record.response_time_ms,
                "response_status": record.response_status,
                "error_message": record.error_message,
                "parameter_validation": record.parameter_validation,
                "response_validation": record.response_validation
            }
            
            with open(self.debug_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                
        except Exception as e:
            log_error("SAVE_RECORD_ERROR", "Failed to save debug record to file", e)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """성능 요약 조회"""
        try:
            metrics = self.performance_metrics
            
            success_rate = 0.0
            if metrics.total_calls > 0:
                success_rate = (metrics.successful_calls / metrics.total_calls) * 100
            
            return {
                "total_calls": metrics.total_calls,
                "successful_calls": metrics.successful_calls,
                "failed_calls": metrics.failed_calls,
                "success_rate": success_rate,
                "avg_response_time_ms": metrics.avg_response_time,
                "min_response_time_ms": metrics.min_response_time,
                "max_response_time_ms": metrics.max_response_time,
                "tr_code_stats": dict(metrics.tr_code_stats),
                "top_errors": dict(sorted(metrics.error_stats.items(), 
                                        key=lambda x: x[1], reverse=True)[:5]),
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            log_error("PERFORMANCE_SUMMARY_ERROR", "Failed to get performance summary", e)
            return {}
    
    def get_recent_calls(self, limit: int = 10) -> List[Dict[str, Any]]:
        """최근 API 호출 조회"""
        try:
            recent_records = self.call_records[-limit:] if limit > 0 else self.call_records
            
            result = []
            for record in reversed(recent_records):  # 최신순 정렬
                result.append({
                    "call_id": record.call_id,
                    "tr_code": record.tr_code,
                    "timestamp": record.timestamp.isoformat(),
                    "status": record.status.value,
                    "response_time_ms": record.response_time_ms,
                    "response_status": record.response_status,
                    "error_message": record.error_message,
                    "is_valid": record.response_validation.get("is_valid", False),
                    "param_count": len(record.request_params),
                    "retry_count": record.retry_count
                })
            
            return result
            
        except Exception as e:
            log_error("RECENT_CALLS_ERROR", "Failed to get recent calls", e)
            return []
    
    def analyze_failures(self, hours: int = 24) -> Dict[str, Any]:
        """실패 분석"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            failed_records = [
                record for record in self.call_records
                if record.timestamp >= cutoff_time and record.status != APICallStatus.SUCCESS
            ]
            
            if not failed_records:
                return {"message": "No failures found in the specified time period"}
            
            # 실패 원인 분석
            failure_reasons = {}
            tr_code_failures = {}
            
            for record in failed_records:
                # 실패 원인
                reason = record.error_message[:50] if record.error_message else "Unknown"
                failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
                
                # TR별 실패
                tr_code_failures[record.tr_code] = tr_code_failures.get(record.tr_code, 0) + 1
            
            return {
                "total_failures": len(failed_records),
                "time_period_hours": hours,
                "failure_rate": (len(failed_records) / len(self.call_records)) * 100 if self.call_records else 0,
                "top_failure_reasons": dict(sorted(failure_reasons.items(), 
                                                 key=lambda x: x[1], reverse=True)[:5]),
                "failed_tr_codes": dict(sorted(tr_code_failures.items(), 
                                             key=lambda x: x[1], reverse=True)[:5]),
                "analysis_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            log_error("FAILURE_ANALYSIS_ERROR", "Failed to analyze failures", e)
            return {}
    
    def generate_debug_report(self) -> str:
        """디버그 리포트 생성"""
        try:
            report_lines = []
            report_lines.append("=" * 60)
            report_lines.append("한국투자 Open API 디버그 리포트")
            report_lines.append("=" * 60)
            
            # 성능 요약
            summary = self.get_performance_summary()
            report_lines.append(f"\n📊 성능 요약:")
            report_lines.append(f"   총 호출 수: {summary.get('total_calls', 0):,}")
            report_lines.append(f"   성공률: {summary.get('success_rate', 0):.1f}%")
            report_lines.append(f"   평균 응답시간: {summary.get('avg_response_time_ms', 0):.1f}ms")
            
            # TR별 통계
            tr_stats = summary.get('tr_code_stats', {})
            if tr_stats:
                report_lines.append(f"\n📋 TR별 통계:")
                for tr_code, stats in tr_stats.items():
                    success_rate = (stats['success'] / stats['total']) * 100 if stats['total'] > 0 else 0
                    report_lines.append(f"   {tr_code}: {stats['total']}회 (성공률: {success_rate:.1f}%)")
            
            # 최근 실패 분석
            failures = self.analyze_failures(24)
            if failures.get('total_failures', 0) > 0:
                report_lines.append(f"\n❌ 최근 24시간 실패 분석:")
                report_lines.append(f"   총 실패: {failures['total_failures']}회")
                report_lines.append(f"   실패율: {failures['failure_rate']:.1f}%")
                
                top_reasons = failures.get('top_failure_reasons', {})
                if top_reasons:
                    report_lines.append(f"   주요 실패 원인:")
                    for reason, count in top_reasons.items():
                        report_lines.append(f"     - {reason}: {count}회")
            
            report_lines.append(f"\n📅 리포트 생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report_lines.append("=" * 60)
            
            return "\n".join(report_lines)
            
        except Exception as e:
            log_error("DEBUG_REPORT_ERROR", "Failed to generate debug report", e)
            return "디버그 리포트 생성 실패"


# 전역 디버거 인스턴스
api_debugger = APIDebugger()


def get_api_debugger() -> APIDebugger:
    """API 디버거 인스턴스 반환"""
    return api_debugger


# 데코레이터 함수
def debug_api_call(tr_code: str):
    """API 호출 디버깅 데코레이터"""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            debugger = get_api_debugger()
            
            # 더미 요청 객체 생성
            from utils.kis_api_standards import APIRequest
            dummy_request = APIRequest(tr_id=tr_code)
            call_id = debugger.start_api_call(tr_code, dummy_request, "")
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                response_time = (time.time() - start_time) * 1000
                
                debugger.end_api_call(
                    call_id=call_id,
                    response_status=200,
                    response_headers={},
                    response_body=result or {},
                    response_time_ms=response_time
                )
                
                return result
                
            except Exception as e:
                response_time = (time.time() - start_time) * 1000
                
                debugger.end_api_call(
                    call_id=call_id,
                    response_status=500,
                    response_headers={},
                    response_body={},
                    response_time_ms=response_time,
                    error_message=str(e)
                )
                
                raise
        
        return wrapper
    return decorator


# 실행 예시
if __name__ == "__main__":
    print("=== API 디버깅 시스템 테스트 ===")
    
    debugger = APIDebugger(LogLevel.DEBUG)
    
    # 성능 요약
    summary = debugger.get_performance_summary()
    print(f"총 호출 수: {summary.get('total_calls', 0)}")
    
    # 디버그 리포트 생성
    report = debugger.generate_debug_report()
    print(report)
    
    print("\nAPI 디버깅 시스템 테스트 완료!")