# HA 集成云海湾门禁系统 — 开发记录

更新时间：2026-05-27

---

## 项目背景

**原项目位置**：`/Users/0xmalphite/Desktop/Unlock`
**原项目 handoff**：`/Users/0xmalphite/Desktop/Unlock/handoff.md`

这个仓库（HA 集成云海湾门禁系统）是将原项目 `Unlock` 的已验证门禁协议和虚拟室内机原型，逐步迁移到 Home Assistant 中运行的加载项和集成。

### 关键结论（来自原项目 handoff.md）

1. **必须先呼叫才能开锁** — 室外机内部有"正在呼叫 1601"的状态门槛，单独发送开门包（b7000600）会被忽略
2. **b7000600** 是确认有效的呼叫会话开锁命令，**b7000c00** 是呼叫/视频会话保活包
3. **b800** 监控会话不能替代呼叫状态
4. **本机 IP 必须绑定在 10000 端口**，源端口随机会导致开门失败
5. **音频**：b7000a00 包含 channel=1（JPEG 视频分片）和 channel=3（8kHz/mono/signed 16-bit PCM）

---

## 当前仓库文件结构

```
HA 集成云海湾门禁系统/
├── repository.yaml              — HA 加载项仓库识别文件
├── README.md                    — 项目总览和迁移计划
├── handoff.md                   — 本文件，记录开发进度
├── addons/
│   └── uppercoast_doorlock/     — HA Addon
│       ├── config.yaml           — addon 配置（楼栋、本机 IP/ID、门口机 IP 等）
│       ├── Dockerfile
│       ├── run.sh
│       ├── CHANGELOG.md
│       ├── README.md
│       ├── app/
│       │   └── uppercoast_doorlock/
│       │       ├── __init__.py
│       │       ├── api.py            — HTTP API（/health、/api/status、/api/frame、/api/unlock、/api/answer、/api/hangup）
│       │       ├── call_state.py    — 呼叫状态跟踪
│       │       ├── config.py        — 配置加载、BUILDING_IPS_BY_ID 等
│       │       ├── core.py          — IntercomCore：UDP 监听、视频组装、解锁协议核心
│       │       ├── protocol.py      — UDP payload 构建和解析
│       │       ├── server.py        — 入口，启动 core + api_server
│       │       └── store.py
│       └── translations/
├── custom_components/           — HA 集成（第三阶段）
│   └── uppercoast_doorlock/
│       ├── __init__.py          — 集成入口
│       ├── manifest.json         — 集成元数据，config_flow:true
│       ├── const.py             — DOMAIN 常量
│       ├── api.py               — HTTP 客户端
│       ├── coordinator.py       — 定时轮询 + 事件发布
│       ├── binary_sensor.py     — 门禁呼叫状态实体
│       ├── camera.py            — 门禁视频实体
│       ├── button.py            — 解锁/接听/挂断 三个按钮实体
│       ├── services.py          — HA 服务调用实现
│       ├── services.yaml        — 服务声明
│       ├── config_flow.py       — UI 配置入口
│       └── translations/
│           ├── zh.json          — 中文翻译
│           └── en.json          — 英文翻译
├── docs/                        — 使用文档
│   ├── get-start.md
│   ├── configuration.md
│   ├── network.md
│   ├── api.md
│   ├── ha-first-test.md
│   ├── troubleshooting.md
│   └── building-ips.md
└── tests/                       — 单元测试（pytest）
```

---

## 迁移计划

| 阶段 | 内容 | 状态 |
|------|------|------|
| 第一阶段 | 整理原型，拆清职责 | ✅ 完成 |
| 第二阶段 | 创建 HA Addon 骨架 | ✅ 完成 |
| 第三阶段 | 创建 HA 集成（实体、服务、事件） | ✅ 完成 |
| 第四阶段 | 仪表盘卡片（Lovelace Custom Card） | ✅ 完成 |
| 第五阶段 | 音频通话、物业中心呼叫、更多楼栋 | 待开始 |

---

## 第三阶段：HA 集成（custom_components）

### 实体列表（当前版本 v0.1.4）

| 实体类型 | 名称 | 图标 | 说明 |
|----------|------|------|------|
| binary_sensor | 门禁呼叫状态 | mdi:doorbell-video | 是否有活跃呼叫；attributes 含门口机详情 |
| camera | 门禁视频 | mdi:cctv | 通过 /api/frame 获取当前 JPEG 帧 |
| button | 门禁解锁 | mdi:door-open | 点击触发 /api/unlock |
| button | 门禁接听 | mdi:phone | 点击触发 /api/answer |
| button | 门禁挂断 | mdi:phone-hangup | 点击触发 /api/hangup |

