"""
강화된 스캘핑 트레이더 - Trailing Stop + 조건부 청산 + AI 신호 연동
초단타 스캘핑 전용 고도화된 자동매매 시스템
"""

import asyncio
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
import threading
# import numpy as np

from config.config import SCALPING_CONFIG, RISK_MANAGEMENT
from utils.logger import get_logger, log_error
from utils.api_client import get_kis_client
from utils.telegram_notifier import get_telegram_notifier
from screener.stock_screener import get_stock_screener
from analyzer.gpt_analyzer import get_market_analyzer

logger = get_logger()


class ExitTriggerType(Enum):
    """청산 트리거 타입"""
    TAKE_PROFIT = "take_profit"           # 익절
    STOP_LOSS = "stop_loss"              # 손절
    TRAILING_STOP = "trailing_stop"       # 트레일링 스탑
    TIME_BASED = "time_based"            # 시간 기반
    CANDLE_REVERSAL = "candle_reversal"   # 캔들 전환
    AI_SIGNAL_WEAK = "ai_signal_weak"     # AI 신호 약화
    VOLUME_DRY = "volume_dry"            # 거래량 고갈
    RISK_MANAGEMENT = "risk_management"   # 리스크 관리


@dataclass
class TrailingStopConfig:
    """트레일링 스탑 설정"""
    activation_profit: float = 0.003    # 0.3% 이익 시 활성화
    trail_distance: float = 0.002       # 0.2% 트레일링 거리
    step_size: float = 0.001            # 0.1% 단위로 업데이트
    max_trail_profit: float = 0.015     # 최대 1.5% 트레일링


@dataclass 
class CandlePattern:
    """캔들 패턴 분석"""
    timestamp: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: int
    pattern_type: str  # BULLISH, BEARISH, DOJI, HAMMER, etc.
    strength: float    # 0-100 패턴 강도


@dataclass
class EnhancedPosition:
    """강화된 포지션 정보"""
    symbol: str
    side: str  # BUY, SELL
    quantity: int
    entry_price: float
    entry_time: datetime
    current_price: float = 0.0
    
    # 기본 청산 조건
    target_profit: float = 0.005        # 0.5% 익절
    stop_loss: float = 0.003            # 0.3% 손절
    max_holding_time: int = 300         # 5분 최대 보유
    
    # AI 분석 결과
    ai_signal_strength: float = 50.0    # AI 신호 강도 (0-100)
    entry_reasoning: str = ""
    confidence_level: float = 50.0      # 신뢰도 (0-100)
    
    # 트레일링 스탑
    trailing_stop: Optional[TrailingStopConfig] = None
    trailing_stop_price: Optional[float] = None
    highest_profit: float = 0.0         # 최대 수익률
    
    # 실시간 모니터링
    last_update: datetime = field(default_factory=datetime.now)
    price_history: List[float] = field(default_factory=list)
    volume_history: List[int] = field(default_factory=list)
    
    # 청산 조건
    exit_triggers: List[ExitTriggerType] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.price_history:
            self.price_history = [self.entry_price]


