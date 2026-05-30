#!/usr/bin/env python3
"""
============================================================
麦驰可视对讲 - 门口机呼入测试脚本 (MacBook 专用版)
============================================================

功能：模拟门口机呼叫室内机，测试 Home Assistant 能否弹出呼叫弹窗。

原理：
  1. 在 Addon 配置中将 MacBook IP 临时注册为某个门口机
  2. 脚本从 MacBook 发送呼叫数据包到 Addon
  3. Addon 认为门口机在呼叫，触发 HA 弹窗

网络要求：
  - MacBook 和 HA 主机必须在同一个局域网（都能访问 192.168.16.xxx）
  - MacBook 需要获取到 192.168.16.xxx 网段的 IP

使用方法：
  1. 将脚本 AirDrop 到 MacBook
  2. 打开「终端」，cd 到脚本所在目录
  3. 先运行一次，按提示操作：
     python3 test_call_mac.py
  4. 根据提示在 HA Addon 配置中添加 MacBook IP
  5. 再次运行脚本开始测试

作者：CelerPi
版本：1.0.0
"""

import base64
import os
import socket
import struct
import subprocess
import sys
import time

# ============================================================
# 协议常量（不要修改）
# ============================================================
TARGET_PORT = 10000
DISCOVERY_PORT = 10008
CALL_TRIGGER = bytes.fromhex("cd000100")
CALL_END = bytes.fromhex("b4000600")

# 320x240 黑色 JPEG（base64 编码，用于模拟视频帧）
TEST_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEB"
    "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEB"
    "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEB"
    "AQEBAQH/wAARCAHgAcADASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAU"
    "EAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEBAAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAA"
    "AAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCf/9k="
)


# ============================================================
# 辅助函数
# ============================================================
def get_macbook_ip():
    """自动获取 MacBook 在门禁网络中的 IP 地址。"""
    # 尝试常见的网络接口
    for iface in ["en0", "en1", "en2", "en3"]:
        try:
            result = subprocess.run(
                ["ipconfig", "getifaddr", iface],
                capture_output=True, text=True, timeout=2
            )
            ip = result.stdout.strip()
            if ip and ip.startswith("192.168.16."):
                return ip
        except Exception:
            continue
    return None


def ask_question(prompt, default=""):
    """交互式提问。"""
    if default:
        user_input = input(f"{prompt} [{default}]: ").strip()
        return user_input if user_input else default
    return input(f"{prompt}: ").strip()


def build_packet(command, payload_length, device_id, device_ip, local_id, local_ip, extra=b""):
    """构建 PENGUIN 协议数据包。"""
    def text_to_hex(s): return s.encode("ascii").hex()
    def ip_to_hex(s): return socket.inet_aton(s).hex()
    def word_hex(n): return n.to_bytes(2, "little").hex()

    payload_hex = "".join([
        "50454e4755494e30",
        command.hex(),
        "0000",
        word_hex(payload_length),
        "0" * 32,
        text_to_hex(device_id),
        "0" * 16,
        ip_to_hex(device_ip),
        text_to_hex(f"S{local_id}"),
        "0" * 16,
        ip_to_hex(local_ip),
    ])
    return bytes.fromhex(payload_hex) + extra


def send_udp(payload, target_ip, target_port):
    """发送 UDP 数据包。"""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(payload, (target_ip, target_port))


# ============================================================
# 测试流程
# ============================================================
def run_test(target_ip, local_id, door_ip, door_no, duration):
    """执行完整的呼入测试。"""
    device_id = f"M000101{door_no}000"
    local_ip = target_ip
    target = (target_ip, TARGET_PORT)

    print("\n" + "=" * 56)
    print("  开始测试")
    print("=" * 56)

    # 阶段 1: 身份发现
    print("\n[1/4] 发送身份发现包...")
    discovery_payload = b"\x02" + f"S{local_id}".encode("ascii")
    discovery_payload += bytes(35 - 1 - len(f"S{local_id}"))
    send_udp(discovery_payload, target_ip, DISCOVERY_PORT)
    print(f"      → {target_ip}:{DISCOVERY_PORT}")
    time.sleep(0.5)

    # 阶段 2: 呼叫触发（连发 3 次确保收到）
    print("\n[2/4] 发送呼叫触发包...")
    for i in range(3):
        pkt = build_packet(CALL_TRIGGER, 80, device_id, door_ip, local_id, local_ip)
        send_udp(pkt, target_ip, TARGET_PORT)
        print(f"      触发包 #{i+1} → {target_ip}:{TARGET_PORT}")
        time.sleep(0.3)

    # 阶段 3: 持续发送视频流
    print(f"\n[3/4] 开始发送视频流（持续 {duration} 秒）...")
    print("      此时 Home Assistant 应该弹出「呼入中」弹窗")
    print("      按 Ctrl+C 提前结束\n")

    pcm_audio = b"\x00" * 512  # 静音 PCM
    frame_count = 0
    start_time = time.time()

    try:
        while time.time() - start_time < duration:
            frame_count += 1
            elapsed = time.time() - start_time

            # 视频帧
            v_header = struct.pack("<HHHHH", 1, frame_count & 0xFFFF, 1, 1, len(TEST_JPEG))
            v_pkt = build_packet(
                bytes.fromhex("b7000a00"), 90 + len(TEST_JPEG),
                device_id, door_ip, local_id, local_ip, v_header + TEST_JPEG
            )
            send_udp(v_pkt, target_ip, TARGET_PORT)

            # 音频帧
            a_header = struct.pack("<HHHHH", 3, frame_count & 0xFFFF, 1, 1, len(pcm_audio))
            a_pkt = build_packet(
                bytes.fromhex("b7000a00"), 90 + len(pcm_audio),
                device_id, door_ip, local_id, local_ip, a_header + pcm_audio
            )
            send_udp(a_pkt, target_ip, TARGET_PORT)

            print(f"\r      已发送 {frame_count} 帧  ({elapsed:.1f}s/{duration}s)", end="", flush=True)
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass

    print(f"\n\n      视频流结束，共发送 {frame_count} 帧")

    # 阶段 4: 发送挂断
    print("\n[4/4] 发送呼叫结束包...")
    end_pkt = build_packet(CALL_END, 80, device_id, door_ip, local_id, local_ip)
    send_udp(end_pkt, target_ip, TARGET_PORT)
    print("      → 呼叫结束")

    print("\n" + "=" * 56)
    print("  测试完成")
    print("=" * 56)


