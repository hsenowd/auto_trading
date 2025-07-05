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
import holidays

from config.config import (
    SCALPING_ACTIVE_HOURS, TRADING_HOURS, US_MARKET_HOLIDAYS,
    is_market_session, get_current_market_session, is_dst_active
)
from utils.logger import get_logger
from utils.api_client import get_kis_client
from utils.telegram_notifier import get_telegram_notifier
from utils.paper_trading_simulator import get_paper_trader
from utils.hybrid_validator import get_hybrid_validator
from utils.gradual_deployment import get_deployment_manager
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
        self.telegram_notifier = get_telegram_notifier()
        
        # 📊 새로운 대안 솔루션들
        self.paper_trader = get_paper_trader()
        self.hybrid_validator = get_hybrid_validator()
        self.deployment_manager = get_deployment_manager()
        
        # 시스템 상태
        self.system_running = False
        self.trading_active = False
        self.current_session = "CLOSED"
        
        # 거래 모드 설정 (모의투자 API 한계 극복)
        self.trading_mode = "paper_simulation"  # paper_simulation, real_api
        
        # 미국 휴장일 확인
        self.us_holidays = holidays.UnitedStates(years=datetime.now().year)
        
        # 시그널 핸들러 등록
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        logger.info("ScalpingSystem initialized with hybrid validation system")
        
        # 시스템 시작 알림
        current_config = self.deployment_manager.get_current_config()
        current_stage = self.deployment_manager.current_stage.value
        
        self.telegram_notifier.send_system_alert(
            "SYSTEM_INIT", 
            f"""한국투자 API 기반 스캘핑 시스템이 초기화되었습니다.

🔧 현재 배포 단계: {current_stage}
💰 최대 포지션 크기: ${current_config.get('max_position_size', 0)}
🎯 최대 포지션 수: {current_config.get('max_positions', 0)}

🛡️ 모의투자 API 한계 극복 솔루션:
• 페이퍼 트레이딩 시뮬레이터 활성화
• 하이브리드 검증 시스템 준비
• 단계별 실전 전환 관리

거래 모드: {self.trading_mode}""", 
            "INFO"
        )
    
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
            logger.info(f"썸머타임 적용: {'Yes' if is_dst_active() else 'No'}")
            logger.info("=" * 60)
            
            # 시스템 상태 확인
            if not self.system_health_check():
                logger.error("System health check failed")
                return False
            
            self.system_running = True
            
            # 시스템 시작 알림
            self.telegram_notifier.send_system_alert(
                "SYSTEM_START", 
                f"스캘핑 시스템이 시작되었습니다.\n썸머타임: {'적용' if is_dst_active() else '미적용'}", 
                "INFO"
            )
            
            # 스케줄 설정
            self.setup_schedule()
            
            # 메인 루프 시작
            self.run_main_loop()
            
        except Exception as e:
            logger.error(f"System startup failed: {e}")
            self.telegram_notifier.send_system_alert("SYSTEM_ERROR", f"시스템 시작 실패: {str(e)}", "ERROR")
            return False
    
    def system_health_check(self) -> bool:
        """시스템 건강 상태 확인"""
        try:
            logger.info("Performing system health check...")
            
            # KIS API 인증 확인
            if not self.kis_client.authenticate():
                logger.error("Failed to authenticate with KIS API")
                self.telegram_notifier.send_system_alert(
                    "AUTH_FAILED", 
                    "한국투자 API 인증에 실패했습니다.", 
                    "ERROR"
                )
                return False
            
            # 시장 상태 확인
            current_session = get_current_market_session()
            is_holiday = self.is_market_holiday()
            
            logger.info(f"Current market session: {current_session}")
            logger.info(f"Is holiday: {is_holiday}")
            
            if is_holiday:
                logger.warning("Today is a US market holiday")
                self.telegram_notifier.send_market_status(
                    "CLOSED", 
                    "미국 시장 휴장일", 
                    "다음 영업일까지 대기"
                )
            
            # 계좌 상태 확인
            balance_result = self.kis_client.get_overseas_stock_balance()
            if not balance_result:
                logger.error("Failed to get account balance")
                self.telegram_notifier.send_system_alert(
                    "BALANCE_CHECK_FAILED", 
                    "계좌 잔고 조회에 실패했습니다.", 
                    "WARNING"
                )
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
                self.telegram_notifier.send_system_alert(
                    "GPT_TEST_FAILED", 
                    f"GPT API 테스트 실패: {str(e)}", 
                    "WARNING"
                )
                return False
            
            logger.info("✅ System health check passed")
            return True
            
        except Exception as e:
            logger.error(f"System health check failed: {e}")
            self.telegram_notifier.send_system_alert(
                "HEALTH_CHECK_FAILED", 
                f"시스템 상태 점검 실패: {str(e)}", 
                "ERROR"
            )
            return False
    
    def is_market_holiday(self) -> bool:
        """미국 시장 휴장일 여부 확인"""
        today = datetime.now().date()
        
        # 주말 확인
        if today.weekday() >= 5:  # 토요일(5), 일요일(6)
            return True
        
        # 미국 연방 휴일 확인
        if today in self.us_holidays:
            return True
        
        return False
    
    def setup_schedule(self):
        """스케줄 설정 - 모든 거래 시간 커버"""
        try:
            # 시장 세션 변경 감지 (매분 체크)
            schedule.every().minute.do(self.check_market_session_change)
            
            # 스캘핑 활성 시간 설정 (동적으로 업데이트)
            self.update_scalping_schedule()
            
            # 정기적인 작업들
            schedule.every(3).minutes.do(self.periodic_screening)  # 더 자주 스크리닝
            schedule.every(1).minutes.do(self.monitor_system)
            schedule.every(30).minutes.do(self.send_position_update)  # 포지션 현황 알림
            
            # 일일 리포트 (미국 시장 마감 후)
            # 썸머타임에 따라 시간 조정
            report_time = "09:30" if is_dst_active() else "10:30"
            schedule.every().day.at(report_time).do(self.post_market_cleanup)
            
            logger.info("Scheduled tasks configured for all trading sessions")
            
        except Exception as e:
            logger.error(f"Schedule setup failed: {e}")
            self.telegram_notifier.send_system_alert(
                "SCHEDULE_ERROR", 
                f"스케줄 설정 실패: {str(e)}", 
                "ERROR"
            )
    
    def update_scalping_schedule(self):
        """스캘핑 스케줄 업데이트 (썸머타임 반영)"""
        try:
            # 기존 스캘핑 스케줄 제거
            schedule.clear('scalping')
            
            # 새로운 스캘핑 활성 시간 설정
            active_hours = SCALPING_ACTIVE_HOURS
            
            for start_time, end_time in active_hours:
                # 세션 시작
                schedule.every().day.at(start_time).do(self.start_scalping_session).tag('scalping')
                # 세션 종료
                schedule.every().day.at(end_time).do(self.end_scalping_session).tag('scalping')
            
            logger.info(f"Updated scalping schedule for {len(active_hours)} sessions")
            
        except Exception as e:
            logger.error(f"Failed to update scalping schedule: {e}")
    
    def check_market_session_change(self):
        """시장 세션 변경 감지 및 처리"""
        try:
            new_session = get_current_market_session()
            
            if new_session != self.current_session:
                logger.info(f"Market session changed: {self.current_session} -> {new_session}")
                
                # 세션 변경 알림
                self.telegram_notifier.send_market_status(
                    new_session,
                    f"{self.current_session} -> {new_session}",
                    self.get_next_session_time(new_session)
                )
                
                self.current_session = new_session
                
                # 휴장 시간에 거래 중지
                if new_session == "CLOSED" and self.trading_active:
                    self.end_scalping_session()
                
        except Exception as e:
            logger.error(f"Failed to check market session change: {e}")
    
    def get_next_session_time(self, current_session: str) -> str:
        """다음 세션 시간 반환"""
        try:
            hours = TRADING_HOURS
            
            session_order = ["CLOSED", "PRE_MARKET", "REGULAR_MARKET", "AFTER_MARKET"]
            current_idx = session_order.index(current_session) if current_session in session_order else 0
            
            if current_session == "CLOSED":
                return f"프리마켓 {hours['pre_market_start']}"
            elif current_session == "PRE_MARKET":
                return f"정규장 {hours['market_open']}"
            elif current_session == "REGULAR_MARKET":
                return f"애프터마켓 {hours['market_close']}"
            elif current_session == "AFTER_MARKET":
                return f"다음날 프리마켓 {hours['pre_market_start']}"
            
            return "알 수 없음"
            
        except Exception as e:
            logger.error(f"Failed to get next session time: {e}")
            return "알 수 없음"
    
    def run_main_loop(self):
        """메인 실행 루프"""
        logger.info("Starting main execution loop...")
        
        while self.system_running:
            try:
                # 스케줄된 작업 실행
                schedule.run_pending()
                
                # 거래 세션 중이면 실시간 거래 처리
                if self.trading_active and is_market_session():
                    self.handle_realtime_trading()
                
                # 짧은 대기
                time.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                self.telegram_notifier.send_system_alert(
                    "MAIN_LOOP_ERROR", 
                    f"메인 루프 오류: {str(e)}", 
                    "WARNING"
                )
                time.sleep(5)  # 에러 시 5초 대기
    
    def start_scalping_session(self):
        """스캘핑 세션 시작"""
        try:
            # 휴장일 체크
            if self.is_market_holiday():
                logger.warning("Market holiday - skipping scalping session")
                return
            
            current_session = get_current_market_session()
            if current_session == "CLOSED":
                logger.warning("Market is closed, skipping scalping session")
                return
            
            logger.info(f"🎯 Starting scalping session - {current_session}")
            
            # 거래 시작
            if self.scalping_trader.start_trading():
                self.trading_active = True
                logger.info("✅ Scalping session started successfully")
                
                # 세션 시작 알림
                self.telegram_notifier.send_market_status(
                    current_session,
                    "스캘핑 세션 시작",
                    self.get_next_session_time(current_session)
                )
            else:
                logger.error("Failed to start scalping session")
                self.telegram_notifier.send_system_alert(
                    "SESSION_START_FAILED", 
                    f"{current_session} 스캘핑 세션 시작 실패", 
                    "ERROR"
                )
                
        except Exception as e:
            logger.error(f"Failed to start scalping session: {e}")
            self.telegram_notifier.send_system_alert(
                "SESSION_START_ERROR", 
                f"스캘핑 세션 시작 오류: {str(e)}", 
                "ERROR"
            )
    
    def end_scalping_session(self):
        """스캘핑 세션 종료"""
        try:
            logger.info("🛑 Ending scalping session")
            
            # 거래 중지
            self.scalping_trader.stop_trading()
            self.trading_active = False
            
            # 세션 결과 로그
            status = self.scalping_trader.get_portfolio_status()
            session_pnl = status.get('daily_pnl', 0)
            win_rate = status.get('win_rate', 0)
            
            logger.info(f"Session Results - P&L: ${session_pnl:.2f}, Win Rate: {win_rate:.1f}%")
            
            # 세션 종료 알림
            self.telegram_notifier.send_market_status(
                self.current_session,
                f"스캘핑 세션 종료\n손익: ${session_pnl:+.2f} | 승률: {win_rate:.1f}%"
            )
            
            logger.info("✅ Scalping session ended")
            
        except Exception as e:
            logger.error(f"Failed to end scalping session: {e}")
            self.telegram_notifier.send_system_alert(
                "SESSION_END_ERROR", 
                f"스캘핑 세션 종료 오류: {str(e)}", 
                "ERROR"
            )
    
    def periodic_screening(self):
        """정기적인 종목 스크리닝"""
        try:
            if not self.trading_active or not is_market_session():
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
                    
                    # 매수 알림 전송
                    self.telegram_notifier.send_trade_alert(
                        symbol,
                        "BUY",
                        stock.get('current_price', 0),
                        stock.get('quantity', 0),
                        signal_score=stock.get('screening_score', 0),
                        reasoning=f"급등주 스크리닝 매수 (점수: {stock.get('screening_score', 0):.1f})"
                    )
                    break  # 한 번에 하나씩만 매수
                    
        except Exception as e:
            logger.error(f"Periodic screening failed: {e}")
    
    def send_position_update(self):
        """포지션 현황 텔레그램 전송"""
        try:
            if not self.trading_active:
                return
            
            positions = self.scalping_trader.get_position_summary()
            self.telegram_notifier.send_position_update(positions)
            
        except Exception as e:
            logger.error(f"Failed to send position update: {e}")
    
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
                self.telegram_notifier.send_system_alert(
                    "CIRCUIT_BREAKER", 
                    "서킷 브레이커가 활성화되었습니다. 거래를 일시 중단합니다.", 
                    "WARNING"
                )
            
            # 활성 포지션 수 확인
            active_positions = status.get('active_positions', 0)
            daily_pnl = status.get('daily_pnl', 0)
            
            if active_positions > 0:
                logger.info(f"📊 Active positions: {active_positions}, Daily P&L: ${daily_pnl:.2f}")
            
            # 큰 손실 발생 시 알림
            if daily_pnl < -500:  # $500 이상 손실
                self.telegram_notifier.send_system_alert(
                    "LARGE_LOSS", 
                    f"일일 손실이 ${abs(daily_pnl):.2f}에 달했습니다.", 
                    "WARNING"
                )
                
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
                report_data = self.scalping_trader.get_portfolio_status()
                
                # 텔레그램으로 일일 리포트 전송
                self.telegram_notifier.send_daily_report(report_data)
                
                # 파일 리포트도 생성
                report = generate_daily_report(self.scalping_trader)
                logger.info("Daily report generated")
                
            except Exception as e:
                logger.error(f"Failed to generate daily report: {e}")
                self.telegram_notifier.send_system_alert(
                    "REPORT_ERROR", 
                    f"일일 리포트 생성 실패: {str(e)}", 
                    "WARNING"
                )
            
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
            self.telegram_notifier.send_system_alert(
                "CLEANUP_ERROR", 
                f"장 마감 후 정리 실패: {str(e)}", 
                "ERROR"
            )
    
    def shutdown(self):
        """시스템 종료"""
        try:
            logger.info("🛑 Shutting down system...")
            
            # 거래 중지
            if self.trading_active:
                self.scalping_trader.stop_trading()
            
            self.system_running = False
            
            # 시스템 종료 알림
            self.telegram_notifier.send_system_alert(
                "SYSTEM_SHUTDOWN", 
                "스캘핑 시스템이 종료되었습니다.", 
                "INFO"
            )
            
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
            
            # 시장 상태 정보
            current_session = get_current_market_session()
            is_holiday = self.is_market_holiday()
            
            print("\n" + "="*50)
            print("📊 시장 상태 정보")
            print("="*50)
            print(f"현재 세션: {current_session}")
            print(f"썸머타임: {'적용' if is_dst_active() else '미적용'}")
            print(f"휴장일: {'예' if is_holiday else '아니오'}")
            print(f"거래 가능: {'예' if is_market_session() and not is_holiday else '아니오'}")
            
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
                
                # 테스트 알림 전송
                if self.telegram_notifier.enabled:
                    print("\n📱 텔레그램 테스트 알림 전송 중...")
                    self.telegram_notifier.send_system_alert(
                        "MANUAL_TEST", 
                        f"수동 모드 테스트\n분석 종목: {symbol}\n점수: {analysis.get('signal_score', 0)}/10", 
                        "INFO"
                    )
            
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