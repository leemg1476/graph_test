from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .llm import make_chat_model
from .tools import get_chunk, graph_search, vector_search


SYSTEM_PROMPT = """\
너는 금융지주회사 감사지적사항을 법령 근거와 연결해 답변하는 ReAct 에이전트다.

사용 가능한 도구:
- vector_search: chunking된 법령 RAG 검색. args: {"query": "...", "k": 5}
- graph_search: entity-edge 그래프 검색. args: {"query": "...", "k": 10}
- get_chunk: chunk id로 원문 조회. args: {"chunk_id": 1}
- final_answer: 최종 답변. args: {"answer": "..."}

각 단계마다 반드시 JSON만 출력한다:
{"thought":"...","tool":"vector_search|graph_search|get_chunk|final_answer","args":{...}}

답변은 감사지적사항의 리스크, 관련 법령/개념, 확인해야 할 내부통제 포인트, 개선 조치 순서로 작성한다.
"""


SYSTEM_PROMPT = """\
너는 금융지주회사 감사지적사항을 법령 근거와 연결해 답변하는 ReAct 에이전트다.

사용 가능한 도구:
- graph_search: 질의의 핵심 표현을 canonical/alias 기반으로 entity linking하고, 관련 entity-edge path와 source chunk preview를 반환한다. args: {"query": "...", "k": 10}
- vector_search: chunking된 법령 원문 RAG 검색. args: {"query": "...", "k": 5}
- get_chunk: chunk id로 원문 조회. args: {"chunk_id": 1}
- final_answer: 최종 답변. args: {"answer": "..."}

도구 사용 원칙:
- 최종 답변 전에 graph_search와 vector_search를 모두 사용한다.
- 먼저 graph_search로 감사지적사항의 핵심 entity, 관련 edge, 변경/병합/관련 관계를 찾는다.
- graph_search 결과의 source_chunk_id가 중요하면 get_chunk로 원문을 확인한다.
- vector_search로 법령 원문 근거를 보강하고, graph 관계와 vector 원문이 충돌하면 원문을 우선한다.
- graph_search 결과가 약하더라도 그 사실을 답변에서 과장하지 말고, vector 근거 중심으로 한계를 밝힌다.

각 단계마다 반드시 JSON만 출력한다:
{"thought":"...","tool":"graph_search|vector_search|get_chunk|final_answer","args":{}}

답변은 감사지적사항의 리스크, 관련 법령/개념, 확인해야 할 내부통제 포인트, 개선 조치 순서로 작성한다.
"""


@dataclass
class ReActStep:
    thought: str
    tool: str
    args: dict[str, Any]
    observation: Any = None


@dataclass
class AgentResult:
    answer: str
    steps: list[ReActStep] = field(default_factory=list)


class AuditFindingReActAgent:
    def __init__(self, max_steps: int = 6) -> None:
        self.max_steps = max_steps
        self.llm = make_chat_model(temperature=0.1, max_tokens=4096, enable_thinking=False)

    def run(self, finding_text: str, company_name: str = "임의 금융지주사") -> AgentResult:
        steps: list[ReActStep] = []
        messages: list[tuple[str, str]] = [
            ("system", SYSTEM_PROMPT),
            ("user", f"회사: {company_name}\n감사지적사항:\n{finding_text}"),
        ]

        for _ in range(self.max_steps):
            action = self._next_action(messages)
            step = ReActStep(
                thought=str(action.get("thought", "")),
                tool=str(action.get("tool", "")),
                args=dict(action.get("args") or {}),
            )
            if step.tool == "final_answer":
                missing_tool = self._missing_required_context_tool(steps)
                if missing_tool:
                    step = ReActStep(
                        thought=f"최종 답변 전에 {missing_tool} context가 필요하다.",
                        tool=missing_tool,
                        args={"query": finding_text, "k": 5 if missing_tool == "vector_search" else 10},
                    )
                    step.observation = self._call_tool(step.tool, step.args, finding_text)
                    steps.append(step)
                    messages.append(
                        (
                            "user",
                            "Observation:\n" + json.dumps(step.observation, ensure_ascii=False, default=str),
                        )
                    )
                    continue
                return AgentResult(answer=str(step.args.get("answer", "")), steps=steps + [step])

            step.observation = self._call_tool(step.tool, step.args, finding_text)
            steps.append(step)
            messages.append(("assistant", json.dumps(action, ensure_ascii=False)))
            messages.append(("user", "Observation:\n" + json.dumps(step.observation, ensure_ascii=False, default=str)))

        return self._fallback_answer(finding_text, company_name, steps)

    @staticmethod
    def _missing_required_context_tool(steps: list[ReActStep]) -> str | None:
        tools = {step.tool for step in steps}
        if "vector_search" not in tools:
            return "vector_search"
        if "graph_search" not in tools:
            return "graph_search"
        return None

    def _next_action(self, messages: list[tuple[str, str]]) -> dict[str, Any]:
        response = self.llm.invoke(messages)
        content = response.content if isinstance(response.content, str) else json.dumps(response.content)
        try:
            return self._parse_json(content)
        except json.JSONDecodeError:
            return {"thought": "LLM 출력이 JSON이 아니므로 법령 RAG 검색부터 수행한다.", "tool": "vector_search", "args": {"query": messages[-1][1], "k": 5}}

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.removeprefix("json").strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end >= start:
            cleaned = cleaned[start : end + 1]
        return json.loads(cleaned)

    @staticmethod
    def _call_tool(tool: str, args: dict[str, Any], fallback_query: str) -> Any:
        if tool == "vector_search":
            return vector_search(str(args.get("query") or fallback_query), int(args.get("k") or 5))
        if tool == "graph_search":
            return graph_search(str(args.get("query") or fallback_query), int(args.get("k") or 10))
        if tool == "get_chunk":
            return get_chunk(int(args["chunk_id"]))
        return {"error": f"unknown tool: {tool}"}

    def _fallback_answer(
        self,
        finding_text: str,
        company_name: str,
        steps: list[ReActStep],
    ) -> AgentResult:
        vector_context = vector_search(finding_text, 5)
        graph_context = graph_search(finding_text, 10)
        prompt = (
            f"회사: {company_name}\n감사지적사항:\n{finding_text}\n\n"
            f"법령 RAG 검색 결과:\n{json.dumps(vector_context, ensure_ascii=False, default=str)}\n\n"
            f"그래프 검색 결과:\n{json.dumps(graph_context, ensure_ascii=False, default=str)}\n\n"
            "위 근거를 바탕으로 리스크, 관련 법령/개념, 내부통제 포인트, 개선 조치 순서로 답변하라."
        )
        response = self.llm.invoke(prompt)
        answer = response.content if isinstance(response.content, str) else json.dumps(response.content, ensure_ascii=False)
        return AgentResult(answer=answer, steps=steps)
