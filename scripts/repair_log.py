#!/usr/bin/env python3
"""
scripts/repair_log.py
修复损坏的 posted-log.json
- 备份原始文件
- 尝试解析并修复 JSON
- 验证每条记录的必要字段
- 重建干净的日志文件
"""

import json
import os
import shutil
import sys
from datetime import datetime, timezone

LOG_FILE = "memory/posted-log.json"
REQUIRED_FIELDS = {"post_id", "url", "subreddit", "angle", "posted_at"}


def backup_file(path: str) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = f"{path}.backup-{ts}"
    shutil.copy2(path, backup_path)
    return backup_path


def validate_entry(entry: dict, idx: int) -> tuple[bool, list[str]]:
    """验证单条记录，返回 (is_valid, list_of_issues)"""
    issues = []
    for field in REQUIRED_FIELDS:
        if field not in entry or not entry[field]:
            issues.append(f"缺少字段: {field}")

    url = entry.get("url", "")
    if url and "reddit.com" not in url:
        issues.append(f"URL 格式可疑: {url[:60]}")

    angle = entry.get("angle")
    if angle and angle not in ("A", "B", "C"):
        issues.append(f"angle 值无效: {angle}（应为 A/B/C）")

    return len(issues) == 0, issues


def repair_entry(entry: dict) -> dict:
    """尽量修复单条记录，填充缺失字段的默认值"""
    now = datetime.now(timezone.utc).isoformat()

    # 尝试从 URL 中提取 post_id 和 subreddit
    url = entry.get("url", "")
    if url and "comments" in url:
        parts = url.rstrip("/").split("/")
        try:
            comments_idx = parts.index("comments")
            if not entry.get("post_id"):
                entry["post_id"] = parts[comments_idx + 1]
            if not entry.get("subreddit"):
                sub = parts[comments_idx - 1]
                entry["subreddit"] = f"r/{sub}" if not sub.startswith("r/") else sub
        except (ValueError, IndexError):
            pass

    # 填充必要默认值
    entry.setdefault("post_id", f"unknown-{hash(url) % 100000}")
    entry.setdefault("subreddit", "r/unknown")
    entry.setdefault("angle", "A")
    entry.setdefault("posted_at", now)
    entry.setdefault("title", "")
    entry.setdefault("score", None)
    entry.setdefault("upvote_ratio", None)
    entry.setdefault("num_comments", None)
    entry.setdefault("last_checked", None)
    entry.setdefault("status", "active")
    entry.setdefault("draft_file", "")

    return entry


def main():
    print("=== posted-log.json 修复工具 ===\n")

    if not os.path.exists(LOG_FILE):
        print(f"❌ {LOG_FILE} 不存在")
        print("将创建空日志文件...")
        os.makedirs("memory", exist_ok=True)
        with open(LOG_FILE, 'w') as f:
            json.dump([], f)
        print(f"✅ 已创建空 {LOG_FILE}")
        return

    # 备份原始文件
    backup_path = backup_file(LOG_FILE)
    print(f"✅ 已备份原始文件: {backup_path}\n")

    # 尝试解析 JSON
    raw_content = open(LOG_FILE, encoding='utf-8').read().strip()
    log = None

    try:
        log = json.loads(raw_content)
        print(f"✅ JSON 解析成功，共 {len(log)} 条记录")
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON 解析失败: {e}")
        print("尝试修复 JSON 结构...")

        # 尝试修复常见问题：末尾逗号、截断
        fixed = raw_content
        if not fixed.endswith("]"):
            # 截断的数组：找最后一个完整的 }
            last_brace = fixed.rfind("}")
            if last_brace > 0:
                fixed = fixed[:last_brace + 1] + "]"
                try:
                    log = json.loads(fixed)
                    print(f"✅ 修复成功（截断修复），恢复 {len(log)} 条记录")
                except json.JSONDecodeError:
                    pass

        if log is None:
            print("❌ 无法自动修复 JSON，创建空日志")
            log = []

    # 验证和修复每条记录
    print(f"\n验证 {len(log)} 条记录...")
    valid_entries = []
    repaired_count = 0
    dropped_count = 0

    for i, entry in enumerate(log):
        if not isinstance(entry, dict):
            print(f"  跳过第 {i+1} 条：不是有效对象")
            dropped_count += 1
            continue

        is_valid, issues = validate_entry(entry, i)

        if is_valid:
            valid_entries.append(entry)
        else:
            print(f"  第 {i+1} 条有问题：{', '.join(issues)}")
            repaired = repair_entry(entry.copy())
            re_valid, remaining = validate_entry(repaired, i)
            if re_valid:
                valid_entries.append(repaired)
                repaired_count += 1
                print(f"    → 已修复")
            else:
                print(f"    → 无法修复（{', '.join(remaining)}），跳过")
                dropped_count += 1

    # 去重（按 post_id）
    seen_ids = set()
    deduped = []
    for entry in valid_entries:
        pid = entry.get("post_id")
        if pid not in seen_ids:
            seen_ids.add(pid)
            deduped.append(entry)
        else:
            print(f"  移除重复记录: {pid}")

    # 保存修复后的文件
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(deduped, f, indent=2, ensure_ascii=False)

    print(f"\n=== 修复完成 ===")
    print(f"  原始记录: {len(log)}")
    print(f"  修复记录: {repaired_count}")
    print(f"  跳过记录: {dropped_count}")
    print(f"  最终记录: {len(deduped)}")
    print(f"\n✅ 已保存到 {LOG_FILE}")
    print(f"   备份位置: {backup_path}")


if __name__ == "__main__":
    main()
