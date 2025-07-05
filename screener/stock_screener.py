"""
급등주 스크리너 모듈
갭상승, 거래량 급증, 거래대금 조건을 만족하는 종목을 선별합니다.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import concurrent.futures
import time

from config.config import SCREENING_CONFIG
from utils.logger import get_logger, log_error
from utils.api_client import get_alpaca_client

logger = get_logger()


class StockScreener:
    """급등주 스크리너 클래스"""
    
    def __init__(self):
        self.alpaca_client = get_alpaca_client()
        self.config = SCREENING_CONFIG
        
        # 미국 주식 주요 종목 리스트 (실제로는 더 많은 종목을 포함)
        self.universe = [
            "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "NFLX",
            "AMD", "CRM", "ZOOM", "PYPL", "SHOP", "SQ", "ROKU", "PELOTON",
            "SNAP", "UBER", "LYFT", "DOCU", "ZM", "PTON", "SPCE", "PLTR",
            "COIN", "RBLX", "HOOD", "SOFI", "LCID", "RIVN", "F", "GM",
            "BAC", "JPM", "GS", "MS", "C", "WFC", "V", "MA", "DIS", "KO"
        ]
        
        logger.info(f"StockScreener initialized with {len(self.universe)} symbols")
    
    def get_market_data(self, symbol: str) -> Optional[Dict]:
        """개별 종목의 시장 데이터 수집"""
        try:
            # Yahoo Finance에서 데이터 가져오기
            ticker = yf.Ticker(symbol)
            
            # 최근 5일 데이터 가져오기
            hist = ticker.history(period="5d", interval="1d")
            if len(hist) < 2:
                return None
            
            # 실시간 정보 가져오기
            info = ticker.info
            
            # 최신 가격 정보
            current_price = info.get('currentPrice', hist['Close'].iloc[-1])
            previous_close = hist['Close'].iloc[-2]
            
            # 거래량 정보
            current_volume = info.get('volume', hist['Volume'].iloc[-1])
            avg_volume = hist['Volume'].mean()
            
            # 시가 정보
            today_open = info.get('open', hist['Open'].iloc[-1])
            
            # 갭 계산
            gap_percent = ((today_open - previous_close) / previous_close) * 100
            
            # 일일 등락률
            daily_change = ((current_price - previous_close) / previous_close) * 100
            
            # 거래대금 (달러)
            dollar_volume = current_price * current_volume
            
            # 거래량 급증 배수
            volume_spike = current_volume / avg_volume if avg_volume > 0 else 0
            
            return {
                'symbol': symbol,
                'current_price': current_price,
                'previous_close': previous_close,
                'today_open': today_open,
                'gap_percent': gap_percent,
                'daily_change': daily_change,
                'current_volume': current_volume,
                'avg_volume': avg_volume,
                'volume_spike': volume_spike,
                'dollar_volume': dollar_volume,
                'market_cap': info.get('marketCap', 0),
                'float_shares': info.get('floatShares', 0),
                'sector': info.get('sector', 'Unknown'),
                'industry': info.get('industry', 'Unknown'),
            }
            
        except Exception as e:
            log_error("MARKET_DATA_ERROR", f"Failed to get market data for {symbol}", e)
            return None
    
    def apply_screening_filters(self, data: Dict) -> bool:
        """스크리닝 필터 적용"""
        try:
            # 가격 범위 필터
            if not (self.config['min_price'] <= data['current_price'] <= self.config['max_price']):
                return False
            
            # 최소 거래량 필터
            if data['current_volume'] < self.config['min_volume']:
                return False
            
            # 갭 상승 필터
            if data['gap_percent'] < self.config['gap_threshold'] * 100:
                return False
            
            # 거래량 급증 필터
            if data['volume_spike'] < self.config['volume_spike']:
                return False
            
            # 상승 종목만 선별
            if data['daily_change'] <= 0:
                return False
            
            return True
            
        except Exception as e:
            log_error("SCREENING_FILTER_ERROR", f"Error applying filters to {data.get('symbol', 'unknown')}", e)
            return False
    
    def calculate_screening_score(self, data: Dict) -> float:
        """스크리닝 점수 계산 (0-100점)"""
        try:
            score = 0
            
            # 갭 상승 점수 (최대 25점)
            gap_score = min(data['gap_percent'] * 2, 25)
            score += gap_score
            
            # 거래량 급증 점수 (최대 25점)
            volume_score = min(data['volume_spike'] * 5, 25)
            score += volume_score
            
            # 일일 등락률 점수 (최대 25점)
            change_score = min(data['daily_change'] * 2, 25)
            score += change_score
            
            # 거래대금 점수 (최대 25점)
            dollar_volume_m = data['dollar_volume'] / 1000000  # 백만 달러 단위
            dollar_score = min(dollar_volume_m / 50 * 25, 25)
            score += dollar_score
            
            return min(score, 100)
            
        except Exception as e:
            log_error("SCORING_ERROR", f"Error calculating score for {data.get('symbol', 'unknown')}", e)
            return 0
    
    def screen_stocks(self, symbols: Optional[List[str]] = None) -> List[Dict]:
        """병렬 처리로 종목 스크리닝 실행"""
        if symbols is None:
            symbols = self.universe
        
        logger.info(f"Starting stock screening for {len(symbols)} symbols")
        
        screened_stocks = []
        
        # 병렬 처리로 시장 데이터 수집
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_symbol = {executor.submit(self.get_market_data, symbol): symbol for symbol in symbols}
            
            for future in concurrent.futures.as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    data = future.result()
                    if data and self.apply_screening_filters(data):
                        # 스크리닝 점수 계산
                        data['screening_score'] = self.calculate_screening_score(data)
                        screened_stocks.append(data)
                        
                        logger.info(f"Screened: {symbol} - Score: {data['screening_score']:.1f}")
                        
                except Exception as e:
                    log_error("SCREENING_ERROR", f"Error screening {symbol}", e)
        
        # 스크리닝 점수 기준으로 정렬
        screened_stocks.sort(key=lambda x: x['screening_score'], reverse=True)
        
        logger.info(f"Screening completed. Found {len(screened_stocks)} qualifying stocks")
        
        return screened_stocks
    
    def get_top_stocks(self, limit: int = 10) -> List[Dict]:
        """상위 N개 종목 반환"""
        screened_stocks = self.screen_stocks()
        return screened_stocks[:limit]
    
    def get_sector_leaders(self) -> Dict[str, List[Dict]]:
        """섹터별 리더 종목 반환"""
        screened_stocks = self.screen_stocks()
        
        sector_leaders = {}
        for stock in screened_stocks:
            sector = stock.get('sector', 'Unknown')
            if sector not in sector_leaders:
                sector_leaders[sector] = []
            sector_leaders[sector].append(stock)
        
        # 각 섹터별 상위 3개 종목만 유지
        for sector in sector_leaders:
            sector_leaders[sector] = sector_leaders[sector][:3]
        
        return sector_leaders
    
    def get_detailed_analysis(self, symbol: str) -> Dict:
        """개별 종목 상세 분석"""
        try:
            # 기본 시장 데이터 수집
            data = self.get_market_data(symbol)
            if not data:
                return {}
            
            # 추가 기술적 지표 계산
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="30d", interval="1d")
            
            if len(hist) >= 20:
                # 20일 이동평균
                data['ma20'] = hist['Close'].rolling(20).mean().iloc[-1]
                data['price_vs_ma20'] = ((data['current_price'] - data['ma20']) / data['ma20']) * 100
                
                # 볼링거 밴드
                rolling_mean = hist['Close'].rolling(20).mean()
                rolling_std = hist['Close'].rolling(20).std()
                data['bb_upper'] = rolling_mean.iloc[-1] + (rolling_std.iloc[-1] * 2)
                data['bb_lower'] = rolling_mean.iloc[-1] - (rolling_std.iloc[-1] * 2)
                
                # RSI 계산
                delta = hist['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                data['rsi'] = 100 - (100 / (1 + rs)).iloc[-1]
                
            # 스크리닝 점수 계산
            data['screening_score'] = self.calculate_screening_score(data)
            
            return data
            
        except Exception as e:
            log_error("DETAILED_ANALYSIS_ERROR", f"Error in detailed analysis for {symbol}", e)
            return {}


# 전역 스크리너 인스턴스
stock_screener = StockScreener()


def get_stock_screener() -> StockScreener:
    """스크리너 인스턴스 반환"""
    return stock_screener


def screen_top_stocks(limit: int = 10) -> List[Dict]:
    """상위 급등주 반환 (간편 함수)"""
    return stock_screener.get_top_stocks(limit)


def analyze_stock(symbol: str) -> Dict:
    """개별 종목 분석 (간편 함수)"""
    return stock_screener.get_detailed_analysis(symbol)


# 실행 예시
if __name__ == "__main__":
    # 급등주 스크리닝 실행
    print("=== 급등주 스크리닝 시작 ===")
    
    screener = StockScreener()
    top_stocks = screener.get_top_stocks(5)
    
    print(f"\n상위 5개 급등주:")
    for i, stock in enumerate(top_stocks, 1):
        print(f"{i}. {stock['symbol']}: {stock['screening_score']:.1f}점")
        print(f"   현재가: ${stock['current_price']:.2f}")
        print(f"   갭상승: {stock['gap_percent']:.2f}%")
        print(f"   거래량급증: {stock['volume_spike']:.1f}배")
        print(f"   일일등락률: {stock['daily_change']:.2f}%")
        print()