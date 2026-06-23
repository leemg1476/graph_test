from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Iterable

from .config import ARTIFACTS_DIR, DATA_DIR


TEXT_EXTENSIONS = {".md", ".txt", ".json", ".jsonl", ".csv"}
READABLE_BINARY_EXTENSIONS = {".hwp", ".gif", ".png", ".jpg", ".jpeg", ".pdf"}


def clean_text(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def safe_relative_path(root: Path, rel_path: str | os.PathLike[str]) -> Path:
    candidate = (root / Path(str(rel_path))).resolve()
    root_resolved = root.resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise ValueError(f"path escapes allowed root: {rel_path}")
    return candidate


def list_collections() -> list[dict]:
    if not DATA_DIR.exists():
        return []
    rows = []
    for child in sorted(DATA_DIR.iterdir(), key=lambda p: p.name):
        if child.is_dir():
            rows.append(
                {
                    "name": child.name,
                    "path": child.name,
                    "has_index": (child / "index.jsonl").exists(),
                    "has_readme": (child / "README.md").exists(),
                }
            )
    return rows


def iter_index_rows(collection: str | None = None) -> Iterable[dict]:
    roots = [safe_relative_path(DATA_DIR, collection)] if collection else [DATA_DIR / row["path"] for row in list_collections()]
    for root in roots:
        for index_path in sorted(root.glob("*.jsonl")):
            if index_path.name == "annex_index.jsonl":
                continue
            for line in index_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    row.setdefault("collection", root.name)
                    row.setdefault("_index", str(index_path.relative_to(DATA_DIR)).replace("\\", "/"))
                    yield row
        annex_index = root / "annex_index.jsonl"
        if annex_index.exists():
            for line in annex_index.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    row.setdefault("collection", root.name)
                    row.setdefault("_index", str(annex_index.relative_to(DATA_DIR)).replace("\\", "/"))
                    yield row


def list_dir(area: str, rel_path: str = ".") -> list[dict]:
    root = root_for_area(area)
    path = safe_relative_path(root, rel_path)
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(str(path))
    rows = []
    for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name)):
        rows.append(
            {
                "name": child.name,
                "path": str(child.relative_to(root)).replace("\\", "/"),
                "type": "directory" if child.is_dir() else "file",
                "size": child.stat().st_size if child.is_file() else None,
            }
        )
    return rows


def root_for_area(area: str) -> Path:
    if area == "data":
        return DATA_DIR
    if area == "artifacts":
        return ARTIFACTS_DIR
    raise ValueError("area must be 'data' or 'artifacts'")


def read_text_file(area: str, rel_path: str, max_chars: int = 20000) -> dict:
    root = root_for_area(area)
    path = safe_relative_path(root, rel_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(str(path))
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return {
            "path": str(path.relative_to(root)).replace("\\", "/"),
            "binary": True,
            "extension": path.suffix.lower(),
            "size": path.stat().st_size,
            "message": "binary file; use metadata or converted markdown if available",
        }
    text = path.read_text(encoding="utf-8", errors="replace")
    truncated = len(text) > max_chars
    return {
        "path": str(path.relative_to(root)).replace("\\", "/"),
        "binary": False,
        "text": text[:max_chars],
        "truncated": truncated,
        "size": path.stat().st_size,
    }


def iter_text_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS:
            yield path


def search_text(query: str, area: str = "data", collection: str | None = None, limit: int = 20) -> list[dict]:
    root = root_for_area(area)
    search_root = safe_relative_path(root, collection) if collection else root
    needles = [part.lower() for part in query.split() if part.strip()]
    rows = []
    for path in iter_text_files(search_root):
        text = path.read_text(encoding="utf-8", errors="replace")
        low = text.lower()
        if all(needle in low for needle in needles):
            pos = min((low.find(needle) for needle in needles if needle in low), default=0)
            snippet = clean_text(text[max(0, pos - 180) : pos + 500])
            rows.append(
                {
                    "path": str(path.relative_to(root)).replace("\\", "/"),
                    "area": area,
                    "snippet": snippet,
                }
            )
            if len(rows) >= limit:
                break
    return rows
