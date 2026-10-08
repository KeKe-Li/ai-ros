"""端到端演示测试：完整闭环、失败注入恢复、CLI 入口与退出码。"""

from __future__ import annotations

import types

from robot_agent.cli import main
from robot_agent.demo.pick_and_place import run_demo
from robot_agent.memory.memory import Memory


def test_demo_closed_loop_succeeds():
    # Act
    report = run_demo()

    # Assert：目标达成，机器人从起点走到桌子再到箱子
    assert report.succeeded
    assert report.world.get("red_cube").in_container == "box"
    assert report.world.holding is None
    assert [r.skill for r in report.trace] == [
        "navigate",
        "detect",
        "grasp",
        "navigate",
        "place",
    ]


def test_demo_with_injected_failure_still_recovers():
    # Act
    report = run_demo(inject_failure=True)

    # Assert：注入一次抓取故障后仍闭环成功
    assert report.succeeded
    assert report.world.get("red_cube").in_container == "box"
    failed = [r for r in report.trace if r.status == "failed"]
    assert failed and failed[0].skill == "grasp"


def test_demo_records_events_into_memory():
    # Arrange
    memory = Memory()

    # Act
    run_demo(memory=memory)

    # Assert：记录了任务开始/结束与各步骤事件
    kinds = [e.kind for e in memory.episode()]
    assert "task_started" in kinds
    assert "task_succeeded" in kinds
    assert kinds.count("step") == 5


def test_cli_demo_returns_zero_on_success():
    # Act
    code = main(["demo"])

    # Assert
    assert code == 0


def test_cli_demo_with_verbose_and_failure(capsys):
    # Act
    code = main(["demo", "--inject-failure", "--verbose"])
    out = capsys.readouterr().out

    # Assert
    assert code == 0
    assert "目标：" in out
    assert "结果：成功" in out
    assert "重试" in out  # 恢复过程可见


def test_stop_web_dashboard_is_safe_with_missing_parts():
    from robot_agent import cli

    cli._stop_web_dashboard(None, None)


def test_wait_for_dashboard_if_needed_stops_web_resources_on_keyboard_interrupt(
    monkeypatch,
):
    from robot_agent import cli

    calls = []

    class _FakeMonitor:
        def stop(self):
            calls.append("monitor.stop")

    class _FakeServer:
        url = "http://127.0.0.1:8000/"

        def stop(self):
            calls.append("server.stop")

    def _raise_keyboard_interrupt():
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_wait_forever", _raise_keyboard_interrupt)

    cli._wait_for_dashboard_if_needed(
        types.SimpleNamespace(), _FakeServer(), _FakeMonitor()
    )

    assert calls == ["monitor.stop", "server.stop"]


def test_start_web_dashboard_returns_handles_and_opens_browser(monkeypatch):
    from robot_agent import cli

    opened = []

    class _FakeServer:
        def __init__(self, broadcaster, port):
            self.url = f"http://127.0.0.1:{port}/"
            self.started = False

        def start(self):
            self.started = True

        def stop(self):
            pass

    class _FakeMonitor:
        def __init__(self, broadcaster, min_interval):
            self.broadcaster = broadcaster
            self.min_interval = min_interval

        def stop(self):
            pass

    monkeypatch.setattr(cli, "DashboardServer", _FakeServer)
    monkeypatch.setattr(cli, "WebMonitor", _FakeMonitor)
    monkeypatch.setattr(cli.webbrowser, "open", opened.append)

    server, monitor = cli._start_web_dashboard(
        types.SimpleNamespace(port=8123, frame_delay=0.25, open=True)
    )

    assert isinstance(server, _FakeServer)
    assert isinstance(monitor, _FakeMonitor)
    assert server.started is True
    assert monitor.min_interval == 0.25
    assert opened == [server.url]
