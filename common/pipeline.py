"""
智能行程规划管道
================

封装完整的AI驱动旅行规划流程。
"""

from __future__ import annotations
import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from gaodeapi import GaodeMapClient
from modules.llm_configurator import LLMConfigurator
from modules.poi_selector import POISelectionEngine
from modules.route_planner import RoutePlanner
from modules.itinerary_adjuster import ItineraryAdjuster
from modules.user_profile_models import UserDemandProfile

from .models import BaseResponse, GeoPoint

logger = logging.getLogger(__name__)


class MaplanaviPipeline:
    """
    智能行程规划管道
    
    封装完整的AI驱动旅行规划流程:
    1. 配置加载与初始化
    2. 构建用户需求
    3. POI筛选与评分
    4. 路径规划
    5. 结果输出
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化规划管道
        
        Args:
            config_path: 配置文件路径（可选）
        """
        self.config: Dict[str, Any] = {}
        self.amap_client: Optional[GaodeMapClient] = None
        self.llm_client: Optional[LLMConfigurator] = None
        self.poi_engine: Optional[POISelectionEngine] = None
        self.route_planner: Optional[RoutePlanner] = None
        self.itinerary_adjuster: Optional[ItineraryAdjuster] = None
        self.user_profile: Optional[UserDemandProfile] = None
        self.candidates: List[Dict] = []
        self.route_result: Optional[Any] = None
        
        self._load_config(config_path)
        self._init_clients()
    
    def _load_config(self, config_path: Optional[str] = None) -> None:
        """加载配置"""
        logger.info("步骤 1/6: 加载配置...")
        
        llm_api_key = (
            os.getenv('LLM_API_KEY') or 
            os.getenv('VOLCENGINE_API_KEY') or 
            os.getenv('ARK_API_KEY') or
            os.getenv('OPENAI_API_KEY') or 
            os.getenv('DASHSCOPE_API_KEY') or 
            ''
        )
        
        llm_type = os.getenv('LLM_TYPE', 'volcengine')
        
        self.config = {
            'amap': {
                'api_key': os.getenv('AMAP_API_KEY', '')
            },
            'llm': {
                'type': llm_type,
                'api_key': llm_api_key,
                'model': os.getenv('LLM_MODEL', 'doubao-seed-2-0-mini-260215'),
                'base_url': os.getenv('LLM_BASE_URL', None),
                'temperature': float(os.getenv('LLM_TEMPERATURE', '0.3')),
                'max_tokens': int(os.getenv('LLM_MAX_TOKENS', '2000')),
                'retry': int(os.getenv('LLM_RETRY', '2')),
                'thinking_enabled': os.getenv('THINKING_ENABLED', 'false').lower() == 'true'
            },
            'poi': {
                'data_path': 'haidian_poi.json',
                'categories_path': 'poi_categories.json'
            }
        }
        
        if config_path and Path(config_path).exists():
            self._merge_config(config_path)
        else:
            default_path = Path(__file__).parent / 'config.yaml'
            if default_path.exists():
                self._merge_config(str(default_path))
        
        logger.info("配置加载完成")
    
    def _merge_config(self, config_path: str) -> None:
        """合并配置文件"""
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                file_config = yaml.safe_load(f)
                if file_config:
                    self._deep_merge(self.config, file_config)
        except ImportError:
            logger.warning("未安装 PyYAML，跳过 YAML 配置文件加载")
        except Exception as e:
            logger.warning(f"加载配置文件失败: {e}")
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """深度合并字典"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    def _init_clients(self) -> None:
        """初始化客户端"""
        self._init_amap_client()
        self._init_llm_client()
    
    def _init_amap_client(self) -> None:
        """初始化高德地图客户端"""
        logger.info("步骤 2/6: 初始化高德地图客户端...")
        
        api_key = self.config.get('amap', {}).get('api_key', '')
        if not api_key:
            api_key = os.getenv('AMAP_API_KEY', '')
        
        if not api_key:
            logger.warning("高德地图 API Key 未配置，将使用受限功能")
            return
        
        self.amap_client = GaodeMapClient(api_key=api_key)
        logger.info("✅ 高德地图客户端初始化成功")
    
    def _init_llm_client(self) -> None:
        """初始化LLM客户端"""
        logger.info("步骤 3/6: 初始化 LLM 客户端...")
        
        llm_config = self.config.get('llm', {})
        api_key = llm_config.get('api_key', '')
        
        if not api_key:
            logger.warning("⚠️ LLM API Key 未配置，将跳过 LLM 评分功能")
            self.llm_client = None
            return
        
        try:
            full_config = {
                'type': llm_config.get('type', 'volcengine'),
                'api_key': api_key,
                'model': llm_config.get('model', 'doubao-seed-2-0-mini-260215'),
                'base_url': llm_config.get('base_url'),
                'temperature': llm_config.get('temperature', 0.3),
                'max_tokens': llm_config.get('max_tokens', 2000),
                'retry': llm_config.get('retry', 2),
                'thinking_enabled': llm_config.get('thinking_enabled', False)
            }
            self.llm_client = LLMConfigurator(full_config)
            logger.info(f"✅ LLM 客户端初始化成功: {full_config['type']} / {full_config['model']}")
        except Exception as e:
            logger.error(f"❌ LLM 客户端初始化失败: {e}")
            self.llm_client = None
    
    def build_user_profile(self) -> UserDemandProfile:
        """
        构建用户需求配置
        
        Returns:
            UserDemandProfile: 用户需求配置对象
        """
        logger.info("步骤 4/6: 构建用户需求...")
        
        from build_user_profile import UserProfileBuilder
        
        builder = UserProfileBuilder()
        self.user_profile = builder.build()
        builder.preview()
        
        confirm = input("\n确认开始规划行程? (y/n): ").strip().lower()
        if confirm != 'y':
            print("已取消规划")
            sys.exit(0)
        
        builder.save()
        
        return self.user_profile
    
    def select_pois(self, top_k: int = 20) -> List[Dict]:
        """
        POI筛选与评分
        
        Args:
            top_k: 返回的候选POI数量
            
        Returns:
            候选POI列表
        """
        if not self.user_profile:
            raise ValueError("请先调用 build_user_profile() 构建用户需求")
        
        logger.info("步骤 5/6: POI 筛选与评分...")
        
        base_dir = Path(__file__).parent
        poi_data_path = str(base_dir / self.config['poi']['data_path'])
        categories_path = str(base_dir / self.config['poi']['categories_path'])
        
        self.poi_engine = POISelectionEngine(
            poi_data_path=poi_data_path,
            categories_path=categories_path,
            llm_client=self.llm_client,
            amap_client=self.amap_client
        )
        
        self.candidates = self.poi_engine.select_pois(
            user_profile=self.user_profile,
            use_llm=self.llm_client is not None,
            use_amap=self.amap_client is not None,
            top_k=top_k
        )
        
        if not self.candidates:
            raise ValueError("未找到符合条件的 POI，请调整筛选条件")
        
        logger.info(f"筛选完成，共 {len(self.candidates)} 个候选 POI")
        
        return self.candidates
    
    def plan_route(self, max_pois: int = 10, start_time: str = "08:00") -> Any:
        """
        路径规划
        
        Args:
            max_pois: 使用的POI数量
            start_time: 开始时间
            
        Returns:
            路径规划结果
        """
        if not self.candidates:
            raise ValueError("请先调用 select_pois() 进行POI筛选")
        
        logger.info("步骤 6/6: 路径规划...")
        
        self.route_planner = RoutePlanner(amap_client=self.amap_client)
        
        start_point = tuple(self.user_profile.hard_constraints.start_point.location)
        
        self.route_result = self.route_planner.plan(
            pois=self.candidates[:max_pois],
            start_point=start_point,
            distribution=self.user_profile.hard_constraints.distribution.model_dump(),
            start_time=start_time
        )
        
        return self.route_result
    
    def get_adjuster(self) -> ItineraryAdjuster:
        """
        获取行程调整器
        
        Returns:
            ItineraryAdjuster: 行程调整器实例
        """
        backup_pool = self.candidates[max_pois:20] if len(self.candidates) > 10 else []
        self.itinerary_adjuster = ItineraryAdjuster(self.amap_client, backup_pool)
        
        return self.itinerary_adjuster
    
    def run(self) -> BaseResponse:
        """
        运行完整流程
        
        Returns:
            BaseResponse: 执行结果
        """
        try:
            self.build_user_profile()
            self.select_pois()
            self.plan_route()
            
            return BaseResponse.ok("行程规划完成", {
                'poi_count': len(self.route_result.pois),
                'total_distance': self.route_result.total_distance_m,
                'total_duration': self.route_result.total_duration_min
            })
            
        except Exception as e:
            logger.error(f"行程规划失败: {e}", exc_info=True)
            return BaseResponse.error(str(e))


def main():
    """主入口"""
    print("=" * 60)
    print("       🎯 智能行程规划系统")
    print("=" * 60)
    
    pipeline = MaplanaviPipeline()
    result = pipeline.run()
    
    if result.success:
        print("\n✅ 行程规划完成！")
    else:
        print(f"\n❌ 规划失败: {result.message}")


if __name__ == "__main__":
    main()
