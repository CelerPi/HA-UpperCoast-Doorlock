#!/usr/bin/env python3
"""
麦驰可视对讲 - 门口机呼入测试脚本

模拟门口机呼叫室内机，测试 HA 能否正常弹出呼叫弹窗。

支持两种模式：
  1. 伪造源 IP 模式（推荐）：使用 scapy 伪造门口机 IP 发送呼叫包
  2. 正常发送模式： Addon 需将脚本电脑 IP 注册为门口机

用法:
    # 模式 1（伪造源 IP，需要 scapy + root）
    sudo python3 test_incoming_call.py 192.168.16.64 00010116010 192.168.16.224

    # 模式 2（正常发送，Addon 需配置脚本 IP 为门口机）
    python3 test_incoming_call.py 192.168.16.64 00010116010 192.168.16.100 --no-spoof

依赖:
    - 模式 1: scapy (pip3 install scapy), 需要 root/Administrator
    - 模式 2: 无需额外依赖
"""

from __future__ import annotations

import argparse
import socket
import struct
import sys
import time

# =============================================================================
# 协议常量
# =============================================================================
TARGET_PORT = 10000
DISCOVERY_PORT = 10008
PENGUIN_HEADER = b"PENGUIN0"

# 呼叫触发命令字（必须与 call_state.py 中的 CALL_TRIGGER_COMMANDS 一致）
CALL_TRIGGERS = [bytes.fromhex(cmd) for cmd in ("cd000100", "98000100", "b7000100")]
CALL_END = bytes.fromhex("b4000600")

# 心跳/视频命令字
HEARTBEAT_CMD = bytes.fromhex("b7000c00")
VIDEO_REQ_CMD = bytes.fromhex("b7000300")
SESSION_INFO_CMD = bytes.fromhex("98000200")


# =============================================================================
# 协议构建函数
# =============================================================================
def _text_to_hex(value: str) -> str:
    return value.encode("ascii").hex()


def _ip_to_hex(ip_address: str) -> str:
    return socket.inet_aton(ip_address).hex()


def _word_to_little_hex(value: int) -> str:
    return value.to_bytes(2, "little").hex()


def build_penguin_packet(command: bytes, payload_length: int,
                         device_id: str, device_ip: str,
                         local_id: str, local_ip: str,
                         extra: bytes = b"") -> bytes:
    """构建 PENGUIN 协议数据包。"""
    payload_hex = "".join([
        "50454e4755494e30",
        command.hex(),
        "0000",
        _word_to_little_hex(payload_length),
        "00000000000000000000000000000000",
        _text_to_hex(device_id),
        "0000000000000000",
        _ip_to_hex(device_ip),
        _text_to_hex(f"S{local_id}"),
        "0000000000000000",
        _ip_to_hex(local_ip),
    ])
    return bytes.fromhex(payload_hex) + extra


def build_session_info(local_ip: str, local_id: str) -> bytes:
    """构建会话信息包（室内机响应时发送）。"""
    payload_hex = "".join([
        "50454e4755494e30",
        "98000200",
        "0000",
        _word_to_little_hex(898),
        "00000000000000000000000000000000",
        "0100",
        _text_to_hex(f"S{local_id}"),
        "0000000000000000",
        _ip_to_hex(local_ip),
    ])
    payload = bytes.fromhex(payload_hex)
    return payload + bytes(898 - len(payload))


def build_heartbeat(device_id: str, device_ip: str, local_id: str, local_ip: str) -> bytes:
    """构建心跳保活包。"""
    return build_penguin_packet(HEARTBEAT_CMD, 80, device_id, device_ip, local_id, local_ip)


def build_video_request(device_id: str, device_ip: str, local_id: str, local_ip: str) -> bytes:
    """构建视频请求包。"""
    video_tail = bytes.fromhex("564944454f410000320009000900ff00")
    return build_penguin_packet(VIDEO_REQ_CMD, 96, device_id, device_ip, local_id, local_ip, video_tail)


def build_call_trigger(command: bytes, device_id: str, device_ip: str,
                       local_id: str, local_ip: str) -> bytes:
    """构建呼叫触发包。"""
    return build_penguin_packet(command, 80, device_id, device_ip, local_id, local_ip)


