from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.legal_graph_rag.config import Settings
from src.legal_graph_rag.db import connect, prepare_age


def main() -> None:
    cfg = Settings()
    with connect(cfg) as conn:
        prepare_age(conn)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.graph_edges")
            cur.execute(
                """
                DO $$
                BEGIN
                    IF to_regclass('public.graph_entity_aliases') IS NOT NULL THEN
                        DELETE FROM public.graph_entity_aliases;
                    END IF;
                END
                $$;
                """
            )
            cur.execute("DELETE FROM public.graph_entities")
            cur.execute("DELETE FROM public.graph_extractions")
            cur.execute("SELECT drop_graph(%s, true)", (cfg.graph_name,))
            cur.execute("SELECT create_graph(%s)", (cfg.graph_name,))
    print({"reset": True, "graph": cfg.graph_name})


if __name__ == "__main__":
    main()
