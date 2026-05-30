#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# 云海湾门禁系统 — 一键安装脚本
# 适用环境：Home Assistant OS / Supervisor（通过 SSH/终端运行）
# =============================================================================

REPO_BASE="https://github.com/CelerPi"
INTEGRATION_REPO="${REPO_BASE}/HA-UpperCoast-Doorlock-Integration"
ADDON_REPO="${REPO_BASE}/HA-UpperCoast-DoorLock-addon"
CARD_REPO="${REPO_BASE}/HA-UpperCoast-Doorlock-Card"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# 检测运行环境
detect_env() {
    CONFIG_DIR=""
    ADDONS_DIR=""

    if [ -d "/config" ] && [ -f "/config/configuration.yaml" ]; then
        CONFIG_DIR="/config"
        ADDONS_DIR="/addons"
        info "检测到 Home Assistant OS / Supervisor 环境"
    elif [ -d "$HOME/.homeassistant" ]; then
        CONFIG_DIR="$HOME/.homeassistant"
        ADDONS_DIR=""
        warn "检测到 Core (venv) 环境，App 需要手动安装"
    elif [ -d "/usr/src/homeassistant" ]; then
        CONFIG_DIR="/config"
        ADDONS_DIR="/addons"
        info "检测到容器化 Home Assistant 环境"
    else
        error "无法自动检测 Home Assistant 配置目录"
        echo "请手动指定 CONFIG_DIR 环境变量后重新运行："
        echo "  export CONFIG_DIR=/path/to/config"
        echo "  bash install.sh"
        exit 1
    fi

    info "配置目录: ${CONFIG_DIR}"
    if [ -n "${ADDONS_DIR}" ]; then
        info "应用目录: ${ADDONS_DIR}"
    fi
}

