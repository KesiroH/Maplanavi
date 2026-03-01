# 运行时错误修复 Spec

## Why
`main.py` 运行时出现 `NameError: name 'llm_client' is not defined`，导致程序无法正常启动。需要修复主入口文件的初始化逻辑，并补充缺失的配置文件。

## What Changes
- **修复** `main.py`：添加 LLM 客户端初始化、配置文件加载、错误处理
- **新增** `config.yaml`：系统配置文件模板
- **新增** `.env.example`：环境变量配置示例
- **修复** `backup_pool` 初始化逻辑

## Impact
- Affected specs: 主入口文件、配置管理
- Affected code: `main.py`, `config.yaml`, `.env.example`

---

## ADDED Requirements

### Requirement: 主入口文件完整初始化
系统 SHALL 在启动时正确初始化所有依赖组件。

#### Scenario: LLM客户端初始化
- **WHEN** 程序启动
- **THEN** 从配置文件或环境变量加载 LLM 配置并初始化客户端

#### Scenario: 配置文件加载
- **WHEN** 配置文件存在
- **THEN** 加载配置；当配置文件不存在时，使用环境变量默认值

#### Scenario: 错误处理
- **WHEN** 初始化失败（如 API Key 无效）
- **THEN** 输出友好的错误提示并退出

### Requirement: 配置文件模板
系统 SHALL 提供配置文件模板。

#### Scenario: config.yaml
- **WHEN** 用户需要配置系统
- **THEN** 提供 YAML 格式的配置模板

#### Scenario: .env.example
- **WHEN** 用户需要设置环境变量
- **THEN** 提供环境变量示例文件

---

## MODIFIED Requirements

### Requirement: main.py 主流程
主入口文件 SHALL 包含完整的初始化流程：

```python
# 1. 加载配置
# 2. 初始化高德客户端
# 3. 初始化LLM客户端
# 4. 构建用户需求
# 5. POI筛选与评分
# 6. 路径规划
# 7. 动态调整（可选）
```