### 事件列表

| 事件名 | 触发条件 | 数据字段 |
|--------|----------|----------|
| `uppercoast_doorlock_call_started` | 检测到 in_call 从 False → True | device_name, display_name, target_ip, floor_label, position_detail |
| `uppercoast_doorlock_call_ended` | 检测到 in_call 从 True → False | device_name, display_name, target_ip |
| `uppercoast_doorlock_frame_received` | frame_id 变化（新视频帧到达） | frame_id |

### 服务调用

- `uppercoast_doorlock.unlock` — 解锁门口机
- `uppercoast_doorlock.answer` — 接听呼叫
- `uppercoast_doorlock.hangup` — 挂断通话

### addon 与集成的通信关系

```
HA Addon (addon/uppercoast_doorlock)
  ├── 绑定 UDP 10000/10008 监听门外机呼叫
  ├── /api/status     ← 集成每 1 秒轮询
  ├── /api/frame      ← 集成获取当前 JPEG 视频帧
  ├── /api/unlock     ← 集成调用（解锁）
  ├── /api/answer     ← 集成调用（接听）
  └── /api/hangup     ← 集成调用（挂断）

HA 集成 (custom_components/uppercoast_doorlock)
  ├── 定时轮询 addon /api/status
  ├── 状态变化 → 发布 HA 事件到 bus
  └── 提供实体（binary_sensor / camera / 3×button）
```

### 版本历史

| 版本 | 变更 |
|------|------|
| v0.1.0 | 初始版本，应用目录和标识统一 |
| v0.1.1 | 新增 /api/frame、/api/hangup 接口 |
| v0.1.2 | 修复 update_interval 类型错误；添加中英文翻译 |
| v0.1.3 | 实体拆分独立平台文件；修复 button 平台漏加载 |
| v0.1.4 | 新增 monitor_start/monitor_stop 服务；Dashboard 卡片点击门口机监控 |

---

## 第四阶段：仪表盘卡片 ✅

**目标**：创建 Lovelace Custom Card，复刻虚拟室内机界面和弹窗交互。

### 已完成

1. **dashboard/doorlock-card.js** — 完整玻璃拟态 UI 的 LitElement 卡片
2. **dashboard/doorlock-card.json** — HACS 资源声明
3. **门口机卡片**：4列响应式门机网格，楼层色彩条，状态指示灯
4. **呼叫弹窗**：动画呼叫图标、视频区域、三操作按钮（解锁/接听/挂断）
5. **事件监听**：通过 hass.connection.socket 监听 call_started/call_ended 事件
6. **楼栋配置**：支持 building_id 选择不同楼栋
7. **点击门口机监控**：点击门口机卡片 → 弹出监控窗口，调用 monitor_start 服务
8. **监控服务**：新增 monitor_start / monitor_stop 服务，支持主动监控指定门口机

### 待做事项

- [ ] 监控弹窗内视频帧渲染（camera entity 或直接 /api/frame 轮询）
- [ ] HACS 插件化发布
- [ ] 与 HA Dashboard 集成配置示例

---

## 各楼栋门口机 IP（已确认）

来源：/Users/0xmalphite/Downloads/ExportBlock-b23bdf6e-3861-4c7a-80e1-502f34aecd6c-Part-1
号段代表 IP 第三段，如号段 16 → 192.168.16.*

### 1栋A座（号段 16）

| 号机 | IP | 位置 |
|------|-----|------|
| 1号机 | 192.168.16.224 | 1F |
| 2号机 | 192.168.16.225 | 2F |
| 3号机 | 192.168.16.226 | -1F |
| 4号机 | 192.168.16.227 | -2F |
| 5号机 | 192.168.16.228 | -1F |
| 6号机 | 192.168.16.229 | -1F |
| 7号机 | 192.168.23.164 | -2F |
| 8号机 | 192.168.23.165 | 1F |

### 1栋B座（号段 18）

| 号机 | IP | 位置 |
|------|-----|------|
| 1号机 | 192.168.18.96 | 1F |
| 2号机 | 192.168.18.97 | 2F |
| 3号机 | 192.168.18.98 | -1F |
| 4号机 | 192.168.18.99 | -2F |
| 5号机 | 192.168.18.100 | -2F |
| 6号机 | 192.168.18.101 | 1F |
| 7号机 | 192.168.23.167 | 2F |

### 1栋C座（号段 19）

