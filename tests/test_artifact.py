"""运行结果 artifact 读写测试。"""

from __future__ import annotations

import pytest

from robot_agent.core import io as io_module
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


def test_save_artifact_cleans_temporary_file_when_write_fails(tmp_path, monkeypatch):
    # Arrange：写入阶段失败，验证不残留临时文件、不生成目标文件
    report = run_demo(scenario="pick_and_place_basic")
    artifact_path = tmp_path / "basic.json"
    original_create = io_module.tempfile.NamedTemporaryFile

    def create_failing_file(*args, **kwargs):
        handle = original_create(*args, **kwargs)
        monkeypatch.setattr(
            handle, "write", lambda *a: (_ for _ in ()).throw(OSError("写入失败"))
        )
        return handle

    monkeypatch.setattr(io_module.tempfile, "NamedTemporaryFile", create_failing_file)

    # Act / Assert
    with pytest.raises(OSError, match="写入失败"):
        save_artifact(report, artifact_path, scenario="pick_and_place_basic")

    assert not artifact_path.exists()
    assert list(tmp_path.iterdir()) == []
