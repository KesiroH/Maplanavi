"""
组件5: 基础行程规划模块

核心职责:
- 结合LLM选点能力与贪心算法生成初始行程
- 按8个环节结构规划地点

输入:
- 清洗后POI数据
- 校验后路网时间矩阵
- LLM客户端实例
- 配置参数

输出:
- 基础行程方案
"""

from __future__ import annotations
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from .models import (
    CleanedPOI, TimeMatrix, SegmentConfig,
    ItineraryStep, Itinerary
)
from .llm_configurator import LLMConfigurator

logger = logging.getLogger(__name__)

class BasicItineraryPlanner:
    """基础行程规划器"""
    
    def __init__(
        self,
        pois: List[CleanedPOI],
        time_matrix: TimeMatrix,
        llm_client: LLMConfigurator,
        config: Dict
    ):
        """
        Args:
            pois: 清洗后的POI列表
            time_matrix: 校验后的时间矩阵
            llm_client: LLM客户端
            config: 行程配置
        """
        self.pois = pois
        self.time_matrix = time_matrix
        self.llm = llm_client
        self.itinerary_config = config['itinerary']
        
        # 构建POI ID到对象的映射
        self.poi_map = {poi.id: poi for poi in pois}
        
        # 构建POI ID到矩阵索引的映射
        self.poi_to_matrix_idx = {}
        for idx, poi_id in enumerate(time_matrix.poi_ids):
            if poi_id >= 0:  # 跳过起点(-1)
                self.poi_to_matrix_idx[poi_id] = idx
    
    def plan(self) -> Itinerary:
        """
        生成基础行程
        
        Returns:
            完整行程对象
        """
        logger.info("开始生成基础行程（8个地点）...")
        
        # 解析环节配置
        segments = [
            SegmentConfig(**seg)
            for seg in self.itinerary_config['segments']
        ]
        
        # 初始化状态
        steps = []
        used_poi_ids = set()
        prev_poi_id = None  # None表示起点
        current_time = self._parse_time(self.itinerary_config['time_window'].split('-')[0])
        
        # 逐环节规划
        for seg_config in segments:
            logger.info(f"规划环节 {seg_config.segment}: {seg_config.name}")
            
            # 1. 筛选候选POI
            candidates = self._filter_candidates(
                seg_config,
                prev_poi_id,
                used_poi_ids
            )
            
            if not candidates:
                raise ValueError(f"环节{seg_config.segment}无可用POI")
            
            logger.info(f"  候选POI数量: {len(candidates)}")
            
            # 2. LLM推荐优先级
            ranked_candidates = self._rank_by_llm(
                candidates,
                seg_config,
                current_time
            )
            
            # 3. 贪心选择（LLM推荐+最短通勤时间）
            selected_poi, travel_time, reason = self._greedy_select(
                ranked_candidates,
                prev_poi_id,
                seg_config
            )
            
            # 4. 计算时间
            time_start = current_time
            time_end = time_start + timedelta(minutes=travel_time + seg_config.stay_minutes)
            
            # 5. 记录步骤
            steps.append(ItineraryStep(
                segment=seg_config.segment,
                segment_name=seg_config.name,
                time_start=self._format_time(time_start),
                time_end=self._format_time(time_end),
                poi_id=selected_poi.id,
                poi_name=selected_poi.name,
                poi_category=selected_poi.category,
                poi_lat=selected_poi.lat,
                poi_lon=selected_poi.lon,
                travel_time_min=travel_time,
                stay_time_min=seg_config.stay_minutes,
                reason=reason
            ))
            
            # 6. 更新状态
            used_poi_ids.add(selected_poi.id)
            prev_poi_id = selected_poi.id
            current_time = time_end
        
        # 构造完整行程
        itinerary = Itinerary(
            steps=steps,
            total_travel_time=sum(s.travel_time_min for s in steps),
            total_stay_time=sum(s.stay_time_min for s in steps),
            total_time=sum(s.travel_time_min + s.stay_time_min for s in steps),
            date=self.itinerary_config['date'],
            start_point=tuple(self.itinerary_config['start_point'])
        )
        
        logger.info(f"✅ 基础行程生成完成，总时长: {itinerary.total_time:.0f}分钟")
        return itinerary
    
    def _filter_candidates(
        self,
        seg_config: SegmentConfig,
        prev_poi_id: Optional[int],
        used_poi_ids: set
    ) -> List[Tuple[CleanedPOI, float]]:
        """
        筛选候选POI
        
        Returns:
            [(POI, travel_time), ...]
        """
        candidates = []
        
        for poi in self.pois:
            # 1. 类别匹配
            if poi.category not in seg_config.category:
                continue
            
            # 2. 避免重复
            if poi.id in used_poi_ids:
                continue
            
            # 3. 计算通勤时间
            travel_time = self._get_travel_time(prev_poi_id, poi.id)
            if travel_time is None or travel_time == float('inf'):
                continue
            
            # 4. 时间约束
            if seg_config.max_commute_minutes is not None:
                if travel_time > seg_config.max_commute_minutes:
                    continue
            
            candidates.append((poi, travel_time))
        
        # 按通勤时间排序
        candidates.sort(key=lambda x: x[1])
        
        # 限制候选池大小
        max_candidates = self.itinerary_config.get('max_candidates_per_segment', 20)
        return candidates[:max_candidates]
    
    def _get_travel_time(
        self,
        from_poi_id: Optional[int],
        to_poi_id: int
    ) -> Optional[float]:
        """获取两点间旅行时间（分钟）"""
        # 起点索引
        if from_poi_id is None:
            from_idx = 0
        else:
            from_idx = self.poi_to_matrix_idx.get(from_poi_id)
            if from_idx is None:
                return None
        
        # 目的地索引
        to_idx = self.poi_to_matrix_idx.get(to_poi_id)
        if to_idx is None:
            return None
        
        return self.time_matrix.get_time(from_idx, to_idx)
    
    def _rank_by_llm(
        self,
        candidates: List[Tuple[CleanedPOI, float]],
        seg_config: SegmentConfig,
        current_time: datetime
    ) -> List[Tuple[CleanedPOI, float, float]]:
        """
        使用LLM对候选POI进行排序
        
        Returns:
            [(POI, travel_time, llm_score), ...]
        """
        # 构造候选POI简要信息
        candidate_summaries = []
        for poi, travel_time in candidates:
            candidate_summaries.append({
                "index": len(candidate_summaries),
                "name": poi.name,
                "category": poi.category,
                "travel_time_min": travel_time,
                "tags": dict(list(poi.tags.items())[:3])
            })
        
        system_prompt = f"""你是一个专业的行程规划助手。
当前环节: {seg_config.name}
环节描述: {seg_config.description}
当前时间: {current_time.strftime('%H:%M')}
要求类别: {seg_config.category}

请根据以下标准为候选POI打分(0-10):
1. 时段适配性（例如午餐时间选评分高的餐厅）
2. 通勤效率（距离上一地点近的优先）
3. 用户隐性需求（例如上午选历史景点，下午选休闲场所）

返回格式:
{{
  "rankings": [
    {{"index": 0, "score": 8.5, "reason": "知名景点,距离适中"}},
    {{"index": 1, "score": 7.0, "reason": "类别匹配,但通勤稍远"}}
  ]
}}"""

        user_prompt = f"""候选POI列表:
{self._format_json(candidate_summaries)}

请为每个候选POI打分并排序。"""

        try:
            response = self.llm.call_json(user_prompt, system_prompt)
            
            # 构建评分映射
            scores = {}
            for rank in response.get("rankings", []):
                idx = rank["index"]
                scores[idx] = rank["score"]
            
            # 添加评分到候选列表
            ranked = []
            for i, (poi, travel_time) in enumerate(candidates):
                score = scores.get(i, 5.0)  # 默认5分
                ranked.append((poi, travel_time, score))
            
            # 按评分降序排序
            ranked.sort(key=lambda x: x[2], reverse=True)
            return ranked
            
        except Exception as e:
            logger.warning(f"LLM排序失败: {e}, 使用默认顺序")
            # Fallback: 使用原始顺序，默认评分5.0
            return [(poi, time, 5.0) for poi, time in candidates]
    
    def _greedy_select(
        self,
        ranked_candidates: List[Tuple[CleanedPOI, float, float]],
        prev_poi_id: Optional[int],
        seg_config: SegmentConfig
    ) -> Tuple[CleanedPOI, float, str]:
        """
        贪心选择POI（优先LLM高分+最短通勤）
        
        Returns:
            (选中的POI, 通勤时间, 选择理由)
        """
        # 选择LLM评分最高的前3个候选
        top_candidates = ranked_candidates[:3]
        
        # 从中选择通勤时间最短的
        best = min(top_candidates, key=lambda x: x[1])
        poi, travel_time, llm_score = best
        
        # 生成选择理由
        reason = f"LLM推荐评分{llm_score:.1f}, 距离{'起点' if prev_poi_id is None else '上一地点'}车程{travel_time:.0f}分钟, 符合{seg_config.name}场景"
        
        return poi, travel_time, reason
    
    @staticmethod
    def _parse_time(time_str: str) -> datetime:
        """解析时间字符串为datetime"""
        h, m = map(int, time_str.split(':'))
        return datetime(2025, 1, 1, h, m)
    
    @staticmethod
    def _format_time(dt: datetime) -> str:
        """格式化datetime为HH:MM"""
        return dt.strftime('%H:%M')
    
    @staticmethod
    def _format_json(obj) -> str:
        """紧凑JSON格式"""
        import json
        return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))