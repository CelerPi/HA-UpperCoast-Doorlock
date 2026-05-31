#!/usr/bin/env python3
"""
============================================================
麦驰可视对讲 - 门口机呼入测试脚本 (Scapy 伪造源 IP 版)
============================================================

功能：模拟门口机呼叫室内机，测试 Home Assistant 能否弹出呼叫弹窗。

原理：
  使用 scapy 伪造 UDP 包的源 IP 为真实门口机 IP，绕过 Addon 的源 IP 校验。
  无需修改 Addon 配置，无需注册 MacBook IP。

网络要求：
  - MacBook 和 HA 主机在同一个二层网络（同一交换机/VLAN）
  - 因为伪造源 IP 需要操作系统支持，MacBook 必须能直接访问目标网段

安装依赖：
  pip3 install scapy
  brew install ffmpeg   # 可选，用于生成动态测试画面或读取视频文件

用法：
  sudo python3 test_call_spoof.py
  sudo python3 test_call_spoof.py --duration 60
  sudo python3 test_call_spoof.py --video ~/Desktop/demo.mp4

注意：
  - 必须使用 sudo（root 权限），否则 scapy 无法伪造源 IP
  - 如果 HA 主机和 MacBook 之间有路由器做源 IP 校验（如 ACL），伪造会失败
============================================================
"""

import argparse
import base64
import math
import shutil
import socket
import struct
import subprocess
import sys
import time

# ============================================================
# 协议常量
# ============================================================
TARGET_PORT = 10000
DISCOVERY_PORT = 10008
PENGUIN_HEADER = b"PENGUIN0"
DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 480
DEFAULT_FPS = 1
DEFAULT_JPEG_QUALITY = 18
DEFAULT_FRAGMENT_SIZE = 1400
DEFAULT_VIDEO_PART_BYTES = 1000
DEFAULT_AUDIO_SAMPLES_PER_PACKET = 256

# 呼叫触发命令字（与 call_state.py 中的 CALL_TRIGGER_COMMANDS 一致）
CALL_TRIGGERS = {
    "cd": bytes.fromhex("cd000100"),
    "98": bytes.fromhex("98000100"),
    "b7": bytes.fromhex("b7000100"),
}
CALL_END = bytes.fromhex("b4000600")

# 测试 JPEG（320x240 黑色）
TEST_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEB"
    "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEB"
    "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEB"
    "AQEBAQH/wAARCAHgAcADASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAU"
    "EAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEBAAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAA"
    "AAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCf/9k="
)


