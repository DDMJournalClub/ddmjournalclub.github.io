#!/usr/bin/env python3
"""Stage 1: Parse DDMJC *_Speaker_Informance.docx -> structured fields_raw.json.

Pure stdlib (zipfile + ElementTree). No external dependencies.

Input : a filled DDMJC Speaker_Informance docx (template: for_administrators/DDMJC_Speaker_Informance.docx)
Output: <outdir>/raw.md            flattened text of the document
        <outdir>/fields_raw.json   best-effort structured fields (agent must review & complete)
        <outdir>/media/            all embedded images from word/media/

Usage:
    python parse_speaker_docx.py <input.docx> [-o OUTDIR]

Default OUTDIR: _speaker_intake/<docx-stem>/ (auto-suffix -2, -3 ... on collision)
Exit codes: 0 ok (with possible warnings) / 2 fatal (not a docx, unreadable).
"""
import argparse
import json
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
PLACEHOLDER = "[speaker to fill]"


# ---------------------------------------------------------------- extraction

def docx_lines(docx: Path) -> list[str]:
    """Text lines in document order; tables flattened to 'cell | cell' rows."""
    with zipfile.ZipFile(docx) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    body = root.find(f"{W}body")
    if body is None:
        return []

    def para_text(p) -> str:
        return "".join(t.text or "" for t in p.iter(f"{W}t")).strip()

    lines: list[str] = []

    def walk(el):
        for child in el:
            if child.tag == f"{W}p":
                lines.append(para_text(child))
            elif child.tag == f"{W}tbl":
                for tr in child.findall(f"{W}tr"):
                    cells = []
                    for tc in tr.findall(f"{W}tc"):
                        ps = [para_text(p) for p in tc.iter(f"{W}p")]
                        cells.append(" / ".join(x for x in ps if x))
                    lines.append(" | ".join(cells))
                lines.append("")
            else:
                walk(child)

    walk(body)
    return lines


def extract_media(docx: Path, outdir: Path) -> list[str]:
    """Copy word/media/* into OUTDIR/media/. Return relative paths."""
    media_dir = outdir / "media"
    copied = []
    with zipfile.ZipFile(docx) as z:
        for name in z.namelist():
            if name.startswith("word/media/") and not name.endswith("/"):
                media_dir.mkdir(parents=True, exist_ok=True)
                target = media_dir / Path(name).name
                target.write_bytes(z.read(name))
                copied.append(f"media/{target.name}")
    return copied


# ---------------------------------------------------------------- label map

# (normalized-prefix match, target key). Order matters only for readability.
LABELS: list[tuple[str, str]] = [
    ("about the speaker", "_sec"),
    ("about the talk", "_sec"),
    ("other questions", "_sec"),
    ("profile photo", "_skip"),
    ("speaker's name", "name_aff"),
    ("a brief bio", "bio"),
    ("title (", "title"),
    ("abstract (", "abstract"),
    ("date/time", "datetime"),
    ("language (", "language"),
    ("reference", "reference"),
    ("can we record", "_skip"),
    ("record the talk", "_yn_record"),
    ("open the recording", "_yn_open"),
    ("share the slides", "_yn_share"),
]


def norm(s: str) -> str:
    return s.replace("\u2019", "'").replace("\u2018", "'").strip().lower()


def classify(line: str):
    n = norm(line)
    for prefix, key in LABELS:
        if n.startswith(prefix):
            return key
    return None


# ---------------------------------------------------------------- field parse

DATE_PATTERNS = [
    (re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})"), "iso"),
    (re.compile(r"(\d{4})\s*[年\.]\s*(\d{1,2})\s*[月\.]\s*(\d{1,2})\s*日?"), "cn"),
    (re.compile(r"(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})"), "us"),
]
URL_RE = re.compile(r"https?://[^\s\)\]，。；]+")


def parse_date(text: str) -> str | None:
    for rx, kind in DATE_PATTERNS:
        m = rx.search(text)
        if m:
            if kind == "us":
                mm, dd, yy = m.groups()
                return f"{yy}-{int(mm):02d}-{int(dd):02d}"
            y, m_, d = m.groups()
            return f"{int(y):04d}-{int(m_):02d}-{int(d):02d}"
    return None


def split_name_aff(raw: str) -> tuple[str | None, str | None]:
    """'张三, 北京师范大学' -> speaker, institution (best effort)."""
    raw = raw.strip().strip("；;")
    if not raw:
        return None, None
    m = re.split(r"[，,]", raw, maxsplit=1)
    if len(m) == 2 and m[1].strip():
        return m[0].strip(), m[1].strip()
    return raw, None


def parse_yesno(line: str) -> str | None:
    n = norm(line)
    for val in ("yes", "no"):
        if re.search(rf"\b{val}\b", n):
            return "Yes" if val == "yes" else "No"
    # 中文回答
    if "是" in n or "允许" in n:
        return "Yes"
    if "否" in n or "不" in n:
        return "No"
    return None


