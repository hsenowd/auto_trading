"""
간단한 로깅 시스템 (loguru 대체)
"""

import logging
import os
from datetime import datetime
from typing import Any, Optional

# 로그 디렉토리 생성
os.makedirs("logs", exist_ok=True)

# 로거 설정
def setup_logger(name: str = "kis_api") -> logging.Logger:
    """로거 설정"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # 이미 핸들러가 있으면 중복 추가 방지
    if logger.handlers:
        return logger
    
    # 파일 핸들러
    timestamp = datetime.now().strftime("%Y%m%d")
    file_handler = logging.FileHandler(f"logs/{name}_{timestamp}.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 포맷터
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# 전역 로거
_logger = setup_logger()

def get_logger(name: str = "kis_api") -> logging.Logger:
    """로거 인스턴스 반환"""
    if name == "kis_api":
        return _logger
    return setup_logger(name)

def log_error(error_code: str, message: str, exception: Optional[Exception] = None) -> None:
    """에러 로깅"""
    error_msg = f"[{error_code}] {message}"
    if exception:
        error_msg += f" | Exception: {str(exception)}"
    
    _logger.error(error_msg)

# 기본 로거 함수들
def debug(message: str) -> None:
    _logger.debug(message)

def info(message: str) -> None:
    _logger.info(message)

def warning(message: str) -> None:
    _logger.warning(message)

def error(message: str) -> None:
    _logger.error(message)

def critical(message: str) -> None:
    _logger.critical(message)