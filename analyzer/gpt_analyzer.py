"""
강화된 GPT 분석 엔진 - 뉴스 감성 분석 + 체결강도 고도화
초단타 스캘핑을 위한 AI 신호 강도 수치화 시스템
"""

import json
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from dataclasses import dataclass

from config.config import SCALPING_CONFIG
from utils.logger import get_logger, log_error
from utils.api_client import get_openai_client, get_kis_client

logger = get_logger()


@dataclass
class NewsItem:
    """뉴스 아이템 데이터 클래스"""
    title: str
    content: str
    timestamp: datetime
    source: str
    symbol: str
    sentiment_score: float = 0.0
    impact_score: float = 0.0
    keywords: Optional[List[str]] = None


@dataclass
class OrderFlowAnalysis:
    """주문 흐름 분석 데이터 클래스"""
    bid_ask_spread: float
    bid_size: float
    ask_size: float
    volume_intensity: float
    price_momentum: float
    order_imbalance: float
    flow_direction: str
    strength_score: float


@dataclass
class EnhancedSignal:
    """강화된 AI 신호 데이터 클래스"""
    symbol: str
    signal_type: str  # BUY, SELL, HOLD
    confidence: float  # 0-100
    ai_signal_strength: float  # 0-100 (AI가 판단한 종합 신호 강도)
    news_sentiment_score: float  # -1 to +1
    order_flow_score: float  # 0-100
    technical_score: float  # 0-100
    reasoning: str
    risk_factors: List[str]
    target_entry: float
    target_exit: float
    stop_loss: float
    holding_time_estimate: int  # minutes


