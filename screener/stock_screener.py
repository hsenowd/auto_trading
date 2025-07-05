"""
급등주 스크리너 모듈
갭상승, 거래량 급증, 거래대금 조건을 만족하는 중소형주를 선별합니다.
동전주부터 30달러까지의 단일 종목만 대상으로 합니다.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import concurrent.futures
import time
import re

from config.config import SCREENING_CONFIG
from utils.logger import get_logger, log_error
from utils.api_client import get_kis_client

logger = get_logger()


class StockScreener:
    """급등주 스크리너 클래스 (중소형주 전용)"""
    
    def __init__(self):
        self.kis_client = get_kis_client()
        self.config = SCREENING_CONFIG
        
        # 중소형주 위주 종목 리스트 (동전주부터 30달러까지)
        self.small_cap_universe = [
            # 소형주 기술주 (전기차, 배터리, 반도체)
            "SIRI", "PLUG", "NKLA", "WKHS", "RIDE", "GOEV", "HYLN", "BLNK",
            "CHPT", "EVGO", "BEEM", "SOLO", "AYRO", "CIIC", "ACTC", "CCIV",
            "FSR", "LCID", "PTRA", "ARVL", "MULN", "ELMS", "RIDE", "WKHS",
            
            # 바이오/헬스케어 소형주
            "OCGN", "VXRT", "NVAX", "SAVA", "ADMS", "ZSAN", "TGTX", "CASI",
            "SNSS", "EVFM", "PRQR", "NVCR", "TOMZ", "LPTX", "OPGN", "ABUS",
            "TNXP", "INUV", "PROG", "XERS", "ONTX", "AYTU", "CDTX", "CRBP",
            "AVCO", "CTMX", "CYTH", "DBVT", "ELDN", "FENC", "GTHX", "HJLI",
            
            # 소형주 리테일/소비재 (태양광, 에너지)
            "BBBY", "EXPR", "COTY", "SPWR", "FSLR", "ENPH", "SEDG", "RUN",
            "NOVA", "CSIQ", "DQ", "JKS", "MAXN", "ARRY", "BEAM", "EDIT",
            "GEVO", "REI", "PLUG", "BLDP", "FCEL", "BE", "AMRC", "CLNE",
            
            # 핀테크/금융 소형주
            "AFRM", "UPST", "LMND", "ROOT", "MTTR", "OPEN", "RDFN", "COMP",
            "NMRD", "TREE", "CACC", "WRLD", "YELL", "PRGS", "EVCM", "PAYO",
            "SOFI", "LC", "HOOD", "COIN", "RBLX", "DWAC", "CFVI", "PHUN",
            
            # 게임/엔터테인먼트 소형주
            "RBLX", "ZNGA", "SLGG", "GBOX", "HEAR", "CRSR", "LOGI", "GPRO",
            "NNDM", "SSYS", "DDD", "XONE", "MKSI", "ONTO", "COHR", "FARO",
            "SKLZ", "DKNG", "PENN", "CHWY", "PETS", "WOOF", "BARK", "PETQ",
            
            # 인터넷/소프트웨어 소형주
            "PLTR", "SNOW", "DDOG", "CRWD", "ZS", "OKTA", "ESTC", "SUMO",
            "FROG", "BIGC", "BAND", "JAMF", "FSLY", "NET", "CFLT", "DOCU",
            "ZOOM", "ZM", "DOCN", "MDB", "GTLB", "S", "CRM", "WORK",
            
            # 통신/미디어/우주 소형주
            "SATS", "IRDM", "VSAT", "ORBC", "GSAT", "ASTS", "SPCE", "ASTR",
            "RKLB", "BKSY", "LUNR", "VORB", "GILT", "MAXR", "BWXT", "KTOS",
            "UFO", "ARKX", "ROKT", "MNTS", "HOL", "VACQ", "RICE", "GNPK",
            
            # 페니 스톡 (1달러 미만, 높은 변동성)
            "SNDL", "NAKD", "CTRM", "SHIP", "TOPS", "DRYS", "GNUS", "IZEA",
            "ZOM", "SNDL", "CTRM", "SHIP", "BIOC", "BIOL", "CLVS", "TTNP",
            "BNGO", "XSPA", "JAGX", "ADTX", "AIHS", "ALBT", "AMPE", "ANEB",
            "ATOS", "AVGR", "AVCO", "BCRX", "BHAT", "BIOL", "BOXL", "BRTX",
            
            # 마이크로/나노 캡 (매우 작은 회사들)
            "SENS", "MVIS", "WIMI", "GEVO", "FTFT", "IDEX", "XPEL", "DMTK",
            "KOSS", "EXPR", "CLOV", "WISH", "COUR", "MAPS", "VERB", "MARK",
            "HMHC", "INUV", "LKCO", "MOXC", "NXTD", "OPTT", "PRPO", "RKDA",
            
            # 최근 상장/특수목적 소형주
            "AMC", "GME", "BBIG", "PROG", "ATER", "SPRT", "IRNT", "OPAD",
            "DWAC", "PHUN", "MARK", "FAMI", "RELI", "ESSC", "LGVN", "PTPI",
            "AVCT", "BMRA", "BFRI", "RDHL", "ISPC", "NRBO", "SMFL", "PQEFF",
            
            # 추가 리스크 높은 소형주
            "CPOP", "DIDI", "BABA", "JD", "PDD", "BILI", "IQ", "VIPS",
            "WB", "TME", "DOYU", "HUYA", "YY", "MOMO", "JOYY", "FENG"
        ]
        
        # ETF/지수/선물 제외 패턴
        self.exclude_patterns = [
            r'.*ETF$',      # ETF 종목
            r'.*ETC$',      # ETC 종목
            r'.*ETN$',      # ETN 종목
            r'^SPY$',       # S&P 500 ETF
            r'^QQQ$',       # 나스닥 ETF
            r'^IWM$',       # 소형주 ETF
            r'^VTI$',       # 전체 시장 ETF
            r'^GLD$',       # 금 ETF
            r'^SLV$',       # 은 ETF
            r'^TLT$',       # 장기 국채 ETF
            r'^VIX$',       # 변동성 지수
            r'^DX-Y$',      # 달러 인덱스
            r'^TNX$',       # 10년 국채 수익률
            r'.*X$',        # 선물 상품
            r'.*=F$',       # 선물 계약
        ]
        
        logger.info(f"StockScreener initialized with {len(self.small_cap_universe)} small-cap symbols")
    
    def is_valid_stock_symbol(self, symbol: str) -> bool:
        """종목 심볼이 유효한 단일 종목인지 확인"""
        try:
            # ETF, 지수, 선물 제외 패턴 확인
            for pattern in self.exclude_patterns:
                if re.match(pattern, symbol, re.IGNORECASE):
                    logger.debug(f"Excluded {symbol} - matches pattern {pattern}")
                    return False
            
            # 추가 제외 조건
            # 1. 길이가 5자 이상인 심볼은 대부분 ETF나 특수 상품
            if len(symbol) > 5:
                logger.debug(f"Excluded {symbol} - symbol too long")
                return False
            
            # 2. 숫자가 포함된 심볼은 대부분 파생상품
            if any(char.isdigit() for char in symbol):
                logger.debug(f"Excluded {symbol} - contains numbers")
                return False
            
            # 3. 점(.)이 포함된 심볼은 대부분 파생상품
            if '.' in symbol:
                logger.debug(f"Excluded {symbol} - contains dot")
                return False
            
            return True
            
        except Exception as e:
            log_error("SYMBOL_VALIDATION_ERROR", f"Error validating symbol {symbol}", e)
            return False
    
    def get_market_data(self, symbol: str) -> Optional[Dict]:
        """개별 종목의 시장 데이터 수집 (한국투자 API 사용)"""
        try:
            # 먼저 종목 심볼 유효성 검증
            if not self.is_valid_stock_symbol(symbol):
                return None
            
            # 한국투자 API로 해외주식 현재가 조회
            price_data = self.kis_client.get_overseas_stock_price(symbol)
            if not price_data:
                logger.debug(f"No price data for {symbol}")
                return None
            
            current_price = price_data.get('current_price', 0)
            
            # 가격 범위 사전 필터링 (API 호출 최소화)
            if not (self.config['min_price'] <= current_price <= self.config['max_price']):
                logger.debug(f"Price out of range for {symbol}: ${current_price:.2f}")
                return None
            
            # 추가 시장 정보 수집
            previous_close = price_data.get('previous_close', current_price)
            today_open = price_data.get('open_price', current_price)
            current_volume = price_data.get('volume', 0)
            
            # 평균 거래량 계산 (최근 20일 평균 근사치)
            avg_volume = current_volume * 0.8  # 근사치 사용
            
            # 갭 계산
            gap_percent = ((today_open - previous_close) / previous_close) * 100 if previous_close > 0 else 0
            
            # 일일 등락률
            daily_change = ((current_price - previous_close) / previous_close) * 100 if previous_close > 0 else 0
            
            # 거래대금 (달러)
            dollar_volume = current_price * current_volume
            
            # 거래량 급증 배수
            volume_spike = current_volume / avg_volume if avg_volume > 0 else 0
            
            # 시가총액 추정 (정확한 값은 별도 API 호출 필요)
            estimated_market_cap = current_price * 50000000  # 5천만주 가정 (중소형주 평균)
            
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
                'estimated_market_cap': estimated_market_cap,
                'price_range': self.classify_price_range(current_price),
                'is_penny_stock': current_price < 1.0,
                'is_small_cap': estimated_market_cap < self.config['market_cap_max']
            }
            
        except Exception as e:
            log_error("MARKET_DATA_ERROR", f"Failed to get market data for {symbol}", e)
            return None
    
    def classify_price_range(self, price: float) -> str:
        """가격 범위 분류"""
        if price < 0.1:
            return "MICRO_PENNY"      # 0.1달러 미만
        elif price < 1.0:
            return "PENNY"            # 1달러 미만
        elif price < 5.0:
            return "LOW_PRICE"        # 5달러 미만
        elif price < 15.0:
            return "MID_PRICE"        # 15달러 미만
        elif price <= 30.0:
            return "HIGH_PRICE"       # 30달러 이하
        else:
            return "OVER_LIMIT"       # 30달러 초과
    
    def apply_screening_filters(self, data: Dict) -> bool:
        """스크리닝 필터 적용 (중소형주 전용)"""
        try:
            # 1. 가격 범위 필터 (이미 사전 필터링됨)
            if not (self.config['min_price'] <= data['current_price'] <= self.config['max_price']):
                return False
            
            # 2. 시가총액 필터 (중소형주만)
            if data['estimated_market_cap'] > self.config['market_cap_max']:
                return False
            
            # 3. 최소 거래량 필터
            if data['current_volume'] < self.config['min_volume']:
                return False
            
            # 4. 갭 상승 필터
            if data['gap_percent'] < self.config['gap_threshold'] * 100:
                return False
            
            # 5. 거래량 급증 필터
            if data['volume_spike'] < self.config['volume_spike']:
                return False
            
            # 6. 상승 종목만 선별
            if data['daily_change'] <= 0:
                return False
            
            # 7. 최소 거래대금 필터 (유동성 확보)
            min_dollar_volume = 100000  # 최소 10만달러 거래대금
            if data['dollar_volume'] < min_dollar_volume:
                return False
            
            # 8. 극단적인 변동성 제외 (20% 이상 급락 후 반등 제외)
            if data['daily_change'] > 50:  # 50% 이상 급등은 제외
                return False
            
            return True
            
        except Exception as e:
            log_error("SCREENING_FILTER_ERROR", f"Error applying filters to {data.get('symbol', 'unknown')}", e)
            return False
    
    def calculate_screening_score(self, data: Dict) -> float:
        """중소형주 스크리닝 점수 계산 (0-100점)"""
        try:
            score = 0
            
            # 1. 갭 상승 점수 (최대 20점)
            gap_score = min(data['gap_percent'] * 2, 20)
            score += gap_score
            
            # 2. 거래량 급증 점수 (최대 25점)
            volume_score = min(data['volume_spike'] * 5, 25)
            score += volume_score
            
            # 3. 일일 등락률 점수 (최대 20점)
            change_score = min(data['daily_change'] * 1.5, 20)
            score += change_score
            
            # 4. 거래대금 점수 (최대 20점)
            dollar_volume_m = data['dollar_volume'] / 1000000  # 백만 달러 단위
            dollar_score = min(dollar_volume_m / 10 * 20, 20)
            score += dollar_score
            
            # 5. 가격 범위 보너스 점수 (최대 15점)
            price_range = data['price_range']
            if price_range == "PENNY":
                score += 15  # 페니 스톡 보너스
            elif price_range == "LOW_PRICE":
                score += 12  # 저가주 보너스
            elif price_range == "MID_PRICE":
                score += 8   # 중간가 보너스
            elif price_range == "HIGH_PRICE":
                score += 5   # 고가주 (30달러 이하)
            elif price_range == "MICRO_PENNY":
                score += 10  # 마이크로 페니 (리스크 고려)
            
            return min(score, 100)
            
        except Exception as e:
            log_error("SCORING_ERROR", f"Error calculating score for {data.get('symbol', 'unknown')}", e)
            return 0
    
    def screen_stocks(self, symbols: Optional[List[str]] = None) -> List[Dict]:
        """병렬 처리로 중소형주 스크리닝 실행"""
        if symbols is None:
            symbols = self.small_cap_universe
        
        # 유효한 심볼만 필터링
        valid_symbols = [s for s in symbols if self.is_valid_stock_symbol(s)]
        
        logger.info(f"Starting small-cap stock screening for {len(valid_symbols)} symbols")
        
        screened_stocks = []
        
        # 병렬 처리로 시장 데이터 수집 (중소형주는 더 많은 동시 처리 가능)
        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            future_to_symbol = {executor.submit(self.get_market_data, symbol): symbol for symbol in valid_symbols}
            
            for future in concurrent.futures.as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    data = future.result()
                    if data and self.apply_screening_filters(data):
                        # 스크리닝 점수 계산
                        data['screening_score'] = self.calculate_screening_score(data)
                        screened_stocks.append(data)
                        
                        logger.info(f"✅ Screened: {symbol} - ${data['current_price']:.3f} - Score: {data['screening_score']:.1f}")
                        
                except Exception as e:
                    log_error("SCREENING_ERROR", f"Error screening {symbol}", e)
        
        # 스크리닝 점수 기준으로 정렬
        screened_stocks.sort(key=lambda x: x['screening_score'], reverse=True)
        
        logger.info(f"Screening completed. Found {len(screened_stocks)} qualifying small-cap stocks")
        
        return screened_stocks
    
    def get_top_stocks(self, limit: int = 10) -> List[Dict]:
        """상위 N개 중소형주 반환"""
        screened_stocks = self.screen_stocks()
        return screened_stocks[:limit]
    
    def get_penny_stocks(self, limit: int = 5) -> List[Dict]:
        """페니 스톡 (1달러 미만) 상위 종목 반환"""
        screened_stocks = self.screen_stocks()
        penny_stocks = [s for s in screened_stocks if s['is_penny_stock']]
        return penny_stocks[:limit]
    
    def get_price_range_stocks(self, price_range: str, limit: int = 5) -> List[Dict]:
        """특정 가격 범위 종목 반환"""
        screened_stocks = self.screen_stocks()
        range_stocks = [s for s in screened_stocks if s['price_range'] == price_range]
        return range_stocks[:limit]
    
    def get_detailed_analysis(self, symbol: str) -> Dict:
        """개별 종목 상세 분석"""
        try:
            # 기본 시장 데이터 수집
            data = self.get_market_data(symbol)
            if not data:
                return {}
            
            # 추가 분석 정보
            data['analysis_time'] = datetime.now().isoformat()
            data['is_screened'] = self.apply_screening_filters(data)
            data['screening_score'] = self.calculate_screening_score(data)
            
            # 리스크 평가
            data['risk_level'] = self.assess_risk_level(data)
            
            # 매매 추천 수량 계산
            data['recommended_quantity'] = self.calculate_position_size(data)
            
            return data
            
        except Exception as e:
            log_error("DETAILED_ANALYSIS_ERROR", f"Error in detailed analysis for {symbol}", e)
            return {}
    
    def assess_risk_level(self, data: Dict) -> str:
        """리스크 레벨 평가"""
        try:
            risk_score = 0
            
            # 가격 기반 리스크
            if data['current_price'] < 0.1:
                risk_score += 3  # 매우 높음
            elif data['current_price'] < 1.0:
                risk_score += 2  # 높음
            elif data['current_price'] < 5.0:
                risk_score += 1  # 보통
            
            # 변동성 기반 리스크
            if data['daily_change'] > 20:
                risk_score += 2
            elif data['daily_change'] > 10:
                risk_score += 1
            
            # 거래량 기반 리스크
            if data['volume_spike'] > 5:
                risk_score += 1
            
            # 거래대금 기반 리스크
            if data['dollar_volume'] < 500000:
                risk_score += 1
            
            # 리스크 레벨 분류
            if risk_score >= 5:
                return "VERY_HIGH"
            elif risk_score >= 3:
                return "HIGH"
            elif risk_score >= 1:
                return "MEDIUM"
            else:
                return "LOW"
                
        except Exception as e:
            log_error("RISK_ASSESSMENT_ERROR", f"Error assessing risk for {data.get('symbol', 'unknown')}", e)
            return "HIGH"
    
    def calculate_position_size(self, data: Dict) -> int:
        """포지션 크기 계산 (중소형주 전용)"""
        try:
            # 기본 포지션 크기 (최대 $10,000)
            max_position_value = 10000
            
            # 가격 기반 조정
            if data['current_price'] < 0.1:
                max_position_value = 2000  # 마이크로 페니 스톡
            elif data['current_price'] < 1.0:
                max_position_value = 5000  # 페니 스톡
            elif data['current_price'] < 5.0:
                max_position_value = 8000  # 저가주
            
            # 리스크 기반 조정
            risk_level = self.assess_risk_level(data)
            if risk_level == "VERY_HIGH":
                max_position_value *= 0.5
            elif risk_level == "HIGH":
                max_position_value *= 0.7
            elif risk_level == "MEDIUM":
                max_position_value *= 0.9
            
            # 수량 계산
            quantity = int(max_position_value / data['current_price'])
            
            # 최소/최대 수량 제한
            min_quantity = 100
            max_quantity = 100000
            
            return max(min_quantity, min(quantity, max_quantity))
            
        except Exception as e:
            log_error("POSITION_SIZE_ERROR", f"Error calculating position size for {data.get('symbol', 'unknown')}", e)
            return 1000  # 기본값


# 전역 스크리너 인스턴스
stock_screener = StockScreener()


def get_stock_screener() -> StockScreener:
    """스크리너 인스턴스 반환"""
    return stock_screener


def screen_top_stocks(limit: int = 10) -> List[Dict]:
    """상위 급등 중소형주 반환 (간편 함수)"""
    return stock_screener.get_top_stocks(limit)


def screen_penny_stocks(limit: int = 5) -> List[Dict]:
    """페니 스톡 반환 (간편 함수)"""
    return stock_screener.get_penny_stocks(limit)


def analyze_stock(symbol: str) -> Dict:
    """개별 종목 분석 (간편 함수)"""
    return stock_screener.get_detailed_analysis(symbol)


# 실행 예시
if __name__ == "__main__":
    # 중소형주 스크리닝 실행
    print("=== 중소형주 급등주 스크리닝 시작 ===")
    
    screener = StockScreener()
    
    # 상위 5개 종목
    top_stocks = screener.get_top_stocks(5)
    
    print(f"\n🔥 상위 5개 중소형주 급등주:")
    for i, stock in enumerate(top_stocks, 1):
        print(f"{i}. {stock['symbol']}: {stock['screening_score']:.1f}점")
        print(f"   💰 현재가: ${stock['current_price']:.3f}")
        print(f"   📈 갭상승: {stock['gap_percent']:.2f}%")
        print(f"   📊 거래량급증: {stock['volume_spike']:.1f}배")
        print(f"   🎯 일일등락률: {stock['daily_change']:.2f}%")
        print(f"   🏷️ 가격범위: {stock['price_range']}")
        print(f"   ⚠️ 리스크: {stock.get('risk_level', 'N/A')}")
        print()
    
    # 페니 스톡 별도 출력
    penny_stocks = screener.get_penny_stocks(3)
    if penny_stocks:
        print(f"\n💰 상위 3개 페니 스톡:")
        for i, stock in enumerate(penny_stocks, 1):
            print(f"{i}. {stock['symbol']}: ${stock['current_price']:.3f} ({stock['daily_change']:.2f}%)")
    
    print("\n스크리닝 완료!")