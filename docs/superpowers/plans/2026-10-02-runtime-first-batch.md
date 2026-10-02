# Runtime First Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变 CLI 与主链路外部行为的前提下，拆薄 `AgentRuntime` 内部职责，并移除 `WebMonitor` 对 runtime 主线程的阻塞式节流。

**Architecture:** 先用回归测试锁住当前运行时的可观测行为，再把 runtime 中的“规划准备”“单步执行/重试”“副作用 hooks”拆到独立模块，由 `AgentRuntime` 保留主编排职责。Web 侧保留现有 API 与演示语义，但将 `min_interval` 从 `on_event()` 的同步 `sleep` 改为内部缓冲/后台发布，避免显示层影响 runtime 执行节奏。

**Tech Stack:** Python 3.11+, pytest, Ruff, 标准库 threading/queue/dataclasses。

---

### Task 1: 用回归测试锁住 runtime 与 web 行为

**Files:**
- Modify: `tests/test_runtime_exceptions.py`
- Modify: `tests/test_monitor_recovery.py`
- Modify: `tests/test_web_display.py`

- [ ] **Step 1: 写失败测试，覆盖 runtime 拆分后的关键不变量**
- [ ] **Step 2: 单测运行确认它们先失败，且失败原因符合预期**
- [ ] **Step 3: 写最小实现通过这些测试**
- [ ] **Step 4: 重新运行定向测试，确认转绿**

### Task 2: 抽出 runtime hooks / planner pipeline / step executor

**Files:**
- Create: `src/robot_agent/runtime/hooks.py`
- Create: `src/robot_agent/runtime/planner_pipeline.py`
- Create: `src/robot_agent/runtime/step_executor.py`
- Modify: `src/robot_agent/runtime/agent_runtime.py`
- Modify: `src/robot_agent/runtime/__init__.py`

- [ ] **Step 1: 创建最小测试所需接口骨架**
- [ ] **Step 2: 将 `_remember` / `_emit` / diagnostics 累积迁入 hooks**
- [ ] **Step 3: 将 goal parse + plan + validate + schedule 迁入 planner pipeline**
- [ ] **Step 4: 将 `_try_step` / `_run_with_retry` 迁入 step executor**
- [ ] **Step 5: 保持 `RunReport`、事件顺序、trace 语义不变**

### Task 3: 将 WebMonitor 节流改为非阻塞

**Files:**
- Modify: `src/robot_agent/display/web/server.py`
- Modify: `tests/test_web_display.py`

- [ ] **Step 1: 写失败测试，证明 `on_event()` 不应被 `min_interval` 阻塞**
- [ ] **Step 2: 运行该测试并确认先失败**
- [ ] **Step 3: 用后台发布或缓冲机制做最小改造**
- [ ] **Step 4: 跑 web 相关测试确认保持原有回放/广播语义**

### Task 4: 全量验证

**Files:**
- Verify only

- [ ] **Step 1: 运行 `".venv/bin/ruff" check .`**
- [ ] **Step 2: 运行 `".venv/bin/ruff" format --check .`**
- [ ] **Step 3: 运行 `python -m pytest -q`**
- [ ] **Step 4: 如核心语义改动较大，再跑 coverage 命令**
- [ ] **Step 5: 汇报实际结果，不做未验证断言**