# =============================================================================
# 发送逻辑
# =============================================================================
def send_with_normal_socket(sock: socket.socket, payload: bytes, target: tuple[str, int]) -> None:
    """使用普通 UDP socket 发送。"""
    sock.sendto(payload, target)


def send_with_scapy(payload: bytes, src_ip: str, src_port: int,
                    dst_ip: str, dst_port: int) -> None:
    """使用 scapy 发送伪造源 IP 的包。"""
    try:
        from scapy.all import IP, UDP, Raw, send
    except ImportError:
        print("错误: 未安装 scapy。请执行: pip3 install scapy")
        sys.exit(1)

    packet = IP(src=src_ip, dst=dst_ip) / UDP(sport=src_port, dport=dst_port) / Raw(payload)
    send(packet, verbose=0)


def send_discovery(target_ip: str, local_id: str, use_spoof: bool, door_ip: str) -> None:
    """发送身份发现包。"""
    device_id = f"S{local_id}".encode("ascii")
    payload = b"\x02" + device_id + bytes(35 - 1 - len(device_id))
    target = (target_ip, DISCOVERY_PORT)

    if use_spoof:
        send_with_scapy(payload, door_ip, DISCOVERY_PORT, target_ip, DISCOVERY_PORT)
    else:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(payload, target)
    print(f"  [发现] 身份包 → {target_ip}:{DISCOVERY_PORT}")


