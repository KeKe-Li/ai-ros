# Runtime 可靠性与工程门禁 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成实体解析、能力契约、不可变快照、完整审计、Memory/SSE 可靠性和工程门禁升级。

**Architecture:** 用 `EntityResolver` 与 `CapabilitySpec` 替代分散规则；用统一冻结/编码边界保证执行数据可追溯；用原子文件替换、有界队列和显式失败策略保证长期运行。工程配置只影响开发和构建，不增加核心运行时依赖。

**Tech Stack:** Python 3.11+、标准库、pytest、Ruff、GitHub Actions、Docker

---

### Task 1: 实体解析器

**Files:** `src/robot_agent/planning/entity_resolver.py`、`src/robot_agent/planning/goal.py`、`src/robot_agent/world/state.py`、`tests/test_entity_resolver.py`

- [x] 先写完整 ID、别名、子串误命中和歧义测试并确认失败。
- [x] 实现 EntityResolver 并接入 GoalSpec。
- [x] 运行目标与规划测试。

### Task 2: 统一能力契约

**Files:** `src/robot_agent/core/capabilities.py`、skills、tools、PlanValidator、LLMPlanner、相关测试。

- [x] 先写技能/工具参数类型、缺参、输出 schema 和动态 LLM 能力测试。
- [x] 实现 CapabilitySpec 并从注册表暴露。
- [x] 删除硬编码 LLM 白名单并重跑规划测试。

### Task 3: 深不可变与完整审计

**Files:** `src/robot_agent/core/frozen.py`、计划/结果/世界/事件/上下文/序列化模块、相关测试。

- [x] 先写嵌套修改隔离、JSON-safe 编码和 StepRecord 输出测试。
- [x] 实现冻结边界并扩展步骤审计字段。
- [x] 运行运行时、显示和 Web 测试。

### Task 4: Memory 与诊断策略

**Files:** Memory、AgentRuntime、LLMPlanner、事件类型和相关测试。

- [x] 先写序列化失败回滚、原子替换、损坏加载和 MemorySink 策略测试。
- [x] 实现原子持久化、失败策略和结构化诊断。
- [x] 运行 Memory 与异常测试。

### Task 5: SSE 背压与参数校验

**Files:** Web broadcaster/server、runtime/grid/terminal 构造器、相关测试。

- [x] 先写历史上限、慢消费者和非法配置测试。
- [x] 实现有界队列、丢弃计数与快速失败。
- [x] 运行 Web 和边界测试。

### Task 6: 工程门禁与完整验证

**Files:** `pyproject.toml`、`.github/workflows/ci.yml`、`Dockerfile`、README。

- [x] 增加 Ruff 配置、CI 矩阵、wheel 构建和非 root Docker。
- [x] 更新中英文文档。
- [x] 运行全量测试、覆盖率、demo、compileall、wheel 和 diff 检查。
