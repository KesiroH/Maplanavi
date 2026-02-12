"""
组件7: 行程自然语言描述模块

核心职责:
- 调用LLM将结构化行程转化为自然语言描述
- 增强用户可读性

输入:
- 优化后的行程方案
- 增强后的POI数据
- LLM客户端实例

输出:
- 行程总览
- 分环节详情
- 实用提示
"""

from __future__ import annotations
import logging
from typing import Dict, List
from .models import Itinerary, EnhancedPOI
from .llm_configurator import LLMConfigurator

logger = logging.getLogger(__name__)

class ItineraryNarrator:
    """行程自然语言生成器"""
    
    def __init__(
        self,
        enhanced_pois: List[EnhancedPOI],
        llm_client: LLMConfigurator
    ):
        """
        Args:
            enhanced_pois: 增强后的POI列表
            llm_client: LLM客户端
        """
        self.enhanced_pois = {poi.id: poi for poi in enhanced_pois}
        self.llm = llm_client
    
    def generate_narration(self, itinerary: Itinerary) -> Dict[str, str]:
        """
        生成自然语言行程描述
        
        Returns:
            {
                "summary": "行程总览",
                "highlights": "精华段落",
                "segment_details": "分环节详情",
                "tips": "实用提示"
            }
        """
        logger.info("开始生成自然语言行程描述...")
        
        # 构造行程摘要
        brief = self._build_brief(itinerary)
        
        # 调用LLM生成
        system_prompt = """你是一个旅游文案专家，擅长将行程表转化为生动的描述。

要求:
1. **行程总览** (100-150字): 概括全天主题（如"皇家园林+高校文化+本地美食"）
2. **精华段落** (200-250字): 生动描述行程体验，使用"上午→中午→下午→晚上"结构
3. **分环节详情** (每个50-80字): 突出每个地点的亮点和注意事项
4. **实用提示** (5-8条): 预约提示、交通建议、避坑指南

风格: 简洁专业，突出实用性，不夸张。

返回JSON格式:
{
  "summary": "...",
  "highlights": "...",
  "segment_details": "...",
  "tips": ["...", "..."]
}"""

        user_prompt = f"""行程概要:
{self._format_json(brief)}

请生成自然语言行程描述。"""

        try:
            response = self.llm.call_json(user_prompt, system_prompt)
            
            # 格式化tips为字符串
            tips = response.get("tips", [])
            response["tips"] = "\n".join([f"• {tip}" for tip in tips])
            
            logger.info("✅ 自然语言描述生成完成")
            return response
            
        except Exception as e:
            logger.error(f"自然语言生成失败: {e}")
            return self._generate_fallback(itinerary)
    
    def _build_brief(self, itinerary: Itinerary) -> List[Dict]:
        """构造行程简要信息"""
        brief = []
        
        for step in itinerary.steps:
            poi = self.enhanced_pois.get(step.poi_id)
            enhanced = poi.enhanced_info if poi else {}
            
            brief.append({
                "time": f"{step.time_start}-{step.time_end}",
                "segment_name": step.segment_name,
                "poi": step.poi_name,
                "category": step.poi_category,
                "rating": enhanced.get("rating"),
                "tags": enhanced.get("tags_llm", []),
                "review_summary": enhanced.get("review_summary"),
                "travel_time": step.travel_time_min,
                "stay_time": step.stay_time_min
            })
        
        return brief
    
    def _generate_fallback(self, itinerary: Itinerary) -> Dict[str, str]:
        """生成后备描述（LLM失败时）"""
        categories = [step.poi_category for step in itinerary.steps]
        unique_cats = list(set(categories))
        
        return {
            "summary": f"今日行程包含{len(itinerary.steps)}个地点，涵盖{', '.join(unique_cats)}等类别。",
            "highlights": f"全天总时长{itinerary.total_time:.0f}分钟，通勤时间{itinerary.total_travel_time:.0f}分钟，节奏合理。",
            "segment_details": "详见结构化行程表。",
            "tips": "• 建议提前确认各地点营业时间\n• 注意交通高峰期"
        }
    
    @staticmethod
    def _format_json(obj) -> str:
        import json
        return json.dumps(obj, ensure_ascii=False, indent=2)