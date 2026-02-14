"""
高德地图 API 数据模型
====================

定义配置模型、返回模型和坐标系相关枚举。
"""

from __future__ import annotations
from typing import Optional, List, Tuple
from enum import Enum
from pydantic import BaseModel, Field, field_validator
import os


class CoordinateSystem(str, Enum):
    """坐标系类型枚举"""
    WGS84 = "WGS84"
    GCJ02 = "GCJ02"
    BD09 = "BD09"


class AmapConfig(BaseModel):
    """高德地图 API 配置模型"""
    api_key: str = Field(..., description="高德地图 Web 服务 API Key")
    timeout: int = Field(default=10, ge=1, le=120, description="请求超时时间（秒）")
    max_retries: int = Field(default=3, ge=0, le=10, description="最大重试次数")
    retry_delay: float = Field(default=1.0, ge=0.1, le=60.0, description="重试间隔（秒）")

    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or v == "your_amap_api_key_here":
            raise ValueError("请提供有效的高德地图 API Key")
        return v

    @classmethod
    def from_env(cls, **kwargs) -> "AmapConfig":
        """
        从环境变量创建配置

        环境变量:
            AMAP_API_KEY: 高德地图 API Key（必需）
            AMAP_TIMEOUT: 请求超时时间（可选，默认10）
            AMAP_MAX_RETRIES: 最大重试次数（可选，默认3）
            AMAP_RETRY_DELAY: 重试间隔（可选，默认1.0）
        """
        api_key = os.environ.get("AMAP_API_KEY")
        if not api_key:
            raise ValueError("环境变量 AMAP_API_KEY 未设置")

        return cls(
            api_key=api_key,
            timeout=int(os.environ.get("AMAP_TIMEOUT", kwargs.get("timeout", 10))),
            max_retries=int(os.environ.get("AMAP_MAX_RETRIES", kwargs.get("max_retries", 3))),
            retry_delay=float(os.environ.get("AMAP_RETRY_DELAY", kwargs.get("retry_delay", 1.0))),
        )


class AmapLocation(BaseModel):
    """位置信息模型"""
    longitude: float = Field(..., description="经度")
    latitude: float = Field(..., description="纬度")
    province: Optional[str] = Field(default=None, description="省份")
    city: Optional[str] = Field(default=None, description="城市")
    district: Optional[str] = Field(default=None, description="区县")
    address: Optional[str] = Field(default=None, description="详细地址")
    adcode: Optional[str] = Field(default=None, description="行政区划代码")
    citycode: Optional[str] = Field(default=None, description="城市代码")

    @field_validator('latitude')
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not (-90 <= v <= 90):
            raise ValueError(f"纬度超出有效范围: {v}")
        return v

    @field_validator('longitude')
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not (-180 <= v <= 180):
            raise ValueError(f"经度超出有效范围: {v}")
        return v

    @property
    def coordinate_str(self) -> str:
        """返回高德API格式的坐标字符串 '经度,纬度'"""
        return f"{self.longitude},{self.latitude}"

    @classmethod
    def from_amap_geocode(cls, data: dict) -> "AmapLocation":
        """从高德地理编码结果创建"""
        location = data.get("location", "").split(",")
        return cls(
            longitude=float(location[0]) if len(location) == 2 else 0.0,
            latitude=float(location[1]) if len(location) == 2 else 0.0,
            province=data.get("province"),
            city=data.get("city"),
            district=data.get("district"),
            address=data.get("formatted_address"),
            adcode=data.get("adcode"),
            citycode=data.get("citycode"),
        )

    @classmethod
    def from_amap_regeocode(cls, data: dict) -> "AmapLocation":
        """从高德逆地理编码结果创建"""
        address_component = data.get("addressComponent", {})
        location = data.get("formatted_address", "")
        return cls(
            longitude=0.0,
            latitude=0.0,
            province=address_component.get("province"),
            city=address_component.get("city"),
            district=address_component.get("district"),
            address=location,
            adcode=address_component.get("adcode"),
            citycode=address_component.get("citycode"),
        )


class AmapRouteStep(BaseModel):
    """路径步骤模型"""
    instruction: str = Field(..., description="行驶指令")
    road_name: Optional[str] = Field(default=None, description="道路名称")
    distance: int = Field(default=0, description="本步骤距离（米）")
    duration: int = Field(default=0, description="本步骤时长（秒）")
    polyline: Optional[List[Tuple[float, float]]] = Field(default=None, description="路径坐标点列表")


