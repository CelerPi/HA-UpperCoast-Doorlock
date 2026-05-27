# 云海湾门禁系统

麦驰可视对讲门禁系统的 Home Assistant 一站式解决方案。

---

## 📦 安装指南

### 第一步：安装 Addon

1. HA → 配置 → Add-on Store → Repositories
2. 添加：`https://github.com/CelerPi/HA-UpperCoast-DoorLock-System`
3. 搜索 **虚拟门禁系统** → 安装

### 第二步：安装集成（通过 HACS）

1. HACS → 集成 → 右下角 → **自定义仓库**
2. 填入：`https://github.com/CelerPi/HA-UpperCoast-Doorlock-Integration`
3. 类别选择：**集成**
4. 搜索并下载 **虚拟门禁系统**

### 第三步：安装仪表盘卡片（通过 HACS）

1. HACS → 仪表盘 → 右下角 → **自定义仓库**
2. 填入：`https://github.com/CelerPi/HA-UpperCoast-Doorlock-Card`
3. 类别选择：**仪表盘**
4. 搜索并下载 **云海湾门禁卡片**

### 第四步：配置集成

1. 重启 HA
2. 配置 → 集成 → 添加集成 → 搜索 **虚拟门禁系统**
3. 填写配置：
   - **Addon 地址**：`192.168.16.64`（Addon 所在主机 IP）
   - **端口**：`8099`
   - **API 令牌**：你在 Addon config 中设置的 token

### 第五步：在仪表盘添加卡片

1. 仪表盘 → 编辑 → 添加卡片
2. 选择任意卡片
3. 在 YAML 模式下填入：

```yaml
type: custom:doorlock-card
building_id: building_1_a
```

---

## 🏠 楼栋配置

| ID | 楼栋 |
|----|------|
| building_1_a | 1栋A座 |
| building_1_b | 1栋B座 |
| building_1_c | 1栋C座 |
| building_1_d | 1栋D座 |
| building_1_e | 1栋E座 |
| building_2_a | 2栋A座 |
| building_2_b | 2栋B座 |
| building_2_c | 2栋C座 |

---

## 📁 相关仓库

| 仓库 | 说明 |
|------|------|
| [HA-UpperCoast-DoorLock-System](https://github.com/CelerPi/HA-UpperCoast-DoorLock-System) | Addon 源码 |
| [HA-UpperCoast-Doorlock-Integration](https://github.com/CelerPi/HA-UpperCoast-Doorlock-Integration) | 集成源码 |
| [HA-UpperCoast-Doorlock-Card](https://github.com/CelerPi/HA-UpperCoast-Doorlock-Card) | 仪表盘卡片源码 |

---

## 🔧 故障排除

### 卡片显示 "Custom element doesn't exist"

1. 确保已安装卡片插件
2. 确保在 HACS 里更新到最新版本
3. 重启 HA
4. 检查资源路径是否为 `/hacsfiles/...`

### 无法添加集成

1. 确保 Addon 已正确运行
2. 检查 Addon 日志确认 API 服务正常
3. 确认 API token 正确配置

### 门口机呼叫无反应

1. 确认 HA 和门口机在同一网络
2. 检查本机 IP 和门口机 IP 是否正确
3. 确认 Addon 的 `local_ip` 和 `local_id` 配置正确

---

## 📄 许可证

MIT License