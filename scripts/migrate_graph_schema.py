from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.legal_graph_rag.db import connect


MIGRATION_SQL = """
ALTER TABLE public.graph_entities
ADD COLUMN IF NOT EXISTS canonical_name TEXT;

ALTER TABLE public.graph_entities
ADD COLUMN IF NOT EXISTS canonical_key TEXT;

UPDATE public.graph_entities
SET canonical_name = COALESCE(NULLIF(canonical_name, ''), name)
WHERE canonical_name IS NULL OR canonical_name = '';

UPDATE public.graph_entities
SET canonical_key = COALESCE(NULLIF(canonical_key, ''), entity_type || ':' || md5(lower(regexp_replace(name, '[^0-9A-Za-z가-힣]+', '', 'g'))))
WHERE canonical_key IS NULL OR canonical_key = '';

ALTER TABLE public.graph_entities
ALTER COLUMN canonical_name SET NOT NULL;

ALTER TABLE public.graph_entities
ALTER COLUMN canonical_key SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS graph_entities_canonical_key_entity_type_key
ON public.graph_entities (canonical_key, entity_type);

CREATE TABLE IF NOT EXISTS public.graph_entity_aliases (
    id BIGSERIAL PRIMARY KEY,
    entity_id BIGINT NOT NULL REFERENCES public.graph_entities(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    alias_key TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (alias_key, entity_type)
);

CREATE INDEX IF NOT EXISTS graph_entity_aliases_entity_id_idx
ON public.graph_entity_aliases (entity_id);

INSERT INTO public.graph_entity_aliases (entity_id, alias, alias_key, entity_type)
SELECT id, name, lower(regexp_replace(name, '[^0-9A-Za-z가-힣]+', '', 'g')), entity_type
FROM public.graph_entities
ON CONFLICT (alias_key, entity_type) DO NOTHING;

ALTER TABLE public.graph_edges
ADD COLUMN IF NOT EXISTS relation_group_key TEXT;

CREATE INDEX IF NOT EXISTS graph_edges_relation_type_idx ON public.graph_edges (relation_type);
CREATE INDEX IF NOT EXISTS graph_edges_relation_group_key_idx ON public.graph_edges (relation_group_key);
"""


def main() -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(MIGRATION_SQL)
    print({"migrated": True})


if __name__ == "__main__":
    main()

