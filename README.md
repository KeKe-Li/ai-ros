**English** | [简体中文](README.zh-CN.md)

## robot-agent — Robotics Agent Runtime Prototype (dimOS-style)

An **upper-layer robot intelligence** prototype: the robot understands a task → decomposes it → calls skills → monitors state → recovers from failures → closes the execution loop.

The core has **zero dependency** on ROS2/GPU/network/API key. By default it uses a pure-Python simulation backend and a rule-based planner, so it **runs, reproduces, and self-verifies anywhere**.

### Architecture

```
Natural-language goal
      │  understand + decompose
      ▼
 ┌──────────┐  schedule ┌──────────────┐ unified call ┌──────────────┐
 │ Planner  │ ────────▶ │ TaskManager  │ ───────────▶ │ SkillManager │
 │(mock/LLM)│           │ (topo sort)  │              │  (registry)  │
 └──────────┘           └──────────────┘              └──────┬───────┘
     ▲                       ▲  monitor/recover              │ actuation
     │ replan                │                               ▼
 ┌───────────── AgentRuntime main loop ─────────┐    ┌──────────────┐
 │ understand→schedule→execute→monitor→recover→  │    │ RobotBackend │
 │ verify                                        │    │ Sim / ROS2*  │
 └──────┬────────────────────────┬───────────────┘    └──────┬───────┘
  Memory / ToolRegistry     event bus (RuntimeObserver)       ▼
                                 │                     GridWorld state
                        ┌────────┴────────┐
                        ▼                 ▼
                 Terminal live view   Web dashboard (SSE)
```
`*` `ROS2Backend` is a reserved adapter — implement it when deploying on Linux + ROS2.

### Core modules

| Module | Responsibility |
|---|---|
| `core/` | Common types (SkillResult/Pose), task state machine (Task), domain errors |
| `world/` | Immutable WorldState + pure-Python GridWorld |
| `backends/` | RobotBackend abstraction; SimBackend (default), ROS2Backend (reserved) |
| `skills/` | Standardized Skill interface + SkillManager; navigate/detect/grasp/place |
| `planning/` | Planner interface; MockPlanner (rules, default), LLMPlanner (Claude, optional); GoalSpec deterministic goal check |
| `runtime/` | TaskManager (scheduling), ExecutionMonitor (monitor/verify), AgentRuntime (main loop), event bus |
| `memory/` | Short-term episode stream + long-term JSON KV memory |
| `tools/` | Tool calling: pure info/compute tools (clear boundary vs. actuation Skills) |
| `display/` | Real-time HMI: terminal live view + web dashboard (subscribe to the runtime event bus) |
| `demo/`, `cli.py` | pick-and-place end-to-end demo and command-line entry |

### Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# End-to-end closed-loop demo (understand→decompose→schedule→execute→monitor→verify)
python -m robot_agent.cli demo --verbose

# Terminal live HMI (real-time grid + status panel)
python -m robot_agent.cli demo --watch --frame-delay 0.6

# Web GUI HMI (view in browser; zero external deps)
python -m robot_agent.cli demo --web --open --frame-delay 0.6
# then open http://127.0.0.1:8000/

# Inject one grasp failure to observe recovery (retry)
python -m robot_agent.cli demo --inject-failure

# Full verification (high-risk changes / before release)
pytest --cov=robot_agent
```

### Real-time monitoring / HMI

During execution the runtime emits structured events through a decoupled **event bus** (`RuntimeObserver`/`RuntimeEvent`). Any display is merely a subscriber — **the runtime never changes**:

- **Terminal live view** (`TerminalMonitor`): ANSI redraw of the grid world + status panel, zero deps.
- **Web dashboard** (`WebMonitor` + stdlib `http.server` + SSE): browser view of grid/task/recovery, with history replay, zero external deps.
- A misbehaving observer is isolated — **a display crash never brings down the robot run**.

### Development & verification guidance

By default, choose verification by change risk; not every change needs the full demo + coverage run.

- **Docs / rules / comments only**: `pytest` is generally not required; if you touch command examples or usage, at least confirm the relevant commands, paths, and file names are still valid.
- **Single-module, small code change**: run the relevant test file or the minimal affected subset.
- **Cross-module change, or touching core paths (`planning/`, `runtime/`, `skills/`, `cli.py`)**: run `pytest -q`.
- **Change affecting dependencies, packaging, entry commands, or the end-to-end path**: run `pytest --cov=robot_agent --cov-report=term-missing -q`; run the demo if needed.

If ROS2 or LLM dependencies are missing locally, out-of-environment verification is not required for optional extension paths not touched this round; note the limitation instead.

### Task completion criteria

By default, judge against the current task's goal; do not treat every task as full feature development.

- **Review / analysis tasks**: locate the issue, explain the impact, give actionable suggestions, and wait for confirmation before editing — that counts as done.
- **Docs / rules tasks**: text updated and consistent with the current repo; if commands, paths, or directory structure are involved, do the necessary smoke check.
- **Code-change tasks**: complete implementation plus risk-matched verification; if behavior, interface, or usage changes, update the corresponding tests and docs.
- **Not required by default**: committing on every task, reading all docs, or re-confirming already-agreed scope; update Memory only when explicitly requested.
- **Requires extra confirmation**: delete, reset, push, sensitive-config edits, permission changes, and other high-risk operations.

### Demo scenario

10×10 grid: robot starts at `(0,0)`, `table@(5,5)` holds `red_cube`, `box@(8,2)` is the container. The goal "把红色方块放到箱子里" (put the red cube into the box) decomposes into `navigate → detect → grasp → navigate → place`; the closed loop verifies the cube ends up inside the box.

### Extension points

- **Integrate ROS2**: in `backends/ros2_backend.py`, follow the mapping notes (Nav2 action, perception service, MoveIt/arm action + TF) and implement `RobotBackend`'s four methods — the upper layer stays unchanged.
- **Integrate a real LLM**: `pip install -e ".[llm]"`, set `ANTHROPIC_API_KEY`, then `python -m robot_agent.cli demo --planner llm`; it falls back to MockPlanner offline or on failure.
- **Add a skill**: subclass `skills/base.py::Skill`, implement execution and pre/post-world postcondition checks, then register it in `default_skill_manager` for uniform dispatch.
- **Add a display**: implement `RuntimeObserver.on_event` and subscribe to the event bus — the runtime stays unchanged.

### Design principles

Immutable data models (frozen dataclass, updates return new copies), dependency inversion & interface segregation, many small files over few large ones, close the loop first then extend (YAGNI).
