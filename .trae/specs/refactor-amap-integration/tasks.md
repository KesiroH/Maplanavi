# Tasks

## Task 1: 高德API适配器重构
重构 `gaodeapi/autoapi.py` 为健壮的服务层。

- [x] Task 1.1: 移除硬编码API Key，改为从环境变量/配置文件读取
  - 创建 `AmapConfig` Pydantic模型
  - 修改 `GaodeMapClient.__init__` 接受配置对象
  - 添加环境变量 `AMAP_API_KEY` 支持
  
- [x] Task 1.2: 添加坐标系审查与转换机制
  - 创建 `CoordinateSystem` 枚举（WGS84, GCJ02, BD09）
  - 实现 `detect_coordinate_system()` 函数
  - 实现 `convert_coordinates()` 转换函数（WGS84 ↔ GCJ02）
  - 在API调用前后自动进行坐标审查
  
- [x] Task 1.3: 定义Pydantic返回模型
  - 创建 `AmapLocation` 模型（经纬度、地址组件）
  - 创建 `AmapRoute` 模型（距离、时长、路径点）
  - 创建 `AmapPOI` 模型（ID、名称、类别、评分、坐标）
  - 创建 `AmapDistance` 模型（起点、终点、距离、时长）
  - 修改所有API方法返回Pydantic模型
  
- [x] Task 1.4: 增强错误处理与重试机制
  - 使用 `tenacity` 库实现指数退避重试
  - 完善 `GaodeMapError` 异常层次结构
  - 添加请求/响应日志记录

## Task 2: 用户需求构建器
创建交互式模块，生成标准化的 `user.json`。

- [x] Task 2.1: 定义用户需求数据模型
  - 创建 `StartPoint` / `EndPoint` 模型
  - 创建 `HardConstraints` 模型（日期、时长、交通方式、分布）
  - 创建 `InterestPreference` 模型（类型、约束级别、类别限制）
  - 创建 `SoftPreferences` 模型（节奏、预算、兴趣、负面关键词）
  - 创建 `UserDemandProfile` 聚合模型
  
- [x] Task 2.2: 实现交互式配置脚本
  - 创建 `build_user_profile.py` 入口脚本
  - 实现日期/时间输入验证
  - 实现出发地选择（支持地名搜索或坐标输入）
  - 实现类别偏好选择（基于 `poi_categories.json`）
  - 实现自然语言偏好解析（调用LLM）
  
- [x] Task 2.3: 集成poi_categories.json
  - 加载并解析类别映射表
  - 提供层级选择界面（大类→中类→小类）
  - 将选择结果转换为 `category_constraint` 格式

## Task 3: 智能POI筛选与评分引擎
从本地数据筛选候选池并进行综合评分。

- [x] Task 3.1: 本地POI初筛器
  - 创建 `POICandidateFilter` 类
  - 实现类别过滤（基于 `category_constraint`）
  - 实现地理范围过滤（基于起点距离）
  - 实现负面关键词过滤
  - 输出候选POI列表
  
- [x] Task 3.2: LLM语义评分器
  - 创建 `LLMScorer` 类
  - 构造POI特征提取Prompt
  - 实现批量评分（避免逐个调用）
  - 输出0-10相关性得分
  
- [x] Task 3.3: 高德实时数据获取
  - 创建 `AmapPOIEnricher` 类
  - 实现POI详情查询（评分、营业时间等）
  - 添加API配额控制（仅对Top N候选调用）
  - 实现缓存机制避免重复请求
  
- [x] Task 3.4: 综合评分算法
  - 创建 `CompositeScorer` 类
  - 实现距离衰减函数
  - 实现加权综合评分公式
  - 输出排序后的 `CandidateList`

## Task 4: 路径规划器
将候选POI串联成合理的多交通模式路线。

- [x] Task 4.1: 地理聚类模块
  - 创建 `GeoClusterer` 类
  - 实现K-Means聚类（按时段分组）
  - 实现聚类中心计算
  - 输出分组的POI集合
  
- [x] Task 4.2: TSP贪心排序
  - 创建 `TSPSolver` 类
  - 实现贪心最近邻算法
  - 实现组内/组间路径优化
  - 输出访问顺序列表
  
- [x] Task 4.3: 多模式通勤计算
  - 创建 `MultiModalRouter` 类
  - 实现距离阈值判断逻辑
  - 集成高德步行/骑行/驾车/公交API
  - 输出每段通勤的时长和距离
  
- [x] Task 4.4: 时间校验与调整
  - 创建 `TimeValidator` 类
  - 实现总时长校验
  - 实现超时自动调整（删除低优先级POI）
  - 输出最终行程时间表

## Task 5: 动态调整功能
支持行程的实时微调。

- [x] Task 5.1: POI替换功能
  - 创建 `swap_poi()` 函数
  - 实现备选池查询（位置接近+类别相似）
  - 实现通勤时间重算
  - 输出更新后的行程
  
- [x] Task 5.2: POI删除功能
  - 创建 `skip_poi()` 函数
  - 实现前后节点连接
  - 实现后续时间戳更新
  - 输出更新后的行程
  
- [x] Task 5.3: 行程调整API
  - 创建 `ItineraryAdjuster` 类
  - 提供统一的调整接口
  - 记录调整历史日志

---

# Task Dependencies

- [Task 1] 是基础，其他任务依赖其API服务层
- [Task 2] 独立，可与Task 1并行
- [Task 3] 依赖 [Task 1.3]（Pydantic模型）和 [Task 2.1]（用户需求模型）
- [Task 4] 依赖 [Task 3]（候选POI列表）
- [Task 5] 依赖 [Task 4]（完整行程）

## 可并行执行的任务
- Task 1.1, 1.2, 1.3, 1.4 可并行
- Task 2.1, 2.2, 2.3 可并行
- Task 3.1, 3.2 可并行（独立于高德API）
- Task 5.1, 5.2 可并行
