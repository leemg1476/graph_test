# legalize-kr 금융업 내부통제/준법/책무 법령 세트

이 저장소는 `legalize-kr/legalize-kr` 원본에서 금융업, 내부통제, 준법, 책무와 관련된 법령 문서만 남긴 작업용 데이터셋입니다.

AX2 프로젝트 템플릿의 문서/작업관리 구조를 적용해, 이후 분석·요약·그래프화·RAG 전처리 작업을 이어갈 수 있도록 구성했습니다.

## Contents

- `kr/`: 선별된 금융업 관련 법령 원문 Markdown
- `AGENTS.md`: AI 작업 에이전트 운영 원칙
- `llms.txt`: LLM용 짧은 진입점
- `docs/`: LLM wiki와 개발/문서 컨벤션
- `memory-bank/`: 프로젝트 목적, 진행 상태, 기술 맥락, 이슈 기록
- `.ai-worklog/`: 세션별 작업 로그
- `adr/`: 되돌리기 어려운 의사결정 기록
- `prompts/`: 세션 시작/종료용 재사용 프롬프트
- `.graphifyignore`: Graphify 입력 제외 규칙

## Current Dataset

현재 `kr/` 아래에는 금융업/금융기관 관련 법령 중 본문에 다음 주제와 관련된 내용이 있는 폴더만 남겨두었습니다.

- 내부통제
- 준법 및 준법감시
- 책무
- 지배구조

현재 기준:

- 법령 폴더: 25개
- Markdown 파일: 55개

## GraphRAG Pipeline

이 프로젝트에는 다음 파이프라인이 포함되어 있습니다.

1. `apache/age` Docker 이미지로 Postgres + Apache AGE 실행
2. `kr/**/*.md` 법령 문서 chunking
3. chunk와 deterministic vector embedding을 Postgres 테이블에 저장
4. Qwen/vLLM 호환 LLM으로 entity-edge 추출
5. 추출 결과를 Apache AGE graph와 관계형 mirror table에 저장
6. 금융지주사 감사지적사항을 입력받아 vector RAG와 graph search 도구를 호출하는 ReAct 에이전트 실행

### Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```

`.env`에서 Qwen/vLLM endpoint를 설정합니다. 방식은 `ra-agent`의 model switching 패턴과 맞췄습니다.

```env
activate_model_name=vllm
VLLM_BASE_URL=http://localhost:8000/v1
VLLM_API_KEY=EMPTY
VLLM_MODEL_NAME=Qwen/Qwen3.5-122B-A10B
VLLM_ENABLE_THINKING=false
```

`activate_model_name=Qwen/...`처럼 모델명을 직접 넣어도 vLLM provider로 해석합니다.

### Run Postgres + AGE

```powershell
docker compose up -d postgres-age
docker compose ps
```

### Ingest Legal Chunks

```powershell
python scripts\ingest_legal_corpus.py
```

현재 로컬 검증 기준으로 55개 문서가 1,520개 chunk로 적재됩니다.

### Extract Entity-Edge Graph

Qwen/vLLM endpoint가 실행 중이어야 합니다.

```powershell
python scripts\extract_graph.py --limit 10 --concurrency 20
```

`--limit`을 빼면 아직 추출되지 않은 모든 chunk를 처리합니다. `--concurrency`는 비동기 LLM 호출 동시 실행 수이며 기본값은 `20`입니다.

AGE graph를 관계형 mirror table 기준으로 재생성해야 할 때는 다음을 실행합니다.

```powershell
python scripts\rebuild_age_graph.py
```

### Ask The ReAct Audit Agent

```powershell
python scripts\ask_audit_agent.py
```

또는 감사지적사항을 직접 입력합니다.

```powershell
python scripts\ask_audit_agent.py --company "샘플금융지주" --finding "준법감시인의 개선권고 이행상황이 감사위원회에 보고되지 않았다."
```

에이전트는 `vector_search`, `graph_search`, `get_chunk` 도구를 필요에 따라 호출하고, 관찰 결과를 바탕으로 다음 도구 호출 또는 최종 답변을 결정합니다.

## Source

- 원본 법령 저장소: <https://github.com/legalize-kr/legalize-kr>
- 적용한 프로젝트 템플릿: <https://github.com/financial-ai-data-business/ax2-project-template>

## Notes

- 이 저장소는 현재 실행 가능한 애플리케이션이 아니라 문서 데이터와 프로젝트 관리 스캐폴드입니다.
- 원본 저장소에서 관련 없는 법령 폴더는 삭제되어 `git status`에 대량 삭제로 표시됩니다.
- 민감정보, 원시 대화 로그, 내부 URL, 고객 식별 정보는 저장하지 않습니다.
