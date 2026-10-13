"""Run artifact 序列化辅助。"""

from __future__ import annotations

from robot_agent.core.frozen import to_jsonable
from robot_agent.planning.base import SkillCall, ToolCall
from robot_agent.runtime.events import RuntimeDiagnostic, StepRecord
from robot_agent.world.state import ObjectInfo, WorldState


def object_info_to_dict(info: ObjectInfo) -> dict[str, object]:
    return {
        "pose": {"x": info.pose.x, "y": info.pose.y},
        "color": info.color,
        "is_graspable": info.is_graspable,
        "is_container": info.is_container,
        "in_container": info.in_container,
        "aliases": list(info.aliases),
    }


def world_to_dict(world: WorldState) -> dict[str, object]:
    return {
        "robot_pose": {"x": world.robot_pose.x, "y": world.robot_pose.y},
        "holding": world.holding,
        "objects": {
            object_id: object_info_to_dict(info)
            for object_id, info in sorted(world.objects.items())
        },
    }


def step_record_to_dict(record: StepRecord) -> dict[str, object]:
    return {
        "skill": record.skill,
        "params": to_jsonable(record.params),
        "status": record.status,
        "message": record.message,
        "attempt": record.attempt,
        "step_id": record.step_id,
        "kind": record.kind,
        "raw_params": to_jsonable(record.raw_params),
        "output": to_jsonable(record.output),
        "error_type": record.error_type,
        "failure_kind": record.failure_kind,
    }


def diagnostic_to_dict(diagnostic: RuntimeDiagnostic) -> dict[str, object]:
    return {
        "component": diagnostic.component,
        "stage": diagnostic.stage,
        "error_type": diagnostic.error_type,
        "message": diagnostic.message,
    }


def plan_step_to_dict(step: SkillCall | ToolCall) -> dict[str, object]:
    if isinstance(step, SkillCall):
        return {
            "kind": "skill",
            "name": step.skill,
            "step_id": step.step_id,
            "depends_on": list(step.depends_on),
            "params": to_jsonable(step.params),
        }
    return {
        "kind": "tool",
        "name": step.tool,
        "step_id": step.step_id,
        "depends_on": list(step.depends_on),
        "params": to_jsonable(step.params),
    }
