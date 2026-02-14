"""
路径规划器模块
==============

包含四个核心组件:
1. GeoClusterer - 地理聚类器，按时段对POI进行分组
2. TSPSolver - TSP贪心排序，优化POI访问顺序
3. MultiModalRouter - 多模式通勤计算
4. TimeValidator - 时间校验与调整
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.warning("numpy not available, using simplified K-Means implementation")


class GeoClusterer:
    """地理聚类器 - 按时段对POI进行分组"""
    
    def __init__(self, n_clusters: int = 3):
        """
        Args:
            n_clusters: 聚类数量（默认3：上午/下午/晚上）
        """
        self.n_clusters = n_clusters
        self._cluster_centers: List[Tuple[float, float]] = []
        self._clusters: Dict[int, List[Dict]] = {}
        self._fitted = False
        
        logger.info(f"GeoClusterer initialized with {n_clusters} clusters")
    
    def fit(self, pois: List[Dict]) -> 'GeoClusterer':
        """
        执行K-Means聚类
        
        Args:
            pois: POI列表，每个POI需包含 'lon' 和 'lat' 字段
            
        Returns:
            self
        """
        if not pois:
            logger.warning("Empty POI list provided to fit()")
            return self
        
        coords = []
        for poi in pois:
            lon = poi.get('lon') or poi.get('longitude')
            lat = poi.get('lat') or poi.get('latitude')
            if lon is not None and lat is not None:
                coords.append((float(lon), float(lat)))
        
        if not coords:
            logger.warning("No valid coordinates found in POIs")
            return self
        
        n_samples = len(coords)
        actual_clusters = min(self.n_clusters, n_samples)
        
        if HAS_NUMPY:
            self._fit_numpy(coords, actual_clusters)
        else:
            self._fit_simple(coords, actual_clusters)
        
        for i, poi in enumerate(pois):
            lon = poi.get('lon') or poi.get('longitude')
            lat = poi.get('lat') or poi.get('latitude')
            if lon is not None and lat is not None:
                cluster_id = self._assign_cluster(float(lon), float(lat))
                if cluster_id not in self._clusters:
                    self._clusters[cluster_id] = []
                self._clusters[cluster_id].append(poi)
        
        self._fitted = True
        logger.info(f"K-Means clustering completed: {len(pois)} POIs -> {len(self._clusters)} clusters")
        
        return self
    
    def _fit_numpy(self, coords: List[Tuple[float, float]], n_clusters: int) -> None:
        """使用numpy实现K-Means"""
        X = np.array(coords)
        
        indices = np.random.choice(len(X), n_clusters, replace=False)
        centers = X[indices].copy()
        
        max_iterations = 100
        for _ in range(max_iterations):
            distances = np.sqrt(((X[:, np.newaxis] - centers) ** 2).sum(axis=2))
            labels = np.argmin(distances, axis=1)
            
            new_centers = np.array([
                X[labels == k].mean(axis=0) if np.sum(labels == k) > 0 else centers[k]
                for k in range(n_clusters)
            ])
            
            if np.allclose(centers, new_centers, rtol=1e-4):
                break
            
            centers = new_centers
        
        self._cluster_centers = [tuple(c) for c in centers]
    
    def _fit_simple(self, coords: List[Tuple[float, float]], n_clusters: int) -> None:
        """简化版K-Means实现（不依赖numpy）"""
        import random
        centers = random.sample(coords, n_clusters)
        
        max_iterations = 100
        for _ in range(max_iterations):
            clusters_assignments = {}
            for coord in coords:
                min_dist = float('inf')
                best_cluster = 0
                for i, center in enumerate(centers):
                    dist = self._haversine_distance(coord[1], coord[0], center[1], center[0])
                    if dist < min_dist:
                        min_dist = dist
                        best_cluster = i
                clusters_assignments[coord] = best_cluster
            
            new_centers = []
            for k in range(n_clusters):
                cluster_coords = [c for c, label in clusters_assignments.items() if label == k]
                if cluster_coords:
                    avg_lon = sum(c[0] for c in cluster_coords) / len(cluster_coords)
                    avg_lat = sum(c[1] for c in cluster_coords) / len(cluster_coords)
                    new_centers.append((avg_lon, avg_lat))
                else:
                    new_centers.append(centers[k])
            
            if all(
                abs(new_centers[i][0] - centers[i][0]) < 1e-6 and
                abs(new_centers[i][1] - centers[i][1]) < 1e-6
                for i in range(n_clusters)
            ):
                break
            
            centers = new_centers
        
        self._cluster_centers = centers
    
    def _assign_cluster(self, lon: float, lat: float) -> int:
        """将坐标分配到最近的聚类"""
        min_dist = float('inf')
        best_cluster = 0
        
        for i, center in enumerate(self._cluster_centers):
            dist = self._haversine_distance(lat, lon, center[1], center[0])
            if dist < min_dist:
                min_dist = dist
                best_cluster = i
        
        return best_cluster
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """计算两点间的Haversine距离（公里）"""
        R = 6371.0
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = math.sin(delta_lat / 2) ** 2 + \
            math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def get_cluster_centers(self) -> List[Tuple[float, float]]:
        """获取聚类中心坐标"""
        return self._cluster_centers.copy()
    
    def get_clusters(self) -> Dict[int, List[Dict]]:
        """返回分组的POI集合"""
        return {k: v.copy() for k, v in self._clusters.items()}
    
    def assign_to_time_slots(
        self, 
        pois: List[Dict], 
        distribution: Dict[str, int]
    ) -> Dict[str, List[Dict]]:
        """
        根据用户分布配置分配POI到时段
        
        Args:
            pois: 待分配的POI列表
            distribution: {"morning": 2, "afternoon": 2, "evening": 1}
            
        Returns:
            {"morning": [poi1, poi2], "afternoon": [...], "evening": [...]}
        """
        if not self._fitted:
            self.fit(pois)
        
        time_slots: Dict[str, List[Dict]] = {slot: [] for slot in distribution}
        used_pois = set()
        
        slot_order = ["morning", "afternoon", "evening", "lunch"]
        slot_to_cluster = {}
        
        sorted_centers = sorted(
            enumerate(self._cluster_centers),
            key=lambda x: x[1][0]
        )
        
        for i, slot in enumerate(slot_order):
            if slot in distribution and i < len(sorted_centers):
                slot_to_cluster[slot] = sorted_centers[i % len(sorted_centers)][0]
        
        for slot in slot_order:
            if slot not in distribution:
                continue
            
            target_count = distribution[slot]
            cluster_id = slot_to_cluster.get(slot, 0)
            
            cluster_pois = self._clusters.get(cluster_id, [])
            available = [p for p in cluster_pois if id(p) not in used_pois]
            
            if len(available) < target_count:
                all_available = [p for p in pois if id(p) not in used_pois]
                available = all_available
            
            selected = available[:target_count]
            time_slots[slot] = selected
            
            for p in selected:
                used_pois.add(id(p))
        
        logger.info(f"Assigned {sum(len(v) for v in time_slots.values())} POIs to time slots")
        return time_slots


class TSPSolver:
    """旅行商问题求解器 - 贪心最近邻算法"""
    
    def __init__(self, distance_matrix: List[List[float]]):
        """
        Args:
            distance_matrix: POI之间的距离矩阵（单位：公里或米，需保持一致）
        """
        self.distance_matrix = distance_matrix
        self.n = len(distance_matrix)
        
        logger.info(f"TSPSolver initialized with {self.n} nodes")
    
    def solve_greedy(self, start_index: int = 0) -> Tuple[List[int], float]:
        """
        贪心最近邻算法
        
        Args:
            start_index: 起始节点索引
            
        Returns:
            (访问顺序索引列表, 总距离)
        """
        if self.n == 0:
            return [], 0.0
        
        if start_index < 0 or start_index >= self.n:
            start_index = 0
        
        visited = [False] * self.n
        path = [start_index]
        visited[start_index] = True
        total_distance = 0.0
        
        current = start_index
        for _ in range(self.n - 1):
            nearest_dist = float('inf')
            nearest_node = -1
            
            for j in range(self.n):
                if not visited[j] and self.distance_matrix[current][j] < nearest_dist:
                    nearest_dist = self.distance_matrix[current][j]
                    nearest_node = j
            
            if nearest_node >= 0:
                path.append(nearest_node)
                visited[nearest_node] = True
                total_distance += nearest_dist
                current = nearest_node
        
        logger.info(f"Greedy TSP solved: path length = {len(path)}, total distance = {total_distance:.2f}")
        return path, total_distance
    
    def optimize_route(
        self, 
        pois: List[Dict], 
        start_point: Tuple[float, float]
    ) -> List[Dict]:
        """
        优化POI访问顺序
        
        Args:
            pois: 待排序的POI列表
            start_point: 起点坐标 (lon, lat)
            
        Returns:
            排序后的POI列表
        """
        if not pois:
            return []
        
        def get_coord(poi: Dict) -> Tuple[float, float]:
            lon = poi.get('lon') or poi.get('longitude')
            lat = poi.get('lat') or poi.get('latitude')
            return float(lon), float(lat)
        
        def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
            R = 6371.0
            lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
            delta_lat = math.radians(lat2 - lat1)
            delta_lon = math.radians(lon2 - lon1)
            a = math.sin(delta_lat / 2) ** 2 + \
                math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
            return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        all_points = [start_point] + [get_coord(poi) for poi in pois]
        n = len(all_points)
        
        dist_matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    dist_matrix[i][j] = haversine(
                        all_points[i][0], all_points[i][1],
                        all_points[j][0], all_points[j][1]
                    )
        
        solver = TSPSolver(dist_matrix)
        path, _ = solver.solve_greedy(start_index=0)
        
        sorted_pois = [pois[i - 1] for i in path[1:] if i > 0]
        
        logger.info(f"Route optimized: {len(sorted_pois)} POIs sorted")
        return sorted_pois
    
    def two_opt_improve(self, path: List[int], max_iterations: int = 100) -> Tuple[List[int], float]:
        """
        2-opt局部优化
        
        Args:
            path: 初始路径
            max_iterations: 最大迭代次数
            
        Returns:
            (优化后的路径, 总距离)
        """
        def calculate_total_distance(p: List[int]) -> float:
            total = 0.0
            for i in range(len(p) - 1):
                total += self.distance_matrix[p[i]][p[i + 1]]
            return total
        
        improved = True
        iterations = 0
        best_path = path.copy()
        best_distance = calculate_total_distance(best_path)
        
        while improved and iterations < max_iterations:
            improved = False
            for i in range(1, self.n - 1):
                for j in range(i + 1, self.n):
                    new_path = best_path[:i] + best_path[i:j+1][::-1] + best_path[j+1:]
                    new_distance = calculate_total_distance(new_path)
                    
                    if new_distance < best_distance:
                        best_path = new_path
                        best_distance = new_distance
                        improved = True
            
            iterations += 1
        
        logger.info(f"2-opt improvement: {iterations} iterations, distance = {best_distance:.2f}")
        return best_path, best_distance


class MultiModalRouter:
    """多模式通勤路由器"""
    
    WALKING_THRESHOLD = 1.0
    BIKING_THRESHOLD = 5.0
    
    MODE_SPEEDS = {
        "walking": 5.0,
        "bicycling": 15.0,
        "driving": 40.0,
        "transit": 25.0
    }
    
    def __init__(self, amap_client=None):
        """
        Args:
            amap_client: GaodeMapClient实例，用于实际路线计算
        """
        self.client = amap_client
        
        if self.client:
            logger.info("MultiModalRouter initialized with GaodeMapClient")
        else:
            logger.info("MultiModalRouter initialized without API client (estimation mode)")
    
    def select_mode(
        self, 
        distance_km: float, 
        user_preference: str = "auto"
    ) -> str:
        """
        根据距离选择交通方式
        
        Args:
            distance_km: 直线距离（公里）
            user_preference: "auto", "driving", "transit", "walking"
            
        Returns:
            "walking", "bicycling", "driving", "transit"
        """
        if user_preference != "auto":
            valid_modes = ["walking", "bicycling", "driving", "transit"]
            if user_preference in valid_modes:
                return user_preference
        
        if distance_km <= self.WALKING_THRESHOLD:
            return "walking"
        elif distance_km <= self.BIKING_THRESHOLD:
            return "bicycling"
        else:
            return "driving"
    
    def compute_route(
        self, 
        origin: Tuple[float, float], 
        destination: Tuple[float, float],
        mode: str = "auto"
    ) -> Dict:
        """
        计算两点间的通勤路线
        
        Args:
            origin: 起点坐标 (lon, lat)
            destination: 终点坐标 (lon, lat)
            mode: 交通方式
            
        Returns:
            {
                "distance": 距离(米),
                "duration": 时长(秒),
                "mode": 交通方式,
                "steps": 路线步骤
            }
        """
        def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
            R = 6371.0
            lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
            delta_lat = math.radians(lat2 - lat1)
            delta_lon = math.radians(lon2 - lon1)
            a = math.sin(delta_lat / 2) ** 2 + \
                math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
            return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        straight_distance = haversine(origin[0], origin[1], destination[0], destination[1])
        
        if mode == "auto":
            mode = self.select_mode(straight_distance)
        
        if self.client:
            return self._compute_with_api(origin, destination, mode, straight_distance)
        else:
            return self._estimate_route(origin, destination, mode, straight_distance)
    
    def _compute_with_api(
        self, 
        origin: Tuple[float, float], 
        destination: Tuple[float, float],
        mode: str,
        straight_distance: float
    ) -> Dict:
        """使用高德API计算路线"""
        origin_str = f"{origin[0]},{origin[1]}"
        dest_str = f"{destination[0]},{destination[1]}"
        
        try:
            if mode == "driving":
                route = self.client.driving_direction(origin_str, dest_str)
                return {
                    "distance": route.distance,
                    "duration": route.duration,
                    "mode": mode,
                    "steps": [
                        {
                            "instruction": step.instruction,
                            "distance": step.distance,
                            "duration": step.duration
                        }
                        for step in route.steps
                    ]
                }
            elif mode == "walking":
                route = self.client.walking_direction(origin_str, dest_str)
                return {
                    "distance": route.distance,
                    "duration": route.duration,
                    "mode": mode,
                    "steps": [
                        {
                            "instruction": step.instruction,
                            "distance": step.distance,
                            "duration": step.duration
                        }
                        for step in route.steps
                    ]
                }
            elif mode == "bicycling":
                route = self.client.bicycling_direction(origin_str, dest_str)
                return {
                    "distance": route.distance,
                    "duration": route.duration,
                    "mode": mode,
                    "steps": [
                        {
                            "instruction": step.instruction,
                            "distance": step.distance,
                            "duration": step.duration
                        }
                        for step in route.steps
                    ]
                }
            else:
                return self._estimate_route(origin, destination, mode, straight_distance)
                
        except Exception as e:
            logger.warning(f"API call failed: {e}, falling back to estimation")
            return self._estimate_route(origin, destination, mode, straight_distance)
    
    def _estimate_route(
        self, 
        origin: Tuple[float, float], 
        destination: Tuple[float, float],
        mode: str,
        straight_distance: float
    ) -> Dict:
        """估算路线（无API时使用）"""
        detour_factors = {
            "walking": 1.2,
            "bicycling": 1.3,
            "driving": 1.4,
            "transit": 1.5
        }
        
        factor = detour_factors.get(mode, 1.3)
        distance_m = straight_distance * 1000 * factor
        
        speed = self.MODE_SPEEDS.get(mode, 30.0)
        duration_s = (distance_m / 1000) / speed * 3600
        
        return {
            "distance": int(distance_m),
            "duration": int(duration_s),
            "mode": mode,
            "steps": [
                {
                    "instruction": f"从起点出发，{mode}前往目的地",
                    "distance": int(distance_m),
                    "duration": int(duration_s)
                }
            ]
        }
    
    def compute_route_matrix(
        self, 
        pois: List[Dict], 
        start_point: Tuple[float, float]
    ) -> List[Dict]:
        """
        计算完整的通勤路线序列
        
        Args:
            pois: 已排序的POI列表
            start_point: 起点坐标 (lon, lat)
            
        Returns:
            每段通勤的详细信息列表
        """
        routes = []
        
        def get_coord(poi: Dict) -> Tuple[float, float]:
            lon = poi.get('lon') or poi.get('longitude')
            lat = poi.get('lat') or poi.get('latitude')
            return float(lon), float(lat)
        
        current_point = start_point
        
        for i, poi in enumerate(pois):
            dest = get_coord(poi)
            route = self.compute_route(current_point, dest)
            
            route["from_index"] = -1 if i == 0 else i - 1
            route["to_index"] = i
            route["poi_name"] = poi.get('name', 'Unknown')
            
            routes.append(route)
            current_point = dest
        
        total_distance = sum(r["distance"] for r in routes)
        total_duration = sum(r["duration"] for r in routes)
        
        logger.info(
            f"Route matrix computed: {len(routes)} segments, "
            f"total {total_distance/1000:.1f}km, {total_duration/60:.0f}min"
        )
        
        return routes


class TimeValidator:
    """时间校验器"""
    
    TIME_SLOTS = {
        "morning": {"start": "08:00", "end": "12:00"},
        "lunch": {"start": "12:00", "end": "14:00"},
        "afternoon": {"start": "14:00", "end": "18:00"},
        "evening": {"start": "18:00", "end": "22:00"}
    }
    
    DEFAULT_STAY_TIMES = {
        "restaurant": 60,
        "cafe": 45,
        "attraction": 90,
        "museum": 120,
        "park": 60,
        "shopping": 90,
        "hotel": 30,
        "default": 60
    }
    
    def __init__(self, distribution: Dict = None):
        """
        Args:
            distribution: 时段分布配置，如 {"morning": 2, "afternoon": 2, "evening": 1}
        """
        self.distribution = distribution or {}
        
        logger.info(f"TimeValidator initialized with distribution: {distribution}")
    
    def estimate_stay_time(self, poi: Dict) -> int:
        """
        估算POI停留时间（分钟）
        
        Args:
            poi: POI信息字典
            
        Returns:
            估算的停留时间（分钟）
        """
        if 'stay_time_min' in poi:
            return poi['stay_time_min']
        
        if 'enhanced_info' in poi:
            enhanced = poi['enhanced_info']
            if 'recommended_duration' in enhanced:
                return int(enhanced['recommended_duration'])
        
        category = poi.get('category', '').lower()
        
        for key, time in self.DEFAULT_STAY_TIMES.items():
            if key in category:
                return time
        
        return self.DEFAULT_STAY_TIMES['default']
    
    def validate_itinerary(
        self, 
        pois: List[Dict], 
        routes: List[Dict]
    ) -> Tuple[bool, Dict]:
        """
        校验行程时间是否合理
        
        Args:
            pois: POI列表
            routes: 路线列表
            
        Returns:
            (是否有效, 详细信息)
        """
        total_stay_time = sum(self.estimate_stay_time(poi) for poi in pois)
        total_travel_time = sum(route.get('duration', 0) for route in routes) / 60
        
        total_time = total_stay_time + total_travel_time
        
        max_reasonable_time = 14 * 60
        is_valid = total_time <= max_reasonable_time
        
        details = {
            "total_stay_time_min": total_stay_time,
            "total_travel_time_min": total_travel_time,
            "total_time_min": total_time,
            "is_valid": is_valid,
            "issues": []
        }
        
        if not is_valid:
            details["issues"].append(
                f"总时间{total_time:.0f}分钟超过合理范围（{max_reasonable_time}分钟）"
            )
        
        if total_travel_time > total_stay_time:
            details["issues"].append(
                f"通勤时间({total_travel_time:.0f}分钟)超过停留时间({total_stay_time:.0f}分钟)"
            )
        
        logger.info(
            f"Itinerary validation: {'valid' if is_valid else 'invalid'}, "
            f"total time = {total_time:.0f}min"
        )
        
        return is_valid, details
    
    def adjust_for_overtime(
        self, 
        pois: List[Dict], 
        routes: List[Dict],
        max_total_minutes: int = 600
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        超时自动调整（删除低优先级POI）
        
        Args:
            pois: POI列表
            routes: 路线列表
            max_total_minutes: 最大允许时间（分钟）
            
        Returns:
            (调整后的POI列表, 调整后的路线列表)
        """
        is_valid, details = self.validate_itinerary(pois, routes)
        
        if is_valid and details["total_time_min"] <= max_total_minutes:
            return pois, routes
        
        def get_priority(poi: Dict) -> float:
            if 'priority' in poi:
                return poi['priority']
            if 'enhanced_info' in poi:
                enhanced = poi['enhanced_info']
                if 'rating' in enhanced:
                    return enhanced['rating']
            return 3.0
        
        indexed_pois = [(i, poi, get_priority(poi)) for i, poi in enumerate(pois)]
        sorted_pois = sorted(indexed_pois, key=lambda x: x[2])
        
        adjusted_pois = pois.copy()
        adjusted_routes = routes.copy()
        
        while True:
            is_valid, details = self.validate_itinerary(adjusted_pois, adjusted_routes)
            
            if details["total_time_min"] <= max_total_minutes:
                break
            
            if not sorted_pois:
                break
            
            _, removed_poi, _ = sorted_pois.pop(0)
            
            for i, p in enumerate(adjusted_pois):
                if id(p) == id(removed_poi):
                    adjusted_pois.pop(i)
                    
                    if i < len(adjusted_routes):
                        adjusted_routes.pop(i)
                    elif adjusted_routes:
                        adjusted_routes.pop(-1)
                    
                    break
        
        logger.info(
            f"Overtime adjustment: {len(pois)} -> {len(adjusted_pois)} POIs, "
            f"time {details['total_time_min']:.0f}min"
        )
        
        return adjusted_pois, adjusted_routes
    
    def generate_time_schedule(
        self, 
        pois: List[Dict], 
        routes: List[Dict],
        start_time: str = "08:00"
    ) -> List[Dict]:
        """
        生成详细的时间安排
        
        Args:
            pois: POI列表
            routes: 路线列表
            start_time: 开始时间 "HH:MM"
            
        Returns:
            每个POI的时间安排
        """
        schedule = []
        
        try:
            current_time = datetime.strptime(start_time, "%H:%M")
        except ValueError:
            current_time = datetime.strptime("08:00", "%H:%M")
        
        for i, poi in enumerate(pois):
            travel_time = 0
            if i < len(routes):
                travel_time = routes[i].get('duration', 0) / 60
            
            current_time += timedelta(minutes=travel_time)
            
            stay_time = self.estimate_stay_time(poi)
            arrival_time = current_time.strftime("%H:%M")
            
            current_time += timedelta(minutes=stay_time)
            departure_time = current_time.strftime("%H:%M")
            
            schedule.append({
                "poi_name": poi.get('name', 'Unknown'),
                "arrival_time": arrival_time,
                "departure_time": departure_time,
                "stay_time_min": stay_time,
                "travel_time_min": travel_time,
                "category": poi.get('category', 'Unknown')
            })
        
        return schedule


