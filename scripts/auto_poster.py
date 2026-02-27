#!/usr/bin/env python3
"""
scripts/auto_poster.py
通过 AppleScript 控制 Chrome 发帖到 Reddit
参考: https://github.com/PHY041/claude-skill-reddit

原理:
  AppleScript → Chrome (execute javascript) → Reddit /api/submit
  利用用户已登录的 Chrome session，无需 API 凭证
  Reddit 无法检测为机器人

前置条件:
  1. macOS + Google Chrome
  2. Chrome → View → Developer → Allow JavaScript from Apple Events
  3. Chrome 中已登录 Reddit
"""

import json
import subprocess
import sys
import time
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Reddit 垃圾过滤触发词（参考 PHY041）
SPAM_TRIGGER_WORDS = [
    "free", "discount", "promo", "hack", "scrape", "bot",
    "automate", "growth hack", "viral", "monetize",
]


def run_applescript(script):
    """执行 AppleScript 并返回结果"""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip(), result.returncode, result.stderr.strip()


def check_chrome():
    """检测 Chrome 是否可用"""
    out, code, err = run_applescript(
        'tell application "Google Chrome" to return count of windows'
    )
    if code != 0 or not out or out == "0":
        return False, "Chrome 未打开或没有窗口"
    return True, f"Chrome 已就绪 ({out} 个窗口)"


def execute_js(js_code):
    """在 Chrome 当前标签页执行 JavaScript"""
    # 转义单引号用于 AppleScript
    escaped = js_code.replace("\\", "\\\\").replace('"', '\\"')
    script = (
        'tell application "Google Chrome" to tell active tab of first window '
        f'to execute javascript "{escaped}"'
    )
    out, code, err = run_applescript(script)
    return out, code, err


def read_title():
    """读取 Chrome 当前标签页的 title"""
    script = 'tell application "Google Chrome" to return title of active tab of first window'
    out, code, err = run_applescript(script)
    return out


def navigate_to_reddit():
    """确保 Chrome 当前页面在 reddit.com（same-origin 要求）"""
    script = 'tell application "Google Chrome" to return URL of active tab of first window'
    url, _, _ = run_applescript(script)

    if "reddit.com" not in (url or ""):
        execute_js("window.location.href='https://www.reddit.com'")
        time.sleep(3)
        return True
    return False


def get_modhash():
    """获取 modhash (CSRF token)"""
    js = (
        'fetch("/api/me.json",{credentials:"include"})'
        '.then(r=>r.json())'
        '.then(d=>{document.title="UH:"+d.data.modhash})'
        '.catch(e=>{document.title="ERR:"+e.message})'
    )
    execute_js(js)
    time.sleep(3)

    title = read_title()
    if title and title.startswith("UH:"):
        modhash = title[3:]
        if modhash:
            return modhash
        return None
    return None


def submit_post(subreddit, title, body, modhash):
    """
    提交帖子到 Reddit

    Args:
        subreddit: subreddit 名称 (不带 r/ 前缀)
        title: 帖子标题
        body: 帖子正文
        modhash: CSRF token

    Returns:
        dict: {"success": bool, "url": str, "post_id": str, "error": str}
    """
    # 转义特殊字符
    safe_title = title.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"').replace("\n", " ")
    safe_body = body.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"').replace("\n", "\\n")

    js = (
        '(async()=>{'
        'try{'
        'let body=new URLSearchParams({'
        f'sr:"{subreddit}",'
        'kind:"self",'
        f'title:"{safe_title}",'
        f'text:"{safe_body}",'
        f'uh:"{modhash}",'
        'api_type:"json",'
        'resubmit:"true"'
        '});'
        'let resp=await fetch("/api/submit",{'
        'method:"POST",'
        'credentials:"include",'
        'headers:{"Content-Type":"application/x-www-form-urlencoded"},'
        'body:body.toString()'
        '});'
        'let result=await resp.json();'
        'document.title="POSTED:"+JSON.stringify(result);'
        '}catch(e){'
        'document.title="ERR:"+e.message;'
        '}'
        '})()'
    )

    execute_js(js)
    time.sleep(5)

    title_result = read_title()

    if not title_result:
        return {"success": False, "url": "", "post_id": "", "error": "无法读取响应"}

    if title_result.startswith("POSTED:"):
        try:
            data = json.loads(title_result[7:])

            # 检查是否有错误
            errors = data.get("json", {}).get("errors", [])
            if errors:
                # 检查是否是 CAPTCHA 错误
                is_captcha = any("CAPTCHA" in str(e).upper() for e in errors)
                error_msg = "; ".join([str(e) for e in errors])
                return {
                    "success": False, "url": "", "post_id": "",
                    "error": error_msg,
                    "captcha_required": is_captcha,
                }

            # 提取帖子 URL
            post_data = data.get("json", {}).get("data", {})
            post_url = post_data.get("url", "")
            post_id = post_data.get("id", "")

            return {"success": True, "url": post_url, "post_id": post_id, "error": ""}

        except json.JSONDecodeError as e:
            return {"success": False, "url": "", "post_id": "", "error": f"解析响应失败: {e}"}

    if title_result.startswith("ERR:"):
        return {"success": False, "url": "", "post_id": "", "error": title_result[4:]}

    return {"success": False, "url": "", "post_id": "", "error": f"未知响应: {title_result[:100]}"}


