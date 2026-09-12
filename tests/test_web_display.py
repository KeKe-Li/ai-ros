"""Web 上位机测试：事件序列化、广播器、WebMonitor 与 HTTP 端点（真实请求）。"""

from __future__ import annotations

import json
import urllib.request

from robot_agent.backends.sim_backend import SimBackend
from robot_agent.display.web import (
    DashboardServer,
    EventBroadcaster,
    WebMonitor,
    event_to_dict,
)
from robot_agent.planning.mock_planner import MockPlanner
from robot_agent.runtime.agent_runtime import AgentRuntime
from robot_agent.runtime.events import RuntimeEvent, StepRecord
from robot_agent.skills import default_skill_manager
from robot_agent.world.grid_world import build_pick_and_place_world

GOAL = "把红色方块放到箱子里"


def _sample_event(kind="task_started"):
    _, world = build_pick_and_place_world()
    return RuntimeEvent(
        kind,
        world=world,
        goal=GOAL,
        step=StepRecord("grasp", {"object_id": "red_cube"}, "ok", "已抓取", 0),
    )


def test_event_to_dict_serializes_world_and_step():
    # Arrange / Act
    payload = event_to_dict(_sample_event())

    # Assert：世界结构化，非字符串拼接
    world = payload["world"]
    assert world["width"] == 9 and world["height"] == 6
    assert world["robot"] == {"x": 0, "y": 0}
    ids = {o["id"] for o in world["objects"]}
    assert {"red_cube", "box", "table"} <= ids
    assert payload["step"]["skill"] == "grasp"
    assert payload["step"]["step_id"] == ""
    # 整体可 JSON 序列化
    assert json.loads(json.dumps(payload))["goal"] == GOAL


def test_broadcaster_delivers_to_subscribers():
    # Arrange
    bus = EventBroadcaster()
    q = bus.subscribe()

    # Act
    bus.publish({"kind": "x"})

    # Assert
    assert q.get_nowait() == {"kind": "x"}


def test_broadcaster_replays_history_to_late_subscriber():
    # Arrange：先发布再订阅
    bus = EventBroadcaster()
    bus.publish({"n": 1})
    bus.publish({"n": 2})

    # Act
    q = bus.subscribe()

    # Assert：历史被回放
    assert q.get_nowait() == {"n": 1}
    assert q.get_nowait() == {"n": 2}
    assert bus.latest() == {"n": 2}


def test_unsubscribe_stops_delivery():
    # Arrange
    bus = EventBroadcaster()
    q = bus.subscribe()

    # Act
    bus.unsubscribe(q)
    bus.publish({"k": 1})

    # Assert
    assert bus.subscriber_count() == 0
    assert q.empty()


def test_web_monitor_publishes_full_run():
    # Arrange
    bus = EventBroadcaster()
    grid, world = build_pick_and_place_world()
    runtime = AgentRuntime(
        SimBackend(grid),
        default_skill_manager(),
        MockPlanner(),
        observers=[WebMonitor(bus)],
    )

    # Act
    runtime.run(GOAL, world)

    # Assert：历史含首尾事件与 5 个步骤事件
    kinds = [e["kind"] for e in bus.history()]
    assert kinds[0] == "task_started"
    assert kinds[-1] == "task_finished"
    assert kinds.count("step_result") == 5


def _serve(bus):
    server = DashboardServer(bus, port=0)  # 0 = 由系统分配空闲端口
    server.start()
    return server


def test_http_serves_dashboard_page():
    # Arrange
    bus = EventBroadcaster()
    server = _serve(bus)
    try:
        # Act
        with urllib.request.urlopen(server.url, timeout=5) as resp:
            body = resp.read().decode("utf-8")
            ctype = resp.headers.get("Content-Type", "")

        # Assert
        assert resp.status == 200
        assert "text/html" in ctype
        assert "上位机监控" in body
        assert "EventSource" in body
    finally:
        server.stop()


def test_http_state_returns_latest_event_json():
    # Arrange
    bus = EventBroadcaster()
    bus.publish(event_to_dict(_sample_event()))
    server = _serve(bus)
    try:
        # Act
        with urllib.request.urlopen(server.url + "state", timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))

        # Assert
        assert payload["goal"] == GOAL
        assert payload["world"]["robot"] == {"x": 0, "y": 0}
    finally:
        server.stop()


def test_http_events_streams_sse():
    # Arrange：先放一条历史事件，订阅后应立即回放
    bus = EventBroadcaster()
    bus.publish(event_to_dict(_sample_event()))
    server = _serve(bus)
    try:
        # Act：读取 SSE 首个 data 行
        with urllib.request.urlopen(server.url + "events", timeout=5) as resp:
            assert "text/event-stream" in resp.headers.get("Content-Type", "")
            data_line = None
            for _ in range(10):
                raw = resp.readline().decode("utf-8").strip()
                if raw.startswith("data:"):
                    data_line = raw[len("data:"):].strip()
                    break

        # Assert
        assert data_line is not None
        assert json.loads(data_line)["goal"] == GOAL
    finally:
        server.stop()
