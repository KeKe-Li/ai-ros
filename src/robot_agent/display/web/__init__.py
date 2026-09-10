"""Web 上位机仪表盘（只读监控）。

作为运行时事件总线的又一个订阅者接入，**不改动 RuntimeObserver/RuntimeEvent**：
    AgentRuntime ──emit──▶ WebMonitor ──▶ EventBroadcaster ──SSE──▶ 浏览器仪表盘

仅使用标准库（http.server + Server-Sent Events），零外部依赖、离线可运行。
"""

from robot_agent.display.web.broadcaster import EventBroadcaster
from robot_agent.display.web.serializer import event_to_dict
from robot_agent.display.web.server import DashboardServer, WebMonitor

__all__ = ["EventBroadcaster", "event_to_dict", "DashboardServer", "WebMonitor"]
