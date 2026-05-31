# 云海湾门禁系统 — 安装指南

![version](https://img.shields.io/badge/release-v0.2.0-blue)
![ha-version](https://img.shields.io/badge/HA-2026.5.0%2B-41BDF5)

完整的新手安装教程，覆盖 App（应用）、Integration（集成）和 Lovelace 卡片（Dashboard）三件套的一键安装与手动安装方式。

---

## 前置条件

| 项目 | 要求 |
|------|------|
| Home Assistant | 2026.5.0 或更高版本（**HAOS / Supervisor 推荐**）|
| HACS | 已安装并正常运行 |
| 网络 | App 需使用 HA 主机的实际 IP（不能填 localhost）|

> 如果你还没装 HACS，先去 https://hacs.xyz 按官方教程安装。

---

## 方式一：一键安装脚本（推荐）

如果你已经通过 SSH 或终端登录到 Home Assistant 主机（HAOS / Supervisor），可以直接运行一键安装脚本：

```bash
# 下载并运行一键安装脚本
curl -fsSL https://raw.githubusercontent.com/CelerPi/HA-UpperCoast-Doorlock/main/install.sh | bash
```

脚本会自动完成以下操作：

1. 下载并安装 Integration 到 `/config/custom_components/uppercoast_doorlock/`
2. 下载 App 到 `/addons/uppercoast_doorlock/`
3. 下载 Card JS 文件到 `/config/www/HA-UpperCoast-DoorLock-Card.js`
4. 注册前端资源到 Lovelace
5. 提示你重启 Home Assistant

运行完成后，在 Home Assistant 中进入 **开发者工具 → 重新启动**，重启后即可继续下面的配置步骤。

---

## 方式二：手动安装

如果一键脚本不适用，请按以下步骤手动安装。

### 第一步：安装 App（应用）

1. 打开 Home Assistant，进入 **设置 → 应用 → 应用商店**
2. 点击右上角菜单 **⋮ → 仓库**
3. 添加仓库地址：
   ```
   https://github.com/CelerPi/HA-UpperCoast-DoorLock-Addon
   ```
4. 点击 **添加 → 关闭**
5. 商店列表会自动刷新，找到 **虚拟门禁系统**，点击 **安装**
6. 安装完成后，进入 **配置** 标签页，填写以下参数：

   | 参数 | 说明 | 示例 |
   |------|------|------|
   | `building_id` | 你的楼栋 | `1A`（对应1栋A座） |
   | `local_ip` | HA 主机在门禁网络中的 IP | `192.168.16.64` |
   | `local_id` | 室内机 ID（房号对应的设备编号）| `00010116010` |
   | `api_token` | API 访问令牌 | `1234` |

   > 中心地址（`192.168.16.2`）和物业中心机地址（`192.168.16.3`）为本小区固定值，已内置在 App 代码中，无需在配置页填写。如果你的小区网络环境不同，请手动编辑 App 目录下的 `app/uppercoast_doorlock/config.py`，修改 `DEFAULT_CENTER_IP` 和 `DEFAULT_PROPERTY_CENTER_IP` 常量后重新安装 App。

   > **自定义号机覆盖**：默认情况下 App 会根据楼栋自动加载门口机 IP。如果你需要覆盖某些号机，在 `custom_device_overrides` 中添加，格式为 `号机编号:IP地址`（如 `01:192.168.16.224`）。App 启动时会自动校验号机是否属于当前楼栋，格式错误或号机不合法的项会被忽略并记录日志。不需要覆盖的号机留空即可。

7. 点击 **保存**，然后切换到 **信息** 标签页，点击 **启动**
8. 在 **日志** 中确认看到类似以下内容，表示 App 启动成功：
   ```
   门禁系统后端已启动
   楼栋：1栋A座；已加载门口机：8 个
   后端接口：http://0.0.0.0:8099
   ```

> **重要**：`local_ip` 必须填写 HA 主机在门禁网络中的实际 IP，不能填 `127.0.0.1` 或 `localhost`。

---

### 第二步：安装 Integration（集成）

#### 通过 HACS 安装（推荐）

1. 打开 **HACS → 集成**
2. 点击右下角 **⋮ → 自定义仓库**
3. 填入仓库地址：
   ```
   https://github.com/CelerPi/HA-UpperCoast-Doorlock-Integration
   ```
4. 类别选择：**集成**
5. 在列表中找到 **云海湾门禁-集成**，点击 **下载**
6. 下载完成后，**重启 Home Assistant**

#### 手动安装

1. 下载本仓库的 `custom_components/uppercoast_doorlock/` 整个目录
2. 将其复制到 Home Assistant 的 `config/custom_components/` 下
3. 重启 Home Assistant

---

### 第三步：配置 Integration

1. 重启后，进入 **设置 → 设备与服务 → 添加集成**
2. 搜索 **虚拟门禁系统**，点击添加
3. 在配置页面填写：
   - **Host**：App 的访问地址，即 HA 主机的实际 IP（如 `192.168.16.64`）
   - **Port**：`8099`（App 默认端口）
   - **Token**：与 App 配置中的 `api_token` 保持一致
4. 点击 **提交**，系统会自动测试连接
5. 连接成功后，你会看到 Integration 创建了以下实体：
   - `binary_sensor.vds_call_status` — 呼叫状态
   - `camera.vds_video` — 视频画面
   - `button.vds_unlock` — 解锁按钮
   - `button.vds_answer` — 接听按钮
   - `button.vds_hangup` — 挂断按钮

> **常见问题**：如果提示连接失败，检查 App 是否已启动、Host 是否填的是 HA 主机实际 IP、防火墙是否放行 8099 端口。

---

### 第四步：安装 Dashboard 卡片

#### 通过 HACS 安装（推荐）

1. 打开 **HACS → 前端**
2. 点击右下角 **⋮ → 自定义仓库**
3. 填入仓库地址：
   ```
   https://github.com/CelerPi/HA-UpperCoast-Doorlock-Card
   ```
4. 类别选择：**仪表盘**
5. 在列表中找到 **云海湾门禁-dashboard**，点击 **下载**
6. 下载完成后，刷新浏览器（**Ctrl + F5 / Cmd + Shift + R**）

#### 手动安装

1. 下载 `HA-UpperCoast-DoorLock-Card.js`
2. 复制到 `config/www/HA-UpperCoast-DoorLock-Card.js`
3. 进入 **设置 → 仪表盘 → 右上角 ⋮ → 资源 → 添加资源**
   - URL：`/local/HA-UpperCoast-DoorLock-Card.js`
   - 资源类型：**JavaScript Module**
4. 保存并刷新浏览器

---

### 第五步：添加卡片到仪表盘

1. 进入任意 Lovelace 仪表盘，点击右上角 **编辑**
2. 点击 **添加卡片**，搜索 **云海湾门禁卡片**
3. 添加后，在 YAML 模式下确认配置如下：
   ```yaml
   type: custom:doorlock-card
   building_id: building_1_a
   ```
4. `building_id` 对应你的楼栋，可选值见下表：

   | ID | 楼栋 |
   |----|------|
   | `building_1_a` | 1 栋 A 座 |
   | `building_1_b` | 1 栋 B 座 |
   | `building_1_c` | 1 栋 C 座 |
   | `building_1_d` | 1 栋 D 座 |
   | `building_1_e` | 1 栋 E 座 |
   | `building_2_a` | 2 栋 A 座 |
   | `building_2_b` | 2 栋 B 座 |
   | `building_2_c` | 2 栋 C 座 |

5. 保存仪表盘，你应该能看到卡片正常显示楼栋名称和「对讲」「监控」两个按钮。

---

## 功能验证

安装完成后，验证以下功能是否正常：

1. **卡片显示**：首页显示「云海湾门禁」卡片，右上角状态为「在线」
2. **监控功能**：点击「监控」→ 选择任意号机 → 能看到视频画面 → 点击「停止监控」返回选择页
3. **对讲拨号**：点击「对讲」→ 拨号盘输入房号 → 点击「呼叫」（目前仅记录通话历史，实际呼叫需等待 App 后续支持）
4. **呼入测试**：让门口机呼叫你的室内机，HA 应自动弹出视频弹窗，显示「呼入中」，可点击「接听」「解锁」「挂断」

---

## 故障排查

### 1. 卡片显示 "Integration 未就绪"

- 确认 Integration 已添加且状态正常
- 检查 `binary_sensor.vds_call_status` 实体是否存在
- 查看 App 日志确认已正常启动
- 确认 Integration 配置的 Host 是 HA 主机实际 IP，不是 `localhost`

### 2. 监控页面显示 "暂无门口机数据"

- 确认 App 已启动且日志显示「已加载门口机 X 个」
- 确认 App 的 `building_id` 配置正确，号机数量不为 0
- 在浏览器 F12 → Console 中查看调试信息

### 3. 提示 "Custom element doesn't exist: doorlock-card"

- 确认已通过 HACS 下载或手动放置了 JS 文件
- 检查 **设置 → 仪表盘 → 资源** 中是否存在对应的 JavaScript Module
- 强制刷新浏览器缓存（Ctrl + F5 / Cmd + Shift + R）
- 查看浏览器开发者工具 Console，确认 JS 文件是否 404 或存在加载报错

### 4. 实体 ID 是拼音或过长

- 确保安装的是 Integration v0.1.5 或更高版本
- 已使用 `translation_key` + `has_entity_name = True` + `_attr_suggested_object_id`，实体 ID 固定为英文简写（如 `vds_call_status`）
- 升级后建议删除旧集成条目并重新添加，以清除 entity registry 中的缓存

---

## 更新

当仓库发布新版本时：

| 组件 | 更新方式 |
|------|----------|
| App | 应用页面 → **虚拟门禁系统** → 右上角 ⋮ → **重新安装** |
| Integration | HACS → 集成 → 找到对应仓库 → **重新下载** → 重启 HA |
| Card | HACS → 前端 → 找到对应仓库 → **重新下载** → 刷新浏览器 |

---

## 相关仓库

| 仓库 | 说明 |
|------|------|
| [HA-UpperCoast-Doorlock](https://github.com/CelerPi/HA-UpperCoast-Doorlock) | 本仓库，安装指南 |
| [HA-UpperCoast-Doorlock-Integration](https://github.com/CelerPi/HA-UpperCoast-Doorlock-Integration) | 集成（Integration）源码 |
| [HA-UpperCoast-DoorLock-App](https://github.com/CelerPi/HA-UpperCoast-DoorLock-addon) | App 源码 |
| [HA-UpperCoast-DoorLock-Card](https://github.com/CelerPi/HA-UpperCoast-DoorLock-Card) | Dashboard 卡片源码 |

## License

[MIT](LICENSE)
