"""
坐标转换工具测试
================

测试坐标系转换的准确性和边界情况。
"""

import pytest
from gaodeapi.coordinate_utils import (
    wgs84_to_gcj02,
    gcj02_to_wgs84,
    wgs84_to_bd09,
    bd09_to_wgs84,
    convert_coordinate,
    detect_coordinate_system,
    is_in_china
)


class TestWGS84ToGCJ02:
    """WGS84 转 GCJ02 测试"""
    
    def test_beijing_coordinates(self):
        """北京坐标转换测试"""
        lng, lat = 116.397428, 39.90923
        result_lng, result_lat = wgs84_to_gcj02(lng, lat)
        
        assert 116.3 < result_lng < 116.5
        assert 39.8 < result_lat < 40.0
    
    def test_shanghai_coordinates(self):
        """上海坐标转换测试"""
        lng, lat = 121.472644, 31.231706
        result_lng, result_lat = wgs84_to_gcj02(lng, lat)
        
        assert 121.3 < result_lng < 121.6
        assert 31.1 < result_lat < 31.4
    
    def test_outside_china(self):
        """中国境外坐标不转换"""
        lng, lat = -122.4194, 37.7749  # 旧金山
        result_lng, result_lat = wgs84_to_gcj02(lng, lat)
        
        assert result_lng == lng
        assert result_lat == lat
    
    def test_boundary_cases(self):
        """边界情况测试"""
        # 中国最北点
        lng, lat = 117.37, 53.55
        result_lng, result_lat = wgs84_to_gcj02(lng, lat)
        assert result_lng is not None
        assert result_lat is not None
        
        # 中国最南点
        lng, lat = 117.21, 18.15
        result_lng, result_lat = wgs84_to_gcj02(lng, lat)
        assert result_lng is not None
        assert result_lat is not None


class TestGCJ02ToWGS84:
    """GCJ02 转 WGS84 测试"""
    
    def test_round_trip(self):
        """往返转换测试"""
        original_lng, original_lat = 116.397428, 39.90923
        
        # WGS84 -> GCJ02
        gcj_lng, gcj_lat = wgs84_to_gcj02(original_lng, original_lat)
        
        # GCJ02 -> WGS84
        wgs_lng, wgs_lat = gcj02_to_wgs84(gcj_lng, gcj_lat)
        
        # 往返转换误差应在可接受范围内
        assert abs(wgs_lng - original_lng) < 0.01
        assert abs(wgs_lat - original_lat) < 0.01


class TestCoordinateSystem:
    """坐标系检测测试"""
    
    def test_detect_gcj02(self):
        """检测 GCJ02 坐标"""
        # GCJ02 坐标通常在中国范围内
        lng, lat = 116.397428, 39.90923
        system = detect_coordinate_system(lng, lat)
        assert system == "GCJ02"
    
    def test_detect_outside_china(self):
        """检测境外坐标"""
        lng, lat = -122.4194, 37.7749
        system = detect_coordinate_system(lng, lat)
        assert system == "WGS84"
    
    def test_is_in_china(self):
        """中国范围判断"""
        assert is_in_china(116.397428, 39.90923) is True
        assert is_in_china(121.472644, 31.231706) is True
        assert is_in_china(-122.4194, 37.7749) is False


class TestConvertCoordinate:
    """坐标转换函数测试"""
    
    def test_wgs84_to_bd09(self):
        """WGS84 转 BD09"""
        lng, lat = 116.397428, 39.90923
        result_lng, result_lat = wgs84_to_bd09(lng, lat)
        
        assert result_lng is not None
        assert result_lat is not None
    
    def test_bd09_to_wgs84(self):
        """BD09 转 WGS84"""
        lng, lat = 116.434047, 39.911161
        result_lng, result_lat = bd09_to_wgs84(lng, lat)
        
        assert abs(result_lng - 116.397428) < 0.01
        assert abs(result_lat - 39.90923) < 0.01
    
    def test_convert_coordinate_function(self):
        """通用转换函数"""
        lng, lat = 116.397428, 39.90923
        
        # WGS84 -> GCJ02
        result = convert_coordinate(lng, lat, "WGS84", "GCJ02")
        assert result is not None
        
        # GCJ02 -> BD09
        result = convert_coordinate(result[0], result[1], "GCJ02", "BD09")
        assert result is not None
