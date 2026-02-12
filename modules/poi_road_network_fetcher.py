"""
组件1: POI与路网信息获取模块

核心职责:
- 从OpenStreetMap (Overpass API)获取原始POI数据
- 从OSRM获取原始路网时间矩阵
- 不包含数据清洗逻辑

输入:
- 配置参数（区域边界、POI类别、OSRM服务地址）

输出:
- 原始POI数据列表
- 原始路网时间矩阵
"""

from __future__ import annotations
import time
import logging
import requests
from typing import Dict, List, Tuple, Any, Optional
import numpy as np
import math
from .models import RawPOI

logger = logging.getLogger(__name__)

class POIRoadNetworkFetcher:
    """POI与路网信息获取器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: 配置字典（来自config.yaml）
        """
        self.region = config['region']
        self.poi_categories = config['poi_categories']
        self.overpass_config = config['data_fetching']['overpass']
        self.osrm_config = config['data_fetching']['osrm']
        
    # ===========================
    # Overpass API: 获取POI
    # ===========================
    
    def fetch_pois(self) -> List[RawPOI]:
        """
        从Overpass API获取原始POI数据
        
        Returns:
            原始POI列表
        """
        logger.info("开始从Overpass API获取POI数据...")
        
        # 构造Overpass查询语句
        query = self._build_overpass_query()
        
        # 请求Overpass API
        raw_data = self._request_overpass(query)
        
        # 解析返回结果
        pois = self._parse_overpass_response(raw_data)
        
        logger.info(f"✅ 成功获取 {len(pois)} 个原始POI")
        return pois
    
    def _build_overpass_query(self) -> str:
        """构造Overpass QL查询语句"""
        bbox = self.region
        south = bbox['min_lat']
        west = bbox['min_lon']
        north = bbox['max_lat']
        east = bbox['max_lon']
        
        # 从配置中提取OSM标签
        tag_queries = []
        for cat in self.poi_categories:
            osm_tag = cat['osm_tag']
            key, value = osm_tag.split('=')
            
            if value == '*':
                # 任意值（如shop=*）
                tag_queries.append(f'nwr["{key}"]({south},{west},{north},{east});')
            else:
                tag_queries.append(f'nwr["{key}"="{value}"]({south},{west},{north},{east});')
        
        query = f"""
        [out:json][timeout:{self.overpass_config['timeout']}];
        (
          {chr(10).join(tag_queries)}
        );
        out tags center;
        """
        
        return "\n".join(line.strip() for line in query.strip().splitlines())
    
    def _request_overpass(self, query: str) -> Dict[str, Any]:
        """请求Overpass API（带重试）"""
        endpoints = self.overpass_config['endpoints']
        timeout = self.overpass_config['timeout']
        retry = self.overpass_config['retry']
        
        last_error = None
        for endpoint in endpoints:
            for attempt in range(retry + 1):
                try:
                    logger.debug(f"请求Overpass API: {endpoint} (尝试 {attempt+1}/{retry+1})")
                    
                    resp = requests.post(
                        endpoint,
                        data={'data': query},
                        timeout=timeout
                    )
                    
                    if resp.status_code != 200:
                        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                    
                    data = resp.json()
                    
                    if 'elements' not in data:
                        raise ValueError("Overpass响应缺少elements字段")
                    
                    logger.info(f"✅ Overpass API返回 {len(data['elements'])} 个元素")
                    return data
                    
                except Exception as e:
                    last_error = e
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"Overpass请求失败: {e}, {wait_time}秒后重试...")
                    time.sleep(wait_time)
            
            logger.info(f"切换到下一个Overpass端点...")
        
        raise RuntimeError(f"所有Overpass端点请求失败: {last_error}")
    
    def _parse_overpass_response(self, data: Dict[str, Any]) -> List[RawPOI]:
        """解析Overpass响应"""
        pois = []
        
        for element in data.get('elements', []):
            osm_type = element.get('type')
            osmid = element.get('id')
            tags = element.get('tags', {})
            
            # 提取坐标
            if osm_type == 'node':
                lat = element.get('lat')
                lon = element.get('lon')
            else:
                # way/relation使用center
                center = element.get('center', {})
                lat = center.get('lat')
                lon = center.get('lon')
            
            # 跳过无效数据
            if osmid is None or lat is None or lon is None:
                continue
            
            pois.append(RawPOI(
                osm_type=osm_type,
                osmid=osmid,
                lat=float(lat),
                lon=float(lon),
                tags=tags
            ))
        
        return pois
    
    # ===========================
    # OSRM: 获取路网时间矩阵
    # ===========================
    
    def fetch_time_matrix(
        self,
        start_point: Tuple[float, float],
        pois: List[RawPOI]
    ) -> np.ndarray:
        """
        从OSRM获取原始时间矩阵
        
        Args:
            start_point: 起点坐标 (lon, lat)
            pois: POI列表（用于计算矩阵）
        
        Returns:
            时间矩阵（分钟），形状为(N+1, N+1)，第0行/列为起点
        """
        logger.info(f"开始获取OSRM时间矩阵 (起点+{len(pois)}个POI)...")
        
        # 1. Haversine预筛选最近的N个POI
        selected_pois = self._select_nearest_pois(start_point, pois)
        logger.info(f"Haversine预筛选: {len(selected_pois)} 个POI")
        
        # 2. 构造坐标列表（起点+POI）
        points = [start_point] + [(p.lon, p.lat) for p in selected_pois]
        
        # 3. 调用OSRM Table API
        durations = self._request_osrm_table(points)
        
        # 4. 转换为分钟
        matrix_minutes = np.array(durations) / 60.0
        
        logger.info(f"✅ 成功获取时间矩阵，维度: {matrix_minutes.shape}")
        return matrix_minutes
    
    def _select_nearest_pois(
        self,
        start: Tuple[float, float],
        pois: List[RawPOI]
    ) -> List[RawPOI]:
        """基于Haversine距离选择最近的POI"""
        top_n = self.osrm_config['top_n']
        start_lon, start_lat = start
        
        # 计算距离
        scored = []
        for poi in pois:
            dist = self._haversine(start_lon, start_lat, poi.lon, poi.lat)
            scored.append((dist, poi))
        
        # 排序并取前N个
        scored.sort(key=lambda x: x[0])
        return [poi for _, poi in scored[:top_n]]
    
    @staticmethod
    def _haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """Haversine公式计算球面距离（米）"""
        R = 6371000.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = phi2 - phi1
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
    
    def _request_osrm_table(self, points: List[Tuple[float, float]]) -> List[List[float]]:
        """请求OSRM Table API"""
        base_url = self.osrm_config['base_url']
        profile = self.osrm_config['profile']
        timeout = self.osrm_config['timeout']
        retry = self.osrm_config['retry']
        
        # 构造URL
        coords = ";".join([f"{lon:.6f},{lat:.6f}" for lon, lat in points])
        url = f"{base_url}/table/v1/{profile}/{coords}?annotations=duration"
        
        last_error = None
        for attempt in range(retry + 1):
            try:
                logger.debug(f"请求OSRM Table API (尝试 {attempt+1}/{retry+1})")
                
                resp = requests.get(url, timeout=timeout)
                
                if resp.status_code != 200:
                    raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                
                data = resp.json()
                
                if 'durations' not in data:
                    raise ValueError("OSRM响应缺少durations字段")
                
                # 处理null值（不可达点）
                durations = []
                for row in data['durations']:
                    durations.append([
                        None if v is None else float(v)
                        for v in row
                    ])
                
                return durations
                
            except Exception as e:
                last_error = e
                wait_time = (attempt + 1) * 2
                logger.warning(f"OSRM请求失败: {e}, {wait_time}秒后重试...")
                time.sleep(wait_time)
        
        raise RuntimeError(f"OSRM请求失败: {last_error}")