"""
고도화된 리스크 관리 시스템
- 비중 자동 조절형 고정금 (손실 누적 시 자동 축소)
- PnL 단위 당 손절 횟수 추적 및 전략별 성과 리밸런싱
- 동적 포지션 사이징 및 위험도 평가
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import threading
import math

from config.config import RISK_MANAGEMENT, SCALPING_CONFIG
from utils.logger import get_logger, log_error

logger = get_logger()


class RiskLevel(Enum):
    """리스크 레벨"""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    EXTREME = "extreme"


class StrategyType(Enum):
    """전략 타입"""
    PENNY_STOCK = "penny_stock"           # 페니스톡 전략
    LOW_PRICE = "low_price"              # 저가주 전략
    MID_PRICE = "mid_price"              # 중간가 전략
    HIGH_PRICE = "high_price"            # 고가주 전략
    EARNINGS_PLAY = "earnings_play"       # 실적 발표 전략
    NEWS_DRIVEN = "news_driven"          # 뉴스 기반 전략
    VOLUME_SURGE = "volume_surge"        # 거래량 급증 전략
    AI_SIGNAL = "ai_signal"              # AI 신호 전략


@dataclass
class RiskMetrics:
    """리스크 지표"""
    timestamp: datetime
    total_exposure: float              # 총 노출 금액
    position_count: int               # 포지션 수
    max_single_loss: float            # 최대 단일 손실
    max_daily_loss: float             # 최대 일일 손실
    drawdown_percentage: float        # 드로우다운 비율
    volatility_score: float           # 변동성 점수
    concentration_risk: float         # 집중 위험도
    leverage_ratio: float             # 레버리지 비율


@dataclass
class StrategyPerformance:
    """전략별 성과 지표"""
    strategy_type: StrategyType
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    total_volume: float = 0.0
    
    # 손절 분석
    stop_loss_count: int = 0           # 손절 횟수
    stop_loss_rate: float = 0.0        # 손절 비율
    avg_stop_loss: float = 0.0         # 평균 손절 금액
    
    # PnL 단위 분석
    pnl_per_dollar_risk: float = 0.0   # 리스크 달러당 PnL
    win_rate: float = 0.0              # 승률
    profit_factor: float = 0.0         # 수익 팩터
    sharpe_ratio: float = 0.0          # 샤프 비율
    
    # 자동 조절 지표
    allocation_multiplier: float = 1.0  # 할당 승수 (손실시 축소)
    performance_score: float = 50.0     # 성과 점수 (0-100)
    last_rebalance: datetime = field(default_factory=datetime.now)


@dataclass
class PositionSizing:
    """포지션 사이징 정보"""
    base_amount: float                 # 기본 금액
    risk_adjusted_amount: float        # 리스크 조정 금액
    strategy_multiplier: float         # 전략별 승수
    market_condition_multiplier: float # 시장 상황 승수
    final_amount: float               # 최종 포지션 크기


class EnhancedRiskManager:
    """고도화된 리스크 관리자"""
    
    def __init__(self):
        self.lock = threading.Lock()
        
        # 기본 설정
        self.base_position_size = SCALPING_CONFIG.get('max_position_size', 10000)
        self.max_daily_loss = RISK_MANAGEMENT.get('max_daily_loss', 1000)
        self.max_total_exposure = RISK_MANAGEMENT.get('max_total_exposure', 50000)
        
        # 동적 조절 설정
        self.min_allocation_multiplier = 0.2   # 최소 20%까지 축소
        self.max_allocation_multiplier = 2.0   # 최대 200%까지 확대
        self.rebalance_threshold = 0.05        # 5% 손실시 리밸런싱
        
        # 성과 추적
        self.strategy_performances: Dict[StrategyType, StrategyPerformance] = {}
        self.daily_pnl_history: List[float] = []
        self.risk_metrics_history: List[RiskMetrics] = []
        
        # 현재 상태
        self.current_total_exposure = 0.0
        self.current_drawdown = 0.0
        self.consecutive_losses = 0
        
        # 초기화
        self._initialize_strategy_performances()
        
        logger.info("Enhanced Risk Manager initialized with dynamic allocation")
    
    def _initialize_strategy_performances(self):
        """전략별 성과 초기화"""
        for strategy_type in StrategyType:
            self.strategy_performances[strategy_type] = StrategyPerformance(
                strategy_type=strategy_type
            )
    
    def calculate_position_size(self, symbol: str, market_data: Dict, 
                              strategy_type: StrategyType, ai_signal_strength: float) -> PositionSizing:
        """동적 포지션 사이징 계산"""
        try:
            with self.lock:
                # 1. 기본 포지션 크기
                base_amount = self.base_position_size
                
                # 2. 전략별 성과 기반 조정
                strategy_perf = self.strategy_performances[strategy_type]
                strategy_multiplier = strategy_perf.allocation_multiplier
                
                # 3. 시장 상황 기반 조정
                market_condition_multiplier = self._calculate_market_condition_multiplier(market_data)
                
                # 4. AI 신호 강도 기반 조정
                ai_multiplier = self._calculate_ai_signal_multiplier(ai_signal_strength)
                
                # 5. 현재 드로우다운 기반 조정
                drawdown_multiplier = self._calculate_drawdown_multiplier()
                
                # 6. 집중도 리스크 조정
                concentration_multiplier = self._calculate_concentration_multiplier(symbol)
                
                # 7. 최종 포지션 크기 계산
                risk_adjusted_amount = (
                    base_amount * 
                    strategy_multiplier * 
                    market_condition_multiplier * 
                    ai_multiplier * 
                    drawdown_multiplier * 
                    concentration_multiplier
                )
                
                # 8. 한도 체크
                final_amount = self._apply_position_limits(risk_adjusted_amount, market_data)
                
                sizing = PositionSizing(
                    base_amount=base_amount,
                    risk_adjusted_amount=risk_adjusted_amount,
                    strategy_multiplier=strategy_multiplier,
                    market_condition_multiplier=market_condition_multiplier,
                    final_amount=final_amount
                )
                
                logger.info(f"Position sizing for {symbol}: ${final_amount:.0f} "
                           f"(Strategy: {strategy_multiplier:.2f}x, Market: {market_condition_multiplier:.2f}x, "
                           f"AI: {ai_multiplier:.2f}x, DD: {drawdown_multiplier:.2f}x)")
                
                return sizing
                
        except Exception as e:
            log_error("POSITION_SIZING_ERROR", f"Failed to calculate position size for {symbol}", e)
            return PositionSizing(
                base_amount=self.base_position_size,
                risk_adjusted_amount=self.base_position_size * 0.5,
                strategy_multiplier=0.5,
                market_condition_multiplier=1.0,
                final_amount=self.base_position_size * 0.5
            )
    
    def _calculate_market_condition_multiplier(self, market_data: Dict) -> float:
        """시장 상황 기반 승수 계산"""
        try:
            multiplier = 1.0
            
            # 거래량 기반 조정
            volume_intensity = market_data.get('volume_intensity', 1.0)
            if volume_intensity > 3.0:      # 거래량 3배 이상
                multiplier *= 1.3
            elif volume_intensity > 2.0:    # 거래량 2배 이상
                multiplier *= 1.1
            elif volume_intensity < 0.5:    # 거래량 절반 이하
                multiplier *= 0.7
            
            # 변동성 기반 조정
            daily_change = abs(market_data.get('daily_change', 0))
            if daily_change > 15:           # 15% 이상 변동
                multiplier *= 0.6           # 고변동성 시 축소
            elif daily_change > 10:         # 10% 이상 변동
                multiplier *= 0.8
            elif daily_change > 5:          # 5% 이상 변동
                multiplier *= 0.9
            
            return max(0.2, min(2.0, multiplier))
            
        except Exception as e:
            log_error("MARKET_CONDITION_ERROR", "Failed to calculate market condition multiplier", e)
            return 1.0
    
    def _calculate_ai_signal_multiplier(self, ai_signal_strength: float) -> float:
        """AI 신호 강도 기반 승수"""
        try:
            if ai_signal_strength >= 90:
                return 1.5      # 매우 강한 신호
            elif ai_signal_strength >= 80:
                return 1.3      # 강한 신호
            elif ai_signal_strength >= 70:
                return 1.1      # 좋은 신호
            elif ai_signal_strength >= 60:
                return 1.0      # 보통 신호
            elif ai_signal_strength >= 50:
                return 0.8      # 약한 신호
            else:
                return 0.5      # 매우 약한 신호
                
        except Exception as e:
            log_error("AI_SIGNAL_MULTIPLIER_ERROR", "Failed to calculate AI signal multiplier", e)
            return 1.0
    
    def _calculate_drawdown_multiplier(self) -> float:
        """드로우다운 기반 승수"""
        try:
            if self.current_drawdown <= 0.02:      # 2% 이하
                return 1.2      # 상황 좋을 때 확대
            elif self.current_drawdown <= 0.05:    # 5% 이하
                return 1.0      # 정상
            elif self.current_drawdown <= 0.10:    # 10% 이하
                return 0.8      # 축소
            elif self.current_drawdown <= 0.15:    # 15% 이하
                return 0.6      # 대폭 축소
            else:
                return 0.3      # 최소한으로 축소
                
        except Exception as e:
            log_error("DRAWDOWN_MULTIPLIER_ERROR", "Failed to calculate drawdown multiplier", e)
            return 1.0
    
    def _calculate_concentration_multiplier(self, symbol: str) -> float:
        """집중도 리스크 기반 승수"""
        try:
            # 현재 총 노출 대비 집중도 계산
            if self.current_total_exposure == 0:
                return 1.0
            
            concentration_ratio = self.current_total_exposure / self.max_total_exposure
            
            if concentration_ratio >= 0.9:         # 90% 이상 집중
                return 0.3
            elif concentration_ratio >= 0.8:       # 80% 이상 집중
                return 0.5
            elif concentration_ratio >= 0.7:       # 70% 이상 집중
                return 0.7
            elif concentration_ratio >= 0.5:       # 50% 이상 집중
                return 0.9
            else:
                return 1.0      # 분산 잘 됨
                
        except Exception as e:
            log_error("CONCENTRATION_MULTIPLIER_ERROR", "Failed to calculate concentration multiplier", e)
            return 1.0
    
    def _apply_position_limits(self, amount: float, market_data: Dict) -> float:
        """포지션 한도 적용"""
        try:
            current_price = market_data.get('current_price', 0)
            
            # 최소/최대 금액 제한
            min_amount = 100    # 최소 $100
            max_amount = self.base_position_size * 2  # 최대 기본 크기의 2배
            
            amount = max(min_amount, min(amount, max_amount))
            
            # 총 노출 한도 체크
            if self.current_total_exposure + amount > self.max_total_exposure:
                remaining = self.max_total_exposure - self.current_total_exposure
                amount = max(0, remaining)
            
            return amount
            
        except Exception as e:
            log_error("POSITION_LIMITS_ERROR", "Failed to apply position limits", e)
            return min(amount, 1000)  # 안전한 기본값
    
    def record_trade_result(self, symbol: str, strategy_type: StrategyType, 
                          entry_price: float, exit_price: float, quantity: int,
                          entry_time: datetime, exit_time: datetime,
                          exit_reason: str) -> None:
        """거래 결과 기록 및 성과 업데이트"""
        try:
            with self.lock:
                # PnL 계산
                pnl = (exit_price - entry_price) * quantity
                trade_value = entry_price * quantity
                pnl_percentage = (pnl / trade_value) * 100 if trade_value > 0 else 0
                
                # 전략별 성과 업데이트
                perf = self.strategy_performances[strategy_type]
                perf.total_trades += 1
                perf.total_pnl += pnl
                perf.total_volume += trade_value
                
                # 승부 분류
                if pnl > 0:
                    perf.winning_trades += 1
                    self.consecutive_losses = 0
                else:
                    perf.losing_trades += 1
                    self.consecutive_losses += 1
                    
                    # 손절 여부 확인
                    if "STOP_LOSS" in exit_reason:
                        perf.stop_loss_count += 1
                        perf.avg_stop_loss = (
                            (perf.avg_stop_loss * (perf.stop_loss_count - 1) + abs(pnl)) / 
                            perf.stop_loss_count
                        )
                
                # 성과 지표 재계산
                self._recalculate_strategy_performance(strategy_type)
                
                # 일일 PnL 히스토리 업데이트
                self.daily_pnl_history.append(pnl)
                if len(self.daily_pnl_history) > 1000:  # 최근 1000건만 유지
                    self.daily_pnl_history = self.daily_pnl_history[-1000:]
                
                # 드로우다운 업데이트
                self._update_drawdown()
                
                # 자동 리밸런싱 확인
                if self._should_rebalance(strategy_type):
                    self._rebalance_strategy_allocation(strategy_type)
                
                logger.info(f"Trade recorded: {symbol} {strategy_type.value} "
                           f"P&L: ${pnl:+.2f} ({pnl_percentage:+.2f}%) "
                           f"Exit: {exit_reason}")
                
        except Exception as e:
            log_error("TRADE_RECORD_ERROR", f"Failed to record trade result for {symbol}", e)
    
    def _recalculate_strategy_performance(self, strategy_type: StrategyType):
        """전략별 성과 재계산"""
        try:
            perf = self.strategy_performances[strategy_type]
            
            if perf.total_trades > 0:
                # 기본 지표
                perf.win_rate = (perf.winning_trades / perf.total_trades) * 100
                perf.stop_loss_rate = (perf.stop_loss_count / perf.total_trades) * 100
                
                # PnL per dollar risk
                if perf.total_volume > 0:
                    perf.pnl_per_dollar_risk = perf.total_pnl / perf.total_volume
                
                # 수익 팩터 (총 이익 / 총 손실)
                total_wins = sum([pnl for pnl in self.daily_pnl_history if pnl > 0])
                total_losses = abs(sum([pnl for pnl in self.daily_pnl_history if pnl < 0]))
                
                if total_losses > 0:
                    perf.profit_factor = total_wins / total_losses
                else:
                    perf.profit_factor = float('inf') if total_wins > 0 else 0
                
                # 성과 점수 계산 (0-100)
                perf.performance_score = self._calculate_performance_score(perf)
                
        except Exception as e:
            log_error("PERFORMANCE_CALC_ERROR", f"Failed to recalculate performance for {strategy_type}", e)
    
    def _calculate_performance_score(self, perf: StrategyPerformance) -> float:
        """성과 점수 계산 (0-100)"""
        try:
            score = 50.0  # 기본점수
            
            # 승률 기여 (최대 20점)
            score += min(20, perf.win_rate * 0.4)
            
            # 수익성 기여 (최대 30점)
            if perf.pnl_per_dollar_risk > 0:
                score += min(30, perf.pnl_per_dollar_risk * 3000)
            else:
                score -= min(30, abs(perf.pnl_per_dollar_risk) * 3000)
            
            # 손절 관리 기여 (최대 20점)
            if perf.stop_loss_rate < 20:        # 손절 20% 미만
                score += 20
            elif perf.stop_loss_rate < 40:      # 손절 40% 미만
                score += 10
            elif perf.stop_loss_rate > 60:      # 손절 60% 이상
                score -= 20
            
            # 수익 팩터 기여 (최대 30점)
            if perf.profit_factor > 2.0:
                score += 30
            elif perf.profit_factor > 1.5:
                score += 20
            elif perf.profit_factor > 1.0:
                score += 10
            elif perf.profit_factor < 0.5:
                score -= 30
            
            return max(0, min(100, score))
            
        except Exception as e:
            log_error("PERFORMANCE_SCORE_ERROR", "Failed to calculate performance score", e)
            return 50.0
    
    def _should_rebalance(self, strategy_type: StrategyType) -> bool:
        """리밸런싱 필요 여부 확인"""
        try:
            perf = self.strategy_performances[strategy_type]
            
            # 최근 리밸런싱으로부터 시간 확인
            time_since_rebalance = datetime.now() - perf.last_rebalance
            if time_since_rebalance < timedelta(hours=1):  # 최소 1시간 간격
                return False
            
            # 성과 기준 리밸런싱
            if perf.performance_score < 20:  # 성과가 매우 나쁜 경우
                return True
            
            # 손실 기준 리밸런싱
            if perf.total_trades >= 10:  # 충분한 거래 수
                recent_pnl = sum(self.daily_pnl_history[-10:])  # 최근 10거래
                if recent_pnl < -self.rebalance_threshold * self.base_position_size:
                    return True
            
            # 연속 손실 기준
            if self.consecutive_losses >= 5:
                return True
            
            return False
            
        except Exception as e:
            log_error("REBALANCE_CHECK_ERROR", f"Failed to check rebalance for {strategy_type}", e)
            return False
    
    def _rebalance_strategy_allocation(self, strategy_type: StrategyType):
        """전략별 할당 리밸런싱"""
        try:
            perf = self.strategy_performances[strategy_type]
            old_multiplier = perf.allocation_multiplier
            
            # 성과 점수 기반 조정
            if perf.performance_score >= 80:
                new_multiplier = min(self.max_allocation_multiplier, old_multiplier * 1.2)
            elif perf.performance_score >= 60:
                new_multiplier = old_multiplier  # 유지
            elif perf.performance_score >= 40:
                new_multiplier = max(self.min_allocation_multiplier, old_multiplier * 0.8)
            elif perf.performance_score >= 20:
                new_multiplier = max(self.min_allocation_multiplier, old_multiplier * 0.6)
            else:
                new_multiplier = self.min_allocation_multiplier  # 최소값
            
            # 연속 손실 추가 조정
            if self.consecutive_losses >= 5:
                new_multiplier *= 0.5
            elif self.consecutive_losses >= 3:
                new_multiplier *= 0.8
            
            # 업데이트
            perf.allocation_multiplier = new_multiplier
            perf.last_rebalance = datetime.now()
            
            logger.info(f"Strategy {strategy_type.value} rebalanced: "
                       f"{old_multiplier:.2f}x → {new_multiplier:.2f}x "
                       f"(Score: {perf.performance_score:.1f})")
            
        except Exception as e:
            log_error("REBALANCE_ERROR", f"Failed to rebalance {strategy_type}", e)
    
    def _update_drawdown(self):
        """드로우다운 업데이트"""
        try:
            if len(self.daily_pnl_history) < 2:
                return
            
            # 최근 손익 기준으로 드로우다운 계산
            cumulative_pnl = sum(self.daily_pnl_history)
            peak_pnl = 0
            max_drawdown = 0
            
            running_pnl = 0
            running_peak = 0
            
            for pnl in self.daily_pnl_history:
                running_pnl += pnl
                running_peak = max(running_peak, running_pnl)
                
                if running_peak > 0:
                    current_drawdown = (running_peak - running_pnl) / running_peak
                    max_drawdown = max(max_drawdown, current_drawdown)
            
            self.current_drawdown = max_drawdown
            
        except Exception as e:
            log_error("DRAWDOWN_UPDATE_ERROR", "Failed to update drawdown", e)
    
    def get_risk_assessment(self) -> RiskLevel:
        """현재 리스크 레벨 평가"""
        try:
            risk_score = 0
            
            # 드로우다운 기여
            if self.current_drawdown > 0.20:        # 20% 이상
                risk_score += 3
            elif self.current_drawdown > 0.15:      # 15% 이상
                risk_score += 2
            elif self.current_drawdown > 0.10:      # 10% 이상
                risk_score += 1
            
            # 연속 손실 기여
            if self.consecutive_losses >= 7:
                risk_score += 3
            elif self.consecutive_losses >= 5:
                risk_score += 2
            elif self.consecutive_losses >= 3:
                risk_score += 1
            
            # 노출 집중도 기여
            concentration = self.current_total_exposure / self.max_total_exposure
            if concentration > 0.9:
                risk_score += 2
            elif concentration > 0.8:
                risk_score += 1
            
            # 리스크 레벨 분류
            if risk_score >= 7:
                return RiskLevel.EXTREME
            elif risk_score >= 5:
                return RiskLevel.VERY_HIGH
            elif risk_score >= 3:
                return RiskLevel.HIGH
            elif risk_score >= 1:
                return RiskLevel.MEDIUM
            else:
                return RiskLevel.LOW
                
        except Exception as e:
            log_error("RISK_ASSESSMENT_ERROR", "Failed to assess risk level", e)
            return RiskLevel.MEDIUM
    
    def get_strategy_rankings(self) -> List[Tuple[StrategyType, float]]:
        """전략별 성과 랭킹"""
        try:
            rankings = []
            
            for strategy_type, perf in self.strategy_performances.items():
                if perf.total_trades >= 5:  # 충분한 거래 수가 있는 전략만
                    rankings.append((strategy_type, perf.performance_score))
            
            # 성과 점수 기준 내림차순 정렬
            rankings.sort(key=lambda x: x[1], reverse=True)
            
            return rankings
            
        except Exception as e:
            log_error("STRATEGY_RANKING_ERROR", "Failed to get strategy rankings", e)
            return []
    
    def get_risk_report(self) -> Dict:
        """종합 리스크 리포트"""
        try:
            total_pnl = sum(self.daily_pnl_history)
            
            return {
                'risk_level': self.get_risk_assessment().value,
                'current_drawdown': self.current_drawdown * 100,
                'consecutive_losses': self.consecutive_losses,
                'total_exposure': self.current_total_exposure,
                'exposure_ratio': (self.current_total_exposure / self.max_total_exposure) * 100,
                'total_pnl': total_pnl,
                'strategy_count': len([p for p in self.strategy_performances.values() if p.total_trades > 0]),
                'best_strategy': self.get_strategy_rankings()[0] if self.get_strategy_rankings() else None,
                'allocation_multipliers': {
                    strategy.value: perf.allocation_multiplier 
                    for strategy, perf in self.strategy_performances.items()
                    if perf.total_trades > 0
                },
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            log_error("RISK_REPORT_ERROR", "Failed to generate risk report", e)
            return {}


# 전역 리스크 관리자 인스턴스
enhanced_risk_manager = EnhancedRiskManager()


def get_risk_manager() -> EnhancedRiskManager:
    """리스크 관리자 인스턴스 반환"""
    return enhanced_risk_manager


# 실행 예시
if __name__ == "__main__":
    print("=== 고도화된 리스크 관리 시스템 테스트 ===")
    
    rm = EnhancedRiskManager()
    
    # 리스크 평가 테스트
    risk_level = rm.get_risk_assessment()
    print(f"현재 리스크 레벨: {risk_level.value}")
    
    # 종합 리포트
    report = rm.get_risk_report()
    print(f"총 노출: ${report.get('total_exposure', 0):,.0f}")
    print(f"드로우다운: {report.get('current_drawdown', 0):.1f}%")
    print(f"연속 손실: {report.get('consecutive_losses', 0)}회")
    
    print("\n고도화된 리스크 관리 시스템 테스트 완료!")