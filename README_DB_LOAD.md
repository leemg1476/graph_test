# Woori PoC DB Load Package

이 패키지는 폐쇄망 PostgreSQL에 우리금융지주 PoC 산출물을 적재하기 위한 최소 파일 묶음입니다.

## 포함 파일

```text
artifacts/graph/*.jsonl
artifacts/graph/semantic_status.json
artifacts/wiki/*.md
artifacts/search/chunks.jsonl
artifacts/search/bm25_index.json
artifacts/search/embedding_config.json
source/sql/001_schema.sql
source/sql/002_load_artifacts.sql
source/sql/003_views_and_queries.sql
```

원천 `data/` 디렉토리와 실행 소스코드는 DB 적재에는 필요하지 않습니다.

## 전제 조건

- PostgreSQL 15 이상 권장
- `psql` 클라이언트 사용 가능
- DB 사용자가 schema/table/index/extension 생성 권한을 가져야 함
- 한글 파일명과 UTF-8 내용을 읽어야 하므로 client encoding은 UTF-8 권장

선택 확장:

- `pg_trgm`: DDL에서 생성 시도, 텍스트 유사 검색 인덱스용
- `pgvector`: 설치되어 있으면 vector 컬럼/인덱스를 생성하지만, 이 패키지는 임베딩 벡터 원본을 포함하지 않습니다.

## 실행 방법

압축을 해제한 패키지 루트에서 실행합니다. 반드시 `artifacts/`와 `source/sql/`가 보이는 위치에서 실행해야 합니다.

```bash
export PGCLIENTENCODING=UTF8

psql "postgresql://USER:PASSWORD@HOST:PORT/DBNAME" -v ON_ERROR_STOP=1 -f source/sql/001_schema.sql
psql "postgresql://USER:PASSWORD@HOST:PORT/DBNAME" -v ON_ERROR_STOP=1 -f source/sql/002_load_artifacts.sql
psql "postgresql://USER:PASSWORD@HOST:PORT/DBNAME" -v ON_ERROR_STOP=1 -f source/sql/003_views_and_queries.sql
```

Windows PowerShell 예시:

```powershell
$env:PGCLIENTENCODING = "UTF8"

psql "postgresql://USER:PASSWORD@HOST:PORT/DBNAME" -v ON_ERROR_STOP=1 -f source/sql/001_schema.sql
psql "postgresql://USER:PASSWORD@HOST:PORT/DBNAME" -v ON_ERROR_STOP=1 -f source/sql/002_load_artifacts.sql
psql "postgresql://USER:PASSWORD@HOST:PORT/DBNAME" -v ON_ERROR_STOP=1 -f source/sql/003_views_and_queries.sql
```

## 적재 결과 확인

```sql
SET search_path TO woori_poc, public;

SELECT * FROM load_audit ORDER BY load_id;

SELECT count(*) AS semantic_nodes FROM semantic_node;
SELECT count(*) AS semantic_edges FROM semantic_edge;
SELECT count(*) AS chunks FROM search_chunk;
SELECT count(*) AS wiki_pages FROM wiki_page;
SELECT * FROM llm_batch_job;
```

## Agent 조회용 대표 View

```sql
SET search_path TO woori_poc, public;

-- 의미 그래프 검색용
SELECT *
FROM v_semantic_graph_search
WHERE label ILIKE '%계좌%' OR description ILIKE '%계좌%'
LIMIT 20;

-- 감사 지적사항 -> 리스크 -> 통제/대응 매핑
SELECT finding, risk, failure_mode, control, remediation, data_path
FROM v_audit_risk_map
WHERE finding ILIKE '%계좌%'
LIMIT 20;

-- 문서별 evidence 확인
SELECT data_path, source_label, edge_type, target_label, evidence
FROM v_document_evidence
WHERE data_path ILIKE '%대구은행%'
LIMIT 20;
```

## 주의 사항

- `002_load_artifacts.sql`는 기존 `woori_poc` 스키마의 대상 테이블을 `TRUNCATE ... CASCADE` 후 재적재합니다.
- 이 패키지는 DB 적재 최소 파일만 포함합니다. 원문 파일 전체 탐색이 필요하면 별도로 `data/`를 반입해야 합니다.
- 임베딩 벡터 자체는 포함하지 않습니다. 현재 패키지는 BM25/텍스트 검색과 그래프 검색 적재용입니다.
- `semantic_status.json` 기준 LLM semantic graphify Batch가 완료 전이면, 현재 포함된 semantic graph는 완료 시점 전 산출물입니다.
