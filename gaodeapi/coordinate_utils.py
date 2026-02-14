"""
坐标系转换工具
==============

实现 WGS-84、GCJ-02、BD-09 三种坐标系之间的转换。

坐标系说明:
- WGS-84: 国际标准坐标系，GPS原始坐标
- GCJ-02: 国家测绘局加密坐标（火星坐标），高德、腾讯地图使用
- BD-09: 百度加密坐标，百度地图使用

注意: 高德地图API使用 GCJ-02 坐标系
"""

from __future__ import annotations
import math
from typing import Tuple, Optional
from enum import Enum


class CoordinateSystem(str, Enum):
    """坐标系类型枚举"""
    WGS84 = "WGS84"
    GCJ02 = "GCJ02"
    BD09 = "BD09"


PI = math.pi
A = 6378245.0
EE = 0.00669342162296594323
X_PI = PI * 3000.0 / 180.0

CHINA_BOUNDS = {
    "north": 53.55,
    "south": 18.15,
    "west": 73.66,
    "east": 135.05,
}


def _transform_lat(lng: float, lat: float) -> float:
    """纬度转换辅助函数"""
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + \
          0.1 * lng * lat + 0.2 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * PI) + 20.0 *
            math.sin(2.0 * lng * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * PI) + 40.0 *
            math.sin(lat / 3.0 * PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * PI) + 320 *
            math.sin(lat * PI / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(lng: float, lat: float) -> float:
    """经度转换辅助函数"""
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + \
          0.1 * lng * lat + 0.1 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * PI) + 20.0 *
            math.sin(2.0 * lng * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * PI) + 40.0 *
            math.sin(lng / 3.0 * PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * PI) + 300.0 *
            math.sin(lng / 30.0 * PI)) * 2.0 / 3.0
    return ret


def _out_of_china(lng: float, lat: float) -> bool:
    """判断坐标是否在中国境外"""
    if lng < CHINA_BOUNDS["west"] or lng > CHINA_BOUNDS["east"]:
        return True
    if lat < CHINA_BOUNDS["south"] or lat > CHINA_BOUNDS["north"]:
        return True
    return False


def wgs84_to_gcj02(lng: float, lat: float) -> Tuple[float, float]:
    """
    WGS-84 转 GCJ-02

    Args:
        lng: WGS-84 经度
        lat: WGS-84 纬度

    Returns:
        Tuple[float, float]: (GCJ-02 经度, GCJ-02 纬度)
    """
    if _out_of_china(lng, lat):
        return lng, lat

    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlng = (dlng * 180.0) / (A / sqrtmagic * math.cos(radlat) * PI)
    mglat = lat + dlat
    mglng = lng + dlng
    return mglng, mglat


def gcj02_to_wgs84(lng: float, lat: float) -> Tuple[float, float]:
    """
    GCJ-02 转 WGS-84

    Args:
        lng: GCJ-02 经度
        lat: GCJ-02 纬度

    Returns:
        Tuple[float, float]: (WGS-84 经度, WGS-84 纬度)
    """
    if _out_of_china(lng, lat):
        return lng, lat

    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlng = (dlng * 180.0) / (A / sqrtmagic * math.cos(radlat) * PI)
    mglat = lat + dlat
    mglng = lng + dlng
    return lng * 2 - mglng, lat * 2 - mglat


def gcj02_to_bd09(lng: float, lat: float) -> Tuple[float, float]:
    """
    GCJ-02 转 BD-09

    Args:
        lng: GCJ-02 经度
        lat: GCJ-02 纬度

    Returns:
        Tuple[float, float]: (BD-09 经度, BD-09 纬度)
    """
    z = math.sqrt(lng * lng + lat * lat) + 0.00002 * math.sin(lat * X_PI)
    theta = math.atan2(lat, lng) + 0.000003 * math.cos(lng * X_PI)
    bd_lng = z * math.cos(theta) + 0.0065
    bd_lat = z * math.sin(theta) + 0.006
    return bd_lng, bd_lat


def bd09_to_gcj02(lng: float, lat: float) -> Tuple[float, float]:
    """
    BD-09 转 GCJ-02

    Args:
        lng: BD-09 经度
        lat: BD-09 纬度

    Returns:
        Tuple[float, float]: (GCJ-02 经度, GCJ-02 纬度)
    """
    x = lng - 0.0065
    y = lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * X_PI)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * X_PI)
    gcj_lng = z * math.cos(theta)
    gcj_lat = z * math.sin(theta)
    return gcj_lng, gcj_lat


def bd09_to_wgs84(lng: float, lat: float) -> Tuple[float, float]:
    """
    BD-09 转 WGS-84

    Args:
        lng: BD-09 经度
        lat: BD-09 纬度

    Returns:
        Tuple[float, float]: (WGS-84 经度, WGS-84 纬度)
    """
    gcj_lng, gcj_lat = bd09_to_gcj02(lng, lat)
    return gcj02_to_wgs84(gcj_lng, gcj_lat)


