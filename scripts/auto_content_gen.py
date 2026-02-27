#!/usr/bin/env python3
"""
scripts/auto_content_gen.py
使用 Anthropic Claude API 自动生成 Reddit 帖子内容
"""

import argparse
import json
import os
import sys
import glob as glob_mod
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 禁用词列表
BANNED_PHRASES = [
    "game-changing", "revolutionary", "excited to share", "thrilled to announce",
    "innovative", "disruptive", "passionate about", "leveraging", "seamless",
    "robust", "cutting-edge",
]

BAD_TITLE_STARTS = ["i built", "i made", "check out", "launching", "excited"]

# Reddit 垃圾过滤触发词（参考 PHY041）
SPAM_TRIGGER_WORDS = [
    "free", "discount", "promo code", "hack", "scrape", "bot",
    "automate posting", "growth hack", "viral trick", "monetize fast",
]


def load_json(path, default=None):
    full = os.path.join(BASE_DIR, path) if not os.path.isabs(path) else path
    if os.path.exists(full):
        try:
            with open(full) as f:
                return json.load(f)
        except Exception:
            return default
    return default


def get_api_key():
    """获取 Anthropic API key"""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key

    key_file = os.path.join(BASE_DIR, "memory", ".anthropic_key")
    if os.path.exists(key_file):
        with open(key_file) as f:
            return f.read().strip()

    return ""


def load_example_drafts(subreddit=None, angle=None, limit=3):
    """加载现有草稿作为 few-shot 示例"""
    drafts_dir = os.path.join(BASE_DIR, "memory", "drafts")
    if not os.path.exists(drafts_dir):
        return []

    examples = []
    files = sorted(glob_mod.glob(os.path.join(drafts_dir, "*.md")), reverse=True)

    for f in files[:limit * 2]:
        try:
            with open(f) as fh:
                content = fh.read()
            # 提取标题和正文
            title = ""
            body = ""
            in_body = False
            for line in content.split("\n"):
                if line.startswith("## Title"):
                    continue
                if line.startswith("## Body"):
                    in_body = True
                    continue
                if line.startswith("## Notes") or line.startswith("## Post Checklist"):
                    in_body = False
                    continue
                if line.startswith("---"):
                    continue
                if not title and not in_body and line.strip() and not line.startswith("#") and not line.startswith("**"):
                    title = line.strip()
                if in_body and line.strip():
                    body += line + "\n"

            if title and body:
                examples.append({"title": title, "body": body.strip()})
                if len(examples) >= limit:
                    break
        except Exception:
            continue

    return examples


def get_recent_titles(log, days=14):
    """获取近期帖子标题避免重复"""
    titles = []
    cutoff = datetime.now().isoformat()[:10]
    for p in log:
        if p.get("title"):
            titles.append(p["title"])
    return titles[-20:]  # 最多 20 个


def fetch_rules(subreddit):
    """获取 subreddit 发帖规则"""
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from reddit_client import fetch_subreddit_rules
        return fetch_subreddit_rules(subreddit)
    except Exception:
        return {"rules": [], "requirements": {}, "flair_required": False, "flair_options": []}


