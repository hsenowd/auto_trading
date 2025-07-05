"""
단계별 실전 전환 전략
한국투자 모의투자 API 한계를 극복하기 위한 점진적 실전 적용 방안
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from enum import Enum
import json

from config.config import SCALPING_CONFIG, RISK_MANAGEMENT
from utils.logger import get_logger, log_error
from utils.telegram_notifier import get_telegram_notifier

logger = get_logger()


class DeploymentStage(Enum):
    """배포 단계"""
    PAPER_TESTING = "paper_testing"           # 페이퍼 트레이딩
    MICRO_REAL = "micro_real"                 # 초소량 실전
    SMALL_REAL = "small_real"                 # 소량 실전
    NORMAL_REAL = "normal_real"               # 일반 실전
    FULL_DEPLOYMENT = "full_deployment"       # 완전 배포


class GradualDeployment:
    """단계별 실전 전환 시스템"""
    
    def __init__(self):
        self.telegram_notifier = get_telegram_notifier()
        
        # 현재 배포 단계
        self.current_stage = DeploymentStage.PAPER_TESTING
        
        # 단계별 설정
        self.stage_configs = {
            DeploymentStage.PAPER_TESTING: {
                "max_position_size": 0,           # 실전 거래 없음
                "max_positions": 5,
                "max_daily_trades": 50,
                "daily_loss_limit": 0,            # 실전 손실 없음
                "validation_period_days": 7,
                "success_criteria": {
                    "min_trades": 30,
                    "min_win_rate": 65,
                    "max_drawdown": 5,
                    "min_sharpe": 1.5
                }
            },
            
            DeploymentStage.MICRO_REAL: {
                "max_position_size": 50,          # $50 이하
                "max_positions": 2,
                "max_daily_trades": 10,
                "daily_loss_limit": 20,           # $20 일일 손실 한도
                "validation_period_days": 5,
                "success_criteria": {
                    "min_trades": 15,
                    "min_win_rate": 60,
                    "max_drawdown": 8,
                    "positive_pnl": True
                }
            },
            
            DeploymentStage.SMALL_REAL: {
                "max_position_size": 200,         # $200 이하
                "max_positions": 3,
                "max_daily_trades": 20,
                "daily_loss_limit": 100,          # $100 일일 손실 한도
                "validation_period_days": 7,
                "success_criteria": {
                    "min_trades": 25,
                    "min_win_rate": 62,
                    "max_drawdown": 6,
                    "positive_pnl": True
                }
            },
            
            DeploymentStage.NORMAL_REAL: {
                "max_position_size": 1000,        # $1000 이하
                "max_positions": 4,
                "max_daily_trades": 30,
                "daily_loss_limit": 300,          # $300 일일 손실 한도
                "validation_period_days": 10,
                "success_criteria": {
                    "min_trades": 40,
                    "min_win_rate": 65,
                    "max_drawdown": 5,
                    "min_sharpe": 1.3
                }
            },
            
            DeploymentStage.FULL_DEPLOYMENT: {
                "max_position_size": 10000,       # 전체 스케일
                "max_positions": 5,
                "max_daily_trades": 50,
                "daily_loss_limit": 1000,         # $1000 일일 손실 한도
                "validation_period_days": 0,      # 지속 모니터링
                "success_criteria": {
                    "continuous_monitoring": True
                }
            }
        }
        
        # 배포 기록
        self.deployment_history = []
        self.stage_metrics = {}
        
        logger.info("Gradual Deployment system initialized")
    
    def get_current_config(self) -> Dict:
        """현재 단계 설정 반환"""
        return self.stage_configs[self.current_stage].copy()
    
    def evaluate_stage_performance(self, trading_stats: Dict) -> Dict:
        """현재 단계 성과 평가"""
        try:
            current_config = self.stage_configs[self.current_stage]
            criteria = current_config["success_criteria"]
            
            evaluation = {
                "stage": self.current_stage.value,
                "criteria_met": {},
                "overall_success": False,
                "recommendations": []
            }
            
            # 각 성공 기준 평가
            criteria_results = []
            
            # 최소 거래 수
            if "min_trades" in criteria:
                min_trades = criteria["min_trades"]
                actual_trades = trading_stats.get("total_trades", 0)
                met = actual_trades >= min_trades
                criteria_results.append(met)
                evaluation["criteria_met"]["min_trades"] = {
                    "required": min_trades,
                    "actual": actual_trades,
                    "met": met
                }
            
            # 최소 승률
            if "min_win_rate" in criteria:
                min_win_rate = criteria["min_win_rate"]
                actual_win_rate = trading_stats.get("win_rate", 0)
                met = actual_win_rate >= min_win_rate
                criteria_results.append(met)
                evaluation["criteria_met"]["min_win_rate"] = {
                    "required": min_win_rate,
                    "actual": actual_win_rate,
                    "met": met
                }
            
            # 최대 드로우다운
            if "max_drawdown" in criteria:
                max_drawdown = criteria["max_drawdown"]
                actual_drawdown = trading_stats.get("max_drawdown", 0)
                met = actual_drawdown <= max_drawdown
                criteria_results.append(met)
                evaluation["criteria_met"]["max_drawdown"] = {
                    "required": max_drawdown,
                    "actual": actual_drawdown,
                    "met": met
                }
            
            # 최소 샤프 비율
            if "min_sharpe" in criteria:
                min_sharpe = criteria["min_sharpe"]
                actual_sharpe = trading_stats.get("sharpe_ratio", 0)
                met = actual_sharpe >= min_sharpe
                criteria_results.append(met)
                evaluation["criteria_met"]["min_sharpe"] = {
                    "required": min_sharpe,
                    "actual": actual_sharpe,
                    "met": met
                }
            
            # 양수 수익
            if "positive_pnl" in criteria:
                positive_required = criteria["positive_pnl"]
                actual_pnl = trading_stats.get("total_pnl", 0)
                met = actual_pnl > 0 if positive_required else True
                criteria_results.append(met)
                evaluation["criteria_met"]["positive_pnl"] = {
                    "required": "Positive",
                    "actual": f"${actual_pnl:.2f}",
                    "met": met
                }
            
            # 전체 성공 여부
            if criteria_results:
                evaluation["overall_success"] = all(criteria_results)
                success_rate = sum(criteria_results) / len(criteria_results)
                evaluation["success_rate"] = success_rate
            
            # 권장사항 생성
            if evaluation["overall_success"]:
                evaluation["recommendations"].append("✅ 다음 단계로 진행 가능")
                if self.current_stage != DeploymentStage.FULL_DEPLOYMENT:
                    evaluation["recommendations"].append("🚀 단계 승격을 고려하세요")
            else:
                evaluation["recommendations"].append("⚠️ 현재 단계에서 더 연습 필요")
                evaluation["recommendations"].append("📊 성과 개선 후 재평가 권장")
            
            return evaluation
            
        except Exception as e:
            log_error("STAGE_EVALUATION_ERROR", "Failed to evaluate stage performance", e)
            return {}
    
    def can_advance_stage(self, trading_stats: Dict) -> bool:
        """다음 단계로 진행 가능한지 확인"""
        try:
            evaluation = self.evaluate_stage_performance(trading_stats)
            return evaluation.get("overall_success", False)
            
        except Exception as e:
            log_error("STAGE_ADVANCE_CHECK_ERROR", "Failed to check stage advancement", e)
            return False
    
    def advance_to_next_stage(self, trading_stats: Dict) -> bool:
        """다음 단계로 진행"""
        try:
            if not self.can_advance_stage(trading_stats):
                logger.warning("Cannot advance - success criteria not met")
                return False
            
            # 현재 단계가 마지막인지 확인
            if self.current_stage == DeploymentStage.FULL_DEPLOYMENT:
                logger.info("Already at full deployment stage")
                return False
            
            # 다음 단계 결정
            stage_order = [
                DeploymentStage.PAPER_TESTING,
                DeploymentStage.MICRO_REAL,
                DeploymentStage.SMALL_REAL,
                DeploymentStage.NORMAL_REAL,
                DeploymentStage.FULL_DEPLOYMENT
            ]
            
            current_index = stage_order.index(self.current_stage)
            next_stage = stage_order[current_index + 1]
            
            # 단계 기록
            stage_record = {
                "from_stage": self.current_stage.value,
                "to_stage": next_stage.value,
                "advancement_time": datetime.now().isoformat(),
                "final_stats": trading_stats,
                "evaluation": self.evaluate_stage_performance(trading_stats)
            }
            
            self.deployment_history.append(stage_record)
            
            # 단계 변경
            previous_stage = self.current_stage
            self.current_stage = next_stage
            
            # 알림 전송
            self.send_stage_advancement_notification(previous_stage, next_stage, trading_stats)
            
            logger.info(f"✅ Advanced from {previous_stage.value} to {next_stage.value}")
            
            return True
            
        except Exception as e:
            log_error("STAGE_ADVANCEMENT_ERROR", "Failed to advance stage", e)
            return False
    
    def get_stage_recommendations(self) -> List[str]:
        """현재 단계별 권장사항"""
        try:
            stage_name = self.current_stage.value
            
            recommendations = {
                "paper_testing": [
                    "📊 페이퍼 트레이딩으로 전략 완전 검증",
                    "🎯 최소 일주일간 안정적 성과 확인",
                    "📈 승률 65% 이상, 샤프비율 1.5 이상 목표",
                    "⚠️ 실전 거래 절대 금지",
                    "🔄 다양한 시장 조건에서 테스트"
                ],
                
                "micro_real": [
                    "💰 최대 $50 이하 초소량 거래만",
                    "🎯 최대 2개 포지션으로 제한",
                    "📊 일일 최대 10건 거래",
                    "💸 일일 손실 $20 이하 엄수",
                    "📱 모든 거래 실시간 모니터링",
                    "⏰ 5일간 안정적 성과 후 다음 단계"
                ],
                
                "small_real": [
                    "💰 최대 $200 이하 소량 거래",
                    "🎯 최대 3개 포지션으로 확대",
                    "📊 일일 최대 20건 거래",
                    "💸 일일 손실 $100 이하",
                    "📈 승률 62% 이상 유지",
                    "⏰ 일주일간 검증 후 진행"
                ],
                
                "normal_real": [
                    "💰 최대 $1,000 일반 규모 거래",
                    "🎯 최대 4개 포지션 운영",
                    "📊 일일 최대 30건 거래",
                    "💸 일일 손실 $300 이하",
                    "📈 승률 65% 이상, 샤프비율 1.3 이상",
                    "⏰ 10일간 안정적 성과 확인"
                ],
                
                "full_deployment": [
                    "🚀 전체 규모 운영 가능",
                    "💰 최대 $10,000 포지션",
                    "🎯 최대 5개 포지션 동시 운영",
                    "📊 일일 최대 50건 거래",
                    "📈 지속적인 성과 모니터링",
                    "⚠️ 리스크 관리 철저히 준수"
                ]
            }
            
            return recommendations.get(stage_name, [])
            
        except Exception as e:
            log_error("RECOMMENDATIONS_ERROR", "Failed to get stage recommendations", e)
            return []
    
    def send_stage_advancement_notification(self, from_stage: DeploymentStage, 
                                          to_stage: DeploymentStage, stats: Dict):
        """단계 승격 알림"""
        try:
            stage_emojis = {
                "paper_testing": "📊",
                "micro_real": "🔬",
                "small_real": "📈",
                "normal_real": "🚀",
                "full_deployment": "🌟"
            }
            
            from_emoji = stage_emojis.get(from_stage.value, "📊")
            to_emoji = stage_emojis.get(to_stage.value, "🚀")
            
            stage_names = {
                "paper_testing": "페이퍼 트레이딩",
                "micro_real": "초소량 실전",
                "small_real": "소량 실전", 
                "normal_real": "일반 실전",
                "full_deployment": "완전 배포"
            }
            
            from_name = stage_names.get(from_stage.value, from_stage.value)
            to_name = stage_names.get(to_stage.value, to_stage.value)
            
            message = f"""
