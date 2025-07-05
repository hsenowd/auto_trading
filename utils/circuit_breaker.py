"""
고도화된 서킷 브레이커 시스템
- 시장 변동성 조건 트리거 (VIX 급등, 지정 뉴스 발생)
- Fail-safe 시나리오 로직 (네트워크 끊김, 거래 지연)
- 자동 포지션 일괄 청산 및 거래 중단
"""

import asyncio
import time
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import threading
import re

from config.config import RISK_MANAGEMENT
from utils.logger import get_logger, log_error
from utils.api_client import get_kis_client

logger = get_logger()


class CircuitBreakerType(Enum):
    """서킷 브레이커 타입"""
    VIX_SPIKE = "vix_spike"                 # VIX 급등
    MARKET_CRASH = "market_crash"           # 시장 급락
    NEWS_ALERT = "news_alert"               # 중요 뉴스 발생
    NETWORK_FAILURE = "network_failure"     # 네트워크 끊김
    API_DELAY = "api_delay"                 # API 지연
    SYSTEM_ERROR = "system_error"           # 시스템 오류
    MANUAL_TRIGGER = "manual_trigger"       # 수동 발동
    EXTREME_VOLATILITY = "extreme_volatility" # 극단적 변동성
    LIQUIDITY_CRISIS = "liquidity_crisis"   # 유동성 위기


@dataclass
class CircuitBreakerEvent:
    """서킷 브레이커 이벤트"""
    event_type: CircuitBreakerType
    timestamp: datetime
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    description: str
    trigger_value: float
    threshold_value: float
    auto_action: str  # ALERT, HALT_NEW, CLOSE_ALL, SHUTDOWN
    recovery_time: Optional[datetime] = None


@dataclass
class MarketCondition:
    """시장 상황 지표"""
    timestamp: datetime
    vix_level: float
    spy_change: float
    qqq_change: float
    volume_surge: float
    volatility_score: float
    sentiment_score: float


@dataclass
class SystemHealth:
    """시스템 헬스 체크"""
    timestamp: datetime
    api_response_time: float
    network_status: str
    last_successful_call: datetime
    error_count: int
    success_rate: float


