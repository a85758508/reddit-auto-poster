#!/usr/bin/env python3
"""
scripts/auto_orchestrator.py
每日自动发帖编排器 — 主入口

流程:
  1. 加载配置 + 历史
  2. auto_scheduler 选择 3 个目标
  3. 循环: 生成内容 → 保存草稿 → 发帖 → 记录日志
  4. 写入每日报告 + 发送通知

用法:
  python3 scripts/auto_orchestrator.py                  # 正常运行
  python3 scripts/auto_orchestrator.py --dry-run        # 只生成不发帖
  python3 scripts/auto_orchestrator.py --count 1        # 只发 1 篇
  python3 scripts/auto_orchestrator.py --no-wait        # 不等待间隔（测试用）
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))

from auto_scheduler import select_daily_targets, load_json
from auto_content_gen import generate_post, get_api_key
from auto_poster import post_to_reddit
from auto_notify import notify_success, notify_failure, notify_partial

LOCK_FILE = os.path.join(BASE_DIR, "memory", "automation", ".lock")
DAILY_LOG_DIR = os.path.join(BASE_DIR, "memory", "automation")
POSTED_LOG = os.path.join(BASE_DIR, "memory", "posted-log.json")

DEFAULT_CONFIG = {
    "posts_per_day": 3,
    "min_days_between_same_subreddit": 4,
    "min_hours_between_posts": 2.5,
    "content_model": "claude-sonnet-4-20250514",
    "dry_run": False,
    "enable_notifications": True,
    "posting_start_hour_local": 8,
}


def acquire_lock():
    """获取锁（防止并发运行）"""
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE) as f:
                pid = int(f.read().strip())
            # 检查进程是否还在运行
            os.kill(pid, 0)
            return False  # 进程仍在运行
        except (ValueError, ProcessLookupError, PermissionError):
            pass  # 旧锁，可以覆盖

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    return True


def release_lock():
    """释放锁"""
    try:
        os.remove(LOCK_FILE)
    except FileNotFoundError:
        pass


def load_posted_log():
    """加载发帖日志"""
    if os.path.exists(POSTED_LOG):
        try:
            with open(POSTED_LOG) as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_posted_log(log):
    """保存发帖日志"""
    with open(POSTED_LOG, "w") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def count_posts_today(log):
    """计算今天已发帖数"""
    today = datetime.now().strftime("%Y-%m-%d")
    return sum(1 for p in log if p.get("posted_at", "").startswith(today))


def save_draft(subreddit, angle, title, body):
    """保存草稿到 memory/drafts/"""
    import subprocess
    result = subprocess.run([
        sys.executable, os.path.join(BASE_DIR, "scripts", "save_draft.py"),
        "--subreddit", subreddit,
        "--angle", angle,
        "--title", title,
        "--body", body,
    ], capture_output=True, text=True)
    return result.returncode == 0


def log_post_entry(post_id, url, subreddit, title, angle, draft_file=""):
    """添加到 posted-log.json"""
    log = load_posted_log()
    now = datetime.now(timezone.utc).isoformat()

    entry = {
        "post_id": post_id,
        "url": url,
        "subreddit": subreddit if subreddit.startswith("r/") else f"r/{subreddit}",
        "title": title,
        "angle": angle,
        "draft_file": draft_file,
        "posted_at": now,
        "score": None,
        "upvote_ratio": None,
        "num_comments": None,
        "last_checked": None,
        "status": "active",
        "auto_posted": True,
    }

    log.append(entry)
    save_posted_log(log)
    return entry


def save_daily_log(date_str, results):
    """保存每日运行日志"""
    os.makedirs(DAILY_LOG_DIR, exist_ok=True)

    succeeded = sum(1 for r in results if r.get("status") == "success")
    failed = sum(1 for r in results if r.get("status") == "failed")

    daily_log = {
        "date": date_str,
        "started_at": results[0].get("started_at", "") if results else "",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "posts": results,
        "summary": {
            "attempted": len(results),
            "succeeded": succeeded,
            "failed": failed,
        }
    }

    filepath = os.path.join(DAILY_LOG_DIR, f"daily-log-{date_str}.json")
    with open(filepath, "w") as f:
        json.dump(daily_log, f, indent=2, ensure_ascii=False)

    # 也保存为 latest
    latest = os.path.join(DAILY_LOG_DIR, "latest-run.json")
    with open(latest, "w") as f:
        json.dump(daily_log, f, indent=2, ensure_ascii=False)

    return filepath


def run_daily(dry_run=False, count=None, no_wait=False):
    """每日发帖主流程"""

    print("\n" + "=" * 60)
    print("🚀 Reddit Assistant — 自动发帖")
    print("=" * 60)

    # 加载配置
    config = load_json("memory/config.json")
    if not config:
        print("❌ 未找到产品配置")
        return False

    auto_config = load_json("memory/automation-config.json") or DEFAULT_CONFIG.copy()
    for key, val in DEFAULT_CONFIG.items():
        auto_config.setdefault(key, val)

    if dry_run:
        auto_config["dry_run"] = True
        print("🔸 DRY RUN 模式 — 只生成不发帖\n")

    # 检查 API key
    if not get_api_key():
        print("❌ 未找到 Anthropic API Key")
        print("   export ANTHROPIC_API_KEY=your-key")
        notify_failure("缺少 Anthropic API Key")
        return False

    # 加载数据
    profiles = load_json("memory/subreddit-profiles.json", [])
    log = load_posted_log()

    if not profiles:
        print("❌ 没有 subreddit 档案")
        return False

    # 检查今天已发帖数
    already_posted = count_posts_today(log)
    max_posts = count or auto_config["posts_per_day"]
    remaining = max_posts - already_posted

    if remaining <= 0:
        print(f"✅ 今天已发 {already_posted} 篇，达到上限")
        return True

    print(f"📋 今天目标: {remaining} 篇 (已发 {already_posted} 篇)")

    # 选择目标
    targets = select_daily_targets(profiles, log, config=auto_config)
    if not targets:
        print("❌ 所有 subreddit 都在冷却期内")
        return False

    targets = targets[:remaining]
    print(f"🎯 选定目标: {', '.join(t['subreddit'] for t in targets)}\n")

    # 执行发帖
    results = []
    succeeded_subs = []
    wait_hours = auto_config["min_hours_between_posts"]
    model = auto_config.get("content_model")

    for i, target in enumerate(targets):
        sub = target["subreddit"]
        angle = target["angle"]
        angle_names = {"A": "Story/Journey", "B": "Feedback Request", "C": "Value/Insight"}

        print(f"\n{'─' * 50}")
        print(f"[{i+1}/{len(targets)}] {sub} — 角度 {angle} ({angle_names.get(angle, '?')})")
        print(f"{'─' * 50}")

        result = {
            "slot": i + 1,
            "subreddit": sub,
            "angle": angle,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        # Step 1: 生成内容
        print("\n  📝 正在生成内容...")
        try:
            # 重新加载 log 以包含本次运行中已发的帖子
            current_log = load_posted_log()
            post_content = generate_post(
                target["profile"], config, current_log, angle, model=model
            )
        except Exception as e:
            print(f"  ❌ 内容生成失败: {e}")
            result.update({"status": "failed", "error": str(e)})
            results.append(result)
            continue

        if not post_content:
            print("  ❌ 内容生成返回空")
            result.update({"status": "failed", "error": "生成返回空"})
            results.append(result)
            continue

        title = post_content["title"]
        body = post_content["body"]
        print(f"  ✅ 内容生成成功")
        print(f"  📌 标题: {title}")

        # Step 2: 保存草稿
        save_draft(sub, angle, title, body)

        # Step 3: 发帖
        print("\n  🚀 正在发帖...")
        try:
            post_result = post_to_reddit(
                sub, title, body,
                dry_run=auto_config.get("dry_run", False),
                verify=not auto_config.get("dry_run", False)
            )
        except Exception as e:
            print(f"  ❌ 发帖失败: {e}")
            result.update({"status": "failed", "error": str(e), "title": title})
            results.append(result)
            continue

        if post_result["success"]:
            print(f"  ✅ 发帖成功: {post_result.get('url', 'DRY_RUN')}")

            # Step 4: 记录日志
            if not post_result.get("dry_run"):
                log_post_entry(
                    post_id=post_result["post_id"],
                    url=post_result["url"],
                    subreddit=sub,
                    title=title,
                    angle=angle,
                )

            result.update({
                "status": "success",
                "title": title,
                "post_id": post_result.get("post_id", ""),
                "url": post_result.get("url", ""),
                "verified": post_result.get("verified", True),
                "attempts": post_content.get("attempts", 1),
            })
            succeeded_subs.append(sub)
        else:
            print(f"  ❌ 发帖失败: {post_result.get('error', '未知错误')}")
            result.update({
                "status": "failed",
                "title": title,
                "error": post_result.get("error", ""),
            })

        results.append(result)

        # 等待间隔
        if i < len(targets) - 1 and not no_wait:
            wait_seconds = int(wait_hours * 3600)
            print(f"\n  ⏳ 等待 {wait_hours} 小时后发下一篇...")
            time.sleep(wait_seconds)

    # 总结
    print(f"\n{'=' * 60}")
    succeeded = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    print(f"📊 完成: {succeeded} 成功 / {failed} 失败")

    for r in results:
        icon = "✅" if r["status"] == "success" else "❌"
        print(f"  {icon} {r['subreddit']} — {r.get('title', '?')[:50]}")
        if r["status"] == "success" and r.get("url"):
            print(f"     {r['url']}")

    # 保存每日日志
    today_str = datetime.now().strftime("%Y-%m-%d")
    log_path = save_daily_log(today_str, results)
    print(f"\n📁 日志: {log_path}")

    # 发送通知
    if auto_config.get("enable_notifications", True):
        if failed == 0 and succeeded > 0:
            notify_success(succeeded, succeeded_subs)
        elif succeeded > 0:
            notify_partial(succeeded, failed, succeeded_subs)
        elif failed > 0:
            notify_failure(f"{failed} 篇全部失败")

    print("=" * 60 + "\n")
    return failed == 0


def main():
    os.chdir(BASE_DIR)

    parser = argparse.ArgumentParser(description="Reddit 每日自动发帖编排器")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                        help="只生成内容不实际发帖")
    parser.add_argument("--count", type=int, default=None,
                        help="发帖数量 (默认: 配置文件中的 posts_per_day)")
    parser.add_argument("--no-wait", action="store_true", dest="no_wait",
                        help="不等待帖子间隔 (测试用)")
    args = parser.parse_args()

    # 获取锁
    if not acquire_lock():
        print("⚠️  另一个实例正在运行，退出")
        sys.exit(0)

    try:
        success = run_daily(
            dry_run=args.dry_run,
            count=args.count,
            no_wait=args.no_wait,
        )
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 未处理的异常: {e}")
        notify_failure(str(e)[:100])
        sys.exit(1)
    finally:
        release_lock()


if __name__ == "__main__":
    main()
