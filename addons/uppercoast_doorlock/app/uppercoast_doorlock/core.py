from __future__ import annotations

import errno
import socket
import threading
import time
from collections import deque
from typing import Any

from .call_state import CallStateTracker
from .config import DoorStation, IntercomConfig
from .protocol import (
    CALL_AUDIO_CHANNEL,
    MONITOR_DISCOVERY_PORT,
    MONITOR_VIDEO_DATA_OFFSET,
    TARGET_PORT,
    MonitorFrameAssembler,
    build_b700_payload,
    build_call_audio_payload,
    build_cd_payload,
    build_identity_payload,
    build_monitor_discovery_payload,
    build_monitor_request_payload,
    build_session_info_payload,
    build_unlock_payload,
    parse_call_audio_packet,
)


CALL_SESSION_SECONDS = 45.0
DEFAULT_VIDEO_DELAY = 0.65
KEEPALIVE_INTERVAL = 0.1
VIDEO_PACKET_INTERVAL = 1.0
CALL_UNLOCK_REPEAT = 8
CALL_UNLOCK_REPEAT_INTERVAL = 0.3
CALL_AUDIO_SAMPLES_PER_PACKET = 256
CALL_AUDIO_BYTES_PER_PACKET = CALL_AUDIO_SAMPLES_PER_PACKET * 2
CALL_OUTGOING_AUDIO_QUEUE_LIMIT = 96


class FrameHub:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._device: DoorStation | None = None
        self._status = "正在启动呼叫监听..."
        self._frame_id = 0
        self._frame: bytes | None = None
        self._audio_id = 0
        self._audio_chunks: list[tuple[int, bytes]] = []

    def update_status(self, status: str) -> None:
        with self._condition:
            self._status = status
            self._condition.notify_all()

    def begin_call(self, device: DoorStation) -> None:
        with self._condition:
            self._device = device
            self._frame = None
            self._audio_chunks = []
            self._status = f"检测到{device.display_name}呼叫，正在建立视频会话..."
            self._condition.notify_all()

    def publish_frame(self, jpeg: bytes) -> None:
        with self._condition:
            self._frame_id += 1
            self._frame = jpeg
            if self._device is not None:
                self._status = f"正在显示{self._device.display_name}呼叫视频"
            self._condition.notify_all()

    def publish_audio(self, pcm: bytes) -> None:
        with self._condition:
            self._audio_id += 1
            self._audio_chunks.append((self._audio_id, pcm))
            self._audio_chunks = self._audio_chunks[-200:]
            self._condition.notify_all()

    def end_call(self) -> None:
        with self._condition:
            self._device = None
            self._frame = None
            self._audio_chunks = []
            self._status = "呼叫会话已结束，继续等待下一次呼叫"
            self._condition.notify_all()

    def snapshot(self) -> dict[str, Any]:
        with self._condition:
            return {
                "status": self._status,
                "in_call": self._device is not None,
                "device_name": self._device.name if self._device else "",
                "display_name": self._device.display_name if self._device else "",
                "target_ip": self._device.target_ip if self._device else "",
                "frame_id": self._frame_id,
                "has_frame": self._frame is not None,
                "audio_id": self._audio_id,
                "has_audio": bool(self._audio_chunks),
            }

    def get_frame(self) -> bytes | None:
        with self._condition:
            return self._frame


