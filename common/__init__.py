"""
公共模块
========

包含共享的模型、异常、日志等基础设施。
"""

from .models import (
    GeoPoint,
    TimeSlot,
    BaseResponse,
    POIScore,
    RouteSegment,
)
from .exceptions import (
    MaplanaviBaseException,
    ConfigurationError,
    LLMServiceError,
    MapServiceError,
    DataValidationError,
    InsufficientPOIError,
    APIRateLimitError,
    NetworkError,
    FileNotFoundError,
    ParseError,
)

def get_pipeline():
    """延迟导入 MaplanaviPipeline，避免循环依赖"""
    from .pipeline import MaplanaviPipeline
    return MaplanaviPipeline

__all__ = [
    'GeoPoint',
    'TimeSlot',
    'BaseResponse',
    'POIScore',
    'RouteSegment',
    'MaplanaviBaseException',
    'ConfigurationError',
    'LLMServiceError',
    'MapServiceError',
    'DataValidationError',
    'InsufficientPOIError',
    'APIRateLimitError',
    'NetworkError',
    'FileNotFoundError',
    'ParseError',
    'get_pipeline',
]
