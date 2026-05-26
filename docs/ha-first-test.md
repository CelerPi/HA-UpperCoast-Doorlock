# HA 首次测试清单

这份清单用于第一次在 Home Assistant 里安装后端应用后验证基础运行状态。当前代码尚未在 HA 实机中测试，因此请按顺序逐项确认。

## 1. 安装前确认

- HA 主机已接入门禁网络。
- HA 主机有门禁网段 IP，例如 `192.168.16.64`。
- 原室内机没有同时使用同一个 IP。
- 旧 `Unlock` 原型和其他测试脚本已经关闭。

## 2. 应用配置

在应用配置页中填写：

```yaml
local_ip: "192.168.16.64"
local_id: "00010116010"
building_id: "building_1_a"
center_ip: "192.168.16.2"
property_center_ip: "192.168.16.3"
api_host: "0.0.0.0"
api_port: 8099
api_token: "自己设置一个长一点的随机字符串"
```

## 3. 启动检查

启动应用后查看日志，确认没有：

- `已被占用`
- `不在当前网卡上`
- Python traceback

日志里应出现启动成功记录。

## 4. 后端接口检查

在同一网络内运行：

```bash
curl http://<HA主机IP>:8099/health
curl http://<HA主机IP>:8099/api/status
```

`/health` 应返回 `{"ok": true}`。

`/api/status` 应能看到：

- `building_id`
- `active_device_count`
- `runtime.status`

## 5. 呼入检查

在门口机上呼叫当前房号。然后再次调用：

```bash
curl http://<HA主机IP>:8099/api/status
```

如果呼入被识别，状态中应出现：

```json
"in_call": true
```

并带有当前门口机 `target_ip`。

## 6. 解锁检查

确认正在呼叫窗口内，再执行：

```bash
curl -X POST http://<HA主机IP>:8099/api/unlock \
  -H "Authorization: Bearer <api_token>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

预期：

- HTTP 返回 `{"ok": true, ...}`。
- 门口机开锁。

如果返回 `409 Conflict`，说明当前没有匹配的呼叫会话，或呼叫来源 IP 与目标 IP 不一致。
