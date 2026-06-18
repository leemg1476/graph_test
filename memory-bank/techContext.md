# Tech Context

## Runtime / Language

- Python 3.10+
- Postgres with Apache AGE via Docker
- `psycopg` for database access
- `langchain-openai` for OpenAI-compatible Qwen/vLLM chat calls
- Deterministic local hashing embeddings for initial vector RAG storage

## Local Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
docker compose up -d postgres-age
python scripts\ingest_legal_corpus.py
```

## Build / Test / Deploy Commands

```powershell
python -m pytest tests -q
python -m compileall src scripts tests
docker compose config
```

Graph extraction requires a running Qwen/vLLM endpoint:

```powershell
python scripts\extract_graph.py --limit 10
```

The audit agent also requires an LLM endpoint:

```powershell
python scripts\ask_audit_agent.py
```

## Documentation / Project Memory

- `AGENTS.md`: operating rules for AI agents.
- `llms.txt`: short LLM entrypoint.
- `docs/llm-wiki.md`: detailed project-management wiki.
- `memory-bank/`: durable project context.
- `.ai-worklog/`: dated session history.
- `adr/`: hard-to-reverse decisions.
- `prompts/`: reusable start/close prompts.

## External Dependencies

- Docker
- `apache/age:latest`
- Qwen-compatible vLLM/OpenAI endpoint for graph extraction and ReAct answering

## Environment Variables Policy

- Do not commit real `.env` values.
- Document required environment variables with placeholders only.
- Mask tokens, passwords, internal URLs, customer names, and account identifiers.
- Record environment assumptions without recording sensitive values.
