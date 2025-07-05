"""
스캘핑 시스템 테스트 코드
주요 기능들에 대한 단위 테스트와 통합 테스트
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from screener.stock_screener import StockScreener
from analyzer.gpt_analyzer import MarketDataAnalyzer
from trader.scalping_trader import ScalpingTrader, Position
from utils.api_client import AlpacaClient, OpenAIClient
from config.config import SCREENING_CONFIG, SCALPING_CONFIG


class TestStockScreener(unittest.TestCase):
    """주식 스크리너 테스트"""
    
    def setUp(self):
        self.screener = StockScreener()
    
    def test_screening_filter_valid_stock(self):
        """유효한 주식 필터링 테스트"""
        valid_data = {
            'current_price': 50.0,
            'current_volume': 2000000,
            'gap_percent': 5.0,
            'volume_spike': 3.0,
            'daily_change': 2.0
        }
        
        result = self.screener.apply_screening_filters(valid_data)
        self.assertTrue(result)
    
    def test_screening_filter_invalid_stock(self):
        """유효하지 않은 주식 필터링 테스트"""
        invalid_data = {
            'current_price': 1.0,  # 너무 낮은 가격
            'current_volume': 100000,  # 너무 낮은 거래량
            'gap_percent': 1.0,  # 너무 낮은 갭
            'volume_spike': 1.0,  # 너무 낮은 거래량 급증
            'daily_change': -1.0  # 하락
        }
        
        result = self.screener.apply_screening_filters(invalid_data)
        self.assertFalse(result)
    
    def test_screening_score_calculation(self):
        """스크리닝 점수 계산 테스트"""
        test_data = {
            'gap_percent': 5.0,
            'volume_spike': 3.0,
            'daily_change': 4.0,
            'dollar_volume': 50000000  # 5천만 달러
        }
        
        score = self.screener.calculate_screening_score(test_data)
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)
    
    @patch('screener.stock_screener.yf.Ticker')
    def test_get_market_data_success(self, mock_ticker):
        """시장 데이터 수집 성공 테스트"""
        # Mock 데이터 설정
        mock_ticker_instance = Mock()
        mock_ticker.return_value = mock_ticker_instance
        
        # 히스토리 데이터 Mock
        mock_hist = pd.DataFrame({
            'Close': [100.0, 105.0],
            'Volume': [1000000, 2000000],
            'Open': [99.0, 104.0]
        })
        mock_ticker_instance.history.return_value = mock_hist
        
        # 정보 데이터 Mock
        mock_info = {
            'currentPrice': 105.0,
            'volume': 2000000,
            'open': 104.0,
            'marketCap': 1000000000,
            'sector': 'Technology'
        }
        mock_ticker_instance.info = mock_info
        
        result = self.screener.get_market_data("TSLA")
        self.assertIsNotNone(result)
        if result:  # None 체크 추가
            self.assertEqual(result['symbol'], 'TSLA')
            self.assertEqual(result['current_price'], 105.0)


class TestMarketDataAnalyzer(unittest.TestCase):
    """시장 데이터 분석기 테스트"""
    
    def setUp(self):
        self.analyzer = MarketDataAnalyzer()
    
    def test_validate_analysis_entry(self):
        """매수 분석 검증 테스트"""
        analysis = {
            'signal_score': 8.5,
            'reasoning': 'Strong upward momentum',
            'action': 'BUY'
        }
        
        validated = self.analyzer.validate_analysis(analysis, 'entry')
        
        self.assertEqual(validated['signal_score'], 8.5)
        self.assertEqual(validated['action'], 'BUY')
        self.assertEqual(validated['confidence'], 'HIGH')
    
    def test_validate_analysis_exit(self):
        """매도 분석 검증 테스트"""
        analysis = {
            'exit_score': 7.0,
            'reasoning': 'Profit taking opportunity',
            'action': 'SELL'
        }
        
        validated = self.analyzer.validate_analysis(analysis, 'exit')
        
        self.assertEqual(validated['exit_score'], 7.0)
        self.assertEqual(validated['action'], 'SELL')
        self.assertEqual(validated['confidence'], 'MEDIUM')
    
    def test_calculate_confidence(self):
        """신뢰도 계산 테스트"""
        self.assertEqual(self.analyzer.calculate_confidence(9.0), 'HIGH')
        self.assertEqual(self.analyzer.calculate_confidence(6.5), 'MEDIUM')
        self.assertEqual(self.analyzer.calculate_confidence(4.5), 'LOW')
        self.assertEqual(self.analyzer.calculate_confidence(2.0), 'VERY_LOW')
    
    def test_save_analysis_history(self):
        """분석 히스토리 저장 테스트"""
        symbol = 'TSLA'
        analysis = {'signal_score': 8.0, 'action': 'BUY'}
        market_data = {'current_price': 100.0}
        
        self.analyzer.save_analysis_history(symbol, 'entry', analysis, market_data)
        
        history = self.analyzer.get_analysis_history(symbol)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['signal_type'], 'entry')


class TestScalpingTrader(unittest.TestCase):
    """스캘핑 트레이더 테스트"""
    
    def setUp(self):
        self.trader = ScalpingTrader()
    
    def test_calculate_position_size(self):
        """포지션 크기 계산 테스트"""
        price = 100.0
        position_size = self.trader.calculate_position_size(price)
        
        self.assertGreater(position_size, 0)
        self.assertLessEqual(position_size * price, SCALPING_CONFIG['max_position_size'])
    
    def test_position_creation(self):
        """포지션 생성 테스트"""
        position = Position(
            symbol='TSLA',
            entry_price=100.0,
            quantity=10,
            entry_time=datetime.now(),
            target_price=105.0,
            stop_loss_price=97.0,
            order_id='test123'
        )
        
        self.assertEqual(position.symbol, 'TSLA')
        self.assertEqual(position.entry_price, 100.0)
        self.assertEqual(position.quantity, 10)
        self.assertEqual(position.target_price, 105.0)
        self.assertEqual(position.stop_loss_price, 97.0)
    
    def test_position_to_dict(self):
        """포지션 딕셔너리 변환 테스트"""
        position = Position(
            symbol='TSLA',
            entry_price=100.0,
            quantity=10,
            entry_time=datetime.now(),
            target_price=105.0,
            stop_loss_price=97.0,
            order_id='test123'
        )
        
        pos_dict = position.to_dict()
        
        self.assertEqual(pos_dict['symbol'], 'TSLA')
        self.assertEqual(pos_dict['entry_price'], 100.0)
        self.assertEqual(pos_dict['quantity'], 10)
    
    def test_update_daily_stats(self):
        """일일 통계 업데이트 테스트"""
        initial_trades = self.trader.daily_stats['total_trades']
        
        # 이익 포지션 테스트
        profit_position = Position(
            symbol='TSLA',
            entry_price=100.0,
            quantity=10,
            entry_time=datetime.now(),
            target_price=105.0,
            stop_loss_price=97.0,
            order_id='test123'
        )
        profit_position.profit_loss = 50.0
        
        self.trader.update_daily_stats(profit_position)
        
        self.assertEqual(self.trader.daily_stats['total_trades'], initial_trades + 1)
        self.assertEqual(self.trader.daily_stats['winning_trades'], 1)
        self.assertEqual(self.trader.daily_stats['total_profit_loss'], 50.0)


class TestAPIClients(unittest.TestCase):
    """API 클라이언트 테스트"""
    
    def setUp(self):
        self.alpaca_client = AlpacaClient()
        self.openai_client = OpenAIClient()
    
    @patch('utils.api_client.tradeapi.REST')
    def test_alpaca_client_initialization(self, mock_rest):
        """Alpaca 클라이언트 초기화 테스트"""
        mock_rest.return_value = Mock()
        client = AlpacaClient()
        self.assertIsNotNone(client.api)
        self.assertIsNotNone(client.data_api)
    
    def test_openai_client_initialization(self):
        """OpenAI 클라이언트 초기화 테스트"""
        client = OpenAIClient()
        self.assertIsNotNone(client)


class TestIntegration(unittest.TestCase):
    """통합 테스트"""
    
    def setUp(self):
        self.screener = StockScreener()
        self.analyzer = MarketDataAnalyzer()
        self.trader = ScalpingTrader()
    
    @patch('screener.stock_screener.yf.Ticker')
    @patch('utils.api_client.openai.ChatCompletion.create')
    def test_full_trading_workflow(self, mock_openai, mock_ticker):
        """전체 거래 워크플로우 테스트"""
        # Mock 데이터 설정
        mock_ticker_instance = Mock()
        mock_ticker.return_value = mock_ticker_instance
        
        # 히스토리 데이터 Mock
        mock_hist = pd.DataFrame({
            'Close': [100.0, 105.0],
            'Volume': [1000000, 2000000],
            'Open': [99.0, 104.0]
        })
        mock_ticker_instance.history.return_value = mock_hist
        
        # 정보 데이터 Mock
        mock_info = {
            'currentPrice': 105.0,
            'volume': 2000000,
            'open': 104.0,
            'marketCap': 1000000000,
            'sector': 'Technology'
        }
        mock_ticker_instance.info = mock_info
        
        # OpenAI API Mock
        mock_openai.return_value = Mock()
        mock_openai.return_value.choices = [Mock()]
        mock_openai.return_value.choices[0].message.content = '{"signal_score": 8, "reasoning": "Strong momentum", "action": "BUY"}'
        
        # 1. 주식 스크리닝
        stocks = self.screener.screen_stocks(['TSLA'])
        self.assertGreater(len(stocks), 0)
        
        # 2. 시장 데이터 분석
        market_data = self.analyzer.collect_market_data('TSLA')
        self.assertIsNotNone(market_data)
        
        # 3. GPT 분석
        analysis = self.analyzer.analyze_entry_signal('TSLA')
        self.assertIsNotNone(analysis)


class TestBacktesting(unittest.TestCase):
    """백테스트 테스트"""
    
    def setUp(self):
        self.test_data = self.create_test_data()
    
    def create_test_data(self):
        """테스트용 데이터 생성"""
        dates = pd.date_range('2024-01-01', periods=100, freq='1H')
        prices = [100.0]
        
        # 간단한 랜덤 워크 생성
        import random
        for i in range(99):
            change = random.uniform(-0.02, 0.02)
            prices.append(prices[-1] * (1 + change))
        
        return pd.DataFrame({
            'timestamp': dates,
            'price': prices,
            'volume': [random.randint(50000, 200000) for _ in range(100)]
        })
    
    def test_backtest_data_preparation(self):
        """백테스트 데이터 준비 테스트"""
        self.assertEqual(len(self.test_data), 100)
        self.assertIn('timestamp', self.test_data.columns)
        self.assertIn('price', self.test_data.columns)
        self.assertIn('volume', self.test_data.columns)
    
    def test_simple_strategy_backtest(self):
        """간단한 전략 백테스트"""
        # 간단한 이동평균 전략
        window = 10
        self.test_data['ma'] = self.test_data['price'].rolling(window).mean()
        
        # 매수/매도 신호 생성
        self.test_data['signal'] = 0
        self.test_data.loc[self.test_data['price'] > self.test_data['ma'], 'signal'] = 1
        
        # 신호 생성 확인
        signals = self.test_data['signal'].sum()
        self.assertGreater(signals, 0)


def run_all_tests():
    """모든 테스트 실행"""
    # 테스트 스위트 생성
    suite = unittest.TestSuite()
    
    # 테스트 클래스들 추가
    test_classes = [
        TestStockScreener,
        TestMarketDataAnalyzer,
        TestScalpingTrader,
        TestAPIClients,
        TestIntegration,
        TestBacktesting
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # 테스트 실행
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    print("=" * 60)
    print("🧪 미국 주식 스캘핑 시스템 테스트 시작")
    print("=" * 60)
    
    success = run_all_tests()
    
    if success:
        print("\n✅ 모든 테스트 통과!")
    else:
        print("\n❌ 일부 테스트 실패!")
        
    print("=" * 60)