#!/bin/bash
# scripts/check_env.sh — 检查运行环境（无需 PRAW/凭证）

echo "=== Reddit Assistant 环境检查 ==="
echo ""

# Python
if command -v python3 &>/dev/null; then
  echo "✅ Python3: $(python3 --version)"
else
  echo "❌ Python3 未安装"
  exit 1
fi

# memory 目录
if [ -d "memory" ]; then
  echo "✅ memory/ 目录存在"
else
  echo "⚠️  memory/ 不存在，初始化中..."
  bash scripts/init_memory.sh
fi

# 产品配置
if [ -f "memory/config.json" ]; then
  PRODUCT=$(python3 -c "import json; c=json.load(open('memory/config.json')); print(c.get('name','未设置'))" 2>/dev/null)
  echo "✅ 产品配置: $PRODUCT"
else
  echo "⚠️  产品配置不存在 → 运行: reddit-assistant setup"
fi

# 帖子记录数
if [ -f "memory/posted-log.json" ]; then
  COUNT=$(python3 -c "import json; print(len(json.load(open('memory/posted-log.json'))))" 2>/dev/null || echo "0")
  echo "✅ 已记录帖子: $COUNT 篇"
fi

echo ""
echo "✅ 环境检查完成（无需 Reddit API 凭证）"
