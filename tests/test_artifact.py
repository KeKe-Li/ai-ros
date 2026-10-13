"""运行结果 artifact 读写测试。"""

from __future__ import annotations

from robot_agent.demo.pick_and_place import run_demo
from robot_agent.reporting import build_artifact, load_artifact, save_artifact


def test_build_artifact_from_successful_run_contains_expected_fields():
    report = run_demo(scenario="pick_and_place_retry_once")

    artifact = build_artifact(report, scenario="pick_and_place_retry_once")

    assert artifact["version"] == 1
    assert artifact["goal"] == "把红色方块放到箱子里"
    assert artifact["scenario"] == "pick_and_place_retry_once"
    assert artifact["task_status"] == "succeeded"
    assert artifact["replans"] == 0
    assert artifact["initial_world"]["objects"]["red_cube"]["pose"] == {"x": 5, "y": 5}
    assert artifact["final_world"]["objects"]["red_cube"]["in_container"] == "box"
    assert artifact["trace"]
    assert artifact["plan_history"]


def test_save_and_load_artifact_round_trip(tmp_path):
    report = run_demo(scenario="pick_and_place_basic")
    artifact_path = tmp_path / "basic.json"

    saved = save_artifact(report, artifact_path, scenario="pick_and_place_basic")
    loaded = load_artifact(saved)

    assert saved == artifact_path
    assert loaded["scenario"] == "pick_and_place_basic"
    assert loaded["task_status"] == "succeeded"
    assert loaded["final_world"]["objects"]["red_cube"]["in_container"] == "box"


def test_failed_run_artifact_preserves_error(tmp_path):
    report = run_demo(scenario="ambiguous_red_cube")
    artifact_path = tmp_path / "ambiguous.json"

    save_artifact(report, artifact_path, scenario="ambiguous_red_cube")
    loaded = load_artifact(artifact_path)

    assert loaded["task_status"] == "failed"
    assert "多个" in (loaded["task_error"] or "")
    assert loaded["trace"] == []
