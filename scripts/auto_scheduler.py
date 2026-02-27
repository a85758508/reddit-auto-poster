#!/usr/bin/env python3
"""
scripts/auto_scheduler.py
智能 Subreddit 轮换算法
选择每天发帖的 3 个目标 subreddit + 角度
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 默认配置
DEFAULT_MIN_DAYS_BETWEEN = 4
DEFAULT_POSTS_PER_DAY = 3
ANGLES = ["A", "B", "C"]

# 打分权重
W_RECENCY = 0.5
W_PERFORMANCE = 0.3
W_REACH = 0.2


def load_json(path, default=None):
    full = os.path.join(BASE_DIR, path) if not os.path.isabs(path) else path
    if os.path.exists(full):
        try:
            with open(full) as f:
                return json.load(f)
        except Exception:
            return default
    return default


def get_posting_history(subreddit, log):
    """获取某个 subreddit 的发帖历史"""
    posts = [p for p in log if p.get("subreddit", "").lower() == subreddit.lower()
             and p.get("status") != "deleted"]
    posts.sort(key=lambda p: p.get("posted_at", ""), reverse=True)
    return posts


def days_since_last_post(subreddit, log, today):
    """计算距离上次发帖的天数"""
    history = get_posting_history(subreddit, log)
    if not history:
        return 999  # 从未发过，最高优先级

    last_date_str = history[0].get("posted_at", "")
    try:
        if "T" in last_date_str:
            last_date = datetime.fromisoformat(last_date_str.replace("Z", "+00:00")).date()
        else:
            last_date = datetime.strptime(last_date_str[:10], "%Y-%m-%d").date()
        return (today - last_date).days
    except (ValueError, TypeError):
        return 999


def avg_score(subreddit, log):
    """计算某个 subreddit 的平均得分"""
    posts = get_posting_history(subreddit, log)
    scores = [p["score"] for p in posts if p.get("score") is not None]
    return sum(scores) / len(scores) if scores else 0


def last_angle_used(subreddit, log):
    """获取上次在该 subreddit 使用的角度"""
    history = get_posting_history(subreddit, log)
    if history:
        return history[0].get("angle", "A")
    return None


def next_angle(last_angle):
    """轮换到下一个角度"""
    if last_angle is None:
        return "A"
    idx = ANGLES.index(last_angle) if last_angle in ANGLES else 0
    return ANGLES[(idx + 1) % len(ANGLES)]


def normalize_subscribers(profiles):
    """将订阅人数归一化到 0-1"""
    subs = [p.get("subscribers", 0) for p in profiles]
    max_sub = max(subs) if subs else 1
    return {p["subreddit"]: p.get("subscribers", 0) / max_sub for p in profiles}


def select_daily_targets(profiles, log, today=None, config=None):
    """
    选择今天的 3 个目标 subreddit + 角度

    返回: [{"subreddit": str, "angle": str, "profile": dict}, ...]
    """
    if today is None:
        today = datetime.now().date()

    config = config or {}
    min_days = config.get("min_days_between_same_subreddit", DEFAULT_MIN_DAYS_BETWEEN)
    posts_per_day = config.get("posts_per_day", DEFAULT_POSTS_PER_DAY)

    # 检查今天已发帖数
    today_str = today.isoformat()
    today_posts = [p for p in log if p.get("posted_at", "").startswith(today_str)]
    remaining = posts_per_day - len(today_posts)
    if remaining <= 0:
        return []

    # 归一化订阅人数
    sub_norm = normalize_subscribers(profiles)

    # 计算每个 subreddit 的得分
    candidates = []
    for profile in profiles:
        sub = profile["subreddit"]
        days = days_since_last_post(sub, log, today)

        # 过滤冷却期内的 subreddit
        if days < min_days:
            continue

        score_avg = avg_score(sub, log)
        reach = sub_norm.get(sub, 0)

        # 加权得分
        total_score = (
            days * W_RECENCY +
            score_avg * W_PERFORMANCE +
            reach * W_REACH * 100  # 归一化到合理范围
        )

        candidates.append({
            "subreddit": sub,
            "profile": profile,
            "score": total_score,
            "days_since": days,
            "avg_score": score_avg,
        })

    # 按得分排序
    candidates.sort(key=lambda c: c["score"], reverse=True)

    # 选择前 N 个，分配角度（确保多样性）
    selected = []
    used_angles = set()

    for candidate in candidates:
        if len(selected) >= remaining:
            break

        sub = candidate["subreddit"]
        profile = candidate["profile"]

        # 决定角度
        last = last_angle_used(sub, log)
        angle = next_angle(last)

        # 如果这个角度今天已经用过，尝试其他
        if angle in used_angles and len(used_angles) < 3:
            for alt in ANGLES:
                if alt not in used_angles and alt != last:
                    angle = alt
                    break

        # 也可以使用 profile 的 best_angle（如果没有历史）
        if last is None:
            angle = profile.get("best_angle", angle)

        used_angles.add(angle)

        selected.append({
            "subreddit": sub,
            "angle": angle,
            "profile": profile,
            "debug": {
                "score": round(candidate["score"], 2),
                "days_since": candidate["days_since"],
                "avg_score": round(candidate["avg_score"], 2),
            }
        })

    return selected


def preview():
    """预览今天的选择"""
    profiles = load_json("memory/subreddit-profiles.json", [])
    log = load_json("memory/posted-log.json", [])
    config = load_json("memory/automation-config.json", {})
    today = datetime.now().date()

    if not profiles:
        print("❌ 没有 subreddit 档案，请先运行研究流程")
        return

    targets = select_daily_targets(profiles, log, today, config)

    angle_names = {"A": "Story/Journey", "B": "Feedback Request", "C": "Value/Insight"}

    print(f"\n📋 今日发帖计划 ({today.isoformat()})")
    print("─" * 60)

    if not targets:
        print("  所有 subreddit 都在冷却期内，今天暂不发帖")
        return

    for i, t in enumerate(targets, 1):
        debug = t["debug"]
        print(f"\n  [{i}] {t['subreddit']}")
        print(f"      角度: {t['angle']} ({angle_names.get(t['angle'], '?')})")
        print(f"      得分: {debug['score']} | 距上次: {debug['days_since']}天 | 历史均分: {debug['avg_score']}")
        print(f"      备注: {t['profile'].get('notes', '')[:60]}...")

    # 显示冷却中的 subreddit
    print(f"\n  ❄️  冷却中的社区:")
    min_days = config.get("min_days_between_same_subreddit", DEFAULT_MIN_DAYS_BETWEEN)
    for p in profiles:
        days = days_since_last_post(p["subreddit"], log, today)
        if days < min_days:
            print(f"      {p['subreddit']} — 还需 {min_days - days} 天")


if __name__ == "__main__":
    os.chdir(BASE_DIR)

    parser = argparse.ArgumentParser(description="Subreddit 轮换算法")
    parser.add_argument("--preview", action="store_true", help="预览今天的发帖计划")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    if args.json:
        profiles = load_json("memory/subreddit-profiles.json", [])
        log = load_json("memory/posted-log.json", [])
        config = load_json("memory/automation-config.json", {})
        targets = select_daily_targets(profiles, log, config=config)
        # 移除不可序列化的 profile 对象
        output = [{"subreddit": t["subreddit"], "angle": t["angle"]} for t in targets]
        print(json.dumps(output, indent=2))
    else:
        preview()
