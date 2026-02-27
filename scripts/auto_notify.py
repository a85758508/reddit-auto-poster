#!/usr/bin/env python3
"""
scripts/auto_notify.py
macOS 桌面通知（通过 osascript）
"""

import subprocess


def notify(title, message, sound="default"):
    """发送 macOS 桌面通知"""
    # 转义引号
    message = message.replace('"', '\\"').replace("'", "\\'")
    title = title.replace('"', '\\"').replace("'", "\\'")

    script = f'display notification "{message}" with title "{title}"'
    if sound:
        script += f' sound name "{sound}"'

    try:
        subprocess.run(["osascript", "-e", script], check=False,
                       capture_output=True, timeout=10)
    except Exception:
        pass  # 通知失败不影响主流程


def notify_success(posts_count, subreddits):
    """发帖成功通知"""
    subs = ", ".join(subreddits)
    notify(
        "Reddit Assistant",
        f"已发布 {posts_count} 篇帖子到 {subs}"
    )


def notify_failure(error_msg):
    """发帖失败通知"""
    notify(
        "Reddit Assistant - 错误",
        f"自动发帖失败: {error_msg[:100]}",
        sound="Basso"
    )


def notify_partial(succeeded, failed, subreddits):
    """部分成功通知"""
    subs = ", ".join(subreddits)
    notify(
        "Reddit Assistant",
        f"发布 {succeeded}/{succeeded+failed} 篇成功 → {subs}"
    )


if __name__ == "__main__":
    notify_success(3, ["r/SideProject", "r/Entrepreneur", "r/GenX"])
    print("✅ 测试通知已发送")
