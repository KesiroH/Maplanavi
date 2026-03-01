# Checklist

## Task 1: 修复 main.py 主入口文件

- [x] load_config() 函数已创建
- [x] 支持从 config.yaml 加载配置
- [x] 支持从环境变量回退
- [x] LLMConfigurator 已正确初始化
- [x] llm_client 变量已定义
- [x] 主流程完整（用户需求 → POI筛选 → 路径规划 → 输出）
- [x] try-except 错误处理已添加
- [x] 友好的错误提示已添加
- [x] 详细的日志输出已添加

## Task 2: 创建配置文件模板

- [x] config.yaml 已创建
- [x] 高德 API 配置项已包含
- [x] LLM 配置项已包含（OpenAI/通义千问）
- [x] POI 筛选配置已包含
- [x] 评分权重配置已包含
- [x] .env.example 已创建
- [x] AMAP_API_KEY 环境变量示例已包含
- [x] OPENAI_API_KEY 环境变量示例已包含
- [x] LLM_TYPE, LLM_MODEL 环境变量示例已包含

## Task 3: 修复其他初始化问题

- [x] backup_pool 已正确初始化
- [x] main.py 运行无 NameError
- [x] 基本功能测试通过

## 集成验证

- [x] python main.py 可正常启动
- [x] 用户配置流程可正常完成
- [x] 无运行时错误
