"""
智能行程规划主入口
==================

完整流程:
1. 加载配置
2. 初始化高德客户端
3. 初始化LLM客户端
4. 构建用户需求（调用 UserProfileBuilder）
5. POI筛选与评分（调用 POISelectionEngine）
6. 路径规划（调用 RoutePlanner）
7. 结果输出
"""

import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from gaodeapi import GaodeMapClient
from build_user_profile import UserProfileBuilder
from modules.poi_selector import POISelectionEngine
from modules.route_planner import RoutePlanner
from modules.itinerary_adjuster import ItineraryAdjuster
from modules.llm_configurator import LLMConfigurator
from common.exceptions import InsufficientPOIError
from common.logger import setup_logger

setup_logger('maplanavi', level=logging.INFO)
logger = logging.getLogger('maplanavi')


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    加载配置文件
    
    优先级:
    1. 指定的配置文件路径
    2. 当前目录下的 config.yaml
    3. 环境变量
    
    Args:
        config_path: 配置文件路径（可选）
    
    Returns:
        配置字典
    """
    llm_api_key = (
        os.getenv('LLM_API_KEY') or 
        os.getenv('VOLCENGINE_API_KEY') or 
        os.getenv('ARK_API_KEY') or  # 火山方舟官网使用的环境变量名
        os.getenv('OPENAI_API_KEY') or 
        os.getenv('DASHSCOPE_API_KEY') or 
        ''
    )
    
    llm_type = os.getenv('LLM_TYPE', 'volcengine')
    if llm_type not in ('openai', 'tongyi', 'volcengine', 'doubao', 'ark'):
        if os.getenv('VOLCENGINE_API_KEY'):
            llm_type = 'volcengine'
        elif os.getenv('OPENAI_API_KEY'):
            llm_type = 'openai'
        elif os.getenv('DASHSCOPE_API_KEY'):
            llm_type = 'tongyi'
    
    config = {
        'amap': {
            'api_key': os.getenv('AMAP_API_KEY', '')
        },
        'llm': {
            'type': llm_type,
            'api_key': llm_api_key,
            'model': os.getenv('LLM_MODEL', 'doubao-1.5-pro-32k'),
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
        logger.info(f"从配置文件加载: {config_path}")
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                file_config = yaml.safe_load(f)
                if file_config:
                    config = _deep_merge(config, file_config)
        except ImportError:
            logger.warning("未安装 PyYAML，跳过 YAML 配置文件加载")
        except Exception as e:
            logger.warning(f"加载配置文件失败: {e}")
    
    default_config_path = Path(__file__).parent / 'config.yaml'
    if default_config_path.exists():
        logger.info(f"从默认配置文件加载: {default_config_path}")
        try:
            import yaml
            with open(default_config_path, 'r', encoding='utf-8') as f:
                file_config = yaml.safe_load(f)
                if file_config:
                    config = _deep_merge(config, file_config)
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"加载默认配置文件失败: {e}")
    
    return config


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """深度合并两个字典"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def init_amap_client(config: Dict[str, Any]) -> GaodeMapClient:
    """
    初始化高德地图客户端
    
    Args:
        config: 配置字典
    
    Returns:
        GaodeMapClient 实例
    
    Raises:
        ValueError: API Key 未配置
    """
    api_key = config.get('amap', {}).get('api_key', '')
    
    if not api_key:
        api_key = os.getenv('AMAP_API_KEY', '')
    
    if not api_key:
        raise ValueError(
            "高德地图 API Key 未配置！\n"
            "请通过以下方式之一配置:\n"
            "  1. 设置环境变量: AMAP_API_KEY=your_key\n"
            "  2. 在 config.yaml 中配置 amap.api_key"
        )
    
    client = GaodeMapClient(api_key=api_key)
    logger.info("✅ 高德地图客户端初始化成功")
    return client


def init_llm_client(config: Dict[str, Any]) -> Optional[LLMConfigurator]:
    """
    初始化 LLM 客户端
    
    Args:
        config: 配置字典
    
    Returns:
        LLMConfigurator 实例，如果配置不完整则返回 None
    """
    llm_config = config.get('llm', {})
    
    api_key = llm_config.get('api_key', '') or os.getenv('LLM_API_KEY', '')
    
    if not api_key:
        logger.warning(
            "⚠️ LLM API Key 未配置，将跳过 LLM 评分功能\n"
            "请通过以下方式之一配置:\n"
            "  1. 设置环境变量: LLM_API_KEY=your_key\n"
            "  2. 在 config.yaml 中配置 llm.api_key"
        )
        return None
    
    full_config = {
        'type': llm_config.get('type', 'openai'),
        'api_key': api_key,
        'model': llm_config.get('model', 'gpt-4o'),
        'base_url': llm_config.get('base_url'),
        'temperature': llm_config.get('temperature', 0.3),
        'max_tokens': llm_config.get('max_tokens', 2000),
        'retry': llm_config.get('retry', 2)
    }
    
    try:
        client = LLMConfigurator(full_config)
        logger.info(f"✅ LLM 客户端初始化成功: {full_config['type']} / {full_config['model']}")
        return client
    except Exception as e:
        logger.error(f"❌ LLM 客户端初始化失败: {e}")
        return None


