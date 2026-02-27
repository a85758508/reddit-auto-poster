#!/bin/bash
# setup.sh — Reddit Assistant v2 安装脚本

set -e

echo "🚀 Reddit Assistant v2 安装中..."
echo ""

# 检查 Python
if ! command -v python3 &>/dev/null; then
  echo "❌ 需要 Python 3.8+"
  exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✅ Python $PYTHON_VERSION"

# 安装 PRAW
echo "📦 安装 PRAW..."
pip3 install praw --quiet
echo "✅ PRAW 安装完成"

# 初始化 memory 目录
bash scripts/init_memory.sh

# 安装到 Claude Code
SKILL_DIR="$HOME/.claude/skills/reddit-assistant"
mkdir -p "$SKILL_DIR"
cp SKILL.md "$SKILL_DIR/"
cp -r scripts "$SKILL_DIR/"
cp -r references "$SKILL_DIR/"
echo "✅ Skill 已安装到 $SKILL_DIR"

echo ""
echo "=== 安装完成！==="
echo ""
echo "📋 接下来："
echo "  1. 配置产品信息："
echo "     python3 scripts/init_config.py --name '产品名' --description '一句话描述' --target_user '目标用户' --stage launched"
echo ""
echo "  2. 配置 Reddit API 凭证（用于发帖后追踪数据）："
echo "     python3 scripts/setup_credentials.py"
echo "     （获取凭证：https://www.reddit.com/prefs/apps）"
echo ""
echo "  3. 在 Claude Code 中使用："
echo "     claude '帮我写一篇 Reddit 帖子，我的产品是...'"
echo "     claude '找适合我产品的 subreddit'"
echo "     claude '查看我的 Reddit 发帖效果'"
echo ""
echo "  4. 发帖后记录 URL："
echo "     python3 scripts/log_post.py --url <帖子URL> --angle A"