def wgs84_to_bd09(lng: float, lat: float) -> Tuple[float, float]:
    """
    WGS-84 转 BD-09

    Args:
        lng: WGS-84 经度
        lat: WGS-84 纬度

    Returns:
        Tuple[float, float]: (BD-09 经度, BD-09 纬度)
    """
    gcj_lng, gcj_lat = wgs84_to_gcj02(lng, lat)
    return gcj02_to_bd09(gcj_lng, gcj_lat)


def detect_coordinate_system(lat: float, lng: float, 
                              reference_lng: Optional[float] = None,
                              reference_lat: Optional[float] = None) -> CoordinateSystem:
    """
    检测坐标所属的坐标系类型

    该方法通过分析坐标与中国境内位置的关系来判断坐标系类型。
    由于 WGS-84 和 GCJ-02 在中国境内存在偏移，可以通过对比来判断。

    Args:
        lat: 纬度
        lng: 经度
        reference_lng: 参考点经度（已知 GCJ-02 坐标），可选
        reference_lat: 参考点纬度（已知 GCJ-02 坐标），可选

    Returns:
        CoordinateSystem: 检测到的坐标系类型

    Note:
        如果坐标在中国境外，返回 WGS84（因为境外无加密）
        如果没有参考点，使用启发式方法判断
    """
    if _out_of_china(lng, lat):
        return CoordinateSystem.WGS84

    if reference_lng is not None and reference_lat is not None:
        wgs_lng, wgs_lat = gcj02_to_wgs84(reference_lng, reference_lat)
        dist_to_gcj = math.sqrt((lng - reference_lng) ** 2 + (lat - reference_lat) ** 2)
        dist_to_wgs = math.sqrt((lng - wgs_lng) ** 2 + (lat - wgs_lat) ** 2)

        if dist_to_gcj < dist_to_wgs:
            return CoordinateSystem.GCJ02
        else:
            return CoordinateSystem.WGS84

    gcj_lng, gcj_lat = wgs84_to_gcj02(lng, lat)
    offset = math.sqrt((gcj_lng - lng) ** 2 + (gcj_lat - lat) ** 2)

    if offset < 0.0001:
        return CoordinateSystem.WGS84
    else:
        return CoordinateSystem.GCJ02


def convert_coordinate(lng: float, lat: float,
                       from_sys: CoordinateSystem,
                       to_sys: CoordinateSystem) -> Tuple[float, float]:
    """
    通用坐标转换函数

    Args:
        lng: 经度
        lat: 纬度
        from_sys: 源坐标系
        to_sys: 目标坐标系

    Returns:
        Tuple[float, float]: 转换后的 (经度, 纬度)
    """
    if from_sys == to_sys:
        return lng, lat

    convert_map = {
        (CoordinateSystem.WGS84, CoordinateSystem.GCJ02): wgs84_to_gcj02,
        (CoordinateSystem.GCJ02, CoordinateSystem.WGS84): gcj02_to_wgs84,
        (CoordinateSystem.GCJ02, CoordinateSystem.BD09): gcj02_to_bd09,
        (CoordinateSystem.BD09, CoordinateSystem.GCJ02): bd09_to_gcj02,
        (CoordinateSystem.WGS84, CoordinateSystem.BD09): wgs84_to_bd09,
        (CoordinateSystem.BD09, CoordinateSystem.WGS84): bd09_to_wgs84,
    }

    converter = convert_map.get((from_sys, to_sys))
    if converter:
        return converter(lng, lat)

    raise ValueError(f"不支持的坐标转换: {from_sys} -> {to_sys}")


def ensure_gcj02(lng: float, lat: float, 
                  source_sys: Optional[CoordinateSystem] = None) -> Tuple[float, float]:
    """
    确保坐标为 GCJ-02 坐标系（高德地图使用）

    Args:
        lng: 经度
        lat: 纬度
        source_sys: 源坐标系，如果不提供则自动检测

    Returns:
        Tuple[float, float]: GCJ-02 坐标 (经度, 纬度)
    """
    if source_sys is None:
        source_sys = detect_coordinate_system(lat, lng)

    if source_sys == CoordinateSystem.GCJ02:
        return lng, lat

    return convert_coordinate(lng, lat, source_sys, CoordinateSystem.GCJ02)


def ensure_wgs84(lng: float, lat: float,
                  source_sys: Optional[CoordinateSystem] = None) -> Tuple[float, float]:
    """
    确保坐标为 WGS-84 坐标系（GPS标准坐标）

    Args:
        lng: 经度
        lat: 纬度
        source_sys: 源坐标系，如果不提供则自动检测

    Returns:
        Tuple[float, float]: WGS-84 坐标 (经度, 纬度)
    """
    if source_sys is None:
        source_sys = detect_coordinate_system(lat, lng)

    if source_sys == CoordinateSystem.WGS84:
        return lng, lat

    return convert_coordinate(lng, lat, source_sys, CoordinateSystem.WGS84)
