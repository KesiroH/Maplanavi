"""
智能POI筛选与评分引擎
=====================

核心组件:
- POICandidateFilter: 本地POI初筛器
- LLMScorer: LLM语义评分器
- AmapPOIEnricher: 高德POI信息增强器
- CompositeScorer: 综合评分器

工作流程:
1. 本地数据初筛 -> 2. LLM语义评分 -> 3. 高德数据增强 -> 4. 综合评分排序
"""

from __future__ import annotations
import json
import logging
import math
import hashlib
from typing import Dict, List, Optional, Any
from pathlib import Path

from .user_profile_models import UserDemandProfile, CategoryConstraint
from .llm_configurator import LLMConfigurator

logger = logging.getLogger(__name__)


class POICandidateFilter:
    """本地POI初筛器"""
    
    def __init__(self, poi_data_path: str, categories_path: str):
        """
        Args:
            poi_data_path: 本地POI数据路径 (haidian_poi.json)
            categories_path: 类别映射表路径 (poi_categories.json)
        """
        self.poi_data_path = Path(poi_data_path)
        self.categories_path = Path(categories_path)
        
        self.poi_data = self._load_poi_data()
        self.category_mapping = self._load_category_mapping()
        
        logger.info(f"POICandidateFilter初始化完成: {len(self._get_all_pois())} 个POI")
    
    def _load_poi_data(self) -> Dict:
        """加载POI数据"""
        if not self.poi_data_path.exists():
            raise FileNotFoundError(f"POI数据文件不存在: {self.poi_data_path}")
        
        with open(self.poi_data_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _load_category_mapping(self) -> Dict:
        """加载类别映射表，构建多级索引"""
        if not self.categories_path.exists():
            raise FileNotFoundError(f"类别映射文件不存在: {self.categories_path}")
        
        with open(self.categories_path, 'r', encoding='utf-8') as f:
            categories = json.load(f)
        
        mapping = {
            'by_code': {},
            'by_major': {},
            'by_middle': {},
            'by_small': {}
        }
        
        for cat in categories:
            code = cat.get('NEW_TYPE', '')
            major = cat.get('大类', '')
            middle = cat.get('中类', '')
            small = cat.get('小类', '')
            
            mapping['by_code'][code] = cat
            
            if major:
                if major not in mapping['by_major']:
                    mapping['by_major'][major] = []
                mapping['by_major'][major].append(code)
            
            if middle:
                if middle not in mapping['by_middle']:
                    mapping['by_middle'][middle] = []
                mapping['by_middle'][middle].append(code)
            
            if small:
                if small not in mapping['by_small']:
                    mapping['by_small'][small] = []
                mapping['by_small'][small].append(code)
        
        return mapping
    
    def _get_all_pois(self) -> List[Dict]:
        """获取所有POI列表"""
        all_pois = []
        categories = self.poi_data.get('categories', [])
        for cat in categories:
            all_pois.extend(cat.get('pois', []))
        return all_pois
    
    def filter_by_category(self, pois: List[Dict], category_constraint: CategoryConstraint) -> List[Dict]:
        """
        根据类别约束过滤POI
        
        Args:
            pois: POI列表
            category_constraint: 类别约束（包含major/middle/small/specific_name）
        
        Returns:
            过滤后的POI列表
        """
        if not category_constraint:
            return pois
        
        filtered = []
        
        target_codes = set()
        
        if category_constraint.major:
            major_codes = self.category_mapping['by_major'].get(category_constraint.major, [])
            target_codes.update(major_codes)
        
        if category_constraint.middle:
            middle_codes = self.category_mapping['by_middle'].get(category_constraint.middle, [])
            if target_codes:
                target_codes = target_codes.intersection(set(middle_codes))
            else:
                target_codes.update(middle_codes)
        
        if category_constraint.small:
            small_codes = self.category_mapping['by_small'].get(category_constraint.small, [])
            if target_codes:
                target_codes = target_codes.intersection(set(small_codes))
            else:
                target_codes.update(small_codes)
        
        if category_constraint.specific_name:
            specific_name = category_constraint.specific_name.lower()
            for poi in pois:
                name = poi.get('name', '').lower()
                if specific_name in name:
                    filtered.append(poi)
            return filtered
        
        if not target_codes:
            return pois
        
        for poi in pois:
            typecode = poi.get('typecode', '')
            poi_codes = set(typecode.split('|'))
            
            if poi_codes.intersection(target_codes):
                filtered.append(poi)
        
        logger.debug(f"类别过滤: {len(pois)} -> {len(filtered)} 个POI")
        return filtered
    
    def filter_by_distance(
        self, 
        pois: List[Dict], 
        start_point: List[float], 
        max_distance_km: float = 10.0
    ) -> List[Dict]:
        """
        根据起点距离过滤POI（使用Haversine公式）
        
        Args:
            pois: POI列表
            start_point: 起点坐标 [经度, 纬度]
            max_distance_km: 最大距离（公里）
        
        Returns:
            过滤后的POI列表，每个POI添加distance_km字段
        """
        filtered = []
        start_lon, start_lat = start_point
        
        for poi in pois:
            location = poi.get('location', '')
            if not location:
                continue
            
            try:
                parts = location.split(',')
                poi_lon = float(parts[0])
                poi_lat = float(parts[1])
                
                distance = self.haversine_distance(start_lat, start_lon, poi_lat, poi_lon)
                
                if distance <= max_distance_km:
                    poi_with_distance = poi.copy()
                    poi_with_distance['distance_km'] = distance
                    filtered.append(poi_with_distance)
            except (ValueError, IndexError) as e:
                logger.warning(f"POI坐标解析失败: {location}, {e}")
                continue
        
        logger.debug(f"距离过滤: {len(pois)} -> {len(filtered)} 个POI (max: {max_distance_km}km)")
        return filtered
    
    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        使用Haversine公式计算两点间距离
        
        Args:
            lat1, lon1: 点1的纬度和经度
            lat2, lon2: 点2的纬度和经度
        
        Returns:
            距离（公里）
        """
        R = 6371.0
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = math.sin(delta_lat / 2) ** 2 + \
            math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def filter_by_negative_keywords(self, pois: List[Dict], negative_keywords: List[str]) -> List[Dict]:
        """
        根据负面关键词过滤POI
        
        Args:
            pois: POI列表
            negative_keywords: 负面关键词列表
        
        Returns:
            过滤后的POI列表
        """
        if not negative_keywords:
            return pois
        
        filtered = []
        negative_lower = [kw.lower() for kw in negative_keywords]
        
        for poi in pois:
            name = poi.get('name', '').lower()
            address = poi.get('address', '').lower()
            poi_type = poi.get('type', '').lower()
            
            combined_text = f"{name} {address} {poi_type}"
            
            should_exclude = False
            for keyword in negative_lower:
                if keyword in combined_text:
                    should_exclude = True
                    break
            
            if not should_exclude:
                filtered.append(poi)
        
        logger.debug(f"负面关键词过滤: {len(pois)} -> {len(filtered)} 个POI")
        return filtered
    
    def get_candidates(self, user_profile: UserDemandProfile) -> List[Dict]:
        """
        综合过滤，返回候选POI列表
        
        Args:
            user_profile: 用户需求画像
        
        Returns:
            候选POI列表
        """
        all_pois = self._get_all_pois()
        logger.info(f"开始筛选候选POI，总数: {len(all_pois)}")
        
        start_point = user_profile.hard_constraints.start_point.location
        
        interests = user_profile.soft_preferences.interests
        negative_keywords = user_profile.soft_preferences.negative_keywords
        
        candidate_pois = []
        
        if interests:
            for interest in interests:
                category_constraint = interest.category_constraint
                pois_by_interest = self.filter_by_category(all_pois, category_constraint)
                candidate_pois.extend(pois_by_interest)
            
            seen_ids = set()
            unique_pois = []
            for poi in candidate_pois:
                poi_id = poi.get('id', '')
                if poi_id and poi_id not in seen_ids:
                    seen_ids.add(poi_id)
                    unique_pois.append(poi)
            candidate_pois = unique_pois
        else:
            candidate_pois = all_pois
        
        candidate_pois = self.filter_by_negative_keywords(candidate_pois, negative_keywords)
        
        candidate_pois = self.filter_by_distance(
            candidate_pois, 
            start_point, 
            max_distance_km=15.0
        )
        
        candidate_pois.sort(key=lambda x: x.get('distance_km', float('inf')))
        
        logger.info(f"候选POI筛选完成: {len(candidate_pois)} 个")
        return candidate_pois


class LLMScorer:
    """LLM语义评分器"""
    
    def __init__(self, llm_client: LLMConfigurator):
        """
        Args:
            llm_client: LLM配置客户端
        """
        self.llm = llm_client
    
    def build_scoring_prompt(self, poi_features: List[Dict], user_preferences: Dict) -> str:
        """
        构造评分Prompt
        
        Args:
            poi_features: POI特征列表
            user_preferences: 用户偏好
        
        Returns:
            评分Prompt
        """
        poi_summaries = []
        for i, poi in enumerate(poi_features):
            poi_summaries.append({
                "index": i,
                "name": poi.get('name', ''),
                "type": poi.get('type', ''),
                "address": poi.get('address', ''),
                "distance_km": round(poi.get('distance_km', 0), 2),
                "rating": poi.get('business', {}).get('rating', ''),
                "tags": poi.get('business', {}).get('tag', '')
            })
        
        preferences_str = json.dumps(user_preferences, ensure_ascii=False, indent=2)
        pois_str = json.dumps(poi_summaries, ensure_ascii=False, indent=2)
        
        prompt = f"""你是一个专业的旅游推荐专家，请根据用户偏好为以下POI进行相关性评分。

## 用户偏好
{preferences_str}

## 待评分POI列表
{pois_str}

## 评分标准 (0-10分)
- 10分: 完美匹配用户需求，距离近、评分高、类型完全符合
- 8-9分: 高度匹配，大部分条件满足
- 6-7分: 中等匹配，基本条件满足
- 4-5分: 低匹配度，部分条件不满足
- 0-3分: 不匹配或距离过远

## 评分维度
1. 类型相关性 (权重40%): POI类型是否匹配用户兴趣
2. 距离因素 (权重30%): 距离越近分数越高
3. 评分因素 (权重20%): 现有评分越高分数越高
4. 特色匹配 (权重10%): 标签是否匹配用户偏好

请返回JSON格式结果:
{{
  "scores": [
    {{"index": 0, "score": 8.5, "reason": "类型匹配，距离适中，评分较高"}},
    {{"index": 1, "score": 6.0, "reason": "类型基本匹配，但距离较远"}}
  ]
}}"""
        
        return prompt
    
    def score_batch(self, pois: List[Dict], user_preferences: Dict, batch_size: int = 15) -> List[float]:
        """
        批量评分，返回0-10的相关性得分列表
        
        Args:
            pois: POI列表
            user_preferences: 用户偏好
            batch_size: 每批处理的POI数量
        
        Returns:
            评分列表，与输入POI顺序对应
        """
        if not pois:
            return []
        
        all_scores = [5.0] * len(pois)
        
        for i in range(0, len(pois), batch_size):
            batch = pois[i:i + batch_size]
            
            try:
                prompt = self.build_scoring_prompt(batch, user_preferences)
                
                response = self.llm.call_json(prompt)
                
                scores = response.get('scores', [])
                for score_item in scores:
                    idx = score_item.get('index', -1)
                    score = score_item.get('score', 5.0)
                    
                    if 0 <= idx < len(batch):
                        actual_idx = i + idx
                        all_scores[actual_idx] = max(0, min(10, float(score)))
                
                logger.debug(f"LLM评分批次 {i//batch_size + 1}: {len(batch)} 个POI")
                
            except Exception as e:
                logger.error(f"LLM评分失败: {e}")
                for j in range(len(batch)):
                    actual_idx = i + j
                    all_scores[actual_idx] = self._fallback_score(batch[j], user_preferences)
        
        logger.info(f"LLM评分完成: {len(pois)} 个POI")
        return all_scores
    
    def _fallback_score(self, poi: Dict, user_preferences: Dict) -> float:
        """LLM失败时的备用评分逻辑"""
        score = 5.0
        
        try:
            rating = float(poi.get('business', {}).get('rating', 0))
            if rating > 4.5:
                score += 1.5
            elif rating > 4.0:
                score += 1.0
            elif rating > 3.5:
                score += 0.5
        except (ValueError, TypeError):
            pass
        
        distance = poi.get('distance_km', 10)
        if distance < 2:
            score += 1.0
        elif distance < 5:
            score += 0.5
        elif distance > 10:
            score -= 1.0
        
        return max(0, min(10, score))


class AmapPOIEnricher:
    """高德POI信息增强器"""
    
    def __init__(self, amap_client, cache_enabled: bool = True):
        """
        Args:
            amap_client: 高德地图客户端 (GaodeMapClient实例)
            cache_enabled: 是否启用缓存
        """
        self.client = amap_client
        self.cache_enabled = cache_enabled
        self.cache: Dict[str, Dict] = {}
    
    def _get_cache_key(self, poi_id: str) -> str:
        """生成缓存键"""
        return f"poi_{poi_id}"
    
    def enrich_poi(self, poi: Dict) -> Dict:
        """
        获取POI实时信息（评分、营业时间等）
        
        Args:
            poi: POI数据
        
        Returns:
            增强后的POI数据
        """
        poi_id = poi.get('id', '')
        
        if not poi_id:
            return poi
        
        cache_key = self._get_cache_key(poi_id)
        
        if self.cache_enabled and cache_key in self.cache:
            logger.debug(f"缓存命中: {poi_id}")
            enriched = poi.copy()
            enriched['amap_enriched'] = self.cache[cache_key]
            return enriched
        
        try:
            results = self.client.poi_search_by_id(poi_id, return_model=False)
            
            if results and results.get('pois'):
                amap_data = results['pois'][0]
                
                enriched_info = {
                    'amap_id': amap_data.get('id'),
                    'amap_rating': amap_data.get('biz_ext', {}).get('rating'),
                    'amap_cost': amap_data.get('biz_ext', {}).get('cost'),
                    'amap_opentime': amap_data.get('biz_ext', {}).get('opentime'),
                    'amap_photos': amap_data.get('photos', [])[:3],
                    'enriched_at': self._get_timestamp()
                }
                
                if self.cache_enabled:
                    self.cache[cache_key] = enriched_info
                
                enriched = poi.copy()
                enriched['amap_enriched'] = enriched_info
                
                logger.debug(f"高德API增强成功: {poi.get('name', '')}")
                return enriched
            
        except Exception as e:
            logger.warning(f"高德API增强失败: {poi.get('name', '')}, {e}")
        
        return poi
    
    def enrich_batch(self, pois: List[Dict], top_n: int = 30) -> List[Dict]:
        """
        批量增强，仅对Top N调用API以控制配额
        
        Args:
            pois: POI列表
            top_n: 仅对前N个POI调用API
        
        Returns:
            增强后的POI列表
        """
        if not pois:
            return pois
        
        enriched_pois = []
        
        for i, poi in enumerate(pois):
            if i < top_n:
                enriched = self.enrich_poi(poi)
            else:
                enriched = poi.copy()
                enriched['amap_enriched'] = {'skipped': True, 'reason': '超出Top N限制'}
            
            enriched_pois.append(enriched)
        
        logger.info(f"高德API增强完成: {min(len(pois), top_n)}/{len(pois)} 个POI")
        return enriched_pois
    
    @staticmethod
    def _get_timestamp() -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
        logger.info("缓存已清空")


class CompositeScorer:
    """综合评分器"""
    
    DEFAULT_WEIGHTS = {
        'llm_relevance': 0.5,
        'amap_rating': 0.3,
        'distance_decay': 0.2
    }
    
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Args:
            weights: 权重配置，默认:
                - llm_relevance: 0.5
                - amap_rating: 0.3
                - distance_decay: 0.2
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.001:
            logger.warning(f"权重总和不为1.0 ({total})，将自动归一化")
            self.weights = {k: v / total for k, v in self.weights.items()}
    
    def distance_decay(self, distance_km: float, max_distance_km: float = 10.0) -> float:
        """
        距离衰减函数，返回0-1的衰减因子
        
        使用指数衰减模型: decay = exp(-distance / max_distance)
        
        Args:
            distance_km: 实际距离（公里）
            max_distance_km: 参考最大距离
        
        Returns:
            衰减因子 (0-1)
        """
        if distance_km <= 0:
            return 1.0
        
        decay = math.exp(-distance_km / max_distance_km)
        
        return max(0.0, min(1.0, decay))
    
    def normalize_rating(self, rating: Any) -> float:
        """
        归一化评分到0-1范围
        
        Args:
            rating: 原始评分（可能是字符串或数字）
        
        Returns:
            归一化评分 (0-1)
        """
        try:
            rating_float = float(rating)
            return max(0.0, min(1.0, rating_float / 5.0))
        except (ValueError, TypeError):
            return 0.6
    
    def compute_score(
        self, 
        poi: Dict, 
        llm_score: float, 
        amap_rating: Optional[float], 
        distance_km: float,
        max_distance_km: float = 10.0
    ) -> float:
        """
        计算综合评分: Final_Score = w1 * LLM + w2 * Rating + w3 * Distance
        
        Args:
            poi: POI数据
            llm_score: LLM评分 (0-10)
            amap_rating: 高德评分 (0-5)，可能为None
            distance_km: 距离（公里）
            max_distance_km: 最大参考距离
        
        Returns:
            综合评分 (0-10)
        """
        llm_normalized = llm_score / 10.0
        
        if amap_rating is not None:
            rating_normalized = self.normalize_rating(amap_rating)
        else:
            business = poi.get('business', {})
            biz_rating = business.get('rating')
            if biz_rating:
                rating_normalized = self.normalize_rating(biz_rating)
            else:
                rating_normalized = 0.6
        
        distance_factor = self.distance_decay(distance_km, max_distance_km)
        
        composite = (
            self.weights['llm_relevance'] * llm_normalized +
            self.weights['amap_rating'] * rating_normalized +
            self.weights['distance_decay'] * distance_factor
        )
        
        final_score = composite * 10.0
        
        return round(final_score, 2)
    
    def rank_pois(self, pois: List[Dict], scores: List[float]) -> List[Dict]:
        """
        排序并返回CandidateList
        
        Args:
            pois: POI列表
            scores: 对应的评分列表
        
        Returns:
            排序后的POI列表，包含综合评分
        """
        if len(pois) != len(scores):
            logger.warning(f"POI数量({len(pois)})与评分数量({len(scores)})不匹配")
            min_len = min(len(pois), len(scores))
            pois = pois[:min_len]
            scores = scores[:min_len]
        
        ranked_pois = []
        for poi, score in zip(pois, scores):
            ranked_poi = poi.copy()
            ranked_poi['composite_score'] = score
            ranked_pois.append(ranked_poi)
        
        ranked_pois.sort(key=lambda x: x.get('composite_score', 0), reverse=True)
        
        for rank, poi in enumerate(ranked_pois, 1):
            poi['rank'] = rank
        
        logger.info(f"POI排序完成: {len(ranked_pois)} 个候选")
        return ranked_pois


class POISelectionEngine:
    """POI选择引擎 - 整合所有组件"""
    
    def __init__(
        self,
        poi_data_path: str,
        categories_path: str,
        llm_client: Optional[LLMConfigurator] = None,
        amap_client = None,
        scorer_weights: Optional[Dict[str, float]] = None
    ):
        """
        Args:
            poi_data_path: POI数据路径
            categories_path: 类别映射路径
            llm_client: LLM客户端（可选）
            amap_client: 高德客户端（可选）
            scorer_weights: 评分权重（可选）
        """
        self.filter = POICandidateFilter(poi_data_path, categories_path)
        
        self.llm_scorer = LLMScorer(llm_client) if llm_client else None
        
        self.amap_enricher = AmapPOIEnricher(amap_client) if amap_client else None
        
        self.composite_scorer = CompositeScorer(scorer_weights)
        
        self.llm_client = llm_client
        self.amap_client = amap_client
    
    def select_pois(
        self,
        user_profile: UserDemandProfile,
        use_llm: bool = True,
        use_amap: bool = True,
        amap_top_n: int = 30,
        top_k: int = 50
    ) -> List[Dict]:
        """
        执行完整的POI选择流程
        
        Args:
            user_profile: 用户需求画像
            use_llm: 是否使用LLM评分
            use_amap: 是否使用高德API增强
            amap_top_n: 高德API增强的Top N
            top_k: 返回的Top K个POI
        
        Returns:
            排序后的候选POI列表
        """
        logger.info("=" * 50)
        logger.info("开始POI选择流程")
        
        candidates = self.filter.get_candidates(user_profile)
        
        if not candidates:
            logger.warning("未找到符合条件的候选POI")
            return []
        
        user_preferences = {
            'interests': [
                {
                    'type': i.type,
                    'level': i.level,
                    'category': i.category_constraint.model_dump() if i.category_constraint else None
                }
                for i in user_profile.soft_preferences.interests
            ],
            'pace': user_profile.soft_preferences.pace,
            'budget_level': user_profile.soft_preferences.budget_level,
            'negative_keywords': user_profile.soft_preferences.negative_keywords
        }
        
        if use_llm and self.llm_scorer:
            llm_scores = self.llm_scorer.score_batch(candidates, user_preferences)
        else:
            llm_scores = [5.0] * len(candidates)
        
        if use_amap and self.amap_enricher:
            candidates = self.amap_enricher.enrich_batch(candidates, top_n=amap_top_n)
        
        final_scores = []
        for i, poi in enumerate(candidates):
            llm_score = llm_scores[i]
            
            amap_rating = None
            amap_enriched = poi.get('amap_enriched', {})
            if amap_enriched and not amap_enriched.get('skipped'):
                amap_rating = amap_enriched.get('amap_rating')
            
            distance_km = poi.get('distance_km', 10.0)
            
            final_score = self.composite_scorer.compute_score(
                poi, llm_score, amap_rating, distance_km
            )
            final_scores.append(final_score)
        
        ranked_pois = self.composite_scorer.rank_pois(candidates, final_scores)
        
        result = ranked_pois[:top_k]
        
        logger.info(f"POI选择完成: 返回 {len(result)} 个候选")
        logger.info("=" * 50)
        
        return result
