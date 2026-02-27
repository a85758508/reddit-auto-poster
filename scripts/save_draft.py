#!/usr/bin/env python3
"""
scripts/save_draft.py
保存帖子草稿到 memory/drafts/
"""

import argparse
import json
import os
import sys
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(description="保存 Reddit 帖子草稿")
    parser.add_argument("--subreddit", required=True, help="目标 subreddit，如 r/SideProject")
    parser.add_argument("--angle", required=True, choices=["A", "B", "C"], help="帖子角度")
    parser.add_argument("--title", required=True, help="帖子标题")
    parser.add_argument("--body", required=True, help="帖子正文")
    parser.add_argument("--notes", default="", help="备注")
    args = parser.parse_args()

    os.makedirs("memory/drafts", exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    sub_name = args.subreddit.lstrip("r/").lower().replace("/", "-")
    filename = f"memory/drafts/{today}-{sub_name}.md"

    # 如果文件已存在，加序号
    counter = 1
    base_filename = filename
    while os.path.exists(filename):
        filename = base_filename.replace(".md", f"-{counter}.md")
        counter += 1

    angle_names = {"A": "Story/Journey", "B": "Feedback Request", "C": "Value/Insight"}

    content = f"""# Draft: {args.subreddit}

**Date:** {today}
**Status:** draft
**Angle:** {args.angle} — {angle_names[args.angle]}

---

## Title

{args.title}

---

## Body

{args.body}

---

## Notes

{args.notes if args.notes else "（无备注）"}

---

## Post Checklist

- [ ] 标题未使用促销词汇
- [ ] 以价值/故事开头，产品在后
- [ ] 透明披露了自己是开发者
- [ ] 结尾有具体的问题
- [ ] 内容适配该社区的语气
- [ ] 已手动发布到 Reddit
- [ ] 已用 `python3 scripts/log_post.py` 记录 URL
"""

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ 草稿已保存: {filename}")
    print(f"\n发布后请运行：")
    print(f"python3 scripts/log_post.py --url <Reddit帖子URL> --angle {args.angle} --draft_file {filename}")


if __name__ == "__main__":
    main()
