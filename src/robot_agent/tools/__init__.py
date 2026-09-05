"""工具调用（Tool Calling）：注册纯信息/计算型工具。

与 Skill 的边界：Tool 不产生物理动作（只读世界或纯计算），Skill 才通过
RobotBackend 执行物理动作。工具供 Planner/Agent 查询信息、辅助决策。
"""

from robot_agent.tools.registry import Tool, ToolRegistry, default_tool_registry

__all__ = ["Tool", "ToolRegistry", "default_tool_registry"]