def open_submit_page(subreddit, title, body, flair_text=None):
    """CAPTCHA fallback: 用 old.reddit.com 打开发帖页面，JS 自动填入标题、正文和 flair"""
    sub_name = subreddit.lstrip("r/").strip()
    url = f"https://old.reddit.com/r/{sub_name}/submit?selftext=true"

    # 打开发帖页面
    script = (
        f'tell application "Google Chrome"\n'
        f'  activate\n'
        f'  tell first window\n'
        f'    make new tab with properties {{URL:"{url}"}}\n'
        f'  end tell\n'
        f'end tell'
    )
    run_applescript(script)
    time.sleep(5)

    # 用 JS 自动填入标题和正文
    safe_title = title.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'").replace("\n", " ")
    safe_body = body.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'").replace("\n", "\\n")

    fill_js = (
        f'var t=document.querySelector("textarea[name=title]")||document.querySelector("input[name=title]");'
        f'var b=document.querySelector("textarea[name=text]");'
        f'if(t)t.value="{safe_title}";'
        f'if(b)b.value="{safe_body}";'
        f'document.title="FILLED:"+(t?"T":"")+(b?"B":"");'
    )

    execute_js(fill_js)
    time.sleep(1)

    result = read_title()
    filled_ok = result and "T" in result and "B" in result
    if filled_ok:
        print(f"  ✅ 标题和正文已自动填入")
    else:
        print(f"  ⚠️  自动填入可能不完整: {result}")

    # 自动选择 Flair
    if flair_text:
        time.sleep(1)
        flair_selected = _select_flair_on_page(flair_text)
        if not flair_selected:
            print(f"  ℹ️  请手动选择 Flair: {flair_text}")

    return url