class VideoFrameSource:
    """使用 ffmpeg 输出连续 MJPEG 帧；失败时回退静态 JPEG。"""

    def __init__(
        self,
        video_path=None,
        fps=5,
        width=DEFAULT_WIDTH,
        height=DEFAULT_HEIGHT,
        jpeg_quality=DEFAULT_JPEG_QUALITY,
        max_jpeg_bytes=None,
    ):
        self.video_path = video_path
        self.fps = fps
        self.width = width
        self.height = height
        self.jpeg_quality = jpeg_quality
        self.max_jpeg_bytes = max_jpeg_bytes
        self.proc = None
        self.buffer = bytearray()

    def start(self):
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            print("[视频] 未找到 ffmpeg，回退为静态黑色画面。")
            return

        if self.video_path:
            cmd = [
                ffmpeg,
                "-hide_banner", "-loglevel", "error",
                "-stream_loop", "-1",
                "-i", self.video_path,
                "-vf", (
                    f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,"
                    f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2"
                ),
                "-r", str(self.fps),
                "-an",
                "-f", "image2pipe",
                "-vcodec", "mjpeg",
                "-q:v", str(self.jpeg_quality),
                "pipe:1",
            ]
            label = self.video_path
        else:
            source = (
                f"testsrc2=size={self.width}x{self.height}:rate={self.fps},"
                "drawbox=x=mod(t*70\\,w)-40:y=40:w=60:h=60:color=white@0.75:t=fill"
            )
            cmd = [
                ffmpeg,
                "-hide_banner", "-loglevel", "error",
                "-f", "lavfi",
                "-i", source,
                "-f", "image2pipe",
                "-vcodec", "mjpeg",
                "-q:v", str(self.jpeg_quality),
                "pipe:1",
            ]
            label = "ffmpeg testsrc2 动态测试画面"

        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"[视频] 使用 {label} ({self.width}x{self.height}, q={self.jpeg_quality})")

    def read_frame(self):
        if not self.proc or not self.proc.stdout:
            return TEST_JPEG

        while True:
            start = self.buffer.find(b"\xff\xd8")
            end = self.buffer.find(b"\xff\xd9", start + 2 if start >= 0 else 0)
            if start >= 0 and end >= 0:
                frame = bytes(self.buffer[start:end + 2])
                del self.buffer[:end + 2]
                if self.max_jpeg_bytes is not None and len(frame) > self.max_jpeg_bytes:
                    print(f"\n[视频] 当前 JPEG {len(frame)} bytes 超过上限 {self.max_jpeg_bytes} bytes，跳过这一帧。")
                    continue
                return frame

            chunk = self.proc.stdout.read(4096)
            if not chunk:
                print("[视频] ffmpeg 没有输出帧，回退为静态黑色画面。")
                self.stop()
                return TEST_JPEG
            self.buffer.extend(chunk)

    def stop(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None


class ToneSource:
    """生成 8kHz / 16-bit little-endian PCM 测试音。"""

    def __init__(self, sample_rate=8000, frequency=440, amplitude=0.22):
        self.sample_rate = sample_rate
        self.frequency = frequency
        self.amplitude = amplitude
        self.sample_index = 0

    def read_pcm(self, samples):
        pcm = bytearray()
        for _ in range(samples):
            value = int(
                32767
                * self.amplitude
                * math.sin(2 * math.pi * self.frequency * self.sample_index / self.sample_rate)
            )
            pcm.extend(struct.pack("<h", value))
            self.sample_index += 1
        return bytes(pcm)


class VideoAudioSource:
    """从视频文件抽取 8kHz / mono / s16le PCM；读完后自动循环。"""

    def __init__(self, video_path):
        self.video_path = video_path
        self.proc = None
        self.buffer = bytearray()

    def start(self):
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            print("[音频] 未找到 ffmpeg，无法读取视频音轨。")
            return

        cmd = [
            ffmpeg,
            "-hide_banner", "-loglevel", "error",
            "-stream_loop", "-1",
            "-i", self.video_path,
            "-vn",
            "-ac", "1",
            "-ar", "8000",
            "-f", "s16le",
            "pipe:1",
        ]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"[音频] 使用视频音轨 {self.video_path} (8kHz mono PCM)")

    def read_pcm(self, samples):
        wanted = samples * 2
        if not self.proc or not self.proc.stdout:
            return b"\x00" * wanted

        while len(self.buffer) < wanted:
            chunk = self.proc.stdout.read(wanted - len(self.buffer))
            if not chunk:
                print("\n[音频] 视频音轨无输出，回退为静音。")
                self.stop()
                return b"\x00" * wanted
            self.buffer.extend(chunk)

        pcm = bytes(self.buffer[:wanted])
        del self.buffer[:wanted]
        return pcm

    def stop(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None


def send_packet_scapy(payload, src_ip, src_port, dst_ip, dst_port, fragment_size=DEFAULT_FRAGMENT_SIZE):
    """使用 scapy 发送伪造源 IP 的 UDP 包。"""
    try:
        from scapy.all import IP, UDP, Raw, fragment, raw, send
    except ImportError:
        print("错误: 未安装 scapy。请执行: pip3 install scapy")
        sys.exit(1)
    packet = IP(src=src_ip, dst=dst_ip) / UDP(sport=src_port, dport=dst_port) / Raw(payload)
    if len(raw(packet)) > fragment_size:
        send(fragment(packet, fragsize=fragment_size), verbose=0)
    else:
        send(packet, verbose=0)


def build_penguin_packet(command_hex, payload_length, device_id, device_ip, local_id, local_ip, extra=b""):
    def text_to_hex(s): return s.encode("ascii").hex()
    def ip_to_hex(s): return socket.inet_aton(s).hex()
    def word_hex(n): return n.to_bytes(2, "little").hex()

    payload_hex = "".join([
        "50454e4755494e30", command_hex, "0000", word_hex(payload_length),
        "0" * 32,
        text_to_hex(device_id), "0" * 16, ip_to_hex(device_ip),
        text_to_hex(f"S{local_id}"), "0" * 16, ip_to_hex(local_ip),
    ])
    return bytes.fromhex(payload_hex) + extra


def build_identity_payload(local_id):
    device_id = f"S{local_id}".encode("ascii")
    return b"\x02" + device_id + bytes(35 - 1 - len(device_id))


def build_cd_payload():
    return bytes.fromhex(
        "50454e4755494e30" "cd000200" "00002000" "00000000000000000000000000000000"
    )


def build_session_info_payload(local_ip, local_id):
    def text_to_hex(s): return s.encode("ascii").hex()
    def ip_to_hex(s): return socket.inet_aton(s).hex()
    def word_hex(n): return n.to_bytes(2, "little").hex()
    payload_hex = "".join([
        "50454e4755494e30", "98000200", "0000", word_hex(898),
        "0" * 32, "0100", text_to_hex(f"S{local_id}"),
        "0000000000000000", ip_to_hex(local_ip),
    ])
    payload = bytes.fromhex(payload_hex)
    return payload + bytes(898 - len(payload))


def send_discovery(target_ip, local_id, door_ip):
    payload = build_identity_payload(local_id)
    send_packet_scapy(payload, door_ip, DISCOVERY_PORT, target_ip, DISCOVERY_PORT)
    print(f"  [发现] 身份包 {door_ip}:{DISCOVERY_PORT} -> {target_ip}:{DISCOVERY_PORT}")


def send_trigger(cmd, device_id, door_ip, local_id, local_ip, target_ip):
    pkt = build_penguin_packet(cmd.hex(), 80, device_id, door_ip, local_id, local_ip)
    send_packet_scapy(pkt, door_ip, TARGET_PORT, target_ip, TARGET_PORT)
    print(f"  [呼叫] 触发包 {cmd.hex()} {door_ip}:{TARGET_PORT} -> {target_ip}:{TARGET_PORT}")


def send_video_frame(
    device_id,
    door_ip,
    local_id,
    local_ip,
    target_ip,
    jpeg,
    frame_no,
    part_bytes=DEFAULT_VIDEO_PART_BYTES,
    fragment_size=DEFAULT_FRAGMENT_SIZE,
):
    parts = [jpeg[index:index + part_bytes] for index in range(0, len(jpeg), part_bytes)]
    total_parts = len(parts)
    for part_no, part in enumerate(parts, start=1):
        hdr = struct.pack("<HHHHH", 1, frame_no & 0xFFFF, total_parts, part_no, len(part))
        pkt = build_penguin_packet("b7000a00", 90 + len(part), device_id, door_ip, local_id, local_ip, hdr + part)
        send_packet_scapy(pkt, door_ip, TARGET_PORT, target_ip, TARGET_PORT, fragment_size)
        time.sleep(0.003)
    return total_parts


def build_video_frame_packets(device_id, door_ip, local_id, local_ip, jpeg, frame_no, part_bytes=DEFAULT_VIDEO_PART_BYTES):
    parts = [jpeg[index:index + part_bytes] for index in range(0, len(jpeg), part_bytes)]
    packets = []
    total_parts = len(parts)
    for part_no, part in enumerate(parts, start=1):
        hdr = struct.pack("<HHHHH", 1, frame_no & 0xFFFF, total_parts, part_no, len(part))
        packets.append(build_penguin_packet("b7000a00", 90 + len(part), device_id, door_ip, local_id, local_ip, hdr + part))
    return packets


def send_audio(device_id, door_ip, local_id, local_ip, target_ip, pcm, sequence, fragment_size=DEFAULT_FRAGMENT_SIZE):
    hdr = struct.pack("<HHHHH", 3, sequence & 0xFFFF or 1, 1, 1, len(pcm))
    pkt = build_penguin_packet("b7000a00", 90 + len(pcm), device_id, door_ip, local_id, local_ip, hdr + pcm)
    send_packet_scapy(pkt, door_ip, TARGET_PORT, target_ip, TARGET_PORT, fragment_size)


def main():
    parser = argparse.ArgumentParser(description="模拟门口机呼叫室内机（伪造源 IP 版）")
    parser.add_argument("--target", default="192.168.16.64", help="Addon 的 local_ip（HA 主机 IP）")
    parser.add_argument("--local-id", default="00010116010", help="Addon 的 local_id")
    parser.add_argument("--door-ip", default="192.168.16.224", help="真实门口机 IP（用于伪造源 IP）")
    parser.add_argument("--door-no", default="01", help="门口机编号")
    parser.add_argument("--duration", type=int, default=30, help="呼叫持续时间（秒）")
    parser.add_argument("--trigger", choices=["cd", "98", "b7"], default="cd", help="触发命令字")
    parser.add_argument("--video", help="用于模拟门口机画面的视频文件；不填则生成动态测试画面")
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS, help="模拟视频帧率，默认 1fps")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH, help="视频宽度，默认 640")
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT, help="视频高度，默认 480")
    parser.add_argument("--jpeg-quality", type=int, default=DEFAULT_JPEG_QUALITY, help="MJPEG 质量参数，越大体积越小，默认 18")
    parser.add_argument("--max-jpeg-bytes", type=int, help="单帧 JPEG 最大字节数；默认不限制")
    parser.add_argument("--video-part-bytes", type=int, default=DEFAULT_VIDEO_PART_BYTES, help="协议内视频分片大小，默认 1000")
    parser.add_argument("--audio-samples", type=int, default=DEFAULT_AUDIO_SAMPLES_PER_PACKET, help="每个音频包的 PCM 采样数，默认 256")
    parser.add_argument("--tone", type=int, help="强制使用测试音频频率 Hz；设为 0 则静音。不填且有 --video 时使用视频音轨")
    parser.add_argument("--fragment-size", type=int, default=DEFAULT_FRAGMENT_SIZE, help="IP 分片阈值，默认 1400")
    args = parser.parse_args()

    target_ip = args.target
    local_id = args.local_id
    door_ip = args.door_ip
    door_no = args.door_no
    duration = args.duration
    fps = max(1, args.fps)
    width = max(64, args.width)
    height = max(48, args.height)
    jpeg_quality = min(31, max(2, args.jpeg_quality))
    max_jpeg_bytes = max(600, args.max_jpeg_bytes) if args.max_jpeg_bytes else None
    video_part_bytes = max(256, args.video_part_bytes)
    audio_samples = max(80, args.audio_samples)
    fragment_size = max(576, args.fragment_size)
    trigger_cmd = CALL_TRIGGERS[args.trigger]
    device_id = f"M000101{door_no}000"
    local_ip = target_ip

    print("=" * 60)
    print("  麦驰可视对讲 - 门口机呼入测试 (Scapy 伪造源 IP)")
    print("=" * 60)
    print(f"\n  目标 HA 主机:  {target_ip}")
    print(f"  室内机 ID:     {local_id}")
    print(f"  伪造门口机 IP: {door_ip} (真实门口机 IP)")
    print(f"  门口机编号:    {door_no}")
    print(f"  触发命令:      {trigger_cmd.hex()}")
    print(f"  持续时间:      {duration} 秒")
    print(f"  模拟帧率:      {fps} fps")
    print(f"  视频尺寸:      {width}x{height}")
    print(f"  JPEG质量参数:  {jpeg_quality}")
    print(f"  单帧上限:      {str(max_jpeg_bytes) + ' bytes' if max_jpeg_bytes else '不限制'}")
    print(f"  视频分片:      {video_part_bytes} bytes/part")
    print(f"  音频包大小:    {audio_samples} samples/packet")
    print(f"  测试视频:      {args.video or '动态测试画面'}")
    if args.tone is None and args.video:
        audio_label = "视频音轨"
    elif args.tone is None:
        audio_label = "440 Hz"
    else:
        audio_label = "静音" if args.tone <= 0 else f"{args.tone} Hz"
    print(f"  测试音频:      {audio_label}")
    print(f"  分片大小:      {fragment_size} bytes")
    print()

    # 检查 scapy
    try:
        from scapy.all import IP, UDP, Raw, send
        print("[检查] scapy 已安装 ✓")
    except ImportError:
        print("[检查] scapy 未安装，请先执行: pip3 install scapy")
        sys.exit(1)

    # 检查权限（macOS 上需要 root）
    if sys.platform != "win32":
        import os
        if os.getuid() != 0:
            print("[警告] 当前不是 root 用户。伪造源 IP 通常需要 sudo 权限。")
            print("       如果测试失败，请用 sudo 运行: sudo python3 test_call_spoof.py")
            print()
            confirm = input("是否继续尝试？(y/N): ").strip().lower()
            if confirm != "y":
                sys.exit(0)

    print("\n[阶段 1] 发送身份发现包...")
    send_discovery(target_ip, local_id, door_ip)
    time.sleep(0.5)

    print(f"\n[阶段 2] 发送呼叫触发包 ({trigger_cmd.hex()})...")
    for i in range(3):
        send_trigger(trigger_cmd, device_id, door_ip, local_id, local_ip, target_ip)
        time.sleep(0.3)

    print(f"\n[阶段 3] 开始模拟视频流（持续 {duration} 秒）...")
    print("         Home Assistant 应该弹出「呼入中」弹窗")
    print("         按 Ctrl+C 提前结束\n")

    video_source = VideoFrameSource(
        args.video,
        fps=fps,
        width=width,
        height=height,
        jpeg_quality=jpeg_quality,
        max_jpeg_bytes=max_jpeg_bytes,
    )
    if args.tone is None and args.video:
        audio_source = VideoAudioSource(args.video)
    elif args.tone is None:
        audio_source = ToneSource(frequency=440)
    elif args.tone <= 0:
        audio_source = None
    else:
        audio_source = ToneSource(frequency=args.tone)

    video_source.start()
    if audio_source is not None and hasattr(audio_source, "start"):
        audio_source.start()
    audio_interval = audio_samples / 8000
    video_interval = 1 / fps
    audio_sequence = 0
    frame_no = 0
    sent_audio_packets = 0
    pending_video_packets = []
    last_jpeg_size = 0
    last_video_parts = 0
    start_at = time.monotonic()
    end_at = start_at + duration
    next_video_at = start_at
    next_audio_at = start_at
    try:
        while time.monotonic() < end_at:
            now = time.monotonic()

            if now >= next_video_at:
                frame_no += 1
                jpeg = video_source.read_frame()
                video_packets = build_video_frame_packets(device_id, door_ip, local_id, local_ip, jpeg, frame_no, video_part_bytes)
                pending_video_packets.extend(video_packets)
                last_jpeg_size = len(jpeg)
                last_video_parts = len(video_packets)
                next_video_at += video_interval

            if now >= next_audio_at:
                audio_sequence += 1
                sent_audio_packets += 1
                pcm = b"\x00" * (audio_samples * 2) if audio_source is None else audio_source.read_pcm(audio_samples)
                send_audio(device_id, door_ip, local_id, local_ip, target_ip, pcm, audio_sequence, fragment_size)
                next_audio_at += audio_interval
            elif pending_video_packets:
                pkt = pending_video_packets.pop(0)
                send_packet_scapy(pkt, door_ip, TARGET_PORT, target_ip, TARGET_PORT, fragment_size)
            else:
                sleep_until = min(next_audio_at, next_video_at, end_at)
                time.sleep(max(0.001, min(0.01, sleep_until - time.monotonic())))

            elapsed = min(duration, time.monotonic() - start_at)
            print(
                f"\r  [流] 帧 #{frame_no}  {last_jpeg_size} bytes/{last_video_parts} parts  音频 {sent_audio_packets} 包  ({elapsed:.1f}s/{duration}s)",
                end="",
                flush=True,
            )
    except KeyboardInterrupt:
        pass
    finally:
        video_source.stop()
        if audio_source is not None and hasattr(audio_source, "stop"):
            audio_source.stop()

    print(f"\n\n[阶段 4] 发送挂断包...")
    end_pkt = build_penguin_packet("b4000600", 80, device_id, door_ip, local_id, local_ip)
    send_packet_scapy(end_pkt, door_ip, TARGET_PORT, target_ip, TARGET_PORT)
    print("         呼叫结束")

    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60)
    print("\n检查 Home Assistant:")
    print("  1. Dashboard 卡片应弹出「呼入中」弹窗")
    print("  2. 显示 1号机 视频画面")
    print("  3. 有「接听」「解锁」「挂断」按钮")
    print("  4. 点击「接听」后视频继续")
    print()


if __name__ == "__main__":
    main()
