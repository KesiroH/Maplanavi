"""
异常体系定义
============

统一的业务异常层次结构。

包含:
- MaplanaviBaseException: 基础异常
- LLMServiceError: LLM服务异常
- MapServiceError: 地图服务异常
- DataValidationError: 数据验证异常
- InsufficientPOIError: POI不足异常
"""

from __future__ import annotations


class MaplanaviBaseException(Exception):
    """Maplanavi 基础异常类"""
    
    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self) -> str:
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


class ConfigurationError(MaplanaviBaseException):
    """配置错误"""
    pass


class LLMServiceError(MaplanaviBaseException):
    """LLM 服务异常"""
    
    def __init__(self, message: str, model: str | None = None, 
                 status_code: int | None = None, details: dict | None = None):
        self.model = model
        self.status_code = status_code
        super().__init__(message, details)


class MapServiceError(MaplanaviBaseException):
    """地图服务异常"""
    
    def __init__(self, message: str, api_name: str | None = None,
                 error_code: str | None = None, details: dict | None = None):
        self.api_name = api_name
        self.error_code = error_code
        super().__init__(message, details)


class DataValidationError(MaplanaviBaseException):
    """数据验证异常"""
    
    def __init__(self, message: str, field: str | None = None,
                 value: any = None, details: dict | None = None):
        self.field = field
        self.value = value
        super().__init__(message, details)


class InsufficientPOIError(MaplanaviBaseException):
    """POI数量不足异常"""
    
    def __init__(self, message: str, required: int | None = None,
                 available: int | None = None, details: dict | None = None):
        self.required = required
        self.available = available
        super().__init__(message, details)
    
    @classmethod
    def from_poi_count(cls, available: int, required: int = 3) -> "InsufficientPOIError":
        """从POI数量创建异常"""
        return cls(
            message=f"POI数量不足: 需要至少 {required} 个POI，当前只有 {available} 个",
            required=required,
            available=available,
            details={"required": required, "available": available}
        )


class APIRateLimitError(MaplanaviBaseException):
    """API频率限制异常"""
    pass


class NetworkError(MaplanaviBaseException):
    """网络请求异常"""
    
    def __init__(self, message: str, url: str | None = None,
                 status_code: int | None = None, details: dict | None = None):
        self.url = url
        self.status_code = status_code
        super().__init__(message, details)


class FileNotFoundError(MaplanaviBaseException):
    """文件未找到异常"""
    pass


class ParseError(MaplanaviBaseException):
    """解析异常"""
    pass
