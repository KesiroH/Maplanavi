"""
用户需求数据模型
基于现有的 user.json 结构定义 Pydantic 模型
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime


class StartPoint(BaseModel):
    name: str
    location: List[float]

    @validator('location')
    def validate_location(cls, v):
        if len(v) != 2:
            raise ValueError("location 必须包含 [经度, 纬度] 两个值")
        lon, lat = v
        if not (-180 <= lon <= 180):
            raise ValueError(f"经度必须在 -180 到 180 之间，当前值: {lon}")
        if not (-90 <= lat <= 90):
            raise ValueError(f"纬度必须在 -90 到 90 之间，当前值: {lat}")
        return v


class EndPoint(BaseModel):
    type: str
    name: Optional[str] = None
    location: Optional[List[float]] = None

    @validator('type')
    def validate_type(cls, v):
        if v not in ["same_as_start", "custom"]:
            raise ValueError("type 必须是 'same_as_start' 或 'custom'")
        return v

    @validator('location')
    def validate_location(cls, v, values):
        if values.get('type') == 'custom':
            if v is None:
                raise ValueError("当 type 为 'custom' 时，location 不能为空")
            if len(v) != 2:
                raise ValueError("location 必须包含 [经度, 纬度] 两个值")
        return v


class Distribution(BaseModel):
    morning: int = Field(default=2, ge=0, le=10, description="上午POI数量")
    afternoon: int = Field(default=2, ge=0, le=10, description="下午POI数量")
    evening: int = Field(default=1, ge=0, le=10, description="晚上POI数量")


class CategoryConstraint(BaseModel):
    major: Optional[str] = Field(default=None, description="大类编码")
    middle: Optional[str] = Field(default=None, description="中类编码")
    small: Optional[str] = Field(default=None, description="小类编码")
    specific_name: Optional[str] = Field(default=None, description="具体名称")


class InterestPreference(BaseModel):
    type: str = Field(description="类型: sight, dining, shopping 等")
    level: str = Field(default="preferred", description="级别: strict, preferred, optional")
    meal: Optional[str] = Field(default=None, description="仅dining类型: lunch, dinner")
    category_constraint: Optional[CategoryConstraint] = None

    @validator('level')
    def validate_level(cls, v):
        if v not in ["strict", "preferred", "optional"]:
            raise ValueError("level 必须是 'strict', 'preferred' 或 'optional'")
        return v

    @validator('meal')
    def validate_meal(cls, v, values):
        if values.get('type') == 'dining' and v is not None:
            if v not in ["lunch", "dinner"]:
                raise ValueError("meal 必须是 'lunch' 或 'dinner'")
        return v


class HardConstraints(BaseModel):
    date: str = Field(description="出行日期，格式: YYYY-MM-DD")
    duration_days: int = Field(default=1, ge=1, le=30, description="出行天数")
    start_point: StartPoint
    end_point: EndPoint
    transport_mode: str = Field(default="driving", description="交通方式")
    distribution: Distribution = Field(default_factory=Distribution)

    @validator('date')
    def validate_date(cls, v):
        try:
            parsed = datetime.strptime(v, "%Y-%m-%d")
            if parsed.date() < datetime.now().date():
                raise ValueError("出行日期不能早于今天")
        except ValueError as e:
            raise ValueError(f"日期格式错误，应为 YYYY-MM-DD: {e}")
        return v

    @validator('transport_mode')
    def validate_transport_mode(cls, v):
        valid_modes = ["driving", "transit", "walking", "mixed"]
        if v not in valid_modes:
            raise ValueError(f"transport_mode 必须是: {valid_modes}")
        return v


class SoftPreferences(BaseModel):
    pace: str = Field(default="relaxed", description="游玩节奏")
    budget_level: int = Field(default=3, ge=1, le=5, description="预算等级 1-5")
    interests: List[InterestPreference] = Field(default_factory=list)
    negative_keywords: List[str] = Field(default_factory=list)

    @validator('pace')
    def validate_pace(cls, v):
        if v not in ["relaxed", "moderate", "intense"]:
            raise ValueError("pace 必须是 'relaxed', 'moderate' 或 'intense'")
        return v


class UserDemandProfile(BaseModel):
    meta: Dict[str, Any] = Field(default_factory=dict)
    hard_constraints: HardConstraints
    soft_preferences: SoftPreferences = Field(default_factory=SoftPreferences)

    def to_json_file(self, filepath: str) -> None:
        import json
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.model_dump(exclude_none=True), f, ensure_ascii=False, indent=2)

    @classmethod
    def from_json_file(cls, filepath: str) -> 'UserDemandProfile':
        import json
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(**data)


def create_default_profile() -> UserDemandProfile:
    return UserDemandProfile(
        meta={
            "user_id": f"u_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "session_id": f"s_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "created_at": datetime.now().isoformat()
        },
        hard_constraints=HardConstraints(
            date=(datetime.now().strftime('%Y-%m-%d')),
            duration_days=1,
            start_point=StartPoint(
                name="未设置",
                location=[116.397, 39.909]
            ),
            end_point=EndPoint(type="same_as_start"),
            transport_mode="driving",
            distribution=Distribution()
        ),
        soft_preferences=SoftPreferences(
            pace="relaxed",
            budget_level=3,
            interests=[],
            negative_keywords=[]
        )
    )
