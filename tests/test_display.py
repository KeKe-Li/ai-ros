"""上位机显示测试：事件流订阅、纯渲染函数与终端监控输出。"""

from __future__ import annotations

import io

from robot_agent.backends.sim_backend import SimBackend
from robot_agent.core.types import Pose
from robot_agent.display.terminal import TerminalMonitor, render_frame
from robot_agent.planning.mock_planner import MockPlanner
from robot_agent.runtime.agent_runtime import AgentRuntime
from robot_agent.runtime.events import RuntimeEvent
from robot_agent.skills import default_skill_manager
from robot_agent.world.grid_world import build_pick_and_place_world

GOAL = "把红色方块放到箱子里"


class _Recorder:
    """记录所有收到的事件，用于验证事件流。"""

    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    def on_event(self, event: RuntimeEvent) -> None:
        self.events.append(event)


def _run_with(observer, **kw):
    grid, world = build_pick_and_place_world(**kw)
    runtime = AgentRuntime(
        SimBackend(grid), default_skill_manager(), MockPlanner(), observers=[observer]
    )
    return runtime.run(GOAL, world)


def test_runtime_emits_event_stream():
    # Arrange
    rec = _Recorder()

    # Act
    _run_with(rec)

    # Assert：首尾事件齐全，且每个技能步骤都有事件
    kinds = [e.kind for e in rec.events]
    assert kinds[0] == "task_started"
    assert kinds[-1] == "task_finished"
    assert kinds.count("step_result") == 5
    # 事件自带世界快照
    assert all(e.world is not None for e in rec.events)


def test_event_stream_includes_replan_on_persistent_failure():
    # Arrange：持续抓取失败会触发重规划事件
    rec = _Recorder()
    grid, world = build_pick_and_place_world(fail_actions={"grasp": 100})
    runtime = AgentRuntime(
        SimBackend(grid),
        default_skill_manager(),
        MockPlanner(),
        observers=[rec],
        max_retries=0,
        max_replans=1,
    )

    # Act
    runtime.run(GOAL, world)

    # Assert
    assert any(e.kind == "replan" for e in rec.events)


def test_render_frame_shows_grid_and_status():
    # Arrange
    _, world = build_pick_and_place_world()
    event = RuntimeEvent("task_started", world=world, goal=GOAL)

    # Act
    frame = render_frame(event)

    # Assert：含目标、机器人符号与图例
    assert GOAL in frame
    assert "R" in frame
    assert "图例" in frame
    # 机器人在原点，首个数据行应以 R 开头
    assert "│ R " in frame


def test_render_frame_marks_holding_after_grasp():
    # Arrange：机器人持有方块
    _, world = build_pick_and_place_world()
    world = world.with_holding("red_cube")
    event = RuntimeEvent("step_result", world=world, goal=GOAL)

    # Act
    frame = render_frame(event)

    # Assert
    assert "持有物：red_cube" in frame


def test_terminal_monitor_writes_frames_to_stream():
    # Arrange：注入自定义流，关闭清屏与延时
    buffer = io.StringIO()
    monitor = TerminalMonitor(step_delay=0.0, stream=buffer, clear=False)

    # Act
    _run_with(monitor)
    output = buffer.getvalue()

    # Assert：输出包含多帧监控画面与最终状态
    assert output.count("上位机监控") >= 5
    assert "任务状态：succeeded" in output


def test_broken_observer_does_not_crash_runtime():
    # Arrange：观察者抛异常不应拖垮运行时
    class _Broken:
        def on_event(self, event):
            raise RuntimeError("显示端崩溃")

    grid, world = build_pick_and_place_world()
    runtime = AgentRuntime(
        SimBackend(grid), default_skill_manager(), MockPlanner(), observers=[_Broken()]
    )

    # Act
    report = runtime.run(GOAL, world)

    # Assert：机器人任务仍正常完成
    assert report.succeeded
