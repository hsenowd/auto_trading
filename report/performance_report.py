"""
성과 리포트 생성 모듈
거래 성과를 분석하고 일일/주간/월간 리포트를 생성합니다.
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import matplotlib.pyplot as plt
import seaborn as sns
from dataclasses import asdict

from utils.logger import get_logger, log_error
from config.config import LOGGING_CONFIG

logger = get_logger()


class PerformanceAnalyzer:
    """성과 분석 클래스"""
    
    def __init__(self):
        self.report_data = {}
        logger.info("PerformanceAnalyzer initialized")
    
    def analyze_daily_performance(self, trader) -> Dict:
        """일일 성과 분석"""
        try:
            # 기본 통계
            stats = trader.daily_stats
            closed_positions = trader.closed_positions
            
            # 거래 분석
            total_trades = len(closed_positions)
            if total_trades == 0:
                return {
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "win_rate": 0,
                    "total_pnl": 0,
                    "average_win": 0,
                    "average_loss": 0,
                    "profit_factor": 0,
                    "max_drawdown": 0,
                    "sharpe_ratio": 0,
                    "trades_detail": []
                }
            
            # 수익/손실 거래 분리
            winning_trades = [pos for pos in closed_positions if pos.profit_loss > 0]
            losing_trades = [pos for pos in closed_positions if pos.profit_loss <= 0]
            
            # 기본 지표 계산
            total_pnl = sum(pos.profit_loss for pos in closed_positions)
            win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
            
            # 평균 수익/손실
            average_win = sum(pos.profit_loss for pos in winning_trades) / len(winning_trades) if winning_trades else 0
            average_loss = sum(pos.profit_loss for pos in losing_trades) / len(losing_trades) if losing_trades else 0
            
            # 수익 팩터 (총 이익 / 총 손실)
            total_profit = sum(pos.profit_loss for pos in winning_trades)
            total_loss = abs(sum(pos.profit_loss for pos in losing_trades))
            profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
            
            # 최대 낙폭
            max_drawdown = stats.get("max_drawdown", 0)
            
            # 샤프 비율 (간단한 계산)
            returns = [pos.profit_loss for pos in closed_positions]
            avg_return = sum(returns) / len(returns) if returns else 0
            return_std = pd.Series(returns).std() if len(returns) > 1 else 0
            sharpe_ratio = avg_return / return_std if return_std > 0 else 0
            
            # 거래 상세 정보
            trades_detail = []
            for pos in closed_positions:
                trades_detail.append({
                    "symbol": pos.symbol,
                    "entry_time": pos.entry_time.isoformat(),
                    "exit_time": pos.exit_time.isoformat() if pos.exit_time else None,
                    "entry_price": pos.entry_price,
                    "exit_price": pos.exit_price,
                    "quantity": pos.quantity,
                    "profit_loss": pos.profit_loss,
                    "holding_time": int((pos.exit_time - pos.entry_time).total_seconds()) if pos.exit_time else 0,
                    "return_pct": (pos.profit_loss / (pos.entry_price * pos.quantity)) * 100 if pos.entry_price > 0 else 0
                })
            
            return {
                "date": datetime.now().date().isoformat(),
                "total_trades": total_trades,
                "winning_trades": len(winning_trades),
                "losing_trades": len(losing_trades),
                "win_rate": win_rate,
                "total_pnl": total_pnl,
                "average_win": average_win,
                "average_loss": average_loss,
                "profit_factor": profit_factor,
                "max_drawdown": max_drawdown,
                "sharpe_ratio": sharpe_ratio,
                "trades_detail": trades_detail
            }
            
        except Exception as e:
            log_error("DAILY_PERFORMANCE_ERROR", "Failed to analyze daily performance", e)
            return {}
    
    def generate_performance_summary(self, analysis: Dict) -> str:
        """성과 요약 텍스트 생성"""
        try:
            if not analysis:
                return "성과 데이터가 없습니다."
            
            summary = f"""
═══════════════════════════════════════════════════════════
📊 일일 거래 성과 리포트 - {analysis.get('date', 'N/A')}
═══════════════════════════════════════════════════════════

