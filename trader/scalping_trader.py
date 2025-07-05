"""
스캘핑 트레이더 모듈
GPT 분석 기반 자동 매수/매도 주문 실행 및 리스크 관리
"""

import time
import threading
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json

from config.config import SCALPING_CONFIG, RISK_MANAGEMENT
from utils.logger import get_logger, log_trade, log_error, log_performance
from utils.api_client import get_alpaca_client
from analyzer.gpt_analyzer import get_market_analyzer
from screener.stock_screener import get_stock_screener

logger = get_logger()


class OrderStatus(Enum):
    """주문 상태 열거형"""
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Position:
    """포지션 정보 클래스"""
    symbol: str
    entry_price: float
    quantity: int
    entry_time: datetime
    target_price: float
    stop_loss_price: float
    order_id: str
    status: str = "active"
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    profit_loss: float = 0.0
    
    def to_dict(self) -> Dict:
        """딕셔너리 변환"""
        return {
            'symbol': self.symbol,
            'entry_price': self.entry_price,
            'quantity': self.quantity,
            'entry_time': self.entry_time.isoformat(),
            'target_price': self.target_price,
            'stop_loss_price': self.stop_loss_price,
            'order_id': self.order_id,
            'status': self.status,
            'exit_price': self.exit_price,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'profit_loss': self.profit_loss
        }


