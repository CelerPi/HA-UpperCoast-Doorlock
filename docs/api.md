# 后端接口

当前后端应用提供一个轻量 JSON 接口，用于后续 HA 集成调用，也方便第一次在 HA 中验证应用是否正常启动。

默认监听：

```text
http://<HA主机IP>:8099
```

监听地址和端口由应用配置页控制：

```yaml
api_host: "0.0.0.0"
api_port: 8099
api_token: ""
```

`api_token` 为空时，状态接口可用，解锁/接听动作接口会拒绝请求。要测试动作接口，请先设置一个 token。

## 健康检查

```bash
curl http://<HA主机IP>:8099/health
```

正常返回：

```json
{"ok": true}
```

## 状态

```bash
curl http://<HA主机IP>:8099/api/status
```

返回内容包括：

- 当前监听/呼叫状态。
- 当前呼叫门口机 IP。
- 当前楼栋和已启用门口机数量。

## 解锁

需要设置 `api_token`，并传入访问令牌：

```bash
curl -X POST http://<HA主机IP>:8099/api/unlock \
  -H "Authorization: Bearer <api_token>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

如果当前存在呼叫会话，后端会请求发送 `b7000600` 解锁 burst。

## 接听

```bash
curl -X POST http://<HA主机IP>:8099/api/answer \
  -H "Authorization: Bearer <api_token>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

如果当前存在呼叫会话，后端会请求发送 `b7000500` 接听命令。

## 指定目标 IP

动作接口默认使用当前呼叫中的门口机 IP。调试时也可以显式指定：

```json
{"target_ip": "192.168.16.225"}
```

如果指定 IP 不是当前呼叫来源，接口会返回 `409 Conflict`。
