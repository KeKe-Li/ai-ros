from __future__ import annotations

from robot_agent.scenarios.builtin import builtin_scenarios
from robot_agent.scenarios.models import ScenarioSpec
from robot_agent.world.grid_world import GridWorld, build_grid_world
from robot_agent.world.state import ObjectInfo, WorldState


def load_scenario(name: str) -> ScenarioSpec:
    scenarios = builtin_scenarios()
    try:
        return scenarios[name]
    except KeyError as exc:
        known = ", ".join(sorted(scenarios))
        raise ValueError(f"未知场景：{name}；可选：{known}") from exc


def list_scenarios() -> list[ScenarioSpec]:
    scenarios = builtin_scenarios()
    return [scenarios[name] for name in sorted(scenarios)]


def build_world_from_scenario(spec: ScenarioSpec) -> tuple[GridWorld, WorldState]:
    objects = {
        item.object_id: ObjectInfo(
            pose=item.pose,
            color=item.color,
            is_graspable=item.is_graspable,
            is_container=item.is_container,
            in_container=item.in_container,
            aliases=item.aliases,
        )
        for item in spec.objects
    }
    return build_grid_world(
        width=spec.width,
        height=spec.height,
        objects=objects,
        robot_pose=spec.robot_pose,
        fail_actions=spec.fail_actions,
    )
