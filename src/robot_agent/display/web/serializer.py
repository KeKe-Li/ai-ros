"""运行时事件 → JSON 友好字典的序列化（纯函数，便于单测）。

发送结构化世界数据（尺寸、机器人、物体、持有物）与任务/步骤状态，由前端渲染
真实网格 GUI，而非在后端拼字符串。
"""

from __future__ import annotations

from typing import Any

from robot_agent.core.frozen import to_jsonable
from robot_agent.display.grid import grid_extent
from robot_agent.runtime.events import RuntimeEvent
from robot_agent.world.state import WorldState


def build_dashboard_world(
    *,
    robot_x: int,
    robot_y: int,
    holding: str | None,
    objects: list[dict[str, Any]],
) -> dict[str, Any]:
    """组装仪表盘世界载荷（宽高 = max(机器人, 各物体坐标) + 1）。

    objects 需为已规范化的列表，每项含 id/x/y/color/graspable/container/
    in_container，由各调用方从自身数据源（活动 WorldState 或 artifact dict）
    抽取后传入。集中此处可保证 live 与 replay 两条路径的仪表盘世界结构一致。
    """
    width, height = grid_extent(
        [robot_x, *(obj["x"] for obj in objects)],
        [robot_y, *(obj["y"] for obj in objects)],
    )
    return {
        "width": width,
        "height": height,
        "robot": {"x": robot_x, "y": robot_y},
        "holding": holding,
        "objects": objects,
    }


def _world_to_dict(world: WorldState) -> dict[str, Any]:
    objects = [
        {
            "id": oid,
            "x": info.pose.x,
            "y": info.pose.y,
            "color": info.color,
            "graspable": info.is_graspable,
            "container": info.is_container,
            "in_container": info.in_container,
        }
        for oid, info in sorted(world.objects.items())
    ]
    return build_dashboard_world(
        robot_x=world.robot_pose.x,
        robot_y=world.robot_pose.y,
        holding=world.holding,
        objects=objects,
    )


def event_to_dict(event: RuntimeEvent) -> dict[str, Any]:
    """把 RuntimeEvent 转为可 JSON 序列化的字典。"""
    payload: dict[str, Any] = {
        "kind": event.kind,
        "goal": event.goal,
        "replans": event.replans,
        "message": event.message,
        "world": _world_to_dict(event.world),
        "task": None,
        "step": None,
    }
    if event.task is not None:
        payload["task"] = {
            "status": event.task.status.value,
            "error": event.task.error,
        }
    if event.step is not None:
        payload["step"] = {
            "skill": event.step.skill,
            "step_id": event.step.step_id,
            "status": event.step.status,
            "message": event.step.message,
            "attempt": event.step.attempt,
            "kind": event.step.kind,
            "params": to_jsonable(event.step.params),
            "raw_params": to_jsonable(event.step.raw_params),
            "output": to_jsonable(event.step.output),
            "error_type": event.step.error_type,
            "failure_kind": event.step.failure_kind,
        }
    return payload
