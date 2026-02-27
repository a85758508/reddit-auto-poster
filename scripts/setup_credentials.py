#!/usr/bin/env python3
"""
scripts/setup_credentials.py
引导新用户配置 Reddit API 凭证（对零基础用户友好）
"""

import json
import os
import sys

CRED_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "memory", ".reddit_credentials"
)

def green(s):  return f"\033[32m{s}\033[0m"
def yellow(s): return f"\033[33m{s}\033[0m"
def red(s):    return f"\033[31m{s}\033[0m"
def bold(s):   return f"\033[1m{s}\033[0m"
def blue(s):   return f"\033[34m{s}\033[0m"
def dim(s):    return f"\033[2m{s}\033[0m"


def check_praw():
    try:
        import praw
        return True
    except ImportError:
        print(yellow("  PRAW 未安装，正在安装..."))
        os.system("pip3 install praw --quiet")
        try:
            import praw
            print(green("  ✅ PRAW 安装完成"))
            return True
        except ImportError:
            print(red("  ❌ PRAW 安装失败，请手动运行: pip3 install praw"))
            return False


def test_connection(client_id, client_secret, username, password):
    try:
        import praw
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent="reddit-assistant/2.0 (personal script)",
            username=username,
            password=password,
        )
        me = reddit.user.me()
        total_karma = (me.link_karma or 0) + (me.comment_karma or 0)
        return True, f"u/{me.name}（Karma: {total_karma:,}）"
    except Exception as e:
        err_str = str(e)
        if "invalid_grant" in err_str or "401" in err_str:
            return False, "用户名或密码错误。注意：用户名不含 u/，密码区分大小写。"
        elif "invalid_client" in err_str or "403" in err_str:
            return False, "client_id 或 client_secret 错误，请重新确认。"
        elif "two-factor" in err_str.lower() or "2fa" in err_str.lower():
            return False, "账号开启了两步验证（2FA），需要在 Reddit 设置中临时关闭。"
        elif "RATELIMIT" in err_str:
            return False, "请求过于频繁，请等待 1 分钟后重试。"
        else:
            return False, f"连接失败: {err_str}"


def get_input(prompt, secret=False):
    import getpass
    while True:
        try:
            val = getpass.getpass(f"  {prompt}: ") if secret else input(f"  {prompt}: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n已取消")
            sys.exit(0)
        if val:
            return val
        print(yellow("  ⚠️  不能为空，请重新输入"))


def main():
    print()
    print(bold("╔════════════════════════════════════════╗"))
    print(bold("║   Reddit API 凭证配置向导              ║"))
    print(bold("╚════════════════════════════════════════╝"))
    print()

    if os.path.exists(CRED_FILE):
        try:
            with open(CRED_FILE) as f:
                existing = json.load(f)
            print(yellow(f"  ⚠️  已存在凭证（账号: {existing.get('username', '?')}）"))
            try:
                if input("  重新配置? [y/N]: ").strip().lower() != 'y':
                    print(dim("  保持现有配置。"))
                    return
            except (KeyboardInterrupt, EOFError):
                sys.exit(0)
            print()
        except Exception:
            pass

    if not check_praw():
        sys.exit(1)

    print(bold("  【获取 API 凭证的步骤】"))
    print()
    print(f"  1. 打开：{blue('https://www.reddit.com/prefs/apps')}")
    print(f"  2. 点击底部 {bold('\"create another app\"')}")
    print(f"  3. 填写：")
    print(f"       name: 任意，如 {bold('my-assistant')}")
    print(f"       类型: {bold('script')}（第三个选项）")
    print(f"       redirect uri: {bold('http://localhost:8080')}")
    print(f"  4. 点击 {bold('\"create app\"')}")
    print(f"  5. 记下 {bold('client_id')}（app名下方）和 {bold('client_secret')}（secret行）")
    print()

    try:
        input("  准备好后按回车继续...")
    except (KeyboardInterrupt, EOFError):
        sys.exit(0)

    print()
    print(bold("  【输入凭证】"))
    print(dim("  （密码输入时不显示字符，正常现象）"))
    print()

    max_tries = 3
    extra = 0
    attempt = 0
    while attempt < max_tries + extra:
        attempt += 1
        if attempt > 1:
            print(f"\n  {yellow(f'第 {attempt} 次尝试')}")

        client_id     = get_input("client_id（app 名称下方的字符串）")
        client_secret = get_input("client_secret（secret 那行）", secret=True)
        username      = get_input("Reddit 用户名（不含 u/）").lstrip("u/")
        password      = get_input("Reddit 密码", secret=True)

        print()
        print(dim("  验证中..."), end="", flush=True)
        success, msg = test_connection(client_id, client_secret, username, password)

        if success:
            print(f"\r  {green('✅ 连接成功！' + msg)}")
            break
        else:
            print(f"\r  {red('❌ 失败：' + msg)}")
            if attempt >= max_tries + extra:
                print()
                print("  排查建议：")
                print(f"    · 类型必须选 {bold('script')}（不是 web app）")
                print(f"    · client_id 是 app 名下方那行，约14个字符")
                print(f"    · 如有两步验证，需在 Reddit 设置中暂时关闭")
                print(f"    · 凭证页面：{blue('https://www.reddit.com/prefs/apps')}")
                try:
                    if input("\n  继续重试? [y/N]: ").strip().lower() == 'y':
                        extra += 3
                        continue
                except (KeyboardInterrupt, EOFError):
                    pass
                sys.exit(1)

    # 保存
    os.makedirs(os.path.dirname(CRED_FILE), exist_ok=True)
    with open(CRED_FILE, 'w') as f:
        json.dump({
            "client_id": client_id,
            "client_secret": client_secret,
            "username": username,
            "password": password,
            "user_agent": "reddit-assistant/2.0 (personal script)"
        }, f, indent=2)
    os.chmod(CRED_FILE, 0o600)

    print()
    print(green("  ✅ 凭证已保存（权限 600，仅你可读）"))
    print()
    print("  接下来运行：")
    print(f"    {blue('reddit-assistant setup')}   配置产品信息")
    print(f"    {blue('reddit-assistant draft')}   开始写第一篇帖子")
    print()


if __name__ == "__main__":
    main()
