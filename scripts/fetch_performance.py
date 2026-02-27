#!/usr/bin/env python3
"""
scripts/fetch_performance.py
从 Reddit 公开 API 批量更新所有已记录帖子的最新数据
无需认证，使用 Reddit 的公开 JSON 端点
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from reddit_client import fetch_post_metrics_public


def load_log():
    if not os.path.exists("memory/posted-log.json"):
        print("❌ memory/posted-log.json 不存在，请先用 log_post.py 记录帖子")
        sys.exit(1)
    with open("memory/posted-log.json") as f:
        return json.load(f)


def save_log(log):
    with open("memory/posted-log.json", 'w') as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def needs_update(entry: dict, force: bool = False) -> bool:
    """判断帖子是否需要更新数据"""
    if force:
        return True
    if entry.get("status") == "deleted":
        return False
    last_checked = entry.get("last_checked")
    if not last_checked:
        return True
    # 48 小时内更新过的跳过
    try:
        checked_at = datetime.fromisoformat(last_checked)
        if checked_at.tzinfo is None:
            checked_at = checked_at.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - checked_at
        return age > timedelta(hours=48)
    except Exception:
        return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="更新所有帖子的 Reddit 数据")
    parser.add_argument("--force", action="store_true", help="强制更新所有帖子，忽略缓存")
    args = parser.parse_args()

    log = load_log()
    if not log:
        print("没有已记录的帖子，请先用 log_post.py 记录帖子")
        return

    to_update = [e for e in log if needs_update(e, force=args.force)]
    print(f"共 {len(log)} 条记录，需要更新 {len(to_update)} 条\n")

    updated = 0
    failed = 0
    now = datetime.now(timezone.utc).isoformat()

    for entry in to_update:
        url = entry.get("url")
        sub = entry.get("subreddit", "?")
        title_preview = (entry.get("title") or "无标题")[:50]
        print(f"更新: {sub} — {title_preview}...")

        try:
            metrics = fetch_post_metrics_public(url)
            entry["score"] = metrics["score"]
            entry["upvote_ratio"] = metrics["upvote_ratio"]
            entry["num_comments"] = metrics["num_comments"]
            entry["last_checked"] = now
            if not entry.get("title") and metrics.get("title"):
                entry["title"] = metrics["title"]
            print(f"  ✅ Score: {metrics['score']} | Comments: {metrics['num_comments']} | Upvote%: {int(metrics['upvote_ratio']*100)}%")
            updated += 1
        except Exception as e:
            err = str(e)
            print(f"  ⚠️  失败: {err}")
            if "404" in err or "removed" in err.lower():
                entry["status"] = "deleted"
                print(f"  → 标记为已删除")
            failed += 1

        # 避免触发 Reddit 速率限制
        time.sleep(2)

    save_log(log)
    print(f"\n✅ 完成：更新 {updated} 条，失败 {failed} 条")
    print("运行 python3 scripts/generate_report.py 生成分析报告")


if __name__ == "__main__":
    main()
