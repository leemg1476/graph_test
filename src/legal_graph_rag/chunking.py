from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


HEADING_RE = re.compile(r"^(#{1,6}\s+.+|제\d+[조장절관].*)$")


@dataclass(frozen=True)
class LegalDocument:
    law_name: str
    doc_type: str
    source_path: str
    text: str
    sha256: str


@dataclass(frozen=True)
class LegalChunk:
    chunk_index: int
    law_name: str
    doc_type: str
    source_path: str
    heading: str
    text: str
    token_estimate: int


def iter_legal_documents(root: Path) -> list[LegalDocument]:
    docs: list[LegalDocument] = []
    for path in sorted(root.glob("kr/**/*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            continue
        rel = path.relative_to(root).as_posix()
        docs.append(
            LegalDocument(
                law_name=path.parent.name,
                doc_type=path.stem,
                source_path=rel,
                text=text,
                sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )
        )
    return docs


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 3)


def chunk_document(
    document: LegalDocument,
    *,
    max_chars: int = 2400,
    overlap_chars: int = 250,
) -> list[LegalChunk]:
    lines = document.text.splitlines()
    chunks: list[LegalChunk] = []
    buffer: list[str] = []
    current_heading = document.law_name
    chunk_index = 0

    def flush() -> None:
        nonlocal chunk_index, buffer
        text = "\n".join(buffer).strip()
        if not text:
            buffer = []
            return
        chunks.append(
            LegalChunk(
                chunk_index=chunk_index,
                law_name=document.law_name,
                doc_type=document.doc_type,
                source_path=document.source_path,
                heading=current_heading,
                text=text,
                token_estimate=_estimate_tokens(text),
            )
        )
        chunk_index += 1
        if overlap_chars > 0:
            tail = text[-overlap_chars:]
            buffer = [tail]
        else:
            buffer = []

    for line in lines:
        stripped = line.strip()
        if HEADING_RE.match(stripped):
            current_heading = stripped.lstrip("#").strip()
        if sum(len(item) + 1 for item in buffer) + len(line) > max_chars:
            flush()
        buffer.append(line)
    flush()
    return chunks

