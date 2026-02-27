#!/usr/bin/env python3
"""
scripts/log_post.py
记录已发布的 Reddit 帖子 URL 到 posted-log.json
在手动发布到 Reddit 后运行此脚本
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

# 把 scripts/ 目录加入路径以复用 reddit_client
sys.path.insert(0, os.path.dirname(__file__))
from reddit_client import fetch_post_metrics_public, extract_post_id_from_url


def load_log():
    if os.path.exists("memory/posted-log.json"):
        with open("memory/posted-log.json") as f:
            return json.load(f)
    return []


def save_log(log):
    os.makedirs("memory", exist_ok=True)
    with open("memory/posted-log.json", 'w') as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="记录已发布的 Reddit 帖子")
    parser.add_argument("--url", required=True, help="Reddit 帖子 URL")
    parser.add_argument("--angle", required=True, choices=["A", "B", "C"], help="帖子角度")
    parser.add_argument("--draft_file", default="", help="对应草稿文件路径（可选）")
    args = parser.parse_args()

    # 解析 URL
    try:
        subreddit, post_id = extract_post_id_from_url(args.url)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    # 检查是否已记录
    log = load_log()
    existing_ids = [p.get("post_id") for p in log]
    if post_id in existing_ids:
        print(f"⚠️  帖子 {post_id} 已在记录中")
        sys.exit(0)

    # 尝试获取初始数据
    print(f"正在获取帖子数据：{args.url}")
    metrics = {}
    try:
        metrics = fetch_post_metrics_public(args.url)
        print(f"✅ 获取成功：Score={metrics['score']}, Comments={metrics['num_comments']}")
        title = metrics.get("title", "")
    except Exception as e:
        print(f"⚠️  获取帖子数据失败（将稍后重试）: {e}")
        title = ""

    # 构建记录
    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "post_id": post_id,
        "url": args.url,
        "subreddit": f"r/{subreddit}",
        "title": title or metrics.get("title", ""),
        "angle": args.angle,
        "draft_file": args.draft_file,
        "posted_at": now,
        "score": metrics.get("score"),
        "upvote_ratio": metrics.get("upvote_ratio"),
        "num_comments": metrics.get("num_comments"),
        "last_checked": now if metrics else None,
        "status": "active"
    }

    log.append(entry)
    save_log(log)

    print(f"\n✅ 已记录帖子：r/{subreddit}/comments/{post_id}/")
    print(f"   标题: {entry['title'] or '（未获取，将在下次分析时更新）'}")
    print(f"\n提示：运行 python3 scripts/fetch_performance.py 来更新所有帖子的最新数据")


if __name__ == "__main__":
    main()
