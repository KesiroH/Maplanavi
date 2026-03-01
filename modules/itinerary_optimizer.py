"""
组件6: 行程优化模块

TODO: 此模块未在 main.py 主流程中被调用
- 当前状态: 功能已实现但未集成
- 建议: 可在完成基本流程后集成，或安全移除

核心职责:
- 基于LLM的语义理解优化行程逻辑
- 处理时间冲突、主题关联、路径效率

输入:
- 基础行程方案
- 增强后的POI数据
- 校验后路网时间矩阵
- LLM客户端实例

输出:
- 优化后的行程方案
- 优化说明列表
"""

from __future__ import annotations
import logging
from typing import Dict, List
from .models import (
    Itinerary, EnhancedPOI, TimeMatrix,
    OptimizationLog
)
from .llm_configurator import LLMConfigurator

logger = logging.getLogger(__name__)

class ItineraryOptimizer:
    """行程优化器"""
    
    def __init__(
        self,
        enhanced_pois: List[EnhancedPOI],
        time_matrix: TimeMatrix,
        llm_client: LLMConfigurator,
        config: Dict
    ):
        """
        Args:
            enhanced_pois: 增强后的POI列表
            time_matrix: 时间矩阵
            llm_client: LLM客户端
            config: 配置
        """
        self.enhanced_pois = {poi.id: poi for poi in enhanced_pois}
        self.time_matrix = time_matrix
        self.llm = llm_client
        self.date = config['itinerary']['date']
    
    def optimize(self, itinerary: Itinerary) -> tuple[Itinerary, List[OptimizationLog]]:
        """
        优化行程
        
        Returns:
            (优化后的行程, 优化日志列表)
        """
        logger.info("开始行程逻辑优化...")
        
        # 构造行程上下文
        itinerary_context = self._build_context(itinerary)
        
        # 调用LLM分析
        optimization_suggestions = self._analyze_by_llm(itinerary_context)
        
        # 应用优化建议
        optimized_itinerary, logs = self._apply_optimizations(
            itinerary,
            optimization_suggestions
        )
        
        logger.info(f"✅ 行程优化完成，应用 {len(logs)} 项调整")
        return optimized_itinerary, logs
    
    def _build_context(self, itinerary: Itinerary) -> List[Dict]:
        """构造行程上下文（用于LLM分析）"""
        context = []
        
        for step in itinerary.steps:
            poi = self.enhanced_pois.get(step.poi_id)
            enhanced_info = poi.enhanced_info if poi else {}
            
            context.append({
                "segment": step.segment,
                "segment_name": step.segment_name,
                "time": f"{step.time_start}-{step.time_end}",
                "poi_name": step.poi_name,
                "poi_category": step.poi_category,
                "travel_time_min": step.travel_time_min,
                "stay_time_min": step.stay_time_min,
                "enhanced_info": {
                    "is_open": enhanced_info.get("is_open"),
                    "opening_hours": enhanced_info.get("opening_hours"),
                    "crowd_level": enhanced_info.get("crowd_level"),
                    "recommended_duration": enhanced_info.get("recommended_duration"),
                    "rating": enhanced_info.get("rating")
                }
            })
        
        return context
    
    def _analyze_by_llm(self, context: List[Dict]) -> Dict:
        """使用LLM分析行程并给出优化建议"""
        
        system_prompt = f"""你是一个专业的行程优化助手。请检测行程中的以下问题:

1. **时间冲突**: POI关闭、营业时间不匹配、停留时长不合理
2. **主题跳跃**: 相邻环节主题差异过大（如历史景点→现代购物中心）
3. **拥挤度预警**: 高峰时段人流量大的地点
4. **路径效率**: 通勤时间过长或绕路

优化原则:
- 保持总时间基本不变（±30分钟）
- 优先替换同类别、同区域的备选POI
- 明确说明调整理由

返回格式:
{{
  "issues_found": [
    {{
      "segment": 3,
      "type": "时间冲突",
      "description": "XX餐厅在指定时间关闭",
      "severity": "high"
    }}
  ],
  "suggestions": [
    {{
      "segment": 3,
      "action": "replace",
      "reason": "餐厅关闭，建议替换为同区域YY餐厅",
      "alternative_criteria": "同类别+评分≥4.0+营业中"
    }}
  ],
  "warnings": [
    "环节5: XX景点周末人流量大，建议提前预约"
  ]
}}"""

        user_prompt = f"""行程日期: {self.date}
当前行程:
{self._format_json(context)}

请分析行程并给出优化建议。"""

        try:
            response = self.llm.call_json(user_prompt, system_prompt)
            return response
        except Exception as e:
            logger.error(f"LLM分析失败: {e}")
            return {"issues_found": [], "suggestions": [], "warnings": []}
    
    def _apply_optimizations(
        self,
        itinerary: Itinerary,
        suggestions: Dict
    ) -> tuple[Itinerary, List[OptimizationLog]]:
        """
        应用优化建议
        
        注: 简化实现，仅记录建议，不实际替换POI
        （实际应用需要根据criteria重新筛选POI）
        """
        logs = []
        
        # 记录发现的问题
        for issue in suggestions.get("issues_found", []):
            step = itinerary.steps[issue["segment"] - 1]
            logs.append(OptimizationLog(
                segment=issue["segment"],
                issue=issue["type"],
                original_poi=step.poi_name,
                new_poi=None,
                reason=issue["description"]
            ))
        
        # 记录建议（这里仅记录，不实际修改）
        for suggestion in suggestions.get("suggestions", []):
            step = itinerary.steps[suggestion["segment"] - 1]
            logs.append(OptimizationLog(
                segment=suggestion["segment"],
                issue="优化建议",
                original_poi=step.poi_name,
                new_poi="[待实现: 根据criteria筛选]",
                reason=suggestion["reason"]
            ))
        
        # 记录警告
        for warning in suggestions.get("warnings", []):
            logs.append(OptimizationLog(
                segment=0,
                issue="提示",
                original_poi="",
                reason=warning
            ))
        
        # 返回原行程（未修改）+ 日志
        return itinerary, logs
    
    @staticmethod
    def _format_json(obj) -> str:
        import json
        return json.dumps(obj, ensure_ascii=False, indent=2)