# ============================================================
# 主程序
# ============================================================
def main():
    print("=" * 56)
    print("  麦驰可视对讲 - 门口机呼入测试 (MacBook 版)")
    print("=" * 56)

    # 步骤 1: 检查 MacBook 网络
    print("\n[检查] 正在检测 MacBook 的网络配置...")
    mac_ip = get_macbook_ip()

    if mac_ip:
        print(f"       检测到门禁网络 IP: {mac_ip} ✓")
    else:
        print("       未检测到 192.168.16.xxx 网段的 IP")
        print("       请确认 MacBook 已连接到门禁网络（WiFi 或有线）")
        print("       当前所有网络接口的 IP：")
        os.system("ifconfig | grep 'inet '")
        sys.exit(1)

    # 步骤 2: 询问配置
    print("\n[配置] 请输入 Addon 配置参数（直接回车使用默认值）：\n")

    target_ip = ask_question("Addon 的 local_ip (HA主机IP)", "192.168.16.64")
    local_id = ask_question("Addon 的 local_id (室内机ID)", "00010116010")
    door_no = ask_question("要模拟的门口机编号", "01")
    duration = int(ask_question("呼叫持续时间(秒)", "30"))

    print("\n" + "-" * 56)
    print("  配置确认：")
    print(f"    HA 主机 IP:  {target_ip}")
    print(f"    室内机 ID:   {local_id}")
    print(f"    MacBook IP:  {mac_ip}")
    print(f"    模拟门口机:  {door_no}号机")
    print(f"    持续时间:    {duration} 秒")
    print("-" * 56)

    # 步骤 3: 关键提示
    print("\n⚠️  重要：在运行测试前，请先在 Home Assistant 中完成以下操作：")
    print("\n    1. 进入「设置 → 加载项 → 虚拟门禁系统 → 配置」")
    print(f"    2. 在 custom_device_overrides 中添加：")
    print(f"       {door_no}:{mac_ip}")
    print("    3. 保存配置并重启 Addon")
    print("    4. 确认 Addon 日志显示「已加载门口机」\n")

    confirm = ask_question("已完成上述配置？(yes/no)", "no")
    if confirm.lower() not in ("yes", "y", "是"):
        print("\n请先完成配置后再运行脚本。")
        print("配置完成后，直接重新运行此脚本即可。")
        sys.exit(0)

    # 步骤 4: 运行测试
    run_test(target_ip, local_id, mac_ip, door_no, duration)

    # 步骤 5: 测试后提示
    print("\n[结果检查] 请确认 Home Assistant 中是否出现以下现象：")
    print("  ✓ Dashboard 卡片弹出「呼入中」弹窗")
    print("  ✓ 弹窗显示视频画面")
    print("  ✓ 有「接听」「解锁」「挂断」按钮")
    print("  ✓ 点击「接听」后视频继续")
    print("\n如果没有弹窗，请检查：")
    print("  1. Addon 是否已启动（日志显示「监听中」）")
    print("  2. Integration 是否已配置并显示实体")
    print("  3. Dashboard 卡片是否正确添加")
    print("  4. 浏览器是否已刷新（Ctrl+Shift+R）")
    print("\n测试完成后，记得将 Addon 配置中的 custom_device_overrides")
    print("改回真实的门口机 IP，避免影响正常使用。")
    print()


if __name__ == "__main__":
    main()
