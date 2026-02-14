# Checklist

## Task 1: 高德API适配器重构

- [x] API Key不再硬编码，从环境变量或配置文件读取
- [x] GaodeMapClient接受AmapConfig配置对象
- [x] 环境变量AMAP_API_KEY支持已添加
- [x] CoordinateSystem枚举已创建（WGS84, GCJ02, BD09）
- [x] detect_coordinate_system()函数已实现
- [x] convert_coordinates()转换函数已实现
- [x] API调用前后自动进行坐标审查
- [x] AmapLocation Pydantic模型已创建
- [x] AmapRoute Pydantic模型已创建
- [x] AmapPOI Pydantic模型已创建
- [x] AmapDistance Pydantic模型已创建
- [x] 所有API方法返回Pydantic模型而非原始JSON
- [x] 使用tenacity实现指数退避重试
- [x] GaodeMapError异常层次结构完善
- [x] 请求/响应日志记录已添加

## Task 2: 用户需求构建器

- [x] StartPoint / EndPoint模型已创建
- [x] HardConstraints模型已创建
- [x] InterestPreference模型已创建
- [x] SoftPreferences模型已创建
- [x] UserDemandProfile聚合模型已创建
- [x] build_user_profile.py入口脚本已创建
- [x] 日期/时间输入验证已实现
- [x] 出发地选择功能已实现（地名搜索/坐标输入）
- [x] 类别偏好选择界面已实现
- [x] 自然语言偏好解析已实现（调用LLM）
- [x] poi_categories.json已集成
- [x] 层级选择界面已实现（大类→中类→小类）

## Task 3: 智能POI筛选与评分引擎

- [x] POICandidateFilter类已创建
- [x] 类别过滤已实现
- [x] 地理范围过滤已实现
- [x] 负面关键词过滤已实现
- [x] LLMScorer类已创建
- [x] POI特征提取Prompt已构造
- [x] 批量评分已实现
- [x] AmapPOIEnricher类已创建
- [x] POI详情查询已实现
- [x] API配额控制已实现（仅对Top N候选调用）
- [x] 缓存机制已实现
- [x] CompositeScorer类已创建
- [x] 距离衰减函数已实现
- [x] 加权综合评分公式已实现
- [x] CandidateList输出格式正确

## Task 4: 路径规划器

- [x] GeoClusterer类已创建
- [x] K-Means聚类已实现
- [x] 聚类中心计算已实现
- [x] TSPSolver类已创建
- [x] 贪心最近邻算法已实现
- [x] 组内/组间路径优化已实现
- [x] MultiModalRouter类已创建
- [x] 距离阈值判断逻辑已实现
- [x] 高德步行/骑行/驾车/公交API已集成
- [x] TimeValidator类已创建
- [x] 总时长校验已实现
- [x] 超时自动调整已实现

## Task 5: 动态调整功能

- [x] swap_poi()函数已创建
- [x] 备选池查询已实现（位置接近+类别相似）
- [x] 通勤时间重算已实现
- [x] skip_poi()函数已创建
- [x] 前后节点连接已实现
- [x] 后续时间戳更新已实现
- [x] ItineraryAdjuster类已创建
- [x] 统一调整接口已提供
- [x] 调整历史日志已记录

## 集成测试

- [x] 完整流程测试：用户输入 → 行程输出
- [x] 高德API配额监控正常
- [x] 错误场景处理正确（网络超时、API限流等）
- [x] 坐标转换准确性验证