class AmapRoute(BaseModel):
    """路径规划结果模型"""
    distance: int = Field(..., description="总距离（米）")
    duration: int = Field(..., description="总时长（秒）")
    steps: List[AmapRouteStep] = Field(default_factory=list, description="路径步骤列表")
    toll_distance: Optional[int] = Field(default=None, description="收费道路距离（米）")
    tolls: Optional[int] = Field(default=None, description="收费金额（元）")
    traffic_lights: Optional[int] = Field(default=None, description="红绿灯数量")

    @property
    def distance_km(self) -> float:
        """距离（公里）"""
        return self.distance / 1000.0

    @property
    def duration_minutes(self) -> float:
        """时长（分钟）"""
        return self.duration / 60.0

    @classmethod
    def from_amap_driving(cls, data: dict) -> "AmapRoute":
        """从高德驾车路径规划结果创建"""
        steps = []
        for step in data.get("steps", []):
            polyline = None
            if step.get("polyline"):
                polyline = [
                    (float(p.split(",")[0]), float(p.split(",")[1]))
                    for p in step["polyline"].split(";")
                ]
            steps.append(AmapRouteStep(
                instruction=step.get("instruction", ""),
                road_name=step.get("road"),
                distance=int(step.get("distance", 0)),
                duration=int(step.get("duration", 0)),
                polyline=polyline,
            ))

        return cls(
            distance=int(data.get("distance", 0)),
            duration=int(data.get("duration", 0)),
            steps=steps,
            toll_distance=int(data.get("toll_distance", 0)) if data.get("toll_distance") else None,
            tolls=int(data.get("tolls", 0)) if data.get("tolls") else None,
            traffic_lights=int(data.get("traffic_light_count", 0)) if data.get("traffic_light_count") else None,
        )

    @classmethod
    def from_amap_walking(cls, data: dict) -> "AmapRoute":
        """从高德步行路径规划结果创建"""
        steps = []
        for step in data.get("steps", []):
            polyline = None
            if step.get("polyline"):
                polyline = [
                    (float(p.split(",")[0]), float(p.split(",")[1]))
                    for p in step["polyline"].split(";")
                ]
            steps.append(AmapRouteStep(
                instruction=step.get("instruction", ""),
                road_name=step.get("road"),
                distance=int(step.get("distance", 0)),
                duration=int(step.get("duration", 0)),
                polyline=polyline,
            ))

        return cls(
            distance=int(data.get("distance", 0)),
            duration=int(data.get("duration", 0)),
            steps=steps,
        )


class AmapPOI(BaseModel):
    """POI信息模型"""
    id: str = Field(..., description="POI ID")
    name: str = Field(..., description="POI名称")
    category: Optional[str] = Field(default=None, description="类别")
    type_code: Optional[str] = Field(default=None, description="类别代码")
    longitude: float = Field(..., description="经度")
    latitude: float = Field(..., description="纬度")
    address: Optional[str] = Field(default=None, description="地址")
    province: Optional[str] = Field(default=None, description="省份")
    city: Optional[str] = Field(default=None, description="城市")
    district: Optional[str] = Field(default=None, description="区县")
    rating: Optional[float] = Field(default=None, ge=0, le=5, description="评分（0-5）")
    cost: Optional[float] = Field(default=None, description="人均消费")
    tel: Optional[str] = Field(default=None, description="电话")
    distance: Optional[int] = Field(default=None, description="距离中心点距离（米）")

    @property
    def coordinate_str(self) -> str:
        """返回高德API格式的坐标字符串"""
        return f"{self.longitude},{self.latitude}"

    @classmethod
    def from_amap_poi(cls, data: dict) -> "AmapPOI":
        """从高德POI搜索结果创建"""
        location = data.get("location", "").split(",")
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            category=data.get("type"),
            type_code=data.get("typecode"),
            longitude=float(location[0]) if len(location) == 2 else 0.0,
            latitude=float(location[1]) if len(location) == 2 else 0.0,
            address=data.get("address"),
            province=data.get("pname"),
            city=data.get("cityname"),
            district=data.get("adname"),
            rating=float(data.get("biz_ext", {}).get("rating", 0)) if data.get("biz_ext") else None,
            cost=float(data.get("biz_ext", {}).get("cost", 0)) if data.get("biz_ext") else None,
            tel=data.get("tel"),
            distance=int(data.get("distance", 0)) if data.get("distance") else None,
        )


class AmapDistance(BaseModel):
    """距离测量结果模型"""
    origin: str = Field(..., description="起点坐标 '经度,纬度'")
    destination: str = Field(..., description="终点坐标 '经度,纬度'")
    distance: int = Field(..., description="距离（米）")
    duration: Optional[int] = Field(default=None, description="时长（秒）")

    @property
    def distance_km(self) -> float:
        """距离（公里）"""
        return self.distance / 1000.0

    @property
    def duration_minutes(self) -> Optional[float]:
        """时长（分钟）"""
        return self.duration / 60.0 if self.duration else None

    @classmethod
    def from_amap_distance(cls, data: dict, origin: str, destination: str) -> "AmapDistance":
        """从高德距离测量结果创建"""
        return cls(
            origin=origin,
            destination=destination,
            distance=int(data.get("distance", 0)),
            duration=int(data.get("duration", 0)) if data.get("duration") else None,
        )


class AmapDistrict(BaseModel):
    """行政区划模型"""
    adcode: str = Field(..., description="行政区划代码")
    name: str = Field(..., description="名称")
    level: Optional[str] = Field(default=None, description="级别")
    center: Optional[str] = Field(default=None, description="中心点坐标")
    polyline: Optional[str] = Field(default=None, description="边界坐标")
    districts: List["AmapDistrict"] = Field(default_factory=list, description="下级行政区")

    @classmethod
    def from_amap_district(cls, data: dict) -> "AmapDistrict":
        """从高德行政区划查询结果创建"""
        districts = [cls.from_amap_district(d) for d in data.get("districts", [])]
        return cls(
            adcode=data.get("adcode", ""),
            name=data.get("name", ""),
            level=data.get("level"),
            center=data.get("center"),
            polyline=data.get("polyline"),
            districts=districts,
        )


AmapDistrict.model_rebuild()
