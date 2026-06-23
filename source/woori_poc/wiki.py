from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date

from .config import WIKI_DIR
from .corpus import DATA_DIR, clean_text, iter_index_rows, list_collections
from .llm import chat_text


def collection_readme(collection: str) -> str:
    path = DATA_DIR / collection / "README.md"
    if path.exists():
        return path.read_text(encoding="utf-8", errors="replace")[:5000]
    return ""


def fallback_wiki(collection: str, rows: list[dict]) -> str:
    types = defaultdict(int)
    for row in rows:
        types[row.get("type") or row.get("class") or row.get("자료유형") or "문서"] += 1
    lines = [
        f"# {collection}",
        "",
        f"- 생성일: {date.today().isoformat()}",
        f"- 문서 수: {len(rows)}",
        "",
        "## 문서 유형",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in sorted(types.items()))
    lines.extend(["", "## 대표 문서", ""])
    for row in rows[:80]:
        title = row.get("title") or row.get("label") or row.get("regulation") or row.get("path")
        path = row.get("path", "")
        lines.append(f"- {title} `{path}`")
    return "\n".join(lines).rstrip() + "\n"


def wiki_prompt(collection: str, rows: list[dict], sample_size: int) -> tuple[str, str]:
    sample_rows = rows[:sample_size]
    sample = "\n".join(
        f"- {row.get('title') or row.get('label') or row.get('regulation')} / {row.get('type') or row.get('class') or ''}"
        for row in sample_rows
    )
    system = (
        "You are creating a Korean internal wiki page for a RAG dataset. "
        "Write concise markdown. Include: 개요, 포함 데이터, 주요 활용 질문, 탐색 시작점, 주의사항. "
        "Do not invent laws or facts not supported by the provided metadata."
    )
    user = (
        f"컬렉션명: {collection}\n"
        f"총 문서 수: {len(rows)}\n"
        f"README:\n{collection_readme(collection)}\n\n"
        f"샘플 색인:\n{sample}"
    )
    return system, user


def build_wiki(sample_size: int) -> None:
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    rows_by_collection: dict[str, list[dict]] = defaultdict(list)
    for row in iter_index_rows():
        rows_by_collection[row.get("collection", "unknown")].append(row)

    wiki_index = ["# LLM Wiki", "", f"- 생성일: {date.today().isoformat()}", ""]
    collections = [row["name"] for row in list_collections()]
    for collection in collections:
        rows = rows_by_collection.get(collection, [])
        system, user = wiki_prompt(collection, rows, sample_size)
        try:
            content = chat_text(system, user)
            if not content.lstrip().startswith("#"):
                content = f"# {collection}\n\n{content}"
        except Exception:
            content = fallback_wiki(collection, rows)

        out = WIKI_DIR / f"{collection}.md"
        out.write_text(content.rstrip() + "\n", encoding="utf-8")
        wiki_index.append(f"- [{collection}]({collection}.md): {len(rows)} records")

    (WIKI_DIR / "index.md").write_text("\n".join(wiki_index).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-size", type=int, default=120, help="metadata rows per collection passed to vLLM")
    args = parser.parse_args()
    build_wiki(args.sample_size)
    print(f"wiki done: {WIKI_DIR}")


if __name__ == "__main__":
    main()
