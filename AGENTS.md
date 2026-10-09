# AGENTS.md - DDMJC Jekyll Site

## ⚡ SKILLS — LOAD THESE FIRST

| Skill | 位置 | 何时加载 |
|-------|------|---------|
| **ddmjc-talk-post** | `.agents/skills/ddmjc-talk-post/SKILL.md` | 收到 `*_Speaker_Informance.docx`（投递至 `for_administrators/speaker_info/`）、要创建新一期报告 post、或需要完结上一篇报告时 |

> ddmjc-talk-post：三阶段全自动流水线（① docx 解析 → ② 生成 post → ③ 完结上一篇），
> 纯 stdlib 脚本，绝不自动 git commit/push。处理报告人信息 docx 时**必须**先读该 SKILL.md。

Guidelines for AI agents working on the DDMJC (Diffusion Decision Model Journal Club) Jekyll website.

## Project Overview

This is a **Jekyll static site** deployed on GitHub Pages for the DDMJC academic journal club. It hosts:
- **Schedule posts**: 24 meeting records with speaker info, abstracts, and recordings
- **Papers**: Academic paper discussions (to be migrated from Notion)
- **Resources**: Discussion threads and tutorials (to be migrated from Notion)

## Build Commands

### Local Development (if Jekyll installed)
```bash
# Install dependencies
bundle install

# Build site
bundle exec jekyll build

# Serve locally with live reload
bundle exec jekyll serve --livereload

# Build for production
bundle exec jekyll build --environment=production
```

### GitHub Pages Deployment
- **Automatic**: Push to `main` branch triggers GitHub Actions workflow (`.github/workflows/jekyll.yml`)
- **Manual**: Use "Run workflow" in GitHub Actions tab
- **Build status**: Check https://github.com/DDMJournalClub/DDM_Journal_Club/actions

### Verify Build
```bash
# Check _site folder after build
ls -la _site/

# Validate HTML (optional)
htmlproofer _site/ --disable-external
```

## Code Style Guidelines

### File Organization
```
_posts/           # Jekyll posts (YYYY-MM-DD-slug.md)
_layouts/         # HTML layouts (default.html, post.html)
_includes/        # Reusable HTML snippets
assets/           # Static assets (images, css, js)
templates/        # Post templates for content creation
Private & Shared/ # Notion backup (excluded from build)
```

### Frontmatter Standards

#### Schedule Post Template
```yaml
---
title: "完整报告标题"
short_title: "简短标题(20字以内)"
speaker: "报告人姓名"
institution: "报告人单位"
host: "主持人姓名"
date: "YYYY-MM-DD"
time: "20:00-21:00"
timezone: "北京时间 [GMT+8]"
zoom_id: "123 4567 8901"
language: "中文"  # 中文 / English
tags:
  - "DDM"
  - "tutorial"
recording: true  # true = 已有录屏，false = 暂无
status: done    # plan / in-progress / done
speaker_image: "/assets/images/speakers/YYYY-MM-DD_name.png"
links:
  paper: "https://doi.org/..."
  bilibili: "https://bilibili.com/..."
---
```

### Post Content Conventions

#### Default Values

When creating or updating posts, use these defaults unless the user specifies otherwise:

| Field | Default Value | Notes |
|-------|---------------|-------|
| `zoom_id` | `"863 0404 9478"` | 默认 Zoom 会议号 |
| `time` | `"20:00-21:00"` | 默认报告时间 |

#### Title Convention

- **Frontmatter `title`**: 保持原文标题（英文论文保持英文，中文论文保持中文），不做翻译
- **正文第一行 `# 标题`**: 翻译为中文，便于中文读者理解报告主题

Example:
```yaml
---
title: "Simulation-Based Evidence Accumulation Modeling: The eam Package"
---
```
```markdown
# 面向单响应与多响应任务的基于模拟的证据积累建模：eam 包
```

### Naming Conventions

- **Post filenames**: `YYYY-MM-DD-topic-slug.md` (lowercase, hyphenated)
- **Images**: `/assets/images/speakers/YYYY-MM-DD_initials.png`
- **Layout files**: `lowercase-with-hyphens.html`
- **Variables in templates**: `lowercase_with_underscores`

### Liquid Template Guidelines

#### DO's
```liquid
<!-- Use relative_url for links -->
<a href="{{ '/schedule/' | relative_url }}">日程</a>

<!-- Use for + if pattern (where_exp has limitations) -->
{% for post in site.posts %}
  {% if post.status == 'plan' %}
    {{ post.title }}
  {% endif %}
{% endfor %}

<!-- Access frontmatter variables -->
{{ page.title }}
{{ post.speaker }}
```

#### DON'Ts
```liquid
<!-- DON'T use complex where_exp conditions (Jekyll 3.10 limitation) -->
{% assign posts = site.posts | where_exp: "post", "post.status == 'a'" %}

<!-- DON'T use recursive glob patterns in exclude -->
exclude:
  - "*.md"  # This excludes ALL .md files recursively!
```

