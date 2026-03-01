# Tasks

## Task 1: 修复 main.py 主入口文件

- [x] Task 1.1: 添加配置加载逻辑
  - 创建 `load_config()` 函数
  - 支持从 `config.yaml` 加载配置
  - 支持从环境变量回退
  
- [x] Task 1.2: 添加 LLM 客户端初始化
  - 从配置中获取 LLM 参数
  - 初始化 `LLMConfigurator` 实例
  - 添加初始化失败的错误处理
  
- [x] Task 1.3: 添加完整的主流程
  - 用户需求构建
  - POI 筛选与评分
  - 路径规划
  - 结果输出
  
- [x] Task 1.4: 添加错误处理和日志
  - try-except 包裹主流程
  - 友好的错误提示
  - 详细的日志输出

## Task 2: 创建配置文件模板

- [x] Task 2.1: 创建 config.yaml
  - 高德 API 配置
  - LLM 配置（支持 OpenAI 和通义千问）
  - POI 筛选配置
  - 评分权重配置
  
- [x] Task 2.2: 创建 .env.example
  - AMAP_API_KEY
  - OPENAI_API_KEY / DASHSCOPE_API_KEY
  - LLM_TYPE, LLM_MODEL 等

## Task 3: 修复其他初始化问题

- [x] Task 3.1: 修复 backup_pool 初始化
  - 在 main.py 中定义 backup_pool
  - 或在 ItineraryAdjuster 中提供默认值
  
- [x] Task 3.2: 验证运行流程
  - 运行 main.py 确认无错误
  - 测试基本功能

---

# Task Dependencies

- [Task 1] 是核心修复，优先执行
- [Task 2] 与 [Task 1] 可并行
- [Task 3] 依赖 [Task 1] 完成后验证
