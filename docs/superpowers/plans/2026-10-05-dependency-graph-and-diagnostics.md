# Dependency Graph And Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 抽出共享依赖图逻辑，移除运行时对错误消息文本的阶段猜测，并为 observer 故障增加结构化 diagnostics，同时保持现有主链路行为和验证基线稳定。

**Architecture:** 先用测试锁住当前运行时和规划层对依赖图/阶段归因/observer 隔离的行为，再把依赖图构建与拓扑排序抽到共享模块，供 `TaskManager` 与 `PlanValidator` 复用；规划准备阶段改为抛出携带明确 stage 的异常；observer 异常继续隔离，但会写入 `RunReport.diagnostics`，不影响主执行成功与失败语义。

**Tech Stack:** Python 3.11+, pytest, Ruff, dataclasses, 标准库 typing/collections。

---

### Task 1: 用失败测试锁住三类目标行为

**Files:**
- Modify: `tests/test_task_manager.py`
- Modify: `tests/test_plan_validator.py`
- Modify: `tests/test_runtime_components.py`
- Modify: `tests/test_runtime_exceptions.py`

- [ ] **Step 1: 写失败测试，要求 `TaskManager` 与 `PlanValidator` 共享一致的依赖图语义**
- [ ] **Step 2: 写失败测试，要求规划阶段失败通过结构化 stage 归因，而不是靠字符串猜测**
- [ ] **Step 3: 写失败测试，要求 observer 异常被隔离且记录 diagnostics**
- [ ] **Step 4: 运行定向测试，确认先失败且失败原因符合预期**

### Task 2: 抽出依赖图共享组件

**Files:**
- Create: `src/robot_agent/planning/dependency_graph.py`
- Modify: `src/robot_agent/runtime/task_manager.py`
- Modify: `src/robot_agent/planning/validator.py`

- [ ] **Step 1: 提供按 `step_id` 建图、校验、拓扑排序的共享接口**
- [ ] **Step 2: 让 `TaskManager` 只消费共享拓扑结果，不再自己重复建图**
- [ ] **Step 3: 让 `PlanValidator` 复用相同的依赖合法性与循环检测逻辑**
- [ ] **Step 4: 保持错误信息和稳定顺序不退化**

### Task 3: 结构化规划阶段错误与 observer diagnostics

**Files:**
- Modify: `src/robot_agent/core/errors.py`
- Modify: `src/robot_agent/runtime/planner_pipeline.py`
- Modify: `src/robot_agent/runtime/agent_runtime.py`
- Modify: `src/robot_agent/runtime/hooks.py`

- [ ] **Step 1: 为规划阶段定义带 stage 语义的错误边界**
- [ ] **Step 2: 让 `RuntimePlanner.prepare()` 在 parse / plan / validate / schedule 失败时抛出对应阶段错误**
- [ ] **Step 3: 让 `AgentRuntime` 基于结构化 stage 生成失败报告，不再解析 message 文本**
- [ ] **Step 4: 让 observer 异常写入 diagnostics，但不改变任务终态与事件隔离行为**

### Task 4: 全量验证

**Files:**
- Verify only

- [ ] **Step 1: 运行 `".venv/bin/ruff" check .`**
- [ ] **Step 2: 运行 `".venv/bin/ruff" format --check .`**
- [ ] **Step 3: 运行 `python -m pytest -q`**
- [ ] **Step 4: 运行 `".venv/bin/python" -m pytest --cov=robot_agent --cov-report=term-missing -q`**
- [ ] **Step 5: 汇报实际结果，不做未验证断言**
