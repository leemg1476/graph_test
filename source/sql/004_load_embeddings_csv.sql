-- Optional DML for embeddings.
-- PostgreSQL cannot read NumPy .npy directly. Export embeddings.npy to CSV first:
--
--   chunk_id,model,dimension,embedding_jsonb
--   0,text-embedding-ada-002,1536,"[0.001,...]"
--
-- Then run:
--   psql "postgresql://user:pass@host:5432/db" -v ON_ERROR_STOP=1 -f source/sql/004_load_embeddings_csv.sql

\set ON_ERROR_STOP on

BEGIN;
SET search_path TO woori_poc, public;

CREATE TEMP TABLE stg_embedding_csv (
  chunk_id integer,
  model text,
  dimension integer,
  embedding_jsonb jsonb
) ON COMMIT DROP;

\copy stg_embedding_csv(chunk_id, model, dimension, embedding_jsonb) FROM 'artifacts/search/embeddings.csv' WITH (FORMAT csv, HEADER true)

INSERT INTO search_embedding(chunk_id, model, dimension, embedding_jsonb)
SELECT chunk_id, model, dimension, embedding_jsonb
FROM stg_embedding_csv
ON CONFLICT (chunk_id) DO UPDATE
SET model = excluded.model,
    dimension = excluded.dimension,
    embedding_jsonb = excluded.embedding_jsonb;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
    EXECUTE $sql$
      UPDATE woori_poc.search_embedding se
      SET embedding_vector = (
        SELECT ('[' || string_agg(value, ',') || ']')::vector
        FROM jsonb_array_elements_text(se.embedding_jsonb) AS values(value)
      )
      WHERE se.embedding_jsonb IS NOT NULL
    $sql$;
  END IF;
END $$;

COMMIT;

ANALYZE woori_poc.search_embedding;
