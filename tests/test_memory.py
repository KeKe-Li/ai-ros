"""记忆模块测试：短期事件流与长期 KV 存储（含持久化）。"""

from __future__ import annotations

from robot_agent.memory.memory import Memory


def test_short_term_record_and_episode():
    # Arrange
    mem = Memory()

    # Act
    mem.record("step", skill="grasp", passed=True)
    mem.record("step", skill="place", passed=True)

    # Assert
    events = mem.episode()
    assert [e.kind for e in events] == ["step", "step"]
    assert events[0].fields["skill"] == "grasp"


def test_recent_returns_tail_and_copy():
    # Arrange
    mem = Memory()
    for i in range(5):
        mem.record("step", i=i)

    # Act
    recent = mem.recent(2)

    # Assert
    assert [e.fields["i"] for e in recent] == [3, 4]
    assert mem.recent(0) == []
    # episode 返回副本，外部修改不影响内部
    recent.clear()
    assert len(mem.episode()) == 5


def test_clear_episode():
    # Arrange
    mem = Memory()
    mem.record("x")

    # Act
    mem.clear_episode()

    # Assert
    assert mem.episode() == []


def test_long_term_store_and_recall_in_memory():
    # Arrange
    mem = Memory()

    # Act
    mem.store("last_goal", "把红色方块放到箱子里")

    # Assert
    assert mem.recall("last_goal") == "把红色方块放到箱子里"
    assert mem.recall("missing", default=0) == 0


def test_long_term_persists_to_file(tmp_path):
    # Arrange
    path = tmp_path / "ltm.json"
    mem = Memory(store_path=path)

    # Act
    mem.store("success_count", 3)

    # Assert：新实例可从文件恢复
    assert path.exists()
    reloaded = Memory(store_path=path)
    assert reloaded.recall("success_count") == 3
