#!/bin/bash
# scripts/init_memory.sh — 初始化 memory 目录结构

mkdir -p memory/drafts memory/performance

# 初始化空的 posted-log.json
if [ ! -f "memory/posted-log.json" ]; then
  echo "[]" > memory/posted-log.json
  echo "✅ 创建 memory/posted-log.json"
fi

# 初始化空的 subreddit-profiles.json
if [ ! -f "memory/subreddit-profiles.json" ]; then
  echo "[]" > memory/subreddit-profiles.json
  echo "✅ 创建 memory/subreddit-profiles.json"
fi

echo "✅ memory/ 目录初始化完成"
