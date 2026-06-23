# Woori Financial PoC Agent

This source tree exposes the collected PoC data as a read-only MCP filesystem/search server and a FastAPI-served LangGraph agent.

## Layout

- `../data`: collected source datasets
- `../artifacts/graph`: graphify output
- `../artifacts/wiki`: LLM wiki output
- `woori_poc/mcp_server.py`: read-only MCP server
- `woori_poc/api.py`: FastAPI LangGraph agent connected to the MCP server

## Setup

```powershell
cd C:\Users\LeeMyeonggyu\Documents\우리금융지주_PoC\source
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

The code reads LLM settings from `../.env`.

Use vLLM:

```env
LLM_PROVIDER=vllm
VLLM_BASE_URL=http://localhost:8000/v1
VLLM_API_KEY=EMPTY
VLLM_MODEL_NAME=your-vllm-model
VLLM_ENABLE_THINKING=false
```

Use OpenAI:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL_NAME=gpt-5.4-nano
OPENAI_BASE_URL=https://api.openai.com/v1
```

For graphify cost reduction with OpenAI Batch:

```env
LLM_PROVIDER=openai
GRAPHIFY_BATCH=true
LLM_BATCH_MAX_WAIT_SECONDS=0
```

With `LLM_BATCH_MAX_WAIT_SECONDS=0`, the first graphify run submits the batch and writes batch metadata under `artifacts/graph/batch`. Re-run the same command after the batch completes to download and apply the results. Set `--wait-batch` and a positive `LLM_BATCH_MAX_WAIT_SECONDS` if you want the command to poll.

## Build Artifacts

```powershell
woori-graphify
woori-wiki
```

Force OpenAI Batch mode for graphify from the CLI:

```powershell
woori-graphify --llm-mode batch
```

`woori-wiki` and `woori-agent-api` always use synchronous LLM calls.

## Enrich And Index

```powershell
woori-annex-describe
woori-collect-supervision
woori-build-search
woori-graphify --sample-size 2000 --llm-mode batch --wait-batch
woori-wiki --sample-size 2000
```

`woori-build-search` creates:

- `artifacts/search/chunks.jsonl`
- `artifacts/search/bm25_index.json`
- `artifacts/search/embeddings.npy`
- `artifacts/search/embedding_config.json`

MCP exposes `search_bm25`, `search_embedding`, and `search_hybrid`.

## Run MCP

```powershell
woori-mcp
```

## Run Agent API

```powershell
woori-agent-api
```

Default API URL: `http://127.0.0.1:8787`

```bash
curl -X POST http://127.0.0.1:8787/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"금융지주회사감독규정시행세칙 별표 목록을 찾아줘\"}"
```

## Run Streamlit Test UI

Run the API first, then start the UI in another terminal:

```powershell
woori-agent-api
woori-agent-ui
```

Default UI URL: `http://127.0.0.1:8501`
