#!/usr/bin/env python3
"""Stage 2: Render a confirmed fields.json into a DDMJC schedule post.

Pure stdlib. Deterministic rendering — all semantic content (Chinese title,
slug, tags, host, chosen photo) must already be decided in fields.json.

Input : fields.json  (agent-reviewed version of fields_raw.json)
Output: _posts/YYYY-MM-DD-<slug>.md
        assets/images/speakers/YYYY-MM-DD_<name>.<ext>  (if photo provided)

Usage:
    python build_post.py <fields.json> [--posts-dir _posts] [--assets-dir assets]
                        [--dry-run] [--force]

Exit codes: 0 ok / 1 validation error / 2 fatal.
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

DEFAULT_ZOOM = "863 0404 9478"
DEFAULT_TIME = "20:00-21:00"
REQUIRED = ["date", "slug", "title", "title_zh", "speaker", "language"]
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def fail(msg: str, code: int = 1):
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(code)


def yaml_str(v: str) -> str:
    """Render a Python string as a double-quoted YAML scalar."""
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def load_fields(path: Path) -> dict:
    if not path.exists():
        fail(f"fields.json 不存在: {path}", 2)
    try:
        f = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"fields.json 不是合法 JSON: {e}", 2)
    return f


def validate(f: dict) -> list[str]:
    errs = []
    for k in REQUIRED:
        if not f.get(k):
            errs.append(f"缺少必填字段: {k}")
    if f.get("date") and not DATE_RE.match(f["date"]):
        errs.append(f"date 格式应为 YYYY-MM-DD: {f['date']}")
    if f.get("slug") and not SLUG_RE.match(f["slug"]):
        errs.append(f"slug 只能含小写字母/数字/连字符: {f['slug']}")
    st = f.get("short_title")
    if st and len(st) > 20:
        errs.append(f"short_title 超过 20 字: {st} ({len(st)} 字)")
    return errs


def frontmatter(f: dict, speaker_image: str | None) -> str:
    zoom = f.get("zoom_id", DEFAULT_ZOOM)
    time_ = f.get("time", DEFAULT_TIME)
    tags = f.get("tags") or ["DDM"]
    lines = [
        "---",
        f"title: {yaml_str(f['title'])}",
        f"short_title: {yaml_str(f.get('short_title') or f['title'])}",
        f"speaker: {yaml_str(f['speaker'])}",
        f"institution: {yaml_str(f.get('institution') or 'TBD')}",
        f"host: {yaml_str(f.get('host') or 'TBD')}",
        f"date: {yaml_str(f['date'])}",
        f"time: {yaml_str(time_)}",
        'timezone: "北京时间 [GMT+8]"',
        f"zoom_id: {yaml_str(zoom)}",
        f"language: {yaml_str(f['language'])}",
        "tags:",
    ]
    lines += [f"  - {yaml_str(t)}" for t in tags]
    recording = (f.get("record") == "Yes" and f.get("open_recording") == "Yes")
    lines.append(f"recording: {'true' if recording else 'false'}")
    lines.append("status: in-progress")
    if speaker_image:
        lines.append(f"speaker_image: {yaml_str(speaker_image)}")
    links = []
    if f.get("paper_link"):
        links.append(f"  paper: {yaml_str(f['paper_link'])}")
    if f.get("bilibili_link"):
        links.append(f"  bilibili: {yaml_str(f['bilibili_link'])}")
    if links:
        lines.append("links:")
        lines += links
    lines.append("---")
    return "\n".join(lines)


def body(f: dict) -> str:
    d = f["date"]
    date_cn = f"{d[0:4]}年{int(d[5:7]):02d}月{int(d[8:10]):02d}日"
    time_tilde = (f.get("time", DEFAULT_TIME)).replace("-", "~")
    host = f.get("host") or "TBD"

    bio_lines = [f"**{f['speaker']}**  "]
    if f.get("institution"):
        bio_lines.append(f"{f['institution']}  ")
    if f.get("bio"):
        bio_lines.append(f"{f['bio']}")

    refs = f.get("reference") or []
    ref_block = "\n".join(f"- {r}" for r in refs) if refs else "- TBD"

    rec = (f.get("record") == "Yes" and f.get("open_recording") == "Yes")
    other = [
        f"- [{'x' if rec else ' '}] 录屏"
        + ("（允许录制并公开）" if rec else "（未获许可或未确认）"),
        f"- [{'x' if f.get('share_slides') == 'Yes' else ' '}] 幻灯片",
    ]

    parts = [
        f"# {f['title_zh']}",
        "",
        f"主持人: {host}",
        "",
        "---",
        "",
        "## 分享嘉宾",
        "",
        "\n".join(bio_lines),
        "",
        "---",
        "",
        "## 报告简介",
        "",
        f.get("abstract") or "TBD",
        "",
        "---",
        "",
        "## 报告时间",
        "",
        f"北京时间 [GMT+8] {date_cn} {time_tilde}",
        "",
        f"**会议信息：** ZOOM 会议号：{f.get('zoom_id', DEFAULT_ZOOM)}",
        "",
        f"**报告语言：** {f['language']}",
        "",
        f"**主持人：** {host}",
        "",
        "---",
        "",
        "## 参考文献",
        "",
        ref_block,
        "",
        "---",
        "",
        "## 其他",
        "",
        "\n".join(other),
        "",
        "---",
        "",
        "## 所属小组",
        "",
        "**DDMJC 主页**: https://ddmjournalclub.github.io",
        "",
        "**DDM Bilibili 主页**: https://space.bilibili.com/3461571806235136",
        "",
    ]
    return "\n".join(parts)


def handle_photo(f: dict, fields_path: Path, assets_dir: Path, dry: bool):
    """Copy photo into assets/images/speakers/. Returns final web path or None."""
    src_rel = f.get("speaker_image_source")
    if not src_rel:
        return None
    src = Path(src_rel)
    if not src.is_absolute():
        cand = fields_path.parent / src_rel
        src = cand if cand.exists() else Path(src_rel)
    if not src.exists():
        print(f"[WARN] 照片源文件不存在，跳过: {src_rel}")
        return None
    ext = src.suffix.lower() or ".png"
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", f.get("speaker_image_name")
                  or f["speaker"]).strip("_") or "speaker"
    fname = f"{f['date']}_{name}{ext}"
    dest = assets_dir / "images" / "speakers" / fname
    if not dry:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    return f"/assets/images/speakers/{fname}"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fields", type=Path)
    ap.add_argument("--posts-dir", type=Path, default=Path("_posts"))
    ap.add_argument("--assets-dir", type=Path, default=Path("assets"))
    ap.add_argument("--dry-run", action="store_true",
                    help="只打印将要写入的文件与内容，不落盘")
    ap.add_argument("--force", action="store_true",
                    help="覆盖已存在的同名 post")
    args = ap.parse_args()

    f = load_fields(args.fields)
    errs = validate(f)
    if errs:
        for e in errs:
            print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    fname = f"{f['date']}-{f['slug']}.md"
    post_path = args.posts_dir / fname
    if post_path.exists() and not args.force:
        fail(f"post 已存在（用 --force 覆盖）: {post_path}")

    speaker_image = handle_photo(f, args.fields, args.assets_dir, args.dry_run)
    if not f.get("host") or f.get("host") == "TBD":
        print("[WARN] host 未填写，已写为 TBD——发布前请人工确认主持人")

    content = frontmatter(f, speaker_image) + "\n\n" + body(f)

    if args.dry_run:
        print(f"[DRY-RUN] 将写入: {post_path}")
        if speaker_image:
            print(f"[DRY-RUN] 将复制照片 -> {args.assets_dir}/images/speakers/")
        print("=" * 60)
        print(content)
        return

    args.posts_dir.mkdir(parents=True, exist_ok=True)
    post_path.write_text(content, encoding="utf-8", newline="\n")
    print(f"[OK] post 已生成: {post_path}")
    if speaker_image:
        print(f"[OK] 照片已复制 -> {args.assets_dir}/images/speakers/")
    print("下一步: 运行 close_previous.py 完结上一篇 post")


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
