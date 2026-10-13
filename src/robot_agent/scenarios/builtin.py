from __future__ import annotations

from robot_agent.core.types import Pose
from robot_agent.scenarios.models import ScenarioObject, ScenarioSpec


def builtin_scenarios() -> dict[str, ScenarioSpec]:
    return {
        "pick_and_place_basic": ScenarioSpec(
            name="pick_and_place_basic",
            description="标准抓取放置闭环场景",
            goal="把红色方块放到箱子里",
            width=10,
            height=10,
            robot_pose=Pose(0, 0),
            objects=(
                ScenarioObject("table", Pose(5, 5)),
                ScenarioObject("box", Pose(8, 2), color="brown", is_container=True),
                ScenarioObject("red_cube", Pose(5, 5), color="red", is_graspable=True),
            ),
        ),
        "pick_and_place_retry_once": ScenarioSpec(
            name="pick_and_place_retry_once",
            description="抓取首次失败一次，用于演示恢复",
            goal="把红色方块放到箱子里",
            width=10,
            height=10,
            robot_pose=Pose(0, 0),
            objects=(
                ScenarioObject("table", Pose(5, 5)),
                ScenarioObject("box", Pose(8, 2), color="brown", is_container=True),
                ScenarioObject("red_cube", Pose(5, 5), color="red", is_graspable=True),
            ),
            fail_actions={"grasp": 1},
        ),
        "already_satisfied": ScenarioSpec(
            name="already_satisfied",
            description="目标初始已满足",
            goal="把红色方块放到箱子里",
            width=10,
            height=10,
            robot_pose=Pose(0, 0),
            objects=(
                ScenarioObject("table", Pose(5, 5)),
                ScenarioObject("box", Pose(8, 2), color="brown", is_container=True),
                ScenarioObject(
                    "red_cube",
                    Pose(8, 2),
                    color="red",
                    is_graspable=True,
                    in_container="box",
                ),
            ),
        ),
        "ambiguous_red_cube": ScenarioSpec(
            name="ambiguous_red_cube",
            description="两个红色方块，展示歧义拒绝",
            goal="把红色方块放到箱子里",
            width=10,
            height=10,
            robot_pose=Pose(0, 0),
            objects=(
                ScenarioObject("box", Pose(8, 2), color="brown", is_container=True),
                ScenarioObject("red_cube_1", Pose(5, 5), color="red", is_graspable=True),
                ScenarioObject("red_cube_2", Pose(6, 5), color="red", is_graspable=True),
            ),
        ),
    }