💰 수익성 지표:
   총 거래 수: {analysis.get('total_trades', 0)}회
   승리 거래: {analysis.get('winning_trades', 0)}회
   패배 거래: {analysis.get('losing_trades', 0)}회
   승률: {analysis.get('win_rate', 0):.1f}%
   
   총 손익: ${analysis.get('total_pnl', 0):.2f}
   평균 수익: ${analysis.get('average_win', 0):.2f}
   평균 손실: ${analysis.get('average_loss', 0):.2f}
   
📈 위험 지표:
   수익 팩터: {analysis.get('profit_factor', 0):.2f}
   최대 낙폭: ${analysis.get('max_drawdown', 0):.2f}
   샤프 비율: {analysis.get('sharpe_ratio', 0):.3f}

🔍 거래 상세:
"""
            
            # 상위 5개 거래 추가
            trades = analysis.get('trades_detail', [])
            if trades:
                # 수익률 기준으로 정렬
                trades_sorted = sorted(trades, key=lambda x: x.get('return_pct', 0), reverse=True)
                
                summary += "\n   🏆 상위 5개 거래:\n"
                for i, trade in enumerate(trades_sorted[:5], 1):
                    summary += f"   {i}. {trade['symbol']}: ${trade['profit_loss']:.2f} ({trade['return_pct']:.2f}%)\n"
                
                if len(trades_sorted) > 5:
                    summary += "\n   📉 하위 5개 거래:\n"
                    for i, trade in enumerate(trades_sorted[-5:], 1):
                        summary += f"   {i}. {trade['symbol']}: ${trade['profit_loss']:.2f} ({trade['return_pct']:.2f}%)\n"
            
            summary += "\n═══════════════════════════════════════════════════════════\n"
            
            return summary
            
        except Exception as e:
            log_error("PERFORMANCE_SUMMARY_ERROR", "Failed to generate performance summary", e)
            return "성과 요약 생성 실패"
    
    def save_report_to_file(self, analysis: Dict, filename: Optional[str] = None):
        """리포트를 파일로 저장"""
        try:
            if not filename:
                date_str = datetime.now().strftime("%Y%m%d")
                filename = f"reports/daily_report_{date_str}.json"
            
            import os
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(analysis, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Report saved to {filename}")
            
        except Exception as e:
            log_error("SAVE_REPORT_ERROR", f"Failed to save report to {filename}", e)
    
    def create_performance_chart(self, analysis: Dict) -> str:
        """성과 차트 생성"""
        try:
            trades = analysis.get('trades_detail', [])
            if not trades:
                return ""
            
            # 데이터 준비
            df = pd.DataFrame(trades)
            df['entry_time'] = pd.to_datetime(df['entry_time'])
            df['cumulative_pnl'] = df['profit_loss'].cumsum()
            
            # 차트 생성
            plt.figure(figsize=(12, 8))
            
            # 서브플롯 1: 누적 손익
            plt.subplot(2, 2, 1)
            plt.plot(df['entry_time'], df['cumulative_pnl'], marker='o', markersize=3)
            plt.title('누적 손익 곡선')
            plt.xlabel('시간')
            plt.ylabel('누적 P&L ($)')
            plt.grid(True, alpha=0.3)
            
            # 서브플롯 2: 거래별 손익
            plt.subplot(2, 2, 2)
            colors = ['green' if pnl > 0 else 'red' for pnl in df['profit_loss']]
            plt.bar(range(len(df)), df['profit_loss'], color=colors, alpha=0.7)
            plt.title('거래별 손익')
            plt.xlabel('거래 번호')
            plt.ylabel('P&L ($)')
            plt.grid(True, alpha=0.3)
            
            # 서브플롯 3: 수익률 분포
            plt.subplot(2, 2, 3)
            plt.hist(df['return_pct'], bins=20, alpha=0.7, color='blue')
            plt.title('수익률 분포')
            plt.xlabel('수익률 (%)')
            plt.ylabel('빈도')
            plt.grid(True, alpha=0.3)
            
            # 서브플롯 4: 보유 시간 분포
            plt.subplot(2, 2, 4)
            plt.hist(df['holding_time'], bins=20, alpha=0.7, color='orange')
            plt.title('보유 시간 분포')
            plt.xlabel('보유 시간 (초)')
            plt.ylabel('빈도')
            plt.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # 차트 저장
            date_str = datetime.now().strftime("%Y%m%d")
            chart_filename = f"reports/performance_chart_{date_str}.png"
            
            import os
            os.makedirs(os.path.dirname(chart_filename), exist_ok=True)
            plt.savefig(chart_filename, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Performance chart saved to {chart_filename}")
            return chart_filename
            
        except Exception as e:
            log_error("CHART_CREATION_ERROR", "Failed to create performance chart", e)
            return ""


def generate_daily_report(trader) -> Dict:
    """일일 리포트 생성 (메인 함수)"""
    try:
        analyzer = PerformanceAnalyzer()
        
        # 성과 분석
        analysis = analyzer.analyze_daily_performance(trader)
        
        # 요약 텍스트 생성
        summary = analyzer.generate_performance_summary(analysis)
        
        # 리포트 출력
        logger.info("Daily Performance Report Generated:")
        logger.info(summary)
        
        # 파일로 저장
        analyzer.save_report_to_file(analysis)
        
        # 차트 생성
        chart_file = analyzer.create_performance_chart(analysis)
        
        return {
            "analysis": analysis,
            "summary": summary,
            "chart_file": chart_file,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        log_error("DAILY_REPORT_ERROR", "Failed to generate daily report", e)
        return {}


def generate_weekly_report(trader_history: List[Dict]) -> Dict:
    """주간 리포트 생성"""
    try:
        if not trader_history:
            return {}
        
        # 주간 통계 계산
        total_trades = sum(report.get('total_trades', 0) for report in trader_history)
        total_pnl = sum(report.get('total_pnl', 0) for report in trader_history)
        
        avg_win_rate = sum(report.get('win_rate', 0) for report in trader_history) / len(trader_history)
        
        weekly_summary = f"""
