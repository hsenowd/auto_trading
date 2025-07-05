"""
급등주 스크리너 - 장 전 거래량 급증 + 실적 발표 필터 추가
초단타 스캘핑에 최적화된 종목 발굴 시스템
"""

import asyncio
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from config.config import SCALPING_CONFIG
from utils.logger import get_logger, log_error
from utils.api_client import get_kis_client

logger = get_logger()


class EnhancedStockScreener:
    """강화된 급등주 스크리너"""
    
    def __init__(self):
        self.kis_client = get_kis_client()
        
        # 스크리닝 설정
        self.screening_config = {
            # 기존 조건들
            'gap_up_threshold': 3.0,           # 갭상승 3% 이상
            'volume_surge_threshold': 2.0,     # 거래량 급증 2배 이상
            'min_volume_threshold': 100000,    # 최소 거래량 10만달러
            'price_change_threshold': 2.0,     # 가격 변동 2% 이상
            
            # 🔥 새로운 조건들
            'pre_market_volume_surge': 3.0,    # 장 전 거래량 급증 3배 이상
            'earnings_priority_boost': 2.0,     # 실적 발표 우선순위 부스트
            'news_sentiment_threshold': 0.3,   # 뉴스 감성 점수 임계값
            'order_flow_intensity': 1.5,      # 주문 흐름 강도 1.5배 이상
            'momentum_persistence': 0.8,       # 모멘텀 지속성 80% 이상
        }
        
        # 실적 발표 캘린더 (예시 - 실제로는 API에서 가져와야 함)
        self.earnings_calendar = self.load_earnings_calendar()
        
        # 뉴스 감성 분석 캐시
        self.news_sentiment_cache = {}
        
        # 장 전 거래량 데이터 캐시
        self.pre_market_data_cache = {}
        
        # 중소형주 종목 리스트 (동전주부터 30달러까지)
        self.small_cap_stocks = [
            # 페니스톡 & 바이오/헬스케어
            "SNDL", "ZOM", "BNGO", "OCGN", "PLUG", "RIOT", "MARA", "TLRY", 
            "NAKD", "CTRM", "SHIP", "TOPS", "GNUS", "IZEA", "BIOC", "BIOL",
            "CLVS", "TTNP", "XSPA", "JAGX", "ADTX", "AIHS", "ALBT", "AMPE",
            
            # 기술주 & 전기차
            "NKLA", "WKHS", "RIDE", "GOEV", "HYLN", "BLNK", "CHPT", "EVGO",
            "BEEM", "SOLO", "AYRO", "FSR", "LCID", "PTRA", "ARVL", "MULN",
            
            # 소형주 ETF & 레버리지
            "SOXL", "TQQQ", "SPXL", "UVXY", "SQQQ", "LABU", "CURE", "TECL",
            
            # 암호화폐 관련
            "RIOT", "MARA", "CAN", "BTBT", "EBON", "SOS", "FTFT", "GREE",
            
            # 기타 중소형주
            "SENS", "MVIS", "WIMI", "GEVO", "IDEX", "XPEL", "KOSS", "EXPR",
            "CLOV", "WISH", "MAPS", "VERB", "MARK", "INUV", "LKCO", "NXTD"
        ]
        
        logger.info("Enhanced Stock Screener initialized with advanced filtering")
    
    def load_earnings_calendar(self) -> Dict:
        """실적 발표 캘린더 로드"""
        try:
            # 실제로는 외부 API에서 가져와야 함 (예: Alpha Vantage, FMP 등)
            # 여기서는 예시 데이터로 구현
            today = datetime.now().date()
            
            # 향후 7일간 실적 발표 예정 종목들 (예시)
            earnings_schedule = {}
            
            # 실적 발표 임박 종목들 (페니스톡 중심)
            earnings_candidates = [
                "SNDL", "ZOM", "BNGO", "OCGN", "PLUG", "RIOT", "MARA",
                "TLRY", "NAKD", "SOXL", "TQQQ", "SPXL", "UVXY", "SQQQ"
            ]
            
            for i, symbol in enumerate(earnings_candidates):
                earnings_date = today + timedelta(days=(i % 7))
                earnings_schedule[symbol] = {
                    'date': earnings_date.isoformat(),
                    'time': 'after_market',  # before_market 또는 after_market
                    'estimate_eps': 0.05,
                    'previous_eps': 0.02,
                    'surprise_history': [0.12, -0.08, 0.15, 0.03],  # 최근 서프라이즈 이력
                    'volatility_expected': 'HIGH'
                }
            
            logger.info(f"Loaded earnings calendar for {len(earnings_schedule)} symbols")
            return earnings_schedule
            
        except Exception as e:
            log_error("EARNINGS_CALENDAR_LOAD_ERROR", "Failed to load earnings calendar", e)
            return {}
    
    def get_pre_market_data(self, symbol: str) -> Dict:
        """장 전 거래량 및 가격 데이터 조회"""
        try:
            # 캐시 확인
            cache_key = f"{symbol}_{datetime.now().strftime('%Y%m%d')}"
            if cache_key in self.pre_market_data_cache:
                return self.pre_market_data_cache[cache_key]
            
            # 한국투자 API로 장 전 데이터 조회
            pre_market_data = self.kis_client.get_overseas_stock_price(symbol)
            
            if not pre_market_data:
                return {}
            
            # 장 전 거래량 분석
            current_volume = pre_market_data.get('volume', 0)
            avg_volume = pre_market_data.get('avg_volume_20d', 0)
            
            # 장 전 가격 변동
            pre_market_price = pre_market_data.get('pre_market_price', 0)
            previous_close = pre_market_data.get('previous_close', 0)
            
            pre_market_change = 0
            if previous_close > 0:
                pre_market_change = ((pre_market_price - previous_close) / previous_close) * 100
            
            # 장 전 거래량 급증도 계산
            volume_surge_ratio = 0
            if avg_volume > 0:
                volume_surge_ratio = current_volume / avg_volume
            
            result = {
                'symbol': symbol,
                'pre_market_price': pre_market_price,
                'previous_close': previous_close,
                'pre_market_change_percent': pre_market_change,
                'pre_market_volume': current_volume,
                'avg_volume_20d': avg_volume,
                'volume_surge_ratio': volume_surge_ratio,
                'timestamp': datetime.now().isoformat(),
                'is_pre_market_active': self.is_pre_market_session()
            }
            
            # 캐시에 저장
            self.pre_market_data_cache[cache_key] = result
            
            return result
            
        except Exception as e:
            log_error("PRE_MARKET_DATA_ERROR", f"Failed to get pre-market data for {symbol}", e)
            return {}
    
    def is_pre_market_session(self) -> bool:
        """현재 장 전 시간인지 확인"""
        from config.config import get_current_market_session
        return get_current_market_session() == "PRE_MARKET"
    
    def check_earnings_proximity(self, symbol: str) -> Dict:
        """실적 발표 임박 여부 확인"""
        try:
            if symbol not in self.earnings_calendar:
                return {
                    'has_earnings': False,
                    'days_until_earnings': 999,
                    'earnings_priority': 0,
                    'volatility_expected': 'NORMAL'
                }
            
            earnings_info = self.earnings_calendar[symbol]
            earnings_date = datetime.fromisoformat(earnings_info['date']).date()
            today = datetime.now().date()
            
            days_until = (earnings_date - today).days
            
            # 실적 발표 우선순위 계산
            if days_until <= 0:
                priority = 3.0  # 오늘 실적 발표
            elif days_until <= 1:
                priority = 2.5  # 내일 실적 발표
            elif days_until <= 2:
                priority = 2.0  # 이틀 후 실적 발표
            elif days_until <= 7:
                priority = 1.5  # 일주일 이내 실적 발표
            else:
                priority = 1.0  # 평상시
            
            # 서프라이즈 이력 기반 추가 점수
            surprise_history = earnings_info.get('surprise_history', [])
            if surprise_history:
                avg_surprise = sum(surprise_history) / len(surprise_history)
                if avg_surprise > 0.1:  # 평균 10% 이상 서프라이즈
                    priority *= 1.3
                elif avg_surprise > 0.05:  # 평균 5% 이상 서프라이즈
                    priority *= 1.1
            
            return {
                'has_earnings': True,
                'days_until_earnings': days_until,
                'earnings_date': earnings_info['date'],
                'earnings_time': earnings_info['time'],
                'earnings_priority': priority,
                'volatility_expected': earnings_info.get('volatility_expected', 'NORMAL'),
                'estimate_eps': earnings_info.get('estimate_eps', 0),
                'previous_eps': earnings_info.get('previous_eps', 0),
                'surprise_history': surprise_history
            }
            
        except Exception as e:
            log_error("EARNINGS_CHECK_ERROR", f"Failed to check earnings for {symbol}", e)
            return {
                'has_earnings': False,
                'days_until_earnings': 999,
                'earnings_priority': 1.0,
                'volatility_expected': 'NORMAL'
            }
    
    def analyze_order_flow_intensity(self, symbol: str) -> Dict:
        """주문 흐름 강도 분석"""
        try:
            # 한국투자 API로 호가 정보 조회
            quote_data = self.kis_client.get_overseas_stock_price(symbol)
            
            if not quote_data:
                return {'order_flow_intensity': 1.0, 'flow_direction': 'NEUTRAL'}
            
            # 호가 정보 분석
            bid_price = quote_data.get('bid_price', 0)
            ask_price = quote_data.get('ask_price', 0)
            bid_size = quote_data.get('bid_size', 0)
            ask_size = quote_data.get('ask_size', 0)
            
            # 체결 강도 계산
            if bid_size + ask_size > 0:
                bid_ratio = bid_size / (bid_size + ask_size)
                ask_ratio = ask_size / (bid_size + ask_size)
                
                # 매수 우세 시 강도 상승
                if bid_ratio > 0.6:
                    intensity = 1.5 + (bid_ratio - 0.6) * 2
                    direction = 'BUY_HEAVY'
                elif ask_ratio > 0.6:
                    intensity = 0.5 + (0.6 - ask_ratio) * 2
                    direction = 'SELL_HEAVY'
                else:
                    intensity = 1.0
                    direction = 'NEUTRAL'
            else:
                intensity = 1.0
                direction = 'NEUTRAL'
            
            # 스프레드 분석
            spread_ratio = 0
            if bid_price > 0:
                spread_ratio = (ask_price - bid_price) / bid_price
            
            # 스프레드가 좁을수록 유동성 높음
            liquidity_score = max(0.1, 1.0 - spread_ratio * 100)
            
            return {
                'order_flow_intensity': intensity,
                'flow_direction': direction,
                'bid_ask_ratio': bid_ratio if bid_size + ask_size > 0 else 0.5,
                'spread_ratio': spread_ratio,
                'liquidity_score': liquidity_score,
                'bid_size': bid_size,
                'ask_size': ask_size
            }
            
        except Exception as e:
            log_error("ORDER_FLOW_ANALYSIS_ERROR", f"Failed to analyze order flow for {symbol}", e)
            return {
                'order_flow_intensity': 1.0,
                'flow_direction': 'NEUTRAL',
                'bid_ask_ratio': 0.5,
                'spread_ratio': 0.01,
                'liquidity_score': 0.8
            }
    
    def calculate_momentum_persistence(self, symbol: str) -> float:
        """모멘텀 지속성 계산"""
        try:
            # 최근 5분간 가격 데이터 분석
            price_data = self.kis_client.get_overseas_stock_price(symbol)
            
            if not price_data:
                return 0.5
            
            current_price = price_data.get('current_price', 0)
            volume_1m = price_data.get('volume_1m', 0)
            volume_5m = price_data.get('volume_5m', 0)
            
            # 간단한 모멘텀 지속성 계산
            # 실제로는 더 복잡한 알고리즘이 필요
            
            # 거래량 증가 추세
            volume_trend = 0.7
            if volume_5m > 0:
                volume_trend = min(1.0, volume_1m / (volume_5m / 5))
            
            # 가격 변동 일관성 (여기서는 단순화)
            price_consistency = 0.8
            
            # 종합 모멘텀 지속성
            momentum_persistence = (volume_trend * 0.6) + (price_consistency * 0.4)
            
            return min(1.0, max(0.0, momentum_persistence))
            
        except Exception as e:
            log_error("MOMENTUM_PERSISTENCE_ERROR", f"Failed to calculate momentum persistence for {symbol}", e)
            return 0.5
    
    def get_enhanced_top_stocks(self, limit: int = 20) -> List[Dict]:
        """강화된 급등주 스크리닝"""
        try:
            logger.info(f"🔍 Enhanced screening for top {limit} stocks...")
            
            # 병렬 처리로 모든 종목 분석
            all_stocks = []
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_symbol = {
                    executor.submit(self.analyze_stock_comprehensive, symbol): symbol
                    for symbol in self.small_cap_stocks[:50]  # 상위 50개 종목만 분석
                }
                
                for future in as_completed(future_to_symbol):
                    symbol = future_to_symbol[future]
                    try:
                        stock_data = future.result(timeout=10)
                        if stock_data and stock_data.get('enhanced_score', 0) > 0:
                            all_stocks.append(stock_data)
                    except Exception as e:
                        logger.warning(f"Failed to analyze {symbol}: {e}")
            
            # 종합 점수 기준으로 정렬
            all_stocks.sort(key=lambda x: x.get('enhanced_score', 0), reverse=True)
            
            # 상위 종목들 반환
            top_stocks = all_stocks[:limit]
            
            logger.info(f"✅ Enhanced screening completed. Found {len(top_stocks)} qualified stocks")
            
            return top_stocks
            
        except Exception as e:
            log_error("ENHANCED_SCREENING_ERROR", "Enhanced screening failed", e)
            return []
    
    def analyze_stock_comprehensive(self, symbol: str) -> Optional[Dict]:
        """종목 종합 분석"""
        try:
            # 1. 기본 가격 및 거래량 데이터
            price_data = self.kis_client.get_overseas_stock_price(symbol)
            if not price_data:
                return None
            
            current_price = price_data.get('current_price', 0)
            
            # 가격 범위 필터링 (동전주 ~ $30)
            if not (0.01 <= current_price <= 30.0):
                return None
            
            # 2. 장 전 거래량 분석
            pre_market_data = self.get_pre_market_data(symbol)
            pre_market_score = 0
            
            if pre_market_data:
                volume_surge = pre_market_data.get('volume_surge_ratio', 0)
                if volume_surge >= self.screening_config['pre_market_volume_surge']:
                    pre_market_score = min(100, volume_surge * 20)
            
            # 3. 실적 발표 임박 여부 확인
            earnings_info = self.check_earnings_proximity(symbol)
            earnings_score = earnings_info.get('earnings_priority', 1.0) * 20
            
            # 4. 주문 흐름 강도 분석
            order_flow = self.analyze_order_flow_intensity(symbol)
            flow_score = order_flow.get('order_flow_intensity', 1.0) * 15
            
            # 5. 모멘텀 지속성 계산
            momentum = self.calculate_momentum_persistence(symbol)
            momentum_score = momentum * 25
            
            # 6. 기존 스크리닝 점수 계산
            basic_score = self.calculate_basic_screening_score(price_data)
            
            # 7. 종합 점수 계산 (가중 평균)
            enhanced_score = (
                basic_score * 0.3 +           # 기본 점수 30%
                pre_market_score * 0.25 +     # 장 전 거래량 25%
                earnings_score * 0.2 +        # 실적 발표 20%
                flow_score * 0.15 +          # 주문 흐름 15%
                momentum_score * 0.1         # 모멘텀 10%
            )
            
            # 최소 점수 필터링
            if enhanced_score < 60:
                return None
            
            # 결과 구성
            result = {
                'symbol': symbol,
                'current_price': current_price,
                'enhanced_score': enhanced_score,
                'basic_score': basic_score,
                'pre_market_score': pre_market_score,
                'earnings_score': earnings_score,
                'flow_score': flow_score,
                'momentum_score': momentum_score,
                
                # 세부 정보
                'pre_market_data': pre_market_data,
                'earnings_info': earnings_info,
                'order_flow': order_flow,
                'momentum_persistence': momentum,
                
                # 기존 데이터
                'volume': price_data.get('volume', 0),
                'daily_change': price_data.get('daily_change', 0),
                'volume_intensity': price_data.get('volume_intensity', 0),
                'screening_time': datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            log_error("COMPREHENSIVE_ANALYSIS_ERROR", f"Failed to analyze {symbol} comprehensively", e)
            return None
    
    def calculate_basic_screening_score(self, price_data: Dict) -> float:
        """기본 스크리닝 점수 계산"""
        try:
            score = 0
            
            # 갭상승 점수
            daily_change = price_data.get('daily_change', 0)
            if daily_change >= self.screening_config['gap_up_threshold']:
                score += min(30, daily_change * 5)
            
            # 거래량 급증 점수
            volume_intensity = price_data.get('volume_intensity', 0)
            if volume_intensity >= self.screening_config['volume_surge_threshold']:
                score += min(25, volume_intensity * 10)
            
            # 거래대금 점수
            volume_usd = price_data.get('volume_usd', 0)
            if volume_usd >= self.screening_config['min_volume_threshold']:
                score += min(20, volume_usd / 10000)
            
            # 가격 변동 점수
            if abs(daily_change) >= self.screening_config['price_change_threshold']:
                score += min(15, abs(daily_change) * 3)
            
            return min(100, score)
            
        except Exception as e:
            log_error("BASIC_SCORING_ERROR", "Failed to calculate basic screening score", e)
            return 0
    
    def get_top_stocks(self, limit: int = 10) -> List[Dict]:
        """상위 급등주 조회 (기존 호환성 유지)"""
        return self.get_enhanced_top_stocks(limit)


# 전역 인스턴스
enhanced_screener = EnhancedStockScreener()


def get_stock_screener() -> EnhancedStockScreener:
    """스크리너 인스턴스 반환"""
    return enhanced_screener


def get_enhanced_top_stocks(limit: int = 10) -> List[Dict]:
    """강화된 급등주 조회 (간편 함수)"""
    return enhanced_screener.get_enhanced_top_stocks(limit)


# 실행 예시
if __name__ == "__main__":
    print("=== 강화된 급등주 스크리너 테스트 ===")
    
    screener = EnhancedStockScreener()
    
    # 강화된 스크리닝 실행
    top_stocks = screener.get_enhanced_top_stocks(5)
    
    for i, stock in enumerate(top_stocks, 1):
        print(f"\n{i}. {stock['symbol']} - ${stock['current_price']:.3f}")
        print(f"   종합 점수: {stock['enhanced_score']:.1f}")
        print(f"   장 전 점수: {stock['pre_market_score']:.1f}")
        print(f"   실적 점수: {stock['earnings_score']:.1f}")
        print(f"   주문 흐름: {stock['flow_score']:.1f}")
        print(f"   모멘텀: {stock['momentum_score']:.1f}")
        
        # 실적 발표 정보
        earnings_info = stock['earnings_info']
        if earnings_info['has_earnings']:
            print(f"   📊 실적 발표: {earnings_info['days_until_earnings']}일 후")
    
    print("\n강화된 스크리닝 테스트 완료!")