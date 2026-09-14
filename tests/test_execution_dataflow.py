"""技能与工具输出驱动后续步骤的端到端测试。"""

from __future__ import annotations

from robot_agent.backends.sim_backend import SimBackend
from robot_agent.core.task import TaskStatus
from robot_agent.core.types import SkillResult
from robot_agent.demo.pick_and_place import DEFAULT_GOAL
from robot_agent.planning.base import OutputRef, Plan, Planner, SkillCall, ToolCall
from robot_agent.planning.mock_planner import MockPlanner
from robot_agent.runtime.agent_runtime import AgentRuntime
from robot_agent.skills import default_skill_manager
from robot_agent.tools.registry import ToolRegistry
from robot_agent.world.grid_world import build_pick_and_place_world


class _WrongDetectionBackend(SimBackend):
    def __init__(self, grid) -> None:
        super().__init__(grid)
        self.grasp_calls = 0

    def detect(self, world, query):
        return SkillResult.success("感知误识别", object_ids=["table"])

    def grasp(self, world, object_id):
        self.grasp_calls += 1
        return super().grasp(world, object_id)


def test_wrong_detection_output_stops_before_grasp():
    grid, world = build_pick_and_place_world()
    backend = _WrongDetectionBackend(grid)
    runtime = AgentRuntime(
        backend,
        default_skill_manager(),
        MockPlanner(),
        max_retries=0,
        max_replans=0,
    )

    report = runtime.run(DEFAULT_GOAL, world)

    assert report.task.status is TaskStatus.FAILED
    assert backend.grasp_calls == 0


def test_tool_output_can_drive_later_skill_parameter():
    grid, world = build_pick_and_place_world()
    tools = ToolRegistry()
    tools.register("select_target", "选择目标物体", lambda current: "red_cube")

    class _ToolPlanner(Planner):
        def plan(self, goal, current_world):
            return Plan(
                goal,
                (
                    SkillCall(
                        "navigate",
                        {"target_object": "red_cube"},
                        step_id="navigate_object",
                    ),
                    ToolCall(
                        "select_target",
                        depends_on=(0,),
                        step_id="select_target",
                    ),
                    SkillCall(
                        "grasp",
                        {
                            "object_id": OutputRef(
                                "select_target",
                                path=("value",),
                                expected="red_cube",
                            )
                        },
                        depends_on=(1,),
                        step_id="grasp_object",
                    ),
                    SkillCall(
                        "navigate",
                        {"target_object": "box"},
                        depends_on=(2,),
                        step_id="navigate_container",
                    ),
                    SkillCall(
                        "place",
                        {"container_id": "box"},
                        depends_on=(3,),
                        step_id="place_object",
                    ),
                ),
            )

    runtime = AgentRuntime(
        SimBackend(grid),
        default_skill_manager(),
        _ToolPlanner(),
        tools=tools,
    )

    report = runtime.run(DEFAULT_GOAL, world)

    assert report.succeeded
    tool_record = next(
        record for record in report.trace if record.skill == "tool:select_target"
    )
    assert tool_record.step_id == "select_target"