class EnhancedScalpingTrader:
    """강화된 스캘핑 트레이더"""
    
    def __init__(self):
        self.kis_client = get_kis_client()
        self.telegram_notifier = get_telegram_notifier()
        self.stock_screener = get_stock_screener()
        self.market_analyzer = get_market_analyzer()
        
        # 포지션 관리
        self.active_positions: Dict[str, EnhancedPosition] = {}
        self.position_lock = threading.Lock()
        
        # 거래 상태
        self.is_trading = False
        self.trading_thread = None
        self.monitoring_thread = None
        
        # 성과 추적
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.win_count = 0
        self.loss_count = 0
        
        # 캔들 데이터 저장
        self.candle_data: Dict[str, List[CandlePattern]] = {}
        
        # AI 신호 강도 임계값
        self.ai_signal_thresholds = {
            'strong_buy': 80,    # 강한 매수 신호
            'buy': 60,          # 일반 매수 신호
            'weak_signal': 40,   # 약한 신호 (청산 고려)
            'exit_signal': 25    # 청산 신호
        }
        
        logger.info("Enhanced Scalping Trader initialized with trailing stops & AI integration")
    
    def start_trading(self) -> bool:
        """거래 시작"""
        try:
            if self.is_trading:
                logger.warning("Trading is already active")
                return False
            
            self.is_trading = True
            
            # 거래 스레드 시작
            self.trading_thread = threading.Thread(target=self._trading_loop, daemon=True)
            self.trading_thread.start()
            
            # 모니터링 스레드 시작
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitoring_thread.start()
            
            logger.info("✅ Enhanced scalping trading started")
            return True
            
        except Exception as e:
            log_error("TRADING_START_ERROR", "Failed to start enhanced trading", e)
            self.is_trading = False
            return False
    
    def stop_trading(self):
        """거래 중지"""
        try:
            logger.info("🛑 Stopping enhanced scalping trading...")
            self.is_trading = False
            
            # 모든 포지션 청산
            self.close_all_positions("TRADING_STOPPED")
            
            # 스레드 정리
            if self.trading_thread:
                self.trading_thread.join(timeout=5)
            if self.monitoring_thread:
                self.monitoring_thread.join(timeout=5)
            
            logger.info("✅ Enhanced scalping trading stopped")
            
        except Exception as e:
            log_error("TRADING_STOP_ERROR", "Failed to stop enhanced trading", e)
    
    def analyze_and_trade(self, symbol: str) -> bool:
        """종목 분석 및 거래 실행"""
        try:
            # 이미 포지션이 있는 경우 스킵
            if symbol in self.active_positions:
                return False
            
            # 최대 포지션 수 확인
            max_positions = SCALPING_CONFIG.get('max_positions', 5)
            if len(self.active_positions) >= max_positions:
                return False
            
            # 시장 데이터 수집
            market_data = self._collect_enhanced_market_data(symbol)
            if not market_data:
                return False
            
            # AI 분석 실행
            ai_analysis = self.market_analyzer.analyze_entry_signal(symbol, market_data)
            if not ai_analysis:
                return False
            
            # AI 신호 강도 확인
            ai_signal_strength = ai_analysis.get('ai_signal_strength', 50)
            confidence = ai_analysis.get('confidence', 50)
            signal_type = ai_analysis.get('signal', 'HOLD')
            
            # 매수 신호 확인
            if signal_type != 'BUY' or ai_signal_strength < self.ai_signal_thresholds['buy']:
                return False
            
            # 포지션 크기 계산 (AI 신호 강도 기반)
            position_size = self._calculate_dynamic_position_size(symbol, market_data, ai_signal_strength)
            if position_size <= 0:
                return False
            
            # 매수 주문 실행
            order_result = self.kis_client.place_overseas_order(
                symbol=symbol,
                side="BUY",
                qty=position_size,
                order_type="MARKET"
            )
            
            if not order_result or order_result.get('rt_cd') != '0':
                logger.error(f"❌ Failed to place buy order for {symbol}")
                return False
            
            # 포지션 생성
            current_price = market_data.get('current_price', 0)
            position = self._create_enhanced_position(
                symbol=symbol,
                quantity=position_size,
                entry_price=current_price,
                ai_analysis=ai_analysis,
                market_data=market_data
            )
            
            # 포지션 추가
            with self.position_lock:
                self.active_positions[symbol] = position
            
            # 성과 업데이트
            self.daily_trades += 1
            
            # 알림 전송
            self.telegram_notifier.send_trade_alert(
                symbol=symbol,
                action="BUY",
                price=current_price,
                quantity=position_size,
                signal_score=ai_signal_strength,
                reasoning=ai_analysis.get('reasoning', 'AI 매수 신호')
            )
            
            logger.info(f"✅ Enhanced position opened: {symbol} x{position_size} @ ${current_price:.3f} "
                       f"(AI: {ai_signal_strength:.1f})")
            
            return True
            
        except Exception as e:
            log_error("ANALYZE_TRADE_ERROR", f"Failed to analyze and trade {symbol}", e)
            return False
    
    def _collect_enhanced_market_data(self, symbol: str) -> Optional[Dict]:
        """강화된 시장 데이터 수집"""
        try:
            # 기본 가격 데이터
            price_data = self.kis_client.get_overseas_stock_price(symbol)
            if not price_data:
                return None
            
            # 스크리너 데이터 결합
            screening_data = self.stock_screener.analyze_stock_comprehensive(symbol)
            if not screening_data:
                screening_data = {}
            
            # 캔들 데이터 업데이트
            self._update_candle_data(symbol, price_data)
            
            # 통합 시장 데이터
            market_data = {
                **price_data,
                **screening_data,
                'timestamp': datetime.now().isoformat(),
                'candle_pattern': self._analyze_candle_pattern(symbol),
                'volume_trend': self._analyze_volume_trend(symbol),
                'price_momentum': self._calculate_price_momentum(symbol)
            }
            
            return market_data
            
        except Exception as e:
            log_error("ENHANCED_DATA_ERROR", f"Failed to collect enhanced data for {symbol}", e)
            return None
    
    def _create_enhanced_position(self, symbol: str, quantity: int, entry_price: float, 
                                ai_analysis: Dict, market_data: Dict) -> EnhancedPosition:
        """강화된 포지션 생성"""
        try:
            ai_signal_strength = ai_analysis.get('ai_signal_strength', 50)
            
            # AI 신호 강도 기반 청산 조건 조정
            if ai_signal_strength >= self.ai_signal_thresholds['strong_buy']:
                # 강한 신호 - 더 공격적인 목표
                target_profit = 0.008  # 0.8% 익절
                stop_loss = 0.004      # 0.4% 손절
                max_holding = 180      # 3분
            elif ai_signal_strength >= self.ai_signal_thresholds['buy']:
                # 일반 신호 - 기본 목표
                target_profit = 0.005  # 0.5% 익절
                stop_loss = 0.003      # 0.3% 손절
                max_holding = 300      # 5분
            else:
                # 약한 신호 - 보수적 목표
                target_profit = 0.003  # 0.3% 익절
                stop_loss = 0.002      # 0.2% 손절
                max_holding = 120      # 2분
            
            # 트레일링 스탑 설정 (강한 신호일 때만)
            trailing_stop = None
            if ai_signal_strength >= self.ai_signal_thresholds['strong_buy']:
                trailing_stop = TrailingStopConfig(
                    activation_profit=0.004,  # 0.4% 이익시 활성화
                    trail_distance=0.002,     # 0.2% 트레일링
                    step_size=0.001,          # 0.1% 단위
                    max_trail_profit=0.02     # 최대 2% 트레일링
                )
            
            # 청산 트리거 설정
            exit_triggers = [
                ExitTriggerType.TAKE_PROFIT,
                ExitTriggerType.STOP_LOSS,
                ExitTriggerType.TIME_BASED,
                ExitTriggerType.AI_SIGNAL_WEAK
            ]
            
            if trailing_stop:
                exit_triggers.append(ExitTriggerType.TRAILING_STOP)
            
            # 캔들 패턴 기반 청산 추가
            if ai_signal_strength >= 70:
                exit_triggers.append(ExitTriggerType.CANDLE_REVERSAL)
            
            # 포지션 객체 생성
            position = EnhancedPosition(
                symbol=symbol,
                side="BUY",
                quantity=quantity,
                entry_price=entry_price,
                entry_time=datetime.now(),
                current_price=entry_price,
                
                target_profit=target_profit,
                stop_loss=stop_loss,
                max_holding_time=max_holding,
                
                ai_signal_strength=ai_signal_strength,
                entry_reasoning=ai_analysis.get('reasoning', ''),
                confidence_level=ai_analysis.get('confidence', 50),
                
                trailing_stop=trailing_stop,
                exit_triggers=exit_triggers
            )
            
            return position
            
        except Exception as e:
            log_error("POSITION_CREATE_ERROR", f"Failed to create enhanced position for {symbol}", e)
            raise
    
    def _calculate_dynamic_position_size(self, symbol: str, market_data: Dict, ai_signal_strength: float) -> int:
        """AI 신호 강도 기반 동적 포지션 사이징"""
        try:
            current_price = market_data.get('current_price', 0)
            if current_price <= 0:
                return 0
            
            # 기본 포지션 크기
            base_position_value = SCALPING_CONFIG.get('max_position_size', 10000)
            
            # AI 신호 강도 기반 조정
            if ai_signal_strength >= self.ai_signal_thresholds['strong_buy']:
                position_multiplier = 1.5   # 강한 신호 - 150%
            elif ai_signal_strength >= self.ai_signal_thresholds['buy']:
                position_multiplier = 1.0   # 일반 신호 - 100%
            else:
                position_multiplier = 0.5   # 약한 신호 - 50%
            
            # 가격 범위별 조정
            if current_price < 0.1:         # 마이크로 페니스톡
                max_value = 1000
            elif current_price < 1.0:       # 페니스톡
                max_value = 3000
            elif current_price < 5.0:       # 저가주
                max_value = 6000
            elif current_price < 15.0:      # 중간가
                max_value = 8000
            else:                           # 고가주 ($15-30)
                max_value = 10000
            
            # 최종 포지션 크기 계산
            target_value = min(base_position_value, max_value) * position_multiplier
            quantity = int(target_value / current_price)
            
            # 최소/최대 수량 제한
            min_quantity = 100
            max_quantity = 50000
            
            quantity = max(min_quantity, min(quantity, max_quantity))
            
            # 리스크 체크
            total_exposure = sum(pos.quantity * pos.current_price for pos in self.active_positions.values())
            max_total_exposure = RISK_MANAGEMENT.get('max_total_exposure', 50000)
            
            if total_exposure + (quantity * current_price) > max_total_exposure:
                # 총 노출 한도 초과 시 포지션 크기 축소
                remaining_capacity = max_total_exposure - total_exposure
                quantity = max(0, int(remaining_capacity / current_price))
            
            return quantity
            
        except Exception as e:
            log_error("POSITION_SIZE_ERROR", f"Failed to calculate position size for {symbol}", e)
            return 0
    
    def _monitoring_loop(self):
        """실시간 포지션 모니터링 루프"""
        try:
            logger.info("🔍 Enhanced monitoring loop started")
            
            while self.is_trading:
                try:
                    if not self.active_positions:
                        time.sleep(1)
                        continue
                    
                    # 모든 포지션 업데이트
                    positions_to_close = []
                    
                    with self.position_lock:
                        for symbol, position in list(self.active_positions.items()):
                            try:
                                # 현재 가격 업데이트
                                market_data = self._collect_enhanced_market_data(symbol)
                                if not market_data:
                                    continue
                                
                                current_price = market_data.get('current_price', position.current_price)
                                position.current_price = current_price
                                position.last_update = datetime.now()
                                position.price_history.append(current_price)
                                
                                # 가격 히스토리 제한 (최근 100개)
                                if len(position.price_history) > 100:
                                    position.price_history = position.price_history[-100:]
                                
                                # 최대 수익률 업데이트
                                current_profit = self._calculate_profit_rate(position)
                                position.highest_profit = max(position.highest_profit, current_profit)
                                
                                # 청산 조건 확인
                                exit_reason = self._check_exit_conditions(position, market_data)
                                if exit_reason:
                                    positions_to_close.append((symbol, exit_reason))
                                
                            except Exception as e:
                                log_error("POSITION_UPDATE_ERROR", f"Error updating position {symbol}", e)
                    
                    # 청산 대상 포지션 처리
                    for symbol, exit_reason in positions_to_close:
                        self._close_position(symbol, exit_reason)
                    
                    # 모니터링 주기
                    time.sleep(0.5)  # 0.5초마다 체크
                    
                except Exception as e:
                    log_error("MONITORING_LOOP_ERROR", "Error in monitoring loop", e)
                    time.sleep(1)
            
            logger.info("🔍 Enhanced monitoring loop stopped")
            
        except Exception as e:
            log_error("MONITORING_LOOP_FATAL", "Fatal error in monitoring loop", e)
    
    def _check_exit_conditions(self, position: EnhancedPosition, market_data: Dict) -> Optional[str]:
        """종합 청산 조건 확인"""
        try:
            current_profit = self._calculate_profit_rate(position)
            holding_time = (datetime.now() - position.entry_time).total_seconds()
            
            # 1. 익절 조건
            if ExitTriggerType.TAKE_PROFIT in position.exit_triggers:
                if current_profit >= position.target_profit:
                    return f"TAKE_PROFIT_{current_profit*100:.2f}%"
            
            # 2. 손절 조건
            if ExitTriggerType.STOP_LOSS in position.exit_triggers:
                if current_profit <= -position.stop_loss:
                    return f"STOP_LOSS_{current_profit*100:.2f}%"
            
            # 3. 트레일링 스탑 조건
            if ExitTriggerType.TRAILING_STOP in position.exit_triggers and position.trailing_stop:
                trailing_exit = self._check_trailing_stop(position)
                if trailing_exit:
                    return trailing_exit
            
            # 4. 시간 기반 청산
            if ExitTriggerType.TIME_BASED in position.exit_triggers:
                if holding_time >= position.max_holding_time:
                    return f"TIME_LIMIT_{holding_time/60:.1f}min"
            
            # 5. AI 신호 약화 청산
            if ExitTriggerType.AI_SIGNAL_WEAK in position.exit_triggers:
                ai_exit = self._check_ai_signal_weakness(position, market_data)
                if ai_exit:
                    return ai_exit
            
            # 6. 캔들 전환 청산
            if ExitTriggerType.CANDLE_REVERSAL in position.exit_triggers:
                candle_exit = self._check_candle_reversal(position, market_data)
                if candle_exit:
                    return candle_exit
            
            # 7. 거래량 고갈 청산
            if ExitTriggerType.VOLUME_DRY in position.exit_triggers:
                volume_exit = self._check_volume_drying(position, market_data)
                if volume_exit:
                    return volume_exit
            
            return None
            
        except Exception as e:
            log_error("EXIT_CONDITIONS_ERROR", f"Error checking exit conditions for {position.symbol}", e)
            return "ERROR_CHECK"
    
    def _check_trailing_stop(self, position: EnhancedPosition) -> Optional[str]:
        """트레일링 스탑 확인"""
        try:
            if not position.trailing_stop:
                return None
            
            current_profit = self._calculate_profit_rate(position)
            trailing_config = position.trailing_stop
            
            # 트레일링 스탑 활성화 조건
            if current_profit >= trailing_config.activation_profit:
                
                # 트레일링 스탑 가격 업데이트
                if position.trailing_stop_price is None:
                    # 첫 번째 활성화
                    position.trailing_stop_price = position.current_price * (1 - trailing_config.trail_distance)
                    logger.info(f"🎯 Trailing stop activated for {position.symbol} @ ${position.trailing_stop_price:.3f}")
                
                else:
                    # 트레일링 스탑 가격 업데이트 (이익 방향으로만)
                    new_trailing_price = position.current_price * (1 - trailing_config.trail_distance)
                    
                    if new_trailing_price > position.trailing_stop_price:
                        # 가격이 단계적으로 상승했을 때만 업데이트
                        price_increase = (new_trailing_price - position.trailing_stop_price) / position.trailing_stop_price
                        
                        if price_increase >= trailing_config.step_size:
                            position.trailing_stop_price = new_trailing_price
                            logger.info(f"📈 Trailing stop updated for {position.symbol} @ ${position.trailing_stop_price:.3f}")
                
                # 트레일링 스탑 청산 조건 확인
                if position.current_price <= position.trailing_stop_price:
                    return f"TRAILING_STOP_{current_profit*100:.2f}%"
            
            return None
            
        except Exception as e:
            log_error("TRAILING_STOP_ERROR", f"Error checking trailing stop for {position.symbol}", e)
            return None
    
    def _check_ai_signal_weakness(self, position: EnhancedPosition, market_data: Dict) -> Optional[str]:
        """AI 신호 약화 확인"""
        try:
            # 현재 AI 신호 재분석
            current_analysis = self.market_analyzer.analyze_entry_signal(position.symbol, market_data)
            if not current_analysis:
                return None
            
            current_ai_strength = current_analysis.get('ai_signal_strength', 50)
            original_strength = position.ai_signal_strength
            
            # 신호 강도 크게 약화 시 청산
            strength_decline = original_strength - current_ai_strength
            
            if strength_decline >= 30:  # 30포인트 이상 하락
                return f"AI_SIGNAL_WEAK_{current_ai_strength:.1f}"
            
            # 신호가 청산 임계값 이하로 떨어진 경우
            if current_ai_strength <= self.ai_signal_thresholds['exit_signal']:
                return f"AI_EXIT_SIGNAL_{current_ai_strength:.1f}"
            
            return None
            
        except Exception as e:
            log_error("AI_SIGNAL_CHECK_ERROR", f"Error checking AI signal for {position.symbol}", e)
            return None
    
    def _check_candle_reversal(self, position: EnhancedPosition, market_data: Dict) -> Optional[str]:
        """캔들 전환 패턴 확인"""
        try:
            # 최근 캔들 패턴 분석
            current_pattern = market_data.get('candle_pattern', {})
            if not current_pattern:
                return None
            
            pattern_type = current_pattern.get('pattern_type', 'NEUTRAL')
            pattern_strength = current_pattern.get('strength', 0)
            
            # 매수 포지션인 경우 약세 전환 확인
            if position.side == "BUY":
                if pattern_type in ['BEARISH', 'DOJI', 'SHOOTING_STAR'] and pattern_strength >= 70:
                    return f"CANDLE_REVERSAL_{pattern_type}"
            
            # 매도 포지션인 경우 강세 전환 확인 (향후 공매도 지원 시)
            elif position.side == "SELL":
                if pattern_type in ['BULLISH', 'HAMMER', 'MORNING_STAR'] and pattern_strength >= 70:
                    return f"CANDLE_REVERSAL_{pattern_type}"
            
            return None
            
        except Exception as e:
            log_error("CANDLE_REVERSAL_ERROR", f"Error checking candle reversal for {position.symbol}", e)
            return None
    
    def _check_volume_drying(self, position: EnhancedPosition, market_data: Dict) -> Optional[str]:
        """거래량 고갈 확인"""
        try:
            current_volume = market_data.get('volume_1m', 0)
            avg_volume = market_data.get('avg_volume_20d', 0)
            
            if avg_volume <= 0:
                return None
            
            volume_ratio = current_volume / (avg_volume / 1440)  # 1분 평균으로 환산
            
            # 거래량이 평소의 20% 이하로 떨어진 경우
            if volume_ratio < 0.2:
                return f"VOLUME_DRY_{volume_ratio:.2f}"
            
            return None
            
        except Exception as e:
            log_error("VOLUME_DRY_ERROR", f"Error checking volume for {position.symbol}", e)
            return None
    
    def _close_position(self, symbol: str, exit_reason: str):
        """포지션 청산"""
        try:
            with self.position_lock:
                if symbol not in self.active_positions:
                    return
                
                position = self.active_positions[symbol]
            
            # 매도 주문 실행
            order_result = self.kis_client.place_overseas_order(
                symbol=symbol,
                side="SELL",
                qty=position.quantity,
                order_type="MARKET"
            )
            
            if not order_result or order_result.get('rt_cd') != '0':
                logger.error(f"❌ Failed to close position {symbol}")
                return
            
            # 수익률 계산
            profit_rate = self._calculate_profit_rate(position)
            profit_amount = profit_rate * position.quantity * position.entry_price
            
            # 통계 업데이트
            self.daily_pnl += profit_amount
            self.total_pnl += profit_amount
            
            if profit_amount > 0:
                self.win_count += 1
            else:
                self.loss_count += 1
            
            # 포지션 제거
            with self.position_lock:
                del self.active_positions[symbol]
            
            # 알림 전송
            self.telegram_notifier.send_trade_alert(
                symbol=symbol,
                action="SELL",
                price=position.current_price,
                quantity=position.quantity,
                signal_score=position.ai_signal_strength,
                reasoning=f"{exit_reason} | P&L: ${profit_amount:+.2f} ({profit_rate*100:+.2f}%)"
            )
            
            logger.info(f"✅ Position closed: {symbol} | {exit_reason} | "
                       f"P&L: ${profit_amount:+.2f} ({profit_rate*100:+.2f}%)")
            
        except Exception as e:
            log_error("CLOSE_POSITION_ERROR", f"Failed to close position {symbol}", e)
    
    def _calculate_profit_rate(self, position: EnhancedPosition) -> float:
        """수익률 계산"""
        try:
            if position.entry_price <= 0:
                return 0.0
            
            if position.side == "BUY":
                return (position.current_price - position.entry_price) / position.entry_price
            else:  # SELL (공매도)
                return (position.entry_price - position.current_price) / position.entry_price
            
        except Exception as e:
            log_error("PROFIT_CALC_ERROR", f"Error calculating profit for {position.symbol}", e)
            return 0.0
    
    def _trading_loop(self):
        """거래 메인 루프"""
        try:
            logger.info("🎯 Enhanced trading loop started")
            
            while self.is_trading:
                try:
                    # 스크리닝 및 거래 기회 탐색
                    top_stocks = self.stock_screener.get_enhanced_top_stocks(10)
                    
                    for stock in top_stocks[:3]:  # 상위 3개만 시도
                        if not self.is_trading:
                            break
                        
                        symbol = stock['symbol']
                        
                        # 거래 시도
                        if self.analyze_and_trade(symbol):
                            logger.info(f"✅ New enhanced position: {symbol}")
                            time.sleep(2)  # 주문 간 간격
                    
                    # 대기 시간
                    time.sleep(30)  # 30초마다 스크리닝
                    
                except Exception as e:
                    log_error("TRADING_LOOP_ERROR", "Error in enhanced trading loop", e)
                    time.sleep(10)
            
            logger.info("🎯 Enhanced trading loop stopped")
            
        except Exception as e:
            log_error("TRADING_LOOP_FATAL", "Fatal error in enhanced trading loop", e)
    
    def close_all_positions(self, reason: str = "MANUAL"):
        """모든 포지션 청산"""
        try:
            with self.position_lock:
                symbols_to_close = list(self.active_positions.keys())
            
            for symbol in symbols_to_close:
                self._close_position(symbol, f"CLOSE_ALL_{reason}")
                time.sleep(0.5)  # 주문 간 간격
            
            logger.info(f"✅ All enhanced positions closed: {reason}")
            
        except Exception as e:
            log_error("CLOSE_ALL_ERROR", "Failed to close all enhanced positions", e)
    
    def get_portfolio_status(self) -> Dict:
        """포트폴리오 상태 반환"""
        try:
            with self.position_lock:
                positions = list(self.active_positions.values())
            
            total_value = 0
            unrealized_pnl = 0
            
            for position in positions:
                position_value = position.quantity * position.current_price
                total_value += position_value
                
                profit_rate = self._calculate_profit_rate(position)
                position_pnl = profit_rate * position.quantity * position.entry_price
                unrealized_pnl += position_pnl
            
            win_rate = 0
            if self.win_count + self.loss_count > 0:
                win_rate = (self.win_count / (self.win_count + self.loss_count)) * 100
            
            return {
                'is_trading': self.is_trading,
                'active_positions': len(positions),
                'total_value': total_value,
                'daily_pnl': self.daily_pnl,
                'total_pnl': self.total_pnl,
                'unrealized_pnl': unrealized_pnl,
                'daily_trades': self.daily_trades,
                'win_count': self.win_count,
                'loss_count': self.loss_count,
                'win_rate': win_rate,
                'positions': [
                    {
                        'symbol': pos.symbol,
                        'quantity': pos.quantity,
                        'entry_price': pos.entry_price,
                        'current_price': pos.current_price,
                        'profit_rate': self._calculate_profit_rate(pos) * 100,
                        'ai_signal_strength': pos.ai_signal_strength,
                        'holding_time': (datetime.now() - pos.entry_time).total_seconds() / 60,
                        'trailing_stop_active': pos.trailing_stop_price is not None,
                        'exit_triggers': [trigger.value for trigger in pos.exit_triggers]
                    }
                    for pos in positions
                ]
            }
            
        except Exception as e:
            log_error("PORTFOLIO_STATUS_ERROR", "Failed to get enhanced portfolio status", e)
            return {}
    
    def get_position_summary(self) -> List[Dict]:
        """포지션 요약 반환"""
        try:
            with self.position_lock:
                positions = list(self.active_positions.values())
            
            return [
                {
                    'symbol': pos.symbol,
                    'side': pos.side,
                    'quantity': pos.quantity,
                    'entry_price': pos.entry_price,
                    'current_price': pos.current_price,
                    'profit_loss': self._calculate_profit_rate(pos) * 100,
                    'ai_strength': pos.ai_signal_strength,
                    'confidence': pos.confidence_level,
                    'holding_minutes': (datetime.now() - pos.entry_time).total_seconds() / 60,
                    'trailing_stop': pos.trailing_stop_price,
                    'max_profit': pos.highest_profit * 100
                }
                for pos in positions
            ]
            
        except Exception as e:
            log_error("POSITION_SUMMARY_ERROR", "Failed to get position summary", e)
            return []
    
    # 캔들 패턴 분석 헬퍼 메서드들
    def _update_candle_data(self, symbol: str, price_data: Dict):
        """캔들 데이터 업데이트"""
        try:
            if symbol not in self.candle_data:
                self.candle_data[symbol] = []
            
            current_time = datetime.now()
            current_price = price_data.get('current_price', 0)
            volume = price_data.get('volume', 0)
            
            # 1분 캔들로 가정 (실제로는 더 정교한 로직 필요)
            candle = CandlePattern(
                timestamp=current_time,
                open_price=current_price,  # 단순화
                high_price=current_price,
                low_price=current_price,
                close_price=current_price,
                volume=volume,
                pattern_type="NEUTRAL",
                strength=50.0
            )
            
            self.candle_data[symbol].append(candle)
            
            # 데이터 제한 (최근 100개)
            if len(self.candle_data[symbol]) > 100:
                self.candle_data[symbol] = self.candle_data[symbol][-100:]
                
        except Exception as e:
            log_error("CANDLE_UPDATE_ERROR", f"Error updating candle data for {symbol}", e)
    
    def _analyze_candle_pattern(self, symbol: str) -> Dict:
        """캔들 패턴 분석"""
        try:
            if symbol not in self.candle_data or len(self.candle_data[symbol]) < 3:
                return {'pattern_type': 'NEUTRAL', 'strength': 50.0}
            
            recent_candles = self.candle_data[symbol][-3:]
            
            # 간단한 패턴 인식 (실제로는 더 복잡한 로직 필요)
            last_candle = recent_candles[-1]
            
            # 도지 패턴 (시가 = 종가)
            if abs(last_candle.close_price - last_candle.open_price) / last_candle.open_price < 0.001:
                return {'pattern_type': 'DOJI', 'strength': 75.0}
            
            # 강세/약세 판단
            if last_candle.close_price > last_candle.open_price:
                return {'pattern_type': 'BULLISH', 'strength': 60.0}
            else:
                return {'pattern_type': 'BEARISH', 'strength': 60.0}
                
        except Exception as e:
            log_error("CANDLE_PATTERN_ERROR", f"Error analyzing candle pattern for {symbol}", e)
            return {'pattern_type': 'NEUTRAL', 'strength': 50.0}
    
    def _analyze_volume_trend(self, symbol: str) -> Dict:
        """거래량 트렌드 분석"""
        try:
            if symbol not in self.candle_data or len(self.candle_data[symbol]) < 5:
                return {'trend': 'NEUTRAL', 'strength': 50.0}
            
            recent_volumes = [candle.volume for candle in self.candle_data[symbol][-5:]]
            
            # 거래량 증가/감소 트렌드
            if len(recent_volumes) >= 2:
                recent_avg = sum(recent_volumes[-2:]) / len(recent_volumes[-2:])
                earlier_avg = sum(recent_volumes[:-2]) / len(recent_volumes[:-2])
                
                if recent_avg > earlier_avg * 1.2:
                    return {'trend': 'INCREASING', 'strength': 70.0}
                elif recent_avg < earlier_avg * 0.8:
                    return {'trend': 'DECREASING', 'strength': 70.0}
            
            return {'trend': 'NEUTRAL', 'strength': 50.0}
            
        except Exception as e:
            log_error("VOLUME_TREND_ERROR", f"Error analyzing volume trend for {symbol}", e)
            return {'trend': 'NEUTRAL', 'strength': 50.0}
    
    def _calculate_price_momentum(self, symbol: str) -> Dict:
        """가격 모멘텀 계산"""
        try:
            if symbol not in self.candle_data or len(self.candle_data[symbol]) < 5:
                return {'momentum': 0.0, 'direction': 'NEUTRAL'}
            
            recent_prices = [candle.close_price for candle in self.candle_data[symbol][-5:]]
            
            if len(recent_prices) >= 2:
                price_change = (recent_prices[-1] - recent_prices[0]) / recent_prices[0]
                
                if price_change > 0.01:  # 1% 이상 상승
                    return {'momentum': price_change, 'direction': 'UP'}
                elif price_change < -0.01:  # 1% 이상 하락
                    return {'momentum': price_change, 'direction': 'DOWN'}
            
            return {'momentum': 0.0, 'direction': 'NEUTRAL'}
            
        except Exception as e:
            log_error("MOMENTUM_CALC_ERROR", f"Error calculating momentum for {symbol}", e)
            return {'momentum': 0.0, 'direction': 'NEUTRAL'}


# 전역 트레이더 인스턴스
enhanced_scalping_trader = EnhancedScalpingTrader()


def get_scalping_trader() -> EnhancedScalpingTrader:
    """스캘핑 트레이더 인스턴스 반환"""
    return enhanced_scalping_trader


# 실행 예시
if __name__ == "__main__":
    print("=== 강화된 스캘핑 트레이더 테스트 ===")
    
    trader = EnhancedScalpingTrader()
    
    # 포트폴리오 상태 확인
    status = trader.get_portfolio_status()
    print(f"거래 활성: {status.get('is_trading', False)}")
    print(f"활성 포지션: {status.get('active_positions', 0)}")
    print(f"일일 P&L: ${status.get('daily_pnl', 0):.2f}")
    print(f"승률: {status.get('win_rate', 0):.1f}%")
    
    print("\n강화된 스캘핑 트레이더 테스트 완료!")