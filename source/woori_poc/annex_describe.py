from __future__ import annotations

import json
import re
import zlib
from pathlib import Path

import olefile

from .config import DATA_DIR
from .corpus import clean_text


FSS_DIR = DATA_DIR / "금융감독원_감독규정시행세칙"
PARA_TEXT_TAG = 67


def _record_iter(data: bytes):
    offset = 0
    while offset + 4 <= len(data):
        header = int.from_bytes(data[offset : offset + 4], "little")
        offset += 4
        tag_id = header & 0x3FF
        size = (header >> 20) & 0xFFF
        if size == 0xFFF:
            if offset + 4 > len(data):
                break
            size = int.from_bytes(data[offset : offset + 4], "little")
            offset += 4
        payload = data[offset : offset + size]
        offset += size
        yield tag_id, payload


def extract_hwp_text(path: Path) -> str:
    ole = olefile.OleFileIO(str(path))
    try:
        header = ole.openstream("FileHeader").read()
        compressed = bool(header[36] & 1) if len(header) > 36 else True
        texts: list[str] = []
        section_names = sorted(
            name for name in ole.listdir(streams=True) if len(name) == 2 and name[0] == "BodyText" and name[1].startswith("Section")
        )
        for name in section_names:
            raw = ole.openstream(name).read()
            if compressed:
                try:
                    raw = zlib.decompress(raw, -15)
                except zlib.error:
                    raw = zlib.decompress(raw)
            for tag_id, payload in _record_iter(raw):
                if tag_id != PARA_TEXT_TAG or not payload:
                    continue
                text = payload.decode("utf-16le", errors="ignore")
                text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
                if text.strip():
                    texts.append(text)
        return clean_text("\n".join(texts))
    finally:
        ole.close()


def short_description(label: str, text: str) -> str:
    lines = [clean_text(line) for line in text.splitlines()]
    lines = [line for line in lines if line and not re.fullmatch(r"[-=·\s]+", line)]
    body = " ".join(lines[:8])
    body = re.sub(r"\s+", " ", body).strip()
    if len(body) > 700:
        body = body[:700].rsplit(" ", 1)[0] + "..."
    if not body:
        return f"{label} 원문 파일입니다. HWP 본문 텍스트를 충분히 추출하지 못했습니다."
    return f"{label}의 주요 내용은 다음과 같습니다. {body}"


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, ensure_ascii=False) + "\n")


def update_markdown_index(index_md: Path, rows: list[dict]) -> None:
    if not index_md.exists():
        return
    title = index_md.read_text(encoding="utf-8").split("\n\n", 1)[0]
    lines = [title, ""]
    reg_title = title.lstrip("# ").replace(" 별표/별지", "")
    lines.extend([f"# {reg_title} 별표/별지", ""])
    for row in rows:
        lines.extend([f"## {row['label']}", ""])
        lines.append(f"- 별표/별지ID: {row['byl_seq']}")
        lines.append(f"- 원문: {row['source_url']}")
        if row.get("description"):
            lines.append(f"- 설명: {row['description']}")
        if row.get("text_path"):
            lines.append(f"- 추출본문: {row['text_path']}")
        for file_path in row.get("files", []):
            lines.append(f"- 파일: {file_path}")
        lines.append("")
    index_md.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    if not FSS_DIR.exists():
        raise SystemExit(f"missing directory: {FSS_DIR}")
    top_rows: list[dict] = []
    converted = 0
    failed = 0

    for index_path in sorted(FSS_DIR.glob("kr/*/별표_별지/index.jsonl")):
        reg_dir = index_path.parents[1]
        annex_dir = index_path.parent
        rows = read_jsonl(index_path)
        for row in rows:
            hwp_files = [annex_dir / file_path.split("/", 1)[-1] for file_path in row.get("files", []) if file_path.lower().endswith(".hwp")]
            hwp_files = [path for path in hwp_files if path.exists()]
            if not hwp_files:
                row["description"] = row.get("description") or f"{row['label']} 원본 HWP 파일을 찾지 못했습니다."
                failed += 1
                continue
            hwp_path = hwp_files[0]
            try:
                text = extract_hwp_text(hwp_path)
            except Exception as exc:
                text = ""
                row["description"] = f"{row['label']} 원문 HWP 추출 실패: {type(exc).__name__}"
                failed += 1
            if text:
                md_name = hwp_path.with_suffix(".description.md").name
                rel_text_path = f"별표_별지/{md_name}"
                description = short_description(row["label"], text)
                safe_label = row["label"].replace("'", "''")
                md = [
                    "---",
                    f"제목: '{safe_label}'",
                    "자료유형: '금융감독원 감독규정 시행세칙 별표/별지 추출본문'",
                    f"별표별지ID: '{row['byl_seq']}'",
                    f"원본파일: '{str(hwp_path.relative_to(reg_dir)).replace(chr(92), '/')}'",
                    "---",
                    "",
                    f"# {row['label']}",
                    "",
                    "## 설명",
                    "",
                    description,
                    "",
                    "## 추출본문",
                    "",
                    text,
                ]
                (annex_dir / md_name).write_text("\n".join(md).rstrip() + "\n", encoding="utf-8")
                row["description"] = description
                row["text_path"] = rel_text_path
                converted += 1
            top_rows.append({**row, "regulation": reg_dir.name})
        write_jsonl(index_path, rows)
        update_markdown_index(annex_dir / "별표_별지_색인.md", rows)

    write_jsonl(FSS_DIR / "annex_index.jsonl", top_rows)
    print(f"annex descriptions done: converted={converted} failed={failed} top_rows={len(top_rows)}")


if __name__ == "__main__":
    main()
