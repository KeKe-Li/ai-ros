from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from robot_agent.core.types import Pose


@dataclass(frozen=True)
class ScenarioObject:
    object_id: str
    pose: Pose
    color: str | None = None
    is_graspable: bool = False
    is_container: bool = False
    in_container: str | None = None
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "aliases", tuple(self.aliases))


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    description: str
    goal: str
    width: int
    height: int
    robot_pose: Pose = Pose(0, 0)
    objects: tuple[ScenarioObject, ...] = ()
    fail_actions: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "objects", tuple(self.objects))
        object.__setattr__(self, "fail_actions", dict(self.fail_actions))