def map_fields(lines: list[str]) -> dict:
    fields: dict = {
        "date": None, "title": None, "title_zh": None, "short_title": None,
        "slug": None, "speaker": None, "institution": None, "bio": None,
        "abstract": None, "language": None, "time": "20:00-21:00",
        "reference": [], "paper_link": None,
        "record": None, "open_recording": None, "share_slides": None,
        "speaker_image_source": None, "host": None,
    }
    warnings: list[str] = []
    current: str | None = None      # active capture key
    buf: list[str] = []

    def flush():
        nonlocal current, buf
        if current and buf:
            val = "\n".join(buf).strip()
            if current == "datetime":
                d = parse_date(val)
                if d:
                    fields["date"] = d
            elif current == "name_aff":
                sp, inst = split_name_aff(val)
                fields["speaker"], fields["institution"] = sp, inst
            elif current == "reference":
                fields["reference"] = [l for l in buf if l.strip()]
            elif current in fields and fields[current] is None:
                fields[current] = val
        current, buf = None, []

    for line in lines:
        if not line.strip():
            continue
        key = classify(line)
        if key == "_skip":
            continue
        if key == "_sec":
            flush()
            continue
        if key and key.startswith("_yn_"):
            flush()
            target = {"_yn_record": "record", "_yn_open": "open_recording",
                      "_yn_share": "share_slides"}[key]
            ans = parse_yesno(line.split(":", 1)[-1] if ":" in line else line)
            fields[target] = ans
            if ans is None:
                warnings.append(f"无法解析 Yes/No: {line[:60]}")
            continue
        if key:                      # new capture section
            flush()
            current = key
            continue
        # plain value line
        if norm(line) == PLACEHOLDER or norm(line).endswith(PLACEHOLDER):
            continue                 # unfilled placeholder -> stays None
        if current:
            buf.append(line)
    flush()

    # paper link: prefer DOI / osf link found in abstract or reference
    hay = " ".join([fields.get("abstract") or "", " ".join(fields["reference"])])
    urls = URL_RE.findall(hay)
    for u in urls:
        if any(k in u for k in ("doi.org", "osf.io", "psyarxiv")):
            fields["paper_link"] = u.rstrip(".")
            break
    if fields["paper_link"] is None and urls:
        fields["paper_link"] = urls[0].rstrip(".")

    # completeness warnings (agent must fill these)
    for k in ("date", "title", "speaker", "abstract", "language"):
        if not fields.get(k):
            warnings.append(f"字段缺失或未填写: {k}")
    return {**fields, "warnings": warnings}


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("docx", type=Path)
    ap.add_argument("-o", "--outdir", type=Path, default=None,
                    help="默认 _speaker_intake/<stem>/")
    args = ap.parse_args()

    if not args.docx.exists():
        print(f"[FATAL] 文件不存在: {args.docx}", file=sys.stderr)
        sys.exit(2)
    if args.docx.suffix.lower() != ".docx":
        print(f"[FATAL] 不是 .docx 文件: {args.docx}", file=sys.stderr)
        sys.exit(2)

    outdir = args.outdir
    if outdir is None:
        base = Path("_speaker_intake") / args.docx.stem
        outdir, n = base, 2
        while outdir.exists():
            outdir = Path(f"{base}-{n}")
            n += 1
    outdir.mkdir(parents=True, exist_ok=True)

    try:
        lines = docx_lines(args.docx)
    except zipfile.BadZipFile:
        print(f"[FATAL] 不是有效的 docx (zip) 文件: {args.docx}", file=sys.stderr)
        sys.exit(2)

    media = extract_media(args.docx, outdir)
    fields = map_fields(lines)
    fields["source_docx"] = str(args.docx)
    fields["parsed_at"] = datetime.now().isoformat(timespec="seconds")
    fields["media"] = media
    if media:
        fields["speaker_image_source"] = media[0]  # 猜测，agent 复核

    (outdir / "raw.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (outdir / "fields_raw.json").write_text(
        json.dumps(fields, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # report
    def mark(v):
        return "OK " if v not in (None, "", []) else "MISS"
    print(f" intake dir : {outdir}")
    print(f" media files: {len(media)}")
    keys = ["date", "title", "speaker", "institution", "bio", "abstract",
            "language", "reference", "paper_link", "record",
            "open_recording", "share_slides"]
    for k in keys:
        v = fields.get(k)
        shown = (str(v)[:60] + "…") if v and len(str(v)) > 60 else v
        print(f"  [{mark(v)}] {k:16s}: {shown}")
    for w in fields["warnings"]:
        print(f"  [WARN] {w}")
    print("\n下一步: agent 复核 fields_raw.json -> 补全 title_zh/short_title/slug/tags/host"
          " -> 存为同目录 fields.json -> 运行 build_post.py")


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