def build_prompt(config, profile, angle, log, examples, rules=None):
    """构建生成 prompt"""
    angle_names = {"A": "Story/Journey", "B": "Feedback Request", "C": "Value/Insight"}
    angle_name = angle_names.get(angle, "Story/Journey")

    angle_guides = {
        "A": """Story/Journey 角度：
- 以一个具体的失败、转折或令人惊讶的结果为钩子
- 结构：发生了什么 → 学到了什么 → 建了什么 → 对读者的问题
- 用真实数字和时间线
- 分享失败和教训让内容更真实""",
        "B": """Feedback Request 角度：
- 以你卡住的问题或需要的意见为钩子
- 结构：做了什么 → 不确定的地方 → 具体问题
- 让社区感觉他们的意见被需要
- 具体地描述你尝试过的和结果""",
        "C": """Value/Insight 角度：
- 以反直觉的发现或来之不易的教训为钩子
- 结构：洞见 → 为什么重要 → 如何发现的（产品背景）→ 讨论
- 先给价值，后提产品
- 让读者即使不点链接也有收获"""
    }

    recent_titles = get_recent_titles(log)
    recent_str = "\n".join(f"- {t}" for t in recent_titles) if recent_titles else "（暂无历史帖子）"

    examples_str = ""
    for i, ex in enumerate(examples, 1):
        examples_str += f"\n--- 示例 {i} ---\nTITLE: {ex['title']}\nBODY:\n{ex['body']}\n"

    system_prompt = f"""You are a Reddit content writer for {config.get('name', 'the product')}.

Product: {config.get('description', '')}
Target user: {config.get('target_user', '')}
Website: {config.get('website_url', '')}

STRICT RULES:
1. Title: NEVER start with "I built", "I made", "Check out", "Launching", "Excited to share"
2. Title: Use specific numbers, questions, "how I...", "what I learned", "after X months"
3. Title: 60-100 characters ideal
4. BANNED phrases (NEVER use): {', '.join(BANNED_PHRASES)}
5. REQUIRED patterns: contractions (I'm, it's), hedging ("I think", "might"), specific failures, approximate numbers ("~200 users", "about 3 months")
5b. SPAM TRIGGER WORDS (avoid these — they trigger Reddit's spam filter): {', '.join(SPAM_TRIGGER_WORDS)}
6. Body template: Hook (1-2 sentences) → Context (2-3 sentences) → Substance (story/insight/question) → Product mention (1 honest sentence) → CTA (one genuine question)
7. Must NOT sound like marketing. Sound like a real person sharing on Reddit.
8. Must disclose you built/work on the product.
9. End with a genuine, specific question for the community.
10. Use markdown formatting (bold, lists) sparingly and naturally."""

    # 构建规则部分
    rules_str = ""
    if rules and rules.get("rules"):
        rules_str = "\n\n⚠️ SUBREDDIT RULES (YOU MUST FOLLOW ALL OF THESE):\n"
        for r in rules["rules"]:
            rules_str += f'- **{r["name"]}**: {r["description"][:200]}\n'

    requirements_str = ""
    if rules and rules.get("requirements"):
        reqs = rules["requirements"]
        parts = []
        if reqs.get("title_min_length"):
            parts.append(f"Title minimum length: {reqs['title_min_length']} chars")
        if reqs.get("body_min_length"):
            parts.append(f"Body minimum length: {reqs['body_min_length']} chars")
        if reqs.get("title_required_strings"):
            parts.append(f"Title MUST contain one of: {reqs['title_required_strings']}")
        if reqs.get("body_required_strings"):
            parts.append(f"Body MUST contain one of: {reqs['body_required_strings']}")
        if reqs.get("is_flair_required"):
            parts.append("Flair is REQUIRED for this subreddit")
        if parts:
            requirements_str = "\n\n⚠️ POST REQUIREMENTS:\n" + "\n".join(f"- {p}" for p in parts)

    flair_str = ""
    if rules and rules.get("flair_required") and rules.get("flair_options"):
        flair_str = "\n\nAVAILABLE FLAIRS (pick the most appropriate one):\n"
        for f in rules["flair_options"][:10]:
            flair_str += f'- {f["text"]} (id: {f["id"]})\n'
        flair_str += "\nInclude your flair choice at the end: FLAIR: [flair text]"

    user_prompt = f"""Write a Reddit post for **{profile.get('subreddit', 'r/unknown')}** using **Angle {angle} ({angle_name})**.

{angle_guides.get(angle, angle_guides['A'])}

Subreddit context:
- Subscribers: {profile.get('subscribers', '?'):,}
- Activity: {profile.get('activity', '?')}
- Tone/rules: {profile.get('promo_rules', '?')}
- Community notes: {profile.get('notes', '?')}
{rules_str}{requirements_str}{flair_str}

Recent post titles (AVOID similar topics — be fresh and different):
{recent_str}

{f"Reference examples of good posts:{examples_str}" if examples_str else ""}

CRITICAL: Your post MUST comply with ALL subreddit rules above. If rules say no promotion, make the post genuinely valuable with only a brief, natural mention of the product. If rules require specific formats, follow them exactly.

Output EXACTLY in this format:
TITLE: [your title here]
---
BODY:
[your body here]"""

    return system_prompt, user_prompt


def quality_check(title, body):
    """质量检查，返回 (passed, issues)"""
    issues = []

    # 检查禁用词
    full_text = (title + " " + body).lower()
    for phrase in BANNED_PHRASES:
        if phrase in full_text:
            issues.append(f"包含禁用词: '{phrase}'")

    # 检查 Reddit 垃圾过滤触发词
    for word in SPAM_TRIGGER_WORDS:
        if word in full_text:
            issues.append(f"包含垃圾过滤触发词: '{word}'")

    # 检查标题开头
    for start in BAD_TITLE_STARTS:
        if title.lower().startswith(start):
            issues.append(f"标题以 '{start}' 开头")

    # 检查标题长度
    if len(title) < 30:
        issues.append(f"标题太短 ({len(title)} 字符，建议 60-100)")
    elif len(title) > 150:
        issues.append(f"标题太长 ({len(title)} 字符，建议 60-100)")

    # 检查正文长度
    if len(body) < 200:
        issues.append("正文太短 (建议至少 200 字符)")

    # 检查是否以问题结尾
    lines = body.strip().split("\n")
    last_line = lines[-1].strip() if lines else ""
    if "?" not in last_line and "?" not in (lines[-2].strip() if len(lines) > 1 else ""):
        issues.append("正文没有以问题结尾")

    return len(issues) == 0, issues


