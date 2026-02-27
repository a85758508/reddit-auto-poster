#!/usr/bin/env python3
"""
scripts/init_config.py
创建或更新产品配置 memory/config.json
"""
import argparse
import json
import os
from datetime import datetime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="产品名称")
    parser.add_argument("--description", required=True, help="一句话描述")
    parser.add_argument("--target_user", required=True, help="目标用户")
    parser.add_argument("--stage", choices=["idea", "beta", "launched", "growing"], default="launched")
    parser.add_argument("--github_url", default="")
    parser.add_argument("--website_url", default="")
    args = parser.parse_args()

    os.makedirs("memory", exist_ok=True)

    config = {
        "name": args.name,
        "description": args.description,
        "target_user": args.target_user,
        "stage": args.stage,
        "github_url": args.github_url,
        "website_url": args.website_url,
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "updated_at": datetime.now().strftime("%Y-%m-%d")
    }

    config_file = "memory/config.json"
    if os.path.exists(config_file):
        with open(config_file) as f:
            existing = json.load(f)
        existing.update(config)
        existing["created_at"] = existing.get("created_at", config["created_at"])
        config = existing

    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"✅ 产品配置已保存: {args.name}")
    print(f"   描述: {args.description}")
    print(f"   目标用户: {args.target_user}")
    print(f"   阶段: {args.stage}")


if __name__ == "__main__":
    main()