class IntercomCore:
    def __init__(self, config: IntercomConfig, frame_hub: FrameHub | None = None) -> None:
        self.config = config
        self.frame_hub = frame_hub or FrameHub()
        self.tracker = CallStateTracker(config)
        self._unlock_requests: deque[str] = deque()
        self._answer_requests: deque[str] = deque()
        self._monitor_requests: deque[str] = deque()
        self._monitor_state: dict[str, Any] = {}
        self._outgoing_audio: deque[tuple[str, bytes]] = deque()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self.run, name="UpperCoastDoorlockCore", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def request_unlock(self, target_ip: str) -> bool:
        if not self._is_current_call(target_ip):
            return False
        with self._lock:
            self._unlock_requests.append(target_ip)
        return True

    def request_answer(self, target_ip: str) -> bool:
        if not self._is_current_call(target_ip):
            return False
        with self._lock:
            self._answer_requests.append(target_ip)
        return True

    def request_hangup(self, target_ip: str) -> bool:
        if not self._is_current_call(target_ip):
            return False
        self.frame_hub.end_call()
        return True

    def request_monitor_start(self, target_ip: str) -> bool:
        with self._lock:
            self._monitor_requests.append(target_ip)
        return True

    def request_monitor_stop(self, target_ip: str) -> bool:
        if not self._monitoring_active(target_ip):
            return False
        self.frame_hub.end_call()
        return True

    def _monitoring_active(self, target_ip: str) -> bool:
        return False

    def request_outgoing_audio(self, target_ip: str, pcm: bytes) -> bool:
        if not self._is_current_call(target_ip) or not pcm or len(pcm) % 2 != 0:
            return False

        chunks = [
            pcm[index : index + CALL_AUDIO_BYTES_PER_PACKET]
            for index in range(0, len(pcm), CALL_AUDIO_BYTES_PER_PACKET)
        ]
        with self._lock:
            for chunk in chunks:
                if len(chunk) % 2 == 0:
                    self._outgoing_audio.append((target_ip, chunk))
            while len(self._outgoing_audio) > CALL_OUTGOING_AUDIO_QUEUE_LIMIT:
                self._outgoing_audio.popleft()
        return bool(chunks)

    def run(self) -> None:
        if not self.config.active_devices:
            self.frame_hub.update_status("没有可监听的门禁配置")
            return

        state: dict[str, Any] = {"active": False}
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as discovery_sock:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as session_sock:
                    self._configure_sockets(discovery_sock, session_sock)
                    self._bind_socket(discovery_sock, (self.config.local_ip, MONITOR_DISCOVERY_PORT))
                    self._bind_socket(session_sock, (self.config.local_ip, TARGET_PORT))
                    discovery_sock.setblocking(False)
                    session_sock.settimeout(0.03)
                    self.frame_hub.update_status(
                        f"持续监听 {self.config.local_ip}:{TARGET_PORT}，等待室外机呼叫"
                    )

                    while not self._stop_event.is_set():
                        self._drain_discovery_replies(discovery_sock)
                        state = self.run_monitor_timers(state, discovery_sock, session_sock)
                        state = self.run_session_timers(state, discovery_sock, session_sock)
                        state = self.run_unlock_timers(state, session_sock)
                        state = self.run_answer_timers(state, session_sock)
                        state = self.run_outgoing_audio_timers(state, session_sock)

                        try:
                            payload, address = session_sock.recvfrom(4096)
                        except socket.timeout:
                            continue

                        state = self.handle_packet(payload, address, state, discovery_sock, session_sock)
        except Exception as exc:
            self.frame_hub.update_status(f"监听已停止：{exc}")

    def handle_packet(
        self,
        payload: bytes,
        address: tuple[str, int],
        state: dict[str, Any],
        discovery_sock: socket.socket,
        session_sock: socket.socket,
    ) -> dict[str, Any]:
        event = self.tracker.handle_packet(payload, address)
        if event is not None and event.kind == "call_started":
            if state.get("active") and state["device"] == event.device:
                state["expires_at"] = time.monotonic() + CALL_SESSION_SECONDS
                return state
            return self.start_call_session(discovery_sock, session_sock, event.device)

        if event is not None and event.kind == "call_ended":
            self.frame_hub.end_call()
            return {"active": False}

        if not state.get("active") or state["device"].target_ip != address[0]:
            return state

        audio = parse_call_audio_packet(payload)
        if audio is not None:
            state["expires_at"] = time.monotonic() + CALL_SESSION_SECONDS
            self.frame_hub.publish_audio(audio)
            return state

        jpeg = state["assembler"].add_packet(payload)
        if jpeg is not None:
            state["expires_at"] = time.monotonic() + CALL_SESSION_SECONDS
            self.frame_hub.publish_frame(jpeg)
        return state

    def start_call_session(
        self,
        discovery_sock: socket.socket,
        session_sock: socket.socket,
        device: DoorStation,
    ) -> dict[str, Any]:
        target_discovery = (device.target_ip, MONITOR_DISCOVERY_PORT)
        target_session = (device.target_ip, TARGET_PORT)

        discovery_sock.sendto(build_identity_payload(self.config.local_id), target_discovery)
        session_sock.sendto(build_cd_payload(), target_session)
        session_sock.sendto(
            build_session_info_payload(self.config.local_ip, self.config.local_id),
            target_session,
        )
        self.frame_hub.begin_call(device)

        now = time.monotonic()
        return {
            "active": True,
            "device": device,
            "assembler": MonitorFrameAssembler(),
            "second_identity_at": now + 0.2,
            "next_video_at": now + DEFAULT_VIDEO_DELAY,
            "next_keepalive_at": now,
            "expires_at": now + CALL_SESSION_SECONDS,
            "audio_sequence": 0,
        }

    def run_session_timers(
        self,
        state: dict[str, Any],
        discovery_sock: socket.socket,
        session_sock: socket.socket,
    ) -> dict[str, Any]:
        if not state.get("active"):
            return state

        now = time.monotonic()
        device = state["device"]
        target_discovery = (device.target_ip, MONITOR_DISCOVERY_PORT)
        target_session = (device.target_ip, TARGET_PORT)

        if state.get("second_identity_at") is not None and now >= state["second_identity_at"]:
            discovery_sock.sendto(build_identity_payload(self.config.local_id), target_discovery)
            state["second_identity_at"] = None

        if now >= state["next_keepalive_at"]:
            session_sock.sendto(
                build_b700_payload("b7000c00", 80, device, self.config.local_ip, self.config.local_id),
                target_session,
            )
            state["next_keepalive_at"] = now + KEEPALIVE_INTERVAL

        if now >= state["next_video_at"]:
            session_sock.sendto(
                build_b700_payload("b7000300", 96, device, self.config.local_ip, self.config.local_id),
                target_session,
            )
            state["next_video_at"] = now + VIDEO_PACKET_INTERVAL

        if now >= state["expires_at"]:
            self.frame_hub.end_call()
            return {"active": False}
        return state

    def run_unlock_timers(self, state: dict[str, Any], session_sock: socket.socket) -> dict[str, Any]:
        if not state.get("active"):
            return state

        device = state["device"]
        now = time.monotonic()
        if state.get("unlock_remaining", 0) <= 0 and self._pop_request(self._unlock_requests, device.target_ip):
            state["unlock_remaining"] = CALL_UNLOCK_REPEAT
            state["next_unlock_at"] = now

        if state.get("unlock_remaining", 0) <= 0 or now < state.get("next_unlock_at", 0):
            return state

        session_sock.sendto(
            build_unlock_payload(device, self.config.local_ip, self.config.local_id),
            (device.target_ip, TARGET_PORT),
        )
        state["unlock_remaining"] -= 1
        state["next_unlock_at"] = now + CALL_UNLOCK_REPEAT_INTERVAL
        state["expires_at"] = max(state["expires_at"], now + CALL_SESSION_SECONDS)
        return state

    def run_answer_timers(self, state: dict[str, Any], session_sock: socket.socket) -> dict[str, Any]:
        if not state.get("active"):
            return state

        device = state["device"]
        if not self._pop_request(self._answer_requests, device.target_ip):
            return state

        session_sock.sendto(
            build_b700_payload("b7000500", 80, device, self.config.local_ip, self.config.local_id),
            (device.target_ip, TARGET_PORT),
        )
        state["expires_at"] = max(state["expires_at"], time.monotonic() + CALL_SESSION_SECONDS)
        return state

    def run_outgoing_audio_timers(self, state: dict[str, Any], session_sock: socket.socket) -> dict[str, Any]:
        if not state.get("active"):
            return state

        device = state["device"]
        sent = 0
        while sent < 4:
            pcm = self._pop_audio(device.target_ip)
            if pcm is None:
                break
            state["audio_sequence"] = (state.get("audio_sequence", 0) + 1) & 0xFFFF
            session_sock.sendto(
                build_call_audio_payload(
                    device,
                    self.config.local_ip,
                    self.config.local_id,
                    state["audio_sequence"],
                    pcm,
                ),
                (device.target_ip, TARGET_PORT),
            )
            sent += 1

        if sent:
            state["expires_at"] = max(state["expires_at"], time.monotonic() + CALL_SESSION_SECONDS)
        return state

    def run_monitor_timers(
        self,
        state: dict[str, Any],
        discovery_sock: socket.socket,
        session_sock: socket.socket,
    ) -> dict[str, Any]:
        if self._monitor_requests:
            target_ip = self._monitor_requests.popleft()
            device = self._find_device_by_ip(target_ip)
            if device is not None:
                self._start_monitor_session(device, discovery_sock, session_sock)
        return state

    def _find_device_by_ip(self, target_ip: str) -> DoorStation | None:
        for device in self.config.active_devices:
            if device.target_ip == target_ip:
                return device
        return None

    def _start_monitor_session(
        self,
        device: DoorStation,
        discovery_sock: socket.socket,
        session_sock: socket.socket,
    ) -> None:
        target_discovery = (device.target_ip, MONITOR_DISCOVERY_PORT)
        target_session = (device.target_ip, TARGET_PORT)
        discovery_sock.sendto(build_monitor_discovery_payload(device), target_discovery)
        session_sock.sendto(build_monitor_request_payload(device, self.config.local_ip, self.config.local_id), target_session)
        self.frame_hub.begin_call(device)

    def _is_current_call(self, target_ip: str) -> bool:
        snapshot = self.frame_hub.snapshot()
        return bool(snapshot["in_call"] and snapshot["target_ip"] == target_ip)

    def _pop_request(self, queue: deque[str], target_ip: str) -> bool:
        with self._lock:
            try:
                queue.remove(target_ip)
            except ValueError:
                return False
        return True

    def _pop_audio(self, target_ip: str) -> bytes | None:
        with self._lock:
            for _ in range(len(self._outgoing_audio)):
                queued_target, pcm = self._outgoing_audio.popleft()
                if queued_target == target_ip:
                    return pcm
                self._outgoing_audio.append((queued_target, pcm))
        return None

    def _configure_sockets(self, discovery_sock: socket.socket, session_sock: socket.socket) -> None:
        discovery_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        discovery_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        session_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def _bind_socket(self, sock: socket.socket, address: tuple[str, int]) -> None:
        try:
            sock.bind(address)
        except OSError as exc:
            if exc.errno == errno.EADDRINUSE:
                raise RuntimeError(f"{address[0]}:{address[1]} 已被占用，请先关闭旧监听程序。") from exc
            if exc.errno == errno.EADDRNOTAVAIL:
                raise RuntimeError(f"本机 IP {address[0]} 不在当前网卡上，请检查 HA 网络配置。") from exc
            raise

    def _drain_discovery_replies(self, discovery_sock: socket.socket) -> None:
        while True:
            try:
                discovery_sock.recvfrom(2048)
            except BlockingIOError:
                return