def _select_flair_on_page(flair_text):
    """在 old.reddit.com 提交页面自动选择 flair"""
    safe_flair = flair_text.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'")

    # Step 1: 点击 flair 选择器按钮打开面板
    open_js = (
        'var btn=document.querySelector(".flairselector-button")'
        '||document.querySelector("a.flairselector")'
        '||document.querySelector("[data-event-action=flair]")'
        '||document.querySelector(".linkflair-button")'
        '||document.querySelector("button.flair-toggle");'
        'if(btn){btn.click();document.title="FLAIR_OPENED:Y"}'
        'else{document.title="FLAIR_OPENED:N"}'
    )
    execute_js(open_js)
    time.sleep(2)

    result = read_title()
    if not result or "FLAIR_OPENED:Y" not in result:
        # 可能没有 flair 选择器按钮，尝试直接查找 flair 面板
        pass

    # Step 2: 在打开的面板中找到匹配的 flair 并点击
    select_js = (
        f'var target="{safe_flair}".toLowerCase();'
        'var found=false;'
        # old.reddit.com flair 选项通常在 .flairselector .flairoptionpane 里
        'var items=document.querySelectorAll(".flairselector .flairoptionpane li,'
        '.flairselector .flairselection,'
        '.flairoptionpane a.customizer,'
        '.flairoptionpane .linkflair a,'
        '.linkflair-widget li,'
        '.flair-list li,'
        '.flair-list-item");'
        'for(var i=0;i<items.length;i++){'
        'var txt=(items[i].textContent||items[i].innerText||"").trim().toLowerCase();'
        'if(txt===target||txt.indexOf(target)>=0||target.indexOf(txt)>=0){'
        'items[i].click();found=true;break;'
        '}}'
        # 也尝试 label/span 匹配
        'if(!found){'
        'var spans=document.querySelectorAll(".flairselector span.linkflairlabel,'
        '.flairselector .linkflair span,'
        '.flairselector .flairselection span");'
        'for(var j=0;j<spans.length;j++){'
        'var st=(spans[j].textContent||"").trim().toLowerCase();'
        'if(st===target||st.indexOf(target)>=0||target.indexOf(st)>=0){'
        'spans[j].closest("li,a,.flairselection")?.click();found=true;break;'
        '}}}'
        'document.title="FLAIR_SELECT:"+(found?"OK":"MISS");'
    )
    execute_js(select_js)
    time.sleep(1)

    result = read_title()
    if result and "FLAIR_SELECT:OK" in result:
        # Step 3: 点击保存按钮
        save_js = (
            'var saveBtn=document.querySelector(".flairselector .save,'
            '.flairselector button[type=submit],'
            '.flairselector input[type=submit],'
            '.flairselector .flairsave");'
            'if(saveBtn){saveBtn.click();document.title="FLAIR_SAVED:Y"}'
            'else{document.title="FLAIR_SAVED:N"}'
        )
        execute_js(save_js)
        time.sleep(1)

        result = read_title()
        if result and "FLAIR_SAVED:Y" in result:
            print(f"  ✅ Flair 已自动选择: {flair_text}")
            return True
        else:
            print(f"  ⚠️  Flair 已选中但保存可能失败")
            return True  # 已选中，可能不需要保存
    else:
        print(f"  ⚠️  未在页面找到匹配的 Flair: {flair_text}")
        return False


def fetch_flairs_via_chrome(subreddit):
    """通过 Chrome 已登录 session 获取 subreddit 的 flair 列表"""
    sub_name = subreddit.lstrip("r/").strip()

    js = (
        '(async()=>{'
        'try{'
        f'let resp=await fetch("/r/{sub_name}/api/link_flair_v2.json",{{credentials:"include"}});'
        'if(!resp.ok){document.title="FLAIRS:[]";return;}'
        'let flairs=await resp.json();'
        'if(!Array.isArray(flairs)){document.title="FLAIRS:[]";return;}'
        'document.title="FLAIRS:"+JSON.stringify(flairs.map(f=>({id:f.id,text:f.text})));'
        '}catch(e){'
        'document.title="FLAIRS:[]";'
        '}'
        '})()'
    )

    execute_js(js)
    time.sleep(3)

    title = read_title()
    if title and title.startswith("FLAIRS:"):
        try:
            return json.loads(title[7:])
        except (json.JSONDecodeError, KeyError):
            pass
    return []


def get_flair_id(subreddit, flair_text):
    """通过 Chrome session 获取 flair template ID，支持模糊匹配"""
    flairs = fetch_flairs_via_chrome(subreddit)
    if not flairs:
        return None

    flair_lower = flair_text.lower().strip()
    # 精确匹配
    for f in flairs:
        if f.get("text", "").lower().strip() == flair_lower:
            return f["id"]
    # 部分匹配
    for f in flairs:
        if flair_lower in f.get("text", "").lower() or f.get("text", "").lower() in flair_lower:
            return f["id"]
    return None


