"""实体 ID、别名、边界和歧义解析测试。"""

from __future__ import annotations

import pytest

from robot_agent.core.errors import PlanningError
from robot_agent.core.types import Pose
from robot_agent.planning.entity_resolver import EntityResolver
from robot_agent.planning.goal import parse_goal
from robot_agent.world.state import ObjectInfo, build_world


def _world():
    return build_world(
        Pose(0, 0),
        {
            "red_cube": ObjectInfo(
                Pose(1, 1), color="red", is_graspable=True, aliases=("红方块",)
            ),
            "box": ObjectInfo(Pose(2, 2), is_container=True, aliases=("收纳箱",)),
        },
    )


def test_resolver_matches_complete_id_and_alias():
    world = _world()
    resolver = EntityResolver(world)

    assert resolver.resolve("把 red_cube 放好", ["red_cube"], "物体") == "red_cube"
    assert resolver.resolve("放入收纳箱", ["box"], "容器") == "box"


def test_resolver_does_not_match_ascii_id_inside_larger_word():
    world = _world()

    with pytest.raises(PlanningError, match="容器/放置意图"):
        parse_goal("把 red_cube 放到 sandbox 里", world)


def test_resolver_rejects_ambiguous_alias():
    world = build_world(
        Pose(0, 0),
        {
            "box_a": ObjectInfo(Pose(1, 1), is_container=True, aliases=("箱子",)),
            "box_b": ObjectInfo(Pose(2, 2), is_container=True, aliases=("箱子",)),
        },
    )

    with pytest.raises(PlanningError, match="多个候选容器"):
        EntityResolver(world).resolve("放到箱子", ["box_a", "box_b"], "容器")
