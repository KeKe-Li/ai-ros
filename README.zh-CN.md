[English](README.md) | **简体中文**

## robot-agent — 机器人 Agent Runtime 原型（类 dimOS）

一个机器人**上层智能系统**原型：让机器人理解任务 → 拆解任务 → 调用技能 → 监控状态 → 异常恢复 → 完成闭环执行。

核心不依赖 ROS2/GPU/网络/API key，默认使用纯 Python 仿真后端与规则分解器，**处处可运行、可复现、可自动化验证**。

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
 ┌────────────── AgentRuntime 主循环 ───────────┐   ┌──────────────┐
 │ 理解→调度→执行→监控→异常恢复→目标验证          │   │ RobotBackend │
 └──────┬────────────────────────┬──────────────┘   │ Sim / ROS2*  │
  Memory / ToolRegistry     事件总线(RuntimeObserver) └──────┬───────┘
                                 │                          ▼
                        ┌────────┴────────┐          GridWorld 世界状态
                        ▼                 ▼
                  终端实时视图        Web 仪表盘(SSE)
```
`*` ROS2Backend 为预留适配器，部署到 Linux + ROS2 时补全实现。

### 核心模块

| 模块 | 职责 |
|---|---|
| `core/` | 公共类型（SkillResult/Pose）、任务状态机（Task）、领域异常 |
| `world/` | 不可变世界状态 WorldState + 纯 Python 网格世界 GridWorld |
| `backends/` | 机器人执行层抽象 RobotBackend；SimBackend（默认）、ROS2Backend（预留） |
| `skills/` | 标准化技能接口 Skill + SkillManager；导航/检测/抓取/放置 |
| `planning/` | Planner 接口；MockPlanner（规则，默认）、LLMPlanner（Claude，可选）；GoalSpec 确定性目标判定 |
| `runtime/` | TaskManager（调度）、ExecutionMonitor（监控/校验）、AgentRuntime（主循环）、事件总线 |
| `memory/` | 短期 episode 事件流 + 长期 JSON KV 记忆 |
| `tools/` | ToolCalling：注册纯信息/计算工具（与产生物理动作的 Skill 边界清晰） |
| `display/` | 上位机实时监控：终端实时视图 + Web 仪表盘（订阅运行时事件总线） |
| `demo/`、`cli.py` | pick-and-place 端到端演示与命令行入口 |

### 快速开始

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 端到端闭环演示（观察：理解→分解→调度→执行→监控→验证）
python -m robot_agent.cli demo --verbose

# 终端实时可视化上位机（实时网格 + 状态面板）
python -m robot_agent.cli demo --watch --frame-delay 0.6

# Web 图形界面上位机（浏览器查看，零外部依赖）
python -m robot_agent.cli demo --web --open --frame-delay 0.6
# 然后打开 http://127.0.0.1:8000/

# 注入一次抓取故障，观察异常恢复（重试）
python -m robot_agent.cli demo --inject-failure

# 完整验证（高风险改动、发布前或需要全量确认时）
pytest --cov=robot_agent
```

### 上位机实时监控

运行时在执行过程中通过一条解耦的**事件总线**（`RuntimeObserver`/`RuntimeEvent`）实时发出结构化事件。任何显示端只是订阅者，**运行时无需改动**：

- **终端实时视图**（`TerminalMonitor`）：用 ANSI 转义实时重绘网格世界 + 状态面板，零依赖。
- **Web 仪表盘**（`WebMonitor` + 标准库 `http.server` + SSE）：浏览器实时查看网格/任务/恢复，支持历史回放，零外部依赖。
- 显示端异常被隔离，**GUI 崩溃不会拖垮机器人运行**。

### 开发与验证建议

默认按改动风险选择验证，不要求每次改动都运行完整 demo 与覆盖率。

- **纯文档、规则、注释改动**：一般不强制运行 `pytest`；若修改命令示例或使用说明，至少核对相关命令、路径和文件名仍然有效。
- **单模块、小范围代码改动**：优先运行相关测试文件或最小受影响测试集。
- **跨模块改动，或涉及 `planning/`、`runtime/`、`skills/`、`cli.py` 等核心链路**：运行 `pytest -q`。
- **影响依赖、打包、入口命令或端到端链路的改动**：运行 `pytest --cov=robot_agent --cov-report=term-missing -q`；必要时再运行 demo 命令。

若本地环境缺少 ROS2 或 LLM 依赖，不要求为本轮未触达的可选扩展路径补做环境外验证；相关限制应在说明中写明。

### 任务完成标准

默认以当前任务目标为准，不把所有任务都按“完整功能开发”处理。

- **审查 / 分析类任务**：明确问题位置、说明影响、给出可执行调整建议，并等待确认后再修改，即可视为完成。
- **文档 / 规则类任务**：文本更新完成，且与当前仓库实际一致；如涉及命令、路径或目录结构，完成必要的 smoke check。
- **代码改动类任务**：实现完整，并完成与风险匹配的验证；若行为、接口或使用方式变化，更新相应测试与文档。
- **默认不要求**：每次任务都提交 `commit`、通读全部文档，或重复确认已明确的范围；Memory 仅在用户明确要求时更新。
- **需要额外确认的情况**：删除、重置、推送、敏感配置修改、权限变更等高风险操作。

### 演示场景

10×10 网格：机器人起点 `(0,0)`，桌子 `table@(5,5)` 上有 `red_cube`，箱子 `box@(8,2)`。
目标"把红色方块放到箱子里"被分解为 `navigate → detect → grasp → navigate → place`， 最终闭环验证方块进入箱子。

### 扩展点

- **接入 ROS2**：在 `backends/ros2_backend.py` 中按注释映射到 Nav2 action、感知 service、
  MoveIt/机械臂 action 与 TF，实现 `RobotBackend` 四个方法，上层无需改动。
- **接入真实 LLM**：`pip install -e ".[llm]"` 并设置 `ANTHROPIC_API_KEY`，
  `python -m robot_agent.cli demo --planner llm`；离线/失败时自动回退到 MockPlanner。
- **新增技能**：继承 `skills/base.py::Skill` 并在 `default_skill_manager` 注册即可被统一调度。
- **新增显示端**：实现 `RuntimeObserver.on_event` 并订阅事件总线即可，运行时无需改动。

### 设计原则

不可变数据模型（frozen dataclass，更新返回新副本）、依赖倒置与接口隔离、多个小文件优于少数大文件、先跑通闭环再谈扩展（YAGNI）。
