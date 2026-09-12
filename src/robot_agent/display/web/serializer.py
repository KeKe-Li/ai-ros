"""运行时事件 → JSON 友好字典的序列化（纯函数，便于单测）。

发送结构化世界数据（尺寸、机器人、物体、持有物）与任务/步骤状态，由前端渲染
真实网格 GUI，而非在后端拼字符串。
"""

from __future__ import annotations

from typing import Any

from robot_agent.runtime.events import RuntimeEvent
from robot_agent.world.state import WorldState


def _world_to_dict(world: WorldState) -> dict[str, Any]:
    poses = [info.pose for info in world.objects.values()] + [world.robot_pose]
    width = max((p.x for p in poses), default=0) + 1
    height = max((p.y for p in poses), default=0) + 1
    return {
        "width": width,
        "height": height,
        "robot": {"x": world.robot_pose.x, "y": world.robot_pose.y},
        "holding": world.holding,
        "objects": [
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
        ],
    }


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
            "params": dict(event.step.params),
        }
    return payload