def parse_response(text):
    """解析 API 响应为 title + body"""
    title = ""
    body = ""

    lines = text.strip().split("\n")
    in_body = False

    for line in lines:
        if line.startswith("TITLE:"):
            title = line[6:].strip().strip('"')
        elif line.strip() == "---":
            continue
        elif line.startswith("BODY:"):
            in_body = True
            remainder = line[5:].strip()
            if remainder:
                body += remainder + "\n"
        elif in_body:
            body += line + "\n"

    return title.strip(), body.strip()


def generate_post(subreddit_profile, config, log, angle, model=None, max_retries=2):
    """
    生成一篇 Reddit 帖子

    返回: {"title": str, "body": str, "angle": str, "subreddit": str}
    """
    try:
        import anthropic
    except ImportError:
        print("❌ 需要安装 anthropic SDK: pip3 install anthropic")
        sys.exit(1)

    api_key = get_api_key()
    if not api_key:
        print("❌ 未找到 Anthropic API Key")
        print("   设置环境变量: export ANTHROPIC_API_KEY=your-key")
        print("   或保存到: memory/.anthropic_key")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    model = model or "claude-sonnet-4-20250514"

    # 获取 subreddit 规则
    print(f"  📋 正在获取 {subreddit_profile.get('subreddit', '?')} 的发帖规则...")
    rules = fetch_rules(subreddit_profile.get("subreddit", ""))
    if rules.get("rules"):
        print(f"  ✅ 获取到 {len(rules['rules'])} 条规则")
        if rules.get("flair_required"):
            print(f"  ⚠️  该 subreddit 要求 Flair")
    else:
        print(f"  ℹ️  未获取到特定规则")

    examples = load_example_drafts(limit=2)
    system_prompt, user_prompt = build_prompt(config, subreddit_profile, angle, log, examples, rules=rules)

    for attempt in range(max_retries + 1):
        extra_instructions = ""
        if attempt > 0:
            extra_instructions = f"\n\nPREVIOUS ATTEMPT FAILED quality check. Issues: {', '.join(issues)}. Please fix these specific problems."

        response = client.messages.create(
            model=model,
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt + extra_instructions}],
        )

        text = response.content[0].text
        title, body = parse_response(text)

        if not title or not body:
            issues = ["无法解析标题或正文"]
            if attempt < max_retries:
                continue
            return None

        passed, issues = quality_check(title, body)
        if passed or attempt >= max_retries:
            # 检查生成内容中是否包含 flair 选择
            flair_choice = None
            for line in body.split("\n"):
                if line.strip().upper().startswith("FLAIR:"):
                    flair_choice = line.strip()[6:].strip()
                    body = body.replace(line, "").strip()
                    break

            return {
                "title": title,
                "body": body,
                "angle": angle,
                "subreddit": subreddit_profile.get("subreddit", ""),
                "quality_passed": passed,
                "quality_issues": issues if not passed else [],
                "attempts": attempt + 1,
                "flair": flair_choice,
                "rules": rules,
            }

    return None


def main():
    os.chdir(BASE_DIR)

    parser = argparse.ArgumentParser(description="Claude API 内容生成")
    parser.add_argument("--subreddit", required=True, help="目标 subreddit (如 r/SideProject)")
    parser.add_argument("--angle", required=True, choices=["A", "B", "C"], help="帖子角度")
    parser.add_argument("--model", default=None, help="Claude 模型 (默认 claude-sonnet-4-20250514)")
    args = parser.parse_args()

    config = load_json("memory/config.json")
    if not config:
        print("❌ 未找到产品配置，请先运行 setup")
        sys.exit(1)

    profiles = load_json("memory/subreddit-profiles.json", [])
    profile = next((p for p in profiles if p["subreddit"].lower() == args.subreddit.lower()), None)
    if not profile:
        profile = {"subreddit": args.subreddit, "subscribers": 0, "activity": "unknown",
                    "promo_rules": "", "notes": "", "best_angle": args.angle}

    log = load_json("memory/posted-log.json", [])

    print(f"\n🤖 正在生成 {args.subreddit} 的帖子（角度 {args.angle}）...")
    result = generate_post(profile, config, log, args.angle, model=args.model)

    if result:
        print(f"\n✅ 生成成功（{result['attempts']} 次尝试）")
        print(f"\n{'='*60}")
        print(f"TITLE: {result['title']}")
        print(f"{'='*60}")
        print(result['body'])
        print(f"{'='*60}")
        if result.get("quality_issues"):
            print(f"\n⚠️  质量警告: {', '.join(result['quality_issues'])}")
    else:
        print("❌ 生成失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