═══════════════════════════════════════════════════════════
📊 주간 거래 성과 리포트
═══════════════════════════════════════════════════════════

기간: {len(trader_history)}일
총 거래: {total_trades}회
총 손익: ${total_pnl:.2f}
평균 승률: {avg_win_rate:.1f}%

일별 성과:
"""
        
        for i, report in enumerate(trader_history, 1):
            weekly_summary += f"Day {i}: {report.get('total_trades', 0)}회, ${report.get('total_pnl', 0):.2f}\n"
        
        weekly_summary += "═══════════════════════════════════════════════════════════\n"
        
        return {
            "summary": weekly_summary,
            "total_trades": total_trades,
            "total_pnl": total_pnl,
            "avg_win_rate": avg_win_rate,
            "days": len(trader_history)
        }
        
    except Exception as e:
        log_error("WEEKLY_REPORT_ERROR", "Failed to generate weekly report", e)
        return {}


# 실행 예시
if __name__ == "__main__":
    # 더미 데이터로 테스트
    from datetime import datetime
    from dataclasses import dataclass
    
    @dataclass
    class DummyPosition:
        symbol: str
        entry_price: float
        exit_price: float
        quantity: int
        profit_loss: float
        entry_time: datetime
        exit_time: datetime
    
    # 더미 트레이더 생성
    class DummyTrader:
        def __init__(self):
            self.daily_stats = {
                "total_trades": 3,
                "winning_trades": 2,
                "losing_trades": 1,
                "total_profit_loss": 50.0,
                "max_drawdown": 25.0
            }
            
            self.closed_positions = [
                DummyPosition("TSLA", 100.0, 105.0, 10, 50.0, datetime.now() - timedelta(hours=2), datetime.now() - timedelta(hours=1)),
                DummyPosition("AAPL", 150.0, 155.0, 5, 25.0, datetime.now() - timedelta(hours=1), datetime.now() - timedelta(minutes=30)),
                DummyPosition("NVDA", 200.0, 195.0, 3, -15.0, datetime.now() - timedelta(minutes=30), datetime.now())
            ]
    
    print("=== 성과 리포트 테스트 ===")
    
    dummy_trader = DummyTrader()
    report = generate_daily_report(dummy_trader)
    
    print("리포트 생성 완료!")
    print(f"차트 파일: {report.get('chart_file', 'N/A')}")