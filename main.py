# 1. 初始化高德客户端
from gaodeapi import GaodeMapClient
client = GaodeMapClient()  # 从环境变量 AMAP_API_KEY 读取

# 2. 构建用户需求
from build_user_profile import UserProfileBuilder
builder = UserProfileBuilder()
profile = builder.build()  # 交互式配置

# 3. POI筛选与评分
from modules.poi_selector import POISelectionEngine
engine = POISelectionEngine(client, llm_client)
candidates = engine.select(profile, top_k=20)

# 4. 路径规划
from modules.route_planner import RoutePlanner
planner = RoutePlanner(client)
result = planner.plan(candidates, profile)

# 5. 动态调整
from modules.itinerary_adjuster import ItineraryAdjuster
adjuster = ItineraryAdjuster(client, backup_pool)
result = adjuster.skip(result, poi_id=123)