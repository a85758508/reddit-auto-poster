#!/usr/bin/env python3
"""
scripts/update_subreddit_profile.py
保存/更新 subreddit 研究档案到 memory/subreddit-profiles.json
"""
import argparse
import json
import os
from datetime import datetime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--subreddit", required=True)
    parser.add_argument("--subscribers", type=int, default=0)
    parser.add_argument("--activity", choices=["high", "medium", "low"], default="medium")
    parser.add_argument("--promo_rules", default="")
    parser.add_argument("--best_angle", choices=["A", "B", "C", "mixed"], default="mixed")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    profile_file = "memory/subreddit-profiles.json"
    profiles = []
    if os.path.exists(profile_file):
        with open(profile_file) as f:
            profiles = json.load(f)

    # 更新或新增
    sub_name = args.subreddit if args.subreddit.startswith("r/") else f"r/{args.subreddit}"
    existing = next((p for p in profiles if p["subreddit"] == sub_name), None)

    entry = {
        "subreddit": sub_name,
        "subscribers": args.subscribers,
        "activity": args.activity,
        "promo_rules": args.promo_rules,
        "best_angle": args.best_angle,
        "notes": args.notes,
        "last_checked": datetime.now().strftime("%Y-%m-%d")
    }

    if existing:
        existing.update(entry)
        print(f"✅ 更新 {sub_name} 的档案")
    else:
        profiles.append(entry)
        print(f"✅ 新增 {sub_name} 的档案")

    with open(profile_file, 'w') as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