def output_result(result, profile, output_format: str = 'text'):
    """
    输出规划结果
    
    Args:
        result: RoutePlanResult 对象
        profile: UserDemandProfile 对象
        output_format: 输出格式 ('text', 'json')
    """
    if output_format == 'json':
        output_data = {
            'status': 'success',
            'total_pois': len(result.pois),
            'total_distance_m': result.total_distance_m,
            'total_duration_min': result.total_duration_min,
            'total_stay_min': result.total_stay_min,
            'is_valid': result.is_valid,
            'pois': [
                {
                    'name': poi.get('name', ''),
                    'category': poi.get('type', ''),
                    'address': poi.get('address', ''),
                    'score': poi.get('composite_score', 0),
                    'rank': poi.get('rank', 0)
                }
                for poi in result.pois
            ],
            'time_schedule': result.time_schedule
        }
        print(json.dumps(output_data, ensure_ascii=False, indent=2))
    else:
        print("\n" + "=" * 60)
        print("           🗺️ 智能行程规划结果")
        print("=" * 60)
        
        print(f"\n📅 出行日期: {profile.hard_constraints.date}")
        print(f"📍 出发地: {profile.hard_constraints.start_point.name}")
        print(f"🚗 交通方式: {profile.hard_constraints.transport_mode}")
        
        print(f"\n📊 行程概览:")
        print(f"   - POI 数量: {len(result.pois)} 个")
        print(f"   - 总路程: {result.total_distance_m / 1000:.1f} 公里")
        print(f"   - 通勤时间: {result.total_duration_min:.0f} 分钟")
        print(f"   - 游玩时间: {result.total_stay_min:.0f} 分钟")
        print(f"   - 时间校验: {'✅ 合理' if result.is_valid else '⚠️ 需调整'}")
        
        print(f"\n📋 详细行程:")
        for i, (poi, schedule) in enumerate(zip(result.pois, result.time_schedule), 1):
            print(f"\n   【{i}】{poi.get('name', 'Unknown')}")
            print(f"       类型: {poi.get('type', 'N/A')}")
            print(f"       时间: {schedule['arrival_time']} - {schedule['departure_time']}")
            print(f"       停留: {schedule['stay_time_min']} 分钟")
            if schedule['travel_time_min'] > 0:
                print(f"       前往此处: {schedule['travel_time_min']:.0f} 分钟")
            print(f"       评分: {poi.get('composite_score', 0):.1f}")
        
        print("\n" + "=" * 60)


def main():
    """主流程入口"""
    print("=" * 60)
    print("       🎯 智能行程规划系统")
    print("=" * 60)
    
    try:
        logger.info("步骤 1/6: 加载配置...")
        config = load_config()
        
        logger.info("步骤 2/6: 初始化高德地图客户端...")
        amap_client = init_amap_client(config)
        
        logger.info("步骤 3/6: 初始化 LLM 客户端...")
        llm_client = init_llm_client(config)
        
        logger.info("步骤 4/6: 构建用户需求...")
        builder = UserProfileBuilder()
        profile = builder.build()
        
        builder.preview()
        
        confirm = input("\n确认开始规划行程? (y/n): ").strip().lower()
        if confirm != 'y':
            print("已取消规划")
            return
        
        builder.save()
        
        logger.info("步骤 5/6: POI 筛选与评分...")
        base_dir = Path(__file__).parent
        poi_data_path = str(base_dir / config['poi']['data_path'])
        categories_path = str(base_dir / config['poi']['categories_path'])
        
        engine = POISelectionEngine(
            poi_data_path=poi_data_path,
            categories_path=categories_path,
            llm_client=llm_client,
            amap_client=amap_client
        )
        
        candidates = engine.select_pois(
            user_profile=profile,
            use_llm=llm_client is not None,
            use_amap=True,
            top_k=20
        )
        
        if not candidates:
            logger.error("未找到符合条件的 POI，请调整筛选条件")
            return
        
        logger.info(f"筛选完成，共 {len(candidates)} 个候选 POI")
        
        logger.info("步骤 6/6: 路径规划...")
        planner = RoutePlanner(amap_client=amap_client)
        
        start_point = tuple(profile.hard_constraints.start_point.location)
        
        result = planner.plan(
            pois=candidates[:10],
            start_point=start_point,
            distribution=profile.hard_constraints.distribution.model_dump(),
            start_time="08:00"
        )
        
        output_result(result, profile, output_format='text')
        
        backup_pool = candidates[10:20] if len(candidates) > 10 else []
        if backup_pool:
            logger.info(f"备选 POI 池: {len(backup_pool)} 个")
        
        itinerary = {
            'pois': result.pois,
            'routes': result.routes,
            'time_slots': {}
        }
        
        adjuster = ItineraryAdjuster(amap_client, backup_pool)
        
        print("\n💡 提示: 可以使用 ItineraryAdjuster 进行动态调整")
        print("   - adjuster.skip(itinerary, poi_id)  # 删除 POI")
        print("   - adjuster.swap(itinerary, poi_id)  # 替换 POI")
        print("   - adjuster.insert(itinerary, poi, position)  # 插入 POI")
        
        logger.info("✅ 行程规划完成！")
        
    except ValueError as e:
        logger.error(f"配置错误: {e}")
        sys.exit(1)
    except InsufficientPOIError as e:
        logger.error(f"POI数量不足: {e.message}")
        logger.info("💡 建议：请放宽筛选条件，增加搜索范围或减少时段要求")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户取消操作")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ 行程规划失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