### Jekyll Configuration Rules

#### Exclude Patterns (CRITICAL)
- **Use absolute paths** for files: `"/README.md"` (NOT `"*.md"`)
- **Directory excludes** are recursive by default: `templates/`
- **Never use** `"*.md"` - it excludes `_posts/*.md` too!

```yaml
# CORRECT
exclude:
  - templates/
  - "/README.md"
  - "/task_plan.md"

# WRONG - excludes _posts/*.md too!
exclude:
  - "*.md"
```

### Error Handling

#### Common Issues & Solutions

1. **Posts not showing**: Check `limit_posts` in `_config.yml` (default: 100)
2. **EntryFilter excluded**: Check `exclude` patterns in `_config.yml`
3. **Liquid syntax error**: Don't use complex `where_exp` with `or` conditions
4. **Image not loading**: Use leading slash `/assets/images/...`

### Content Migration Guidelines

When migrating from Notion (`Private & Shared/DDM Club/`):

1. **Schedule entries** → `_posts/` (already done: 24 posts)
2. **Papers** → `_posts/` with `category: paper` (67 files pending)
3. **Discussions** → `_posts/` with `category: discussion` (26 files pending)

#### Migration Checklist
- [ ] Add proper frontmatter with date
- [ ] Convert Notion links to local paths
- [ ] Move images to `/assets/images/`
- [ ] Update status: `plan` / `in-progress` / `done`
- [ ] Test build locally if possible

## Post Lifecycle & Management

### Status Workflow

Posts follow a three-stage lifecycle:

```
plan → in-progress → done
```

| Status | Meaning | When to Use |
|--------|---------|-------------|
| `plan` | 计划中 | 新报告刚确定日期，但 speaker/host/Zoom 等详情尚未确认。可全部填 TBD |
| `in-progress` | 进行中 | 详情已确认（speaker/host/Zoom），等待报告日期到来 |
| `done` | 已完成 | 报告已结束。更新录屏链接、bilibili 链接，`recording: true` |

### Creating a New Post

**From speaker info document（推荐）**：

> 优先使用 `ddmjc-talk-post` skill（`.agents/skills/ddmjc-talk-post/SKILL.md`）自动完成本节全部流程；以下字段映射为其依据。

当报告人提交了 `*_Speaker_Informance.md`（或 `.docx`）格式的信息文件时，从中提取以下字段：

| 信息来源 | 对应 Frontmatter | 对应正文区域 |
|----------|-----------------|-------------|
| Speaker's name & affiliation | `speaker`, `institution` | 分享嘉宾（bio 作为简介） |
| Title | `title`, `short_title` | 报告标题 |
| Abstract | — | 报告简介 |
| Date/time & length | `date`, `time` | 报告时间 |
| Language | `language` | 报告语言 |
| Reference (APA) | `links.paper` | 参考文献 |
| Record/Open/Share slides | `recording` | 其他（录屏/幻灯片） |
| Profile photo | `speaker_image` | 复制到 `/assets/images/speakers/` |

**从空模板创建**：
当仅有日期和主题，尚无详情时，使用 `templates/schedule-entry-template.md` 创建，关键字段填 TBD，`status: plan`。

### Accepted Input Materials

AI agent can accept the following types of materials to create or update posts:

1. **`*_Speaker_Informance.md` / `*_Speaker_Informance.docx`** — 结构化报告人信息文件，包含所有必要字段。`.docx` 版投递至 `for_administrators/speaker_info/`，**必须走 ddmjc-talk-post skill 三阶段流水线**（见顶部 SKILLS 节：解析 → 生成 post → 完结上一篇）
2. **图片文件** (`.png`, `.jpeg`) — 报告人照片，复制到 `/assets/images/speakers/YYYY-MM-DD_initials.png`
3. **口头/文字描述** — 用户直接提供日期、主题、speaker 等关键信息
4. **PDF/论文链接** — 补充 `links.paper` 和参考文献

### Updating an Existing Post

When new information arrives for an existing `plan` or `in-progress` post:

1. **补充 TBD 字段**：更新 speaker/host/Zoom ID/time 等
2. **升级状态**：`plan` → `in-progress`（详情确认后），`in-progress` → `done`（报告结束后）
3. **添加链接**：报告结束后补充 `links.bilibili` / `links.slides`
4. **更新 recording**：报告结束后设为 `true`
5. **更新 speaker_image**：收到照片后复制到 assets 并更新路径

### Batch Status Update Pattern

When updating multiple historical posts to `done`:
- Insert `status: done` on the line immediately after `recording:` in each post's frontmatter
- Avoid adding `status: done` to posts that are genuinely still `plan` or `in-progress`

### Quick Reference: Create vs Update

| 场景 | 操作 |
|------|------|
| 新报告，有完整 speaker info 文件 | `write_to_file` 创建新 post，`status: in-progress` |
| 新报告，只知道日期/主题 | `write_to_file` 创建新 post，`status: plan`，其余填 TBD |
| 已有 plan post，收到了 speaker info | 更新现有 post 的 TBD 字段，状态改为 `in-progress` |
| 报告已结束 | 更新现有 post，补充录屏链接，状态改为 `done` |