@dataclass
class RoutePlanResult:
    """路径规划结果"""
    pois: List[Dict]
    routes: List[Dict]
    time_schedule: List[Dict]
    total_distance_m: float
    total_duration_min: float
    total_stay_min: float
    is_valid: bool
    validation_details: Dict = field(default_factory=dict)


class RoutePlanner:
    """路径规划器 - 整合所有组件"""
    
    def __init__(
        self,
        amap_client=None,
        n_clusters: int = 3,
        default_distribution: Dict = None
    ):
        """
        Args:
            amap_client: GaodeMapClient实例
            n_clusters: 聚类数量
            default_distribution: 默认时段分布
        """
        self.amap_client = amap_client
        self.n_clusters = n_clusters
        self.default_distribution = default_distribution or {
            "morning": 2,
            "afternoon": 2,
            "evening": 1
        }
        
        self.clusterer = GeoClusterer(n_clusters=n_clusters)
        self.router = MultiModalRouter(amap_client=amap_client)
        
        logger.info("RoutePlanner initialized")
    
    def plan(
        self,
        pois: List[Dict],
        start_point: Tuple[float, float],
        distribution: Dict = None,
        max_total_minutes: int = 600,
        start_time: str = "08:00"
    ) -> RoutePlanResult:
        """
        执行完整的路径规划
        
        Args:
            pois: POI列表
            start_point: 起点 (lon, lat)
            distribution: 时段分布
            max_total_minutes: 最大时间
            start_time: 开始时间
            
        Returns:
            RoutePlanResult
        """
        distribution = distribution or self.default_distribution
        
        logger.info(f"Starting route planning for {len(pois)} POIs")
        
        self.clusterer.fit(pois)
        
        tsp_solver = TSPSolver(self._build_distance_matrix(pois))
        sorted_indices, _ = tsp_solver.solve_greedy()
        sorted_pois = [pois[i] for i in sorted_indices if i < len(pois)]
        
        sorted_pois = tsp_solver.optimize_route(sorted_pois, start_point)
        
        routes = self.router.compute_route_matrix(sorted_pois, start_point)
        
        validator = TimeValidator(distribution)
        is_valid, validation_details = validator.validate_itinerary(sorted_pois, routes)
        
        if not is_valid or validation_details["total_time_min"] > max_total_minutes:
            sorted_pois, routes = validator.adjust_for_overtime(
                sorted_pois, routes, max_total_minutes
            )
            is_valid, validation_details = validator.validate_itinerary(sorted_pois, routes)
        
        time_schedule = validator.generate_time_schedule(sorted_pois, routes, start_time)
        
        total_distance = sum(r.get('distance', 0) for r in routes)
        total_duration = sum(r.get('duration', 0) for r in routes) / 60
        total_stay = sum(validator.estimate_stay_time(p) for p in sorted_pois)
        
        result = RoutePlanResult(
            pois=sorted_pois,
            routes=routes,
            time_schedule=time_schedule,
            total_distance_m=total_distance,
            total_duration_min=total_duration,
            total_stay_min=total_stay,
            is_valid=is_valid,
            validation_details=validation_details
        )
        
        logger.info(
            f"Route planning completed: {len(sorted_pois)} POIs, "
            f"{total_duration:.0f}min travel, {total_stay:.0f}min stay"
        )
        
        return result
    
    def _build_distance_matrix(self, pois: List[Dict]) -> List[List[float]]:
        """构建POI间距离矩阵"""
        n = len(pois)
        matrix = [[0.0] * n for _ in range(n)]
        
        def get_coord(poi: Dict) -> Tuple[float, float]:
            lon = poi.get('lon') or poi.get('longitude')
            lat = poi.get('lat') or poi.get('latitude')
            return float(lon), float(lat)
        
        for i in range(n):
            for j in range(n):
                if i != j:
                    coord_i = get_coord(pois[i])
                    coord_j = get_coord(pois[j])
                    matrix[i][j] = self._haversine(
                        coord_i[0], coord_i[1],
                        coord_j[0], coord_j[1]
                    )
        
        return matrix
    
    def _haversine(self, lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """Haversine距离计算"""
        R = 6371.0
        lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        a = math.sin(delta_lat / 2) ** 2 + \
            math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
