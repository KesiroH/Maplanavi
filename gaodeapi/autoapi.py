"""
高德地图 Web 服务 API Python SDK
=================================

本 SDK 封装了高德地图 Web 服务 API 的常用接口，包括：
- 地理编码 / 逆地理编码 / 批量逆地理编码
- 路径规划（驾车、步行、骑行、公交）
- POI 搜索（关键字、周边、多边形、ID查询）
- 距离测量
- 行政区划查询

官方文档参考:
- 地理/逆地理编码: https://lbs.amap.com/api/webservice/guide/api/georegeo
- 路径规划: https://lbs.amap.com/api/webservice/guide/api/direction
- POI 搜索: https://lbs.amap.com/api/webservice/guide/api-advanced/search
- 新版POI搜索: https://lbs.amap.com/api/webservice/guide/api-advanced/newpoisearch
- 距离测量: https://lbs.amap.com/api/webservice/guide/api/distance
- 行政区划: https://lbs.amap.com/api/webservice/guide/api/district

使用前请确保:
1. 在高德开放平台 (https://lbs.amap.com/) 申请 Web 服务 Key。
2. 设置环境变量 AMAP_API_KEY 或在代码中传入配置。
3. 安装依赖: `pip install requests pydantic tenacity`
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

from .models import (
    AmapConfig,
    AmapDistance,
    AmapDistrict,
    AmapLocation,
    AmapPOI,
    AmapRoute,
    CoordinateSystem,
)
from .coordinate_utils import (
    convert_coordinate,
    detect_coordinate_system,
    ensure_gcj02,
    ensure_wgs84,
    gcj02_to_wgs84,
    wgs84_to_gcj02,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('GaodeMapClient')


class DistanceType(Enum):
    """距离测量类型"""
    DRIVING = 1
    STRAIGHT = 0
    WALKING = 3


class GaodeMapError(Exception):
    """高德地图 API 错误基类"""
    def __init__(self, message: str, info_code: Optional[str] = None, response: Optional[Dict] = None):
        self.message = message
        self.info_code = info_code
        self.response = response
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.info_code:
            return f"{self.message} (code: {self.info_code})"
        return self.message


class GaodeMapConnectionError(GaodeMapError):
    """网络连接错误"""
    pass


class GaodeMapAPIError(GaodeMapError):
    """API 返回错误"""
    pass


class GaodeMapTimeoutError(GaodeMapError):
    """请求超时错误"""
    pass


class GaodeMapConfigError(GaodeMapError):
    """配置错误"""
    pass


class GaodeMapCoordinateError(GaodeMapError):
    """坐标系错误"""
    pass


@dataclass
class APIResponse:
    """API 响应数据模型"""
    status: str
    info: str
    info_code: str
    data: Dict[str, Any]
    
    @property
    def is_success(self) -> bool:
        return self.status == "1"


class GaodeMapClient:
    """高德地图 Web 服务 API 客户端"""

    BASE_URL = "https://restapi.amap.com"

    ERROR_CODES = {
        "10000": "OK",
        "10001": "key不正确或过期",
        "10002": "服务维护中",
        "10003": "服务不可用",
        "10004": "访问已超出日访问量",
        "10005": "用户访问过于频繁",
        "10006": "用户IP无效",
        "10007": "用户域名无效",
        "10008": "用户签名无效",
        "10009": "用户请求非法",
        "10010": "用户无权限",
        "10011": "用户无该接口权限",
        "10012": "服务不存在",
        "10013": "服务不可用",
        "10014": "服务已下线",
        "10015": "服务正在上线",
        "10016": "服务正在下线",
        "10017": "服务正在维护",
        "10018": "服务正在升级",
        "10019": "服务正在迁移",
        "10020": "服务正在重启",
        "20000": "请求参数非法",
        "20001": "缺少必填参数",
        "20002": "请求协议非法",
        "20003": "请求方法非法",
        "20004": "请求内容非法",
        "20005": "请求长度非法",
        "20006": "请求格式非法",
        "20007": "请求编码非法",
        "20008": "请求签名非法",
        "20009": "请求时间非法",
        "20010": "请求来源非法",
        "20011": "请求目标非法",
        "20012": "请求路径非法",
        "20013": "请求头部非法",
        "20014": "请求体非法",
        "20015": "请求参数非法",
        "20016": "请求参数缺失",
        "20017": "请求参数类型非法",
        "20018": "请求参数值非法",
        "20019": "请求参数长度非法",
        "20020": "请求参数格式非法",
        "20021": "请求参数编码非法",
        "20022": "请求参数签名非法",
        "20023": "请求参数时间非法",
        "20024": "请求参数来源非法",
        "20025": "请求参数目标非法",
        "20026": "请求参数路径非法",
        "20027": "请求参数头部非法",
        "20028": "请求参数体非法",
        "30000": "服务端错误",
        "30001": "服务端内部错误",
        "30002": "服务端服务错误",
        "30003": "服务端服务不可用",
        "30004": "服务端服务超时",
        "30005": "服务端服务过载",
        "30006": "服务端服务限流",
        "30007": "服务端服务降级",
        "30008": "服务端服务熔断",
        "30009": "服务端服务隔离",
        "30010": "服务端服务不可用",
    }

    RETRYABLE_ERRORS = {
        "10002", "10003", "10004", "10005",
        "30001", "30002", "30003", "30004", "30005", "30006", "30007", "30008", "30009", "30010"
    }

    def __init__(
        self,
        api_key: Optional[str] = "a1fd193c9a05059c48dea35bd2f8a287",
        config: Optional[AmapConfig] = None,
        timeout: int = 10,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        初始化客户端

        优先级: config > api_key参数 > 环境变量

        Args:
            api_key (str, optional): 高德地图 Web 服务 API Key
            config (AmapConfig, optional): 配置对象，优先级最高
            timeout (int): 请求超时时间（秒），默认10秒
            max_retries (int): 最大重试次数，默认3次
            retry_delay (float): 重试间隔（秒），默认1秒

        Raises:
            GaodeMapConfigError: 未提供有效的 API Key
        """
        if config is not None:
            self._config = config
        elif api_key is not None:
            self._config = AmapConfig(
                api_key=api_key,
                timeout=timeout,
                max_retries=max_retries,
                retry_delay=retry_delay,
            )
        else:
            try:
                self._config = AmapConfig.from_env(
                    timeout=timeout,
                    max_retries=max_retries,
                    retry_delay=retry_delay,
                )
            except ValueError as e:
                raise GaodeMapConfigError(
                    f"未提供有效的 API Key。请设置环境变量 AMAP_API_KEY 或传入 api_key 参数。错误: {e}"
                )

        self.api_key = self._config.api_key
        self.timeout = self._config.timeout
        self.max_retries = self._config.max_retries
        self.retry_delay = self._config.retry_delay

        self._request_count = 0
        self._last_request_time: Optional[float] = None

        logger.info(
            "GaodeMapClient initialized: timeout=%ds, max_retries=%d, retry_delay=%.1fs",
            self.timeout, self.max_retries, self.retry_delay
        )

    @property
    def config(self) -> AmapConfig:
        """获取当前配置"""
        return self._config

    @property
    def request_stats(self) -> Dict[str, Any]:
        """获取请求统计信息"""
        return {
            "total_requests": self._request_count,
            "last_request_time": self._last_request_time,
        }

    def _exponential_backoff(self, attempt: int) -> float:
        """计算指数退避时间"""
        return min(self.retry_delay * (2 ** attempt), 60.0)

    def _make_request(
        self,
        endpoint: str,
        params: Dict[str, Any],
        method: str = "GET"
    ) -> Dict[str, Any]:
        """
        发送 HTTP 请求到高德 API（带指数退避重试）

        Args:
            endpoint (str): API 端点，例如 "/v3/geocode/geo"
            params (dict): 请求参数
            method (str): 请求方法，GET 或 POST

        Returns:
            dict: API 返回的 JSON 数据

        Raises:
            GaodeMapConnectionError: 网络连接错误
            GaodeMapTimeoutError: 请求超时
            GaodeMapAPIError: API 返回错误
        """
        all_params = {
            "key": self.api_key,
            **params
        }

        url = f"{self.BASE_URL}{endpoint}"
        
        logger.debug("Request URL: %s", url)
        logger.debug("Request params: %s", {k: v for k, v in all_params.items() if k != 'key'})

        last_exception = None
        for attempt in range(self.max_retries):
            try:
                self._request_count += 1
                self._last_request_time = time.time()

                if method.upper() == "GET":
                    response = requests.get(url, params=all_params, timeout=self.timeout)
                else:
                    response = requests.post(url, data=all_params, timeout=self.timeout)
                
                response.raise_for_status()
                
                data = response.json()
                status = data.get("status")
                info_code = data.get("infocode", "unknown")
                info = data.get("info", "未知错误")
                
                logger.debug("Response status: %s, info_code: %s", status, info_code)
                
                if status != "1":
                    error_msg = self.ERROR_CODES.get(info_code, info)
                    logger.error("API error: %s (infocode: %s)", error_msg, info_code)

                    if info_code in self.RETRYABLE_ERRORS and attempt < self.max_retries - 1:
                        backoff_time = self._exponential_backoff(attempt)
                        logger.warning(
                            "Retryable error, retrying in %.1fs (attempt %d/%d)",
                            backoff_time, attempt + 1, self.max_retries
                        )
                        time.sleep(backoff_time)
                        continue

                    raise GaodeMapAPIError(
                        message=f"高德 API 调用失败: {error_msg}",
                        info_code=info_code,
                        response=data
                    )
                
                logger.info("API call successful: %s", endpoint)
                return data
                
            except requests.exceptions.Timeout as e:
                last_exception = GaodeMapTimeoutError(
                    message=f"请求超时: {str(e)}",
                    response=None
                )
                logger.warning("Request timeout, attempt %d/%d", attempt + 1, self.max_retries)
                
            except requests.exceptions.ConnectionError as e:
                last_exception = GaodeMapConnectionError(
                    message=f"网络连接错误: {str(e)}",
                    response=None
                )
                logger.warning("Connection error, attempt %d/%d", attempt + 1, self.max_retries)
                
            except requests.exceptions.RequestException as e:
                last_exception = GaodeMapConnectionError(
                    message=f"请求错误: {str(e)}",
                    response=None
                )
                logger.warning("Request error, attempt %d/%d", attempt + 1, self.max_retries)
            
            if attempt < self.max_retries - 1:
                backoff_time = self._exponential_backoff(attempt)
                logger.info("Retrying in %.1fs...", backoff_time)
                time.sleep(backoff_time)
        
        logger.error("All retry attempts failed for %s", endpoint)
        raise last_exception

    def _parse_response(self, data: Dict[str, Any]) -> APIResponse:
        """解析 API 响应"""
        return APIResponse(
            status=data.get("status", "0"),
            info=data.get("info", ""),
            info_code=data.get("infocode", ""),
            data=data
        )

    def _parse_coordinate(self, location: str) -> Tuple[float, float]:
        """解析坐标字符串 '经度,纬度'"""
        parts = location.split(",")
        if len(parts) != 2:
            raise GaodeMapCoordinateError(f"无效的坐标格式: {location}")
        return float(parts[0]), float(parts[1])

    def _validate_and_convert_coordinate(
        self,
        lng: float,
        lat: float,
        source_sys: Optional[CoordinateSystem] = None,
        target_sys: CoordinateSystem = CoordinateSystem.GCJ02
    ) -> Tuple[float, float]:
        """
        验证并转换坐标系

        Args:
            lng: 经度
            lat: 纬度
            source_sys: 源坐标系（可选，自动检测）
            target_sys: 目标坐标系（默认 GCJ-02，高德使用）

        Returns:
            Tuple[float, float]: 转换后的坐标
        """
        if not (-180 <= lng <= 180):
            raise GaodeMapCoordinateError(f"经度超出有效范围: {lng}")
        if not (-90 <= lat <= 90):
            raise GaodeMapCoordinateError(f"纬度超出有效范围: {lat}")

        if source_sys is None:
            source_sys = detect_coordinate_system(lat, lng)

        if source_sys == target_sys:
            return lng, lat

        return convert_coordinate(lng, lat, source_sys, target_sys)

    def audit_coordinate(
        self,
        lng: float,
        lat: float,
        expected_sys: CoordinateSystem = CoordinateSystem.GCJ02
    ) -> Dict[str, Any]:
        """
        审查坐标信息

        Args:
            lng: 经度
            lat: 纬度
            expected_sys: 期望的坐标系

        Returns:
            dict: 包含坐标系检测结果和转换建议
        """
        detected_sys = detect_coordinate_system(lat, lng)
        needs_conversion = detected_sys != expected_sys

        result = {
            "input": {"longitude": lng, "latitude": lat},
            "detected_system": detected_sys.value,
            "expected_system": expected_sys.value,
            "needs_conversion": needs_conversion,
        }

        if needs_conversion:
            converted_lng, converted_lat = convert_coordinate(lng, lat, detected_sys, expected_sys)
            result["converted"] = {"longitude": converted_lng, "latitude": converted_lat}

        return result

    def geocode(
        self,
        address: str,
        city: Optional[str] = None,
        return_model: bool = True
    ) -> Union[Dict[str, Any], List[AmapLocation]]:
        """
        地理编码: 将地址转换为经纬度坐标

        文档: https://lbs.amap.com/api/webservice/guide/api/georegeo#1

        Args:
            address (str): 结构化地址或关键词
            city (str, optional): 指定查询的城市
            return_model (bool): 是否返回 Pydantic 模型，默认 True

        Returns:
            如果 return_model=True: List[AmapLocation]
            如果 return_model=False: dict
        """
        logger.info("Geocoding address: %s, city: %s", address, city)
        params = {"address": address}
        if city:
            params["city"] = city

        data = self._make_request("/v3/geocode/geo", params)

        if return_model:
            geocodes = data.get("geocodes", [])
            return [AmapLocation.from_amap_geocode(gc) for gc in geocodes]
        return data

    def reverse_geocode(
        self,
        location: str,
        radius: Optional[int] = None,
        extensions: str = "base",
        return_model: bool = True
    ) -> Union[Dict[str, Any], AmapLocation]:
        """
        逆地理编码: 将经纬度坐标转换为地址描述

        文档: https://lbs.amap.com/api/webservice/guide/api/georegeo#2

        Args:
            location (str): 经纬度坐标，格式 "经度,纬度"
            radius (int, optional): 查询半径（米）
            extensions (str): 返回结果控制。"base" 或 "all"
            return_model (bool): 是否返回 Pydantic 模型，默认 True

        Returns:
            如果 return_model=True: AmapLocation
            如果 return_model=False: dict
        """
        logger.info("Reverse geocoding location: %s, extensions: %s", location, extensions)
        params = {
            "location": location,
            "extensions": extensions
        }
        if radius is not None:
            params["radius"] = str(radius)

        data = self._make_request("/v3/geocode/regeo", params)

        if return_model:
            regeocode = data.get("regeocode", {})
            location_obj = AmapLocation.from_amap_regeocode(regeocode)
            lng, lat = self._parse_coordinate(location)
            location_obj.longitude = lng
            location_obj.latitude = lat
            return location_obj
        return data

    def batch_reverse_geocode(
        self,
        locations: List[str],
        extensions: str = "base",
        return_model: bool = True
    ) -> Union[Dict[str, Any], List[AmapLocation]]:
        """
        批量逆地理编码

        Args:
            locations (list): 经纬度坐标列表
            extensions (str): 返回结果控制
            return_model (bool): 是否返回 Pydantic 模型，默认 True

        Returns:
            如果 return_model=True: List[AmapLocation]
            如果 return_model=False: dict
        """
        logger.info("Batch reverse geocoding %d locations", len(locations))
        params = {
            "location": "|".join(locations),
            "extensions": extensions,
            "batch": "true"
        }
        data = self._make_request("/v3/geocode/regeo", params)

        if return_model:
            regeocodes = data.get("regeocodes", [])
            results = []
            for i, regeo in enumerate(regeocodes):
                loc = AmapLocation.from_amap_regeocode(regeo)
                if i < len(locations):
                    lng, lat = self._parse_coordinate(locations[i])
                    loc.longitude = lng
                    loc.latitude = lat
                results.append(loc)
            return results
        return data

    def driving_direction(
        self,
        origin: str,
        destination: str,
        strategy: int = 10,
        waypoints: Optional[str] = None,
        avoidpolygons: Optional[str] = None,
        avoidroad: Optional[str] = None,
        return_model: bool = True
    ) -> Union[Dict[str, Any], AmapRoute]:
        """
        驾车路径规划

        Args:
            origin (str): 起点经纬度，格式 "经度,纬度"
            destination (str): 终点经纬度
            strategy (int): 路径计算策略，默认10
            waypoints (str, optional): 途经点
            avoidpolygons (str, optional): 避让区域
            avoidroad (str, optional): 避让道路
            return_model (bool): 是否返回 Pydantic 模型，默认 True

        Returns:
            如果 return_model=True: AmapRoute
            如果 return_model=False: dict
        """
        logger.info("Driving direction: %s -> %s, strategy: %d", origin, destination, strategy)
        params = {
            "origin": origin,
            "destination": destination,
            "strategy": str(strategy)
        }
        if waypoints:
            params["waypoints"] = waypoints
        if avoidpolygons:
            params["avoidpolygons"] = avoidpolygons
        if avoidroad:
            params["avoidroad"] = avoidroad

        data = self._make_request("/v3/direction/driving", params)

        if return_model:
            path = data.get("route", {}).get("paths", [{}])[0]
            return AmapRoute.from_amap_driving(path)
        return data

    def walking_direction(
        self,
        origin: str,
        destination: str,
        return_model: bool = True
    ) -> Union[Dict[str, Any], AmapRoute]:
        """
        步行路径规划

        Args:
            origin (str): 起点经纬度
            destination (str): 终点经纬度
            return_model (bool): 是否返回 Pydantic 模型，默认 True

        Returns:
            如果 return_model=True: AmapRoute
            如果 return_model=False: dict
        """
        logger.info("Walking direction: %s -> %s", origin, destination)
        params = {
            "origin": origin,
            "destination": destination
        }
        data = self._make_request("/v3/direction/walking", params)

        if return_model:
            path = data.get("route", {}).get("paths", [{}])[0]
            return AmapRoute.from_amap_walking(path)
        return data

    def bicycling_direction(
        self,
        origin: str,
        destination: str,
        return_model: bool = True
    ) -> Union[Dict[str, Any], AmapRoute]:
        """
        骑行路径规划

        Args:
            origin (str): 起点经纬度
            destination (str): 终点经纬度
            return_model (bool): 是否返回 Pydantic 模型，默认 True

        Returns:
            如果 return_model=True: AmapRoute
            如果 return_model=False: dict
        """
        logger.info("Bicycling direction: %s -> %s", origin, destination)
        params = {
            "origin": origin,
            "destination": destination
        }
        data = self._make_request("/v4/direction/bicycling", params)

        if return_model:
            path = data.get("data", {}).get("paths", [{}])[0]
            return AmapRoute.from_amap_driving(path)
        return data

    def transit_direction(
        self,
        origin: str,
        destination: str,
        city: str,
        cityd: Optional[str] = None,
        strategy: int = 0,
        nightflag: int = 0
    ) -> Dict[str, Any]:
        """
        公交（公交+地铁）路径规划

        Args:
            origin (str): 起点经纬度
            destination (str): 终点经纬度
            city (str): 起点所在城市
            cityd (str, optional): 终点所在城市
            strategy (int): 换乘策略
            nightflag (int): 是否计算夜班车

        Returns:
            dict: 公交路线详情
        """
        logger.info("Transit direction: %s -> %s, city: %s", origin, destination, city)
        params = {
            "origin": origin,
            "destination": destination,
            "city": city,
            "strategy": str(strategy),
            "nightflag": str(nightflag)
        }
        if cityd:
            params["cityd"] = cityd
        return self._make_request("/v3/direction/transit/integrated", params)

    def poi_search_by_keyword(
        self,
        keywords: str,
        types: Optional[str] = None,
        city: Optional[str] = None,
        citylimit: bool = False,
        page: int = 1,
        offset: int = 20,
        extensions: str = "base",
        return_model: bool = True
    ) -> Union[Dict[str, Any], List[AmapPOI]]:
        """
        关键字搜索 POI

        Args:
            keywords (str): 查询关键字
            types (str, optional): POI 类型
            city (str, optional): 查询城市
            citylimit (bool): 是否限制城市范围内
            page (int): 页码
            offset (int): 每页记录数
            extensions (str): 返回数据扩展
            return_model (bool): 是否返回 Pydantic 模型，默认 True

        Returns:
            如果 return_model=True: List[AmapPOI]
            如果 return_model=False: dict
        """
        logger.info("POI keyword search: keywords=%s, city=%s, types=%s", keywords, city, types)
        params = {
            "keywords": keywords,
            "page": str(page),
            "offset": str(offset),
            "extensions": extensions
        }
        if types:
            params["types"] = types
        if city:
            params["city"] = city
            params["citylimit"] = "true" if citylimit else "false"

        data = self._make_request("/v5/place/text", params)

        if return_model:
            pois = data.get("pois", [])
            return [AmapPOI.from_amap_poi(poi) for poi in pois]
        return data

    def poi_search_around(
        self,
        center: str,
        radius: int = 3000,
        keywords: Optional[str] = None,
        types: Optional[str] = None,
        page: int = 1,
        offset: int = 20,
        extensions: str = "base",
        return_model: bool = True
    ) -> Union[Dict[str, Any], List[AmapPOI]]:
        """
        周边搜索 POI

        Args:
            center (str): 中心点经纬度
            radius (int): 查询半径（米）
            keywords (str, optional): 查询关键字
            types (str, optional): POI 类型
            page (int): 页码
            offset (int): 每页记录数
            extensions (str): 返回数据扩展
            return_model (bool): 是否返回 Pydantic 模型，默认 True

        Returns:
            如果 return_model=True: List[AmapPOI]
            如果 return_model=False: dict
        """
        logger.info("POI around search: center=%s, radius=%dm, keywords=%s", center, radius, keywords)
        params = {
            "center": center,
            "radius": str(radius),
            "page": str(page),
            "offset": str(offset),
            "extensions": extensions
        }
        if keywords:
            params["keywords"] = keywords
        if types:
            params["types"] = types

        data = self._make_request("/v5/place/around", params)

        if return_model:
            pois = data.get("pois", [])
            return [AmapPOI.from_amap_poi(poi) for poi in pois]
        return data

    def poi_search_by_polygon(
        self,
        polygon: str,
        keywords: Optional[str] = None,
        types: Optional[str] = None,
        page: int = 1,
        offset: int = 20,
        extensions: str = "base",
        return_model: bool = True
    ) -> Union[Dict[str, Any], List[AmapPOI]]:
        """
        多边形搜索 POI

        Args:
            polygon (str): 多边形区域坐标
            keywords (str, optional): 查询关键字
            types (str, optional): POI 类型
            page (int): 页码
            offset (int): 每页记录数
            extensions (str): 返回数据扩展
            return_model (bool): 是否返回 Pydantic 模型，默认 True

        Returns:
            如果 return_model=True: List[AmapPOI]
            如果 return_model=False: dict
        """
        logger.info("POI polygon search: polygon=%s, keywords=%s", polygon[:50] + "...", keywords)
        params = {
            "polygon": polygon,
            "page": str(page),
            "offset": str(offset),
            "extensions": extensions
        }
        if keywords:
            params["keywords"] = keywords
        if types:
            params["types"] = types

        data = self._make_request("/v5/place/polygon", params)

        if return_model:
            pois = data.get("pois", [])
            return [AmapPOI.from_amap_poi(poi) for poi in pois]
        return data

    def poi_search_by_id(
        self,
        ids: Union[str, List[str]],
        return_model: bool = True
    ) -> Union[Dict[str, Any], List[AmapPOI]]:
        """
        ID 查询 POI

        Args:
            ids (str or list): POI ID 或 ID 列表
            return_model (bool): 是否返回 Pydantic 模型，默认 True

        Returns:
            如果 return_model=True: List[AmapPOI]
            如果 return_model=False: dict
        """
        if isinstance(ids, list):
            ids = ",".join(ids)
        logger.info("POI ID search: ids=%s", ids)
        params = {"id": ids}
        data = self._make_request("/v5/place/detail", params)

        if return_model:
            pois = data.get("pois", [])
            return [AmapPOI.from_amap_poi(poi) for poi in pois]
        return data

    def distance(
        self,
        origins: Union[str, List[str]],
        destination: str,
        distance_type: Union[int, DistanceType] = DistanceType.STRAIGHT,
        return_model: bool = True
    ) -> Union[Dict[str, Any], List[AmapDistance]]:
        """
        距离测量

        Args:
            origins (str or list): 起点经纬度
            destination (str): 终点经纬度
            distance_type (int or DistanceType): 距离测量类型
            return_model (bool): 是否返回 Pydantic 模型，默认 True

        Returns:
            如果 return_model=True: List[AmapDistance]
            如果 return_model=False: dict
        """
        if isinstance(origins, list):
            origins = "|".join(origins)
        
        if isinstance(distance_type, DistanceType):
            distance_type = distance_type.value
            
        logger.info("Distance measurement: origins=%s, destination=%s, type=%d", 
                   origins[:50] + "..." if len(origins) > 50 else origins, 
                   destination, distance_type)
        
        params = {
            "origins": origins,
            "destination": destination,
            "type": str(distance_type)
        }
        data = self._make_request("/v3/distance", params)

        if return_model:
            results = data.get("results", [])
            origin_list = origins.split("|")
            distances = []
            for i, result in enumerate(results):
                origin = origin_list[i] if i < len(origin_list) else ""
                distances.append(AmapDistance.from_amap_distance(result, origin, destination))
            return distances
        return data

    def district_query(
        self,
        keywords: Optional[str] = None,
        subdistrict: int = 1,
        extensions: str = "base",
        return_model: bool = True
    ) -> Union[Dict[str, Any], AmapDistrict]:
        """
        行政区划查询

        Args:
            keywords (str, optional): 查询关键字
            subdistrict (int): 子级行政区级别
            extensions (str): 返回数据扩展
            return_model (bool): 是否返回 Pydantic 模型，默认 True

        Returns:
            如果 return_model=True: AmapDistrict
            如果 return_model=False: dict
        """
        logger.info("District query: keywords=%s, subdistrict=%d", keywords, subdistrict)
        params = {
            "subdistrict": str(subdistrict),
            "extensions": extensions
        }
        if keywords:
            params["keywords"] = keywords
        data = self._make_request("/v3/config/district", params)

        if return_model:
            districts = data.get("districts", [])
            if districts:
                return AmapDistrict.from_amap_district(districts[0])
            return AmapDistrict(adcode="", name="")
        return data

    def ip_location(self, ip: Optional[str] = None) -> Dict[str, Any]:
        """
        IP 定位

        Args:
            ip (str, optional): IP 地址

        Returns:
            dict: IP 定位结果
        """
        logger.info("IP location query: ip=%s", ip or "auto")
        params = {}
        if ip:
            params["ip"] = ip
        return self._make_request("/v3/ip", params)

    def weather(self, city: str, extensions: str = "base") -> Dict[str, Any]:
        """
        天气查询

        Args:
            city (str): 城市名称或 adcode
            extensions (str): 返回数据扩展

        Returns:
            dict: 天气信息
        """
        logger.info("Weather query: city=%s, extensions=%s", city, extensions)
        params = {
            "city": city,
            "extensions": extensions
        }
        return self._make_request("/v3/weather/weatherInfo", params)

    def input_tips(
        self,
        keywords: str,
        city: Optional[str] = None,
        citylimit: bool = False,
        datatype: str = "all"
    ) -> Dict[str, Any]:
        """
        输入提示（自动补全）

        Args:
            keywords (str): 查询关键字
            city (str, optional): 查询城市
            citylimit (bool): 是否限制城市范围内
            datatype (str): 数据类型

        Returns:
            dict: 输入提示结果
        """
        logger.info("Input tips: keywords=%s, city=%s", keywords, city)
        params = {
            "keywords": keywords,
            "datatype": datatype
        }
        if city:
            params["city"] = city
            params["citylimit"] = "true" if citylimit else "false"
        return self._make_request("/v3/assistant/inputtips", params)


if __name__ == "__main__":
    print("=" * 60)
    print("高德地图 API SDK 使用示例")
    print("=" * 60)
    print()
    print("请设置环境变量 AMAP_API_KEY 或在代码中传入 api_key 参数:")
    print()
    print("方式一: 环境变量")
    print("  export AMAP_API_KEY='your_api_key_here'  # Linux/Mac")
    print("  set AMAP_API_KEY=your_api_key_here       # Windows")
    print()
    print("方式二: 代码传入")
    print("  from gaodeapi import GaodeMapClient")
    print("  client = GaodeMapClient(api_key='your_api_key_here')")
    print()
    print("方式三: 使用配置对象")
    print("  from gaodeapi.models import AmapConfig")
    print("  from gaodeapi import GaodeMapClient")
    print("  config = AmapConfig(api_key='your_api_key_here', timeout=30)")
    print("  client = GaodeMapClient(config=config)")
    print()
    print("=" * 60)
