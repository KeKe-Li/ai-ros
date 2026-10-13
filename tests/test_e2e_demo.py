"""端到端演示测试：完整闭环、失败注入恢复、CLI 入口与退出码。"""

from __future__ import annotations

import types

import pytest

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


def test_start_web_dashboard_stops_server_when_monitor_init_raises(monkeypatch):
    from robot_agent import cli

    calls = []

    class _FakeServer:
        url = "http://127.0.0.1:8123/"

        def __init__(self, broadcaster, port):
            self.started = False

        def start(self):
            self.started = True
            calls.append("server.start")

        def stop(self):
            calls.append("server.stop")

    def _boom(*args, **kwargs):
        raise RuntimeError("monitor exploded")

    monkeypatch.setattr(cli, "DashboardServer", _FakeServer)
    monkeypatch.setattr(cli, "WebMonitor", _boom)

    with pytest.raises(RuntimeError, match="monitor exploded"):
        cli._start_web_dashboard(
            types.SimpleNamespace(port=8123, frame_delay=0.1, open=False)
        )

    assert calls == ["server.start", "server.stop"]


def test_start_web_dashboard_does_not_print_started_message_when_monitor_init_raises(
    monkeypatch, capsys
):
    from robot_agent import cli

    calls = []

    class _FakeServer:
        url = "http://127.0.0.1:8123/"

        def __init__(self, broadcaster, port):
            self.started = False

        def start(self):
            self.started = True
            calls.append("server.start")

        def stop(self):
            calls.append("server.stop")

    def _boom(*args, **kwargs):
        raise RuntimeError("monitor exploded")

    monkeypatch.setattr(cli, "DashboardServer", _FakeServer)
    monkeypatch.setattr(cli, "WebMonitor", _boom)

    with pytest.raises(RuntimeError, match="monitor exploded"):
        cli._start_web_dashboard(
            types.SimpleNamespace(port=8123, frame_delay=0.1, open=False)
        )

    out = capsys.readouterr().out
    assert "上位机仪表盘已启动" not in out
    assert calls == ["server.start", "server.stop"]


def test_cmd_demo_stops_web_resources_when_run_demo_raises(monkeypatch):
    from robot_agent import cli

    calls = []

    class _FakeServer:
        url = "http://127.0.0.1:8123/"

        def stop(self):
            calls.append("server.stop")

    class _FakeMonitor:
        def stop(self):
            calls.append("monitor.stop")

    monkeypatch.setattr(
        cli,
        "_start_web_dashboard",
        lambda args: (_FakeServer(), _FakeMonitor()),
    )
    monkeypatch.setattr(
        cli,
        "run_demo",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("demo exploded")),
    )

    with pytest.raises(RuntimeError, match="demo exploded"):
        cli._cmd_demo(
            types.SimpleNamespace(
                planner="mock",
                verbose=False,
                watch=False,
                web=True,
                inject_failure=False,
                frame_delay=0.1,
                port=8123,
                open=False,
                llm_fallback="allow",
                scenario="pick_and_place_basic",
                list_scenarios=False,
                artifact_out=None,
            )
        )

    assert calls == ["monitor.stop", "server.stop"]


def test_cmd_demo_stops_web_resources_when_print_report_raises(monkeypatch):
    from robot_agent import cli

    calls = []

    class _FakeServer:
        url = "http://127.0.0.1:8123/"

        def stop(self):
            calls.append("server.stop")

    class _FakeMonitor:
        def stop(self):
            calls.append("monitor.stop")

    monkeypatch.setattr(
        cli,
        "_start_web_dashboard",
        lambda args: (_FakeServer(), _FakeMonitor()),
    )
    monkeypatch.setattr(
        cli,
        "run_demo",
        lambda **kwargs: types.SimpleNamespace(succeeded=True),
    )
    monkeypatch.setattr(
        cli,
        "_print_report",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("print exploded")),
    )

    with pytest.raises(RuntimeError, match="print exploded"):
        cli._cmd_demo(
            types.SimpleNamespace(
                planner="mock",
                verbose=False,
                watch=False,
                web=True,
                inject_failure=False,
                frame_delay=0.1,
                port=8123,
                open=False,
                llm_fallback="allow",
                scenario="pick_and_place_basic",
                list_scenarios=False,
                artifact_out=None,
            )
        )

    assert calls == ["monitor.stop", "server.stop"]


