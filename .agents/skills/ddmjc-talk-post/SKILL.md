---
name: ddmjc-talk-post
description: >-
  DDMJC 新一期报告发布流水线：从 *_Speaker_Informance.docx（投递至
  for_administrators/speaker_info/）自动解析报告人信息、生成 _posts/ 日程 post、
  并将上一篇 post 完结为 done。三阶段全自动（解析 → 生成 → 状态更新）。
  触发词：收到 Speaker_Informance docx、新一期报告、新报告上线、完结上一篇、
  更新报告状态。
---

# ddmjc-talk-post — 新一期报告三阶段发布流水线

**用途**：报告人提交 `*_Speaker_Informance.docx` 后，一条龙完成
**① docx 解析 → ② 生成 post → ③ 完结上一篇**，产出 `_posts/YYYY-MM-DD-<slug>.md`（`status: in-progress`）并把上一篇翻为 `done`。

**用户已确认的运行策略（2026-10-08）**：
- 三阶段**全自动**，中途不停顿确认，跑完统一汇报
- 完结上一篇时缺录屏/bilibili 链接 → **只警告不阻断**（链接通常报告后数天才补）

## 硬约束（不可违反）

1. **绝不自动 `git commit` / `git push`**——本项目 proj-tracker 规则：AI 只写文件，
   提交由用户手动完成（push 到 main 才触发 GitHub Pages 部署）
2. 脚本全部**纯 Python stdlib**，无需 venv、无第三方依赖
3. 中间产物落在 `_speaker_intake/`（Jekyll 自动忽略下划线目录，不进 build）

## 输入约定

| 输入 | 位置 | 说明 |
|------|------|------|
| docx（标准入口） | `for_administrators/speaker_info/` | 报告人填好的 `DDMJC_Speaker_Informance` 模板 |
| 空模板参考 | `for_administrators/DDMJC_Speaker_Informance.docx` | 字段标签的唯一权威来源 |
| 其他 | 口头描述 / `*_Speaker_Informance.md` | 跳过阶段①，agent 直接手写 fields.json |

## 三阶段工作流

### 阶段① docx 解析

```bash
python .agents/skills/ddmjc-talk-post/scripts/parse_speaker_docx.py \
    "for_administrators/speaker_info/<文件>.docx"
# 默认输出 _speaker_intake/<docx名>/ ：raw.md + fields_raw.json + media/
# （agent 确定 slug 后须将目录重命名为 _speaker_intake/<解析日期>-<slug>/，见下）
```

脚本按模板固定标签（Speaker's name / Title / Abstract / Date / Language /
Reference / Record-Open-Share）做状态机解析，产出 `fields_raw.json`。

**agent 复核补全**（脚本无法完成的部分），另存为同目录 `fields.json`：

| 字段 | agent 必做 |
|------|-----------|
| `title_zh` | 把原文标题译成中文（正文 h1 用；frontmatter title 保持原文） |
| `short_title` | ≤20 字简短标题 |
| `slug` | 小写连字符文件名片段（如 `hierarchical-drift-model`） |
| `tags` | 3–5 个领域标签 |
| `host` | 主持人（勿留 TBD） |
| `speaker_image_source` | 从 media/ 中挑出真正的报告人照片（模板 logo、示意图除外） |
| `speaker_image_name` | **作者名字**（拼音全名，如 `zhuruida`；照片落盘为 `报告日期_作者名.<ext>`） |

**intake 目录重命名（必做）**：确定 slug 后，把阶段①的 intake 目录重命名为
`_speaker_intake/<解析当日 YYYY-MM-DD>-<slug>/`（如 `2026-10-09-moral-perceptual-conflict/`），
使提取产物可按「收到日期-主题」追溯；`fields.json` 内均为相对路径，重命名后无需改引用。

### 清洗检查（报告人常见填写问题）

- **方括号残留**：报告人常把模板的 `[ ]` 一起抄进答案（title/abstract/language/reference
  出现 `[中文]`、`[Moral and...]`），复核时须剥掉外层方括号
