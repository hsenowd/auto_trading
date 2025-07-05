"""
텔레그램 알림 모듈
거래 알림, 일일 리포트 등을 텔레그램으로 전송합니다.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional
from telegram import Bot
from telegram.error import TelegramError

from config.config import TELEGRAM_CONFIG
from utils.logger import get_logger, log_error

logger = get_logger()


class TelegramNotifier:
    """텔레그램 알림 클래스"""
    
    def __init__(self):
        self.bot_token = TELEGRAM_CONFIG["bot_token"]
        self.chat_id = TELEGRAM_CONFIG["chat_id"]
        self.enabled = TELEGRAM_CONFIG["enabled"]
        
        if self.enabled and self.bot_token and self.chat_id:
            self.bot = Bot(token=self.bot_token)
            logger.info("Telegram notifier initialized")
        else:
            self.bot = None
            if self.enabled:
                logger.warning("Telegram notifier disabled - missing token or chat_id")
            else:
                logger.info("Telegram notifier disabled by configuration")
    
    async def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """텔레그램 메시지 전송"""
        if not self.bot:
            return False
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode
            )
            return True
            
        except TelegramError as e:
            log_error("TELEGRAM_SEND_ERROR", f"Failed to send telegram message", e)
            return False
        except Exception as e:
            log_error("TELEGRAM_GENERAL_ERROR", f"Unexpected error in telegram send", e)
            return False
    
    def send_message_sync(self, message: str, parse_mode: str = "HTML") -> bool:
        """동기식 메시지 전송 (기존 코드와 호환성)"""
        if not self.bot:
            return False
        
        try:
            # 새로운 이벤트 루프에서 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.send_message(message, parse_mode))
            loop.close()
            return result
            
        except Exception as e:
            log_error("TELEGRAM_SYNC_ERROR", f"Failed to send telegram message sync", e)
            return False
    
    def send_trade_alert(self, symbol: str, action: str, price: float, quantity: int, 
                        signal_score: Optional[float] = None, reasoning: Optional[str] = None) -> bool:
        """거래 알림 전송"""
        try:
            # 이모지 설정
            action_emoji = "🟢" if action.upper() == "BUY" else "🔴"
            action_kr = "매수" if action.upper() == "BUY" else "매도"
            
            message = f"""
{action_emoji} <b>{action_kr} 알림</b>

