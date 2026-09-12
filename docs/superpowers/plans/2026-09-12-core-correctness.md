# 核心正确性第一轮优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复目标实体误选、放置后置条件假阳性和运行时阶段异常逃逸，并以回归测试锁定行为。

**Architecture:** 保持现有模块边界，只增强 `planning.goal` 的确定性实体解析、扩展 `Skill` 后置条件契约，并让 `AgentRuntime` 统一收敛阶段错误。第二轮的感知结果数据流与完整计划安全策略不在本计划范围内。

**Tech Stack:** Python 3.11+、dataclasses、pytest、pytest-cov

---

### Task 1: 目标实体解析

**Files:**
- Modify: `src/robot_agent/planning/goal.py`
- Test: `tests/test_goal.py`

- [x] 编写明确容器 ID、明确物体 ID和多候选歧义测试。
- [x] 运行 `pytest tests/test_goal.py -q`，确认新测试因当前首项选择行为失败。
- [x] 实现 ID 优先、唯一候选回退和歧义拒绝。
- [x] 重跑 `pytest tests/test_goal.py -q`，确认通过。

### Task 2: 放置后置条件契约

**Files:**
- Modify: `src/robot_agent/skills/base.py`
- Modify: `src/robot_agent/skills/navigation.py`
- Modify: `src/robot_agent/skills/manipulation.py`
- Modify: `src/robot_agent/runtime/monitor.py`
- Modify: `src/robot_agent/runtime/agent_runtime.py`
- Test: `tests/test_skills.py`
- Test: `tests/test_monitor_recovery.py`

- [x] 编写容器已有其它物体但目标未放入时必须失败的测试。
- [x] 运行最小测试，确认当前实现产生假阳性。
- [x] 扩展后置条件接口并更新所有实现与调用点。
- [x] 验证正确放置仍通过、错误放置被拒绝。

### Task 3: 运行时阶段异常边界

**Files:**
- Modify: `src/robot_agent/runtime/agent_runtime.py`
- Test: `tests/test_runtime_exceptions.py`

- [x] 编写目标解析、规划、调度、重规划和目标验证异常测试。
- [x] 运行测试并确认异常当前会逃出 `run()`。
- [x] 实现统一失败收敛与终态事件发送。
- [x] 重跑运行时异常测试并确认通过。

### Task 4: 回归验证与文档同步

**Files:**
- Modify if needed: `README.md`
- Modify if needed: `README.zh-CN.md`

- [x] 运行 `pytest -q`。
- [x] 运行 `pytest --cov=robot_agent --cov-report=term-missing -q`。
- [x] 运行 `python -m robot_agent.cli demo --verbose`。
- [x] 检查 `git diff --check` 和最终 diff，确认没有范围外修改。