- **姓名单位分隔符**：可能用空格而非逗号（`朱睿达 中山大学心理学系`），此时 institution
  会 MISS，agent 手工拆分
- **录屏三连答案**：若 Record/Open 全 No 导致 `recording: false`，**发布前向用户确认**
  是否为报告人真实意图（2026-10-09 朱睿达场次的 No 是笔误，已由用户改判为 Yes）

### 阶段② 生成 post

```bash
python .agents/skills/ddmjc-talk-post/scripts/build_post.py \
    _speaker_intake/<目录>/fields.json
# 校验必填字段/日期格式/slug 规范/文件名冲突，写 _posts/YYYY-MM-DD-<slug>.md
# 照片自动复制到 assets/images/speakers/YYYY-MM-DD_<name>.<ext>
```

frontmatter 遵循项目规范（AGENTS.md Frontmatter Standards）：默认
`zoom_id: "863 0404 9478"`、`time: "20:00-21:00"`、`status: in-progress`；
`recording` 由 Record+Open 两个 Yes/No 共同决定。

### 阶段③ 完结上一篇

```bash
python .agents/skills/ddmjc-talk-post/scripts/close_previous.py <YYYY-MM-DD>
# 或 --new-post _posts/YYYY-MM-DD-<slug>.md
# 将 date < 新日期 且 status != done 的 post 翻为 done（按 AGENTS.md
# 批量模式：status 行插在 recording: 之后）；缺 bilibili 链接只警告
```

### Bilibili 链接回填（阶段③附属步骤，新 post 产生时必查）

旧 post 翻为 done 时，若其 `recording: true`（当初承诺录屏并上传）但 `links.bilibili` 缺失：

1. **agent 先自行检索** DDMJC B 站主页（`https://space.bilibili.com/3461571806235136`），
   按报告人姓名 / 报告标题关键词在视频列表与系列合集中找对应投稿；
   可用 browser skill（Edge CDP, session `edbr`）访问。找到 → 回填 `links.bilibili` 并告知用户。
2. **找不到 → 提醒用户提供 URL**，不阻断（链接可后续补）。
3. 旧 post `recording: false`（本就不录屏）→ 跳过，无需回填。

### 收尾汇报（agent 输出给用户）

跑完三阶段后统一汇报：生成/修改的文件清单、字段核对表、警告项
（缺链接等）、**提醒用户手动 git commit + push 触发部署**。

## fields.json schema

```json
{
  "date": "YYYY-MM-DD", "slug": "lower-hyphen", "title": "原文标题",
  "title_zh": "中文标题", "short_title": "≤20字", "speaker": "姓名",
  "institution": "单位", "bio": "报告人简介", "host": "主持人",
  "time": "20:00-21:00", "language": "中文",
  "tags": ["tag1"], "abstract": "报告简介",
  "reference": ["APA 格式参考文献行"],
  "paper_link": "https://doi.org/...", "bilibili_link": null,
  "record": "Yes", "open_recording": "Yes", "share_slides": "No",
  "speaker_image_source": "media/image2.png", "speaker_image_name": "zhangsan"
}
```

## 故障排查

| 症状 | 处置 |
|------|------|
| fields_raw.json 大面积 MISS | docx 是空模板（`[Speaker to fill]` 未填）→ 退回用户找报告人补填 |
| 标签解析错位 | 查看同目录 raw.md 对照模板原文，agent 手工修正 fields.json |
| 报告人没走模板（自由格式 docx） | 阶段①照跑拿全文，agent 直接读 raw.md 手写 fields.json |
| post 文件名冲突 | 确认是否同一报告；是则 `--force` 覆盖，否则改 slug |

## 维护

- 脚本：`scripts/parse_speaker_docx.py` / `build_post.py` / `close_previous.py`
- 模板标签若变更（发新模板给报告人），需同步更新 parse 的 `LABELS` 表
- 相关项目规范：AGENTS.md「Post Lifecycle & Management」节