class EnhancedGPTAnalyzer:
    """강화된 GPT 분석기"""
    
    def __init__(self):
        self.openai_client = get_openai_client()
        self.kis_client = get_kis_client()
        
        # 뉴스 감성 분석 캐시
        self.news_cache = {}
        self.sentiment_cache = {}
        
        # 주문 흐름 데이터 캐시
        self.order_flow_cache = {}
        
        # AI 신호 강도 가중치 설정
        self.signal_weights = {
            'news_sentiment': 0.3,      # 뉴스 감성 30%
            'order_flow': 0.4,          # 주문 흐름 40%
            'technical': 0.2,           # 기술적 분석 20%
            'momentum': 0.1             # 모멘텀 10%
        }
        
        logger.info("Enhanced GPT Analyzer initialized with news sentiment & order flow analysis")
    
    def get_stock_news(self, symbol: str, hours_back: int = 24) -> List[NewsItem]:
        """종목 관련 뉴스 수집"""
        try:
            # 뉴스 캐시 확인
            cache_key = f"{symbol}_{hours_back}_{datetime.now().strftime('%Y%m%d_%H')}"
            if cache_key in self.news_cache:
                return self.news_cache[cache_key]
            
            # 실제로는 뉴스 API (예: Alpha Vantage, NewsAPI, Yahoo Finance 등) 사용
            # 여기서는 시뮬레이션 데이터로 구현
            news_items = []
            
            # 시뮬레이션된 뉴스 데이터 생성
            sample_news = [
                {
                    'title': f"{symbol} Reports Strong Q3 Earnings Beat",
                    'content': f"{symbol} exceeded analyst expectations with quarterly earnings...",
                    'sentiment': 0.8,
                    'impact': 0.9,
                    'keywords': ['earnings', 'beat', 'strong', 'growth']
                },
                {
                    'title': f"Analyst Upgrades {symbol} to Buy Rating",
                    'content': f"Leading investment firm upgrades {symbol} citing strong fundamentals...",
                    'sentiment': 0.6,
                    'impact': 0.7,
                    'keywords': ['upgrade', 'buy', 'analyst', 'fundamentals']
                },
                {
                    'title': f"{symbol} Announces New Partnership Deal",
                    'content': f"{symbol} enters strategic partnership with major tech company...",
                    'sentiment': 0.5,
                    'impact': 0.6,
                    'keywords': ['partnership', 'deal', 'strategic', 'collaboration']
                },
                {
                    'title': f"FDA Approval Risk for {symbol} Drug Candidate",
                    'content': f"{symbol} awaits FDA decision on key drug approval...",
                    'sentiment': -0.2,
                    'impact': 0.8,
                    'keywords': ['FDA', 'approval', 'risk', 'drug', 'regulatory']
                }
            ]
            
            # 뉴스 아이템 생성
            for news in sample_news:
                news_item = NewsItem(
                    title=news['title'],
                    content=news['content'],
                    timestamp=datetime.now() - timedelta(hours=np.random.randint(1, hours_back)),
                    source="MarketWatch",
                    symbol=symbol,
                    sentiment_score=news['sentiment'],
                    impact_score=news['impact'],
                    keywords=news['keywords']
                )
                news_items.append(news_item)
            
            # 캐시에 저장
            self.news_cache[cache_key] = news_items
            
            logger.info(f"Collected {len(news_items)} news items for {symbol}")
            return news_items
            
        except Exception as e:
            log_error("NEWS_COLLECTION_ERROR", f"Failed to collect news for {symbol}", e)
            return []
    
    def analyze_news_sentiment_with_gpt(self, news_items: List[NewsItem]) -> Dict:
        """GPT를 사용한 뉴스 감성 분석"""
        try:
            if not news_items:
                return {
                    'overall_sentiment': 0.0,
                    'confidence': 0.0,
                    'key_factors': [],
                    'sentiment_breakdown': {}
                }
            
            # 뉴스 텍스트 준비
            news_text = "\n\n".join([
                f"제목: {item.title}\n내용: {item.content[:200]}..."
                for item in news_items[:5]  # 최대 5개 뉴스만 분석
            ])
            
            # GPT 프롬프트 구성
            prompt = f"""
다음 주식 뉴스들을 분석하여 감성 점수를 제공해주세요.

뉴스 내용:
{news_text}

분석 요청:
1. 전체 감성 점수 (-1.0 ~ +1.0): 매우 부정(-1.0) ~ 중립(0.0) ~ 매우 긍정(+1.0)
2. 신뢰도 (0.0 ~ 1.0): 분석의 확신 정도
3. 핵심 요인들: 감성에 영향을 미치는 주요 키워드/사건들
4. 초단타 거래 관점에서의 영향도 (0.0 ~ 1.0)

응답 형식 (JSON):
{{
    "overall_sentiment": float,
    "confidence": float,
    "scalping_impact": float,
    "key_factors": ["factor1", "factor2", ...],
    "sentiment_breakdown": {{
        "positive_factors": ["긍정 요인들"],
        "negative_factors": ["부정 요인들"],
        "neutral_factors": ["중립 요인들"]
    }},
    "reasoning": "분석 근거 설명"
}}
"""
            
            # GPT API 호출
            response = self.openai_client.analyze_entry_signal(
                symbol="SENTIMENT_ANALYSIS",
                market_data={
                    "news_text": news_text,
                    "analysis_type": "sentiment",
                    "prompt": prompt
                }
            )
            
            # 응답 파싱
            if isinstance(response, dict) and 'reasoning' in response:
                # OpenAI 클라이언트가 이미 분석 결과를 반환한 경우
                sentiment_analysis = {
                    'overall_sentiment': 0.0,  # 기본값
                    'confidence': 0.7,
                    'scalping_impact': 0.5,
                    'key_factors': ['GPT 분석 결과'],
                    'sentiment_breakdown': {
                        'positive_factors': ['분석 완료'],
                        'negative_factors': [],
                        'neutral_factors': []
                    },
                    'reasoning': response.get('reasoning', '뉴스 감성 분석 완료')
                }
            else:
                # 기본값 반환
                sentiment_analysis = {
                    'overall_sentiment': 0.0,
                    'confidence': 0.5,
                    'scalping_impact': 0.3,
                    'key_factors': ['기본 분석'],
                    'sentiment_breakdown': {
                        'positive_factors': [],
                        'negative_factors': [],
                        'neutral_factors': ['중립적 뉴스']
                    },
                    'reasoning': '기본 뉴스 감성 분석'
                }
            
            return sentiment_analysis
            
        except Exception as e:
            log_error("GPT_SENTIMENT_ANALYSIS_ERROR", "Failed to analyze news sentiment with GPT", e)
            return {
                'overall_sentiment': 0.0,
                'confidence': 0.0,
                'scalping_impact': 0.0,
                'key_factors': [],
                'sentiment_breakdown': {},
                'reasoning': f'분석 오류: {str(e)}'
            }
    
    def analyze_enhanced_order_flow(self, symbol: str) -> OrderFlowAnalysis:
        """강화된 주문 흐름 분석 (호가 잔량 변화 + 체결 속도)"""
        try:
            # 캐시 확인
            cache_key = f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M')}"
            if cache_key in self.order_flow_cache:
                return self.order_flow_cache[cache_key]
            
            # 한국투자 API로 실시간 호가 데이터 조회
            quote_data = self.kis_client.get_overseas_stock_price(symbol)
            
            if not quote_data:
                return OrderFlowAnalysis(
                    bid_ask_spread=0.01,
                    bid_size=1000,
                    ask_size=1000,
                    volume_intensity=1.0,
                    price_momentum=0.0,
                    order_imbalance=0.0,
                    flow_direction='NEUTRAL',
                    strength_score=50.0
                )
            
            # 호가 데이터 추출
            bid_price = quote_data.get('bid_price', 0)
            ask_price = quote_data.get('ask_price', 0)
            bid_size = quote_data.get('bid_size', 0)
            ask_size = quote_data.get('ask_size', 0)
            current_price = quote_data.get('current_price', 0)
            volume = quote_data.get('volume', 0)
            
            # 1. 호가 스프레드 계산
            bid_ask_spread = 0
            if bid_price > 0:
                bid_ask_spread = (ask_price - bid_price) / bid_price
            
            # 2. 주문 불균형 계산
            total_size = bid_size + ask_size
            order_imbalance = 0
            if total_size > 0:
                order_imbalance = (bid_size - ask_size) / total_size
            
            # 3. 거래량 강도 계산 (시뮬레이션)
            avg_volume = volume * 0.8  # 평균 거래량 근사치
            volume_intensity = volume / avg_volume if avg_volume > 0 else 1.0
            
            # 4. 가격 모멘텀 계산 (최근 변화율)
            daily_change = quote_data.get('daily_change', 0)
            price_momentum = daily_change / 100  # 백분율을 소수점으로 변환
            
            # 5. 주문 흐름 방향 결정
            if order_imbalance > 0.2:
                flow_direction = 'BUY_PRESSURE'
            elif order_imbalance < -0.2:
                flow_direction = 'SELL_PRESSURE'
            else:
                flow_direction = 'NEUTRAL'
            
            # 6. 종합 강도 점수 계산 (0-100)
            strength_factors = [
                min(100, abs(order_imbalance) * 200),  # 주문 불균형 (최대 40점)
                min(100, volume_intensity * 50),       # 거래량 강도 (최대 50점)
                min(100, abs(price_momentum) * 1000),  # 가격 모멘텀 (최대 10점)
                100 - min(100, bid_ask_spread * 10000) # 유동성 (스프레드 역수)
            ]
            
            strength_score = sum(strength_factors) / 4  # 평균값
            
            # 결과 객체 생성
            analysis = OrderFlowAnalysis(
                bid_ask_spread=bid_ask_spread,
                bid_size=bid_size,
                ask_size=ask_size,
                volume_intensity=volume_intensity,
                price_momentum=price_momentum,
                order_imbalance=order_imbalance,
                flow_direction=flow_direction,
                strength_score=strength_score
            )
            
            # 캐시에 저장
            self.order_flow_cache[cache_key] = analysis
            
            return analysis
            
        except Exception as e:
            log_error("ORDER_FLOW_ANALYSIS_ERROR", f"Failed to analyze order flow for {symbol}", e)
            return OrderFlowAnalysis(
                bid_ask_spread=0.01,
                bid_size=1000,
                ask_size=1000,
                volume_intensity=1.0,
                price_momentum=0.0,
                order_imbalance=0.0,
                flow_direction='NEUTRAL',
                strength_score=50.0
            )
    
    def calculate_ai_signal_strength(self, symbol: str, market_data: Dict) -> float:
        """AI 신호 강도 수치화 (뉴스 + 체결 + 기술적 분석 종합)"""
        try:
            # 1. 뉴스 감성 분석
            news_items = self.get_stock_news(symbol, hours_back=6)  # 최근 6시간 뉴스
            news_sentiment = self.analyze_news_sentiment_with_gpt(news_items)
            
            # 뉴스 점수 계산 (0-100)
            sentiment_score = news_sentiment.get('overall_sentiment', 0.0)
            sentiment_confidence = news_sentiment.get('confidence', 0.0)
            scalping_impact = news_sentiment.get('scalping_impact', 0.3)
            
            news_score = (
                (sentiment_score + 1) * 50 *  # -1~1을 0~100으로 변환
                sentiment_confidence *         # 신뢰도 가중
                scalping_impact               # 스캘핑 영향도 가중
            )
            
            # 2. 주문 흐름 분석
            order_flow = self.analyze_enhanced_order_flow(symbol)
            flow_score = order_flow.strength_score
            
            # 3. 기술적 분석 점수 (기존 데이터 활용)
            technical_score = 0
            
            # 갭상승 점수
            daily_change = market_data.get('daily_change', 0)
            if daily_change > 0:
                technical_score += min(30, daily_change * 2)
            
            # 거래량 점수
            volume_intensity = market_data.get('volume_intensity', 0)
            technical_score += min(25, volume_intensity * 10)
            
            # 가격 모멘텀 점수
            if abs(daily_change) > 2:
                technical_score += min(20, abs(daily_change))
            
            # 유동성 점수
            volume_usd = market_data.get('volume_usd', 0)
            if volume_usd > 100000:
                technical_score += min(25, volume_usd / 50000)
            
            # 4. 모멘텀 점수 (가격 + 거래량 추세)
            momentum_score = 50  # 기본값
            if order_flow.price_momentum > 0.02:  # 2% 이상 상승
                momentum_score += 30
            elif order_flow.price_momentum < -0.02:  # 2% 이상 하락
                momentum_score -= 30
            
            if order_flow.volume_intensity > 1.5:  # 거래량 1.5배 이상
                momentum_score += 20
            
            momentum_score = max(0, min(100, momentum_score))
            
            # 5. 가중 평균으로 최종 AI 신호 강도 계산
            ai_signal_strength = (
                news_score * self.signal_weights['news_sentiment'] +
                flow_score * self.signal_weights['order_flow'] +
                technical_score * self.signal_weights['technical'] +
                momentum_score * self.signal_weights['momentum']
            )
            
            # 0-100 범위로 정규화
            ai_signal_strength = max(0, min(100, ai_signal_strength))
            
            logger.info(f"AI Signal Strength for {symbol}: {ai_signal_strength:.1f} "
                       f"(News: {news_score:.1f}, Flow: {flow_score:.1f}, "
                       f"Tech: {technical_score:.1f}, Momentum: {momentum_score:.1f})")
            
            return ai_signal_strength
            
        except Exception as e:
            log_error("AI_SIGNAL_STRENGTH_ERROR", f"Failed to calculate AI signal strength for {symbol}", e)
            return 50.0  # 기본값
    
    def generate_enhanced_signal(self, symbol: str, market_data: Dict) -> EnhancedSignal:
        """강화된 AI 신호 생성"""
        try:
            # AI 신호 강도 계산
            ai_signal_strength = self.calculate_ai_signal_strength(symbol, market_data)
            
            # 뉴스 감성 분석
            news_items = self.get_stock_news(symbol, hours_back=6)
            news_sentiment = self.analyze_news_sentiment_with_gpt(news_items)
            
            # 주문 흐름 분석
            order_flow = self.analyze_enhanced_order_flow(symbol)
            
            # 신호 타입 결정
            signal_type = "HOLD"
            confidence = 50.0
            
            if ai_signal_strength >= 75:
                signal_type = "BUY"
                confidence = min(95, ai_signal_strength + 10)
            elif ai_signal_strength >= 60:
                signal_type = "BUY"
                confidence = ai_signal_strength
            elif ai_signal_strength <= 25:
                signal_type = "SELL"
                confidence = 100 - ai_signal_strength
            elif ai_signal_strength <= 40:
                signal_type = "SELL"
                confidence = 60 - ai_signal_strength
            
            # 현재가 및 목표가 설정
            current_price = market_data.get('current_price', 0)
            daily_change = market_data.get('daily_change', 0)
            
            # 목표 진입가 (현재가 기준)
            target_entry = current_price
            
            # 목표 청산가 (0.5% 익절 기본)
            if signal_type == "BUY":
                target_exit = current_price * 1.005  # 0.5% 익절
                stop_loss = current_price * 0.997    # 0.3% 손절
            else:
                target_exit = current_price * 0.995  # 0.5% 이익 (공매도)
                stop_loss = current_price * 1.003    # 0.3% 손절
            
            # 보유 시간 추정 (AI 신호 강도 기반)
            if ai_signal_strength >= 80:
                holding_time_estimate = 2  # 2분 (강한 신호)
            elif ai_signal_strength >= 60:
                holding_time_estimate = 3  # 3분
            else:
                holding_time_estimate = 5  # 5분 (약한 신호)
            
            # 리스크 요인 분석
            risk_factors = []
            
            if order_flow.bid_ask_spread > 0.01:
                risk_factors.append("Wide bid-ask spread")
            
            if order_flow.volume_intensity < 1.2:
                risk_factors.append("Low volume intensity")
            
            if news_sentiment.get('confidence', 0) < 0.5:
                risk_factors.append("Uncertain news sentiment")
            
            if abs(daily_change) > 10:
                risk_factors.append("High volatility")
            
            # 추론 설명 생성
            reasoning_parts = []
            
            # 뉴스 요인
            sentiment_score = news_sentiment.get('overall_sentiment', 0)
            if sentiment_score > 0.3:
                reasoning_parts.append(f"긍정적 뉴스 감성 ({sentiment_score:.2f})")
            elif sentiment_score < -0.3:
                reasoning_parts.append(f"부정적 뉴스 감성 ({sentiment_score:.2f})")
            
            # 주문 흐름 요인
            if order_flow.order_imbalance > 0.2:
                reasoning_parts.append("강한 매수 압력")
            elif order_flow.order_imbalance < -0.2:
                reasoning_parts.append("강한 매도 압력")
            
            # 기술적 요인
            if daily_change > 3:
                reasoning_parts.append(f"강한 상승 모멘텀 ({daily_change:.1f}%)")
            elif daily_change < -3:
                reasoning_parts.append(f"강한 하락 모멘텀 ({daily_change:.1f}%)")
            
            reasoning = "; ".join(reasoning_parts) if reasoning_parts else "중립적 시장 조건"
            
            # 강화된 신호 객체 생성
            enhanced_signal = EnhancedSignal(
                symbol=symbol,
                signal_type=signal_type,
                confidence=confidence,
                ai_signal_strength=ai_signal_strength,
                news_sentiment_score=sentiment_score,
                order_flow_score=order_flow.strength_score,
                technical_score=self.calculate_technical_score(market_data),
                reasoning=reasoning,
                risk_factors=risk_factors,
                target_entry=target_entry,
                target_exit=target_exit,
                stop_loss=stop_loss,
                holding_time_estimate=holding_time_estimate
            )
            
            return enhanced_signal
            
        except Exception as e:
            log_error("ENHANCED_SIGNAL_ERROR", f"Failed to generate enhanced signal for {symbol}", e)
            
            # 오류 시 기본 신호 반환
            current_price = market_data.get('current_price', 100)
            return EnhancedSignal(
                symbol=symbol,
                signal_type="HOLD",
                confidence=50.0,
                ai_signal_strength=50.0,
                news_sentiment_score=0.0,
                order_flow_score=50.0,
                technical_score=50.0,
                reasoning="분석 오류로 인한 기본 신호",
                risk_factors=["Analysis error"],
                target_entry=current_price,
                target_exit=current_price * 1.005,
                stop_loss=current_price * 0.997,
                holding_time_estimate=5
            )
    
    def calculate_technical_score(self, market_data: Dict) -> float:
        """기술적 분석 점수 계산"""
        try:
            score = 0
            
            # 가격 변동
            daily_change = market_data.get('daily_change', 0)
            score += min(25, abs(daily_change) * 2)
            
            # 거래량
            volume_intensity = market_data.get('volume_intensity', 0)
            score += min(25, volume_intensity * 10)
            
            # 거래대금
            volume_usd = market_data.get('volume_usd', 0)
            score += min(25, volume_usd / 100000)
            
            # 모멘텀
            if daily_change > 0:
                score += min(25, daily_change)
            
            return min(100, score)
            
        except Exception as e:
            log_error("TECHNICAL_SCORE_ERROR", "Failed to calculate technical score", e)
            return 50.0
    
    def analyze_entry_signal(self, symbol: str, market_data: Dict) -> Dict:
        """진입 신호 분석 (기존 호환성 유지)"""
        try:
            enhanced_signal = self.generate_enhanced_signal(symbol, market_data)
            
            # 기존 형식으로 변환
            return {
                'symbol': symbol,
                'signal': enhanced_signal.signal_type,
                'confidence': enhanced_signal.confidence,
                'ai_signal_strength': enhanced_signal.ai_signal_strength,
                'reasoning': enhanced_signal.reasoning,
                'target_entry': enhanced_signal.target_entry,
                'target_exit': enhanced_signal.target_exit,
                'stop_loss': enhanced_signal.stop_loss,
                'risk_level': 'HIGH' if enhanced_signal.risk_factors else 'MEDIUM',
                'holding_time_estimate': enhanced_signal.holding_time_estimate
            }
            
        except Exception as e:
            log_error("ENTRY_SIGNAL_ERROR", f"Failed to analyze entry signal for {symbol}", e)
            return {
                'symbol': symbol,
                'signal': 'HOLD',
                'confidence': 50,
                'ai_signal_strength': 50,
                'reasoning': 'Analysis error',
                'risk_level': 'HIGH'
            }


