"""artifact replay 测试。"""

from __future__ import annotations

import types

from robot_agent.cli import main
from robot_agent.demo.pick_and_place import run_demo
from robot_agent.reporting import (
    build_replay_payloads,
    replay_plan_history,
    replay_trace,
    save_artifact,
)


def test_replay_helpers_return_trace_and_plan_history(tmp_path):
    report = run_demo(scenario="pick_and_place_retry_once")
    artifact_path = tmp_path / "retry.json"
    save_artifact(report, artifact_path, scenario="pick_and_place_retry_once")

    from robot_agent.reporting import load_artifact

    artifact = load_artifact(artifact_path)
    trace = replay_trace(artifact)
    plan_history = replay_plan_history(artifact)

    assert trace
    assert trace[2]["skill"] == "grasp"
    assert trace[2]["status"] == "failed"
    assert plan_history
    assert plan_history[0][0]["name"] == "navigate"


def test_build_replay_payloads_contains_plan_and_final_state(tmp_path):
    report = run_demo(scenario="pick_and_place_retry_once")
    artifact_path = tmp_path / "retry.json"
    save_artifact(report, artifact_path, scenario="pick_and_place_retry_once")

    from robot_agent.reporting import load_artifact

    artifact = load_artifact(artifact_path)
    payloads = build_replay_payloads(artifact)

    assert payloads[0]["kind"] == "task_started"
    assert payloads[0]["scenario"] == "pick_and_place_retry_once"
    assert payloads[0]["plan"]
    assert payloads[-1]["kind"] == "task_finished"
    assert payloads[-1]["world"]["objects"][1]["id"] == "red_cube"


def test_cli_replay_prints_trace_and_returns_zero_on_success(tmp_path, capsys):
    report = run_demo(scenario="pick_and_place_basic")
    artifact_path = tmp_path / "basic.json"
    save_artifact(report, artifact_path, scenario="pick_and_place_basic")

    code = main(["replay", str(artifact_path), "--verbose"])
    out = capsys.readouterr().out

    assert code == 0
    assert "执行轨迹回放" in out
    assert "计划历史" in out
    assert "pick_and_place_basic" in out


def test_cli_replay_returns_one_on_failed_artifact(tmp_path, capsys):
    report = run_demo(scenario="ambiguous_red_cube")
    artifact_path = tmp_path / "ambiguous.json"
    save_artifact(report, artifact_path, scenario="ambiguous_red_cube")

    code = main(["replay", str(artifact_path)])
    out = capsys.readouterr().out

    assert code == 1
    assert "结果：失败" in out
    assert "ambiguous_red_cube" in out


def test_cmd_replay_web_starts_dashboard_and_waits(monkeypatch, tmp_path):
    from robot_agent import cli

    report = run_demo(scenario="pick_and_place_basic")
    artifact_path = tmp_path / "basic.json"
    save_artifact(report, artifact_path, scenario="pick_and_place_basic")

    calls = []

    class _FakeServer:
        url = "http://127.0.0.1:8123/"

        def stop(self):
            calls.append("server.stop")

    class _FakeBroadcaster:
        def __init__(self):
            self.payloads = []

        def publish(self, payload):
            self.payloads.append(payload)

    broadcaster = _FakeBroadcaster()

    monkeypatch.setattr(
        cli,
        "_start_dashboard_server",
        lambda args: (broadcaster, _FakeServer()),
    )
    monkeypatch.setattr(cli, "_print_replay", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        cli,
        "_wait_for_dashboard_if_needed",
        lambda *args, **kwargs: calls.append("wait.called"),
    )

    code = cli._cmd_replay(
        types.SimpleNamespace(
            artifact_path=str(artifact_path),
            frame_delay=0.0,
            verbose=False,
            web=True,
            port=8123,
            open=False,
        )
    )

    assert code == 0
    assert "wait.called" in calls
