"""
组件2: POI过滤清洗模块

核心职责:
- 对原始POI数据进行校验与清洗
- 对路网时间矩阵进行校验
- 确保数据有效性

输入:
- 原始POI数据（组件1输出）
- 原始路网时间矩阵（组件1输出）
- 配置参数

输出:
- 清洗后POI数据
- 校验后路网时间矩阵
- 清洗报告
"""

from __future__ import annotations
import logging
from typing import Dict, List, Optional, Tuple
import numpy as np
import re
from .models import RawPOI, CleanedPOI, TimeMatrix

logger = logging.getLogger(__name__)

class POIFilterCleaner:
    """POI过滤清洗器"""
    
    # 名称黑名单关键词（包含任一关键词则过滤）
    NAME_BLACKLIST = {
        '超市', '百货', '宿舍', '洗衣', '理发', '美发', '食堂', '成人', 
        '商店', '健身', 'gym', '眼镜', '医院', '便利店', '经销商', 
        '黄金', '钻石', '金银', '移动', '联通', '电信', '造型', '服务',
        '修脚', '美甲', '养生', '烟', '市场', '洗浴', '足浴', '按摩', 
        '药', '汽车', '电动车', '体育', '操场', '足球', '游泳', '排球',
        '篮球', '网球', '运动', '训练', '售票', '手球', '门球', '速滑',
        '滑雪', '文具', '物美', '便利蜂', '发艺', '法院', '检察院', '邮政', '邮局',
        '快递', '出租', '租赁', '驾校', '车行', '加油', '加气', '充电', '停车', '停车', '球场'
    }
    def __init__(self, config: Dict):
        """
        Args:
            config: 配置字典
        """
        self.region = config['region']
        self.poi_categories = config['poi_categories']
        self.cleaning_config = config['data_cleaning']
        
        # 构建OSM标签到中文类别的映射
        self.tag_to_category = self._build_tag_mapper()
    
    def _build_tag_mapper(self) -> Dict[str, str]:
        """构建OSM标签->中文类别映射器"""
        mapper = {}
        for cat_config in self.poi_categories:
            osm_tag = cat_config['osm_tag']
            chinese_category = cat_config['chinese_category']
            mapper[osm_tag] = chinese_category
        return mapper
    
    # ===========================
    # POI清洗
    # ===========================
    
    def clean_pois(self, raw_pois: List[RawPOI]) -> Tuple[List[CleanedPOI], Dict]:
        """
        清洗POI数据
        
        Args:
            raw_pois: 原始POI列表
        
        Returns:
            (清洗后POI列表, 清洗报告)
        """
        logger.info(f"开始清洗 {len(raw_pois)} 个原始POI...")
        
        report = {
            'total_raw': len(raw_pois),
            'filtered': {
                'no_name': 0,
                'invalid_coordinates': 0,
                'out_of_region': 0,
                'no_category_match': 0,
                'duplicate': 0,
                'blacklist_name': 0,  # 新增：被名称黑名单过滤
                'pure_digits': 0      # 新增：纯数字名称
            },
            'cleaned_count': 0
        }
        
        cleaned = []
        seen_osmids = set()
        
        for idx, raw_poi in enumerate(raw_pois):
            # 1. 检查名称
            name = self._extract_name(raw_poi.tags)
            if not name and self.cleaning_config['poi_filters']['require_name']:
                report['filtered']['no_name'] += 1
                continue
            
            # 2. 检查纯数字名称
            if name and self._is_pure_digits(name):
                report['filtered']['pure_digits'] += 1
                logger.debug(f"过滤纯数字名称: {name}")
                continue
            
            # 3. 检查黑名单关键词
            if name and self._contains_blacklist_keyword(name):
                report['filtered']['blacklist_name'] += 1
                logger.debug(f"过滤黑名单名称: {name}")
                continue
            
            # 4. 检查坐标
            if not self._validate_coordinates(raw_poi.lat, raw_poi.lon):
                report['filtered']['invalid_coordinates'] += 1
                continue
            
            # 5. 检查是否在区域内
            if not self._is_in_region(raw_poi.lat, raw_poi.lon):
                report['filtered']['out_of_region'] += 1
                continue
            
            # 6. 映射中文类别
            category = self._map_category(raw_poi.tags)
            if not category:
                report['filtered']['no_category_match'] += 1
                continue
            
            # 7. 去重
            if raw_poi.osmid in seen_osmids:
                report['filtered']['duplicate'] += 1
                continue
            seen_osmids.add(raw_poi.osmid)
            
            # 8. 构造清洗后POI
            cleaned.append(CleanedPOI(
                id=idx,
                osm_type=raw_poi.osm_type,
                osmid=raw_poi.osmid,
                name=name,
                category=category,
                lat=raw_poi.lat,
                lon=raw_poi.lon,
                tags=raw_poi.tags
            ))
        
        report['cleaned_count'] = len(cleaned)
        
        logger.info(f"✅ POI清洗完成: {len(cleaned)}/{len(raw_pois)} 保留")
        logger.info(f"   过滤原因: {report['filtered']}")
        
        return cleaned, report
    
    def _extract_name(self, tags: Dict[str, str]) -> str:
        """从tags中提取名称（优先级: name > name:zh > name:en）"""
        return (
            tags.get('name') or
            tags.get('name:zh') or
            tags.get('name:en') or
            ""
        )
    
    def _is_pure_digits(self, name: str) -> bool:
        """检查名称是否为纯数字（含空格、标点）"""
        # 移除所有非数字字符后，如果剩余内容全是数字，则认为是纯数字
        clean_name = re.sub(r'[\s\-_.,;:()（）]', '', name)
        return clean_name.isdigit() and len(clean_name) > 0
    
    def _contains_blacklist_keyword(self, name: str) -> bool:
        """检查名称是否包含黑名单关键词"""
        name_lower = name.lower()
        for keyword in self.NAME_BLACKLIST:
            if keyword.lower() in name_lower:
                return True
        return False
    
    def _validate_coordinates(self, lat: float, lon: float) -> bool:
        """验证坐标是否在有效范围"""
        return -90 <= lat <= 90 and -180 <= lon <= 180
    
    def _is_in_region(self, lat: float, lon: float) -> bool:
        """检查坐标是否在配置的区域内"""
        return (
            self.region['min_lat'] <= lat <= self.region['max_lat'] and
            self.region['min_lon'] <= lon <= self.region['max_lon']
        )
    
    def _map_category(self, tags: Dict[str, str]) -> Optional[str]:
        """
        将OSM标签映射为中文类别（按优先级匹配）
        
        Returns:
            中文类别名，无匹配返回None
        """
        for cat_config in self.poi_categories:
            osm_tag = cat_config['osm_tag']
            chinese_category = cat_config['chinese_category']
            
            key, value = osm_tag.split('=')
            
            if key in tags:
                if value == '*' or tags[key] == value:
                    return chinese_category
        
        return None
    
    # ===========================
    # 时间矩阵校验
    # ===========================
    
    def validate_time_matrix(
        self,
        matrix: np.ndarray,
        cleaned_pois: List[CleanedPOI]
    ) -> TimeMatrix:
        """
        校验路网时间矩阵
        
        Args:
            matrix: 原始时间矩阵（分钟）
            cleaned_pois: 清洗后的POI列表
        
        Returns:
            校验后的TimeMatrix对象
        """
        logger.info(f"开始校验时间矩阵，维度: {matrix.shape}")
        
        max_time = self.cleaning_config['time_matrix']['max_reasonable_time_minutes']
        min_time = self.cleaning_config['time_matrix']['min_reasonable_time_minutes']
        
        validated = []
        anomaly_count = 0
        
        for row in matrix:
            validated_row = []
            for val in row:
                if val is None:
                    validated_row.append(None)
                elif val < min_time or val > max_time:
                    logger.warning(f"异常时间值: {val:.1f}分钟 (范围: {min_time}-{max_time})")
                    validated_row.append(None)  # 替换为None
                    anomaly_count += 1
                else:
                    validated_row.append(float(val))
            validated.append(validated_row)
        
        # 构造POI ID列表（第0个为起点，ID=-1）
        poi_ids = [-1] + [poi.id for poi in cleaned_pois]
        
        time_matrix = TimeMatrix(
            matrix=validated,
            poi_ids=poi_ids
        )
        
        logger.info(f"✅ 时间矩阵校验完成，发现 {anomaly_count} 个异常值")
        return time_matrix