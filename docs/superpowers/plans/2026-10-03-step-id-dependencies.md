# Step ID Dependency Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将计划依赖从索引语义统一升级为 `step_id` 语义，同时保持执行数据流、调度顺序和 LLM 计划解析能力可用。

**Architecture:** 先用测试锁住“依赖声明应使用 step_id”这一新契约，再把 `SkillCall` / `ToolCall` 的 `depends_on` 切为字符串元组；随后同步迁移 `TaskManager`、`PlanValidator`、`MockPlanner`、`LLMPlanner` 和相关测试。调度内部允许基于 `step_id` 构图，但最终仍输出稳定、可复现的有序步骤列表。

**Tech Stack:** Python 3.11+, pytest, Ruff, dataclasses, 标准库 JSON。

---

### Task 1: 用失败测试锁住 step_id 依赖语义

**Files:**
- Modify: `tests/test_task_manager.py`
- Modify: `tests/test_plan_validator.py`
- Modify: `tests/test_llm_planner.py`
- Modify: `tests/test_planner.py`
- Modify: `tests/test_execution_dataflow.py`

- [ ] **Step 1: 写失败测试，要求 `depends_on` 使用 step_id 字符串而不是索引**
- [ ] **Step 2: 运行定向测试，确认先失败且失败原因正确**
- [ ] **Step 3: 写最小实现让这些测试转绿**
- [ ] **Step 4: 继续补边界测试，如非法 step_id、缺失依赖、循环依赖**

### Task 2: 迁移计划数据模型与调度器

**Files:**
- Modify: `src/robot_agent/planning/base.py`
- Modify: `src/robot_agent/runtime/task_manager.py`

- [ ] **Step 1: 将 `depends_on` 类型从 `tuple[int, ...]` 迁移到 `tuple[str, ...]`**
- [ ] **Step 2: 在 `TaskManager` 中基于 `step_id` 建图并做稳定拓扑排序**
- [ ] **Step 3: 保持无依赖步骤的稳定顺序不变**
- [ ] **Step 4: 为非法 / 重复 / 自依赖 / 缺失依赖保留清晰错误信息**

### Task 3: 迁移验证器与规划器

**Files:**
- Modify: `src/robot_agent/planning/validator.py`
- Modify: `src/robot_agent/planning/mock_planner.py`
- Modify: `src/robot_agent/planning/llm_planner.py`

- [ ] **Step 1: 让 `PlanValidator` 校验 `step_id` 依赖与 `OutputRef.step_id` 一致性**
- [ ] **Step 2: 让 `MockPlanner` 生成 `depends_on=("prev_step_id",)`**
- [ ] **Step 3: 让 `LLMPlanner._parse_plan()` 接受并生成 step_id 依赖列表**
- [ ] **Step 4: 保持现有 goal 对齐和 capability 校验逻辑不回退**

### Task 4: 全量验证

**Files:**
- Verify only

- [ ] **Step 1: 运行 `".venv/bin/ruff" check .`**
- [ ] **Step 2: 运行 `".venv/bin/ruff" format --check .`**
- [ ] **Step 3: 运行 `python -m pytest -q`**
- [ ] **Step 4: 运行 `".venv/bin/python" -m pytest --cov=robot_agent --cov-report=term-missing -q`**
- [ ] **Step 5: 汇报实际结果，不做未验证断言**
