"""
로깅 유틸리티 모듈
스캘핑 시스템의 모든 로그를 관리합니다.
"""

import os
import sys
from loguru import logger
from datetime import datetime
from config.config import LOGGING_CONFIG


class TradingLogger:
    """거래 시스템 전용 로거 클래스"""
    
    def __init__(self):
        self.setup_logger()
    
    def setup_logger(self):
        """로거 초기 설정"""
        # 기본 로거 제거
        logger.remove()
        
        # 로그 디렉토리 생성
        log_dir = os.path.dirname(LOGGING_CONFIG["log_file"])
        os.makedirs(log_dir, exist_ok=True)
        
        # 콘솔 로거 추가
        logger.add(
            sys.stdout,
            format=LOGGING_CONFIG["format"],
            level=LOGGING_CONFIG["level"],
            colorize=True,
        )
        
        # 파일 로거 추가
        logger.add(
            LOGGING_CONFIG["log_file"],
            format=LOGGING_CONFIG["format"],
            level=LOGGING_CONFIG["level"],
            rotation=LOGGING_CONFIG["rotation"],
            retention=LOGGING_CONFIG["retention"],
            compression="zip",
        )
        
        # 거래 전용 로그 파일 추가
        logger.add(
            "logs/trades.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {extra[trade_type]} | {message}",
            filter=lambda record: "trade_type" in record["extra"],
            rotation="1 day",
            retention="90 days",
        )
    
    def log_trade(self, trade_type: str, symbol: str, action: str, 
                  price: float, quantity: int, reason: str = ""):
        """거래 로그 기록"""
        logger.bind(trade_type=trade_type).info(
            f"{symbol} | {action} | Price: ${price:.2f} | Qty: {quantity} | {reason}"
        )
    
    def log_signal(self, symbol: str, signal_type: str, score: float, reasoning: str):
        """시그널 로그 기록"""
        logger.info(
            f"SIGNAL | {symbol} | {signal_type} | Score: {score:.2f} | {reasoning}"
        )
    
    def log_error(self, error_type: str, message: str, exception: Exception = None):
        """에러 로그 기록"""
        if exception:
            logger.error(f"ERROR | {error_type} | {message} | {str(exception)}")
        else:
            logger.error(f"ERROR | {error_type} | {message}")
    
    def log_performance(self, symbol: str, entry_price: float, exit_price: float,
                       profit_loss: float, holding_time: int):
        """성과 로그 기록"""
        logger.info(
            f"PERFORMANCE | {symbol} | Entry: ${entry_price:.2f} | "
            f"Exit: ${exit_price:.2f} | P&L: ${profit_loss:.2f} | "
            f"Time: {holding_time}s"
        )


# 전역 로거 인스턴스
trading_logger = TradingLogger()


def get_logger():
    """로거 인스턴스 반환"""
    return logger


def log_trade(trade_type: str, symbol: str, action: str, 
              price: float, quantity: int, reason: str = ""):
    """거래 로그 기록 (간편 함수)"""
    trading_logger.log_trade(trade_type, symbol, action, price, quantity, reason)


def log_signal(symbol: str, signal_type: str, score: float, reasoning: str):
    """시그널 로그 기록 (간편 함수)"""
    trading_logger.log_signal(symbol, signal_type, score, reasoning)


def log_error(error_type: str, message: str, exception: Exception = None):
    """에러 로그 기록 (간편 함수)"""
    trading_logger.log_error(error_type, message, exception)


def log_performance(symbol: str, entry_price: float, exit_price: float,
                   profit_loss: float, holding_time: int):
    """성과 로그 기록 (간편 함수)"""
    trading_logger.log_performance(symbol, entry_price, exit_price, profit_loss, holding_time)