# =============================================================================
# 主程序
# =============================================================================
def main() -> None:
    parser = argparse.ArgumentParser(
        description="模拟门口机呼叫室内机，测试 HA 呼叫弹窗",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 模式 1: 伪造源 IP（需要 scapy + root，最真实）
  sudo python3 %(prog)s 192.168.16.64 00010116010 192.168.16.224

  # 模式 2: 正常发送（Addon 需将脚本 IP 配置为门口机）
  python3 %(prog)s 192.168.16.64 00010116010 192.168.16.100 --no-spoof

说明:
  - 目标 IP:  Addon 配置中的 local_ip（HA 主机在门禁网络的 IP）
  - 室内机ID: Addon 配置中的 local_id
  - 门口机IP: 模式 1 填真实门口机 IP（用于伪造）；模式 2 填脚本电脑 IP
        """
    )
    parser.add_argument("target_ip", help="Addon 的 local_ip（HA 主机 IP）")
    parser.add_argument("local_id", help="Addon 的 local_id（室内机 ID）")
    parser.add_argument("door_ip", help="门口机 IP（模式1用真实门口机 IP，模式2用脚本电脑 IP）")
    parser.add_argument("--no-spoof", action="store_true",
                        help="不使用 scapy 伪造源 IP（Addon 需将 door_ip 配置为门口机）")
    parser.add_argument("--door-no", default="01", help="门口机编号（默认 01）")
    parser.add_argument("--duration", type=int, default=30, help="呼叫持续时间（秒，默认 30）")
    parser.add_argument("--trigger", choices=["cd", "98", "b7"], default="cd",
                        help="触发命令字: cd=cd000100, 98=98000100, b7=b7000100（默认 cd）")

    args = parser.parse_args()

    target_ip = args.target_ip
    local_id = args.local_id
    door_ip = args.door_ip
    door_no = args.door_no
    use_spoof = not args.no_spoof
    duration = args.duration
    trigger_cmd = {"cd": CALL_TRIGGERS[0], "98": CALL_TRIGGERS[1], "b7": CALL_TRIGGERS[2]}[args.trigger]

    device_id = f"M000101{door_no}000"
    local_ip = target_ip  # 室内机响应时使用目标 IP

    print("=" * 60)
    print("   麦驰可视对讲 - 门口机呼入测试")
    print("=" * 60)
    print(f"\n  目标 IP:      {target_ip}")
    print(f"  室内机 ID:    {local_id}")
    print(f"  门口机编号:   {door_no}")
    print(f"  门口机 IP:    {door_ip}")
    print(f"  模式:         {'伪造源 IP (scapy)' if use_spoof else '正常发送'}")
    print(f"  触发命令:     {trigger_cmd.hex()}")
    print(f"  持续时间:     {duration} 秒")
    print()

    if use_spoof:
        print("[检查] 验证 scapy 可用性...")
        try:
            from scapy.all import IP, UDP, Raw, send
            print("       scapy 已安装 ✓")
        except ImportError:
            print("       scapy 未安装，请执行: pip3 install scapy")
            sys.exit(1)

        if sys.platform != "win32" and hasattr(os, "getuid") and os.getuid() != 0:
            print("       警告: 伪造源 IP 通常需要 root 权限")
    else:
        print("[提示] 正常发送模式：确保 Addon 配置中已将以下 IP 注册为门口机")
        print(f"       {door_ip} (door_{door_no})")
        print("       否则 Addon 会静默丢弃呼叫包")
    print()

    # 阶段 1: 发现
    print("[阶段 1] 发送身份发现包...")
    send_discovery(target_ip, local_id, use_spoof, door_ip)
    time.sleep(0.5)

    # 阶段 2: 发送呼叫触发包
    print(f"\n[阶段 2] 发送呼叫触发包 ({trigger_cmd.hex()})...")
    call_pkt = build_call_trigger(trigger_cmd, device_id, door_ip, local_id, local_ip)
    target = (target_ip, TARGET_PORT)

    for i in range(3):
        if use_spoof:
            send_with_scapy(call_pkt, door_ip, TARGET_PORT, target_ip, TARGET_PORT)
        else:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.sendto(call_pkt, target)
        print(f"  [呼叫] 触发包 #{i+1} → {target_ip}:{TARGET_PORT}")
        time.sleep(0.3)

    # 阶段 3: 模拟门口机发送视频流
    print(f"\n[阶段 3] 开始模拟视频流（持续 {duration} 秒）...")
    print("         按 Ctrl+C 提前结束\n")

    # 创建测试 JPEG（320x240 黑色，base64 编码，避免 hex 字符串出错）
    import base64
    jpeg = base64.b64decode(
        "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEB"
        "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEB"
        "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEB"
        "AQEBAQH/wAARCAHgAcADASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAU"
        "EAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEBAAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAA"
        "AAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCf/9k="
    )

    start_time = time.time()
    frame_no = 0

    try:
        while time.time() - start_time < duration:
            frame_no += 1
            elapsed = time.time() - start_time

            # 构建视频帧
            data_length = len(jpeg)
            payload_length = 90 + data_length
            video_header = struct.pack("<HHHHH", 1, frame_no & 0xFFFF, 1, 1, data_length)
            video_pkt = build_penguin_packet(
                bytes.fromhex("b7000a00"), payload_length,
                device_id, door_ip, local_id, local_ip,
                video_header + jpeg
            )

            # 构建音频帧（静音）
            pcm = b"\x00" * 512
            audio_header = struct.pack("<HHHHH", 3, frame_no & 0xFFFF, 1, 1, len(pcm))
            audio_pkt = build_penguin_packet(
                bytes.fromhex("b7000a00"), 90 + len(pcm),
                device_id, door_ip, local_id, local_ip,
                audio_header + pcm
            )

            if use_spoof:
                send_with_scapy(video_pkt, door_ip, TARGET_PORT, target_ip, TARGET_PORT)
                send_with_scapy(audio_pkt, door_ip, TARGET_PORT, target_ip, TARGET_PORT)
            else:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.sendto(video_pkt, target)
                    sock.sendto(audio_pkt, target)

            print(f"\r  [视频] 帧 #{frame_no}  已发送 {elapsed:.1f}s/{duration}s", end="", flush=True)
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        print(f"\n\n[停止] 共发送 {frame_no} 帧视频")

    # 阶段 4: 发送挂断
    print("\n[阶段 4] 发送呼叫结束包...")
    end_pkt = build_penguin_packet(CALL_END, 80, device_id, door_ip, local_id, local_ip)
    if use_spoof:
        send_with_scapy(end_pkt, door_ip, TARGET_PORT, target_ip, TARGET_PORT)
    else:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(end_pkt, target)
    print("       呼叫结束")

    print("\n" + "=" * 60)
    print("   测试结束")
    print("=" * 60)
    print("\n检查 Home Assistant:")
    print("  1. Dashboard 卡片应弹出「呼入中」弹窗")
    print("  2. 弹窗显示 1号机 视频画面")
    print("  3. 有「接听」「解锁」「挂断」按钮")
    print("  4. 点击「接听」后视频继续，点击「挂断」结束")
    print()


if __name__ == "__main__":
    import os
    main()