## Committee Member Management

组委会成员数据存储在 `_config.yml` 的 `team` 数组中，渲染在 `index.html` 首页。

### Data Structure

```yaml
team:
  - name: "成员姓名"
    institution: "机构名称 (学位/身份)"
    role: "组织者"  # 组织者 / 指导老师
```

| 字段 | 说明 |
|------|------|
| `name` | 成员中文姓名 |
| `institution` | 当前所属机构及身份，格式为 `"机构名 (学位)"`，如 `"南京师范大学 (博士研究生)"`、`"中国科学院心理研究所 (博士)"` |
| `role` | `"组织者"`（日常运营成员）或 `"指导老师"`（导师/顾问） |

### Adding a New Member

当用户提供新成员信息时：

1. **确定 role**：
   - 在读研究生（硕士/博士）→ `"组织者"`
   - 已获博士学位、在职研究人员 → 询问用户意向，默认为 `"组织者"`
   - 明确标注为"指导老师"的导师 → `"指导老师"`
2. **格式化 institution**：从用户描述中提取当前机构和最高学位，如 `"中科院心理所"` → `"中国科学院心理研究所 (博士)"`
3. **插入位置**：新 `"组织者"` 插入在现有组织者列表末尾、指导老师之前；新 `"指导老师"` 插入在指导老师列表末尾
4. **修改文件**（共 3 个文件，必须全部同步）：

   | 文件 | 内容 | 说明 |
   |------|------|------|
   | `_config.yml` | `team` 数组 | 网站数据源 |
   | `README.md` | Organizing Committee 表格 | 英文 README，使用英文名和英文机构名 |
   | `README_CH.md` | 组委会成员 表格 | 中文 README，使用中文名和中文机构名 |

5. **注意**：`README_zh.md` 是旧版 README，不含组委会名单，无需更新

### Updating an Existing Member

当成员的机构或角色发生变化时：
- 同步更新 `_config.yml`、`README.md`、`README_CH.md` 三个文件中对应成员的信息
- 例如：博士研究生毕业入职 → 更新 institution，role 可能从 `"组织者"` 改为 `"指导老师"`

### Display

成员通过 `index.html` 中的 Liquid 模板渲染：

```liquid
{% for member in site.team %}
<div class="team-card">
  <div class="team-avatar">{{ member.name | slice: 0, 1 }}</div>
  <div class="team-info">
    <h4>{{ member.name }}</h4>
    <p>{{ member.institution }}</p>
    <span class="team-role">{{ member.role }}</span>
  </div>
</div>
{% endfor %}
```

- 头像自动取姓名首字，无需上传图片
- CSS 样式在 `assets/css/style.css` 中 `.team-*` 相关规则

## Testing

### Pre-deployment Checklist
1. Verify `_config.yml` syntax is valid YAML
2. Check no `"*.md"` patterns in `exclude`
3. Confirm all post filenames match `YYYY-MM-DD-*.md`
4. Verify frontmatter in all posts
5. Build passes in GitHub Actions

### Post-deployment Verification
1. Check https://ddmjournalclub.github.io/DDM_Journal_Club/ loads
2. Verify schedule page shows posts
3. Test navigation links
4. Check images load correctly

## Key Technical Constraints

- **Jekyll version**: 3.10.0 (GitHub Pages)
- **where_exp limitation**: No complex `or` conditions
- **exclude behavior**: Recursive by default
- **Post limit**: `limit_posts: 100` (configure in `_config.yml`)
- **URL structure**: `/:year-:month-:day-:slug/` (permalink setting)

## References

- Jekyll docs: https://jekyllrb.com/docs/
- GitHub Pages: https://docs.github.com/en/pages
- Liquid docs: https://shopify.github.io/liquid/

<!-- proj-tracker:begin v2 -->
## proj-tracker（ARA trace 维护）

- 本项目 action state 由 `proj-tracker` 维护，canonical 载体为本地 ARA trace：
  - `trace/status.json` — 当前 focus / TODO / blockers（脚本读写，勿手改）
  - `trace/decisions/Dxxx_*.md` — 重大决策记录（低频、不可变，ARA 格式）
  - `trace/research-dag.yaml` — 决策链 DAG（nodes 列表保持在文件末尾）
- Resume / 总结时由 trace 渲染人类可读报告（md 默认 / html 按需）；渲染产物为派生文件，勿手改。
- **严格禁止私自 git commit / push**：Track 只写文件，提交由用户手动完成。
- Project HEAD 权威存于中央 `project-heads.json`（head.py 读写）；`ara.yaml` 的 `head_focus` 仅为本地缓存。
- 嵌套子项目各自的 ara.yaml / trace 由 `ara-research-structure` 处理结构，`proj-tracker` 只写对应层的 trace。
<!-- proj-tracker:end -->