class ScalpingTrader:
    """스캘핑 트레이더 클래스"""
    
    def __init__(self):
        self.alpaca_client = get_alpaca_client()
        self.market_analyzer = get_market_analyzer()
        self.stock_screener = get_stock_screener()
        
        # 거래 설정
        self.config = SCALPING_CONFIG
        self.risk_config = RISK_MANAGEMENT
        
        # 활성 포지션 관리
        self.active_positions: Dict[str, Position] = {}
        self.closed_positions: List[Position] = []
        
        # 일일 거래 통계
        self.daily_stats = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_profit_loss": 0.0,
            "start_time": datetime.now(),
            "max_drawdown": 0.0,
            "current_drawdown": 0.0
        }
        
        # 거래 실행 제어
        self.trading_enabled = False
        self.circuit_breaker_triggered = False
        
        # 스레드 관리
        self.monitoring_thread = None
        self.stop_monitoring = False
        
        logger.info("ScalpingTrader initialized")
    
    def start_trading(self):
        """거래 시작"""
        try:
            # 사전 검사
            if not self.pre_trading_checks():
                logger.error("Pre-trading checks failed")
                return False
            
            self.trading_enabled = True
            self.circuit_breaker_triggered = False
            
            # 포지션 모니터링 스레드 시작
            self.start_position_monitoring()
            
            logger.info("Trading started")
            return True
            
        except Exception as e:
            log_error("TRADING_START_ERROR", "Failed to start trading", e)
            return False
    
    def stop_trading(self):
        """거래 중지"""
        try:
            self.trading_enabled = False
            self.stop_monitoring = True
            
            # 모든 열린 포지션 청산
            self.close_all_positions("TRADING_STOPPED")
            
            logger.info("Trading stopped")
            
        except Exception as e:
            log_error("TRADING_STOP_ERROR", "Failed to stop trading", e)
    
    def pre_trading_checks(self) -> bool:
        """거래 전 사전 검사"""
        try:
            # 시장 오픈 여부 확인
            if not self.alpaca_client.is_market_open():
                logger.warning("Market is closed")
                return False
            
            # 계좌 상태 확인
            account = self.alpaca_client.get_account()
            if not account:
                logger.error("Failed to get account info")
                return False
            
            # 구매력 확인
            buying_power = float(account.get('buying_power', 0))
            if buying_power < self.config['max_position_size']:
                logger.warning(f"Insufficient buying power: ${buying_power}")
                return False
            
            logger.info("Pre-trading checks passed")
            return True
            
        except Exception as e:
            log_error("PRE_TRADING_CHECK_ERROR", "Pre-trading checks failed", e)
            return False
    
    def analyze_and_trade(self, symbol: str) -> bool:
        """분석 후 거래 실행"""
        try:
            # 거래 활성화 여부 확인
            if not self.trading_enabled or self.circuit_breaker_triggered:
                return False
            
            # 이미 포지션이 있는지 확인
            if symbol in self.active_positions:
                logger.info(f"Already have position in {symbol}")
                return False
            
            # 최대 포지션 수 확인
            if len(self.active_positions) >= self.config['max_positions']:
                logger.info("Maximum positions reached")
                return False
            
            # GPT 분석 실행
            analysis = self.market_analyzer.analyze_entry_signal(symbol)
            
            # 매수 시그널 확인
            if analysis.get("action") == "BUY" and analysis.get("signal_score", 0) >= 7:
                return self.execute_buy_order(symbol, analysis)
            
            return False
            
        except Exception as e:
            log_error("ANALYZE_AND_TRADE_ERROR", f"Failed to analyze and trade {symbol}", e)
            return False
    
    def execute_buy_order(self, symbol: str, analysis: Dict) -> bool:
        """매수 주문 실행"""
        try:
            # 시장 데이터 수집
            market_data = self.market_analyzer.collect_market_data(symbol)
            if not market_data:
                logger.error(f"Failed to get market data for {symbol}")
                return False
            
            current_price = market_data.get('current_price', 0)
            if current_price <= 0:
                logger.error(f"Invalid price for {symbol}: ${current_price}")
                return False
            
            # 포지션 크기 계산
            position_size = self.calculate_position_size(current_price)
            if position_size <= 0:
                logger.warning(f"Invalid position size for {symbol}")
                return False
            
            # 목표가 및 손절가 계산
            target_price = current_price * (1 + self.config['profit_target'])
            stop_loss_price = current_price * (1 - self.config['stop_loss'])
            
            # 주문 실행
            order = self.alpaca_client.place_order(
                symbol=symbol,
                qty=position_size,
                side="buy",
                type="market",
                time_in_force="gtc"
            )
            
            if order:
                # 포지션 생성
                position = Position(
                    symbol=symbol,
                    entry_price=current_price,
                    quantity=position_size,
                    entry_time=datetime.now(),
                    target_price=target_price,
                    stop_loss_price=stop_loss_price,
                    order_id=order.get('id', ''),
                    status="active"
                )
                
                self.active_positions[symbol] = position
                
                # 로그 기록
                log_trade(
                    "BUY",
                    symbol,
                    "MARKET_BUY",
                    current_price,
                    position_size,
                    f"GPT Score: {analysis.get('signal_score', 0)}"
                )
                
                logger.info(f"Buy order executed: {symbol} @ ${current_price:.2f} x {position_size}")
                return True
            
            return False
            
        except Exception as e:
            log_error("BUY_ORDER_ERROR", f"Failed to execute buy order for {symbol}", e)
            return False
    
    def calculate_position_size(self, price: float) -> int:
        """포지션 크기 계산"""
        try:
            # 최대 포지션 크기 기준으로 계산
            max_shares = int(self.config['max_position_size'] / price)
            
            # 계좌 잔액 기준 확인
            account = self.alpaca_client.get_account()
            if account:
                buying_power = float(account.get('buying_power', 0))
                max_shares_by_bp = int(buying_power / price)
                max_shares = min(max_shares, max_shares_by_bp)
            
            return max(1, max_shares)
            
        except Exception as e:
            log_error("POSITION_SIZE_ERROR", f"Failed to calculate position size for price ${price}", e)
            return 0
    
    def monitor_positions(self):
        """포지션 모니터링 (실시간)"""
        try:
            for symbol, position in list(self.active_positions.items()):
                # 포지션 상태 업데이트
                self.update_position_status(position)
                
                # 청산 조건 확인
                if self.should_close_position(position):
                    self.close_position(position)
                    
        except Exception as e:
            log_error("POSITION_MONITORING_ERROR", "Failed to monitor positions", e)
    
    def should_close_position(self, position: Position) -> bool:
        """포지션 청산 조건 확인"""
        try:
            # 시장 데이터 수집
            market_data = self.market_analyzer.collect_market_data(position.symbol)
            if not market_data:
                return False
            
            current_price = market_data.get('current_price', 0)
            if current_price <= 0:
                return False
            
            # 수익률 계산
            profit_loss_pct = ((current_price - position.entry_price) / position.entry_price) * 100
            
            # 익절 조건
            if current_price >= position.target_price:
                logger.info(f"Target reached for {position.symbol}: {profit_loss_pct:.2f}%")
                return True
            
            # 손절 조건
            if current_price <= position.stop_loss_price:
                logger.info(f"Stop loss triggered for {position.symbol}: {profit_loss_pct:.2f}%")
                return True
            
            # 시간 기반 청산 (최대 보유 시간 초과)
            holding_time = (datetime.now() - position.entry_time).total_seconds()
            if holding_time > self.config['holding_time_limit']:
                logger.info(f"Time limit reached for {position.symbol}: {holding_time:.0f}s")
                return True
            
            # GPT 분석 기반 청산
            analysis = self.market_analyzer.analyze_exit_signal(
                position.symbol,
                position.to_dict()
            )
            
            if analysis.get("action") == "SELL" and analysis.get("exit_score", 0) >= 7:
                logger.info(f"GPT exit signal for {position.symbol}: {analysis.get('exit_score', 0)}")
                return True
            
            return False
            
        except Exception as e:
            log_error("CLOSE_CONDITION_ERROR", f"Failed to check close condition for {position.symbol}", e)
            return False
    
    def close_position(self, position: Position, reason: str = "AUTO_CLOSE") -> bool:
        """포지션 청산"""
        try:
            # 매도 주문 실행
            order = self.alpaca_client.place_order(
                symbol=position.symbol,
                qty=position.quantity,
                side="sell",
                type="market",
                time_in_force="gtc"
            )
            
            if order:
                # 현재 가격 가져오기
                market_data = self.market_analyzer.collect_market_data(position.symbol)
                current_price = market_data.get('current_price', position.entry_price)
                
                # 포지션 업데이트
                position.exit_price = current_price
                position.exit_time = datetime.now()
                position.profit_loss = (current_price - position.entry_price) * position.quantity
                position.status = "closed"
                
                # 포지션 이동 (활성 -> 완료)
                self.closed_positions.append(position)
                del self.active_positions[position.symbol]
                
                # 일일 통계 업데이트
                self.update_daily_stats(position)
                
                # 로그 기록
                log_trade(
                    "SELL",
                    position.symbol,
                    "MARKET_SELL",
                    current_price,
                    position.quantity,
                    f"Reason: {reason}"
                )
                
                log_performance(
                    position.symbol,
                    position.entry_price,
                    current_price,
                    position.profit_loss,
                    int((position.exit_time - position.entry_time).total_seconds())
                )
                
                logger.info(f"Position closed: {position.symbol} @ ${current_price:.2f} | P&L: ${position.profit_loss:.2f}")
                return True
            
            return False
            
        except Exception as e:
            log_error("CLOSE_POSITION_ERROR", f"Failed to close position for {position.symbol}", e)
            return False
    
    def close_all_positions(self, reason: str = "MANUAL_CLOSE"):
        """모든 포지션 청산"""
        try:
            for position in list(self.active_positions.values()):
                self.close_position(position, reason)
                time.sleep(0.1)  # API 호출 제한 고려
                
        except Exception as e:
            log_error("CLOSE_ALL_POSITIONS_ERROR", "Failed to close all positions", e)
    
    def update_position_status(self, position: Position):
        """포지션 상태 업데이트"""
        try:
            # 주문 상태 확인
            orders = self.alpaca_client.get_orders("open")
            for order in orders:
                if order.get('id') == position.order_id:
                    status = order.get('status')
                    if status == 'filled':
                        position.status = "filled"
                    elif status in ['cancelled', 'rejected'] and status:
                        position.status = status
                        
        except Exception as e:
            log_error("POSITION_STATUS_ERROR", f"Failed to update position status for {position.symbol}", e)
    
    def update_daily_stats(self, position: Position):
        """일일 통계 업데이트"""
        try:
            self.daily_stats["total_trades"] += 1
            self.daily_stats["total_profit_loss"] += position.profit_loss
            
            if position.profit_loss > 0:
                self.daily_stats["winning_trades"] += 1
            else:
                self.daily_stats["losing_trades"] += 1
            
            # 드로우다운 계산
            if position.profit_loss < 0:
                self.daily_stats["current_drawdown"] += abs(position.profit_loss)
                if self.daily_stats["current_drawdown"] > self.daily_stats["max_drawdown"]:
                    self.daily_stats["max_drawdown"] = self.daily_stats["current_drawdown"]
            else:
                self.daily_stats["current_drawdown"] = max(0, self.daily_stats["current_drawdown"] - position.profit_loss)
            
            # 서킷 브레이커 확인
            if self.daily_stats["total_profit_loss"] < -self.risk_config["max_daily_loss"]:
                self.trigger_circuit_breaker()
                
        except Exception as e:
            log_error("DAILY_STATS_ERROR", "Failed to update daily stats", e)
    
    def trigger_circuit_breaker(self):
        """서킷 브레이커 발동"""
        try:
            self.circuit_breaker_triggered = True
            self.trading_enabled = False
            
            # 모든 포지션 청산
            self.close_all_positions("CIRCUIT_BREAKER")
            
            logger.warning("Circuit breaker triggered - Trading halted")
            
        except Exception as e:
            log_error("CIRCUIT_BREAKER_ERROR", "Failed to trigger circuit breaker", e)
    
    def start_position_monitoring(self):
        """포지션 모니터링 스레드 시작"""
        def monitoring_loop():
            while not self.stop_monitoring:
                try:
                    self.monitor_positions()
                    time.sleep(5)  # 5초마다 모니터링
                except Exception as e:
                    log_error("MONITORING_LOOP_ERROR", "Error in monitoring loop", e)
        
        self.monitoring_thread = threading.Thread(target=monitoring_loop)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
    
    def get_portfolio_status(self) -> Dict:
        """포트폴리오 상태 반환"""
        try:
            account = self.alpaca_client.get_account()
            
            return {
                "active_positions": len(self.active_positions),
                "total_positions": len(self.active_positions) + len(self.closed_positions),
                "daily_pnl": self.daily_stats["total_profit_loss"],
                "win_rate": (self.daily_stats["winning_trades"] / max(1, self.daily_stats["total_trades"])) * 100,
                "max_drawdown": self.daily_stats["max_drawdown"],
                "account_value": float(account.get('portfolio_value', 0)) if account else 0,
                "buying_power": float(account.get('buying_power', 0)) if account else 0,
                "trading_enabled": self.trading_enabled,
                "circuit_breaker": self.circuit_breaker_triggered
            }
            
        except Exception as e:
            log_error("PORTFOLIO_STATUS_ERROR", "Failed to get portfolio status", e)
            return {}
    
    def get_position_summary(self) -> List[Dict]:
        """포지션 요약 반환"""
        try:
            summary = []
            
            for position in self.active_positions.values():
                # 현재 가격 가져오기
                market_data = self.market_analyzer.collect_market_data(position.symbol)
                current_price = market_data.get('current_price', position.entry_price)
                
                # 수익률 계산
                profit_loss_pct = ((current_price - position.entry_price) / position.entry_price) * 100
                unrealized_pnl = (current_price - position.entry_price) * position.quantity
                
                summary.append({
                    "symbol": position.symbol,
                    "entry_price": position.entry_price,
                    "current_price": current_price,
                    "quantity": position.quantity,
                    "profit_loss_pct": profit_loss_pct,
                    "unrealized_pnl": unrealized_pnl,
                    "holding_time": int((datetime.now() - position.entry_time).total_seconds()),
                    "status": position.status
                })
            
            return summary
            
        except Exception as e:
            log_error("POSITION_SUMMARY_ERROR", "Failed to get position summary", e)
            return []


