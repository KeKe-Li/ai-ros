"""Artifact replay 辅助。"""

from __future__ import annotations

from typing import Any


def replay_trace(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    trace = artifact.get("trace", [])
    if not isinstance(trace, list):
        raise ValueError("artifact.trace 必须是列表")
    for index, item in enumerate(trace):
        if not isinstance(item, dict):
            raise ValueError(f"artifact.trace[{index}] 必须是对象")
    return trace


def replay_plan_history(artifact: dict[str, Any]) -> list[list[dict[str, Any]]]:
    plan_history = artifact.get("plan_history", [])
    if not isinstance(plan_history, list):
        raise ValueError("artifact.plan_history 必须是列表")
    normalized: list[list[dict[str, Any]]] = []
    for index, plan in enumerate(plan_history):
        if not isinstance(plan, list):
            raise ValueError(f"artifact.plan_history[{index}] 必须是列表")
        if not all(isinstance(step, dict) for step in plan):
            raise ValueError(f"artifact.plan_history[{index}] 的元素必须是对象")
        normalized.append(plan)
    return normalized


def _artifact_world_to_dashboard_world(world: dict[str, Any]) -> dict[str, Any]:
    robot_pose = world.get("robot_pose", {}) if isinstance(world, dict) else {}
    robot_x = int(robot_pose.get("x", 0)) if isinstance(robot_pose, dict) else 0
    robot_y = int(robot_pose.get("y", 0)) if isinstance(robot_pose, dict) else 0
    objects = world.get("objects", {}) if isinstance(world, dict) else {}

    object_list: list[dict[str, Any]] = []
    max_x = robot_x
    max_y = robot_y
    if isinstance(objects, dict):
        for object_id, info in sorted(objects.items()):
            if not isinstance(info, dict):
                continue
            pose = info.get("pose", {}) if isinstance(info, dict) else {}
            x = int(pose.get("x", 0)) if isinstance(pose, dict) else 0
            y = int(pose.get("y", 0)) if isinstance(pose, dict) else 0
            max_x = max(max_x, x)
            max_y = max(max_y, y)
            object_list.append(
                {
                    "id": object_id,
                    "x": x,
                    "y": y,
                    "color": info.get("color"),
                    "graspable": bool(info.get("is_graspable", False)),
                    "container": bool(info.get("is_container", False)),
                    "in_container": info.get("in_container"),
                }
            )

    return {
        "width": max_x + 1,
        "height": max_y + 1,
        "robot": {"x": robot_x, "y": robot_y},
        "holding": world.get("holding") if isinstance(world, dict) else None,
        "objects": object_list,
    }


def build_replay_payloads(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    goal = str(artifact.get("goal", ""))
    scenario = artifact.get("scenario")
    replans = int(artifact.get("replans", 0) or 0)
    task_status = str(artifact.get("task_status", "unknown"))
    task_error = artifact.get("task_error")
    plan_history = replay_plan_history(artifact)
    trace = replay_trace(artifact)
    active_plan = plan_history[-1] if plan_history else []

    initial_world = _artifact_world_to_dashboard_world(
        artifact.get("initial_world", {})
    )
    final_world = _artifact_world_to_dashboard_world(artifact.get("final_world", {}))

    payloads: list[dict[str, Any]] = [
        {
            "kind": "task_started",
            "goal": goal,
            "scenario": scenario,
            "replans": 0,
            "message": "artifact replay started",
            "world": initial_world,
            "task": {"status": "running", "error": None},
            "step": None,
            "plan": active_plan,
            "current_step_id": None,
        }
    ]

    for item in trace:
        step_status = str(item.get("status", ""))
        payloads.append(
            {
                "kind": "step_result",
                "goal": goal,
                "scenario": scenario,
                "replans": replans,
                "message": str(item.get("message", "")),
                "world": initial_world,
                "task": {
                    "status": "recovering" if step_status == "failed" else "running",
                    "error": None,
                },
                "step": item,
                "plan": active_plan,
                "current_step_id": item.get("step_id"),
            }
        )

    payloads.append(
        {
            "kind": "task_finished",
            "goal": goal,
            "scenario": scenario,
            "replans": replans,
            "message": str(task_error or ""),
            "world": final_world,
            "task": {"status": task_status, "error": task_error},
            "step": None,
            "plan": active_plan,
            "current_step_id": None,
        }
    )
    return payloads
