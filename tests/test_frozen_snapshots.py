"""计划、结果、世界、上下文和运行轨迹的不可变快照测试。"""

from __future__ import annotations

import json

import pytest

from robot_agent.core.frozen import to_jsonable
from robot_agent.core.types import Pose, SkillResult
from robot_agent.demo.pick_and_place import run_demo
from robot_agent.planning import OutputRef, SkillCall
from robot_agent.runtime import ExecutionContext
from robot_agent.world.state import ObjectInfo, WorldState


def test_skill_result_and_plan_params_are_deeply_frozen():
    raw_output = {"object_ids": ["red_cube"]}
    raw_params = {"query": {"colors": ["red"]}}

    result = SkillResult.success(**raw_output)
    call = SkillCall("detect", raw_params, step_id="detect")
    raw_output["object_ids"][0] = "blue_cube"
    raw_params["query"]["colors"][0] = "blue"

    assert result.data["object_ids"] == ("red_cube",)
    assert call.params["query"]["colors"] == ("red",)
    with pytest.raises(TypeError):
        result.data["new"] = True


def test_world_state_defensively_copies_direct_constructor_input():
    objects = {"cube": ObjectInfo(Pose(0, 0), is_graspable=True)}
    world = WorldState(Pose(0, 0), objects=objects)

    objects["box"] = ObjectInfo(Pose(1, 1), is_container=True)

    assert world.get("box") is None
    with pytest.raises(TypeError):
        world.objects["other"] = ObjectInfo(Pose(2, 2))


def test_object_aliases_are_defensively_copied():
    aliases = ["红方块"]
    info = ObjectInfo(Pose(0, 0), aliases=aliases)

    aliases[0] = "蓝方块"

    assert info.aliases == ("红方块",)


def test_execution_context_records_deep_snapshot():
    payload = {"object_ids": ["red_cube"]}
    context = ExecutionContext()
    context.record("detect", payload)
    payload["object_ids"][0] = "blue_cube"

    resolved = context.resolve_params({"id": OutputRef("detect", ("object_ids", 0))})

    assert resolved == {"id": "red_cube"}


def test_step_record_contains_raw_resolved_params_and_output():
    report = run_demo()
    grasp = next(record for record in report.trace if record.skill == "grasp")
    detect = next(record for record in report.trace if record.skill == "detect")

    assert isinstance(grasp.raw_params["object_id"], OutputRef)
    assert grasp.params["object_id"] == "red_cube"
    assert detect.output["object_ids"] == ("red_cube",)
    assert detect.kind == "skill"
    assert detect.error_type is None
    assert json.loads(json.dumps(to_jsonable(detect.output))) == {
        "object_ids": ["red_cube"]
    }
