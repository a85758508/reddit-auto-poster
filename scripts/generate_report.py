#!/usr/bin/env python3
"""
scripts/generate_report.py
根据 posted-log.json 生成月度分析报告
带洞察和推荐
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone


def load_log():
    if not os.path.exists("memory/posted-log.json"):
        print("❌ 没有发帖记录，请先使用 log_post.py 记录帖子")
        sys.exit(1)
    with open("memory/posted-log.json") as f:
        return json.load(f)


def filter_by_month(log: list, month: str) -> list:
    """筛选指定月份的帖子，month 格式: YYYY-MM。None 表示全部"""
    if not month:
        return [e for e in log if e.get("score") is not None]
    result = []
    for e in log:
        posted = e.get("posted_at", "")
        if posted.startswith(month) and e.get("score") is not None:
            result.append(e)
    return result


def generate_insights(posts: list) -> list:
    """分析数据，生成洞察"""
    if not posts:
        return ["数据不足，无法生成洞察"]

    insights = []

    # 按 subreddit 分组
    by_sub = defaultdict(list)
    for p in posts:
        by_sub[p.get("subreddit", "unknown")].append(p)

    sub_avg = {
        sub: sum(p["score"] for p in ps) / len(ps)
        for sub, ps in by_sub.items()
    }
    if sub_avg:
        best_sub = max(sub_avg, key=sub_avg.get)
        insights.append(
            f"**最佳社区**: {best_sub}（平均 Score {sub_avg[best_sub]:.1f}）"
            + (f"，共 {len(by_sub[best_sub])} 篇帖子" if len(by_sub[best_sub]) > 1 else "")
        )

    # 按角度分组
    by_angle = defaultdict(list)
    angle_names = {"A": "Story/Journey", "B": "Feedback Request", "C": "Value/Insight"}
    for p in posts:
        angle = p.get("angle", "unknown")
        by_angle[angle].append(p)

    angle_avg = {
        k: sum(p["score"] for p in v) / len(v)
        for k, v in by_angle.items() if v
    }
    if len(angle_avg) > 1:
        best_angle = max(angle_avg, key=angle_avg.get)
        worst_angle = min(angle_avg, key=angle_avg.get)
        ratio = angle_avg[best_angle] / max(angle_avg[worst_angle], 0.1)
        insights.append(
            f"**最佳角度**: {angle_names.get(best_angle, best_angle)}"
            f"（平均 Score {angle_avg[best_angle]:.1f}，"
            f"比{angle_names.get(worst_angle, worst_angle)}高 {ratio:.1f}x）"
        )

    # 最高分帖子
    top = max(posts, key=lambda p: p.get("score", 0))
    insights.append(
        f"**最高分帖子**: 「{top.get('title', '?')[:60]}」"
        f"（{top.get('score', 0)} 分，{top.get('num_comments', 0)} 评论，{top.get('subreddit', '?')}）"
    )

    # 平均参与度
    avg_score = sum(p["score"] for p in posts) / len(posts)
    avg_comments = sum(p.get("num_comments", 0) for p in posts) / len(posts)
    avg_upvote = sum(p.get("upvote_ratio", 0) for p in posts if p.get("upvote_ratio")) / len(posts)
    insights.append(
        f"**平均数据**: Score {avg_score:.1f} | 评论 {avg_comments:.1f} | 赞同率 {avg_upvote*100:.0f}%"
    )

    return insights


def generate_recommendations(posts: list) -> list:
    """基于数据生成具体建议"""
    if len(posts) < 2:
        return ["积累更多数据后将生成个性化建议（至少需要 2 篇已记录帖子）"]

    recs = []
    by_angle = defaultdict(list)
    angle_names = {"A": "Story/Journey", "B": "Feedback Request", "C": "Value/Insight"}

    for p in posts:
        by_angle[p.get("angle", "?")].append(p.get("score", 0))

    angle_avg = {k: sum(v)/len(v) for k, v in by_angle.items() if v}

    if len(angle_avg) >= 2:
        best = max(angle_avg, key=angle_avg.get)
        worst = min(angle_avg, key=angle_avg.get)
        if angle_avg[best] > angle_avg[worst] * 1.5:
            recs.append(
                f"你的 {angle_names.get(best, best)} 型帖子表现明显优于 "
                f"{angle_names.get(worst, worst)} 型，下次优先考虑前者"
            )

    # 评论多但分数低 → 内容引发讨论但没获得广泛认同
    high_comment = [p for p in posts if p.get("num_comments", 0) > 10 and p.get("score", 0) < 5]
    if high_comment:
        recs.append(
            f"有 {len(high_comment)} 篇帖子评论多但得分低——内容引发了讨论但标题可能需要更吸引人"
        )

    if not recs:
        recs.append("继续保持当前策略，数据还在积累中")

    return recs


def main():
    import argparse
    parser = argparse.ArgumentParser(description="生成 Reddit 发帖分析报告")
    parser.add_argument("--month", default="", help="月份，格式 YYYY-MM。留空=全部数据")
    args = parser.parse_args()

    log = load_log()
    posts = filter_by_month(log, args.month)

    period = args.month if args.month else "全部时间"
    print(f"分析 {period} 的数据，共 {len(posts)} 篇有效帖子\n")

    if not posts:
        print("没有该时间段的有效数据（需要先运行 fetch_performance.py 获取数据）")
        return

    # 排序
    posts_sorted = sorted(posts, key=lambda p: p.get("score", 0), reverse=True)

    # 生成报告内容
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# Reddit 发帖分析报告",
        f"",
        f"**分析周期**: {period}  ",
        f"**生成时间**: {now}  ",
        f"**帖子总数**: {len(posts)}",
        f"",
        f"---",
        f"",
        f"## 数据总览",
        f"",
        f"| 标题 | 社区 | Score | 评论 | 赞同率 | 角度 | 发布日期 |",
        f"|------|------|-------|------|--------|------|----------|",
    ]

    angle_names = {"A": "Story", "B": "Feedback", "C": "Insight"}
    for p in posts_sorted:
        title = (p.get("title") or "无标题")[:40]
        sub = p.get("subreddit", "?")
        score = p.get("score", "?")
        comments = p.get("num_comments", "?")
        upvote = f"{int((p.get('upvote_ratio') or 0) * 100)}%"
        angle = angle_names.get(p.get("angle", "?"), p.get("angle", "?"))
        date = (p.get("posted_at") or "")[:10]
        lines.append(f"| {title} | {sub} | {score} | {comments} | {upvote} | {angle} | {date} |")

    # 洞察
    insights = generate_insights(posts)
    lines += ["", "---", "", "## 关键洞察", ""]
    for i, insight in enumerate(insights, 1):
        lines.append(f"{i}. {insight}")

    # 建议
    recs = generate_recommendations(posts)
    lines += ["", "---", "", "## 行动建议", ""]
    for i, rec in enumerate(recs, 1):
        lines.append(f"{i}. {rec}")

    report = "\n".join(lines)

    # 保存
    os.makedirs("memory/performance", exist_ok=True)
    month_key = args.month or datetime.now().strftime("%Y-%m")
    report_file = f"memory/performance/{month_key}.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print(report)
    print(f"\n✅ 报告已保存: {report_file}")


if __name__ == "__main__":
    main()