| 号机 | IP | 位置 |
|------|-----|------|
| 1号机 | 192.168.19.98 | 1F |
| 2号机 | 192.168.19.99 | 2F |
| 3号机 | 192.168.19.100 | -1F |
| 4号机 | 192.168.19.101 | -2F |
| 5号机 | 192.168.19.102 | -1F |
| 6号机 | 192.168.19.103 | 1F |
| 7号机 | 192.168.23.168 | 2F |

### 1栋D座（号段 19）

| 号机 | IP | 位置 |
|------|-----|------|
| 1号机 | 192.168.19.219 | 1F |
| 2号机 | 192.168.19.220 | 1F |
| 3号机 | 192.168.19.221 | -1F |
| 4号机 | 192.168.19.222 | -1F |
| 5号机 | 192.168.19.223 | 2F |
| 6号机 | 192.168.19.224 | 2F |
| 7号机 | 192.168.23.163 | 1F |
| 8号机 | 192.168.23.164 | 1F |

### 1栋E座（号段 20）

| 号机 | IP | 位置 |
|------|-----|------|
| 1号机 | 192.168.20.116 | 1F |
| 2号机 | 192.168.20.117 | 2F |
| 3号机 | 192.168.20.118 | -1F |
| 4号机 | 192.168.20.119 | 1F |
| 5号机 | 192.168.20.120 | 2F |

### 2栋A座（号段 21）

| 号机 | IP | 位置 |
|------|-----|------|
| 1号机 | 192.168.21.212 | 1F |
| 2号机 | 192.168.21.213 | 2F |
| 3号机 | 192.168.21.214 | -1F |
| 4号机 | 192.168.21.215 | -2F |
| 5号机 | 192.168.21.216 | 1F |
| 6号机 | 192.168.21.217 | 2F |

### 2栋B座（号段 22）

| 号机 | IP | 位置 |
|------|-----|------|
| 1号机 | 192.168.22.184 | 1F |
| 2号机 | 192.168.22.185 | 2F |
| 3号机 | 192.168.22.186 | -1F |
| 4号机 | 192.168.22.187 | -2F |

### 2栋C座（号段 23）

| 号机 | IP | 位置 |
|------|-----|------|
| 1号机 | 192.168.23.155 | 1F |
| 2号机 | 192.168.23.156 | 2F |
| 3号机 | 192.168.23.157 | -1F |
| 4号机 | 192.168.23.158 | -2F |
| 5号机 | 待补充 | 缺失 |
| 6号机 | 192.168.23.160 | -1F |
| 7号机 | 192.168.23.161 | -2F |
| 8号机 | 192.168.23.169 | 2F |

### 已知 IP 冲突

- **192.168.23.164**：1栋A座 7号机 和 1栋D座 8号机 重复，需现场核实

---

## 网络常量

| 常量 | 值 |
|------|-----|
| 子网掩码 | 255.255.248.0 |
| 网关地址 | 192.168.16.1 |
| 中心地址 | 192.168.16.2 |
| 物业中心机 | 192.168.16.3 |
| 本机 IP | 192.168.16.64 |
| 本机 ID | 00010116010 |

---

## 待完善

1. **第四阶段** — 仪表盘卡片开发（见上文）
2. **IP 冲突核实** — 192.168.23.164 需现场确认归属
3. **2栋C座 5号机** — 待补充 IP
4. **自动化测试** — 目前 tests/ 目录仅有 Python 单元测试

---

## 在 HA 上安装使用

1. 通过 HACS 安装 `uppercoast_doorlock` 集成（或手动复制 custom_components）
2. 重启 HA
3. **配置 → 集成 → 添加集成 → 搜索 `虚拟门禁系统`**
4. 填写配置：

| 字段 | 值 | 说明 |
|------|-----|------|
| **Addon 地址** | `192.168.16.64` | Addon 所在主机 IP |
| **端口** | `8099` | addon API 端口 |
| **API 令牌** | 你在 addon config 中设置的 token | 认证令牌 |

5. 集成添加成功后可用实体：binary_sensor、camera、3个 button
6. 自动化可订阅事件：`uppercoast_doorlock_call_started` / `uppercoast_doorlock_call_ended`

### 自动化示例

```yaml
automation:
  - alias: 门禁呼入通知
    trigger:
      platform: event
      event_type: uppercoast_doorlock_call_started
    action:
      - service: notify.persistent_notification
        data:
          title: 门禁呼叫
          message: "{{ trigger.event.data.display_name }} 正在呼叫"

  - alias: 呼叫结束自动关闭
    trigger:
      platform: event
      event_type: uppercoast_doorlock_call_ended
    action:
      - service: persistent_notification.dismiss
        data:
          notification_id: doorlock_call
```