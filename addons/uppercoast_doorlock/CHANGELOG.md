# 更新日志

## 0.1.4 - 2026-05-27

- 新增 `POST /api/monitor/start` 和 `/api/monitor/stop` 接口，支持主动监控指定门口机
- 新增 `request_monitor_start` 和 `request_monitor_stop` 方法到 `IntercomCore`
- 新增 `monitor_start` 和 `monitor_stop` 服务，支持从 HA 调用主动监控
- Dashboard 卡片支持点击门口机卡片直接弹出监控窗口
- Dashboard 卡片新增监控弹窗 UI（独立于呼叫弹窗）

## 0.1.3 - 2026-05-27

- 实体拆分独立平台文件：binary_sensor.py、camera.py、button.py
- 实体图标确认：binary_sensor (doorbell-video)、camera (cctv)、button解锁 (door-open)、button接听 (phone)、button挂断 (phone-hangup)

## 0.1.2 - 2026-05-27

- 修复 HA 集成 `update_interval` 参数类型错误：`float` 改为 `timedelta`。
- 添加中文/英文国际化翻译文件（zh.json / en.json），ConfigFlow UI 现已支持中文显示。

## 0.1.1 - 2026-05-27

- 新增 `GET /api/frame` 接口，返回当前 JPEG 视频帧，供 HA 集成 camera 实体调用。
- 新增 `POST /api/hangup` 接口，挂断当前通话。
- 新增 `request_hangup()` 方法到 `IntercomCore`，触发通话结束。
- 新增 `get_frame()` 方法到 `FrameHub`，获取当前帧数据。
- Build config 中 building_id 下拉选项移除 `2栋B座`（该楼栋不存在）。

## 0.1.0 - 2026-05-27

- 将应用目录、应用标识和 Python 包名统一改为 `uppercoast_doorlock`。
- 加载项名称使用中文功能名：虚拟门禁系统。
- 当前仅支持的可视对讲品牌：麦驰可视对讲机。
- 楼栋下拉选项为中文楼栋名，保存并重启后加载对应门口机配置。
- 启动日志输出为中文摘要，不再输出完整 JSON 配置。
- 配置页、应用说明、使用文档和排障文档均使用中文命名。