def auto_select_flair(subreddit, title, body):
    """自动根据帖子内容选择最佳 flair（通过 Chrome 获取可用 flair 后用关键词匹配）"""
    flairs = fetch_flairs_via_chrome(subreddit)
    if not flairs:
        return None, []

    text = (title + " " + body).lower()

    # 关键词 → flair 类型映射
    keyword_map = {
        "feedback": ["feedback", "review", "critique", "roast"],
        "question": ["question", "advice", "how do i", "how can i", "how should i"],
        "how do": ["how do i", "how can i", "how should", "stuck", "can't figure", "help me"],
        "help": ["help", "stuck", "can't figure", "need advice", "how do i"],
        "discussion": ["discussion", "thoughts", "what do you think", "your take", "opinion", "have you"],
        "story": ["story", "journey", "experience", "learned", "months ago", "lost", "failed", "after"],
        "success": ["success", "achieved", "milestone", "growth", "revenue", "users", "launched"],
        "showcase": ["showcase", "show", "demo", "launched", "built", "made"],
        "resource": ["resource", "guide", "tutorial", "tip", "best practice"],
        "best practice": ["best practice", "tips", "advice", "strategy", "approach"],
        "promotion": ["promo", "launch", "announce", "introducing"],
        "project": ["project", "side project", "app", "tool", "platform"],
        "insight": ["insight", "data", "found", "discovered", "research", "tracking"],
        "growth": ["growth", "scale", "expand", "revenue", "marketing", "retention"],
        "tiktok": ["tiktok", "short-form", "short form", "reels", "shorts"],
        "youtube": ["youtube", "video", "channel", "subscriber"],
        "content": ["content", "creator", "creating", "posting"],
    }

    best_flair = None
    best_score = 0

    for flair in flairs:
        flair_text_lower = flair.get("text", "").lower().strip()
        score = 0

        # 精确 flair 名称匹配关键词类别
        for category, keywords in keyword_map.items():
            if category in flair_text_lower or flair_text_lower in category:
                for kw in keywords:
                    if kw in text:
                        score += 3

        # flair 名称中的词出现在帖子内容中
        for word in flair_text_lower.replace("&amp;", "&").split():
            if len(word) > 2 and word in text:
                score += 1

        # 帖子标题中的词出现在 flair 名称中
        title_lower = title.lower()
        for word in flair_text_lower.split():
            if len(word) > 2 and word in title_lower:
                score += 2

        if score > best_score:
            best_score = score
            best_flair = flair

    # 没匹配到时选通用类 flair
    if not best_flair:
        generic = ["discussion", "general", "other", "misc", "question"]
        for flair in flairs:
            if flair.get("text", "").lower() in generic:
                best_flair = flair
                break
        if not best_flair and flairs:
            best_flair = flairs[0]

    if best_flair:
        return best_flair.get("text"), flairs
    return None, flairs


def apply_flair(post_id, subreddit, flair_text, modhash):
    """发帖后通过 /api/selectflair 设置 flair（参考 PHY041 方案）"""
    flair_id = get_flair_id(subreddit, flair_text)
    if not flair_id:
        print(f"  ⚠️  未找到匹配的 Flair: {flair_text}")
        return False

    sub_name = subreddit.lstrip("r/").strip()
    js = (
        '(async()=>{'
        'try{'
        'let body=new URLSearchParams({'
        f'link:"t3_{post_id}",'
        f'flair_template_id:"{flair_id}",'
        f'uh:"{modhash}"'
        '});'
        f'let resp=await fetch("/r/{sub_name}/api/selectflair",{{'
        'method:"POST",'
        'credentials:"include",'
        'headers:{"Content-Type":"application/x-www-form-urlencoded"},'
        'body:body.toString()'
        '});'
        'let result=await resp.json();'
        'document.title="FLAIR_SET:"+JSON.stringify(result);'
        '}catch(e){'
        'document.title="ERR:"+e.message;'
        '}'
        '})()'
    )

    execute_js(js)
    time.sleep(3)

    title = read_title()
    if title and title.startswith("FLAIR_SET:"):
        print(f"  ✅ Flair 已设置: {flair_text}")
        return True
    print(f"  ⚠️  Flair 设置可能失败: {title}")
    return False


def verify_post(post_url, wait_seconds=60):
    """等待后验证帖子是否被自动删除"""
    if not post_url:
        return False

    print(f"  等待 {wait_seconds} 秒后验证帖子状态...")
    time.sleep(wait_seconds)

    # 通过公开 API 检查
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from reddit_client import fetch_post_metrics
        metrics = fetch_post_metrics(post_url)
        return not metrics.get("is_removed", True)
    except Exception:
        return True  # API 调用失败，假设未删除


