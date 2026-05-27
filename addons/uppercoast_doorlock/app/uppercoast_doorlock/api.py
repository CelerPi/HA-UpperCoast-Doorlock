from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .config import IntercomConfig


def make_api_handler(core: Any, config: IntercomConfig) -> type[BaseHTTPRequestHandler]:
    class UpperCoastDoorlockApiHandler(BaseHTTPRequestHandler):
        server_version = "UpperCoastDoorlockAPI/0.1"

        def do_GET(self) -> None:
            if self.path == "/health":
                self._write_json(200, {"ok": True})
                return
            if self.path == "/api/status":
                self._write_json(
                    200,
                    {
                        "runtime": core.frame_hub.snapshot(),
                        "config": config.as_dict(),
                    },
                )
                return
            if self.path == "/api/frame":
                frame = core.frame_hub.get_frame()
                if frame is None:
                    self._write_json(404, {"ok": False, "error": "no_frame"})
                    return
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(frame)))
                self.end_headers()
                self.wfile.write(frame)
                return
            self._write_json(404, {"ok": False, "error": "not_found"})

        def do_POST(self) -> None:
            if self.path not in ("/api/unlock", "/api/answer", "/api/hangup"):
                self._write_json(404, {"ok": False, "error": "not_found"})
                return
            if not self._authorized():
                self._write_json(403, {"ok": False, "error": "forbidden"})
                return

            body = self._read_json()
            target_ip = body.get("target_ip") or core.frame_hub.snapshot().get("target_ip")
            if not target_ip:
                self._write_json(409, {"ok": False, "error": "no_active_call"})
                return

            if self.path == "/api/unlock":
                accepted = core.request_unlock(str(target_ip))
                action = "unlock"
            elif self.path == "/api/answer":
                accepted = core.request_answer(str(target_ip))
                action = "answer"
            else:
                accepted = core.request_hangup(str(target_ip))
                action = "hangup"

            if not accepted:
                self._write_json(409, {"ok": False, "error": "request_rejected", "action": action})
                return
            self._write_json(200, {"ok": True, "action": action, "target_ip": target_ip})

        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def _authorized(self) -> bool:
            if not config.api_token:
                return False
            return self.headers.get("Authorization", "") == f"Bearer {config.api_token}"

        def _read_json(self) -> dict[str, Any]:
            content_length = int(self.headers.get("Content-Length") or 0)
            if content_length <= 0:
                return {}
            try:
                payload = self.rfile.read(content_length)
                data = json.loads(payload.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return {}
            return data if isinstance(data, dict) else {}

        def _write_json(self, status: int, body: dict[str, Any]) -> None:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return UpperCoastDoorlockApiHandler


class ApiServer:
    def __init__(self, core: Any, config: IntercomConfig) -> None:
        self.core = core
        self.config = config
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._server is not None:
            return
        handler = make_api_handler(self.core, self.config)
        self._server = ThreadingHTTPServer((self.config.api_host, self.config.api_port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, name="UpperCoastDoorlockAPI", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._server = None
        self._thread = None
