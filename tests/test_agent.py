from dataclasses import dataclass

from src.legal_graph_rag import agent as agent_module
from src.legal_graph_rag.agent import AuditFindingReActAgent


@dataclass
class FakeResponse:
    content: str


class FakeLLM:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, _messages):
        self.calls += 1
        if self.calls == 1:
            return FakeResponse(
                '{"thought":"법령 context가 필요하다","tool":"vector_search","args":{"query":"내부통제 준법감시","k":2}}'
            )
        if self.calls == 2:
            return FakeResponse(
                '{"thought":"그래프 관계를 확인한다","tool":"graph_search","args":{"query":"준법감시인 보고","k":2}}'
            )
        return FakeResponse(
            '{"thought":"충분한 근거를 확보했다","tool":"final_answer","args":{"answer":"내부통제기준과 준법감시 보고체계를 보완해야 한다."}}'
        )


def test_react_agent_calls_tools_and_returns_final(monkeypatch) -> None:
    monkeypatch.setattr(agent_module, "make_chat_model", lambda **_kwargs: FakeLLM())
    monkeypatch.setattr(agent_module, "vector_search", lambda query, k: [{"query": query, "k": k}])
    monkeypatch.setattr(agent_module, "graph_search", lambda query, k: [{"query": query, "k": k}])

    result = AuditFindingReActAgent().run("준법감시 보고 미흡")

    assert result.answer == "내부통제기준과 준법감시 보고체계를 보완해야 한다."
    assert [step.tool for step in result.steps] == ["vector_search", "graph_search", "final_answer"]