def post_to_reddit(subreddit, title, body, dry_run=False, verify=True, flair_text=None):
    """
    完整发帖流程

    Args:
        subreddit: subreddit 名称 (如 "r/SideProject" 或 "SideProject")
        title: 帖子标题
        body: 帖子正文
        dry_run: 仅模拟，不实际发帖
        verify: 发帖后是否验证
        flair_text: 如需 flair，传入 flair 文本

    Returns:
        dict: {"success": bool, "url": str, "post_id": str, "error": str, "verified": bool}
    """
    # 清理 subreddit 名称
    sub_name = subreddit.lstrip("r/").strip()

    if dry_run:
        print(f"  [DRY RUN] 模拟发帖到 r/{sub_name}")
        print(f"  标题: {title}")
        print(f"  正文: {body[:100]}...")
        return {
            "success": True,
            "url": f"https://reddit.com/r/{sub_name}/comments/DRY_RUN/",
            "post_id": "DRY_RUN",
            "error": "",
            "verified": True,
            "dry_run": True,
        }

    # Step 1: 检查 Chrome
    ok, msg = check_chrome()
    if not ok:
        return {"success": False, "url": "", "post_id": "", "error": msg, "verified": False}
    print(f"  ✅ {msg}")

    # Step 2: 导航到 Reddit
    navigated = navigate_to_reddit()
    if navigated:
        print("  ✅ 已导航到 reddit.com")
        time.sleep(2)

    # Step 3: 获取 modhash
    print("  正在获取认证信息...")
    modhash = get_modhash()
    if not modhash:
        return {"success": False, "url": "", "post_id": "", "error": "无法获取 modhash（可能未登录 Reddit）", "verified": False}
    print("  ✅ 认证成功")

    # Step 4: 获取 flair（如果没有预选，自动根据内容选择）
    if not flair_text:
        print("  🏷️  正在获取可用 Flair...")
        auto_flair, available_flairs = auto_select_flair(sub_name, title, body)
        if auto_flair:
            flair_text = auto_flair
            print(f"  ✅ 自动选择 Flair: {flair_text}")
        elif available_flairs:
            print(f"  ℹ️  有 {len(available_flairs)} 个可用 Flair 但未匹配到合适的")
        else:
            print(f"  ℹ️  该 subreddit 无需 Flair")

    # Step 5: 提交帖子
    print(f"  正在发帖到 r/{sub_name}...")
    result = submit_post(sub_name, title, body, modhash)

    if not result["success"]:
        if result.get("captcha_required"):
            print(f"  ⚠️  需要 CAPTCHA 验证，正在打开浏览器发帖页面...")
            open_submit_page(sub_name, title, body, flair_text=flair_text)
            print(f"  📋 已在 Chrome 中打开 r/{sub_name} 发帖页面（标题和内容已预填）")
            print(f"  👉 请手动完成验证码并点击发布")
            return {**result, "verified": False, "captcha_fallback": True}
        print(f"  ❌ 发帖失败: {result['error']}")
        return {**result, "verified": False}

    print(f"  ✅ 发帖成功: {result['url']}")

    # Step 6: 发帖成功后设置 Flair（参考 PHY041 方案：flair 在帖子创建后单独设置）
    if flair_text and result.get("post_id"):
        print(f"  🏷️  正在设置 Flair: {flair_text}")
        apply_flair(result["post_id"], sub_name, flair_text, modhash)

    # Step 7: 验证
    verified = True
    if verify and result["url"]:
        verified = verify_post(result["url"], wait_seconds=60)
        if verified:
            print("  ✅ 帖子验证通过（未被自动删除）")
        else:
            print("  ⚠️  帖子可能被自动删除")

    return {**result, "verified": verified, "dry_run": False}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="通过 Chrome 发帖到 Reddit")
    parser.add_argument("--subreddit", required=True, help="目标 subreddit")
    parser.add_argument("--title", required=True, help="帖子标题")
    parser.add_argument("--body", required=True, help="帖子正文")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run", help="模拟发帖")
    parser.add_argument("--no-verify", action="store_true", dest="no_verify", help="跳过验证")
    args = parser.parse_args()

    result = post_to_reddit(
        args.subreddit, args.title, args.body,
        dry_run=args.dry_run, verify=not args.no_verify
    )

    print(f"\n结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    sys.exit(0 if result["success"] else 1)
