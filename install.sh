#!/bin/bash
# =====================================================
# Reddit Assistant — macOS 一键安装脚本（无需 API 凭证）
# 用法: bash install.sh
# =====================================================

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; RESET='\033[0m'

ok()   { echo -e "${GREEN}✅ $1${RESET}"; }
warn() { echo -e "${YELLOW}⚠️  $1${RESET}"; }
err()  { echo -e "${RED}❌ $1${RESET}"; exit 1; }
info() { echo -e "${BLUE}→  $1${RESET}"; }
step() { echo -e "\n${BOLD}[ $1 ]${RESET}"; }

SKILL_NAME="reddit-assistant"
INSTALL_DIR="$HOME/.claude/skills/$SKILL_NAME"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo -e "${BOLD}╔══════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║   Reddit Assistant — 安装程序        ║${RESET}"
echo -e "${BOLD}║   （无需 Reddit API 凭证）            ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════╝${RESET}"
echo ""

# Step 1: 检查系统
step "1/4 检查系统环境"
[[ "$(uname)" == "Darwin" ]] || err "此脚本仅支持 macOS"
ok "macOS $(sw_vers -productVersion)"

# Step 2: 检查 Python
step "2/4 检查 Python"
if command -v python3 &>/dev/null; then
  PYMAJ=$(python3 -c 'import sys; print(sys.version_info.major)')
  PYMIN=$(python3 -c 'import sys; print(sys.version_info.minor)')
  PYVER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  if [[ "$PYMAJ" -ge 3 && "$PYMIN" -ge 8 ]]; then
    ok "Python $PYVER"
  else
    err "需要 Python 3.8+，当前 $PYVER。请从 https://www.python.org 升级。"
  fi
else
  warn "未找到 Python3，尝试用 Homebrew 安装..."
  command -v brew &>/dev/null || err "请先安装 Homebrew: https://brew.sh"
  brew install python3
  ok "Python3 安装完成"
fi

# Step 3: 安装 Skill 文件
step "3/4 安装 Skill 到 Claude Code"

if [[ -d "$INSTALL_DIR" ]]; then
  BACKUP="$INSTALL_DIR.backup.$(date +%Y%m%d-%H%M%S)"
  mv "$INSTALL_DIR" "$BACKUP"
  warn "旧版本已备份至: $(basename $BACKUP)"
fi

mkdir -p "$INSTALL_DIR"
cp "$SCRIPT_DIR/SKILL.md"            "$INSTALL_DIR/"
cp "$SCRIPT_DIR/reddit-assistant.py" "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR/scripts"          "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR/references"       "$INSTALL_DIR/"

mkdir -p "$INSTALL_DIR/memory/drafts" "$INSTALL_DIR/memory/performance"
[[ -f "$INSTALL_DIR/memory/posted-log.json" ]]         || echo "[]" > "$INSTALL_DIR/memory/posted-log.json"
[[ -f "$INSTALL_DIR/memory/subreddit-profiles.json" ]]  || echo "[]" > "$INSTALL_DIR/memory/subreddit-profiles.json"

chmod +x "$INSTALL_DIR/scripts/"*.sh
chmod +x "$INSTALL_DIR/reddit-assistant.py"
ok "Skill 已安装到 $INSTALL_DIR"

# Step 4: 配置快捷命令
step "4/4 配置命令行快捷方式"

WRAPPER="/usr/local/bin/reddit-assistant"
ALIAS_CMD="alias reddit-assistant='cd $INSTALL_DIR && python3 reddit-assistant.py'"

if [[ -w "/usr/local/bin" ]]; then
  cat > "$WRAPPER" << WRAPPER_INNER
#!/bin/bash
cd "$INSTALL_DIR" && python3 reddit-assistant.py "\$@"
WRAPPER_INNER
  chmod +x "$WRAPPER"
  ok "全局命令 reddit-assistant 已配置"
else
  # 写入 zshrc（macOS 默认 shell）
  RC="$HOME/.zshrc"
  [[ -f "$RC" ]] || touch "$RC"
  if ! grep -q "reddit-assistant" "$RC" 2>/dev/null; then
    echo "" >> "$RC"
    echo "# Reddit Assistant" >> "$RC"
    echo "$ALIAS_CMD" >> "$RC"
    ok "已添加 alias 到 ~/.zshrc"
    warn "运行 source ~/.zshrc 或重启终端后生效"
  else
    ok "Alias 已存在于 ~/.zshrc"
  fi
fi

# 完成
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${GREEN}║   ✅  安装完成！                      ║${RESET}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════╝${RESET}"
echo ""
echo -e "${BOLD}立即开始：${RESET}"
echo ""
echo -e "  ${BLUE}reddit-assistant setup${RESET}     配置你的产品信息（第一步）"
echo -e "  ${BLUE}reddit-assistant draft${RESET}     写帖子草稿"
echo -e "  ${BLUE}reddit-assistant status${RESET}    查看状态"
echo ""
echo -e "  ${BOLD}或在 Claude Code 中直接说：${RESET}"
echo -e "  ${BLUE}「帮我写一篇 Reddit 帖子，我的产品是...」${RESET}"
echo ""
echo -e "  安装位置: $INSTALL_DIR"
echo ""
