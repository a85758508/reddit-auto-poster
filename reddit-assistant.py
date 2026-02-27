#!/usr/bin/env python3
"""
reddit-assistant — 统一 CLI 入口
用法: python3 reddit-assistant.py <命令> [选项]

命令:
  setup        首次配置产品信息和 Reddit 凭证
  draft        交互式生成帖子草稿
  log          记录已发布的帖子 URL
  sync         更新所有帖子的最新数据（调用 Reddit API）
  report       生成分析报告
  status       查看当前状态摘要
  repair       修复损坏的日志文件
  auto-setup   配置自动发帖系统
  auto-run     手动触发自动发帖
  auto-status  查看自动化状态
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone


# ── 颜色输出 ──────────────────────────────────────────────────────────────────
def green(s): return f"\033[32m{s}\033[0m"
def yellow(s): return f"\033[33m{s}\033[0m"
def red(s):   return f"\033[31m{s}\033[0m"
def bold(s):  return f"\033[1m{s}\033[0m"
def dim(s):   return f"\033[2m{s}\033[0m"


def run(cmd: list, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=False)


def script(name: str) -> str:
    """返回脚本路径（兼容从任意目录调用）"""
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "scripts", name)


def load_json(path: str, default=None):
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return default
    return default


# ── 命令实现 ──────────────────────────────────────────────────────────────────

def cmd_status(args):
    """显示当前状态摘要"""
    print(bold("\n📊 Reddit Assistant — 状态摘要"))
    print("─" * 45)

    # 产品配置
    config = load_json("memory/config.json")
    if config:
        print(f"  产品: {green(config.get('name', '?'))}")
        print(f"  描述: {config.get('description', '?')}")
        print(f"  阶段: {config.get('stage', '?')}")
    else:
        print(f"  产品: {yellow('未配置 → 运行 setup')}")


    # 帖子统计
    log = load_json("memory/posted-log.json", [])
    active = [p for p in log if p.get("status") != "deleted"]
    with_data = [p for p in active if p.get("score") is not None]

    print(f"\n  帖子记录: {len(active)} 篇")
    if with_data:
        avg_score = sum(p["score"] for p in with_data) / len(with_data)
        top = max(with_data, key=lambda p: p["score"])
        print(f"  平均 Score: {avg_score:.1f}")
        print(f"  最高分: {top['score']} ({top.get('subreddit','?')})")
    else:
        print(f"  {dim('（还没有帖子数据，发帖后运行 log 命令记录）')}")

    # 草稿
    drafts_dir = "memory/drafts"
    draft_count = len([f for f in os.listdir(drafts_dir) if f.endswith(".md")]) if os.path.exists(drafts_dir) else 0
    print(f"\n  待发草稿: {draft_count} 篇")

    # Subreddit 档案
    profiles = load_json("memory/subreddit-profiles.json", [])
    print(f"  社区档案: {len(profiles)} 个")

    # 最近一次分析
    perf_dir = "memory/performance"
    if os.path.exists(perf_dir):
        reports = sorted(os.listdir(perf_dir))
        if reports:
            print(f"  最新报告: {reports[-1].replace('.md','')}")

    print()


def cmd_setup(args):
    """交互式配置向导"""
    print(bold("\n🔧 Reddit Assistant 配置向导"))
    print("─" * 45)

    # 产品信息
    print("\n【第一步】产品信息\n")
    name = input("  产品名称: ").strip()
    description = input("  一句话描述 (是什么/给谁用的): ").strip()
    target_user = input("  目标用户群体: ").strip()
    stage = input("  开发阶段 [idea/beta/launched/growing]: ").strip() or "launched"
    github = input("  GitHub URL (可选，回车跳过): ").strip()
    website = input("  网站 URL (可选，回车跳过): ").strip()

    if not all([name, description, target_user]):
        print(red("\n❌ 产品名称、描述、目标用户不能为空"))
        sys.exit(1)

    cmd = [
        sys.executable, script("init_config.py"),
        "--name", name,
        "--description", description,
        "--target_user", target_user,
        "--stage", stage,
    ]
    if github:
        cmd += ["--github_url", github]
    if website:
        cmd += ["--website_url", website]

    run(cmd)

    # 初始化 memory
    run(["bash", script("init_memory.sh")])


    print(green("\n✅ 配置完成！"))
    print("  下一步：运行 draft 命令开始写帖子")
    print(f"  {dim('python3 reddit-assistant.py draft')}\n")


def cmd_draft(args):
    """交互式草稿生成"""
    print(bold("\n✍️  生成 Reddit 帖子草稿"))
    print("─" * 45)

    # 检查配置
    config = load_json("memory/config.json")
    if not config:
        print(yellow("⚠️  未找到产品配置，请先运行 setup"))
        sys.exit(1)

    print(f"\n  产品: {config['name']} — {config['description']}")

    # 加载社区档案
    profiles = load_json("memory/subreddit-profiles.json", [])

    # 选择 subreddit
    print(bold("\n【目标社区】"))
    if profiles:
        print("  已知社区档案：")
        for i, p in enumerate(profiles, 1):
            print(f"    {i}. {p['subreddit']} ({p.get('activity','?')} activity, {p.get('subscribers',0):,} 订阅)")
        print(f"    {len(profiles)+1}. 手动输入")
        choice = input(f"\n  选择 (1-{len(profiles)+1}): ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(profiles):
                subreddit = profiles[idx]["subreddit"]
            else:
                subreddit = input("  输入 subreddit（如 r/SideProject）: ").strip()
        except ValueError:
            subreddit = input("  输入 subreddit（如 r/SideProject）: ").strip()
    else:
        subreddit = input("  目标 subreddit（如 r/SideProject）: ").strip()

    if not subreddit.startswith("r/"):
        subreddit = f"r/{subreddit}"

    # 帖子信息
    print(bold("\n【帖子内容】"))
    milestone = input("  这次要分享的里程碑/故事（越具体越好）: ").strip()
    goal = input("  发帖目标 [story/feedback/insight] (默认 story): ").strip() or "story"
    angle_map = {"story": "A", "feedback": "B", "insight": "C", "A": "A", "B": "B", "C": "C"}
    angle = angle_map.get(goal.upper(), angle_map.get(goal, "A"))

    # 生成标题建议
    print(bold(f"\n【Claude 建议】角度 {angle} 的帖子框架"))
    angle_guides = {
        "A": (
            "Story/Journey 角度",
            "标题公式: 「[结果] + [时间/代价] — [关键转折]」\n"
            "  例: 'After 8 months of failures, we finally crossed $1k MRR — here's what changed'\n\n"
            "正文结构:\n"
            "  1. 开头：一个具体的失败或转折时刻\n"
            "  2. 背景：为什么你做这件事\n"
            "  3. 主体：发生了什么（带数字）\n"
            "  4. 产品提及：一句话，透明\n"
            "  5. 结尾：对读者有意义的问题"
        ),
        "B": (
            "Feedback Request 角度",
            "标题公式: 「[具体问题/困境] — 寻求建议/经验」\n"
            "  例: 'Been building a freelancer time tracker for 6 months — struggling with pricing. Anyone been through this?'\n\n"
            "正文结构:\n"
            "  1. 你在解决什么问题\n"
            "  2. 你目前的尝试和结果\n"
            "  3. 具体卡在哪里\n"
            "  4. 向社区提问（开放式）"
        ),
        "C": (
            "Value/Insight 角度",
            "标题公式: 「[反直觉的发现] + [来源]」\n"
            "  例: 'The feature our users actually use surprised us — it wasn't what we built first'\n\n"
            "正文结构:\n"
            "  1. 先抛出洞察（不要卖关子）\n"
            "  2. 数据或证据\n"
            "  3. 背后的原因分析\n"
            "  4. 你是怎么发现的（产品背景）\n"
            "  5. 对其他建设者的意义"
        ),
    }

    angle_name, guide = angle_guides.get(angle, angle_guides["A"])
    print(f"\n  {bold(angle_name)}")
    print(f"\n{guide}")

    # 让用户写标题和正文，或标记为 AI 生成
    print(bold("\n【写帖子】"))
    print(dim("  提示：把以上框架和里程碑发给 Claude 让它帮你写，然后粘贴到这里"))
    print()

    title = input("  标题: ").strip()
    print("  正文（Ctrl+D 结束）:")
    body_lines = []
    try:
        while True:
            line = input()
            body_lines.append(line)
    except EOFError:
        pass
    body = "\n".join(body_lines).strip()

    if not title or not body:
        print(yellow("\n⚠️  标题或正文为空，草稿未保存"))
        sys.exit(1)

    notes = input("\n  备注（时机、注意事项等，可选）: ").strip()

    # 质量检查
    print(bold("\n【质量检查】"))
    banned = ["game-changing", "revolutionary", "excited to share", "thrilled to",
              "innovative", "disruptive", "cutting-edge", "seamless", "robust"]
    found_banned = [w for w in banned if w.lower() in (title + body).lower()]
    if found_banned:
        print(yellow(f"  ⚠️  发现促销词汇: {', '.join(found_banned)}"))
        print(dim("     建议替换为具体描述"))
    else:
        print(green("  ✅ 未发现常见促销词汇"))

    starts_bad = any(title.lower().startswith(p) for p in ["i built", "i made", "check out", "launching", "excited"])
    if starts_bad:
        print(yellow("  ⚠️  标题以推广词开头，建议改写"))
    else:
        print(green("  ✅ 标题开头良好"))

    # 保存草稿
    run([
        sys.executable, script("save_draft.py"),
        "--subreddit", subreddit,
        "--angle", angle,
        "--title", title,
        "--body", body,
        "--notes", notes or "",
    ])

    print(green(f"\n✅ 草稿已保存！"))
    print(f"\n  下一步：")
    print(f"  1. 登录 Reddit，复制内容手动发布")
    print(f"  2. 发布后运行：")
    print(f"     {bold('python3 reddit-assistant.py log --url <帖子URL> --angle ' + angle)}\n")


def cmd_log(args):
    """记录已发布的帖子"""
    print(bold("\n📝 记录已发布帖子"))
    print("─" * 45)

    url = args.url
    if not url:
        url = input("  Reddit 帖子 URL: ").strip()

    angle = args.angle
    if not angle:
        angle = input("  帖子角度 [A/B/C]: ").strip().upper()

    if angle not in ("A", "B", "C"):
        print(red(f"❌ 无效角度: {angle}（应为 A、B 或 C）"))
        sys.exit(1)

    draft_file = args.draft_file or ""

    run([
        sys.executable, script("log_post.py"),
        "--url", url,
        "--angle", angle,
        "--draft_file", draft_file,
    ])


def cmd_sync(args):
    """从 Reddit 拉取最新数据"""
    print(bold("\n🔄 同步 Reddit 数据"))
    print("─" * 45)

    flags = []
    if args.force:
        flags.append("--force")
        print(dim("  强制模式：更新所有帖子（忽略 48h 缓存）"))
    else:
        print(dim("  只更新 48h 以上未刷新的帖子"))

    print()
    run([sys.executable, script("fetch_performance.py")] + flags)


def cmd_report(args):
    """生成分析报告"""
    print(bold("\n📈 生成分析报告"))
    print("─" * 45)

    # 先同步数据
    if not args.no_sync:
        print(dim("  先更新帖子数据...\n"))
        subprocess.run([sys.executable, script("fetch_performance.py")], check=False)
        print()

    month = args.month or ""
    cmd = [sys.executable, script("generate_report.py")]
    if month:
        cmd += ["--month", month]
        print(f"  分析月份: {month}")
    else:
        print(f"  分析范围: 全部历史数据")

    print()
    run(cmd)


def cmd_repair(args):
    """修复损坏的日志文件"""
    print(bold("\n🔧 修复日志文件"))
    print("─" * 45 + "\n")
    run([sys.executable, script("repair_log.py")])


# ── 自动化命令 ────────────────────────────────────────────────────────────────

def cmd_auto_setup(args):
    """配置自动发帖系统"""
    print(bold("\n⚙️  自动发帖 — 配置"))
    print("─" * 45)

    # 检查 Chrome
    print("\n【第一步】检测 Chrome...")
    try:
        result = subprocess.run(
            ["osascript", "-e", 'tell application "Google Chrome" to return count of windows'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip() not in ("0", ""):
            print(green("  ✅ Chrome 已就绪"))
        else:
            print(yellow("  ⚠️  Chrome 未打开，请先打开 Chrome 并登录 Reddit"))
    except Exception:
        print(red("  ❌ 无法检测 Chrome"))

    print(dim("  确保: Chrome → View → Developer → Allow JavaScript from Apple Events"))

    # Anthropic API Key
    print("\n【第二步】Anthropic API Key")
    key_file = "memory/.anthropic_key"
    env_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if env_key:
        print(green(f"  ✅ 环境变量 ANTHROPIC_API_KEY 已设置 ({env_key[:8]}...)"))
    elif os.path.exists(key_file):
        print(green(f"  ✅ API Key 已保存在 {key_file}"))
    else:
        key = input("  请输入 Anthropic API Key: ").strip()
        if key:
            with open(key_file, "w") as f:
                f.write(key)
            os.chmod(key_file, 0o600)
            print(green(f"  ✅ 已保存到 {key_file}"))

            # 测试
            print("  正在测试 API 连接...")
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=key)
                resp = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=10,
                    messages=[{"role": "user", "content": "Hi"}]
                )
                print(green("  ✅ API 连接成功"))
            except Exception as e:
                print(red(f"  ❌ API 连接失败: {e}"))
        else:
            print(yellow("  ⚠️  跳过（需要在运行前设置）"))

    # 自动化配置
    print("\n【第三步】发帖配置")
    config_file = "memory/automation-config.json"
    if os.path.exists(config_file):
        existing = load_json(config_file, {})
        print(f"  当前配置: 每天 {existing.get('posts_per_day', 3)} 篇, "
              f"间隔 {existing.get('min_hours_between_posts', 2.5)} 小时")
        change = input("  要修改吗？[y/N]: ").strip().lower()
        if change != "y":
            print(dim("  保持当前配置"))
            print(green("\n✅ 自动化配置完成！"))
            _print_auto_usage()
            return

    posts_per_day = input("  每天发帖数 [3]: ").strip() or "3"
    hours_between = input("  帖子间隔小时 [2.5]: ").strip() or "2.5"
    min_days = input("  同 subreddit 最少间隔天数 [4]: ").strip() or "4"

    config = {
        "posts_per_day": int(posts_per_day),
        "min_days_between_same_subreddit": int(min_days),
        "min_hours_between_posts": float(hours_between),
        "content_model": "claude-sonnet-4-20250514",
        "dry_run": False,
        "enable_notifications": True,
        "posting_start_hour_local": 8,
    }

    os.makedirs("memory", exist_ok=True)
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)
    print(green(f"\n  ✅ 配置已保存: {config_file}"))

    # launchd 安装提示
    print("\n【第四步】定时任务（可选）")
    print(dim("  如需每天自动运行，安装 launchd 定时任务:"))
    print(f"  cp com.reddit-assistant.daily.plist ~/Library/LaunchAgents/")
    print(f"  launchctl load ~/Library/LaunchAgents/com.reddit-assistant.daily.plist")

    print(green("\n✅ 自动化配置完成！"))
    _print_auto_usage()


def _print_auto_usage():
    print(f"\n  手动运行:")
    print(f"    {bold('python3 reddit-assistant.py auto-run --dry-run')}   # 测试（不实际发帖）")
    print(f"    {bold('python3 reddit-assistant.py auto-run')}             # 正式运行")
    print(f"    {bold('python3 reddit-assistant.py auto-run --count 1')}   # 只发 1 篇")
    print(f"    {bold('python3 reddit-assistant.py auto-status')}          # 查看状态\n")


def cmd_auto_run(args):
    """手动触发自动发帖"""
    cmd = [sys.executable, script("auto_orchestrator.py")]
    if args.dry_run:
        cmd.append("--dry-run")
    if args.count:
        cmd.extend(["--count", str(args.count)])
    if args.no_wait:
        cmd.append("--no-wait")
    run(cmd, check=False)


def cmd_auto_status(args):
    """查看自动化状态"""
    print(bold("\n🤖 自动发帖 — 状态"))
    print("─" * 45)

    # 自动化配置
    auto_config = load_json("memory/automation-config.json")
    if auto_config:
        print(f"\n  配置: {auto_config.get('posts_per_day', '?')} 篇/天, "
              f"间隔 {auto_config.get('min_hours_between_posts', '?')} 小时")
    else:
        print(yellow("\n  ⚠️  未配置 → 运行 auto-setup"))
        return

    # API Key
    key_file = "memory/.anthropic_key"
    has_key = os.environ.get("ANTHROPIC_API_KEY") or os.path.exists(key_file)
    print(f"  API Key: {green('✅ 已配置') if has_key else red('❌ 未配置')}")

    # 最近运行
    latest = load_json("memory/automation/latest-run.json")
    if latest:
        summary = latest.get("summary", {})
        print(f"\n  上次运行: {latest.get('date', '?')}")
        print(f"  结果: {green(str(summary.get('succeeded', 0)) + ' 成功')} / "
              f"{red(str(summary.get('failed', 0)) + ' 失败') if summary.get('failed') else dim('0 失败')}")

        for post in latest.get("posts", []):
            icon = "✅" if post.get("status") == "success" else "❌"
            print(f"    {icon} {post.get('subreddit', '?')} — {post.get('title', '?')[:45]}...")
    else:
        print(dim("\n  还没有运行记录"))

    # 下次预览
    print(bold("\n  下次发帖预览:"))
    try:
        result = subprocess.run(
            [sys.executable, script("auto_scheduler.py"), "--json"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            targets = json.loads(result.stdout)
            angle_names = {"A": "Story", "B": "Feedback", "C": "Insight"}
            for t in targets:
                print(f"    → {t['subreddit']} ({angle_names.get(t['angle'], t['angle'])})")
            if not targets:
                print(dim("    所有社区在冷却期内"))
        else:
            print(dim("    无法预览"))
    except Exception:
        print(dim("    无法预览"))

    print()


# ── 主程序 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="reddit-assistant",
        description="Reddit 内容助手 — 写帖、追踪、分析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
命令示例:
  python3 reddit-assistant.py status           # 查看状态摘要
  python3 reddit-assistant.py setup            # 首次配置
  python3 reddit-assistant.py draft            # 交互式写草稿
  python3 reddit-assistant.py log --url <URL> --angle A   # 记录已发帖子
  python3 reddit-assistant.py sync             # 更新帖子数据
  python3 reddit-assistant.py report           # 生成月度报告
  python3 reddit-assistant.py report --month 2026-02
  python3 reddit-assistant.py repair           # 修复损坏的日志
  python3 reddit-assistant.py auto-setup       # 配置自动发帖
  python3 reddit-assistant.py auto-run         # 手动触发自动发帖
  python3 reddit-assistant.py auto-run --dry-run  # 测试运行（不实际发帖）
  python3 reddit-assistant.py auto-status      # 查看自动化状态
        """
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<命令>")
    subparsers.required = True

    # status
    p_status = subparsers.add_parser("status", help="查看当前状态摘要")
    p_status.set_defaults(func=cmd_status)

    # setup
    p_setup = subparsers.add_parser("setup", help="首次配置产品信息和 Reddit 凭证")
    p_setup.set_defaults(func=cmd_setup)

    # draft
    p_draft = subparsers.add_parser("draft", help="交互式生成帖子草稿")
    p_draft.set_defaults(func=cmd_draft)

    # log
    p_log = subparsers.add_parser("log", help="记录已发布的帖子 URL")
    p_log.add_argument("--url", default="", help="Reddit 帖子完整 URL")
    p_log.add_argument("--angle", default="", choices=["A", "B", "C", ""], help="帖子角度")
    p_log.add_argument("--draft_file", default="", help="对应草稿文件路径（可选）")
    p_log.set_defaults(func=cmd_log)

    # sync
    p_sync = subparsers.add_parser("sync", help="从 Reddit 拉取最新数据")
    p_sync.add_argument("--force", action="store_true", help="强制更新所有帖子")
    p_sync.set_defaults(func=cmd_sync)

    # report
    p_report = subparsers.add_parser("report", help="生成分析报告")
    p_report.add_argument("--month", default="", help="指定月份 YYYY-MM（留空=全部）")
    p_report.add_argument("--no-sync", action="store_true", dest="no_sync", help="跳过数据同步直接生成报告")
    p_report.set_defaults(func=cmd_report)

    # repair
    p_repair = subparsers.add_parser("repair", help="修复损坏的日志文件")
    p_repair.set_defaults(func=cmd_repair)

    # auto-setup
    p_auto_setup = subparsers.add_parser("auto-setup", help="配置自动发帖系统")
    p_auto_setup.set_defaults(func=cmd_auto_setup)

    # auto-run
    p_auto_run = subparsers.add_parser("auto-run", help="手动触发自动发帖")
    p_auto_run.add_argument("--dry-run", action="store_true", dest="dry_run", help="只生成不发帖")
    p_auto_run.add_argument("--count", type=int, default=None, help="发帖数量")
    p_auto_run.add_argument("--no-wait", action="store_true", dest="no_wait", help="不等待间隔（测试用）")
    p_auto_run.set_defaults(func=cmd_auto_run)

    # auto-status
    p_auto_status = subparsers.add_parser("auto-status", help="查看自动化状态")
    p_auto_status.set_defaults(func=cmd_auto_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    # 确保从技能目录运行
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    main()