🎉 <b>단계 승격 완료!</b>

{from_emoji} <b>이전 단계:</b> {from_name}
{to_emoji} <b>새 단계:</b> {to_name}

📊 <b>최종 성과:</b>
• 총 거래: {stats.get('total_trades', 0)}건
• 승률: {stats.get('win_rate', 0):.1f}%
• 총 손익: ${stats.get('total_pnl', 0):+.2f}
• 최대 낙폭: {stats.get('max_drawdown', 0):.1f}%
• 샤프 비율: {stats.get('sharpe_ratio', 0):.2f}

💡 <b>새 단계 권장사항:</b>
"""
            
            new_recommendations = self.get_stage_recommendations()
            for i, rec in enumerate(new_recommendations[:4], 1):
                message += f"{i}. {rec}\n"
            
            message += f"\n⏰ <b>승격 시간:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            self.telegram_notifier.send_system_alert(
                "STAGE_ADVANCEMENT",
                message,
                "INFO"
            )
            
        except Exception as e:
            log_error("ADVANCEMENT_NOTIFICATION_ERROR", "Failed to send advancement notification", e)
    
    def get_deployment_summary(self) -> Dict:
        """배포 현황 요약"""
        try:
            current_config = self.get_current_config()
            
            return {
                "current_stage": self.current_stage.value,
                "stage_config": current_config,
                "recommendations": self.get_stage_recommendations(),
                "advancement_history": self.deployment_history,
                "total_advancements": len(self.deployment_history),
                "deployment_start_date": self.deployment_history[0]["advancement_time"] if self.deployment_history else None,
                "is_fully_deployed": self.current_stage == DeploymentStage.FULL_DEPLOYMENT
            }
            
        except Exception as e:
            log_error("DEPLOYMENT_SUMMARY_ERROR", "Failed to get deployment summary", e)
            return {}
    
    def force_stage_change(self, target_stage: str, reason: str = "Manual override"):
        """강제 단계 변경 (관리자용)"""
        try:
            logger.warning(f"⚠️ Force changing stage to {target_stage}. Reason: {reason}")
            
            # 유효한 단계인지 확인
            try:
                new_stage = DeploymentStage(target_stage)
            except ValueError:
                logger.error(f"Invalid stage: {target_stage}")
                return False
            
            previous_stage = self.current_stage
            self.current_stage = new_stage
            
            # 강제 변경 기록
            force_record = {
                "from_stage": previous_stage.value,
                "to_stage": new_stage.value,
                "change_time": datetime.now().isoformat(),
                "change_type": "FORCE",
                "reason": reason
            }
            
            self.deployment_history.append(force_record)
            
            # 알림 전송
            self.telegram_notifier.send_system_alert(
                "FORCE_STAGE_CHANGE",
                f"단계가 강제로 변경되었습니다.\n{previous_stage.value} → {new_stage.value}\n사유: {reason}",
                "WARNING"
            )
            
            logger.info(f"✅ Force changed stage from {previous_stage.value} to {new_stage.value}")
            return True
            
        except Exception as e:
            log_error("FORCE_STAGE_CHANGE_ERROR", "Failed to force stage change", e)
            return False


# 전역 배포 관리자 인스턴스
deployment_manager = GradualDeployment()


def get_deployment_manager() -> GradualDeployment:
    """배포 관리자 인스턴스 반환"""
    return deployment_manager


def get_current_stage_config() -> Dict:
    """현재 단계 설정 반환 (간편 함수)"""
    return deployment_manager.get_current_config()


def evaluate_advancement(trading_stats: Dict) -> Dict:
    """승급 가능 여부 평가 (간편 함수)"""
    return deployment_manager.evaluate_stage_performance(trading_stats)


# 실행 예시
if __name__ == "__main__":
    print("=== 단계별 실전 전환 시스템 테스트 ===")
    
    manager = GradualDeployment()
    
    # 현재 단계 확인
    current_config = manager.get_current_config()
    print(f"현재 단계: {manager.current_stage.value}")
    print(f"최대 포지션 크기: ${current_config['max_position_size']}")
    
    # 테스트 성과 데이터
    test_stats = {
        "total_trades": 35,
        "win_rate": 68.5,
        "total_pnl": 234.50,
        "max_drawdown": 3.8,
        "sharpe_ratio": 1.75
    }
    
    # 승급 평가
    evaluation = manager.evaluate_stage_performance(test_stats)
    print(f"\n승급 가능: {evaluation.get('overall_success', False)}")
    
    # 권장사항
    recommendations = manager.get_stage_recommendations()
    print(f"\n현재 단계 권장사항:")
    for i, rec in enumerate(recommendations[:3], 1):
        print(f"{i}. {rec}")
    
    print("\n테스트 완료!")