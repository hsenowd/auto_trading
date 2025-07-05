"""
고도화된 성과 지표 관리 시스템
- MFE/MAE (최대 이익/손실폭) 추적
- 거래 단위 전략별 KPI 분리 (종목 유형/가격대/전략 종류별)
- 구조적 문제 판단 및 성과 최적화 분석
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import os

from config.config import SCALPING_CONFIG
from utils.logger import get_logger, log_error
from utils.risk_manager import StrategyType

logger = get_logger()


class PriceCategory(Enum):
    """가격대 분류"""
    PENNY_STOCK = "penny_stock"      # $0.01 - $5.00
    LOW_PRICE = "low_price"          # $5.01 - $20.00
    MID_PRICE = "mid_price"          # $20.01 - $100.00
    HIGH_PRICE = "high_price"        # $100.01 - $500.00
    PREMIUM = "premium"              # $500.01+


class SectorType(Enum):
    """섹터 분류"""
    TECHNOLOGY = "technology"
    HEALTHCARE = "healthcare"
    FINANCIALS = "financials"
    ENERGY = "energy"
    CONSUMER_DISCRETIONARY = "consumer_discretionary"
    CONSUMER_STAPLES = "consumer_staples"
    INDUSTRIALS = "industrials"
    MATERIALS = "materials"
    UTILITIES = "utilities"
    REAL_ESTATE = "real_estate"
    COMMUNICATION = "communication"
    OTHER = "other"


@dataclass
class TradeRecord:
    """거래 기록"""
    trade_id: str
    timestamp: datetime
    symbol: str
    strategy_type: StrategyType
    price_category: PriceCategory
    sector_type: SectorType
    
    # 거래 정보
    entry_price: float
    exit_price: float
    quantity: int
    direction: str  # LONG, SHORT
    
    # 성과 지표
    pnl: float
    pnl_percentage: float
    duration_seconds: int
    
    # MFE/MAE 추적
    mfe: float = 0.0  # Maximum Favorable Excursion
    mae: float = 0.0  # Maximum Adverse Excursion
    mfe_percentage: float = 0.0
    mae_percentage: float = 0.0
    
    # 시장 상황
    market_volatility: float = 0.0
    volume_intensity: float = 0.0
    ai_signal_strength: float = 0.0
    
    # 종료 원인
    exit_reason: str = ""
    
    # 추가 지표
    max_drawdown_during_trade: float = 0.0
    efficiency_ratio: float = 0.0  # PnL / (MFE + MAE)


@dataclass
class StrategyKPI:
    """전략별 KPI"""
    strategy_name: str
    filter_criteria: Dict  # 필터링 기준
    
    # 기본 지표
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    # 수익성 지표
    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    
    # MFE/MAE 분석
    avg_mfe: float = 0.0
    avg_mae: float = 0.0
    mfe_mae_ratio: float = 0.0
    efficiency_ratio: float = 0.0
    
    # 리스크 지표
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    calmar_ratio: float = 0.0
    
    # 구조적 문제 지표
    premature_exit_rate: float = 0.0  # MFE 대비 실제 수익 비율
    late_exit_rate: float = 0.0       # MAE 대비 실제 손실 비율
    opportunity_cost: float = 0.0     # 놓친 수익 기회
    
    # 시장 적응력
    volatility_performance: Dict = field(default_factory=dict)
    volume_performance: Dict = field(default_factory=dict)
    
    # 업데이트 시간
    last_update: datetime = field(default_factory=datetime.now)


class EnhancedPerformanceAnalyzer:
    """고도화된 성과 분석기"""
    
    def __init__(self):
        self.trade_records: List[TradeRecord] = []
        self.strategy_kpis: Dict[str, StrategyKPI] = {}
        
        # 분석 설정
        self.analysis_window = 30  # 30일 분석 창
        self.benchmark_symbol = "SPY"
        
        # 데이터 경로
        self.data_path = "data/performance/"
        os.makedirs(self.data_path, exist_ok=True)
        
        # 로드 기존 데이터
        self._load_existing_data()
        
        logger.info("Enhanced Performance Analyzer initialized")
    
    def record_trade(self, trade_record: TradeRecord):
        """거래 기록 추가"""
        try:
            # MFE/MAE 계산
            self._calculate_mfe_mae(trade_record)
            
            # 효율성 비율 계산
            self._calculate_efficiency_ratio(trade_record)
            
            # 가격대 분류
            trade_record.price_category = self._classify_price_category(trade_record.entry_price)
            
            # 기록 추가
            self.trade_records.append(trade_record)
            
            # 전략별 KPI 업데이트
            self._update_strategy_kpis(trade_record)
            
            # 데이터 저장
            self._save_trade_record(trade_record)
            
            logger.info(f"Trade recorded: {trade_record.symbol} "
                       f"MFE: {trade_record.mfe_percentage:.2f}% "
                       f"MAE: {trade_record.mae_percentage:.2f}% "
                       f"Efficiency: {trade_record.efficiency_ratio:.2f}")
            
        except Exception as e:
            log_error("TRADE_RECORD_ERROR", f"Failed to record trade {trade_record.trade_id}", e)
    
    def _calculate_mfe_mae(self, trade_record: TradeRecord):
        """MFE/MAE 계산"""
        try:
            # 실제로는 거래 중 실시간 가격 데이터가 필요
            # 여기서는 시뮬레이션
            
            entry_price = trade_record.entry_price
            exit_price = trade_record.exit_price
            direction = trade_record.direction
            
            # 예상 최대 유리한 움직임 (MFE)
            if direction == "LONG":
                # 상승 시 최대 이익 (시뮬레이션)
                mfe_price = entry_price * (1 + abs(trade_record.pnl_percentage / 100) * 1.5)
                trade_record.mfe = (mfe_price - entry_price) * trade_record.quantity
                trade_record.mfe_percentage = ((mfe_price - entry_price) / entry_price) * 100
                
                # 하락 시 최대 손실 (시뮬레이션)
                mae_price = entry_price * (1 - abs(trade_record.pnl_percentage / 100) * 0.8)
                trade_record.mae = (entry_price - mae_price) * trade_record.quantity
                trade_record.mae_percentage = -((entry_price - mae_price) / entry_price) * 100
                
            else:  # SHORT
                # 하락 시 최대 이익
                mfe_price = entry_price * (1 - abs(trade_record.pnl_percentage / 100) * 1.5)
                trade_record.mfe = (entry_price - mfe_price) * trade_record.quantity
                trade_record.mfe_percentage = ((entry_price - mfe_price) / entry_price) * 100
                
                # 상승 시 최대 손실
                mae_price = entry_price * (1 + abs(trade_record.pnl_percentage / 100) * 0.8)
                trade_record.mae = (mae_price - entry_price) * trade_record.quantity
                trade_record.mae_percentage = -((mae_price - entry_price) / entry_price) * 100
                
        except Exception as e:
            log_error("MFE_MAE_CALC_ERROR", f"Failed to calculate MFE/MAE for {trade_record.trade_id}", e)
    
    def _calculate_efficiency_ratio(self, trade_record: TradeRecord):
        """효율성 비율 계산"""
        try:
            mfe_abs = abs(trade_record.mfe)
            mae_abs = abs(trade_record.mae)
            
            if mfe_abs + mae_abs > 0:
                trade_record.efficiency_ratio = abs(trade_record.pnl) / (mfe_abs + mae_abs)
            else:
                trade_record.efficiency_ratio = 0.0
                
        except Exception as e:
            log_error("EFFICIENCY_CALC_ERROR", f"Failed to calculate efficiency ratio", e)
    
    def _classify_price_category(self, price: float) -> PriceCategory:
        """가격대 분류"""
        if price <= 5.0:
            return PriceCategory.PENNY_STOCK
        elif price <= 20.0:
            return PriceCategory.LOW_PRICE
        elif price <= 100.0:
            return PriceCategory.MID_PRICE
        elif price <= 500.0:
            return PriceCategory.HIGH_PRICE
        else:
            return PriceCategory.PREMIUM
    
    def _update_strategy_kpis(self, trade_record: TradeRecord):
        """전략별 KPI 업데이트"""
        try:
            # 여러 차원의 전략 KPI 생성
            strategy_keys = [
                # 기본 전략
                f"{trade_record.strategy_type.value}",
                
                # 전략 + 가격대
                f"{trade_record.strategy_type.value}_{trade_record.price_category.value}",
                
                # 전략 + 섹터
                f"{trade_record.strategy_type.value}_{trade_record.sector_type.value}",
                
                # 가격대별
                f"price_{trade_record.price_category.value}",
                
                # 섹터별
                f"sector_{trade_record.sector_type.value}",
                
                # 종합
                f"{trade_record.strategy_type.value}_{trade_record.price_category.value}_{trade_record.sector_type.value}"
            ]
            
            for strategy_key in strategy_keys:
                if strategy_key not in self.strategy_kpis:
                    self.strategy_kpis[strategy_key] = StrategyKPI(
                        strategy_name=strategy_key,
                        filter_criteria=self._get_filter_criteria(strategy_key, trade_record)
                    )
                
                # KPI 업데이트
                self._update_single_kpi(self.strategy_kpis[strategy_key], trade_record)
                
        except Exception as e:
            log_error("STRATEGY_KPI_UPDATE_ERROR", f"Failed to update strategy KPIs", e)
    
    def _get_filter_criteria(self, strategy_key: str, trade_record: TradeRecord) -> Dict:
        """필터링 기준 생성"""
        criteria = {}
        
        if trade_record.strategy_type.value in strategy_key:
            criteria['strategy_type'] = trade_record.strategy_type.value
        
        if trade_record.price_category.value in strategy_key:
            criteria['price_category'] = trade_record.price_category.value
        
        if trade_record.sector_type.value in strategy_key:
            criteria['sector_type'] = trade_record.sector_type.value
        
        return criteria
    
    def _update_single_kpi(self, kpi: StrategyKPI, trade_record: TradeRecord):
        """단일 KPI 업데이트"""
        try:
            # 기본 지표
            kpi.total_trades += 1
            
            if trade_record.pnl > 0:
                kpi.winning_trades += 1
                kpi.avg_win = (kpi.avg_win * (kpi.winning_trades - 1) + trade_record.pnl) / kpi.winning_trades
            else:
                kpi.losing_trades += 1
                kpi.avg_loss = (kpi.avg_loss * (kpi.losing_trades - 1) + abs(trade_record.pnl)) / kpi.losing_trades
            
            kpi.win_rate = (kpi.winning_trades / kpi.total_trades) * 100
            kpi.total_pnl += trade_record.pnl
            
            # 수익 팩터
            total_wins = kpi.avg_win * kpi.winning_trades
            total_losses = kpi.avg_loss * kpi.losing_trades
            kpi.profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
            
            # MFE/MAE 분석
            kpi.avg_mfe = (kpi.avg_mfe * (kpi.total_trades - 1) + trade_record.mfe) / kpi.total_trades
            kpi.avg_mae = (kpi.avg_mae * (kpi.total_trades - 1) + trade_record.mae) / kpi.total_trades
            kpi.mfe_mae_ratio = abs(kpi.avg_mfe / kpi.avg_mae) if kpi.avg_mae != 0 else 0
            
            # 효율성 비율
            kpi.efficiency_ratio = (kpi.efficiency_ratio * (kpi.total_trades - 1) + trade_record.efficiency_ratio) / kpi.total_trades
            
            # 구조적 문제 분석
            self._analyze_structural_issues(kpi, trade_record)
            
            kpi.last_update = datetime.now()
            
        except Exception as e:
            log_error("SINGLE_KPI_UPDATE_ERROR", f"Failed to update single KPI", e)
    
    def _analyze_structural_issues(self, kpi: StrategyKPI, trade_record: TradeRecord):
        """구조적 문제 분석"""
        try:
            # 조기 종료 비율 (MFE 대비 실제 수익이 낮은 경우)
            if trade_record.mfe > 0 and trade_record.pnl > 0:
                exit_efficiency = trade_record.pnl / trade_record.mfe
                if exit_efficiency < 0.5:  # 50% 이하 효율성
                    kpi.premature_exit_rate = (kpi.premature_exit_rate * (kpi.total_trades - 1) + 1) / kpi.total_trades
                
            # 늦은 종료 비율 (MAE 대비 실제 손실이 큰 경우)
            if trade_record.mae > 0 and trade_record.pnl < 0:
                loss_efficiency = abs(trade_record.pnl) / trade_record.mae
                if loss_efficiency > 0.8:  # 80% 이상 손실
                    kpi.late_exit_rate = (kpi.late_exit_rate * (kpi.total_trades - 1) + 1) / kpi.total_trades
            
            # 기회 비용 (놓친 수익)
            opportunity_loss = max(0, trade_record.mfe - trade_record.pnl)
            kpi.opportunity_cost = (kpi.opportunity_cost * (kpi.total_trades - 1) + opportunity_loss) / kpi.total_trades
            
        except Exception as e:
            log_error("STRUCTURAL_ANALYSIS_ERROR", f"Failed to analyze structural issues", e)
    
    def get_comprehensive_report(self, days: int = 30) -> Dict:
        """종합 성과 리포트"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_trades = [t for t in self.trade_records if t.timestamp >= cutoff_date]
            
            if not recent_trades:
                return {"error": "No recent trades found"}
            
            # 기본 통계
            total_trades = len(recent_trades)
            winning_trades = len([t for t in recent_trades if t.pnl > 0])
            total_pnl = sum(t.pnl for t in recent_trades)
            
            # MFE/MAE 분석
            avg_mfe = np.mean([t.mfe_percentage for t in recent_trades])
            avg_mae = np.mean([t.mae_percentage for t in recent_trades])
            avg_efficiency = np.mean([t.efficiency_ratio for t in recent_trades])
            
            # 전략별 성과
            strategy_performance = {}
            for strategy_key, kpi in self.strategy_kpis.items():
                if kpi.total_trades >= 10:  # 충분한 데이터가 있는 전략만
                    strategy_performance[strategy_key] = {
                        'total_trades': kpi.total_trades,
                        'win_rate': kpi.win_rate,
                        'profit_factor': kpi.profit_factor,
                        'avg_mfe': kpi.avg_mfe,
                        'avg_mae': kpi.avg_mae,
                        'efficiency_ratio': kpi.efficiency_ratio,
                        'premature_exit_rate': kpi.premature_exit_rate,
                        'late_exit_rate': kpi.late_exit_rate,
                        'opportunity_cost': kpi.opportunity_cost
                    }
            
            # 가격대별 성과
            price_performance = {}
            for price_cat in PriceCategory:
                price_trades = [t for t in recent_trades if t.price_category == price_cat]
                if price_trades:
                    price_performance[price_cat.value] = {
                        'count': len(price_trades),
                        'win_rate': len([t for t in price_trades if t.pnl > 0]) / len(price_trades) * 100,
                        'avg_pnl': np.mean([t.pnl for t in price_trades]),
                        'avg_mfe': np.mean([t.mfe_percentage for t in price_trades]),
                        'avg_mae': np.mean([t.mae_percentage for t in price_trades])
                    }
            
            # 구조적 문제 식별
            structural_issues = self._identify_structural_problems(recent_trades)
            
            return {
                'period': f"{days} days",
                'total_trades': total_trades,
                'win_rate': (winning_trades / total_trades) * 100,
                'total_pnl': total_pnl,
                'avg_mfe': avg_mfe,
                'avg_mae': avg_mae,
                'avg_efficiency': avg_efficiency,
                'strategy_performance': strategy_performance,
                'price_performance': price_performance,
                'structural_issues': structural_issues,
                'top_strategies': self._get_top_strategies(),
                'recommendations': self._generate_recommendations(recent_trades),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            log_error("COMPREHENSIVE_REPORT_ERROR", f"Failed to generate comprehensive report", e)
            return {"error": str(e)}
    
    def _identify_structural_problems(self, trades: List[TradeRecord]) -> Dict:
        """구조적 문제 식별"""
        try:
            problems = {}
            
            # 1. 조기 종료 문제
            premature_exits = [t for t in trades if t.mfe > 0 and t.pnl > 0 and t.pnl < t.mfe * 0.5]
            if len(premature_exits) > len(trades) * 0.3:  # 30% 이상
                problems['premature_exit'] = {
                    'severity': 'HIGH',
                    'description': f"{len(premature_exits)} trades ({len(premature_exits)/len(trades)*100:.1f}%) exited too early",
                    'avg_opportunity_cost': np.mean([t.mfe - t.pnl for t in premature_exits])
                }
            
            # 2. 늦은 손절 문제
            late_exits = [t for t in trades if t.mae > 0 and t.pnl < 0 and abs(t.pnl) > t.mae * 0.8]
            if len(late_exits) > len(trades) * 0.2:  # 20% 이상
                problems['late_exit'] = {
                    'severity': 'HIGH',
                    'description': f"{len(late_exits)} trades ({len(late_exits)/len(trades)*100:.1f}%) cut losses too late",
                    'avg_excess_loss': np.mean([abs(t.pnl) - t.mae for t in late_exits])
                }
            
            # 3. 저효율성 문제
            low_efficiency = [t for t in trades if t.efficiency_ratio < 0.3]
            if len(low_efficiency) > len(trades) * 0.4:  # 40% 이상
                problems['low_efficiency'] = {
                    'severity': 'MEDIUM',
                    'description': f"{len(low_efficiency)} trades ({len(low_efficiency)/len(trades)*100:.1f}%) showed low efficiency",
                    'avg_efficiency': np.mean([t.efficiency_ratio for t in low_efficiency])
                }
            
            return problems
            
        except Exception as e:
            log_error("STRUCTURAL_PROBLEMS_ERROR", f"Failed to identify structural problems", e)
            return {}
    
    def _get_top_strategies(self) -> List[Dict]:
        """상위 전략 조회"""
        try:
            strategies = []
            
            for strategy_key, kpi in self.strategy_kpis.items():
                if kpi.total_trades >= 10:  # 충분한 데이터
                    score = (kpi.win_rate * 0.3 + 
                            kpi.profit_factor * 10 * 0.3 + 
                            kpi.efficiency_ratio * 100 * 0.4)
                    
                    strategies.append({
                        'strategy': strategy_key,
                        'score': score,
                        'trades': kpi.total_trades,
                        'win_rate': kpi.win_rate,
                        'profit_factor': kpi.profit_factor,
                        'efficiency_ratio': kpi.efficiency_ratio
                    })
            
            # 점수순 정렬
            strategies.sort(key=lambda x: x['score'], reverse=True)
            
            return strategies[:10]  # 상위 10개
            
        except Exception as e:
            log_error("TOP_STRATEGIES_ERROR", f"Failed to get top strategies", e)
            return []
    
    def _generate_recommendations(self, trades: List[TradeRecord]) -> List[str]:
        """개선 권고사항 생성"""
        try:
            recommendations = []
            
            # MFE/MAE 분석 기반 권고
            avg_mfe = np.mean([t.mfe_percentage for t in trades])
            avg_mae = np.mean([t.mae_percentage for t in trades])
            avg_efficiency = np.mean([t.efficiency_ratio for t in trades])
            
            if avg_efficiency < 0.4:
                recommendations.append(f"효율성 개선 필요: 평균 효율성 {avg_efficiency:.2f}는 낮은 수준입니다. 익절/손절 타이밍 최적화를 고려하세요.")
            
            if avg_mfe > 2.0 and avg_efficiency < 0.5:
                recommendations.append(f"조기 종료 문제: 평균 MFE {avg_mfe:.2f}%에 비해 실제 수익이 낮습니다. 보유 시간을 늘리는 것을 고려하세요.")
            
            if avg_mae > 1.5:
                recommendations.append(f"손절 타이밍 개선: 평균 MAE {avg_mae:.2f}%가 높습니다. 더 빠른 손절을 고려하세요.")
            
            # 가격대별 권고
            price_performance = {}
            for price_cat in PriceCategory:
                price_trades = [t for t in trades if t.price_category == price_cat]
                if price_trades:
                    win_rate = len([t for t in price_trades if t.pnl > 0]) / len(price_trades)
                    price_performance[price_cat.value] = win_rate
            
            if price_performance:
                best_price_cat = max(price_performance.keys(), key=lambda x: price_performance[x])
                recommendations.append(f"가격대 집중: {best_price_cat} 가격대에서 승률이 {price_performance[best_price_cat]*100:.1f}%로 가장 높습니다.")
            
            return recommendations
            
        except Exception as e:
            log_error("RECOMMENDATIONS_ERROR", f"Failed to generate recommendations", e)
            return []
    
    def generate_charts(self, days: int = 30) -> Dict[str, str]:
        """차트 생성"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_trades = [t for t in self.trade_records if t.timestamp >= cutoff_date]
            
            if not recent_trades:
                return {"error": "No recent trades found"}
            
            chart_paths = {}
            
            # 1. MFE/MAE 산점도
            plt.figure(figsize=(12, 8))
            plt.scatter([t.mfe_percentage for t in recent_trades], 
                       [t.mae_percentage for t in recent_trades],
                       c=[t.pnl for t in recent_trades], 
                       cmap='RdYlGn', alpha=0.6)
            plt.xlabel('MFE (%)')
            plt.ylabel('MAE (%)')
            plt.title('MFE vs MAE Analysis')
            plt.colorbar(label='PnL ($)')
            plt.grid(True, alpha=0.3)
            
            chart_path = f"{self.data_path}/mfe_mae_analysis.png"
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            plt.close()
            chart_paths['mfe_mae'] = chart_path
            
            # 2. 전략별 성과 비교
            strategy_data = {}
            for strategy_key, kpi in self.strategy_kpis.items():
                if kpi.total_trades >= 10:
                    strategy_data[strategy_key] = {
                        'Win Rate': kpi.win_rate,
                        'Profit Factor': kpi.profit_factor,
                        'Efficiency': kpi.efficiency_ratio * 100
                    }
            
            if strategy_data:
                df = pd.DataFrame(strategy_data).T
                
                plt.figure(figsize=(15, 8))
                df.plot(kind='bar', ax=plt.gca())
                plt.title('Strategy Performance Comparison')
                plt.xlabel('Strategy')
                plt.ylabel('Value')
                plt.xticks(rotation=45)
                plt.legend()
                plt.tight_layout()
                
                chart_path = f"{self.data_path}/strategy_comparison.png"
                plt.savefig(chart_path, dpi=300, bbox_inches='tight')
                plt.close()
                chart_paths['strategy_comparison'] = chart_path
            
            return chart_paths
            
        except Exception as e:
            log_error("CHART_GENERATION_ERROR", f"Failed to generate charts", e)
            return {"error": str(e)}
    
    def _load_existing_data(self):
        """기존 데이터 로드"""
        try:
            # 기존 거래 기록 로드
            trade_file = f"{self.data_path}/trades.json"
            if os.path.exists(trade_file):
                with open(trade_file, 'r') as f:
                    data = json.load(f)
                    # JSON에서 TradeRecord 객체로 변환하는 로직 필요
                    # 여기서는 간단히 패스
                    pass
            
        except Exception as e:
            log_error("DATA_LOAD_ERROR", f"Failed to load existing data", e)
    
    def _save_trade_record(self, trade_record: TradeRecord):
        """거래 기록 저장"""
        try:
            # 실제로는 데이터베이스나 파일에 저장
            # 여기서는 간단히 패스
            pass
            
        except Exception as e:
            log_error("TRADE_SAVE_ERROR", f"Failed to save trade record", e)


# 전역 성과 분석기 인스턴스
enhanced_performance_analyzer = EnhancedPerformanceAnalyzer()


def get_performance_analyzer() -> EnhancedPerformanceAnalyzer:
    """성과 분석기 인스턴스 반환"""
    return enhanced_performance_analyzer


# 실행 예시
if __name__ == "__main__":
    print("=== 고도화된 성과 분석 시스템 테스트 ===")
    
    analyzer = EnhancedPerformanceAnalyzer()
    
    # 종합 리포트 생성
    report = analyzer.get_comprehensive_report(30)
    print(f"총 거래 수: {report.get('total_trades', 0)}")
    print(f"승률: {report.get('win_rate', 0):.1f}%")
    print(f"평균 MFE: {report.get('avg_mfe', 0):.2f}%")
    print(f"평균 MAE: {report.get('avg_mae', 0):.2f}%")
    print(f"평균 효율성: {report.get('avg_efficiency', 0):.2f}")
    
    # 차트 생성
    charts = analyzer.generate_charts(30)
    print(f"\n생성된 차트: {list(charts.keys())}")
    
    print("\n고도화된 성과 분석 시스템 테스트 완료!")