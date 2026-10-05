"""领域异常定义。

在系统边界快速失败并给出清晰信息，避免静默吞掉错误。
"""

from __future__ import annotations


class RobotAgentError(Exception):
    """框架内所有异常的基类。"""


class UnknownSkillError(RobotAgentError):
    """请求调用了未注册的技能。"""


class PlanningError(RobotAgentError):
    """规划器无法从目标生成有效计划。"""


class SchedulingError(RobotAgentError):
    """计划步骤存在循环依赖或非法依赖，无法调度。"""


class BackendNotAvailableError(RobotAgentError):
    """请求的机器人执行后端在当前环境不可用（如 ROS2 未安装）。"""


class OutputResolutionError(RobotAgentError):
    """计划步骤引用的上游输出不存在、路径无效或值不符合预期。"""


class MemoryCorruptionError(RobotAgentError):
    """长期记忆文件损坏或根结构不合法。"""


class PlanningStageFailure(PlanningError):
    """规划准备流水线在明确阶段失败。"""

    def __init__(self, stage: str, cause: Exception):
        self.stage = stage
        self.cause = cause
        super().__init__(f"{stage}（{type(cause).__name__}）：{cause}")
