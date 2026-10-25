"""命令行报告与 artifact 回放输出。"""

from __future__ import annotations

import time
from typing import Any

from robot_agent.reporting.replay import (
    build_replay_payloads,
    replay_plan_history,
    replay_trace,
)
from robot_agent.runtime.agent_runtime import RunReport

_STATUS_ICON = {"ok": "✅", "failed": "❌"}


def format_final_state_line(container: str | None, holding: str | None) -> str:
    """终态行文案：live 报告与 artifact 回放共用，保证两条路径表述一致。"""
    return (
        f"终态：red_cube 所在容器 = {container or '（未入箱）'}；机械臂持有 = {holding}"
    )


def format_result_line(succeeded: bool) -> str:
    return "结果：成功 ✅" if succeeded else "结果：失败 ❌"


def print_report(report: RunReport, goal: str, verbose: bool) -> None:
    print(f"目标：{goal}")
    print(
        f"任务状态：{report.task.status.value}"
        + (f"（{report.task.error}）" if report.task.error else "")
    )
    print(f"重规划次数：{report.replans}")
    print("执行轨迹：")
    for i, rec in enumerate(report.trace, 1):
        icon = _STATUS_ICON.get(rec.status, "•")
        retry = f" [重试#{rec.attempt}]" if rec.attempt > 0 else ""
        print(f"  {i:>2}. {icon} {rec.skill}{retry} — {rec.message}")
    cube = report.world.get("red_cube")
    container = cube.in_container if cube else None
    print(format_final_state_line(container, report.world.holding))
    print(format_result_line(report.succeeded))
    if verbose:
        print("\n[verbose] 世界物体快照：")
        for oid in sorted(report.world.objects):
            info = report.world.get(oid)
            print(
                f"  - {oid}: pose=({info.pose.x},{info.pose.y}) "
                f"color={info.color} in_container={info.in_container}"
            )


def format_artifact_status(artifact: dict[str, Any]) -> str:
    status = str(artifact.get("task_status", "unknown"))
    error = artifact.get("task_error")
    return f"{status}（{error}）" if error else status


def print_replay(artifact: dict[str, Any], verbose: bool, frame_delay: float) -> None:
    goal = artifact.get("goal", "")
    scenario = artifact.get("scenario") or "（未记录）"
    replans = artifact.get("replans", 0)
    trace = replay_trace(artifact)
    plan_history = replay_plan_history(artifact)
    final_world = artifact.get("final_world", {})
    objects = final_world.get("objects", {}) if isinstance(final_world, dict) else {}
    cube = objects.get("red_cube", {}) if isinstance(objects, dict) else {}
    holding = final_world.get("holding") if isinstance(final_world, dict) else None

    print(f"目标：{goal}")
    print(f"场景：{scenario}")
    print(f"任务状态：{format_artifact_status(artifact)}")
    print(f"重规划次数：{replans}")
    print(f"计划版本数：{len(plan_history)}")
    print("执行轨迹回放：")
    for index, item in enumerate(trace, 1):
        status = str(item.get("status", ""))
        icon = _STATUS_ICON.get(status, "•")
        attempt = int(item.get("attempt", 0))
        retry = f" [重试#{attempt}]" if attempt > 0 else ""
        skill = item.get("skill", "unknown")
        message = item.get("message", "")
        print(f"  {index:>2}. {icon} {skill}{retry} — {message}")
        if frame_delay > 0:
            time.sleep(frame_delay)

    container = cube.get("in_container") if isinstance(cube, dict) else None
    print(format_final_state_line(container, holding))
    print(format_result_line(artifact.get("task_status") == "succeeded"))

    if verbose:
        print("\n[verbose] 计划历史：")
        for version, plan in enumerate(plan_history, 1):
            print(f"  - plan#{version}:")
            for step in plan:
                kind = step.get("kind", "unknown")
                name = step.get("name", "unknown")
                step_id = step.get("step_id", "")
                depends_on = step.get("depends_on", [])
                print(f"      {kind}:{name} step_id={step_id} depends_on={depends_on}")


def publish_replay_payloads(
    broadcaster: Any,
    artifact: dict[str, Any],
    frame_delay: float,
) -> None:
    payloads = build_replay_payloads(artifact)
    plan_history = replay_plan_history(artifact)
    plan_versions = len(plan_history)
    for payload in payloads:
        replay_payload = dict(payload)
        replay_payload["plan_versions"] = plan_versions
        broadcaster.publish(replay_payload)
        if frame_delay > 0 and payload["kind"] != "task_finished":
            time.sleep(frame_delay)
