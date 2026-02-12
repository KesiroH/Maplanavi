"""
数据模型定义
使用Pydantic确保类型安全和数据验证
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field, validator
from datetime import datetime

# =========================
# 基础数据模型
# =========================

class RawPOI(BaseModel):
    """原始POI数据（来自Overpass）"""
    osm_type: str  # node / way / relation
    osmid: int
    lat: float
    lon: float
    tags: Dict[str, str] = Field(default_factory=dict)
    
    class Config:
        frozen = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于JSON序列化）"""
        return {
            'osm_type': self.osm_type,
            'osmid': self.osmid,
            'lat': self.lat,
            'lon': self.lon,
            'tags': self.tags
        }

class CleanedPOI(BaseModel):
    """清洗后的POI数据"""
    id: int  # 内部ID（索引）
    osm_type: str
    osmid: int
    name: str
    category: str  # 中文类别
    lat: float
    lon: float
    tags: Dict[str, str] = Field(default_factory=dict)
    
    @validator('lat')
    def validate_lat(cls, v):
        if not (-90 <= v <= 90):
            raise ValueError(f"Invalid latitude: {v}")
        return v
    
    @validator('lon')
    def validate_lon(cls, v):
        if not (-180 <= v <= 180):
            raise ValueError(f"Invalid longitude: {v}")
        return v
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于JSON序列化）"""
        return {
            'id': self.id,
            'osm_type': self.osm_type,
            'osmid': self.osmid,
            'name': self.name,
            'category': self.category,
            'lat': self.lat,
            'lon': self.lon,
            'tags': self.tags
        }

class EnhancedPOI(CleanedPOI):
    """LLM增强后的POI数据"""
    enhanced_info: Dict[str, Any] = Field(default_factory=dict)
    # enhanced_info包含:
    # - rating: float (0-5)
    # - price_range: str
    # - opening_hours: str
    # - is_open: bool
    # - recommended_duration: int (分钟)
    # - crowd_level: str (低/中/高)
    # - tags_llm: List[str]
    # - review_summary: str
    data_source: str = "LLM"
    updated_at: str = Field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d'))
    llm_processed: bool = False
    llm_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于JSON序列化）"""
        base_dict = super().to_dict()
        base_dict.update({
            'enhanced_info': self.enhanced_info,
            'data_source': self.data_source,
            'updated_at': self.updated_at,
            'llm_processed': self.llm_processed,
            'llm_error': self.llm_error
        })
        return base_dict

# =========================
# 路网数据模型
# =========================

class TimeMatrix(BaseModel):
    """路网时间矩阵"""
    matrix: List[List[Optional[float]]]  # 分钟，None表示不可达
    poi_ids: List[int]  # 对应POI的ID列表（第0个为起点）
    
    def get_time(self, from_idx: int, to_idx: int) -> Optional[float]:
        """获取两点间时间"""
        try:
            return self.matrix[from_idx][to_idx]
        except IndexError:
            return None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于JSON序列化）"""
        return {
            'matrix': self.matrix,
            'poi_ids': self.poi_ids,
            'shape': [len(self.matrix), len(self.matrix[0]) if self.matrix else 0]
        }

# =========================
# 行程相关模型
# =========================

class SegmentConfig(BaseModel):
    """环节配置（来自config.yaml）"""
    segment: int
    name: str
    time_range: str
    category: List[str]
    max_commute_minutes: Optional[int]
    stay_minutes: int
    description: str

class ItineraryStep(BaseModel):
    """行程单步"""
    segment: int
    segment_name: str
    time_start: str
    time_end: str
    poi_id: int
    poi_name: str
    poi_category: str
    poi_lat: float
    poi_lon: float
    travel_time_min: float  # 从上一点到此点的通勤时间
    stay_time_min: int
    reason: str  # 选择理由
    llm_recommendation_score: Optional[float] = None  # LLM评分
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于JSON序列化）"""
        return {
            'segment': self.segment,
            'segment_name': self.segment_name,
            'time_start': self.time_start,
            'time_end': self.time_end,
            'poi_id': self.poi_id,
            'poi_name': self.poi_name,
            'poi_category': self.poi_category,
            'poi_lat': self.poi_lat,
            'poi_lon': self.poi_lon,
            'travel_time_min': self.travel_time_min,
            'stay_time_min': self.stay_time_min,
            'reason': self.reason,
            'llm_recommendation_score': self.llm_recommendation_score
        }

class Itinerary(BaseModel):
    """完整行程"""
    steps: List[ItineraryStep]
    total_travel_time: float  # 总通勤时间（分钟）
    total_stay_time: int      # 总停留时间（分钟）
    total_time: float         # 总时间
    date: str
    start_point: Tuple[float, float]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于JSON序列化）"""
        return {
            'steps': [step.to_dict() for step in self.steps],
            'total_travel_time': self.total_travel_time,
            'total_stay_time': self.total_stay_time,
            'total_time': self.total_time,
            'date': self.date,
            'start_point': list(self.start_point)
        }

class OptimizationLog(BaseModel):
    """优化记录"""
    segment: int
    issue: str
    original_poi: str
    new_poi: Optional[str] = None
    reason: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于JSON序列化）"""
        return {
            'segment': self.segment,
            'issue': self.issue,
            'original_poi': self.original_poi,
            'new_poi': self.new_poi,
            'reason': self.reason,
            'timestamp': self.timestamp
        }

# =========================
# 流程数据传递模型
# =========================

class ProcessedData(BaseModel):
    """主流程中间数据"""
    raw_pois: List[RawPOI] = Field(default_factory=list)
    cleaned_pois: List[CleanedPOI] = Field(default_factory=list)
    enhanced_pois: List[EnhancedPOI] = Field(default_factory=list)
    time_matrix: Optional[TimeMatrix] = None
    basic_itinerary: Optional[Itinerary] = None
    optimized_itinerary: Optional[Itinerary] = None
    optimization_logs: List[OptimizationLog] = Field(default_factory=list)
    narration: Dict[str, str] = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于JSON序列化）"""
        return {
            'raw_pois': [poi.to_dict() for poi in self.raw_pois],
            'cleaned_pois': [poi.to_dict() for poi in self.cleaned_pois],
            'enhanced_pois': [poi.to_dict() for poi in self.enhanced_pois],
            'time_matrix': self.time_matrix.to_dict() if self.time_matrix else None,
            'basic_itinerary': self.basic_itinerary.to_dict() if self.basic_itinerary else None,
            'optimized_itinerary': self.optimized_itinerary.to_dict() if self.optimized_itinerary else None,
            'optimization_logs': [log.to_dict() for log in self.optimization_logs],
            'narration': self.narration
        }