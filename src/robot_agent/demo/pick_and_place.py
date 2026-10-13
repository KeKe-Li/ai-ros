"""pick-and-place 端到端演示场景。

在纯 Python 网格世界中装配完整 Agent 闭环，演示：
    理解目标 → 分解为技能序列 → 调度执行 → 监控 → （可选）异常恢复 → 目标验证。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from robot_agent.backends.sim_backend import SimBackend
from robot_agent.planning.base import Planner
from robot_agent.planning.mock_planner import MockPlanner
from robot_agent.runtime.agent_runtime import AgentRuntime, MemorySink, RunReport
from robot_agent.runtime.events import RuntimeObserver
from robot_agent.scenarios import build_world_from_scenario, load_scenario
from robot_agent.scenarios.models import ScenarioSpec
from robot_agent.skills import default_skill_manager
from robot_agent.tools import default_tool_registry
from robot_agent.world.grid_world import GridWorld
from robot_agent.world.state import WorldState

DEFAULT_GOAL = "把红色方块放到箱子里"
DEFAULT_SCENARIO = "pick_and_place_basic"


def _with_injected_failure(
    spec: ScenarioSpec,
    *,
    inject_failure: bool,
) -> ScenarioSpec:
    if not inject_failure:
        return spec
    fail_actions = dict(spec.fail_actions)
    fail_actions["grasp"] = max(fail_actions.get("grasp", 0), 1)
    return replace(spec, fail_actions=fail_actions)


def _build_scenario_world(
    scenario: str,
    *,
    inject_failure: bool,
) -> tuple[ScenarioSpec, GridWorld, WorldState]:
    spec = load_scenario(scenario)
    effective_spec = _with_injected_failure(spec, inject_failure=inject_failure)
    grid, world = build_world_from_scenario(effective_spec)
    return effective_spec, grid, world


def build_runtime(
    *,
    inject_failure: bool = False,
    planner: Planner | None = None,
    memory: MemorySink | None = None,
    observers: Sequence[RuntimeObserver] | None = None,
    scenario: str = DEFAULT_SCENARIO,
) -> tuple[AgentRuntime, WorldState]:
    """装配演示用的运行时与初始世界。

    inject_failure=True 时注入一次 grasp 瞬时故障，用于演示重试恢复。
    observers 可挂载上位机显示等实时事件订阅者。
    """
    _, grid, world = _build_scenario_world(scenario, inject_failure=inject_failure)
    runtime = AgentRuntime(
        backend=SimBackend(grid),
        skill_manager=default_skill_manager(),
        planner=planner or MockPlanner(),
        tools=default_tool_registry(),
        memory=memory,
        observers=observers,
    )
    return runtime, world


def run_demo(
    *,
    goal: str | None = None,
    inject_failure: bool = False,
    planner: Planner | None = None,
    memory: MemorySink | None = None,
    observers: Sequence[RuntimeObserver] | None = None,
    scenario: str = DEFAULT_SCENARIO,
) -> RunReport:
    """运行演示并返回结果报告。"""
    spec = load_scenario(scenario)
    runtime, world = build_runtime(
        inject_failure=inject_failure,
        planner=planner,
        memory=memory,
        observers=observers,
        scenario=scenario,
    )
    effective_goal = goal if goal is not None else spec.goal
    return runtime.run(effective_goal, world)
