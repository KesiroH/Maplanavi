"""
公共模型定义
============

统一的基础数据模型，供所有模块使用。

包含:
- GeoPoint: 地理坐标点
- BaseResponse: 基础响应模型
- TimeSlot: 时间槽模型
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field, field_validator


class GeoPoint(BaseModel):
    """地理坐标点模型"""
    longitude: float = Field(..., description="经度", ge=-180, le=180)
    latitude: float = Field(..., description="纬度", ge=-90, le=90)
    name: Optional[str] = Field(default=None, description="地点名称")
    address: Optional[str] = Field(default=None, description="地址")

    @field_validator('latitude')
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not (-90 <= v <= 90):
            raise ValueError(f"纬度超出有效范围 [-90, 90]: {v}")
        return v

    @field_validator('longitude')
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not (-180 <= v <= 180):
            raise ValueError(f"经度超出有效范围 [-180, 180]: {v}")
        return v

    @property
    def coordinate_str(self) -> str:
        """返回 '经度,纬度' 格式字符串"""
        return f"{self.longitude},{self.latitude}"

    @property
    def tuple(self) -> tuple:
        """返回 (经度, 纬度) 元组"""
        return (self.longitude, self.latitude)

    @classmethod
    def from_tuple(cls, coord: tuple, name: Optional[str] = None) -> "GeoPoint":
        """从 (lng, lat) 元组创建"""
        return cls(longitude=coord[0], latitude=coord[1], name=name)

    def distance_to(self, other: "GeoPoint") -> float:
        """计算到另一个点的球面距离（公里）"""
        import math
        R = 6371.0  # 地球半径（公里）

        lat1, lat2 = math.radians(self.latitude), math.radians(other.latitude)
        dlat = math.radians(other.latitude - self.latitude)
        dlon = math.radians(other.longitude - self.longitude)

        a = (math.sin(dlat / 2) ** 2 +
             math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c


class TimeSlot(BaseModel):
    """时间槽模型"""
    id: int = Field(..., description="时间槽ID")
    time_period: str = Field(..., description="时间段 (morning/afternoon/evening)")
    start_hour: int = Field(..., ge=0, le=23, description="开始小时")
    end_hour: int = Field(..., ge=0, le=23, description="结束小时")
    poi_count: int = Field(default=2, ge=0, le=10, description="POI数量")

    @property
    def duration_hours(self) -> float:
        """持续小时数"""
        return self.end_hour - self.start_hour

    @property
    def duration_minutes(self) -> float:
        """持续分钟数"""
        return (self.end_hour - self.start_hour) * 60

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class BaseResponse(BaseModel):
    """基础响应模型"""
    success: bool = Field(default=True, description="是否成功")
    message: str = Field(default="", description="响应消息")
    data: Optional[Dict[str, Any]] = Field(default=None, description="响应数据")
    error_code: Optional[str] = Field(default=None, description="错误代码")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="时间戳"
    )

    @classmethod
    def ok(cls, message: str = "", data: Optional[Dict] = None) -> "BaseResponse":
        """创建成功响应"""
        return cls(success=True, message=message, data=data)

    @classmethod
    def error(cls, message: str, error_code: Optional[str] = None) -> "BaseResponse":
        """创建错误响应"""
        return cls(success=False, message=message, error_code=error_code)


class POIScore(BaseModel):
    """POI评分模型"""
    poi_id: str = Field(..., description="POI ID")
    name: str = Field(..., description="POI名称")
    score: float = Field(..., ge=0, le=10, description="综合评分")
    llm_relevance: Optional[float] = Field(default=None, ge=0, le=10, description="LLM相关性评分")
    rating: Optional[float] = Field(default=None, ge=0, le=5, description="高德评分")
    distance_km: Optional[float] = Field(default=None, description="距离（公里）")
    composite_score: float = Field(..., description="最终综合评分")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class RouteSegment(BaseModel):
    """路线段模型"""
    origin: GeoPoint = Field(..., description="起点")
    destination: GeoPoint = Field(..., description="终点")
    distance_m: int = Field(..., description="距离（米）")
    duration_min: int = Field(..., description="时长（分钟）")
    transport_mode: str = Field(default="driving", description="交通方式")

    @property
    def distance_km(self) -> float:
        return self.distance_m / 1000.0

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
