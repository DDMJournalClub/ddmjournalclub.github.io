#!/usr/bin/env python3
"""Stage 3: Close previous posts — flip the last talk to `done` when a new one is scheduled.

Pure stdlib. Non-blocking by design: missing bilibili / recording links only
produce warnings (links usually arrive days after the talk).

Logic:
  1. Scan --posts-dir/*.md, read date (from filename) + status (frontmatter).
  2. Any post with date < NEW_DATE and status != done  ->  status: done.
     Status line is replaced in place; if absent it is inserted immediately
     after `recording:` (fallback: after `language:`; last resort: before the
     closing `---`), per AGENTS.md Batch Status Update Pattern.
  3. Warn (never block) if a closed post lacks a bilibili link or recording.
  4. Report any remaining plan / in-progress posts (should be the new one only).

Usage:
    python close_previous.py <NEW_DATE YYYY-MM-DD | --new-post _posts/xxxx.md>
                            [--posts-dir _posts] [--dry-run]

Exit codes: 0 ok (warnings possible) / 1 usage error / 2 fatal.
"""
import argparse
import re
import sys
from pathlib import Path

DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def parse_frontmatter(text: str):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return None, None
    block, rest = m.group(1), text[m.end():]
    return block, rest


def get_status(fm: str):
    m = re.search(r"^status:\s*(\S+)\s*$", fm, re.M)
    return m.group(1) if m else None


def set_status(text: str, new: str = "done") -> str:
    """Return text with status flipped. Insert position per AGENTS.md.
    Preserves the original line endings (CRLF/LF)."""
    crlf = "\r\n" in text
    if re.search(r"^status:\s*\S+\s*$", text, re.M):
        # only rewrite the value on that line; keep surrounding bytes intact
        return re.sub(r"^(\s*status:\s*)\S+(\s*)$", rf"\g<1>{new}\g<2>",
                      text, count=1, flags=re.M)
    ins = f"status: {new}\r" if crlf else f"status: {new}"
    lines = text.split("\n")
    anchor_idx = None
    for i, ln in enumerate(lines):
        if re.match(r"^recording:", ln):
            anchor_idx = i
            break
    if anchor_idx is None:
        for i, ln in enumerate(lines):
            if re.match(r"^language:", ln):
                anchor_idx = i
                break
    if anchor_idx is not None:
        lines.insert(anchor_idx + 1, ins)
        return "\n".join(lines)
    # last resort: before the closing --- of frontmatter
    for i, ln in enumerate(lines):
        if i > 0 and ln.strip() == "---":
            lines.insert(i, ins)
            return "\n".join(lines)
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("new", nargs="?", default=None,
                    help="新报告日期 YYYY-MM-DD，或 --new-post 指定的 post 文件路径")
    ap.add_argument("--new-post", type=Path, default=None,
                    help="新 post 文件路径（从文件名取日期）")
    ap.add_argument("--posts-dir", type=Path, default=Path("_posts"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    new_date = None
    if args.new_post:
        m = DATE_RE.match(args.new_post.name)
        if not m:
            fail(f"无法从文件名解析日期: {args.new_post.name}")
        new_date = m.group(1)
    elif args.new:
        m = DATE_RE.match(args.new.strip())
        if not m:
            fail(f"日期格式应为 YYYY-MM-DD: {args.new}")
        new_date = m.group(1)
    else:
        fail("必须提供新报告日期 YYYY-MM-DD 或 --new-post <file>")

    posts = sorted(args.posts_dir.glob("*.md"))
    if not posts:
        fail(f"posts 目录为空或不存在: {args.posts_dir}", 2)

    closed, warnings, remaining = [], [], []
    for p in posts:
        m = DATE_RE.match(p.name)
        if not m:
            continue
        d = m.group(1)
        # newline='' -> 不做换行符转换，保留原文件行尾
        text = p.read_text(encoding="utf-8", newline="")
        fm, _ = parse_frontmatter(text)
        if fm is None:
            warnings.append(f"[WARN] {p.name}: 无 frontmatter，跳过")
            continue
        st = get_status(fm) or "plan"
        if d < new_date and st != "done":
            if not args.dry_run:
                p.write_text(set_status(text, "done"),
                             encoding="utf-8", newline="")
            closed.append((p.name, st))
            if "bilibili" not in fm and not re.search(r"^recording:\s*false", fm, re.M):
                warnings.append(
                    f"[TODO] {p.name}: 已完结且承诺录屏但缺 bilibili 链接——"
                    f"agent 先到 https://space.bilibili.com/3461571806235136 检索回填，"
                    f"找不到再提醒用户提供 URL")
            if re.search(r"^recording:\s*false", fm, re.M):
                warnings.append(f"[WARN] {p.name}: recording: false（无录屏或未公开）")
        elif d >= new_date and st != "done":
            remaining.append((p.name, st))

    tag = "[DRY-RUN] " if args.dry_run else ""
    print(f"{tag}基准日期（新报告）: {new_date}\n")
    if closed:
        print(f"{tag}已翻为 done（{len(closed)} 篇）:")
        for name, old in closed:
            print(f"  - {name}: {old} -> done")
    else:
        print(f"{tag}无需完结的 post（早于 {new_date} 且未 done 的不存在）")
    if remaining:
        print(f"\n仍处于筹备中的 post（应只剩新报告）:")
        for name, st in remaining:
            print(f"  - {name}: {st}")
    if warnings:
        print("\n" + "\n".join(warnings))
        print("\n（警告不阻断：录屏链接通常在报告结束数天后才可补）")


def fail(msg: str, code: int = 1):
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(code)


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
