"""pick-and-place 端到端演示场景。

在纯 Python 网格世界中装配完整 Agent 闭环，演示：
    理解目标 → 分解为技能序列 → 调度执行 → 监控 → （可选）异常恢复 → 目标验证。
"""

from __future__ import annotations

from typing import Sequence

from robot_agent.backends.sim_backend import SimBackend
from robot_agent.planning.base import Planner
from robot_agent.planning.mock_planner import MockPlanner
from robot_agent.runtime.agent_runtime import AgentRuntime, MemorySink, RunReport
from robot_agent.runtime.events import RuntimeObserver
from robot_agent.skills import default_skill_manager
from robot_agent.tools import default_tool_registry
from robot_agent.world.grid_world import build_pick_and_place_world
from robot_agent.world.state import WorldState

DEFAULT_GOAL = "把红色方块放到箱子里"


def build_runtime(
    *,
    inject_failure: bool = False,
    planner: Planner | None = None,
    memory: MemorySink | None = None,
    observers: Sequence[RuntimeObserver] | None = None,
) -> tuple[AgentRuntime, WorldState]:
    """装配演示用的运行时与初始世界。

    inject_failure=True 时注入一次 grasp 瞬时故障，用于演示重试恢复。
    observers 可挂载上位机显示等实时事件订阅者。
    """
    fail_actions = {"grasp": 1} if inject_failure else None
    grid, world = build_pick_and_place_world(fail_actions=fail_actions)
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
    goal: str = DEFAULT_GOAL,
    inject_failure: bool = False,
    planner: Planner | None = None,
    memory: MemorySink | None = None,
    observers: Sequence[RuntimeObserver] | None = None,
) -> RunReport:
    """运行演示并返回结果报告。"""
    runtime, world = build_runtime(
        inject_failure=inject_failure,
        planner=planner,
        memory=memory,
        observers=observers,
    )
    return runtime.run(goal, world)
