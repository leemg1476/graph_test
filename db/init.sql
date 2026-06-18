CREATE EXTENSION IF NOT EXISTS age;

CREATE TABLE IF NOT EXISTS public.legal_documents (
    id BIGSERIAL PRIMARY KEY,
    law_name TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    source_path TEXT NOT NULL UNIQUE,
    content_sha256 TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.legal_chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES legal_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    law_name TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    source_path TEXT NOT NULL,
    heading TEXT,
    text TEXT NOT NULL,
    token_estimate INTEGER NOT NULL,
    embedding DOUBLE PRECISION[] NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS legal_chunks_law_name_idx ON public.legal_chunks (law_name);
CREATE INDEX IF NOT EXISTS legal_chunks_source_path_idx ON public.legal_chunks (source_path);

CREATE TABLE IF NOT EXISTS public.graph_extractions (
    id BIGSERIAL PRIMARY KEY,
    chunk_id BIGINT NOT NULL REFERENCES legal_chunks(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    raw_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (chunk_id, model_name)
);

CREATE TABLE IF NOT EXISTS public.graph_entities (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    canonical_name TEXT NOT NULL DEFAULT '',
    canonical_key TEXT NOT NULL DEFAULT '',
    entity_type TEXT NOT NULL,
    description TEXT,
    source_chunk_id BIGINT REFERENCES legal_chunks(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name, entity_type),
    UNIQUE (canonical_key, entity_type)
);

CREATE TABLE IF NOT EXISTS public.graph_entity_aliases (
    id BIGSERIAL PRIMARY KEY,
    entity_id BIGINT NOT NULL REFERENCES graph_entities(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    alias_key TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (alias_key, entity_type)
);

CREATE INDEX IF NOT EXISTS graph_entity_aliases_entity_id_idx
ON public.graph_entity_aliases (entity_id);

CREATE TABLE IF NOT EXISTS public.graph_edges (
    id BIGSERIAL PRIMARY KEY,
    source_entity_id BIGINT NOT NULL REFERENCES graph_entities(id) ON DELETE CASCADE,
    target_entity_id BIGINT NOT NULL REFERENCES graph_entities(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,
    relation_group_key TEXT,
    description TEXT,
    source_chunk_id BIGINT REFERENCES legal_chunks(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_entity_id, target_entity_id, relation_type, source_chunk_id)
);

CREATE INDEX IF NOT EXISTS graph_edges_relation_type_idx ON public.graph_edges (relation_type);
CREATE INDEX IF NOT EXISTS graph_edges_relation_group_key_idx ON public.graph_edges (relation_group_key);

CREATE TABLE IF NOT EXISTS public.audit_findings (
    id BIGSERIAL PRIMARY KEY,
    company_name TEXT NOT NULL,
    finding_title TEXT NOT NULL,
    finding_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION public.cosine_similarity(a DOUBLE PRECISION[], b DOUBLE PRECISION[])
RETURNS DOUBLE PRECISION
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    dot DOUBLE PRECISION := 0;
    norm_a DOUBLE PRECISION := 0;
    norm_b DOUBLE PRECISION := 0;
    i INTEGER;
BEGIN
    IF array_length(a, 1) IS NULL OR array_length(b, 1) IS NULL THEN
        RETURN 0;
    END IF;
    IF array_length(a, 1) <> array_length(b, 1) THEN
        RAISE EXCEPTION 'embedding dimensions differ: % vs %', array_length(a, 1), array_length(b, 1);
    END IF;
    FOR i IN 1..array_length(a, 1) LOOP
        dot := dot + a[i] * b[i];
        norm_a := norm_a + a[i] * a[i];
        norm_b := norm_b + b[i] * b[i];
    END LOOP;
    IF norm_a = 0 OR norm_b = 0 THEN
        RETURN 0;
    END IF;
    RETURN dot / sqrt(norm_a * norm_b);
END;
$$;

LOAD 'age';
SET search_path = ag_catalog, "$user", public;

DO $$
BEGIN
    PERFORM create_graph('legal_graph');
EXCEPTION
    WHEN duplicate_schema THEN NULL;
    WHEN unique_violation THEN NULL;
END
$$;
