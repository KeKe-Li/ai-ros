"""技能层：标准化技能接口、技能管理器与具体技能实现。"""

from robot_agent.skills.base import Skill
from robot_agent.skills.manager import SkillManager
from robot_agent.skills.manipulation import GraspSkill, PlaceSkill
from robot_agent.skills.navigation import NavigateSkill
from robot_agent.skills.perception import DetectObjectSkill


def default_skill_manager() -> SkillManager:
    """注册全部内置技能，返回可直接使用的 SkillManager。"""
    manager = SkillManager()
    for skill in (
        NavigateSkill(),
        DetectObjectSkill(),
        GraspSkill(),
        PlaceSkill(),
    ):
        manager.register(skill)
    return manager


__all__ = [
    "Skill",
    "SkillManager",
    "NavigateSkill",
    "DetectObjectSkill",
    "GraspSkill",
    "PlaceSkill",
    "default_skill_manager",
]
