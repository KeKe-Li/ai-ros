"""端到端演示测试：完整闭环、失败注入恢复、CLI 入口与退出码。"""

from __future__ import annotations

from robot_agent.cli import main
from robot_agent.demo.pick_and_place import DEFAULT_GOAL, run_demo
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