📊 <b>종목:</b> {symbol}
💰 <b>가격:</b> ${price:.2f}
📈 <b>수량:</b> {quantity:,}주
💵 <b>금액:</b> ${price * quantity:,.2f}
⏰ <b>시간:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            if signal_score is not None:
                message += f"🎯 <b>시그널 점수:</b> {signal_score:.1f}/10\n"
            
            if reasoning:
                message += f"📝 <b>분석 근거:</b> {reasoning[:100]}...\n"
            
            return self.send_message_sync(message)
            
        except Exception as e:
            log_error("TRADE_ALERT_ERROR", f"Failed to send trade alert for {symbol}", e)
            return False
    
    def send_daily_report(self, report_data: Dict) -> bool:
        """일일 거래 리포트 전송"""
        try:
            # 수익률에 따른 이모지
            total_pnl = report_data.get('total_pnl', 0)
            pnl_emoji = "📈" if total_pnl > 0 else "📉" if total_pnl < 0 else "➡️"
            
            # 승률에 따른 이모지
            win_rate = report_data.get('win_rate', 0)
            win_emoji = "🎯" if win_rate >= 70 else "📊" if win_rate >= 50 else "⚠️"
            
            message = f"""
🌟 <b>일일 거래 리포트</b> - {datetime.now().strftime('%Y-%m-%d')}

{pnl_emoji} <b>총 손익:</b> ${total_pnl:+.2f}
{win_emoji} <b>승률:</b> {win_rate:.1f}% ({report_data.get('winning_trades', 0)}/{report_data.get('total_trades', 0)})
📊 <b>총 거래:</b> {report_data.get('total_trades', 0)}건
📈 <b>수익률:</b> {report_data.get('return_rate', 0):+.2f}%
📉 <b>최대 낙폭:</b> {report_data.get('max_drawdown', 0):.2f}%
⚡ <b>샤프 비율:</b> {report_data.get('sharpe_ratio', 0):.2f}

💰 <b>거래 종목 요약:</b>
"""
            
            # 상위 수익 종목 추가
            top_performers = report_data.get('top_performers', [])
            if top_performers:
                message += "\n🏆 <b>상위 수익 종목:</b>\n"
                for i, stock in enumerate(top_performers[:5], 1):
                    symbol = stock.get('symbol', 'N/A')
                    pnl = stock.get('pnl', 0)
                    pnl_pct = stock.get('pnl_percent', 0)
                    message += f"{i}. {symbol}: ${pnl:+.2f} ({pnl_pct:+.2f}%)\n"
            
            # 거래 통계 추가
            message += f"""
📊 <b>상세 통계:</b>
• 평균 보유시간: {report_data.get('avg_holding_time', 0):.1f}분
• 평균 거래 금액: ${report_data.get('avg_trade_amount', 0):,.0f}
• 최대 연속 승리: {report_data.get('max_consecutive_wins', 0)}회
• 최대 연속 손실: {report_data.get('max_consecutive_losses', 0)}회

⚠️ <b>리스크 지표:</b>
• 일일 VaR: ${report_data.get('daily_var', 0):.2f}
• 포트폴리오 베타: {report_data.get('portfolio_beta', 0):.2f}
"""
            
            return self.send_message_sync(message)
            
        except Exception as e:
            log_error("DAILY_REPORT_ERROR", "Failed to send daily report", e)
            return False
    
    def send_position_update(self, positions: List[Dict]) -> bool:
        """포지션 현황 업데이트"""
        try:
            if not positions:
                message = "📊 <b>현재 포지션:</b> 없음"
                return self.send_message_sync(message)
            
            message = f"📊 <b>현재 포지션 현황</b> ({len(positions)}개)\n\n"
            
            total_unrealized_pnl = 0
            
            for i, pos in enumerate(positions, 1):
                symbol = pos.get('symbol', 'N/A')
                entry_price = pos.get('entry_price', 0)
                current_price = pos.get('current_price', 0)
                quantity = pos.get('quantity', 0)
                unrealized_pnl = pos.get('unrealized_pnl', 0)
                pnl_percent = pos.get('unrealized_pnl_percent', 0)
                holding_time = pos.get('holding_time_minutes', 0)
                
                total_unrealized_pnl += unrealized_pnl
                
                pnl_emoji = "🟢" if unrealized_pnl > 0 else "🔴" if unrealized_pnl < 0 else "⚪"
                
                message += f"""
{i}. <b>{symbol}</b> {pnl_emoji}
   💰 진입: ${entry_price:.2f} → 현재: ${current_price:.2f}
   📈 수량: {quantity:,}주
   💵 평가손익: ${unrealized_pnl:+.2f} ({pnl_percent:+.2f}%)
   ⏱️ 보유시간: {holding_time:.1f}분
"""
            
            # 총 평가손익 추가
            total_emoji = "📈" if total_unrealized_pnl > 0 else "📉" if total_unrealized_pnl < 0 else "➡️"
            message += f"\n{total_emoji} <b>총 평가손익:</b> ${total_unrealized_pnl:+.2f}"
            
            return self.send_message_sync(message)
            
        except Exception as e:
            log_error("POSITION_UPDATE_ERROR", "Failed to send position update", e)
            return False
    
    def send_system_alert(self, alert_type: str, message: str, severity: str = "INFO") -> bool:
        """시스템 알림 전송"""
        try:
            # 심각도에 따른 이모지
            severity_emojis = {
                "INFO": "ℹ️",
                "WARNING": "⚠️",
                "ERROR": "🚨",
                "CRITICAL": "💥"
            }
            
            emoji = severity_emojis.get(severity.upper(), "ℹ️")
            
            notification = f"""
{emoji} <b>시스템 알림</b>

🏷️ <b>유형:</b> {alert_type}
⚠️ <b>심각도:</b> {severity}
📝 <b>메시지:</b> {message}
⏰ <b>시간:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            return self.send_message_sync(notification)
            
        except Exception as e:
            log_error("SYSTEM_ALERT_ERROR", f"Failed to send system alert: {alert_type}", e)
            return False
    
    def send_market_status(self, session: str, status: str, next_session_time: str = None) -> bool:
        """시장 상태 알림"""
        try:
            session_emojis = {
                "PRE_MARKET": "🌅",
                "REGULAR_MARKET": "🏛️", 
                "AFTER_MARKET": "🌆",
                "CLOSED": "🌙"
            }
            
            session_names = {
                "PRE_MARKET": "프리마켓",
                "REGULAR_MARKET": "정규장",
                "AFTER_MARKET": "애프터마켓", 
                "CLOSED": "휴장"
            }
            
            emoji = session_emojis.get(session, "❓")
            session_name = session_names.get(session, session)
            
            message = f"""
{emoji} <b>시장 상태 변경</b>

