#!/usr/bin/env zsh
# =============================================================
# AI Companion 一键启动脚本 (macOS 可双击执行)
#
# 双击执行:  弹出交互菜单选择启动模式
# 命令行用法:
#   ./start.command                  交互菜单
#   ./start.command --dev            后端 + 前端 (浏览器开发模式)
#   ./start.command --electron       前端 + Electron (Electron 自行管理后端)
#   ./start.command --all            后端 + 前端 + Electron (完整模式)
#   ./start.command --backend-only   只启动后端
#   ./start.command --frontend-only  只启动前端
# =============================================================

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT" || exit 1
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
ELECTRON_DIR="$PROJECT_ROOT/electron"

# ── 颜色 ──────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${CYAN}[STEP]${NC} $1"; }

# ── 子进程清理 ────────────────────────────────────────────────────────
cleanup() {
    echo ""
    log_warn "正在关闭所有服务..."
    [[ -n "$ELECTRON_PID" ]] && kill "$ELECTRON_PID" 2>/dev/null && log_info "已停止 Electron"
    [[ -n "$VITE_PID" ]] && kill "$VITE_PID" 2>/dev/null && log_info "已停止 前端 (Vite)"
    [[ -n "$UVICORN_PID" ]] && kill "$UVICORN_PID" 2>/dev/null && log_info "已停止 后端 (Uvicorn)"
    lsof -ti tcp:18080 -sTCP:LISTEN 2>/dev/null | xargs kill 2>/dev/null || true
    lsof -ti tcp:9753 -sTCP:LISTEN 2>/dev/null | xargs kill 2>/dev/null || true
    log_info "所有服务已关闭"
}
trap cleanup SIGINT SIGTERM

# ── 检测依赖 ──────────────────────────────────────────────────────────
check_deps() {
    local has_error=0

    # 后端：检测 uv 虚拟环境
    if [[ ! -d "$BACKEND_DIR/.venv" ]]; then
        log_warn "后端虚拟环境不存在，尝试初始化..."
        (cd "$BACKEND_DIR" && uv venv && uv sync) || {
            log_error "后端虚拟环境初始化失败，请手动运行: cd backend && uv venv && uv sync"
            has_error=1
        }
    fi

    # 前端：检测 node_modules
    if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
        log_warn "前端依赖未安装，正在安装..."
        (cd "$FRONTEND_DIR" && npm install) || {
            log_error "前端依赖安装失败，请手动运行: cd frontend && npm install"
            has_error=1
        }
    fi

    # Electron：检测 node_modules
    if [[ ! -d "$ELECTRON_DIR/node_modules" ]]; then
        log_warn "Electron 依赖未安装，正在安装..."
        (cd "$ELECTRON_DIR" && npm install) || {
            log_error "Electron 依赖安装失败，请手动运行: cd electron && npm install"
            has_error=1
        }
    fi

    return $has_error
}

# ── 启动后端 ──────────────────────────────────────────────────────────
start_backend() {
    log_step "正在启动后端服务 (Uvicorn)..."
    cd "$PROJECT_ROOT"
    uv run --directory backend uvicorn app.main:app \
        --host 127.0.0.1 --port 18080 --reload &
    UVICORN_PID=$!
    log_info "后端服务启动中 (PID: $UVICORN_PID)..."

    # 等待后端就绪（最多等 15 秒）
    local wait_sec=0
    while [[ $wait_sec -lt 15 ]]; do
        if curl -sf http://127.0.0.1:18080/health >/dev/null 2>&1; then
            log_info "后端服务就绪 → http://127.0.0.1:18080"
            log_info "API 文档  → http://127.0.0.1:18080/docs"
            return 0
        fi
        sleep 1
        ((wait_sec++))
    done
    log_error "后端服务启动超时，请检查日志"
    return 1
}

# ── 启动前端 ──────────────────────────────────────────────────────────
start_frontend() {
    log_step "正在启动前端开发服务器 (Vite)..."
    cd "$FRONTEND_DIR"
    npm run dev &
    VITE_PID=$!
    log_info "前端开发服务器启动中 (PID: $VITE_PID)..."

    # 等待前端就绪（最多等 15 秒）
    local wait_sec=0
    while [[ $wait_sec -lt 15 ]]; do
        if curl -sf http://127.0.0.1:9753 >/dev/null 2>&1; then
            log_info "前端开发就绪 → http://127.0.0.1:9753"
            return 0
        fi
        sleep 1
        ((wait_sec++))
    done
    log_error "前端启动超时"
    return 1
}

