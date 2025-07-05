"""
페이퍼 트레이딩 시뮬레이터
한국투자 모의투자 API 한계를 극복하기 위한 자체 시뮬레이션 엔진
실전과 동일한 조건으로 백테스트 및 페이퍼 트레이딩 수행
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from dataclasses import dataclass, asdict
import pickle
import os

from config.config import SCALPING_CONFIG, RISK_MANAGEMENT
from utils.logger import get_logger, log_error
from utils.api_client import get_kis_client

logger = get_logger()


@dataclass
class SimulatedOrder:
    """시뮬레이션 주문"""
    order_id: str
    symbol: str
    side: str  # BUY, SELL
    quantity: int
    price: float
    order_type: str  # MARKET, LIMIT
    timestamp: datetime
    status: str  # PENDING, FILLED, CANCELLED
    filled_price: Optional[float] = None
    filled_quantity: int = 0
    commission: float = 0.0
    slippage: float = 0.0


@dataclass
class SimulatedPosition:
    """시뮬레이션 포지션"""
    symbol: str
    quantity: int
    avg_price: float
    entry_time: datetime
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0


@dataclass
class SimulatedAccount:
    """시뮬레이션 계좌"""
    cash: float
    equity: float
    buying_power: float
    positions: Dict[str, SimulatedPosition]
    orders: List[SimulatedOrder]
    total_pnl: float = 0.0
    daily_pnl: float = 0.0
    max_drawdown: float = 0.0
    trade_count: int = 0
    win_count: int = 0


class PaperTradingSimulator:
    """페이퍼 트레이딩 시뮬레이터"""
    
    def __init__(self, initial_cash: float = 50000):
        self.kis_client = get_kis_client()
        self.initial_cash = initial_cash
        
        # 계좌 초기화
        self.account = SimulatedAccount(
            cash=initial_cash,
            equity=initial_cash,
            buying_power=initial_cash,
            positions={},
            orders=[]
        )
        
        # 거래 기록
        self.trade_history = []
        self.daily_stats = {}
        
        # 수수료 및 슬리피지 설정 (실전 수준)
        self.commission_rate = 0.00025  # 0.025% (실제 한국투자 수준)
        self.slippage_rate = 0.0002     # 0.02% (실제 슬리피지)
        
        # 데이터베이스 초기화
        self.db_path = "data/paper_trading.db"
        self.init_database()
        
        logger.info(f"Paper Trading Simulator initialized with ${initial_cash:,.2f}")
    
    def init_database(self):
        """데이터베이스 초기화"""
        try:
            os.makedirs("data", exist_ok=True)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 주문 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    symbol TEXT,
                    side TEXT,
                    quantity INTEGER,
                    price REAL,
                    order_type TEXT,
                    timestamp TEXT,
                    status TEXT,
                    filled_price REAL,
                    filled_quantity INTEGER,
                    commission REAL,
                    slippage REAL
                )
            ''')
            
            # 거래 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    entry_time TEXT,
                    exit_time TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    quantity INTEGER,
                    pnl REAL,
                    pnl_percent REAL,
                    holding_time_seconds INTEGER,
                    entry_signal_score REAL,
                    exit_reason TEXT
                )
            ''')
            
            # 일일 통계 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_stats (
                    date TEXT PRIMARY KEY,
                    starting_equity REAL,
                    ending_equity REAL,
                    daily_pnl REAL,
                    total_trades INTEGER,
                    winning_trades INTEGER,
                    losing_trades INTEGER,
                    win_rate REAL,
                    max_drawdown REAL,
                    sharpe_ratio REAL
                )
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info("Paper trading database initialized")
            
        except Exception as e:
            log_error("DB_INIT_ERROR", "Failed to initialize database", e)
    
    def get_real_time_price(self, symbol: str) -> Optional[float]:
        """실시간 가격 조회 (실제 한국투자 API 사용)"""
        try:
            price_data = self.kis_client.get_overseas_stock_price(symbol)
            if price_data:
                return price_data.get('current_price', None)
            return None
            
        except Exception as e:
            log_error("PRICE_FETCH_ERROR", f"Failed to get real-time price for {symbol}", e)
            return None
    
    def calculate_slippage(self, symbol: str, side: str, quantity: int) -> float:
        """슬리피지 계산 (실제 시장 조건 반영)"""
        try:
            # 기본 슬리피지
            base_slippage = self.slippage_rate
            
            # 수량 기반 슬리피지 (대량 거래 시 증가)
            if quantity > 10000:
                base_slippage *= 2.0
            elif quantity > 5000:
                base_slippage *= 1.5
            elif quantity > 1000:
                base_slippage *= 1.2
            
            # 매수/매도 방향 (매수 시 불리, 매도 시 불리)
            direction_multiplier = 1.0 if side == "BUY" else -1.0
            
            return base_slippage * direction_multiplier
            
        except Exception as e:
            log_error("SLIPPAGE_CALC_ERROR", f"Error calculating slippage", e)
            return self.slippage_rate
    
    def place_order(self, symbol: str, side: str, quantity: int, 
                   order_type: str = "MARKET", limit_price: Optional[float] = None) -> str:
        """주문 실행 (실제 시장 조건 시뮬레이션)"""
        try:
            order_id = f"{symbol}_{side}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            
            # 현재가 조회
            current_price = self.get_real_time_price(symbol)
            if not current_price:
                logger.error(f"Cannot get price for {symbol}")
                return None
            
            # 주문 가격 결정
            if order_type == "MARKET":
                order_price = current_price
            else:  # LIMIT
                order_price = limit_price or current_price
            
            # 매수 가능 여부 확인
            if side == "BUY":
                total_cost = order_price * quantity
                commission = total_cost * self.commission_rate
                required_cash = total_cost + commission
                
                if self.account.cash < required_cash:
                    logger.warning(f"Insufficient cash for {symbol}: need ${required_cash:.2f}, have ${self.account.cash:.2f}")
                    return None
            
            # 매도 가능 여부 확인
            elif side == "SELL":
                if symbol not in self.account.positions:
                    logger.warning(f"No position to sell for {symbol}")
                    return None
                
                position = self.account.positions[symbol]
                if position.quantity < quantity:
                    logger.warning(f"Insufficient shares to sell: need {quantity}, have {position.quantity}")
                    return None
            
            # 주문 생성
            order = SimulatedOrder(
                order_id=order_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=order_price,
                order_type=order_type,
                timestamp=datetime.now(),
                status="PENDING"
            )
            
            # 시장가 주문은 즉시 체결
            if order_type == "MARKET":
                self.fill_order(order)
            
            self.account.orders.append(order)
            
            # 데이터베이스 저장
            self.save_order_to_db(order)
            
            logger.info(f"Order placed: {order_id} - {side} {quantity} {symbol} @ ${order_price:.3f}")
            return order_id
            
        except Exception as e:
            log_error("ORDER_PLACE_ERROR", f"Failed to place order for {symbol}", e)
            return None
    
    def fill_order(self, order: SimulatedOrder):
        """주문 체결 처리"""
        try:
            # 현재가 기준 체결가 계산
            current_price = self.get_real_time_price(order.symbol)
            if not current_price:
                order.status = "CANCELLED"
                return
            
            # 슬리피지 적용
            slippage = self.calculate_slippage(order.symbol, order.side, order.quantity)
            filled_price = current_price * (1 + slippage)
            
            # 수수료 계산
            trade_value = filled_price * order.quantity
            commission = trade_value * self.commission_rate
            
            # 주문 업데이트
            order.status = "FILLED"
            order.filled_price = filled_price
            order.filled_quantity = order.quantity
            order.commission = commission
            order.slippage = slippage
            
            # 계좌 업데이트
            if order.side == "BUY":
                self.execute_buy(order)
            else:
                self.execute_sell(order)
            
            logger.info(f"Order filled: {order.order_id} - {order.side} {order.quantity} {order.symbol} @ ${filled_price:.3f}")
            
        except Exception as e:
            log_error("ORDER_FILL_ERROR", f"Failed to fill order {order.order_id}", e)
            order.status = "CANCELLED"
    
    def execute_buy(self, order: SimulatedOrder):
        """매수 실행"""
        try:
            total_cost = order.filled_price * order.quantity + order.commission
            
            # 현금 차감
            self.account.cash -= total_cost
            
            # 포지션 업데이트
            if order.symbol in self.account.positions:
                # 기존 포지션에 추가
                position = self.account.positions[order.symbol]
                total_quantity = position.quantity + order.quantity
                total_cost_basis = (position.avg_price * position.quantity) + (order.filled_price * order.quantity)
                position.avg_price = total_cost_basis / total_quantity
                position.quantity = total_quantity
            else:
                # 새 포지션 생성
                self.account.positions[order.symbol] = SimulatedPosition(
                    symbol=order.symbol,
                    quantity=order.quantity,
                    avg_price=order.filled_price,
                    entry_time=order.timestamp
                )
            
            self.update_account_equity()
            
        except Exception as e:
            log_error("BUY_EXECUTION_ERROR", f"Failed to execute buy for {order.symbol}", e)
    
    def execute_sell(self, order: SimulatedOrder):
        """매도 실행"""
        try:
            position = self.account.positions[order.symbol]
            
            # 손익 계산
            cost_basis = position.avg_price * order.quantity
            proceeds = order.filled_price * order.quantity - order.commission
            realized_pnl = proceeds - cost_basis
            
            # 현금 증가
            self.account.cash += proceeds
            
            # 포지션 업데이트
            position.quantity -= order.quantity
            position.realized_pnl += realized_pnl
            
            # 거래 기록 저장
            trade_record = {
                'symbol': order.symbol,
                'entry_time': position.entry_time,
                'exit_time': order.timestamp,
                'entry_price': position.avg_price,
                'exit_price': order.filled_price,
                'quantity': order.quantity,
                'pnl': realized_pnl,
                'pnl_percent': (realized_pnl / cost_basis) * 100,
                'holding_time_seconds': (order.timestamp - position.entry_time).total_seconds(),
                'commission': order.commission,
                'slippage': order.slippage
            }
            
            self.trade_history.append(trade_record)
            self.save_trade_to_db(trade_record)
            
            # 포지션 완전 청산 시 제거
            if position.quantity == 0:
                del self.account.positions[order.symbol]
            
            # 계좌 통계 업데이트
            self.account.total_pnl += realized_pnl
            self.account.trade_count += 1
            if realized_pnl > 0:
                self.account.win_count += 1
            
            self.update_account_equity()
            
            logger.info(f"Trade completed: {order.symbol} PnL: ${realized_pnl:+.2f} ({(realized_pnl/cost_basis)*100:+.2f}%)")
            
        except Exception as e:
            log_error("SELL_EXECUTION_ERROR", f"Failed to execute sell for {order.symbol}", e)
    
    def update_account_equity(self):
        """계좌 자산 업데이트"""
        try:
            total_position_value = 0
            
            for symbol, position in self.account.positions.items():
                current_price = self.get_real_time_price(symbol)
                if current_price:
                    position_value = current_price * position.quantity
                    position.unrealized_pnl = position_value - (position.avg_price * position.quantity)
                    total_position_value += position_value
            
            self.account.equity = self.account.cash + total_position_value
            self.account.buying_power = self.account.cash  # 간단화
            
            # 최대 낙폭 계산
            peak_equity = max(self.initial_cash, self.account.equity)
            current_drawdown = (peak_equity - self.account.equity) / peak_equity
            self.account.max_drawdown = max(self.account.max_drawdown, current_drawdown)
            
        except Exception as e:
            log_error("EQUITY_UPDATE_ERROR", "Failed to update account equity", e)
    
    def get_account_status(self) -> Dict:
        """계좌 상태 반환"""
        try:
            self.update_account_equity()
            
            win_rate = (self.account.win_count / self.account.trade_count * 100) if self.account.trade_count > 0 else 0
            
            return {
                'cash': self.account.cash,
                'equity': self.account.equity,
                'total_pnl': self.account.total_pnl,
                'unrealized_pnl': sum(pos.unrealized_pnl for pos in self.account.positions.values()),
                'positions_count': len(self.account.positions),
                'trade_count': self.account.trade_count,
                'win_rate': win_rate,
                'max_drawdown': self.account.max_drawdown * 100,
                'return_percent': ((self.account.equity - self.initial_cash) / self.initial_cash) * 100
            }
            
        except Exception as e:
            log_error("ACCOUNT_STATUS_ERROR", "Failed to get account status", e)
            return {}
    
    def save_order_to_db(self, order: SimulatedOrder):
        """주문을 데이터베이스에 저장"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                order.order_id, order.symbol, order.side, order.quantity,
                order.price, order.order_type, order.timestamp.isoformat(),
                order.status, order.filled_price, order.filled_quantity,
                order.commission, order.slippage
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            log_error("DB_SAVE_ORDER_ERROR", f"Failed to save order {order.order_id}", e)
    
    def save_trade_to_db(self, trade: Dict):
        """거래를 데이터베이스에 저장"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO trades (symbol, entry_time, exit_time, entry_price, exit_price,
                                  quantity, pnl, pnl_percent, holding_time_seconds, 
                                  entry_signal_score, exit_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade['symbol'], trade['entry_time'].isoformat(), trade['exit_time'].isoformat(),
                trade['entry_price'], trade['exit_price'], trade['quantity'],
                trade['pnl'], trade['pnl_percent'], trade['holding_time_seconds'],
                trade.get('entry_signal_score', 0), trade.get('exit_reason', 'MANUAL')
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            log_error("DB_SAVE_TRADE_ERROR", f"Failed to save trade", e)
    
    def get_trading_performance(self, days: int = 30) -> Dict:
        """거래 성과 분석"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            # 최근 거래 조회
            query = '''
                SELECT * FROM trades 
                WHERE exit_time >= datetime('now', '-{} days')
                ORDER BY exit_time DESC
            '''.format(days)
            
            trades_df = pd.read_sql_query(query, conn)
            conn.close()
            
            if trades_df.empty:
                return {
                    'total_trades': 0,
                    'win_rate': 0,
                    'avg_pnl': 0,
                    'total_pnl': 0,
                    'sharpe_ratio': 0,
                    'max_drawdown': 0,
                    'avg_holding_time': 0
                }
            
            # 성과 지표 계산
            total_trades = len(trades_df)
            winning_trades = len(trades_df[trades_df['pnl'] > 0])
            win_rate = (winning_trades / total_trades) * 100
            
            total_pnl = trades_df['pnl'].sum()
            avg_pnl = trades_df['pnl'].mean()
            
            # 샤프 비율 (간단 계산)
            if trades_df['pnl'].std() > 0:
                sharpe_ratio = avg_pnl / trades_df['pnl'].std() * np.sqrt(252)  # 연율화
            else:
                sharpe_ratio = 0
            
            # 평균 보유 시간 (분)
            avg_holding_time = trades_df['holding_time_seconds'].mean() / 60
            
            return {
                'total_trades': total_trades,
                'win_rate': win_rate,
                'avg_pnl': avg_pnl,
                'total_pnl': total_pnl,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': self.account.max_drawdown * 100,
                'avg_holding_time': avg_holding_time,
                'best_trade': trades_df['pnl'].max(),
                'worst_trade': trades_df['pnl'].min()
            }
            
        except Exception as e:
            log_error("PERFORMANCE_ANALYSIS_ERROR", "Failed to analyze performance", e)
            return {}
    
    def reset_account(self, new_cash: float = None):
        """계좌 초기화"""
        try:
            initial_cash = new_cash or self.initial_cash
            
            self.account = SimulatedAccount(
                cash=initial_cash,
                equity=initial_cash,
                buying_power=initial_cash,
                positions={},
                orders=[]
            )
            
            self.trade_history = []
            self.initial_cash = initial_cash
            
            logger.info(f"Account reset with ${initial_cash:,.2f}")
            
        except Exception as e:
            log_error("ACCOUNT_RESET_ERROR", "Failed to reset account", e)


# 전역 시뮬레이터 인스턴스
paper_trader = PaperTradingSimulator()


def get_paper_trader() -> PaperTradingSimulator:
    """페이퍼 트레이더 인스턴스 반환"""
    return paper_trader


# 실행 예시
if __name__ == "__main__":
    print("=== 페이퍼 트레이딩 시뮬레이터 테스트 ===")
    
    simulator = PaperTradingSimulator(initial_cash=50000)
    
    # 계좌 상태 확인
    status = simulator.get_account_status()
    print(f"초기 자산: ${status['equity']:,.2f}")
    
    # 테스트 주문 (실제로는 실시간 데이터 필요)
    print("\n테스트 주문 실행...")
    
    # 매수 주문
    order_id = simulator.place_order("SNDL", "BUY", 1000, "MARKET")
    if order_id:
        print(f"매수 주문 완료: {order_id}")
    
    # 계좌 상태 재확인
    status = simulator.get_account_status()
    print(f"매수 후 자산: ${status['equity']:,.2f}")
    print(f"포지션 수: {status['positions_count']}")
    
    print("\n시뮬레이터 테스트 완료!")