📊 <b>현재 세션:</b> {session_name}
📈 <b>상태:</b> {status}
⏰ <b>시간:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            if next_session_time:
                message += f"⏰ <b>다음 세션:</b> {next_session_time}"
            
            return self.send_message_sync(message)
            
        except Exception as e:
            log_error("MARKET_STATUS_ERROR", "Failed to send market status", e)
            return False
    
    def send_performance_milestone(self, milestone_type: str, value: float, description: str) -> bool:
        """성과 마일스톤 알림"""
        try:
            milestone_emojis = {
                "profit": "🎉",
                "loss": "😰", 
                "win_streak": "🔥",
                "loss_streak": "❄️",
                "volume": "📊",
                "trades": "⚡"
            }
            
            emoji = milestone_emojis.get(milestone_type, "📊")
            
            message = f"""
{emoji} <b>성과 마일스톤 달성!</b>

🏆 <b>달성 내용:</b> {description}
📊 <b>값:</b> {value}
⏰ <b>시간:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            return self.send_message_sync(message)
            
        except Exception as e:
            log_error("MILESTONE_ERROR", f"Failed to send milestone: {milestone_type}", e)
            return False


# 전역 알림 인스턴스
telegram_notifier = TelegramNotifier()


def get_telegram_notifier() -> TelegramNotifier:
    """텔레그램 알림 인스턴스 반환"""
    return telegram_notifier


def send_trade_alert(symbol: str, action: str, price: float, quantity: int, **kwargs) -> bool:
    """거래 알림 전송 (간편 함수)"""
    return telegram_notifier.send_trade_alert(symbol, action, price, quantity, **kwargs)


def send_daily_report(report_data: Dict) -> bool:
    """일일 리포트 전송 (간편 함수)"""
    return telegram_notifier.send_daily_report(report_data)


def send_system_alert(alert_type: str, message: str, severity: str = "INFO") -> bool:
    """시스템 알림 전송 (간편 함수)"""
    return telegram_notifier.send_system_alert(alert_type, message, severity)


# 실행 예시
if __name__ == "__main__":
    # 텔레그램 알림 테스트
    print("=== 텔레그램 알림 테스트 ===")
    
    notifier = TelegramNotifier()
    
    # 거래 알림 테스트
    print("매수 알림 전송 중...")
    notifier.send_trade_alert("AAPL", "BUY", 150.25, 100, signal_score=8.5, reasoning="강한 매수 신호 감지")
    
    # 시스템 알림 테스트
    print("시스템 알림 전송 중...")
    notifier.send_system_alert("SYSTEM_START", "스캘핑 시스템이 시작되었습니다.", "INFO")
    
    print("테스트 완료!")