# ── 启动 Electron ────────────────────────────────────────────────────
start_electron() {
    log_step "正在编译并启动 Electron..."

    # 完整编译：tsc 编译 TypeScript（preload 已内联 IPC_CHANNELS 消除本地 require）
    cd "$ELECTRON_DIR"
    npm run build || {
        log_error "Electron 编译失败"
        return 1
    }

    # 诊断：验证 preload.js 不包含沙盒不支持的本地模块引用
    echo -e "${CYAN}[DIAG]${NC} dist/preload.js 行数: $(wc -l < dist/preload.js)"
    echo -e "${CYAN}[DIAG]${NC} require 列表: $(grep -o 'require("[^"]*")' dist/preload.js | tr '\n' ' ')"
    echo -e "${CYAN}[DIAG]${NC} 更新时间: $(date -r dist/preload.js '+%H:%M:%S')"
    if grep -q 'require.*constants.*channels' dist/preload.js; then
        log_error "preload.js 编译后仍包含 require('./constants/channels')，内联失败"
        log_error "文件内容前5行:"
        head -5 dist/preload.js
        return 1
    fi

    # 以开发模式启动 Electron
    NODE_ENV=development npx electron . &
    ELECTRON_PID=$!
    log_info "Electron 已启动 (PID: $ELECTRON_PID)"
}

# ── 驻留等待 ──────────────────────────────────────────────────────────
# 保持终端存活 + 检测后台进程状态
keep_alive() {
    local label="${1:-服务}"
    echo ""
    log_info "$label 正在运行中，按 Ctrl+C 停止"
    while true; do
        # 检查关键进程是否存活
        local alive=0
        [[ -n "$UVICORN_PID" ]] && kill -0 "$UVICORN_PID" 2>/dev/null && ((alive++))
        [[ -n "$VITE_PID" ]] && kill -0 "$VITE_PID" 2>/dev/null && ((alive++))
        [[ -n "$ELECTRON_PID" ]] && kill -0 "$ELECTRON_PID" 2>/dev/null && ((alive++))
        if [[ $alive -eq 0 ]]; then
            echo ""
            log_warn "所有服务已退出，自动关闭"
            cleanup
            exit 0
        fi
        # 回收已结束的子进程，防止僵尸
        wait -n 2>/dev/null || true
        sleep 1
    done
}

# ── 打印帮助 ──────────────────────────────────────────────────────────
print_usage() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  (无参数)      交互菜单选择启动模式"
    echo "  --dev         启动后端 + 前端 (浏览器访问)"
    echo "  --electron    启动前端 + Electron (Electron 自行管理后端)"
    echo "  --all         启动后端 + 前端 + Electron (完整模式)"
    echo "  --backend-only   只启动后端"
    echo "  --frontend-only  只启动前端"
    echo "  --help        显示此帮助"
    echo ""
    echo "访问地址:"
    echo "  后端 API:  http://127.0.0.1:18080"
    echo "  API 文档:  http://127.0.0.1:18080/docs"
    echo "  前端页面:  http://127.0.0.1:9753"
    exit 0
}

# ── 交互式模式选择（双击/无参数时） ───────────────────────────────────
choose_mode() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  AI Companion 启动模式${NC}"
    echo -e "${CYAN}  ─────────────────────────────${NC}"
    echo -e "  ${GREEN}1${NC}) 浏览器开发模式  (后端 + 前端)  [默认]"
    echo -e "  ${GREEN}2${NC}) 桌面模式        (前端 + Electron)"
    echo -e "  ${GREEN}3${NC}) 完整模式        (后端 + 前端 + Electron)"
    echo -e "  ${GREEN}4${NC}) 仅后端"
    echo -e "  ${GREEN}5${NC}) 仅前端"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    local choice
    read "choice?请输入序号并回车 [1]: "
    case "$choice" in
        2) MODE="--electron" ;;
        3) MODE="--all" ;;
        4) MODE="--backend-only" ;;
        5) MODE="--frontend-only" ;;
        *) MODE="--dev" ;;
    esac
}

# ── 主流程 ─────────────────────────────────────────────────────────────
MODE="${1:-}"
[[ -z "$MODE" ]] && choose_mode

case "$MODE" in
    --help|-h)
        print_usage
        ;;
    --backend-only|-b)
        check_deps
        start_backend
        keep_alive "后端"
        ;;
    --frontend-only|-f)
        check_deps
        start_frontend
        keep_alive "前端"
        ;;
    --electron|-e)
        check_deps
        start_frontend
        log_info "等待前端就绪后启动 Electron..."
        sleep 3
        start_electron
        keep_alive "前端 + Electron"
        ;;
    --all|-a)
        check_deps
        start_backend
        start_frontend
        log_info "等待服务就绪后启动 Electron..."
        sleep 3
        start_electron
        keep_alive "全部"
        ;;
    --dev|dev)
        # 后端 + 前端 (浏览器开发模式)
        check_deps
        start_backend
        start_frontend
        echo ""
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${CYAN}  AI Companion 开发环境${NC}"
        echo -e "${CYAN}  ─────────────────────────────${NC}"
        echo -e "  前端页面:  ${GREEN}http://127.0.0.1:9753${NC}"
        echo -e "  后端 API:  ${GREEN}http://127.0.0.1:18080${NC}"
        echo -e "  API 文档:  ${GREEN}http://127.0.0.1:18080/docs${NC}"
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        keep_alive "开发模式"
        ;;
    *)
        echo -e "${RED}未知选项: $MODE${NC}"
        print_usage
        ;;
esac