def test_cmd_demo_stops_web_resources_when_verbose_output_raises(monkeypatch):
    from robot_agent import cli

    calls = []

    class _FakeServer:
        url = "http://127.0.0.1:8123/"

        def stop(self):
            calls.append("server.stop")

    class _FakeMonitor:
        def stop(self):
            calls.append("monitor.stop")

    class _FakeMemory:
        def episode(self):
            raise RuntimeError("verbose exploded")

    monkeypatch.setattr(
        cli,
        "_start_web_dashboard",
        lambda args: (_FakeServer(), _FakeMonitor()),
    )
    monkeypatch.setattr(cli, "Memory", lambda: _FakeMemory())
    monkeypatch.setattr(
        cli,
        "run_demo",
        lambda **kwargs: types.SimpleNamespace(succeeded=True),
    )
    monkeypatch.setattr(cli, "_print_report", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        cli, "_wait_for_dashboard_if_needed", lambda *args, **kwargs: None
    )

    with pytest.raises(RuntimeError, match="verbose exploded"):
        cli._cmd_demo(
            types.SimpleNamespace(
                planner="mock",
                verbose=True,
                watch=False,
                web=True,
                inject_failure=False,
                frame_delay=0.1,
                port=8123,
                open=False,
                llm_fallback="allow",
                scenario="pick_and_place_basic",
                list_scenarios=False,
                artifact_out=None,
            )
        )

    assert calls == ["monitor.stop", "server.stop"]


def test_cmd_demo_web_success_path_stops_resources_only_once(monkeypatch):
    from robot_agent import cli

    calls = []

    class _FakeServer:
        url = "http://127.0.0.1:8123/"

        def stop(self):
            calls.append("server.stop")

    class _FakeMonitor:
        def stop(self):
            calls.append("monitor.stop")

    monkeypatch.setattr(
        cli,
        "_start_web_dashboard",
        lambda args: (_FakeServer(), _FakeMonitor()),
    )
    monkeypatch.setattr(
        cli,
        "run_demo",
        lambda **kwargs: types.SimpleNamespace(succeeded=True),
    )
    monkeypatch.setattr(cli, "_print_report", lambda *args, **kwargs: None)

    def _fake_wait(args, server, web_monitor):
        cli._stop_web_dashboard(server, web_monitor)

    monkeypatch.setattr(cli, "_wait_for_dashboard_if_needed", _fake_wait)

    code = cli._cmd_demo(
        types.SimpleNamespace(
            planner="mock",
            verbose=False,
            watch=False,
            web=True,
            inject_failure=False,
            frame_delay=0.1,
            port=8123,
            open=False,
            llm_fallback="allow",
            scenario="pick_and_place_basic",
            list_scenarios=False,
            artifact_out=None,
        )
    )

    assert code == 0
    assert calls == ["monitor.stop", "server.stop"]


def test_demo_basic_scenario_succeeds():
    report = run_demo(scenario="pick_and_place_basic")

    assert report.succeeded
    assert report.world.get("red_cube").in_container == "box"


def test_demo_retry_once_scenario_recovers():
    report = run_demo(scenario="pick_and_place_retry_once")

    assert report.succeeded
    assert any(r.skill == "grasp" and r.status == "failed" for r in report.trace)


def test_demo_already_satisfied_succeeds_without_steps():
    report = run_demo(scenario="already_satisfied")

    assert report.succeeded
    assert report.world.get("red_cube").in_container == "box"
    assert len(report.trace) == 0


def test_demo_ambiguous_scenario_fails_cleanly():
    report = run_demo(scenario="ambiguous_red_cube")

    assert not report.succeeded
    assert report.task.error is not None
    assert "多个" in report.task.error


def test_cli_can_list_scenarios(capsys):
    code = main(["demo", "--list-scenarios"])
    out = capsys.readouterr().out

    assert code == 0
    assert "pick_and_place_basic" in out
    assert "already_satisfied" in out


def test_cli_demo_accepts_scenario(capsys):
    code = main(["demo", "--scenario", "pick_and_place_basic"])
    out = capsys.readouterr().out

    assert code == 0
    assert "结果：成功" in out
