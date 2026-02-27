# Reddit Content Assistant v2

基于 PHY041/claude-agent-skills 架构理念构建的 Reddit 内容效率工具。  
**合规使用官方数据，专注提升创作质量和速度。**

---

## 解决的三个痛点

| 痛点 | 解决方案 |
|------|----------|
| 写帖子标题和正文太慢 | Claude 生成3个角度草稿 + 质量门控自动检测 |
| 不知道去哪些 subreddit 发 | 脚本获取社区实时数据 + 建立你的专属档案库 |
| 发完不知道效果如何 | Reddit 公开 API 自动追踪数据 + 月度分析报告 |

---

## 架构亮点（来自 PHY041 的设计理念）

```
SKILL.md                    ← Claude 的"大脑"：Just-in-Time 上下文注入
  └── 触发词匹配
  └── 5个工作流（Workflow A-E）
  └── 质量门控（Quality Gate）
  └── 错误恢复机制

scripts/                    ← 执行层：真实数据操作
  ├── reddit_client.py      ← Reddit 公开 API 封装
  ├── fetch_performance.py  ← 批量拉取帖子数据
  ├── generate_report.py    ← 月度分析 + 洞察生成
  ├── save_draft.py         ← 草稿保存
  ├── log_post.py           ← 发帖记录
  └── ...

memory/                     ← 长期记忆（文件系统 = LLM 数据库）
  ├── config.json           ← 产品配置
  ├── posted-log.json       ← 所有帖子 + 实时指标
  ├── subreddit-profiles.json ← 社区研究档案
  ├── drafts/               ← 草稿存档
  └── performance/          ← 月度报告

references/
  └── subreddit-guide.md    ← Claude 执行时按需读取的知识库
```

---

## 安装

```bash
git clone <this-repo> reddit-assistant
cd reddit-assistant
bash setup.sh
```

**安装后配置（两步）：**

```bash
# 1. 配置你的产品信息
python3 scripts/init_config.py \
  --name "你的产品名" \
  --description "一句话描述" \
  --target_user "目标用户群体" \
  --stage launched

# 2. 配置 Reddit API 凭证（用于数据追踪）
# 先去 https://www.reddit.com/prefs/apps 创建 script 类型应用
python3 scripts/setup_credentials.py
```

---

## 使用方式

在 Claude Code 中自然语言驱动：

### 写帖子
```
claude "帮我写一篇 Reddit 帖子，刚刚达到 100 个付费用户，产品是一个时间追踪工具"
```
Claude 会：读取你的产品配置 → 推荐合适的 subreddit → 生成3个角度草稿 → 质量检测 → 保存草稿

### 研究社区
```
claude "找适合我的 AI 写作工具的 subreddit，目标用户是开发者"
```
Claude 会：搜索候选社区 → 调用脚本获取实时数据 → 建立档案 → 给出推荐排序

### 查看效果
```
claude "生成上个月的 Reddit 发帖分析报告"
```
Claude 会：运行 fetch_performance.py 更新数据 → 运行 generate_report.py → 输出洞察和建议

### 发帖后记录（手动发布后运行）
```bash
python3 scripts/log_post.py \
  --url "https://reddit.com/r/SideProject/comments/abc123/" \
  --angle A
```

---

## 完整工作流

```
1. Setup（首次）
   python3 scripts/init_config.py ...
   python3 scripts/setup_credentials.py

2. 写帖子
   claude "写 Reddit 帖子"
   → 选择草稿 → 复制到 Reddit → 手动发布

3. 记录
   python3 scripts/log_post.py --url <URL> --angle A

4. 追踪（48小时后）
   python3 scripts/fetch_performance.py

5. 分析（每月）
   python3 scripts/generate_report.py --month 2026-02
```

---

## v1 → v2 升级内容

| 功能 | v1 | v2 |
|------|----|----|
| SKILL.md 触发词 | 基础 | 完整 YAML frontmatter + 7个触发词组 |
| 工作流 | 3个 | 5个（新增 Setup + Log） |
| Memory 系统 | 基础草稿 | 完整状态管理（config/log/profiles/performance） |
| Reddit 数据 | curl 一次性 | Python 脚本批量追踪 + 48h 缓存 |
| 报告 | 表格 | 洞察 + 具体建议 + 角度对比 |
| 错误处理 | 无 | 6种场景 + 回退策略 |
| 环境检测 | 无 | check_env.sh 自动检测 |
| 安全 | 无 | .gitignore + 凭证文件 600 权限 |

---

## 关于发帖

实际发帖仍需**手动操作**（登录 Reddit，复制内容发布）。  

这是有意为之的设计：Reddit 的真正价值在于**发帖后的真实互动**——回复评论、参与讨论、建立社区关系。这部分 AI 无法替代，也不应该替代。

工具负责让你**花更少时间写内容、花更多时间做真实互动**。