class EnhancedCircuitBreaker:
    """고도화된 서킷 브레이커"""
    
    def __init__(self):
        self.kis_client = get_kis_client()
        self.lock = threading.Lock()
        
        # 서킷 브레이커 설정
        self.thresholds = {
            'vix_spike': 30.0,              # VIX 30 이상
            'vix_critical': 50.0,           # VIX 50 이상 (위험)
            'market_crash': -5.0,           # SPY 5% 이상 하락
            'extreme_volatility': 25.0,     # 25% 이상 변동
            'api_delay': 5.0,               # API 응답 5초 이상
            'network_timeout': 10.0,        # 네트워크 타임아웃 10초
            'error_rate': 0.3,              # 에러율 30% 이상
            'volume_surge': 5.0             # 거래량 5배 이상 급증
        }
        
        # 중요 뉴스 키워드 (자동 감지)
        self.critical_news_keywords = [
            'market crash', 'circuit breaker', 'trading halt',
            'federal reserve', 'interest rate', 'recession',
            'bankruptcy', 'default', 'crisis', 'emergency',
            'war', 'attack', 'pandemic', 'lockdown',
            'flash crash', 'margin call', 'liquidation',
            'bank failure', 'credit crisis', 'systemic risk'
        ]
        
        # 상태 관리
        self.is_active = False
        self.is_halted = False
        self.monitoring_thread = None
        self.last_vix_check = datetime.min
        self.recent_events: List[CircuitBreakerEvent] = []
        
        # 시스템 헬스
        self.system_health = SystemHealth(
            timestamp=datetime.now(),
            api_response_time=0.0,
            network_status="UNKNOWN",
            last_successful_call=datetime.now(),
            error_count=0,
            success_rate=1.0
        )
        
        # 콜백 함수들
        self.emergency_callbacks: List[Callable] = []
        
        logger.info("Enhanced Circuit Breaker initialized")
    
    def start_monitoring(self):
        """모니터링 시작"""
        try:
            if self.is_active:
                logger.warning("Circuit breaker monitoring already active")
                return
            
            self.is_active = True
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitoring_thread.start()
            
            logger.info("🚨 Circuit breaker monitoring started")
            
        except Exception as e:
            log_error("CB_START_ERROR", "Failed to start circuit breaker monitoring", e)
    
    def stop_monitoring(self):
        """모니터링 중지"""
        try:
            self.is_active = False
            if self.monitoring_thread:
                self.monitoring_thread.join(timeout=5)
            
            logger.info("🚨 Circuit breaker monitoring stopped")
            
        except Exception as e:
            log_error("CB_STOP_ERROR", "Failed to stop circuit breaker monitoring", e)
    
    def add_emergency_callback(self, callback: Callable):
        """긴급 상황 콜백 추가"""
        self.emergency_callbacks.append(callback)
    
    def _monitoring_loop(self):
        """모니터링 메인 루프"""
        try:
            logger.info("🔍 Circuit breaker monitoring loop started")
            
            while self.is_active:
                try:
                    # 1. 시장 변동성 체크
                    self._check_market_volatility()
                    
                    # 2. VIX 급등 체크
                    self._check_vix_spike()
                    
                    # 3. 뉴스 알림 체크
                    self._check_critical_news()
                    
                    # 4. 시스템 헬스 체크
                    self._check_system_health()
                    
                    # 5. API 응답 시간 체크
                    self._check_api_performance()
                    
                    # 6. 네트워크 상태 체크
                    self._check_network_status()
                    
                    # 7. 이벤트 정리 (오래된 이벤트 삭제)
                    self._cleanup_old_events()
                    
                    # 모니터링 주기 (10초)
                    time.sleep(10)
                    
                except Exception as e:
                    log_error("CB_MONITORING_ERROR", "Error in circuit breaker monitoring", e)
                    time.sleep(5)
            
            logger.info("🔍 Circuit breaker monitoring loop stopped")
            
        except Exception as e:
            log_error("CB_MONITORING_FATAL", "Fatal error in circuit breaker monitoring", e)
    
    def _check_market_volatility(self):
        """시장 변동성 체크"""
        try:
            # SPY, QQQ 급락 체크
            market_data = self._get_market_indices()
            
            if market_data:
                spy_change = market_data.get('spy_change', 0)
                qqq_change = market_data.get('qqq_change', 0)
                
                # 급락 체크
                if spy_change <= self.thresholds['market_crash']:
                    self._trigger_circuit_breaker(
                        CircuitBreakerType.MARKET_CRASH,
                        f"SPY crashed: {spy_change:.2f}%",
                        spy_change,
                        self.thresholds['market_crash'],
                        "CLOSE_ALL"
                    )
                
                # 극단적 변동성 체크
                volatility = max(abs(spy_change), abs(qqq_change))
                if volatility >= self.thresholds['extreme_volatility']:
                    self._trigger_circuit_breaker(
                        CircuitBreakerType.EXTREME_VOLATILITY,
                        f"Extreme volatility detected: {volatility:.2f}%",
                        volatility,
                        self.thresholds['extreme_volatility'],
                        "HALT_NEW"
                    )
                    
        except Exception as e:
            log_error("CB_MARKET_CHECK_ERROR", "Failed to check market volatility", e)
    
    def _check_vix_spike(self):
        """VIX 급등 체크"""
        try:
            # VIX 데이터는 실제로는 외부 API에서 가져와야 함
            # 여기서는 시뮬레이션
            current_time = datetime.now()
            
            # 1분에 한 번만 체크 (API 호출 제한)
            if (current_time - self.last_vix_check).total_seconds() < 60:
                return
            
            self.last_vix_check = current_time
            
            # VIX 데이터 조회 (시뮬레이션)
            vix_level = self._get_vix_level()
            
            if vix_level is not None:
                # VIX 경고 레벨
                if vix_level >= self.thresholds['vix_critical']:
                    self._trigger_circuit_breaker(
                        CircuitBreakerType.VIX_SPIKE,
                        f"VIX critical level: {vix_level:.2f}",
                        vix_level,
                        self.thresholds['vix_critical'],
                        "CLOSE_ALL"
                    )
                elif vix_level >= self.thresholds['vix_spike']:
                    self._trigger_circuit_breaker(
                        CircuitBreakerType.VIX_SPIKE,
                        f"VIX spike detected: {vix_level:.2f}",
                        vix_level,
                        self.thresholds['vix_spike'],
                        "HALT_NEW"
                    )
                    
        except Exception as e:
            log_error("CB_VIX_CHECK_ERROR", "Failed to check VIX spike", e)
    
    def _check_critical_news(self):
        """중요 뉴스 체크"""
        try:
            # 실제로는 뉴스 API (NewsAPI, Bloomberg, Reuters 등) 연결
            # 여기서는 기본 구조만 구현
            
            news_items = self._get_recent_news()
            
            for news in news_items:
                title = news.get('title', '').lower()
                content = news.get('content', '').lower()
                
                # 중요 키워드 검색
                for keyword in self.critical_news_keywords:
                    if keyword in title or keyword in content:
                        self._trigger_circuit_breaker(
                            CircuitBreakerType.NEWS_ALERT,
                            f"Critical news detected: {keyword} in {news.get('title', '')}",
                            1.0,
                            0.5,
                            "ALERT"
                        )
                        break
                        
        except Exception as e:
            log_error("CB_NEWS_CHECK_ERROR", "Failed to check critical news", e)
    
    def _check_system_health(self):
        """시스템 헬스 체크"""
        try:
            # API 성공률 체크
            if self.system_health.success_rate < (1.0 - self.thresholds['error_rate']):
                self._trigger_circuit_breaker(
                    CircuitBreakerType.SYSTEM_ERROR,
                    f"High error rate: {(1.0 - self.system_health.success_rate) * 100:.1f}%",
                    1.0 - self.system_health.success_rate,
                    self.thresholds['error_rate'],
                    "HALT_NEW"
                )
            
            # 최근 API 호출 성공 여부
            time_since_success = (datetime.now() - self.system_health.last_successful_call).total_seconds()
            if time_since_success > 300:  # 5분 이상 성공하지 못함
                self._trigger_circuit_breaker(
                    CircuitBreakerType.SYSTEM_ERROR,
                    f"No successful API calls for {time_since_success:.0f} seconds",
                    time_since_success,
                    300,
                    "CLOSE_ALL"
                )
                
        except Exception as e:
            log_error("CB_HEALTH_CHECK_ERROR", "Failed to check system health", e)
    
    def _check_api_performance(self):
        """API 성능 체크"""
        try:
            start_time = time.time()
            
            # 테스트 API 호출
            test_result = self.kis_client.get_overseas_stock_price("AAPL")
            
            response_time = time.time() - start_time
            self.system_health.api_response_time = response_time
            
            if test_result:
                self.system_health.last_successful_call = datetime.now()
                # 성공률 업데이트 (지수 이동 평균)
                self.system_health.success_rate = (
                    self.system_health.success_rate * 0.9 + 1.0 * 0.1
                )
            else:
                self.system_health.error_count += 1
                self.system_health.success_rate = (
                    self.system_health.success_rate * 0.9 + 0.0 * 0.1
                )
            
            # 응답 시간 체크
            if response_time >= self.thresholds['api_delay']:
                self._trigger_circuit_breaker(
                    CircuitBreakerType.API_DELAY,
                    f"API response delay: {response_time:.2f}s",
                    response_time,
                    self.thresholds['api_delay'],
                    "ALERT"
                )
                
        except Exception as e:
            self.system_health.error_count += 1
            self.system_health.success_rate = (
                self.system_health.success_rate * 0.9 + 0.0 * 0.1
            )
            log_error("CB_API_CHECK_ERROR", "Failed to check API performance", e)
    
    def _check_network_status(self):
        """네트워크 상태 체크"""
        try:
            start_time = time.time()
            
            # 인터넷 연결 테스트
            try:
                response = requests.get("https://www.google.com", timeout=5)
                network_time = time.time() - start_time
                
                if response.status_code == 200:
                    self.system_health.network_status = "GOOD"
                    
                    # 네트워크 지연 체크
                    if network_time >= self.thresholds['network_timeout']:
                        self._trigger_circuit_breaker(
                            CircuitBreakerType.NETWORK_FAILURE,
                            f"Network timeout: {network_time:.2f}s",
                            network_time,
                            self.thresholds['network_timeout'],
                            "ALERT"
                        )
                else:
                    self.system_health.network_status = "POOR"
                    
            except requests.exceptions.RequestException:
                self.system_health.network_status = "FAILED"
                self._trigger_circuit_breaker(
                    CircuitBreakerType.NETWORK_FAILURE,
                    "Network connection failed",
                    1.0,
                    0.5,
                    "HALT_NEW"
                )
                
        except Exception as e:
            log_error("CB_NETWORK_CHECK_ERROR", "Failed to check network status", e)
            self.system_health.network_status = "ERROR"
    
    def _get_market_indices(self) -> Optional[Dict]:
        """주요 지수 데이터 조회"""
        try:
            # 실제로는 SPY, QQQ 등의 실시간 데이터를 가져와야 함
            # 여기서는 시뮬레이션
            
            spy_data = self.kis_client.get_overseas_stock_price("SPY")
            qqq_data = self.kis_client.get_overseas_stock_price("QQQ")
            
            if spy_data and qqq_data:
                return {
                    'spy_change': spy_data.get('daily_change', 0),
                    'qqq_change': qqq_data.get('daily_change', 0),
                    'spy_volume': spy_data.get('volume', 0),
                    'qqq_volume': qqq_data.get('volume', 0)
                }
            
            return None
            
        except Exception as e:
            log_error("MARKET_INDICES_ERROR", "Failed to get market indices", e)
            return None
    
    def _get_vix_level(self) -> Optional[float]:
        """VIX 레벨 조회"""
        try:
            # 실제로는 VIX 데이터 API 사용
            # 여기서는 시뮬레이션 (평상시 15-25 범위)
            import random
            return random.uniform(15, 25)
            
        except Exception as e:
            log_error("VIX_LEVEL_ERROR", "Failed to get VIX level", e)
            return None
    
    def _get_recent_news(self) -> List[Dict]:
        """최근 뉴스 조회"""
        try:
            # 실제로는 뉴스 API 사용
            # 여기서는 시뮬레이션
            return [
                {
                    'title': 'Market Update: Stocks Continue Rally',
                    'content': 'Markets are showing positive momentum...',
                    'timestamp': datetime.now() - timedelta(minutes=30)
                }
            ]
            
        except Exception as e:
            log_error("NEWS_FETCH_ERROR", "Failed to get recent news", e)
            return []
    
    def _trigger_circuit_breaker(self, event_type: CircuitBreakerType, 
                                description: str, trigger_value: float,
                                threshold_value: float, auto_action: str):
        """서킷 브레이커 발동"""
        try:
            with self.lock:
                # 중복 이벤트 방지 (같은 타입의 이벤트가 최근 1분 내에 있으면 무시)
                recent_events = [
                    e for e in self.recent_events 
                    if e.event_type == event_type and 
                    (datetime.now() - e.timestamp).total_seconds() < 60
                ]
                
                if recent_events:
                    return  # 중복 이벤트 무시
                
                # 심각도 결정
                if auto_action == "CLOSE_ALL":
                    severity = "CRITICAL"
                elif auto_action == "HALT_NEW":
                    severity = "HIGH"
                elif auto_action == "ALERT":
                    severity = "MEDIUM"
                else:
                    severity = "LOW"
                
                # 이벤트 생성
                event = CircuitBreakerEvent(
                    event_type=event_type,
                    timestamp=datetime.now(),
                    severity=severity,
                    description=description,
                    trigger_value=trigger_value,
                    threshold_value=threshold_value,
                    auto_action=auto_action
                )
                
                self.recent_events.append(event)
                
                # 자동 액션 실행
                self._execute_auto_action(event)
                
                # 긴급 콜백 실행
                for callback in self.emergency_callbacks:
                    try:
                        callback(event)
                    except Exception as e:
                        log_error("CB_CALLBACK_ERROR", f"Error in emergency callback", e)
                
                logger.warning(f"🚨 CIRCUIT BREAKER TRIGGERED: {event_type.value} - {description}")
                
        except Exception as e:
            log_error("CB_TRIGGER_ERROR", f"Failed to trigger circuit breaker", e)
    
    def _execute_auto_action(self, event: CircuitBreakerEvent):
        """자동 액션 실행"""
        try:
            action = event.auto_action
            
            if action == "CLOSE_ALL":
                # 모든 포지션 즉시 청산
                self._emergency_close_all_positions(event)
                self.is_halted = True
                
            elif action == "HALT_NEW":
                # 신규 거래 중단
                self.is_halted = True
                logger.warning("🛑 New trading halted due to circuit breaker")
                
            elif action == "ALERT":
                # 알림만 전송
                logger.warning(f"⚠️ Circuit breaker alert: {event.description}")
                
        except Exception as e:
            log_error("CB_ACTION_ERROR", f"Failed to execute auto action {event.auto_action}", e)
    
    def _emergency_close_all_positions(self, event: CircuitBreakerEvent):
        """긴급 모든 포지션 청산"""
        try:
            # 이 함수는 실제로는 트레이더의 close_all_positions를 호출해야 함
            # 여기서는 구조만 보여줌
            
            logger.critical(f"🚨 EMERGENCY: Closing all positions due to {event.event_type.value}")
            
            # 실제 구현에서는:
            # trader = get_scalping_trader()
            # trader.close_all_positions(f"CIRCUIT_BREAKER_{event.event_type.value}")
            
        except Exception as e:
            log_error("CB_EMERGENCY_CLOSE_ERROR", "Failed to emergency close all positions", e)
    
    def _cleanup_old_events(self):
        """오래된 이벤트 정리"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=24)
            self.recent_events = [
                event for event in self.recent_events 
                if event.timestamp > cutoff_time
            ]
            
        except Exception as e:
            log_error("CB_CLEANUP_ERROR", "Failed to cleanup old events", e)
    
    def manual_trigger(self, reason: str = "Manual intervention"):
        """수동 서킷 브레이커 발동"""
        try:
            self._trigger_circuit_breaker(
                CircuitBreakerType.MANUAL_TRIGGER,
                f"Manual trigger: {reason}",
                1.0,
                0.5,
                "CLOSE_ALL"
            )
            
        except Exception as e:
            log_error("CB_MANUAL_TRIGGER_ERROR", "Failed to manually trigger circuit breaker", e)
    
    def reset_circuit_breaker(self):
        """서킷 브레이커 리셋"""
        try:
            with self.lock:
                self.is_halted = False
                logger.info("🔄 Circuit breaker reset - Trading resumed")
                
        except Exception as e:
            log_error("CB_RESET_ERROR", "Failed to reset circuit breaker", e)
    
    def get_status(self) -> Dict:
        """서킷 브레이커 상태 반환"""
        try:
            recent_critical = [
                e for e in self.recent_events 
                if e.severity in ["HIGH", "CRITICAL"] and 
                (datetime.now() - e.timestamp).total_seconds() < 3600  # 1시간 내
            ]
            
            return {
                'is_active': self.is_active,
                'is_halted': self.is_halted,
                'system_health': {
                    'api_response_time': self.system_health.api_response_time,
                    'network_status': self.system_health.network_status,
                    'success_rate': self.system_health.success_rate * 100,
                    'error_count': self.system_health.error_count
                },
                'recent_events_count': len(self.recent_events),
                'critical_events_count': len(recent_critical),
                'last_event': self.recent_events[-1].__dict__ if self.recent_events else None,
                'thresholds': self.thresholds,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            log_error("CB_STATUS_ERROR", "Failed to get circuit breaker status", e)
            return {}
    
    def get_recent_events(self, hours: int = 24) -> List[Dict]:
        """최근 이벤트 조회"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent = [
                event.__dict__ for event in self.recent_events 
                if event.timestamp > cutoff_time
            ]
            
            # 시간순 정렬 (최신순)
            recent.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return recent
            
        except Exception as e:
            log_error("CB_EVENTS_ERROR", "Failed to get recent events", e)
            return []


# 전역 서킷 브레이커 인스턴스
enhanced_circuit_breaker = EnhancedCircuitBreaker()


def get_circuit_breaker() -> EnhancedCircuitBreaker:
    """서킷 브레이커 인스턴스 반환"""
    return enhanced_circuit_breaker


# 실행 예시
if __name__ == "__main__":
    print("=== 고도화된 서킷 브레이커 시스템 테스트 ===")
    
    cb = EnhancedCircuitBreaker()
    
    # 서킷 브레이커 상태 확인
    status = cb.get_status()
    print(f"활성 상태: {status.get('is_active', False)}")
    print(f"거래 중단: {status.get('is_halted', False)}")
    print(f"시스템 헬스: {status.get('system_health', {})}")
    
    # 수동 발동 테스트
    print("\n수동 서킷 브레이커 테스트...")
    cb.manual_trigger("테스트 목적")
    
    print("\n고도화된 서킷 브레이커 시스템 테스트 완료!")