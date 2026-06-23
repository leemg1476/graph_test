# PostgreSQL Offline Load Scripts

Run from `C:\Users\LeeMyeonggyu\Documents\우리금융지주_PoC`.

```powershell
psql "postgresql://user:pass@host:5432/db" -v ON_ERROR_STOP=1 -f source/sql/001_schema.sql
psql "postgresql://user:pass@host:5432/db" -v ON_ERROR_STOP=1 -f source/sql/002_load_artifacts.sql
psql "postgresql://user:pass@host:5432/db" -v ON_ERROR_STOP=1 -f source/sql/003_views_and_queries.sql
```

Optional embeddings:

1. Export `artifacts/search/embeddings.npy` to `artifacts/search/embeddings.csv` with columns:
   `chunk_id,model,dimension,embedding_jsonb`
2. Run:

```powershell
psql "postgresql://user:pass@host:5432/db" -v ON_ERROR_STOP=1 -f source/sql/004_load_embeddings_csv.sql
```

The schema works without `pgvector`; embeddings remain in `embedding_jsonb`.
If `pgvector` is installed, `search_embedding.embedding_vector` is populated for vector search.