# 전역 트레이더 인스턴스
scalping_trader = ScalpingTrader()


def get_scalping_trader() -> ScalpingTrader:
    """스캘핑 트레이더 인스턴스 반환"""
    return scalping_trader


def start_auto_trading():
    """자동 거래 시작 (간편 함수)"""
    return scalping_trader.start_trading()


def stop_auto_trading():
    """자동 거래 중지 (간편 함수)"""
    scalping_trader.stop_trading()


def trade_symbol(symbol: str) -> bool:
    """개별 종목 거래 (간편 함수)"""
    return scalping_trader.analyze_and_trade(symbol)


# 실행 예시
if __name__ == "__main__":
    # 트레이더 테스트
    print("=== 스캘핑 트레이더 테스트 ===")
    
    trader = ScalpingTrader()
    
    # 거래 시작
    if trader.start_trading():
        print("거래 시작됨")
        
        # 급등주 스크리닝 및 거래
        screener = get_stock_screener()
        top_stocks = screener.get_top_stocks(3)
        
        for stock in top_stocks:
            symbol = stock['symbol']
            print(f"\n{symbol} 거래 시도...")
            
            if trader.analyze_and_trade(symbol):
                print(f"{symbol} 매수 완료")
            else:
                print(f"{symbol} 매수 조건 불만족")
        
        # 포트폴리오 상태 확인
        status = trader.get_portfolio_status()
        print(f"\n포트폴리오 상태:")
        print(f"활성 포지션: {status.get('active_positions', 0)}")
        print(f"일일 손익: ${status.get('daily_pnl', 0):.2f}")
        print(f"승률: {status.get('win_rate', 0):.1f}%")
        
        # 거래 중지
        time.sleep(10)
        trader.stop_trading()
        print("\n거래 중지됨")
    else:
        print("거래 시작 실패")