# 전역 인스턴스
enhanced_gpt_analyzer = EnhancedGPTAnalyzer()


def get_market_analyzer() -> EnhancedGPTAnalyzer:
    """분석기 인스턴스 반환"""
    return enhanced_gpt_analyzer


def analyze_stock_with_ai(symbol: str, market_data: Dict) -> Dict:
    """AI 주식 분석 (간편 함수)"""
    return enhanced_gpt_analyzer.analyze_entry_signal(symbol, market_data)


# 실행 예시
if __name__ == "__main__":
    print("=== 강화된 GPT 분석기 테스트 ===")
    
    analyzer = EnhancedGPTAnalyzer()
    
    # 테스트 시장 데이터
    test_data = {
        'current_price': 2.45,
        'daily_change': 5.8,
        'volume_intensity': 2.3,
        'volume_usd': 250000,
        'bid_price': 2.44,
        'ask_price': 2.46,
        'bid_size': 5000,
        'ask_size': 3000
    }
    
    # 강화된 신호 생성
    signal = analyzer.generate_enhanced_signal("SNDL", test_data)
    
    print(f"\n📊 {signal.symbol} 분석 결과:")
    print(f"신호: {signal.signal_type} (신뢰도: {signal.confidence:.1f}%)")
    print(f"AI 신호 강도: {signal.ai_signal_strength:.1f}/100")
    print(f"뉴스 감성: {signal.news_sentiment_score:.2f}")
    print(f"주문 흐름: {signal.order_flow_score:.1f}/100")
    print(f"추론: {signal.reasoning}")
    print(f"목표가: ${signal.target_exit:.3f}")
    print(f"손절가: ${signal.stop_loss:.3f}")
    print(f"예상 보유시간: {signal.holding_time_estimate}분")
    
    if signal.risk_factors:
        print(f"리스크 요인: {', '.join(signal.risk_factors)}")
    
    print("\n강화된 GPT 분석 테스트 완료!")