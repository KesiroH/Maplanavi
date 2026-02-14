# 高德地图API集成与行程规划系统重构 Spec

## Why
当前系统基于OSM/OSRM，存在数据时效性差、国内POI覆盖不全的问题。需要引入高德地图API提升数据质量，同时重构用户需求层和路径规划算法，实现更智能的个性化旅行规划。

## What Changes
- **重构** `gaodeapi/autoapi.py`：移除硬编码Key，添加坐标审查机制，定义Pydantic返回模型
- **新增** 用户需求构建器模块：生成交互式用户配置文件
- **新增** 智能POI筛选与评分引擎：结合LLM语义评分与高德实时数据
- **新增** 路径规划器：支持多交通模式、聚类分组、TSP排序
- **新增** 动态调整功能：支持POI替换与删除
- **BREAKING** 数据流从OSM优先改为高德优先，需更新配置结构

## Impact
- Affected specs: POI获取、行程规划、用户交互
- Affected code: `gaodeapi/autoapi.py`, `modules/basic_itinerary_planner.py`, `modules/poi_road_network_fetcher.py`

---

## ADDED Requirements

### Requirement: 高德API服务层重构
系统 SHALL 提供安全、健壮的高德地图API服务层。

#### Scenario: API Key安全读取
- **WHEN** 初始化GaodeMapClient
- **THEN** API Key从环境变量或config.yaml读取，不硬编码

#### Scenario: 坐标系审查
- **WHEN** 调用高德API获取坐标
- **THEN** 系统自动检测坐标系类型（GCJ-02/WGS-84），必要时进行转换

#### Scenario: 错误处理与重试
- **WHEN** API调用失败
- **THEN** 系统捕获异常，执行重试机制，返回结构化错误信息

#### Scenario: Pydantic模型返回
- **WHEN** 调用路径规划/POI搜索接口
- **THEN** 返回类型化的Pydantic模型（AmapRoute, AmapPOI），非原始JSON

---

### Requirement: 用户需求构建器
系统 SHALL 提供交互式用户需求收集模块，生成标准化的user.json。

#### Scenario: 硬约束收集
- **WHEN** 用户输入日期、出发地、时长、预算、出行方式
- **THEN** 系统生成UserDemandProfile模型的hard_constraints字段

#### Scenario: 游玩节奏配置
- **WHEN** 用户设置上午/下午/晚上的POI数量分布
- **THEN** 系统生成distribution字段（如 {"morning": 2, "afternoon": 2, "evening": 1}）

#### Scenario: 软约束偏好
- **WHEN** 用户选择偏好类别或输入自然语言描述
- **THEN** 系统解析为interests列表和negative_keywords

---

### Requirement: 智能POI筛选与评分引擎
系统 SHALL 从本地POI数据库中筛选候选池并进行综合评分。

#### Scenario: 本地初筛
- **WHEN** 根据用户类别偏好和时间约束
- **THEN** 系统从haidian_poi.json提取候选POI，不调用高德API

#### Scenario: LLM语义评分
- **WHEN** 提取POI的tags和name
- **THEN** LLM输出0-10的相关性得分

#### Scenario: 综合评分计算
- **WHEN** 计算最终得分
- **THEN** 使用公式: Final_Score = w1 * LLM_Relevance + w2 * (Amap_Rating/5.0) + w3 * Distance_Decay

#### Scenario: API配额控制
- **WHEN** 筛选候选POI
- **THEN** 仅对最终几十个候选点调用高德API获取实时详情

---

### Requirement: 路径规划器
系统 SHALL 将候选POI串联成合理的多交通模式路线。

#### Scenario: 地理聚类
- **WHEN** 用户设置游玩节奏
- **THEN** 使用K-Means或简单聚类将POI按时段分组

#### Scenario: TSP排序
- **WHEN** 组内POI需要排序
- **THEN** 使用贪心算法确定访问顺序

#### Scenario: 多模式通勤
- **WHEN** 计算点对点通勤
- **THEN** 根据距离自动选择：(<1km步行, 1-5km骑行/公交, >5km驾车)

#### Scenario: 时间校验
- **WHEN** 生成行程
- **THEN** 确保"通勤时间+游玩时间"不超过用户设定的时限

---

### Requirement: 动态调整功能
系统 SHALL 支持行程的实时微调。

#### Scenario: POI替换
- **WHEN** 用户请求替换某个POI
- **THEN** 从备选池中寻找地理位置接近且类别相似的POI，重新计算通勤时间

#### Scenario: POI删除
- **WHEN** 用户删除某个POI
- **THEN** 自动连接前后节点，重新计算时间并更新后续时间戳

---

## MODIFIED Requirements

### Requirement: 配置文件结构
配置文件 SHALL 支持高德API配置项。

```yaml
amap:
  api_key: ${AMAP_API_KEY}  # 环境变量引用
  timeout: 10
  max_retries: 3
  
user_profile:
  path: "modules/user.json"
  
scoring:
  weights:
    llm_relevance: 0.5
    amap_rating: 0.3
    distance_decay: 0.2
```

---

## REMOVED Requirements

### Requirement: OSM优先数据获取
**Reason**: 高德API提供更准确的国内POI数据
**Migration**: 保留OSM作为备用数据源，但默认使用高德
