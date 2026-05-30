#!/usr/bin/env python3
"""
麦驰可视对讲 - 门口机呼叫测试脚本

模拟门口机向 Addon 发送呼叫数据包，用于测试 HA 能否正常收到呼叫。

用法:
    python3 test_call_simulator.py [目标IP] [室内机ID]

示例:
    python3 test_call_simulator.py 192.168.16.64 00010116010

依赖: Python 3.8+
"""

from __future__ import annotations

import socket
import struct
import sys
import time
from pathlib import Path

# =============================================================================
# 默认配置（根据你的 Addon 配置修改）
# =============================================================================
TARGET_IP = "192.168.16.64"      # Addon 的 local_ip
TARGET_PORT = 10000              # 会话端口
DISCOVERY_PORT = 10008           # 发现端口

LOCAL_ID = "00010116010"         # Addon 的 local_id
LOCAL_IP = "192.168.16.64"       # Addon 的 local_ip

DOOR_NO = "01"                   # 模拟的门口机编号
DOOR_IP = "192.168.16.224"       # 模拟的门口机 IP
DEVICE_ID = f"M000101{DOOR_NO}000"

# 协议常量
PENGUIN_HEADER = bytes.fromhex("50454e4755494e30")
PADDING = bytes.fromhex("0000000000000000")


# =============================================================================
# 协议构建函数
# =============================================================================
def _text_to_hex(value: str) -> str:
    return value.encode("ascii").hex()


def _ip_to_hex(ip_address: str) -> str:
    return socket.inet_aton(ip_address).hex()


def _word_to_little_hex(value: int) -> str:
    return value.to_bytes(2, "little").hex()


def build_identity_payload(local_id: str) -> bytes:
    """构建身份发现包。"""
    device_id = f"S{local_id}".encode("ascii")
    return b"\x02" + device_id + bytes(35 - 1 - len(device_id))


def build_cd_payload() -> bytes:
    """构建 CD 包。"""
    return bytes.fromhex(
        "".join([
            "50454e4755494e30",
            "cd000200",
            "00002000",
            "00000000000000000000000000000000",
        ])
    )


def build_session_info_payload(local_ip: str, local_id: str) -> bytes:
    """构建会话信息包。"""
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


def build_b700_payload(
    command_hex: str,
    payload_length: int,
    device_id: str,
    target_ip: str,
    local_id: str,
    local_ip: str,
) -> bytes:
    """构建 b700 系列命令包。"""
    payload_hex = "".join([
        "50454e4755494e30",
        command_hex,
        "0000",
        _word_to_little_hex(payload_length),
        "00000000000000000000000000000000",
        _text_to_hex(device_id),
        "0000000000000000",
        _ip_to_hex(target_ip),
        _text_to_hex(f"S{local_id}"),
        "0000000000000000",
        _ip_to_hex(local_ip),
    ])
    return bytes.fromhex(payload_hex)


def build_video_frame(device_id: str, target_ip: str, local_id: str, local_ip: str, jpeg: bytes) -> bytes:
    """构建视频帧数据包。"""
    data_length = len(jpeg)
    payload_length = 90 + data_length
    header = build_b700_payload("b7000a00", payload_length, device_id, target_ip, local_id, local_ip)
    video_header = struct.pack("<HHHHH", 1, 1, 1, 1, data_length)
    return header + video_header + jpeg


def build_call_audio(device_id: str, target_ip: str, local_id: str, local_ip: str, pcm: bytes) -> bytes:
    """构建音频数据包。"""
    data_length = len(pcm)
    payload_length = 90 + data_length
    header = build_b700_payload("b7000a00", payload_length, device_id, target_ip, local_id, local_ip)
    audio_header = struct.pack("<HHHHH", 3, 1, 1, 1, data_length)
    return header + audio_header + pcm


# =============================================================================
# 测试 JPEG（1x1 像素黑色图片）
# =============================================================================
def create_test_jpeg() -> bytes:
    """创建测试 JPEG 图片（320x240 黑色，base64 编码）。"""
    import base64
    return base64.b64decode(
        "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEB"
        "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEB"
        "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEB"
        "AQEBAQH/wAARCAHgAcADASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAU"
        "EAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEBAAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAA"
        "AAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCf/9k="
    )


