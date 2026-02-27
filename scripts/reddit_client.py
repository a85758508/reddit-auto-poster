"""
scripts/reddit_client.py
Reddit 公开 JSON 接口封装（无需任何认证）
Reddit 的所有公开内容都可以通过在 URL 后加 .json 访问
"""

import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

HEADERS = {"User-Agent": "reddit-assistant/2.0 (personal use)"}


def _get(url: str, retries: int = 2) -> dict:
    """通用 GET，自动重试，处理速率限制"""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = int(e.headers.get("Retry-After", 60))
                if attempt < retries:
                    time.sleep(wait)
                    continue
                raise Exception(f"Reddit 速率限制，请 {wait} 秒后重试")
            elif e.code == 404:
                raise Exception(f"内容不存在（已删除或 URL 错误）: {url}")
            elif e.code == 403:
                raise Exception("访问被拒绝（可能是私密社区或已删除内容）")
            raise Exception(f"HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(3)
                continue
            raise Exception(f"网络连接失败: {e.reason}")
    raise Exception("请求失败，已达最大重试次数")


def fetch_post_metrics(post_url: str) -> dict:
    """
    获取帖子数据（无需认证）
    支持格式:
      https://reddit.com/r/SideProject/comments/abc123/title/
      https://www.reddit.com/r/SideProject/comments/abc123/
    """
    clean = post_url.rstrip("/").split("?")[0]
    if not clean.endswith(".json"):
        clean += ".json"

    data = _get(clean)
    p = data[0]["data"]["children"][0]["data"]

    return {
        "score":        p.get("score", 0),
        "upvote_ratio": p.get("upvote_ratio", 0),
        "num_comments": p.get("num_comments", 0),
        "title":        p.get("title", ""),
        "subreddit":    p.get("subreddit_name_prefixed", ""),
        "author":       p.get("author", ""),
        "created_utc":  p.get("created_utc", 0),
        "url":          "https://reddit.com" + p.get("permalink", ""),
        "is_removed":   p.get("removed_by_category") is not None,
    }


def fetch_subreddit_info(subreddit_name: str) -> dict:
    """获取 subreddit 基本信息（无需认证）"""
    name = subreddit_name.lstrip("r/").strip()
    data = _get(f"https://www.reddit.com/r/{name}/about.json")
    d = data["data"]

    return {
        "name":         f"r/{d.get('display_name', name)}",
        "subscribers":  d.get("subscribers", 0),
        "active_users": d.get("active_user_count", 0),
        "description":  d.get("public_description", "")[:300],
        "over18":       d.get("over18", False),
        "allow_text":   d.get("submission_type", "any") in ("any", "self"),
        "allow_link":   d.get("submission_type", "any") in ("any", "link"),
    }


def fetch_subreddit_posts(subreddit_name: str, sort: str = "hot", limit: int = 10) -> list:
    """
    获取 subreddit 帖子列表（用于研究社区风格）
    sort: hot / new / top / rising
    """
    name = subreddit_name.lstrip("r/").strip()
    data = _get(f"https://www.reddit.com/r/{name}/{sort}.json?limit={limit}")

    posts = []
    for child in data["data"]["children"]:
        p = child["data"]
        posts.append({
            "title":        p.get("title", ""),
            "score":        p.get("score", 0),
            "num_comments": p.get("num_comments", 0),
            "upvote_ratio": p.get("upvote_ratio", 0),
            "is_self":      p.get("is_self", True),
            "flair":        p.get("link_flair_text", ""),
            "url":          "https://reddit.com" + p.get("permalink", ""),
            "created_utc":  p.get("created_utc", 0),
        })
    return posts


# backward compatibility alias
fetch_post_metrics_public = fetch_post_metrics


def extract_post_id_from_url(url: str) -> tuple:
    """从 Reddit URL 提取 (subreddit, post_id)"""
    parts = url.rstrip("/").split("/")
    try:
        idx = parts.index("comments")
        return parts[idx - 1], parts[idx + 1]
    except (ValueError, IndexError):
        raise ValueError(f"无法解析 Reddit URL: {url}")
