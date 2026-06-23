from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid

import uvicorn
from fastapi import FastAPI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from .config import LLM_PROVIDER, SOURCE_DIR, TRACES_DIR, VLLM_ENABLE_THINKING, active_api_key, active_base_url, active_model_name


SYSTEM_PROMPT = """You are a Korean audit-risk advisory agent for the Woori Financial PoC corpus.

Primary mission:
- Given an audit finding, identify potential risks and practical remediation actions.
- Ground the answer in collected source data, semantic graphify artifacts, and LLM wiki.

Mandatory workflow:
1. Call graph_summary to understand graphify and semantic graphify coverage.
2. Call list_wiki_pages and read the most relevant wiki pages before forming the answer.
3. Call search_graph with the user's core finding/risk keywords. The semantic graph contains AuditFinding, Risk, FailureMode, Control, RegulationTopic, Remediation, and Evidence nodes; use it to map finding -> risk -> control/remediation.
4. Use search_hybrid for substantive source evidence. Use search_bm25/search_embedding/search_text only as fallback or cross-check.
5. If using graph evidence, use related_paths or exact data/artifacts paths as citations. Do not cite semantic:* IDs as source evidence by themselves.
6. Read or cite concrete source paths. Do not cite vague paths with ellipses.

Answer format:
Use these exact six section headings, in this order, even when some evidence is sparse:
1. 지적사항 재정의
2. 잠재 리스크
3. 관련 근거 문서
4. 대응방안
5. 우선순위
6. 점검 체크리스트
Do not rename, omit, merge, or skip any of the six headings. Each heading must appear verbatim.

Citation rules:
- Include exact data/artifact paths in backticks.
- If a graph result gives a related_paths value without a prefix, cite it as `data/{related_path}`.
- Semantic graph node IDs can be mentioned as internal mapping hints, but they are not sufficient citations.
- If a source is binary-only, say so and cite the converted markdown/description if available.
- Do not claim a regulation or case says something unless it appears in retrieved evidence.
- A final answer with no exact path citation is invalid. If search results are weak, cite the closest retrieved wiki or graph artifact path and clearly label it as weaker supporting evidence.
- Before finalizing, self-check that all six exact headings exist and at least one exact path is cited.
"""


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    answer: str
    trace_id: str | None = None


class DebugChatResponse(BaseModel):
    answer: str
    trace_id: str
    trace_path: str
    events: list[dict]


app = FastAPI(title="Woori PoC LangGraph Agent", version="0.1.0")

_agent = None
_client = None
_lock = asyncio.Lock()


async def get_agent():
    global _agent, _client
    async with _lock:
        if _agent is not None:
            return _agent
        model_name = active_model_name()
        if not model_name:
            raise RuntimeError("active LLM model is not configured in ../.env")

        server_args = {
            "woori_poc_data": {
                "command": sys.executable,
                "args": ["-m", "woori_poc.mcp_server"],
                "transport": "stdio",
                "cwd": str(SOURCE_DIR),
            }
        }
        _client = MultiServerMCPClient(server_args)
        tools = await _client.get_tools()
        model_kwargs = {}
        if LLM_PROVIDER == "vllm" and not VLLM_ENABLE_THINKING:
            model_kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
        model = ChatOpenAI(
            model=model_name,
            base_url=active_base_url(),
            api_key=active_api_key(),
            temperature=0.1,
            model_kwargs=model_kwargs,
        )
        _agent = create_react_agent(model, tools, prompt=SYSTEM_PROMPT)
        return _agent


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "provider": LLM_PROVIDER, "model": active_model_name(), "model_configured": bool(active_model_name())}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    agent = await get_agent()
    result = await agent.ainvoke({"messages": [("user", request.message)]})
    message = result["messages"][-1]
    content = getattr(message, "content", str(message))
    return ChatResponse(answer=content)


def compact_event(event: dict) -> dict | None:
    event_type = event.get("event", "")
    name = event.get("name", "")
    data = event.get("data") or {}
    if event_type in {"on_tool_start", "on_tool_end", "on_chat_model_start", "on_chat_model_end"}:
        item = {"event": event_type, "name": name}
        if event_type == "on_tool_start":
            item["input"] = data.get("input")
        elif event_type == "on_tool_end":
            output = data.get("output")
            text = str(output)
            item["output_preview"] = text[:1200]
        return item
    return None


@app.post("/debug/chat", response_model=DebugChatResponse)
async def debug_chat(request: ChatRequest) -> DebugChatResponse:
    agent = await get_agent()
    trace_id = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
    events: list[dict] = []
    final_answer = ""
    async for event in agent.astream_events({"messages": [("user", request.message)]}, version="v2"):
        compact = compact_event(event)
        if compact:
            events.append(compact)
        if event.get("event") == "on_chain_end" and event.get("name") == "LangGraph":
            output = (event.get("data") or {}).get("output") or {}
            messages = output.get("messages") or []
            if messages:
                final_answer = getattr(messages[-1], "content", str(messages[-1]))
    if not final_answer:
        result = await agent.ainvoke({"messages": [("user", request.message)]})
        final_answer = getattr(result["messages"][-1], "content", str(result["messages"][-1]))
    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    trace_path = TRACES_DIR / f"{trace_id}.json"
    trace_path.write_text(
        json.dumps({"trace_id": trace_id, "question": request.message, "answer": final_answer, "events": events}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return DebugChatResponse(answer=final_answer, trace_id=trace_id, trace_path=str(trace_path), events=events)


def main() -> None:
    uvicorn.run("woori_poc.api:app", host="127.0.0.1", port=8787, reload=False)


if __name__ == "__main__":
    main()
