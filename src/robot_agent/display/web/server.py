"""仪表盘 HTTP 服务与 WebMonitor 观察者。

WebMonitor 实现 RuntimeObserver：把事件序列化后交给 EventBroadcaster 广播。
DashboardServer 基于标准库 ThreadingHTTPServer 提供三个端点：
    GET /        仪表盘页面（内嵌 HTML）
    GET /events  SSE 事件流（实时 + 历史回放）
    GET /state   最近一条事件快照（JSON）
"""

from __future__ import annotations

import json
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from robot_agent.display.web.broadcaster import EventBroadcaster
from robot_agent.display.web.dashboard_html import DASHBOARD_HTML
from robot_agent.display.web.serializer import event_to_dict
from robot_agent.runtime.events import RuntimeEvent

# SSE 队列等待超时；超时后发送心跳注释，避免连接被中间层判定为空闲断开
_SSE_POLL_SECONDS = 1.0


class WebMonitor:
    """把运行时事件推送到浏览器的观察者（实现 RuntimeObserver）。

    min_interval 用于在实时演示时放慢节奏，让浏览器看清闭环推进（默认 0 不节流）。
    """

    def __init__(self, broadcaster: EventBroadcaster, min_interval: float = 0.0) -> None:
        self._broadcaster = broadcaster
        self._min_interval = min_interval

    def on_event(self, event: RuntimeEvent) -> None:
        self._broadcaster.publish(event_to_dict(event))
        if self._min_interval > 0:
            time.sleep(self._min_interval)


def _make_handler(broadcaster: EventBroadcaster) -> type[BaseHTTPRequestHandler]:
    """构造绑定到指定广播器的请求处理器类。"""

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:  # 静默默认访问日志
            pass

        def do_GET(self) -> None:  # noqa: N802 - 基类要求的方法名
            if self.path in ("/", "/index.html"):
                self._send_html(DASHBOARD_HTML)
            elif self.path == "/state":
                self._send_json(broadcaster.latest() or {})
            elif self.path == "/events":
                self._stream_events()
            else:
                self.send_error(404, "Not Found")

        def _send_html(self, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, obj: object) -> None:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _stream_events(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            q = broadcaster.subscribe()
            try:
                while True:
                    try:
                        item = q.get(timeout=_SSE_POLL_SECONDS)
                        data = json.dumps(item, ensure_ascii=False)
                        self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")  # 心跳
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass  # 客户端断开，正常退出
            finally:
                broadcaster.unsubscribe(q)

    return _Handler


class DashboardServer:
    """后台线程运行的仪表盘 HTTP 服务。"""

    def __init__(
        self,
        broadcaster: EventBroadcaster,
        host: str = "127.0.0.1",
        port: int = 8000,
    ) -> None:
        self._httpd = ThreadingHTTPServer((host, port), _make_handler(broadcaster))
        self._httpd.daemon_threads = True
        self._thread: threading.Thread | None = None

    @property
    def address(self) -> tuple[str, int]:
        return self._httpd.server_address  # type: ignore[return-value]

    @property
    def url(self) -> str:
        host, port = self.address
        return f"http://{host}:{port}/"

    def start(self) -> None:
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
