"""
组件: 行程动态调整模块

核心职责:
- POI替换功能 (swap_poi)
- POI删除功能 (skip_poi)
- POI插入功能 (insert_poi)
- POI重排序功能 (reorder_pois)
- 调整历史管理和撤销操作

输入:
- 当前行程数据
- 备选POI池
- 高德客户端

输出:
- 更新后的行程
- 调整记录
"""

from __future__ import annotations
import logging
import copy
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AdjustmentRecord(BaseModel):
    """调整记录"""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    action: str  # "swap", "skip", "insert", "reorder"
    poi_id: int
    details: Dict[str, Any] = Field(default_factory=dict)
    old_state: Dict[str, Any] = Field(default_factory=dict)
    new_state: Dict[str, Any] = Field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp,
            'action': self.action,
            'poi_id': self.poi_id,
            'details': self.details,
            'old_state': self.old_state,
            'new_state': self.new_state
        }


class AdjustmentError(Exception):
    """调整操作错误"""
    pass


class POINotFoundError(AdjustmentError):
    """POI未找到错误"""
    pass


class NoCandidateError(AdjustmentError):
    """无候选POI错误"""
    pass


def _calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    使用Haversine公式计算两点间距离（公里）
    """
    import math
    R = 6371.0
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat / 2) ** 2 + \
        math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def _find_poi_index(itinerary: Dict, poi_id: int) -> int:
    """
    查找POI在行程中的索引位置
    
    Args:
        itinerary: 行程数据
        poi_id: POI ID
        
    Returns:
        POI索引，未找到返回-1
    """
    pois = itinerary.get('pois', [])
    for i, poi in enumerate(pois):
        if poi.get('id') == poi_id:
            return i
    return -1


def _get_poi_by_id(itinerary: Dict, poi_id: int) -> Optional[Dict]:
    """根据ID获取POI信息"""
    pois = itinerary.get('pois', [])
    for poi in pois:
        if poi.get('id') == poi_id:
            return poi
    return None


def _recalculate_travel_time(
    origin: Dict, 
    destination: Dict, 
    amap_client
) -> float:
    """
    使用高德API重新计算两点间通勤时间
    
    Args:
        origin: 起点POI
        destination: 终点POI
        amap_client: 高德客户端
        
    Returns:
        通勤时间（分钟）
    """
    try:
        origin_loc = f"{origin['lon']},{origin['lat']}"
        dest_loc = f"{destination['lon']},{destination['lat']}"
        
        route = amap_client.driving_direction(origin_loc, dest_loc)
        return route.duration_minutes
    except Exception as e:
        logger.warning(f"计算通勤时间失败: {e}，使用直线距离估算")
        distance = _calculate_distance(
            origin['lat'], origin['lon'],
            destination['lat'], destination['lon']
        )
        return distance * 3  # 假设平均时速20km/h


def _update_timestamps(itinerary: Dict, start_index: int, amap_client) -> Dict:
    """
    从指定索引开始更新所有后续节点的时间戳
    
    Args:
        itinerary: 行程数据
        start_index: 开始更新的索引
        amap_client: 高德客户端
        
    Returns:
        更新后的行程
    """
    pois = itinerary.get('pois', [])
    routes = itinerary.get('routes', [])
    time_slots = itinerary.get('time_slots', {})
    
    if start_index >= len(pois):
        return itinerary
    
    for i in range(start_index, len(pois)):
        poi = pois[i]
        prev_poi = pois[i - 1] if i > 0 else None
        
        if prev_poi:
            travel_time = _recalculate_travel_time(prev_poi, poi, amap_client)
            routes[i - 1] = {
                'from_poi_id': prev_poi['id'],
                'to_poi_id': poi['id'],
                'travel_time_min': travel_time
            }
        else:
            travel_time = 0
        
        segment = poi.get('segment', i + 1)
        if str(segment) in time_slots:
            slot = time_slots[str(segment)]
            base_time = datetime.strptime(slot['start'], '%H:%M')
            
            if i > 0:
                prev_end = datetime.strptime(pois[i-1].get('time_end', '00:00'), '%H:%M')
                current_start = prev_end + timedelta(minutes=travel_time)
            else:
                current_start = base_time
            
            stay_time = poi.get('stay_time_min', 60)
            current_end = current_start + timedelta(minutes=stay_time)
            
            poi['time_start'] = current_start.strftime('%H:%M')
            poi['time_end'] = current_end.strftime('%H:%M')
    
    itinerary['pois'] = pois
    itinerary['routes'] = routes
    
    return itinerary


def swap_poi(
    itinerary: Dict, 
    poi_id: int, 
    backup_pool: List[Dict], 
    amap_client, 
    max_distance_km: float = 2.0
) -> Tuple[Dict, Dict]:
    """
    替换行程中的POI
    
    Args:
        itinerary: 当前行程 {"pois": [...], "routes": [...], "time_slots": {...}}
        poi_id: 要替换的POI ID
        backup_pool: 备选POI池（落选但高分的POI）
        amap_client: 高德客户端（用于重新计算通勤时间）
        max_distance_km: 替换POI与原POI的最大距离
        
    Returns:
        (更新后的行程, 替换记录)
        
    Raises:
        POINotFoundError: 指定POI不存在
        NoCandidateError: 无合适的替换候选
    """
    logger.info(f"开始替换POI: ID={poi_id}")
    
    poi_index = _find_poi_index(itinerary, poi_id)
    if poi_index == -1:
        raise POINotFoundError(f"POI {poi_id} 不在行程中")
    
    original_poi = itinerary['pois'][poi_index]
    original_category = original_poi.get('category', '')
    original_lat = original_poi.get('lat', 0)
    original_lon = original_poi.get('lon', 0)
    
    candidates = []
    for backup in backup_pool:
        if backup.get('id') == poi_id:
            continue
        
        if original_category and backup.get('category') != original_category:
            continue
        
        distance = _calculate_distance(
            original_lat, original_lon,
            backup.get('lat', 0), backup.get('lon', 0)
        )
        
        if distance <= max_distance_km:
            score = backup.get('score', backup.get('llm_recommendation_score', 5.0))
            candidates.append({
                'poi': backup,
                'distance': distance,
                'score': score,
                'combined_score': score - distance * 0.5
            })
    
    if not candidates:
        raise NoCandidateError(
            f"未找到合适的替换候选（类别: {original_category}, 最大距离: {max_distance_km}km）"
        )
    
    candidates.sort(key=lambda x: x['combined_score'], reverse=True)
    best_candidate = candidates[0]['poi']
    
    new_itinerary = copy.deepcopy(itinerary)
    old_poi = new_itinerary['pois'][poi_index]
    
    new_poi = copy.deepcopy(best_candidate)
    new_poi['segment'] = old_poi.get('segment')
    new_poi['time_start'] = old_poi.get('time_start')
    new_poi['time_end'] = old_poi.get('time_end')
    new_poi['stay_time_min'] = old_poi.get('stay_time_min', 60)
    
    new_itinerary['pois'][poi_index] = new_poi
    
    new_itinerary = _update_timestamps(new_itinerary, poi_index, amap_client)
    
    record = AdjustmentRecord(
        action="swap",
        poi_id=poi_id,
        details={
            'original_poi_name': original_poi.get('name', ''),
            'original_poi_category': original_category,
            'new_poi_id': new_poi.get('id'),
            'new_poi_name': new_poi.get('name', ''),
            'new_poi_category': new_poi.get('category', ''),
            'distance_km': candidates[0]['distance'],
            'score': candidates[0]['score'],
            'candidates_count': len(candidates)
        },
        old_state={'poi': old_poi},
        new_state={'poi': new_poi}
    )
    
    logger.info(f"POI替换成功: {original_poi.get('name')} -> {new_poi.get('name')}")
    
    return new_itinerary, record.to_dict()


def skip_poi(
    itinerary: Dict, 
    poi_id: int, 
    amap_client
) -> Tuple[Dict, Dict]:
    """
    删除行程中的POI
    
    Args:
        itinerary: 当前行程
        poi_id: 要删除的POI ID
        amap_client: 高德客户端
        
    Returns:
        (更新后的行程, 删除记录)
        
    Raises:
        POINotFoundError: 指定POI不存在
        AdjustmentError: 行程只剩一个POI，无法删除
    """
    logger.info(f"开始删除POI: ID={poi_id}")
    
    poi_index = _find_poi_index(itinerary, poi_id)
    if poi_index == -1:
        raise POINotFoundError(f"POI {poi_id} 不在行程中")
    
    pois = itinerary.get('pois', [])
    if len(pois) <= 1:
        raise AdjustmentError("行程只剩一个POI，无法删除")
    
    new_itinerary = copy.deepcopy(itinerary)
    removed_poi = new_itinerary['pois'].pop(poi_index)
    
    routes = new_itinerary.get('routes', [])
    if poi_index > 0:
        routes_to_remove = [poi_index - 1, poi_index]
        for idx in sorted(routes_to_remove, reverse=True):
            if 0 <= idx < len(routes):
                routes.pop(idx)
    elif routes:
        routes.pop(0)
    
    if poi_index > 0 and poi_index < len(new_itinerary['pois']):
        prev_poi = new_itinerary['pois'][poi_index - 1]
        next_poi = new_itinerary['pois'][poi_index]
        travel_time = _recalculate_travel_time(prev_poi, next_poi, amap_client)
        routes.insert(poi_index - 1, {
            'from_poi_id': prev_poi['id'],
            'to_poi_id': next_poi['id'],
            'travel_time_min': travel_time
        })
    
    new_itinerary['routes'] = routes
    
    for i, poi in enumerate(new_itinerary['pois']):
        if i >= poi_index:
            poi['segment'] = poi.get('segment', i + 1) - 1
    
    new_itinerary = _update_timestamps(new_itinerary, max(0, poi_index - 1), amap_client)
    
    record = AdjustmentRecord(
        action="skip",
        poi_id=poi_id,
        details={
            'removed_poi_name': removed_poi.get('name', ''),
            'removed_poi_category': removed_poi.get('category', ''),
            'removed_index': poi_index,
            'remaining_pois': len(new_itinerary['pois'])
        },
        old_state={'poi': removed_poi, 'index': poi_index},
        new_state={'pois_count': len(new_itinerary['pois'])}
    )
    
    logger.info(f"POI删除成功: {removed_poi.get('name')}")
    
    return new_itinerary, record.to_dict()


def insert_poi(
    itinerary: Dict, 
    poi: Dict, 
    position: int,
    amap_client
) -> Tuple[Dict, Dict]:
    """
    在指定位置插入新POI
    
    Args:
        itinerary: 当前行程
        poi: 要插入的POI
        position: 插入位置（0-based）
        amap_client: 高德客户端
        
    Returns:
        (更新后的行程, 插入记录)
        
    Raises:
        AdjustmentError: 位置无效
    """
    logger.info(f"开始插入POI: {poi.get('name')} at position {position}")
    
    pois = itinerary.get('pois', [])
    
    if position < 0:
        position = 0
    elif position > len(pois):
        position = len(pois)
    
    new_itinerary = copy.deepcopy(itinerary)
    
    new_poi = copy.deepcopy(poi)
    new_poi['segment'] = position + 1
    new_poi['stay_time_min'] = poi.get('stay_time_min', 60)
    
    new_itinerary['pois'].insert(position, new_poi)
    
    routes = new_itinerary.get('routes', [])
    
    if position > 0:
        prev_poi = new_itinerary['pois'][position - 1]
        travel_time = _recalculate_travel_time(prev_poi, new_poi, amap_client)
        routes.insert(position - 1, {
            'from_poi_id': prev_poi['id'],
            'to_poi_id': new_poi['id'],
            'travel_time_min': travel_time
        })
    
    if position < len(new_itinerary['pois']) - 1:
        next_poi = new_itinerary['pois'][position + 1]
        travel_time = _recalculate_travel_time(new_poi, next_poi, amap_client)
        routes.insert(position, {
            'from_poi_id': new_poi['id'],
            'to_poi_id': next_poi['id'],
            'travel_time_min': travel_time
        })
    
    new_itinerary['routes'] = routes
    
    for i, p in enumerate(new_itinerary['pois']):
        if i > position:
            p['segment'] = i + 1
    
    new_itinerary = _update_timestamps(new_itinerary, position, amap_client)
    
    record = AdjustmentRecord(
        action="insert",
        poi_id=poi.get('id', -1),
        details={
            'inserted_poi_name': new_poi.get('name', ''),
            'inserted_poi_category': new_poi.get('category', ''),
            'insert_position': position,
            'total_pois': len(new_itinerary['pois'])
        },
        old_state={'pois_count': len(pois)},
        new_state={'poi': new_poi, 'position': position}
    )
    
    logger.info(f"POI插入成功: {new_poi.get('name')} at position {position}")
    
    return new_itinerary, record.to_dict()


def reorder_pois(
    itinerary: Dict, 
    new_order: List[int],
    amap_client
) -> Tuple[Dict, Dict]:
    """
    重新排序POI
    
    Args:
        itinerary: 当前行程
        new_order: 新的POI ID顺序列表
        amap_client: 高德客户端
        
    Returns:
        (更新后的行程, 重排序记录)
        
    Raises:
        AdjustmentError: 新顺序与原POI数量不匹配
        POINotFoundError: POI ID不存在
    """
    logger.info(f"开始重排序POI: {new_order}")
    
    pois = itinerary.get('pois', [])
    original_order = [p['id'] for p in pois]
    
    if len(new_order) != len(pois):
        raise AdjustmentError(
            f"新顺序数量({len(new_order)})与原POI数量({len(pois)})不匹配"
        )
    
    poi_map = {p['id']: p for p in pois}
    for poi_id in new_order:
        if poi_id not in poi_map:
            raise POINotFoundError(f"POI {poi_id} 不在行程中")
    
    new_itinerary = copy.deepcopy(itinerary)
    
    new_pois = []
    for i, poi_id in enumerate(new_order):
        poi = copy.deepcopy(poi_map[poi_id])
        poi['segment'] = i + 1
        new_pois.append(poi)
    
    new_itinerary['pois'] = new_pois
    
    new_routes = []
    for i in range(len(new_pois) - 1):
        from_poi = new_pois[i]
        to_poi = new_pois[i + 1]
        travel_time = _recalculate_travel_time(from_poi, to_poi, amap_client)
        new_routes.append({
            'from_poi_id': from_poi['id'],
            'to_poi_id': to_poi['id'],
            'travel_time_min': travel_time
        })
    
    new_itinerary['routes'] = new_routes
    new_itinerary = _update_timestamps(new_itinerary, 0, amap_client)
    
    record = AdjustmentRecord(
        action="reorder",
        poi_id=-1,
        details={
            'original_order': original_order,
            'new_order': new_order,
            'total_pois': len(new_pois)
        },
        old_state={'order': original_order},
        new_state={'order': new_order}
    )
    
    logger.info(f"POI重排序成功: {original_order} -> {new_order}")
    
    return new_itinerary, record.to_dict()


class ItineraryAdjuster:
    """行程调整器 - 统一调整接口"""
    
    MAX_HISTORY_SIZE = 10
    
    def __init__(self, amap_client, backup_pool: List[Dict]):
        """
        初始化行程调整器
        
        Args:
            amap_client: 高德客户端
            backup_pool: 备选POI池
        """
        self.client = amap_client
        self.backup_pool = backup_pool
        self.adjustment_history: List[Dict] = []
        self._snapshot_stack: List[Dict] = []
    
    def swap(self, itinerary: Dict, poi_id: int, **kwargs) -> Dict:
        """
        执行POI替换
        
        Args:
            itinerary: 当前行程
            poi_id: 要替换的POI ID
            **kwargs: 额外参数（如max_distance_km）
            
        Returns:
            更新后的行程
        """
        self._save_snapshot(itinerary)
        
        result, record = swap_poi(
            itinerary, poi_id, self.backup_pool, 
            self.client, **kwargs
        )
        
        self._add_to_history(record)
        return result
    
    def skip(self, itinerary: Dict, poi_id: int) -> Dict:
        """
        执行POI删除
        
        Args:
            itinerary: 当前行程
            poi_id: 要删除的POI ID
            
        Returns:
            更新后的行程
        """
        self._save_snapshot(itinerary)
        
        result, record = skip_poi(itinerary, poi_id, self.client)
        
        self._add_to_history(record)
        return result
    
    def insert(self, itinerary: Dict, poi: Dict, position: int) -> Dict:
        """
        在指定位置插入新POI
        
        Args:
            itinerary: 当前行程
            poi: 要插入的POI
            position: 插入位置
            
        Returns:
            更新后的行程
        """
        self._save_snapshot(itinerary)
        
        result, record = insert_poi(itinerary, poi, position, self.client)
        
        self._add_to_history(record)
        return result
    
    def reorder(self, itinerary: Dict, new_order: List[int]) -> Dict:
        """
        重新排序POI
        
        Args:
            itinerary: 当前行程
            new_order: 新的POI ID顺序列表
            
        Returns:
            更新后的行程
        """
        self._save_snapshot(itinerary)
        
        result, record = reorder_pois(itinerary, new_order, self.client)
        
        self._add_to_history(record)
        return result
    
    def get_adjustment_history(self) -> List[Dict]:
        """
        获取调整历史
        
        Returns:
            调整历史列表
        """
        return copy.deepcopy(self.adjustment_history)
    
    def undo_last_adjustment(self, itinerary: Dict) -> Dict:
        """
        撤销最后一次调整
        
        Args:
            itinerary: 当前行程（用于验证）
            
        Returns:
            撤销后的行程
            
        Raises:
            AdjustmentError: 无可撤销的操作
        """
        if not self._snapshot_stack:
            raise AdjustmentError("无可撤销的操作")
        
        last_snapshot = self._snapshot_stack.pop()
        
        if self.adjustment_history:
            undone_record = self.adjustment_history.pop()
            logger.info(f"撤销操作: {undone_record.get('action')} - POI {undone_record.get('poi_id')}")
        
        return copy.deepcopy(last_snapshot)
    
    def clear_history(self):
        """清空调整历史"""
        self.adjustment_history.clear()
        self._snapshot_stack.clear()
        logger.info("调整历史已清空")
    
    def get_last_adjustment(self) -> Optional[Dict]:
        """
        获取最后一次调整记录
        
        Returns:
            最后一次调整记录，无则返回None
        """
        if self.adjustment_history:
            return copy.deepcopy(self.adjustment_history[-1])
        return None
    
    def _save_snapshot(self, itinerary: Dict):
        """保存行程快照（用于撤销）"""
        snapshot = copy.deepcopy(itinerary)
        self._snapshot_stack.append(snapshot)
        
        if len(self._snapshot_stack) > self.MAX_HISTORY_SIZE:
            self._snapshot_stack.pop(0)
    
    def _add_to_history(self, record: Dict):
        """添加调整记录到历史"""
        self.adjustment_history.append(record)
        
        if len(self.adjustment_history) > self.MAX_HISTORY_SIZE:
            self.adjustment_history.pop(0)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取调整统计信息
        
        Returns:
            统计信息字典
        """
        stats = {
            'total_adjustments': len(self.adjustment_history),
            'can_undo': len(self._snapshot_stack) > 0,
            'undo_available': len(self._snapshot_stack),
            'by_action': {}
        }
        
        for record in self.adjustment_history:
            action = record.get('action', 'unknown')
            stats['by_action'][action] = stats['by_action'].get(action, 0) + 1
        
        return stats
