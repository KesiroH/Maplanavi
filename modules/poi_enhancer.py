"""
组件4: POI信息增强模块

核心职责:
- 调用LLM联网获取POI深度信息
- 补充基础数据中缺失的实时/细节属性

输入:
- 清洗后POI数据（组件2输出）
- LLM客户端实例（组件3输出）
- 配置参数

输出:
- 增强后的POI数据（含结构化补充信息）
"""

from __future__ import annotations
import logging
from typing import Dict, List, Any
from .models import CleanedPOI, EnhancedPOI
from .llm_configurator import LLMConfigurator

logger = logging.getLogger(__name__)

class POIEnhancer:
    """POI信息增强器"""
    
    def __init__(self, llm_client: LLMConfigurator):
        """
        Args:
            llm_client: LLM配置客户端
        """
        self.llm = llm_client
    
    def enhance_batch(
        self,
        pois: List[CleanedPOI],
        date: str,
        batch_size: int = 10
    ) -> List[EnhancedPOI]:
        """
        批量增强POI信息
        
        Args:
            pois: 待增强的POI列表
            date: 行程日期（影响营业时间判断）
            batch_size: 每批处理的POI数量
        
        Returns:
            增强后的POI列表
        """
        logger.info(f"开始批量增强 {len(pois)} 个POI信息...")
        
        enhanced_pois = []
        
        # 分批处理
        for i in range(0, len(pois), batch_size):
            batch = pois[i:i+batch_size]
            logger.info(f"处理批次 {i//batch_size + 1}: {len(batch)} 个POI")
            
            try:
                enhanced_batch = self._enhance_batch_llm(batch, date)
                enhanced_pois.extend(enhanced_batch)
            except Exception as e:
                logger.error(f"批次增强失败: {e}, 使用基础数据")
                # Fallback: 返回未增强的POI
                enhanced_pois.extend([
                    EnhancedPOI(
                        **poi.dict(),
                        llm_processed=False,
                        llm_error=str(e)
                    )
                    for poi in batch
                ])
        
        success_count = sum(1 for p in enhanced_pois if p.llm_processed)
        logger.info(f"✅ POI增强完成: {success_count}/{len(pois)} 成功")
        
        return enhanced_pois
    
    def _enhance_batch_llm(
        self,
        pois: List[CleanedPOI],
        date: str
    ) -> List[EnhancedPOI]:
        """使用LLM增强一批POI"""
        
        # 构造POI简要信息
        poi_summaries = []
        for i, poi in enumerate(pois):
            poi_summaries.append({
                "index": i,
                "name": poi.name,
                "category": poi.category,
                "lat": poi.lat,
                "lon": poi.lon,
                "tags": dict(list(poi.tags.items())[:5])  # 只传关键标签
            })
        
        system_prompt = """你是一个专业的旅游信息助手,负责为POI(兴趣点)补充深度信息。

对于每个POI,请根据其类别补充以下信息（基于常识推断或搜索）:

**餐饮类**:
- rating: 评分(0-5),如果是知名餐厅可根据常识
- price_range: 价格区间,如"50-100元"
- opening_hours: 营业时间,如"10:00-22:00"
- is_open: 在指定日期是否营业(true/false)
- recommended_duration: 建议用餐时长(分钟),通常60-90
- crowd_level: 拥挤度("低"/"中"/"高")
- tags_llm: 特色标签,如["川菜","适合聚餐"]
- review_summary: 评价摘要,1-2句话

**景点/公园类**:
- rating: 评分(0-5)
- price_range: 门票价格,如"免费"或"25元"
- opening_hours: 开放时间
- is_open: 是否开放
- recommended_duration: 推荐游玩时长(分钟),如120-180
- crowd_level: 拥挤度
- tags_llm: 特色标签,如["历史遗迹","需预约"]
- review_summary: 景点特色

**购物/休闲类**:
- rating: 评分
- price_range: 定位,如"中档"或"奢侈品"
- opening_hours: 营业时间
- is_open: 是否营业
- recommended_duration: 建议停留时长(分钟)
- crowd_level: 拥挤度
- tags_llm: 特色,如["连锁超市","电子产品"]
- review_summary: 特色说明

**酒店类**:
- rating: 评分
- price_range: 价格,如"500-800元/晚"
- opening_hours: "全天"
- is_open: true
- recommended_duration: 0
- crowd_level: "低"
- tags_llm: 特色,如["五星级","交通便利"]
- review_summary: 酒店特色

请严格按照JSON格式返回,如果某些信息无法推断,用null填充。"""

        user_prompt = f"""行程日期: {date}
POI列表:
{self._format_json(poi_summaries)}

请为每个POI补充深度信息,返回格式:
{{
  "results": [
    {{
      "index": 0,
      "rating": 4.5,
      "price_range": "80-120元",
      "opening_hours": "10:00-22:00",
      "is_open": true,
      "recommended_duration": 90,
      "crowd_level": "中",
      "tags_llm": ["川菜", "排队久"],
      "review_summary": "口味地道,环境不错",
      "data_source": "LLM推断",
      "updated_at": "{date}"
    }}
  ]
}}"""

        # 调用LLM
        response = self.llm.call_json(user_prompt, system_prompt)
        
        # 解析响应
        enhanced_pois = []
        for result in response.get("results", []):
            idx = result["index"]
            original_poi = pois[idx]
            
            enhanced = EnhancedPOI(
                **original_poi.dict(),
                enhanced_info={
                    "rating": result.get("rating"),
                    "price_range": result.get("price_range"),
                    "opening_hours": result.get("opening_hours"),
                    "is_open": result.get("is_open"),
                    "recommended_duration": result.get("recommended_duration"),
                    "crowd_level": result.get("crowd_level"),
                    "tags_llm": result.get("tags_llm", []),
                    "review_summary": result.get("review_summary")
                },
                data_source=result.get("data_source", "LLM"),
                updated_at=result.get("updated_at", date),
                llm_processed=True
            )
            enhanced_pois.append(enhanced)
        
        return enhanced_pois
    
    @staticmethod
    def _format_json(obj: Any) -> str:
        """格式化JSON（紧凑格式,节省token）"""
        import json
        return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))