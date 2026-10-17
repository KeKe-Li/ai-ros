"""命令行入口。

用法：
    python -m robot_agent.cli demo [--planner mock|llm] [--inject-failure] [--verbose]
    python -m robot_agent.cli demo --web [--port 8000] [--open]   # Web 图形界面上位机
    python -m robot_agent.cli demo --watch                        # 终端实时可视化
    python -m robot_agent.cli replay <artifact.json>             # 回放已保存的运行结果

打印完整闭环执行轨迹：目标、分解与每步状态、异常恢复过程、终态验证结果。
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
import webbrowser
from typing import Any

from robot_agent.demo.pick_and_place import DEFAULT_SCENARIO, run_demo
from robot_agent.display.web import DashboardServer, EventBroadcaster, WebMonitor
from robot_agent.memory.memory import Memory
from robot_agent.planning.base import Planner
from robot_agent.reporting import (
    build_replay_payloads,
    load_artifact,
    replay_plan_history,
    replay_trace,
    save_artifact,
)
from robot_agent.runtime.agent_runtime import RunReport
from robot_agent.scenarios import list_scenarios, load_scenario

_STATUS_ICON = {"ok": "✅", "failed": "❌"}


def _start_dashboard_server(
    args: argparse.Namespace,
) -> tuple[EventBroadcaster, DashboardServer]:
    broadcaster = EventBroadcaster()
    server = DashboardServer(broadcaster, port=args.port)
    server.start()
    return broadcaster, server


def _announce_dashboard(args: argparse.Namespace, server: DashboardServer) -> None:
    print(f"上位机仪表盘已启动：{server.url}")
    if args.open:
        try:
            webbrowser.open(server.url)
        except Exception:  # noqa: BLE001 - 打开浏览器失败不影响服务
            pass


def _start_web_dashboard(
    args: argparse.Namespace,
) -> tuple[DashboardServer, WebMonitor]:
    broadcaster, server = _start_dashboard_server(args)
    try:
        web_monitor = WebMonitor(broadcaster, min_interval=args.frame_delay)
    except Exception:
        server.stop()
        raise
    _announce_dashboard(args, server)
    return server, web_monitor


def _stop_web_dashboard(
    server: DashboardServer | None, web_monitor: WebMonitor | None
) -> None:
    if web_monitor is not None:
        web_monitor.stop()
    if server is not None:
        server.stop()


def _wait_forever() -> None:
    threading.Event().wait()


def _wait_for_dashboard_if_needed(
    args: argparse.Namespace,
    server: DashboardServer | None,
    web_monitor: WebMonitor | None,
) -> None:
    if server is None:
        return
    print(f"\n仪表盘持续服务中：{server.url}  （按 Ctrl+C 退出）")
    try:
        _wait_forever()
    except KeyboardInterrupt:
        print("\n正在关闭仪表盘…")
    finally:
        _stop_web_dashboard(server, web_monitor)


def _make_planner(args: argparse.Namespace) -> Planner:
    """按名称构造规划器。llm 分解器为可选能力，延迟导入。"""
    name = args.planner
    if name == "mock":
        from robot_agent.planning.mock_planner import MockPlanner

        return MockPlanner()
    if name == "llm":
        from robot_agent.planning.llm_planner import LLMPlanner

        return LLMPlanner(fallback_mode=args.llm_fallback)
    raise SystemExit(f"未知的 planner：{name}（可选 mock / llm）")


def _format_final_state_line(container: str | None, holding: str | None) -> str:
    """终态行文案：live 报告与 artifact 回放共用，保证两条路径表述一致。"""
    return (
        f"终态：red_cube 所在容器 = {container or '（未入箱）'}；机械臂持有 = {holding}"
    )


def _format_result_line(succeeded: bool) -> str:
    return "结果：成功 ✅" if succeeded else "结果：失败 ❌"


def _print_report(report: RunReport, goal: str, verbose: bool) -> None:
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
    print(_format_final_state_line(container, report.world.holding))
    print(_format_result_line(report.succeeded))
    if verbose:
        print("\n[verbose] 世界物体快照：")
        for oid in sorted(report.world.objects):
            info = report.world.get(oid)
            print(
                f"  - {oid}: pose=({info.pose.x},{info.pose.y}) "
                f"color={info.color} in_container={info.in_container}"
            )


def _print_scenarios() -> None:
    print("可用场景：")
    for spec in list_scenarios():
        print(f"  - {spec.name}: {spec.description}")
        print(f"      goal: {spec.goal}")


def _format_artifact_status(artifact: dict[str, Any]) -> str:
    status = str(artifact.get("task_status", "unknown"))
    error = artifact.get("task_error")
    return f"{status}（{error}）" if error else status


def _print_replay(artifact: dict[str, Any], verbose: bool, frame_delay: float) -> None:
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
    print(f"任务状态：{_format_artifact_status(artifact)}")
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
    print(_format_final_state_line(container, holding))
    print(_format_result_line(artifact.get("task_status") == "succeeded"))

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


def _publish_replay_payloads(
    broadcaster: EventBroadcaster,
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


def _cmd_demo(args: argparse.Namespace) -> int:
    if args.list_scenarios:
        _print_scenarios()
        return 0

    planner = _make_planner(args)
    memory = Memory() if args.verbose else None
    observers: list[object] = []

    if args.watch:
        from robot_agent.display.terminal import TerminalMonitor

        observers.append(TerminalMonitor(step_delay=args.frame_delay))

    server = None
    web_monitor = None
    if args.web:
        server, web_monitor = _start_web_dashboard(args)
        observers.append(web_monitor)

    try:
        scenario_spec = load_scenario(args.scenario)
        report = run_demo(
            inject_failure=args.inject_failure,
            planner=planner,
            memory=memory,
            observers=observers or None,
            scenario=args.scenario,
        )
        _print_report(report, scenario_spec.goal, args.verbose)
        if args.artifact_out:
            artifact_path = save_artifact(
                report,
                args.artifact_out,
                scenario=args.scenario,
            )
            print(f"artifact 已保存：{artifact_path}")
        if memory is not None:
            print(f"\n[verbose] 短期记忆事件数：{len(memory.episode())}")
    except Exception:
        if server is not None or web_monitor is not None:
            _stop_web_dashboard(server, web_monitor)
        raise

    _wait_for_dashboard_if_needed(args, server, web_monitor)
    return 0 if report.succeeded else 1


def _cmd_replay(args: argparse.Namespace) -> int:
    artifact = load_artifact(args.artifact_path)

    server = None
    if args.web:
        broadcaster, server = _start_dashboard_server(args)
        _announce_dashboard(args, server)
        publisher = threading.Thread(
            target=_publish_replay_payloads,
            args=(broadcaster, artifact, args.frame_delay),
            daemon=True,
        )
        publisher.start()

    _print_replay(artifact, args.verbose, 0.0 if args.web else args.frame_delay)
    _wait_for_dashboard_if_needed(args, server, None)
    return 0 if artifact.get("task_status") == "succeeded" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="robot-agent", description="机器人 Agent Runtime 原型 CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="运行 pick-and-place 端到端演示")
    demo.add_argument(
        "--planner", default="mock", choices=["mock", "llm"], help="任务分解器"
    )
    demo.add_argument(
        "--scenario",
        default=DEFAULT_SCENARIO,
        help="选择内置演示场景",
    )
    demo.add_argument(
        "--list-scenarios",
        action="store_true",
        help="列出可用场景并退出",
    )
    demo.add_argument(
        "--inject-failure", action="store_true", help="注入一次抓取故障以演示恢复"
    )
    demo.add_argument(
        "--artifact-out",
        help="把本次运行结果保存为 artifact JSON 文件",
    )
    demo.add_argument(
        "--llm-fallback",
        default="allow",
        choices=["allow", "strict"],
        help="LLM 规划失败时的策略（仅对 --planner llm 生效）",
    )
    demo.add_argument("--verbose", action="store_true", help="打印世界快照与记忆")
    demo.add_argument(
        "--watch", action="store_true", help="启用终端实时可视化上位机监控"
    )
    demo.add_argument(
        "--web", action="store_true", help="启用 Web 图形界面上位机（浏览器查看）"
    )
    demo.add_argument("--port", type=int, default=8000, help="Web 仪表盘端口")
    demo.add_argument("--open", action="store_true", help="自动在默认浏览器打开仪表盘")
    demo.add_argument(
        "--frame-delay",
        type=float,
        default=0.6,
        help="上位机每帧停留秒数（配合 --watch / --web）",
    )
    demo.set_defaults(func=_cmd_demo)

    replay = sub.add_parser("replay", help="回放已保存的 artifact 结果")
    replay.add_argument("artifact_path", help="artifact JSON 文件路径")
    replay.add_argument(
        "--frame-delay",
        type=float,
        default=0.0,
        help="逐步回放时每步暂停秒数",
    )
    replay.add_argument("--verbose", action="store_true", help="打印计划历史")
    replay.add_argument(
        "--web", action="store_true", help="启用 Web 图形界面展示 artifact 回放"
    )
    replay.add_argument("--port", type=int, default=8000, help="Web 仪表盘端口")
    replay.add_argument(
        "--open", action="store_true", help="自动在默认浏览器打开仪表盘"
    )
    replay.set_defaults(func=_cmd_replay)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