# 检查必要命令
check_deps() {
    local missing=()
    for cmd in curl unzip python3; do
        if ! command -v "$cmd" &> /dev/null; then
            missing+=("$cmd")
        fi
    done

    if [ ${#missing[@]} -ne 0 ]; then
        error "缺少必要命令: ${missing[*]}"
        info "在 HAOS 中可以通过以下方式安装："
        info "  apk add curl unzip python3"
        exit 1
    fi
}

# 下载 GitHub 仓库最新 release 的 ZIP
download_repo() {
    local repo_url="$1"
    local dest_dir="$2"
    local name="$3"

    info "正在下载 ${name} ..."

    local tmpzip="/tmp/${name}.zip"
    local tmpdir="/tmp/${name}-extract"

    # 清理旧文件
    rm -rf "$tmpdir" "$tmpzip"

    # 下载主分支 ZIP
    local zip_url="${repo_url}/archive/refs/heads/main.zip"
    if ! curl -fsSL -o "$tmpzip" "$zip_url"; then
        # 尝试 master 分支
        zip_url="${repo_url}/archive/refs/heads/master.zip"
        if ! curl -fsSL -o "$tmpzip" "$zip_url"; then
            error "下载 ${name} 失败，请检查网络连接"
            return 1
        fi
    fi

    # 解压
    unzip -q "$tmpzip" -d "$tmpdir"

    # 复制到目标目录
    rm -rf "$dest_dir"
    mkdir -p "$(dirname "$dest_dir")"

    # 找到解压后的根目录（通常是 repo-main/ 或 repo-master/）
    local extracted_root
    extracted_root=$(find "$tmpdir" -maxdepth 1 -type d | tail -n 1)
    mv "$extracted_root" "$dest_dir"

    rm -rf "$tmpdir" "$tmpzip"
    success "${name} 安装完成: ${dest_dir}"
}

# 安装 Integration
install_integration() {
    info "========== 安装 Integration（集成） =========="
    local dest="${CONFIG_DIR}/custom_components/uppercoast_doorlock"

    if [ -d "$dest" ]; then
        warn "Integration 已存在，将覆盖更新"
        rm -rf "$dest"
    fi

    local tmpdir="/tmp/uppercoast-integration"
    download_repo "$INTEGRATION_REPO" "$tmpdir" "uppercoast-integration"

    # 只复制 custom_components 目录下的内容
    if [ -d "${tmpdir}/custom_components/uppercoast_doorlock" ]; then
        cp -r "${tmpdir}/custom_components/uppercoast_doorlock" "$dest"
    else
        # 有些仓库结构不同，尝试直接找 uppercoast_doorlock 目录
        local found
        found=$(find "$tmpdir" -type d -name "uppercoast_doorlock" | head -n 1)
        if [ -n "$found" ]; then
            cp -r "$found" "$dest"
        else
            error "无法在下载的 Integration 包中找到 uppercoast_doorlock 目录"
            rm -rf "$tmpdir"
            return 1
        fi
    fi

    rm -rf "$tmpdir"
    success "Integration 已安装到: ${dest}"
}

# 安装 App
install_app() {
    if [ -z "${ADDONS_DIR}" ]; then
        warn "当前环境不支持自动安装 App，请手动在 UI 中添加仓库："
        echo "  ${ADDON_REPO}"
        return 0
    fi

    info "========== 安装 App（应用） =========="
    local dest="${ADDONS_DIR}/uppercoast_doorlock"

    if [ -d "$dest" ]; then
        warn "App 已存在，将覆盖更新"
        rm -rf "$dest"
    fi

    local tmpdir="/tmp/uppercoast-app"
    download_repo "$ADDON_REPO" "$tmpdir" "uppercoast-app"

    # 仓库已扁平化，App 文件直接在根目录
    if [ -f "${tmpdir}/config.yaml" ]; then
        cp -r "$tmpdir" "$dest"
    else
        error "无法找到 config.yaml，仓库结构异常"
        rm -rf "$tmpdir"
        return 1
    fi

    rm -rf "$tmpdir"
    success "App 已安装到: ${dest}"
    info "请进入 Home Assistant → 设置 → 应用 → 应用商店 → 右上角 ⋮ → 重新加载"
    info "然后找到「虚拟门禁系统」并安装启动"
}

# 安装 Dashboard 卡片
install_card() {
    info "========== 安装 Dashboard 卡片 =========="
    local www_dir="${CONFIG_DIR}/www"
    local card_file="${www_dir}/HA-UpperCoast-DoorLock-Card.js"

    mkdir -p "$www_dir"

    if [ -f "$card_file" ]; then
        warn "卡片 JS 文件已存在，将覆盖更新"
        rm -f "$card_file"
    fi

    # 尝试下载仓库根目录的 JS 文件
    local js_url="${CARD_REPO}/raw/main/HA-UpperCoast-DoorLock-Card.js"
    if ! curl -fsSL -o "$card_file" "$js_url"; then
        js_url="${CARD_REPO}/raw/master/HA-UpperCoast-DoorLock-Card.js"
        if ! curl -fsSL -o "$card_file" "$js_url"; then
            error "下载卡片 JS 文件失败"
            return 1
        fi
    fi

    success "卡片 JS 已安装到: ${card_file}"

    # 注册资源到 Lovelace
    info "正在注册 Lovelace 资源 ..."
    local lovelace_file="${CONFIG_DIR}/lovelace.yaml"
    local ui_lovelace="${CONFIG_DIR}/.storage/lovelace"

    if [ -f "$lovelace_file" ]; then
        # YAML 模式
        if ! grep -q "HA-UpperCoast-DoorLock-Card.js" "$lovelace_file" 2>/dev/null; then
            warn "请手动在 lovelace.yaml 的 resources 中添加："
            echo "  url: /local/HA-UpperCoast-DoorLock-Card.js"
            echo "  type: module"
        else
            info "Lovelace YAML 中已存在资源引用"
        fi
    else
        # UI 模式：尝试通过 Supervisor API 注册
        if command -v hassio &> /dev/null || command -v ha &> /dev/null; then
            # 通过 REST API 添加资源
            local token
            token="${SUPERVISOR_TOKEN:-}"
            if [ -n "$token" ]; then
                curl -fsSL -X POST \
                    -H "Authorization: Bearer ${token}" \
                    -H "Content-Type: application/json" \
                    -d '{"url":"/local/HA-UpperCoast-DoorLock-Card.js","type":"module"}' \
                    "http://supervisor/core/api/config/lovelace/resources" 2>/dev/null || true
            fi
        fi
        info "UI 模式下资源通常会自动识别，如果卡片不显示请手动添加资源"
    fi
}

# 写入 icon.png（可选）
copy_icon() {
    info "========== 复制 Logo 图标 =========="
    local card_icon="${CONFIG_DIR}/www/icon.png"
    local integration_icon="${CONFIG_DIR}/custom_components/uppercoast_doorlock/icon.png"

    # 从卡片仓库下载 icon.png
    local icon_url="${CARD_REPO}/raw/main/icon.png"
    if curl -fsSL -o "$card_icon" "$icon_url" 2>/dev/null || \
       curl -fsSL -o "$card_icon" "${CARD_REPO}/raw/master/icon.png" 2>/dev/null; then
        cp "$card_icon" "$integration_icon" 2>/dev/null || true
        success "Logo 图标已复制"
    else
        warn "Logo 图标下载失败（非关键错误）"
    fi
}

# 主流程
main() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║        云海湾门禁系统 — 一键安装脚本 v1.0.0                  ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""

    detect_env
    check_deps

    echo ""
    read -rp "确认开始安装？(y/N): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        info "已取消安装"
        exit 0
    fi
    echo ""

    install_integration
    echo ""
    install_app
    echo ""
    install_card
    echo ""
    copy_icon
    echo ""

    success "========== 安装完成 =========="
    echo ""
    echo "接下来请完成以下步骤："
    echo ""
    echo "1. 重启 Home Assistant"
    echo "   - HAOS: 设置 → 系统 → 重新启动"
    echo ""
    echo "2. 配置 App"
    echo "   - 设置 → 应用 → 虚拟门禁系统 → 配置"
    echo "   - 填写 building_id、local_ip、local_id 等参数"
    echo "   - 保存并启动 App"
    echo ""
    echo "3. 配置 Integration"
    echo "   - 设置 → 设备与服务 → 添加集成 → 搜索「虚拟门禁系统」"
    echo "   - Host 填 HA 主机实际 IP，Port 填 8099"
    echo ""
    echo "4. 添加 Dashboard 卡片"
    echo "   - 进入 Lovelace 编辑模式 → 添加卡片"
    echo "   - 搜索「云海湾门禁卡片」"
    echo ""
    echo "详细图文教程请访问："
    echo "  https://github.com/CelerPi/HA-UpperCoast-Doorlock#readme"
    echo ""

    # 询问是否立即重启
    read -rp "是否立即重启 Home Assistant？(y/N): " restart
    if [[ "$restart" =~ ^[Yy]$ ]]; then
        info "正在重启 Home Assistant ..."
        if command -v ha &> /dev/null; then
            ha core restart
        elif command -v hassio &> /dev/null; then
            hassio homeassistant restart
        else
            warn "无法自动重启，请手动在 UI 中操作"
        fi
    fi
}

main "$@"
