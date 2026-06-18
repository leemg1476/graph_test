from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.legal_graph_rag.config import Settings
from src.legal_graph_rag.db import connect, prepare_age
from src.legal_graph_rag.graph_extract import (
    ExtractedEdge,
    ExtractedEntity,
    ExtractionPayload,
    _upsert_graph_payload,
)


def main() -> None:
    cfg = Settings()
    with connect(cfg) as conn:
        prepare_age(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT drop_graph(%s, true)", (cfg.graph_name,))
            cur.execute("SELECT create_graph(%s)", (cfg.graph_name,))
            cur.execute(
                """
                SELECT id, name, entity_type, COALESCE(description, '') AS description,
                       COALESCE(source_chunk_id, 0) AS source_chunk_id
                FROM graph_entities
                ORDER BY id
                """
            )
            entities = cur.fetchall()
            cur.execute(
                """
                SELECT ge.source_chunk_id,
                       se.name AS source_name,
                       se.entity_type AS source_type,
                       te.name AS target_name,
                       te.entity_type AS target_type,
                       ge.relation_type,
                       COALESCE(ge.description, '') AS description
                FROM graph_edges ge
                JOIN graph_entities se ON se.id = ge.source_entity_id
                JOIN graph_entities te ON te.id = ge.target_entity_id
                ORDER BY ge.id
                """
            )
            edges = cur.fetchall()

        for entity in entities:
            payload = ExtractionPayload(
                entities=[
                    ExtractedEntity(
                        name=entity["name"],
                        type=entity["entity_type"],
                        description=entity["description"],
                    )
                ],
                edges=[],
            )
            _upsert_graph_payload(conn, cfg.graph_name, int(entity["source_chunk_id"] or 0), payload)

        for edge in edges:
            payload = ExtractionPayload(
                entities=[
                    ExtractedEntity(name=edge["source_name"], type=edge["source_type"]),
                    ExtractedEntity(name=edge["target_name"], type=edge["target_type"]),
                ],
                edges=[
                    ExtractedEdge(
                        source=edge["source_name"],
                        target=edge["target_name"],
                        type=edge["relation_type"],
                        description=edge["description"],
                    )
                ],
            )
            _upsert_graph_payload(conn, cfg.graph_name, int(edge["source_chunk_id"] or 0), payload)

    print({"rebuilt": cfg.graph_name, "entities": len(entities), "edges": len(edges)})


if __name__ == "__main__":
    main()
