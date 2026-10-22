# 第一批优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变现有外部行为的前提下，完成第一批低风险优化：收敛 runtime 执行流程、解耦 CLI/Web 生命周期，并补齐对应测试，降低后续演进复杂度。

**Architecture:** 保持现有模块边界不变，不做功能扩展，不改默认用户路径；只做“职责拆分 + 生命周期收敛 + 测试补强”。核心思路是把 `AgentRuntime` / `StepExecutor` 中不断膨胀的流程逻辑拆成小而清晰的阶段方法，同时把 CLI 中“运行任务”和“持续提供 Web 服务”的职责显式化。

**Tech Stack:** Python 3.11+、pytest、pytest-cov、ruff、stdlib `argparse`、`http.server`、线程与事件广播模型。

---

## 任务范围

1. runtime 主循环结构收敛
2. step executor 职责拆分
3. CLI/Web 生命周期收敛与测试补强
4. 批次级验证
