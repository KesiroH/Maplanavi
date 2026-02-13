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
2. 安装 requests 库: `pip install requests`
"""

import requests
import json
import logging
import time
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass
from enum import Enum


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


class GaodeMapConnectionError(GaodeMapError):
    """网络连接错误"""
    pass


class GaodeMapAPIError(GaodeMapError):
    """API 返回错误"""
    pass


class GaodeMapTimeoutError(GaodeMapError):
    """请求超时错误"""
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

    def __init__(self, api_key: str, timeout: int = 10, max_retries: int = 3, retry_delay: float = 1.0):
        """
        初始化客户端

        Args:
            api_key (str): 高德地图 Web 服务 API Key
            timeout (int): 请求超时时间（秒），默认10秒
            max_retries (int): 最大重试次数，默认3次
            retry_delay (float): 重试间隔（秒），默认1秒
        """
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        logger.info("GaodeMapClient initialized with timeout=%ds, max_retries=%d", timeout, max_retries)

    def _make_request(self, endpoint: str, params: Dict[str, Any], method: str = "GET") -> Dict[str, Any]:
        """
        发送 HTTP 请求到高德 API

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
                time.sleep(self.retry_delay)
        
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

    # ======================
    # 地理/逆地理编码
    # ======================

    def geocode(self, address: str, city: Optional[str] = None) -> Dict[str, Any]:
        """
        地理编码: 将地址转换为经纬度坐标

        文档: https://lbs.amap.com/api/webservice/guide/api/georegeo#1

        Args:
            address (str): 结构化地址或关键词，例如 "北京市朝阳区阜通东大街6号"
            city (str, optional): 指定查询的城市。可选，但能提高准确性。

        Returns:
            dict: 包含地理编码结果的字典
                {
                    "geocodes": [
                        {
                            "location": "116.481499,39.990475",
                            "province": "北京市",
                            "city": "北京市",
                            "citycode": "010",
                            "district": "朝阳区",
                            "adcode": "110105",
                            ...
                        }
                    ]
                }
        """
        logger.info("Geocoding address: %s, city: %s", address, city)
        params = {"address": address}
        if city:
            params["city"] = city

        return self._make_request("/v3/geocode/geo", params)

    def reverse_geocode(self, location: str, radius: Optional[int] = None, 
                       extensions: str = "base") -> Dict[str, Any]:
        """
        逆地理编码: 将经纬度坐标转换为地址描述

        文档: https://lbs.amap.com/api/webservice/guide/api/georegeo#2

        Args:
            location (str): 经纬度坐标，格式 "经度,纬度"，例如 "116.481499,39.990475"
            radius (int, optional): 查询半径（米），默认1000米。
            extensions (str): 返回结果控制。"base"（基本地址信息）或 "all"（包含附近POI列表）。

        Returns:
            dict: 包含逆地理编码结果的字典
                {
                    "regeocode": {
                        "formatted_address": "北京市朝阳区望京街与阜通东大街交叉口",
                        "addressComponent": {...},
                        "pois": [...] # 仅当 extensions="all" 时存在
                    }
                }
        """
        logger.info("Reverse geocoding location: %s, extensions: %s", location, extensions)
        params = {
            "location": location,
            "extensions": extensions
        }
        if radius is not None:
            params["radius"] = str(radius)

        return self._make_request("/v3/geocode/regeo", params)

    def batch_reverse_geocode(self, locations: List[str], 
                              extensions: str = "base") -> Dict[str, Any]:
        """
        批量逆地理编码: 将多个经纬度坐标转换为地址描述

        文档: https://lbs.amap.com/api/webservice/guide/api/georegeo#3

        Args:
            locations (list): 经纬度坐标列表，每个坐标格式为 "经度,纬度"
            extensions (str): 返回结果控制。"base" 或 "all"

        Returns:
            dict: 包含批量逆地理编码结果的字典
        """
        logger.info("Batch reverse geocoding %d locations", len(locations))
        params = {
            "location": "|".join(locations),
            "extensions": extensions,
            "batch": "true"
        }
        return self._make_request("/v3/geocode/regeo", params)

    # ======================
    # 路径规划
    # ======================

    def driving_direction(self, origin: str, destination: str, 
                         strategy: int = 10, waypoints: Optional[str] = None,
                         avoidpolygons: Optional[str] = None, avoidroad: Optional[str] = None) -> Dict[str, Any]:
        """
        驾车路径规划

        文档: https://lbs.amap.com/api/webservice/guide/api/direction#1

        Args:
            origin (str): 起点经纬度，格式 "经度,纬度"
            destination (str): 终点经纬度，格式 "经度,纬度"
            strategy (int): 路径计算策略。默认10（速度优先，躲避拥堵）。
                0: 速度优先（时间）
                1: 费用优先（不走收费路段的最快道路）
                2: 距离优先（最短）
                10: 速度优先（推荐）
                11: 躲避拥堵
                12: 躲避拥堵且速度优先
            waypoints (str, optional): 途经点经纬度，多个用 "|" 分隔
            avoidpolygons (str, optional): 避让区域
            avoidroad (str, optional): 避让道路名称

        Returns:
            dict: 包含驾车路线详情的字典
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
        return self._make_request("/v3/direction/driving", params)

    def walking_direction(self, origin: str, destination: str) -> Dict[str, Any]:
        """
        步行路径规划

        文档: https://lbs.amap.com/api/webservice/guide/api/direction#2

        Args:
            origin (str): 起点经纬度，格式 "经度,纬度"
            destination (str): 终点经纬度，格式 "经度,纬度"

        Returns:
            dict: 包含步行路线详情的字典
        """
        logger.info("Walking direction: %s -> %s", origin, destination)
        params = {
            "origin": origin,
            "destination": destination
        }
        return self._make_request("/v3/direction/walking", params)

    def bicycling_direction(self, origin: str, destination: str) -> Dict[str, Any]:
        """
        骑行路径规划

        文档: https://lbs.amap.com/api/webservice/guide/api/direction#3

        Args:
            origin (str): 起点经纬度，格式 "经度,纬度"
            destination (str): 终点经纬度，格式 "经度,纬度"

        Returns:
            dict: 包含骑行路线详情的字典
        """
        logger.info("Bicycling direction: %s -> %s", origin, destination)
        params = {
            "origin": origin,
            "destination": destination
        }
        return self._make_request("/v4/direction/bicycling", params)

    def transit_direction(self, origin: str, destination: str, 
                         city: str, cityd: Optional[str] = None,
                         strategy: int = 0, nightflag: int = 0) -> Dict[str, Any]:
        """
        公交（公交+地铁）路径规划

        文档: https://lbs.amap.com/api/webservice/guide/api/direction#4

        Args:
            origin (str): 起点经纬度，格式 "经度,纬度"
            destination (str): 终点经纬度，格式 "经度,纬度"
            city (str): 起点所在城市（必须提供）
            cityd (str, optional): 终点所在城市（跨城公交时必填）
            strategy (int): 换乘策略。默认0（最快捷模式）。
                0: 最快捷模式
                1: 最经济模式
                2: 最少换乘模式
                3: 最少步行模式
                5: 不乘地铁模式
            nightflag (int): 是否计算夜班车。0: 不计算，1: 计算。

        Returns:
            dict: 包含公交路线详情的字典
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

    # ======================
    # POI 搜索
    # ======================

    def poi_search_by_keyword(self, keywords: str, types: Optional[str] = None,
                              city: Optional[str] = None, citylimit: bool = False,
                              page: int = 1, offset: int = 20,
                              extensions: str = "base") -> Dict[str, Any]:
        """
        关键字搜索 POI

        文档: https://lbs.amap.com/api/webservice/guide/api-advanced/newpoisearch#1

        Args:
            keywords (str): 查询关键字，多个关键字用空格分隔
            types (str, optional): POI 类型，例如 "010000"（美食）。详见高德分类代码表。
            city (str, optional): 查询城市
            citylimit (bool): 是否限制城市范围内搜索，默认 False
            page (int): 页码，默认1
            offset (int): 每页记录数，最大50
            extensions (str): 返回数据扩展。"base" 或 "all"

        Returns:
            dict: 包含POI列表的字典
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

        return self._make_request("/v5/place/text", params)

    def poi_search_around(self, center: str, radius: int = 3000,
                          keywords: Optional[str] = None, types: Optional[str] = None,
                          page: int = 1, offset: int = 20,
                          extensions: str = "base") -> Dict[str, Any]:
        """
        周边搜索 POI

        文档: https://lbs.amap.com/api/webservice/guide/api-advanced/newpoisearch#2

        Args:
            center (str): 中心点经纬度，格式 "经度,纬度"
            radius (int): 查询半径（米），最大50000
            keywords (str, optional): 查询关键字
            types (str, optional): POI 类型
            page (int): 页码
            offset (int): 每页记录数
            extensions (str): 返回数据扩展。"base" 或 "all"

        Returns:
            dict: 包含POI列表的字典
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

        return self._make_request("/v5/place/around", params)

    def poi_search_by_polygon(self, polygon: str, keywords: Optional[str] = None,
                              types: Optional[str] = None, page: int = 1, 
                              offset: int = 20, extensions: str = "base") -> Dict[str, Any]:
        """
        多边形搜索 POI

        文档: https://lbs.amap.com/api/webservice/guide/api-advanced/newpoisearch#3

        Args:
            polygon (str): 多边形区域坐标，格式 "经度1,纬度1|经度2,纬度2|...|经度n,纬度n"
                          首尾坐标需相同形成闭合区域
            keywords (str, optional): 查询关键字
            types (str, optional): POI 类型
            page (int): 页码
            offset (int): 每页记录数
            extensions (str): 返回数据扩展。"base" 或 "all"

        Returns:
            dict: 包含POI列表的字典
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

        return self._make_request("/v5/place/polygon", params)

    def poi_search_by_id(self, ids: Union[str, List[str]]) -> Dict[str, Any]:
        """
        ID 查询 POI

        文档: https://lbs.amap.com/api/webservice/guide/api-advanced/newpoisearch#4

        Args:
            ids (str or list): POI ID 或 ID 列表，多个ID用","分隔

        Returns:
            dict: 包含POI详情的字典
        """
        if isinstance(ids, list):
            ids = ",".join(ids)
        logger.info("POI ID search: ids=%s", ids)
        params = {"id": ids}
        return self._make_request("/v5/place/detail", params)

    # ======================
    # 距离测量
    # ======================

    def distance(self, origins: Union[str, List[str]], destination: str,
                 distance_type: Union[int, DistanceType] = DistanceType.STRAIGHT) -> Dict[str, Any]:
        """
        距离测量

        文档: https://lbs.amap.com/api/webservice/guide/api/distance

        Args:
            origins (str or list): 起点经纬度，可以是单个坐标或坐标列表
                单个: "经度,纬度"
                多个: ["经度1,纬度1", "经度2,纬度2"] 或 "经度1,纬度1|经度2,纬度2"
            destination (str): 终点经纬度，格式 "经度,纬度"
            distance_type (int or DistanceType): 距离测量类型
                0: 直线距离
                1: 驾车距离
                3: 步行距离

        Returns:
            dict: 包含距离测量结果的字典
                {
                    "results": [
                        {
                            "origin_id": "1",
                            "dest_id": "1",
                            "distance": "1234",
                            "duration": "300"
                        }
                    ]
                }
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
        return self._make_request("/v3/distance", params)

    # ======================
    # 行政区划查询
    # ======================

    def district_query(self, keywords: Optional[str] = None, 
                       subdistrict: int = 1, 
                       extensions: str = "base") -> Dict[str, Any]:
        """
        行政区划查询

        文档: https://lbs.amap.com/api/webservice/guide/api/district

        Args:
            keywords (str, optional): 查询关键字，支持行政区名称、adcode、citycode
                例如: "北京"、"110000"、"010"
            subdistrict (int): 子级行政区级别
                0: 不返回下级行政区
                1: 返回下一级行政区
                2: 返回下两级行政区
                3: 返回下三级行政区
            extensions (str): 返回数据扩展。"base" 或 "all"（包含边界坐标）

        Returns:
            dict: 包含行政区划信息的字典
                {
                    "districts": [
                        {
                            "adcode": "110000",
                            "name": "北京市",
                            "center": "116.405285,39.904989",
                            "level": "province",
                            "districts": [...]
                        }
                    ]
                }
        """
        logger.info("District query: keywords=%s, subdistrict=%d", keywords, subdistrict)
        params = {
            "subdistrict": str(subdistrict),
            "extensions": extensions
        }
        if keywords:
            params["keywords"] = keywords
        return self._make_request("/v3/config/district", params)

    # ======================
    # IP 定位
    # ======================

    def ip_location(self, ip: Optional[str] = None) -> Dict[str, Any]:
        """
        IP 定位

        文档: https://lbs.amap.com/api/webservice/guide/api/ipconfig

        Args:
            ip (str, optional): IP 地址，不传则使用请求者的 IP

        Returns:
            dict: 包含 IP 定位结果的字典
                {
                    "province": "北京",
                    "city": "北京市",
                    "adcode": "110000",
                    "rectangle": "116.0119343,39.6612767;116.7829835,40.2164962"
                }
        """
        logger.info("IP location query: ip=%s", ip or "auto")
        params = {}
        if ip:
            params["ip"] = ip
        return self._make_request("/v3/ip", params)

    # ======================
    # 天气查询
    # ======================

    def weather(self, city: str, extensions: str = "base") -> Dict[str, Any]:
        """
        天气查询

        文档: https://lbs.amap.com/api/webservice/guide/api/weatherinfo

        Args:
            city (str): 城市名称或 adcode
            extensions (str): 返回数据扩展。"base"（实况天气）或 "all"（预报天气）

        Returns:
            dict: 包含天气信息的字典
        """
        logger.info("Weather query: city=%s, extensions=%s", city, extensions)
        params = {
            "city": city,
            "extensions": extensions
        }
        return self._make_request("/v3/weather/weatherInfo", params)

    # ======================
    # 输入提示
    # ======================

    def input_tips(self, keywords: str, city: Optional[str] = None,
                   citylimit: bool = False, datatype: str = "all") -> Dict[str, Any]:
        """
        输入提示（自动补全）

        文档: https://lbs.amap.com/api/webservice/guide/api/inputtips

        Args:
            keywords (str): 查询关键字
            city (str, optional): 查询城市
            citylimit (bool): 是否限制城市范围内
            datatype (str): 数据类型。"all" 或 "poi"

        Returns:
            dict: 包含输入提示结果的字典
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


# ======================
# 使用示例
# ======================
if __name__ == "__main__":
    API_KEY = "your_amap_api_key_here"

    client = GaodeMapClient(API_KEY)

    try:
        print("1. 地理编码:")
        geo_result = client.geocode("北京市朝阳区望京SOHO")
        print(json.dumps(geo_result, indent=2, ensure_ascii=False))

        location = geo_result["geocodes"][0]["location"]

        print("\n2. 逆地理编码:")
        regeo_result = client.reverse_geocode(location, extensions="all")
        print(json.dumps(regeo_result, indent=2, ensure_ascii=False))

        print("\n3. 驾车路径规划:")
        drive_result = client.driving_direction(
            origin=location,
            destination="116.386837,39.863673"
        )
        print(f"预计驾车时长: {drive_result['route']['paths'][0]['duration']} 秒")

        print("\n4. 关键字搜索 POI:")
        poi_result = client.poi_search_by_keyword(
            keywords="咖啡厅",
            types="060100",
            city="北京",
            offset=5
        )
        for poi in poi_result["pois"][:3]:
            print(f"- {poi['name']}: {poi['address']}")

        print("\n5. 距离测量:")
        dist_result = client.distance(
            origins=location,
            destination="116.386837,39.863673",
            distance_type=DistanceType.DRIVING
        )
        print(f"距离: {dist_result['results'][0]['distance']} 米")

        print("\n6. 行政区划查询:")
        district_result = client.district_query("北京", subdistrict=1)
        print(f"北京市中心: {district_result['districts'][0]['center']}")

    except GaodeMapAPIError as e:
        print(f"API 错误: {e.message} (code: {e.info_code})")
    except GaodeMapConnectionError as e:
        print(f"连接错误: {e.message}")
    except Exception as e:
        print(f"未知错误: {e}")
