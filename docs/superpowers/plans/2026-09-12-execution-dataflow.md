# 执行数据流与计划安全 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立统一步骤输出数据流、计划执行前验证和只读工具执行能力，使感知结果能够安全驱动后续动作。

**Architecture:** 在计划模型中加入稳定步骤 ID、工具步骤和结构化输出引用；由 `ExecutionContext` 解析运行时数据，由 `PlanValidator` 在执行前阻止无效或偏离目标的计划。运行时统一执行技能与工具，但只有技能能够改变世界。

**Tech Stack:** Python 3.11+、dataclasses、pytest、标准库

---

### Task 1: 计划模型与执行上下文

**Files:**
- Modify: `src/robot_agent/planning/base.py`
- Create: `src/robot_agent/runtime/context.py`
- Modify: `src/robot_agent/core/errors.py`
- Test: `tests/test_execution_context.py`

- [x] 编写输出引用解析、嵌套路径、预期值和错误路径测试。
- [x] 运行测试并确认缺少实现。
- [x] 实现 `OutputRef`、`ToolCall`、`PlanStep` 与 `ExecutionContext`。
- [x] 重跑最小测试。

### Task 2: 计划验证器

**Files:**
- Create: `src/robot_agent/planning/validator.py`
- Modify: `src/robot_agent/runtime/agent_runtime.py`
- Test: `tests/test_plan_validator.py`

- [x] 编写合法计划、重复 ID、非法引用、缺参、未知能力和目标偏离测试。
- [x] 运行测试并确认缺少实现。
- [x] 实现 `PlanValidator` 并接入每次调度前。
- [x] 重跑验证器测试。

### Task 3: 感知结果驱动抓取

**Files:**
- Modify: `src/robot_agent/planning/mock_planner.py`
- Modify: `src/robot_agent/backends/sim_backend.py`
- Modify: `src/robot_agent/skills/perception.py`
- Modify: `src/robot_agent/runtime/agent_runtime.py`
- Test: `tests/test_planner.py`
- Test: `tests/test_skills.py`
- Test: `tests/test_execution_dataflow.py`

- [x] 编写规则计划引用与错误检测结果阻止抓取的测试。
- [x] 运行测试并确认旧运行时仍忽略检测输出。
- [x] 记录成功步骤输出、解析后续参数并增强检测后置条件。
- [x] 重跑相关测试。

### Task 4: ToolRegistry 接入

**Files:**
- Modify: `src/robot_agent/runtime/agent_runtime.py`
- Modify: `src/robot_agent/demo/pick_and_place.py`
- Test: `tests/test_execution_dataflow.py`

- [x] 编写工具执行结果被后续技能引用的端到端测试。
- [x] 运行测试并确认工具步骤尚不可执行。
- [x] 实现只读工具步骤执行与默认工具注册表注入。
- [x] 重跑相关测试。

### Task 5: LLM 解析、文档与完整验证

**Files:**
- Modify: `src/robot_agent/planning/llm_planner.py`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Test: `tests/test_llm_planner.py`

- [x] 编写 LLM 步骤 ID、输出引用和工具步骤解析测试。
- [x] 更新 LLM JSON 协议与解析。
- [x] 同步中英文架构说明。
- [x] 运行 `pytest --cov=robot_agent --cov-report=term-missing -q`。
- [x] 运行 CLI demo、`compileall`、`pip check` 和 `git diff --check`。
