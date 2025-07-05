"""
GPT 기반 실시간 분석 엔진
시장 데이터를 GPT로 분석하여 매수/매도 시그널을 생성합니다.
"""

import json
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

from config.config import GPT_PROMPTS, SCALPING_CONFIG
from utils.logger import get_logger, log_signal, log_error
from utils.api_client import get_alpaca_client, get_openai_client
from screener.stock_screener import get_stock_screener

logger = get_logger()


class MarketDataAnalyzer:
    """시장 데이터 분석 클래스"""
    
    def __init__(self):
        self.alpaca_client = get_alpaca_client()
        self.openai_client = get_openai_client()
        self.stock_screener = get_stock_screener()
        
        # 분석 히스토리 저장 (메모리 기반)
        self.analysis_history = {}
        
        logger.info("MarketDataAnalyzer initialized")
    
    def collect_market_data(self, symbol: str) -> Dict:
        """종목의 실시간 시장 데이터 수집"""
        try:
            # 기본 시장 데이터 수집
            base_data = self.stock_screener.get_detailed_analysis(symbol)
            
            # Alpaca API에서 추가 데이터 수집
            latest_quotes = self.alpaca_client.get_latest_quotes([symbol])
            latest_trades = self.alpaca_client.get_latest_trades([symbol])
            latest_bars = self.alpaca_client.get_latest_bars([symbol], "1Min")
            
            # 호가 데이터 처리
            quote_data = latest_quotes.get(symbol, {})
            bid_price = quote_data.get('bid_price', 0)
            ask_price = quote_data.get('ask_price', 0)
            bid_size = quote_data.get('bid_size', 0)
            ask_size = quote_data.get('ask_size', 0)
            
            # 체결 데이터 처리
            trade_data = latest_trades.get(symbol, {})
            last_price = trade_data.get('price', base_data.get('current_price', 0))
            last_size = trade_data.get('size', 0)
            
            # 호가 스프레드 계산
            bid_ask_spread = (ask_price - bid_price) / last_price if last_price > 0 else 0
            
            # 체결강도 계산 (매수량 vs 매도량 비율)
            volume_intensity = self.calculate_volume_intensity(symbol)
            
            # 1분봉 데이터 처리
            bar_data = latest_bars.get(symbol, {})
            if isinstance(bar_data, dict) and 'volume' in bar_data:
                volume_1m = bar_data['volume']
                volume_5m = self.get_5min_volume(symbol)
            else:
                volume_1m = last_size
                volume_5m = volume_1m * 5  # 추정치
            
            # 통합 시장 데이터 생성
            market_data = {
                **base_data,
                'current_price': last_price,
                'bid_price': bid_price,
                'ask_price': ask_price,
                'bid_size': bid_size,
                'ask_size': ask_size,
                'bid_ask_spread': bid_ask_spread,
                'volume_intensity': volume_intensity,
                'volume_1m': volume_1m,
                'volume_5m': volume_5m,
                'last_trade_size': last_size,
                'timestamp': datetime.now().isoformat(),
            }
            
            return market_data
            
        except Exception as e:
            log_error("MARKET_DATA_COLLECTION_ERROR", f"Failed to collect market data for {symbol}", e)
            return {}
    
    def calculate_volume_intensity(self, symbol: str) -> float:
        """체결강도 계산 (매수세 vs 매도세)"""
        try:
            # 최근 거래 데이터를 기반으로 체결강도 계산
            # 실제로는 tick 데이터가 필요하지만, 여기서는 간단한 추정치 사용
            
            # 호가 데이터 가져오기
            quotes = self.alpaca_client.get_latest_quotes([symbol])
            quote_data = quotes.get(symbol, {})
            
            bid_size = quote_data.get('bid_size', 0)
            ask_size = quote_data.get('ask_size', 0)
            
            # 매수세 vs 매도세 비율
            total_size = bid_size + ask_size
            if total_size > 0:
                intensity = (bid_size / total_size) * 100
            else:
                intensity = 50  # 중립
            
            return intensity
            
        except Exception as e:
            log_error("VOLUME_INTENSITY_ERROR", f"Failed to calculate volume intensity for {symbol}", e)
            return 50
    
    def get_5min_volume(self, symbol: str) -> int:
        """5분간 거래량 계산"""
        try:
            # 5분 바 데이터 가져오기
            bars = self.alpaca_client.get_latest_bars([symbol], "5Min")
            bar_data = bars.get(symbol, {})
            
            if isinstance(bar_data, dict) and 'volume' in bar_data:
                return bar_data['volume']
            else:
                return 0
                
        except Exception as e:
            log_error("5MIN_VOLUME_ERROR", f"Failed to get 5min volume for {symbol}", e)
            return 0
    
    def analyze_entry_signal(self, symbol: str) -> Dict:
        """매수 시그널 분석"""
        try:
            # 시장 데이터 수집
            market_data = self.collect_market_data(symbol)
            if not market_data:
                return {"signal_score": 0, "reasoning": "시장 데이터 수집 실패", "action": "HOLD"}
            
            # GPT 분석 실행
            analysis = self.openai_client.analyze_entry_signal(symbol, market_data)
            
            # 분석 결과 검증 및 보정
            analysis = self.validate_analysis(analysis, "entry")
            
            # 분석 히스토리 저장
            self.save_analysis_history(symbol, "entry", analysis, market_data)
            
            # 로그 기록
            log_signal(symbol, "ENTRY", analysis.get("signal_score", 0), analysis.get("reasoning", ""))
            
            return analysis
            
        except Exception as e:
            log_error("ENTRY_SIGNAL_ERROR", f"Failed to analyze entry signal for {symbol}", e)
            return {"signal_score": 0, "reasoning": "분석 실패", "action": "HOLD"}
    
    def analyze_exit_signal(self, symbol: str, position_data: Dict) -> Dict:
        """매도 시그널 분석"""
        try:
            # 현재 시장 데이터 수집
            market_data = self.collect_market_data(symbol)
            if not market_data:
                return {"exit_score": 0, "reasoning": "시장 데이터 수집 실패", "action": "HOLD"}
            
            # 포지션 데이터 보강
            enhanced_position_data = {
                **position_data,
                'current_price': market_data.get('current_price', 0),
                'current_volume': market_data.get('volume_1m', 0),
                'volume_intensity': market_data.get('volume_intensity', 50),
                'bid_ask_spread': market_data.get('bid_ask_spread', 0),
            }
            
            # 수익률 계산
            entry_price = position_data.get('entry_price', 0)
            current_price = market_data.get('current_price', 0)
            if entry_price > 0:
                profit_loss = ((current_price - entry_price) / entry_price) * 100
                enhanced_position_data['profit_loss'] = profit_loss
            
            # 보유 시간 계산
            entry_time = position_data.get('entry_time', datetime.now())
            if isinstance(entry_time, str):
                entry_time = datetime.fromisoformat(entry_time)
            holding_time = (datetime.now() - entry_time).total_seconds()
            enhanced_position_data['holding_time'] = holding_time
            
            # GPT 분석 실행
            analysis = self.openai_client.analyze_exit_signal(symbol, enhanced_position_data)
            
            # 분석 결과 검증 및 보정
            analysis = self.validate_analysis(analysis, "exit")
            
            # 분석 히스토리 저장
            self.save_analysis_history(symbol, "exit", analysis, enhanced_position_data)
            
            # 로그 기록
            log_signal(symbol, "EXIT", analysis.get("exit_score", 0), analysis.get("reasoning", ""))
            
            return analysis
            
        except Exception as e:
            log_error("EXIT_SIGNAL_ERROR", f"Failed to analyze exit signal for {symbol}", e)
            return {"exit_score": 0, "reasoning": "분석 실패", "action": "HOLD"}
    
    def validate_analysis(self, analysis: Dict, signal_type: str) -> Dict:
        """분석 결과 검증 및 보정"""
        try:
            if signal_type == "entry":
                # 매수 시그널 검증
                score = analysis.get("signal_score", 5)
                score = max(0, min(10, score))  # 0-10 범위로 제한
                
                action = analysis.get("action", "HOLD").upper()
                if action not in ["BUY", "HOLD", "SELL"]:
                    action = "HOLD"
                
                return {
                    "signal_score": score,
                    "reasoning": analysis.get("reasoning", "분석 결과 없음"),
                    "action": action,
                    "confidence": self.calculate_confidence(score),
                    "timestamp": datetime.now().isoformat()
                }
            
            elif signal_type == "exit":
                # 매도 시그널 검증
                score = analysis.get("exit_score", 5)
                score = max(0, min(10, score))  # 0-10 범위로 제한
                
                action = analysis.get("action", "HOLD").upper()
                if action not in ["HOLD", "SELL"]:
                    action = "HOLD"
                
                return {
                    "exit_score": score,
                    "reasoning": analysis.get("reasoning", "분석 결과 없음"),
                    "action": action,
                    "confidence": self.calculate_confidence(score),
                    "timestamp": datetime.now().isoformat()
                }
            
            return analysis
            
        except Exception as e:
            log_error("ANALYSIS_VALIDATION_ERROR", f"Failed to validate analysis for {signal_type}", e)
            return analysis
    
    def calculate_confidence(self, score: float) -> str:
        """신뢰도 계산"""
        if score >= 8:
            return "HIGH"
        elif score >= 6:
            return "MEDIUM"
        elif score >= 4:
            return "LOW"
        else:
            return "VERY_LOW"
    
    def save_analysis_history(self, symbol: str, signal_type: str, analysis: Dict, market_data: Dict):
        """분석 히스토리 저장"""
        try:
            if symbol not in self.analysis_history:
                self.analysis_history[symbol] = []
            
            history_entry = {
                "timestamp": datetime.now().isoformat(),
                "signal_type": signal_type,
                "analysis": analysis,
                "market_data": market_data,
            }
            
            self.analysis_history[symbol].append(history_entry)
            
            # 히스토리 크기 제한 (최근 100개만 유지)
            if len(self.analysis_history[symbol]) > 100:
                self.analysis_history[symbol] = self.analysis_history[symbol][-100:]
                
        except Exception as e:
            log_error("HISTORY_SAVE_ERROR", f"Failed to save analysis history for {symbol}", e)
    
    def get_analysis_history(self, symbol: str, limit: int = 10) -> List[Dict]:
        """분석 히스토리 조회"""
        try:
            history = self.analysis_history.get(symbol, [])
            return history[-limit:] if limit > 0 else history
            
        except Exception as e:
            log_error("HISTORY_GET_ERROR", f"Failed to get analysis history for {symbol}", e)
            return []
    
    def batch_analyze_symbols(self, symbols: List[str]) -> Dict[str, Dict]:
        """여러 종목 일괄 분석"""
        try:
            results = {}
            
            for symbol in symbols:
                try:
                    analysis = self.analyze_entry_signal(symbol)
                    results[symbol] = analysis
                    
                    # API 호출 제한 고려하여 잠시 대기
                    time.sleep(0.5)
                    
                except Exception as e:
                    log_error("BATCH_ANALYSIS_ERROR", f"Failed to analyze {symbol} in batch", e)
                    results[symbol] = {"signal_score": 0, "reasoning": "분석 실패", "action": "HOLD"}
            
            return results
            
        except Exception as e:
            log_error("BATCH_ANALYSIS_ERROR", "Failed to execute batch analysis", e)
            return {}
    
    def get_market_sentiment(self, symbols: List[str]) -> Dict:
        """시장 전체 심리 분석"""
        try:
            analyses = self.batch_analyze_symbols(symbols)
            
            # 전체 시장 지표 계산
            total_signals = len(analyses)
            buy_signals = sum(1 for analysis in analyses.values() if analysis.get("action") == "BUY")
            sell_signals = sum(1 for analysis in analyses.values() if analysis.get("action") == "SELL")
            
            avg_score = np.mean([analysis.get("signal_score", 0) for analysis in analyses.values()])
            
            # 시장 심리 분류
            if avg_score >= 7:
                sentiment = "BULLISH"
            elif avg_score >= 5:
                sentiment = "NEUTRAL"
            else:
                sentiment = "BEARISH"
            
            return {
                "sentiment": sentiment,
                "average_score": avg_score,
                "total_signals": total_signals,
                "buy_signals": buy_signals,
                "sell_signals": sell_signals,
                "buy_ratio": buy_signals / total_signals if total_signals > 0 else 0,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            log_error("MARKET_SENTIMENT_ERROR", "Failed to analyze market sentiment", e)
            return {"sentiment": "NEUTRAL", "average_score": 5, "timestamp": datetime.now().isoformat()}


# 전역 분석기 인스턴스
market_analyzer = MarketDataAnalyzer()


def get_market_analyzer() -> MarketDataAnalyzer:
    """마켓 분석기 인스턴스 반환"""
    return market_analyzer


def analyze_entry_signal(symbol: str) -> Dict:
    """매수 시그널 분석 (간편 함수)"""
    return market_analyzer.analyze_entry_signal(symbol)


def analyze_exit_signal(symbol: str, position_data: Dict) -> Dict:
    """매도 시그널 분석 (간편 함수)"""
    return market_analyzer.analyze_exit_signal(symbol, position_data)


# 실행 예시
if __name__ == "__main__":
    # 분석기 테스트
    print("=== GPT 분석기 테스트 ===")
    
    analyzer = MarketDataAnalyzer()
    
    # 개별 종목 분석
    symbol = "TSLA"
    print(f"\n{symbol} 매수 시그널 분석:")
    entry_analysis = analyzer.analyze_entry_signal(symbol)
    print(f"점수: {entry_analysis.get('signal_score', 0)}")
    print(f"액션: {entry_analysis.get('action', 'HOLD')}")
    print(f"근거: {entry_analysis.get('reasoning', 'N/A')}")
    
    # 시장 심리 분석
    symbols = ["TSLA", "AAPL", "NVDA"]
    print(f"\n시장 심리 분석:")
    sentiment = analyzer.get_market_sentiment(symbols)
    print(f"심리: {sentiment.get('sentiment', 'NEUTRAL')}")
    print(f"평균 점수: {sentiment.get('average_score', 0):.1f}")
    print(f"매수 비율: {sentiment.get('buy_ratio', 0):.1%}")