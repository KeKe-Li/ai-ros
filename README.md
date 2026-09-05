## robot-agent — 机器人 Agent Runtime 原型（类 dimOS）

一个机器人**上层智能系统**原型：让机器人理解任务 → 拆解任务 → 调用技能 → 监控状态 → 异常恢复 → 完成闭环执行。核心不依赖 ROS2/GPU/网络/API key，
默认使用纯 Python 仿真后端与规则分解器，**处处可运行、可复现、可自动化验证**。

### 架构总览

```
自然语言目标
     │  理解 + 分解
     ▼
 ┌──────────┐   调度   ┌──────────────┐  统一调用    ┌──────────────┐
 │ Planner  │ ──────▶ │ TaskManager  │ ─────────▶  │ SkillManager │
 │(mock/LLM)│         │ (拓扑排序)    │             │  (技能注册)    │
 └──────────┘         └──────────────┘             └──────┬───────┘
     ▲                      ▲  监控/恢复                   │ 物理动作
     │ 重规划                │                             ▼
 ┌────────────────── AgentRuntime 主循环 ──────┐   ┌──────────────┐
 │ 理解→分解→调度→执行→监控→异常恢复→目标验证       │   │ RobotBackend │
 └───────────────────┬────────────────────────┘   │ Sim / ROS2*  │
             记忆 Memory / 工具 ToolRegistry       └──────┬───────┘
                                                          ▼
                                                     GridWorld 世界状态
```
`*` ROS2Backend 为预留适配器，部署到 Linux + ROS2 时补全实现。

### 核心模块

| 模块 | 职责 |
|---|---|
| `core/` | 公共类型（SkillResult/Pose）、任务状态机（Task）、领域异常 |
| `world/` | 不可变世界状态 WorldState + 纯 Python 网格世界 GridWorld |
| `backends/` | 机器人执行层抽象 RobotBackend；SimBackend（默认）、ROS2Backend（预留） |
| `skills/` | 标准化技能接口 Skill + SkillManager；导航/检测/抓取/放置 |
| `planning/` | Planner 接口；MockPlanner（规则，默认）、LLMPlanner（Claude，可选） |
| `runtime/` | TaskManager（调度）、ExecutionMonitor（监控/校验）、AgentRuntime（主循环） |
| `memory/` | 短期 episode 事件流 + 长期 JSON KV 记忆 |
| `tools/` | ToolCalling：注册纯信息/计算工具（与产生物理动作的 Skill 边界清晰） |
| `demo/`、`cli.py` | pick-and-place 端到端演示与命令行入口 |

### 快速开始

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 端到端闭环演示（观察：理解→分解→调度→执行→监控→验证）
python -m robot_agent.cli demo --verbose

# 注入一次抓取故障，观察异常恢复（重试）
python -m robot_agent.cli demo --inject-failure

# 全量测试 + 覆盖率
pytest --cov=robot_agent
```

### 演示场景

10×10 网格：机器人起点 `(0,0)`，桌子 `table@(5,5)` 上有 `red_cube`，箱子 `box@(8,2)`。
目标"把红色方块放到箱子里"被分解为 `navigate → detect → grasp → navigate → place`， 最终闭环验证方块进入箱子。

### 扩展点

- **接入 ROS2**：在 `backends/ros2_backend.py` 中按注释映射到 Nav2 action、感知 service、
  MoveIt/机械臂 action 与 TF，实现 `RobotBackend` 四个方法，上层无需改动。
- **接入真实 LLM**：`pip install -e ".[llm]"` 并设置 `ANTHROPIC_API_KEY`，
  `python -m robot_agent.cli demo --planner llm`；离线/失败时自动回退到 MockPlanner。
- **新增技能**：继承 `skills/base.py::Skill` 并在 `default_skill_manager` 注册即可被统一调度。

### 设计原则

不可变数据模型（frozen dataclass，更新返回新副本）、依赖倒置与接口隔离、多个小文件优于少数大文件、先跑通闭环再谈扩展（YAGNI）。
