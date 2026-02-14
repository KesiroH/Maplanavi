"""
高德地图 Web 服务 API Python SDK
=================================

提供安全、健壮的高德地图 API 服务封装。
"""

from .models import (
    AmapConfig,
    AmapLocation,
    AmapRoute,
    AmapRouteStep,
    AmapPOI,
    AmapDistance,
    AmapDistrict,
    CoordinateSystem,
)
from .coordinate_utils import (
    detect_coordinate_system,
    gcj02_to_wgs84,
    wgs84_to_gcj02,
    bd09_to_gcj02,
    gcj02_to_bd09,
    wgs84_to_bd09,
    bd09_to_wgs84,
    convert_coordinate,
    ensure_gcj02,
    ensure_wgs84,
)
from .autoapi import (
    GaodeMapClient,
    GaodeMapError,
    GaodeMapAPIError,
    GaodeMapConnectionError,
    GaodeMapTimeoutError,
    GaodeMapConfigError,
    GaodeMapCoordinateError,
    DistanceType,
    APIResponse,
)

__all__ = [
    "AmapConfig",
    "AmapLocation",
    "AmapRoute",
    "AmapRouteStep",
    "AmapPOI",
    "AmapDistance",
    "AmapDistrict",
    "CoordinateSystem",
    "GaodeMapClient",
    "GaodeMapError",
    "GaodeMapAPIError",
    "GaodeMapConnectionError",
    "GaodeMapTimeoutError",
    "GaodeMapConfigError",
    "GaodeMapCoordinateError",
    "DistanceType",
    "APIResponse",
    "detect_coordinate_system",
    "gcj02_to_wgs84",
    "wgs84_to_gcj02",
    "bd09_to_gcj02",
    "gcj02_to_bd09",
    "wgs84_to_bd09",
    "bd09_to_wgs84",
    "convert_coordinate",
    "ensure_gcj02",
    "ensure_wgs84",
]

__version__ = "2.0.0"
