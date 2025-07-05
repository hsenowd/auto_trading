#!/usr/bin/env python3
"""
한국투자 Open API 기반 미국 주식 초단타 스캘핑 자동매매 시스템
GPT 분석 기반 실시간 거래 시스템

실행 방법:
    python main.py
"""

import time
import schedule
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, List

from config.config import SCALPING_ACTIVE_HOURS, TRADING_HOURS
from utils.logger import get_logger
from utils.api_client import get_kis_client
from screener.stock_screener import get_stock_screener
from analyzer.gpt_analyzer import get_market_analyzer
from trader.scalping_trader import get_scalping_trader
from report.performance_report import generate_daily_report

logger = get_logger()


class ScalpingSystem:
    """스캘핑 시스템 메인 클래스"""
    
    def __init__(self):
        self.kis_client = get_kis_client()
        self.stock_screener = get_stock_screener()
        self.market_analyzer = get_market_analyzer()
        self.scalping_trader = get_scalping_trader()
        
        # 시스템 상태
        self.system_running = False
        self.trading_active = False
        
        # 시그널 핸들러 등록
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        logger.info("ScalpingSystem initialized")
    
    def signal_handler(self, signum, frame):
        """시그널 핸들러 (Ctrl+C 등)"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.shutdown()
        sys.exit(0)
    
    def start_system(self):
        """시스템 시작"""
        try:
            logger.info("=" * 60)
            logger.info("🚀 한국투자 API 기반 미국 주식 초단타 스캘핑 자동매매 시스템 시작")
            logger.info("=" * 60)
            
            # 시스템 상태 확인
            if not self.system_health_check():
                logger.error("System health check failed")
                return False
            
            self.system_running = True
            
            # 스케줄 설정
            self.setup_schedule()
            
            # 메인 루프 시작
            self.run_main_loop()
            
        except Exception as e:
            logger.error(f"System startup failed: {e}")
            return False
    
    def system_health_check(self) -> bool:
        """시스템 건강 상태 확인"""
        try:
            logger.info("Performing system health check...")
            
            # KIS API 인증 확인
            if not self.kis_client.authenticate():
                logger.error("Failed to authenticate with KIS API")
                return False
            
            # 시장 상태 확인
            if not self.kis_client.is_market_open():
                logger.warning("Market is currently closed")
            
            # 계좌 상태 확인
            balance_result = self.kis_client.get_overseas_stock_balance()
            if not balance_result:
                logger.error("Failed to get account balance")
                return False
            
            logger.info("✅ KIS API connection successful")
            
            # GPT API 확인 (간단한 테스트)
            try:
                test_data = {
                    'current_price': 100.0,
                    'volume_intensity': 60.0,
                    'bid_ask_spread': 0.01,
                    'volume_1m': 1000,
                    'volume_5m': 5000,
                    'daily_change': 2.5
                }
                analysis = self.market_analyzer.openai_client.analyze_entry_signal("TEST", test_data)
                if analysis:
                    logger.info("✅ GPT API connection successful")
                
            except Exception as e:
                logger.warning(f"GPT API test failed: {e}")
                return False
            
            logger.info("✅ System health check passed")
            return True
            
        except Exception as e:
            logger.error(f"System health check failed: {e}")
            return False
    
    def setup_schedule(self):
        """스케줄 설정"""
        try:
            # 장 시작 전 준비 (한국 시간 기준)
            schedule.every().day.at("23:15").do(self.pre_market_setup)
            
            # 스캘핑 활성 시간 설정
            for start_time, end_time in SCALPING_ACTIVE_HOURS:
                schedule.every().day.at(start_time).do(self.start_scalping_session)
                schedule.every().day.at(end_time).do(self.end_scalping_session)
            
            # 정기적인 작업들
            schedule.every(5).minutes.do(self.periodic_screening)
            schedule.every(1).minutes.do(self.monitor_system)
            
            # 장 마감 후 정리 (한국 시간 기준)
            schedule.every().day.at("06:30").do(self.post_market_cleanup)
            
            logger.info("Scheduled tasks configured")
            
        except Exception as e:
            logger.error(f"Schedule setup failed: {e}")
    
    def run_main_loop(self):
        """메인 실행 루프"""
        logger.info("Starting main execution loop...")
        
        while self.system_running:
            try:
                # 스케줄된 작업 실행
                schedule.run_pending()
                
                # 거래 세션 중이면 실시간 거래 처리
                if self.trading_active:
                    self.handle_realtime_trading()
                
                # 짧은 대기
                time.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(5)  # 에러 시 5초 대기
    
    def pre_market_setup(self):
        """장 시작 전 준비"""
        try:
            logger.info("📋 Pre-market setup started")
            
            # 시스템 상태 초기화
            self.scalping_trader.daily_stats = {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "total_profit_loss": 0.0,
                "start_time": datetime.now(),
                "max_drawdown": 0.0,
                "current_drawdown": 0.0
            }
            
            # 급등주 사전 스크리닝
            logger.info("Pre-screening potential stocks...")
            top_stocks = self.stock_screener.get_top_stocks(20)
            
            logger.info(f"Found {len(top_stocks)} potential stocks:")
            for i, stock in enumerate(top_stocks[:5], 1):
                logger.info(f"{i}. {stock['symbol']}: {stock['screening_score']:.1f}점")
            
            logger.info("✅ Pre-market setup completed")
            
        except Exception as e:
            logger.error(f"Pre-market setup failed: {e}")
    
    def start_scalping_session(self):
        """스캘핑 세션 시작"""
        try:
            if not self.kis_client.is_market_open():
                logger.warning("Market is closed, skipping scalping session")
                return
            
            logger.info("🎯 Starting scalping session")
            
            # 거래 시작
            if self.scalping_trader.start_trading():
                self.trading_active = True
                logger.info("✅ Scalping session started successfully")
            else:
                logger.error("Failed to start scalping session")
                
        except Exception as e:
            logger.error(f"Failed to start scalping session: {e}")
    
    def end_scalping_session(self):
        """스캘핑 세션 종료"""
        try:
            logger.info("🛑 Ending scalping session")
            
            # 거래 중지
            self.scalping_trader.stop_trading()
            self.trading_active = False
            
            # 세션 결과 로그
            status = self.scalping_trader.get_portfolio_status()
            logger.info(f"Session Results - P&L: ${status.get('daily_pnl', 0):.2f}, "
                       f"Win Rate: {status.get('win_rate', 0):.1f}%")
            
            logger.info("✅ Scalping session ended")
            
        except Exception as e:
            logger.error(f"Failed to end scalping session: {e}")
    
    def periodic_screening(self):
        """정기적인 종목 스크리닝"""
        try:
            if not self.trading_active:
                return
            
            logger.info("🔍 Performing periodic screening...")
            
            # 급등주 스크리닝
            top_stocks = self.stock_screener.get_top_stocks(10)
            
            # 상위 종목들 거래 시도
            for stock in top_stocks[:3]:  # 상위 3개만 시도
                symbol = stock['symbol']
                
                # 이미 포지션이 있는 종목은 스킵
                if symbol in self.scalping_trader.active_positions:
                    continue
                
                # 거래 시도
                if self.scalping_trader.analyze_and_trade(symbol):
                    logger.info(f"✅ New position opened: {symbol}")
                    break  # 한 번에 하나씩만 매수
                    
        except Exception as e:
            logger.error(f"Periodic screening failed: {e}")
    
    def handle_realtime_trading(self):
        """실시간 거래 처리"""
        try:
            # 활성 포지션 상태 확인
            positions = self.scalping_trader.get_position_summary()
            
            if positions:
                # 실시간 모니터링 (이미 별도 스레드에서 실행 중)
                pass
                
        except Exception as e:
            logger.error(f"Realtime trading error: {e}")
    
    def monitor_system(self):
        """시스템 모니터링"""
        try:
            # 포트폴리오 상태 확인
            status = self.scalping_trader.get_portfolio_status()
            
            # 중요한 상태 변화 시 로그
            if status.get('circuit_breaker', False):
                logger.warning("⚠️ Circuit breaker is active")
            
            # 활성 포지션 수 확인
            active_positions = status.get('active_positions', 0)
            if active_positions > 0:
                logger.info(f"📊 Active positions: {active_positions}, "
                           f"Daily P&L: ${status.get('daily_pnl', 0):.2f}")
                
        except Exception as e:
            logger.error(f"System monitoring failed: {e}")
    
    def post_market_cleanup(self):
        """장 마감 후 정리"""
        try:
            logger.info("🧹 Post-market cleanup started")
            
            # 거래 중지
            if self.trading_active:
                self.scalping_trader.stop_trading()
                self.trading_active = False
            
            # 일일 리포트 생성
            try:
                report = generate_daily_report(self.scalping_trader)
                logger.info("Daily report generated")
            except Exception as e:
                logger.error(f"Failed to generate daily report: {e}")
            
            # 포트폴리오 최종 상태
            status = self.scalping_trader.get_portfolio_status()
            logger.info(f"📊 Final Daily Results:")
            logger.info(f"   Total Trades: {status.get('total_positions', 0)}")
            logger.info(f"   Daily P&L: ${status.get('daily_pnl', 0):.2f}")
            logger.info(f"   Win Rate: {status.get('win_rate', 0):.1f}%")
            logger.info(f"   Max Drawdown: ${status.get('max_drawdown', 0):.2f}")
            
            logger.info("✅ Post-market cleanup completed")
            
        except Exception as e:
            logger.error(f"Post-market cleanup failed: {e}")
    
    def shutdown(self):
        """시스템 종료"""
        try:
            logger.info("🛑 Shutting down system...")
            
            # 거래 중지
            if self.trading_active:
                self.scalping_trader.stop_trading()
            
            self.system_running = False
            
            logger.info("✅ System shutdown completed")
            
        except Exception as e:
            logger.error(f"System shutdown failed: {e}")
    
    def run_manual_mode(self):
        """수동 모드 실행 (테스트용)"""
        try:
            logger.info("🔧 Running in manual mode")
            
            # KIS API 인증
            if not self.kis_client.authenticate():
                logger.error("Failed to authenticate with KIS API")
                return
            
            # 급등주 스크리닝
            logger.info("Screening stocks...")
            top_stocks = self.stock_screener.get_top_stocks(5)
            
            print("\n" + "="*50)
            print("📊 상위 5개 급등주")
            print("="*50)
            
            for i, stock in enumerate(top_stocks, 1):
                print(f"{i}. {stock['symbol']}")
                print(f"   점수: {stock['screening_score']:.1f}")
                print(f"   현재가: ${stock['current_price']:.2f}")
                print(f"   갭상승: {stock['gap_percent']:.2f}%")
                print(f"   거래량급증: {stock['volume_spike']:.1f}배")
                print()
            
            # 첫 번째 종목 분석
            if top_stocks:
                symbol = top_stocks[0]['symbol']
                logger.info(f"Analyzing {symbol}...")
                
                analysis = self.market_analyzer.analyze_entry_signal(symbol)
                
                print(f"\n📈 {symbol} GPT 분석 결과:")
                print(f"   시그널 점수: {analysis.get('signal_score', 0)}/10")
                print(f"   추천 액션: {analysis.get('action', 'HOLD')}")
                print(f"   분석 근거: {analysis.get('reasoning', 'N/A')}")
                print(f"   신뢰도: {analysis.get('confidence', 'UNKNOWN')}")
            
            print("\n" + "="*50)
            print("Manual mode completed")
            print("="*50)
            
        except Exception as e:
            logger.error(f"Manual mode failed: {e}")


def main():
    """메인 함수"""
    try:
        # 시스템 생성
        system = ScalpingSystem()
        
        # 명령행 인수 확인
        if len(sys.argv) > 1:
            if sys.argv[1] == "--manual":
                # 수동 모드 실행
                system.run_manual_mode()
                return
            elif sys.argv[1] == "--test":
                # 테스트 모드 실행
                system.system_health_check()
                return
        
        # 정상 모드 실행
        system.start_system()
        
    except Exception as e:
        logger.error(f"Application failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()