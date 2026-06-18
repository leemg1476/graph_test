from __future__ import annotations

from pathlib import Path

from .chunking import chunk_document, iter_legal_documents
from .config import Settings
from .db import connect
from .embedding import HashingEmbedder


def ingest_legal_corpus(root: Path | None = None, settings: Settings | None = None) -> dict[str, int]:
    cfg = settings or Settings()
    project_root = root or cfg.project_root
    embedder = HashingEmbedder(cfg.embed_dim)
    docs = iter_legal_documents(project_root)
    document_count = 0
    chunk_count = 0

    with connect(cfg) as conn:
        with conn.cursor() as cur:
            for doc in docs:
                cur.execute(
                    """
                    INSERT INTO legal_documents (law_name, doc_type, source_path, content_sha256)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (source_path) DO UPDATE
                    SET law_name = EXCLUDED.law_name,
                        doc_type = EXCLUDED.doc_type,
                        content_sha256 = EXCLUDED.content_sha256
                    RETURNING id
                    """,
                    (doc.law_name, doc.doc_type, doc.source_path, doc.sha256),
                )
                document_id = cur.fetchone()["id"]
                document_count += 1

                for chunk in chunk_document(doc):
                    embedding = embedder.embed(chunk.text)
                    cur.execute(
                        """
                        INSERT INTO legal_chunks (
                            document_id, chunk_index, law_name, doc_type, source_path,
                            heading, text, token_estimate, embedding, metadata
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (document_id, chunk_index) DO UPDATE
                        SET heading = EXCLUDED.heading,
                            text = EXCLUDED.text,
                            token_estimate = EXCLUDED.token_estimate,
                            embedding = EXCLUDED.embedding,
                            metadata = EXCLUDED.metadata
                        """,
                        (
                            document_id,
                            chunk.chunk_index,
                            chunk.law_name,
                            chunk.doc_type,
                            chunk.source_path,
                            chunk.heading,
                            chunk.text,
                            chunk.token_estimate,
                            embedding,
                            "{}",
                        ),
                    )
                    chunk_count += 1

    return {"documents": document_count, "chunks": chunk_count}

