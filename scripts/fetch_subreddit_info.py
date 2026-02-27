#!/usr/bin/env python3
"""获取 subreddit 信息 + 最近帖子风格分析"""

import argparse, json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from reddit_client import fetch_subreddit_info, fetch_subreddit_posts

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--subreddit", required=True)
    parser.add_argument("--posts", type=int, default=5, help="同时获取最近几篇帖子")
    args = parser.parse_args()

    try:
        info = fetch_subreddit_info(args.subreddit)
        print(json.dumps(info, indent=2, ensure_ascii=False))

        if args.posts > 0:
            print("\n--- 最近热门帖子（供参考社区风格）---")
            posts = fetch_subreddit_posts(args.subreddit, sort="hot", limit=args.posts)
            for i, p in enumerate(posts, 1):
                print(f"{i}. [{p['score']}↑] {p['title'][:80]}")
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
