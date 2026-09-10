"""命令行入口。

用法：
    python -m robot_agent.cli demo [--planner mock|llm] [--inject-failure] [--verbose]
    python -m robot_agent.cli demo --web [--port 8000] [--open]   # Web 图形界面上位机
    python -m robot_agent.cli demo --watch                        # 终端实时可视化

打印完整闭环执行轨迹：目标、分解与每步状态、异常恢复过程、终态验证结果。
"""

from __future__ import annotations

import argparse
import sys
import threading

from robot_agent.demo.pick_and_place import DEFAULT_GOAL, run_demo
from robot_agent.memory.memory import Memory
from robot_agent.planning.base import Planner
from robot_agent.runtime.agent_runtime import RunReport

_STATUS_ICON = {"ok": "✅", "failed": "❌"}


def _make_planner(name: str) -> Planner:
    """按名称构造规划器。llm 分解器为可选能力，延迟导入。"""
    if name == "mock":
        from robot_agent.planning.mock_planner import MockPlanner

        return MockPlanner()
    if name == "llm":
        from robot_agent.planning.llm_planner import LLMPlanner

        return LLMPlanner()
    raise SystemExit(f"未知的 planner：{name}（可选 mock / llm）")


def _print_report(report: RunReport, goal: str, verbose: bool) -> None:
    print(f"目标：{goal}")
    print(f"任务状态：{report.task.status.value}"
          + (f"（{report.task.error}）" if report.task.error else ""))
    print(f"重规划次数：{report.replans}")
    print("执行轨迹：")
    for i, rec in enumerate(report.trace, 1):
        icon = _STATUS_ICON.get(rec.status, "•")
        retry = f" [重试#{rec.attempt}]" if rec.attempt > 0 else ""
        print(f"  {i:>2}. {icon} {rec.skill}{retry} — {rec.message}")
    cube = report.world.get("red_cube")
    where = cube.in_container if cube and cube.in_container else "（未入箱）"
    print(f"终态：red_cube 所在容器 = {where}；机械臂持有 = {report.world.holding}")
    print("结果：成功 ✅" if report.succeeded else "结果：失败 ❌")
    if verbose:
        print("\n[verbose] 世界物体快照：")
        for oid in sorted(report.world.objects):
            info = report.world.get(oid)
            print(
                f"  - {oid}: pose=({info.pose.x},{info.pose.y}) "
                f"color={info.color} in_container={info.in_container}"
            )


def _cmd_demo(args: argparse.Namespace) -> int:
    planner = _make_planner(args.planner)
    memory = Memory() if args.verbose else None
    observers: list[object] = []

    if args.watch:
        from robot_agent.display.terminal import TerminalMonitor

        observers.append(TerminalMonitor(step_delay=args.frame_delay))

    server = None
    if args.web:
        from robot_agent.display.web import DashboardServer, EventBroadcaster, WebMonitor

        broadcaster = EventBroadcaster()
        server = DashboardServer(broadcaster, port=args.port)
        server.start()
        print(f"上位机仪表盘已启动：{server.url}")
        observers.append(WebMonitor(broadcaster, min_interval=args.frame_delay))
        if args.open:
            import webbrowser

            try:
                webbrowser.open(server.url)
            except Exception:  # noqa: BLE001 - 打开浏览器失败不影响服务
                pass

    report = run_demo(
        inject_failure=args.inject_failure,
        planner=planner,
        memory=memory,
        observers=observers or None,
    )
    _print_report(report, DEFAULT_GOAL, args.verbose)
    if memory is not None:
        print(f"\n[verbose] 短期记忆事件数：{len(memory.episode())}")

    if server is not None:
        print(f"\n仪表盘持续服务中：{server.url}  （按 Ctrl+C 退出）")
        try:
            threading.Event().wait()  # 阻塞，保持服务以便浏览器查看/回放
        except KeyboardInterrupt:
            print("\n正在关闭仪表盘…")
        finally:
            server.stop()
    return 0 if report.succeeded else 1


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
        "--inject-failure", action="store_true", help="注入一次抓取故障以演示恢复"
    )
    demo.add_argument("--verbose", action="store_true", help="打印世界快照与记忆")
    demo.add_argument(
        "--watch", action="store_true", help="启用终端实时可视化上位机监控"
    )
    demo.add_argument(
        "--web", action="store_true", help="启用 Web 图形界面上位机（浏览器查看）"
    )
    demo.add_argument("--port", type=int, default=8000, help="Web 仪表盘端口")
    demo.add_argument(
        "--open", action="store_true", help="自动在默认浏览器打开仪表盘"
    )
    demo.add_argument(
        "--frame-delay",
        type=float,
        default=0.6,
        help="上位机每帧停留秒数（配合 --watch / --web）",
    )
    demo.set_defaults(func=_cmd_demo)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