# =============================================================================
# 发送逻辑
# =============================================================================
def send_discovery(sock: socket.socket, target_ip: str, local_id: str) -> None:
    """发送身份发现包到 discovery 端口。"""
    payload = build_identity_payload(local_id)
    sock.sendto(payload, (target_ip, DISCOVERY_PORT))
    print(f"  [发现] 发送身份包到 {target_ip}:{DISCOVERY_PORT} ({len(payload)} bytes)")


def send_session_init(sock: socket.socket, target_ip: str, local_ip: str, local_id: str) -> None:
    """发送会话初始化包。"""
    cd = build_cd_payload()
    sock.sendto(cd, (target_ip, TARGET_PORT))
    print(f"  [会话] 发送 CD 包 ({len(cd)} bytes)")

    session = build_session_info_payload(local_ip, local_id)
    sock.sendto(session, (target_ip, TARGET_PORT))
    print(f"  [会话] 发送 Session Info ({len(session)} bytes)")


def send_call_packet(sock: socket.socket, device_id: str, door_ip: str,
                     local_id: str, local_ip: str, jpeg: bytes) -> None:
    """发送单个呼叫数据包（视频+音频）。"""
    video = build_video_frame(device_id, door_ip, local_id, local_ip, jpeg)
    sock.sendto(video, (TARGET_IP, TARGET_PORT))

    pcm = b"\x00" * 512
    audio = build_call_audio(device_id, door_ip, local_id, local_ip, pcm)
    sock.sendto(audio, (TARGET_IP, TARGET_PORT))


def print_status(frame_no: int) -> None:
    """打印状态。"""
    print(f"\r  [呼叫] 发送帧 #{frame_no}  视频+音频", end="", flush=True)


# =============================================================================
# 主程序
# =============================================================================
def main() -> None:
    print("=" * 60)
    print("   麦驰可视对讲 - 门口机呼叫测试脚本")
    print("=" * 60)

    # 解析命令行参数
    target_ip = sys.argv[1] if len(sys.argv) > 1 else TARGET_IP
    local_id = sys.argv[2] if len(sys.argv) > 2 else LOCAL_ID
    door_no = sys.argv[3] if len(sys.argv) > 3 else DOOR_NO

    device_id = f"M000101{door_no}000"
    door_ip = DOOR_IP
    local_ip = target_ip  # 通常和 target_ip 相同

    print(f"\n  目标 IP:      {target_ip}")
    print(f"  目标端口:     {TARGET_PORT} (会话) / {DISCOVERY_PORT} (发现)")
    print(f"  室内机 ID:    {local_id}")
    print(f"  门口机 ID:    {device_id}")
    print(f"  门口机 IP:    {door_ip}")
    print()

    # 检查目标 IP 是否可达
    print("[检查] 测试目标 IP 连通性...")
    try:
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        test_sock.settimeout(2.0)
        test_sock.sendto(b"PING", (target_ip, TARGET_PORT))
        test_sock.close()
        print("       UDP 端口测试通过（无响应也正常）")
    except Exception as exc:
        print(f"       警告: {exc}")

    # 创建测试 JPEG
    print("\n[准备] 生成测试视频帧...")
    jpeg = create_test_jpeg()
    print(f"       测试 JPEG: {len(jpeg)} bytes")

    # 创建 UDP socket
    print("\n[连接] 创建 UDP socket...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # 阶段 1: 发现
    print("\n[阶段 1] 发送身份发现包...")
    send_discovery(sock, target_ip, local_id)
    time.sleep(0.5)

    # 阶段 2: 会话初始化
    print("\n[阶段 2] 发送会话初始化...")
    send_session_init(sock, target_ip, local_ip, local_id)
    time.sleep(0.5)

    # 阶段 3: 持续发送呼叫数据
    print("\n[阶段 3] 开始模拟呼叫视频流...")
    print("         按 Ctrl+C 停止\n")

    frame_no = 0
    try:
        while True:
            frame_no += 1
            send_call_packet(sock, device_id, door_ip, local_id, local_ip, jpeg)
            print_status(frame_no)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print(f"\n\n[停止] 共发送 {frame_no} 帧")
    finally:
        sock.close()

    print("\n" + "=" * 60)
    print("   测试结束")
    print("=" * 60)
    print("\n检查 Home Assistant:")
    print("  1. 开发者工具 → 状态 → binary_sensor.vds_call_status")
    print("     应该显示 'on'（呼叫中）")
    print("  2. Dashboard 卡片应该弹出呼叫弹窗")
    print("  3. 相机实体 camera.vds_video 应该显示视频画面")
    print()


if __name__ == "__main__":
    main()
