from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.legal_graph_rag.agent import AgentResult, AuditFindingReActAgent


CASES = [
    {
        "id": "case-01-compliance-reporting",
        "company": "샘플금융지주",
        "finding": (
            "준법감시인의 개선권고 및 조치 이행 현황이 이사회 또는 감사위원회에 정기적으로 보고되지 않았고, "
            "보고 누락 건에 대한 사후 점검 기록도 남아 있지 않다."
        ),
        "expected_focus": ["준법감시인", "보고", "이사회", "감사위원회", "개선권고"],
    },
    {
        "id": "case-02-internal-control-standard",
        "company": "테스트금융지주",
        "finding": (
            "내부통제기준 개정 절차가 형식적으로 운영되어 신규 사업 부문의 업무 분장, 승인권자, "
            "통제 활동이 기준에 반영되지 않았다."
        ),
        "expected_focus": ["내부통제기준", "업무분장", "승인", "통제", "개정"],
    },
    {
        "id": "case-03-accountability-map",
        "company": "가상금융지주",
        "finding": (
            "임원별 책무 배분 문서가 조직 개편 이후 갱신되지 않아 위험관리, 준법, 보고 책임의 담당자가 "
            "현행 조직도와 일치하지 않는다."
        ),
        "expected_focus": ["책무", "임원", "조직개편", "위험관리", "준법"],
    },
    {
        "id": "case-04-outsourcing-control",
        "company": "모의금융지주",
        "finding": (
            "중요 업무 위탁 업체에 대한 사전 심사와 정기 점검이 미흡하고, 위탁 업무 관련 사고 발생 시 "
            "보고 및 책임 소재를 확인하는 절차가 불명확하다."
        ),
        "expected_focus": ["위탁", "점검", "보고", "책임", "내부통제"],
    },
    {
        "id": "case-05-consumer-protection",
        "company": "예시금융지주",
        "finding": (
            "금융소비자 민원과 불완전판매 징후가 내부통제 회의체에 공유되지 않았고, 소비자보호 담당 부서와 "
            "준법감시 조직 간 재발방지 조치 협의가 지연되었다."
        ),
        "expected_focus": ["금융소비자", "불완전판매", "내부통제", "준법감시", "재발방지"],
    },
]


def _step_summary(result: AgentResult) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, step in enumerate(result.steps, start=1):
        observation_count = len(step.observation) if isinstance(step.observation, list) else 0
        rows.append(
            {
                "index": index,
                "tool": step.tool,
                "thought": step.thought,
                "args": step.args,
                "observation_count": observation_count,
            }
        )
    return rows


def _evaluate(case: dict[str, Any], result: AgentResult) -> dict[str, Any]:
    answer = result.answer or ""
    tools = [step.tool for step in result.steps]
    expected_hits = [term for term in case["expected_focus"] if term in answer]
    used_vector = "vector_search" in tools
    used_graph = "graph_search" in tools
    has_final = bool(answer.strip())
    has_action_words = any(term in answer for term in ["개선", "조치", "점검", "보고", "확인", "정비"])
    score = sum(
        [
            has_final,
            used_vector,
            used_graph,
            has_action_words,
            len(expected_hits) >= 2,
        ]
    )
    return {
        "score": score,
        "grade": "good" if score >= 4 else "fair" if score >= 3 else "poor",
        "used_vector_search": used_vector,
        "used_graph_search": used_graph,
        "expected_focus_hits": expected_hits,
        "has_actionable_recommendation": has_action_words,
        "notes": _evaluation_notes(used_vector, used_graph, has_action_words, expected_hits),
    }


def _evaluation_notes(
    used_vector: bool,
    used_graph: bool,
    has_action_words: bool,
    expected_hits: list[str],
) -> str:
    issues: list[str] = []
    if not used_vector:
        issues.append("vector RAG 미사용")
    if not used_graph:
        issues.append("graph search 미사용")
    if not has_action_words:
        issues.append("개선 조치 구체성 부족")
    if len(expected_hits) < 2:
        issues.append("핵심 주제 반영 부족")
    return "법령 RAG와 그래프를 모두 사용했고 개선 조치가 포함됨" if not issues else ", ".join(issues)


def _markdown_report(results: list[dict[str, Any]]) -> str:
    lines = [
        "# Audit Agent Evaluation Report",
        "",
        f"- Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"- Cases: {len(results)}",
        "",
        "## Summary",
        "",
        "| Case | Grade | Score | Vector | Graph | Focus Hits |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for row in results:
        evaluation = row["evaluation"]
        lines.append(
            "| {case_id} | {grade} | {score}/5 | {vector} | {graph} | {hits} |".format(
                case_id=row["id"],
                grade=evaluation["grade"],
                score=evaluation["score"],
                vector="yes" if evaluation["used_vector_search"] else "no",
                graph="yes" if evaluation["used_graph_search"] else "no",
                hits=", ".join(evaluation["expected_focus_hits"]) or "-",
            )
        )

    for row in results:
        lines.extend(
            [
                "",
                f"## {row['id']}",
                "",
                f"- Company: {row['company']}",
                f"- Finding: {row['finding']}",
                f"- Evaluation: {row['evaluation']['grade']} ({row['evaluation']['score']}/5)",
                f"- Notes: {row['evaluation']['notes']}",
                "",
                "### Tool Steps",
                "",
            ]
        )
        for step in row["steps"]:
            lines.append(
                f"{step['index']}. `{step['tool']}` observations={step['observation_count']} thought={step['thought']}"
            )
        lines.extend(["", "### Answer", "", row["answer"].strip() or "(empty answer)"])

    return "\n".join(lines) + "\n"


def main() -> None:
    agent = AuditFindingReActAgent(max_steps=8)
    results: list[dict[str, Any]] = []
    for case in CASES:
        result = agent.run(case["finding"], case["company"])
        results.append(
            {
                "id": case["id"],
                "company": case["company"],
                "finding": case["finding"],
                "expected_focus": case["expected_focus"],
                "answer": result.answer,
                "steps": _step_summary(result),
                "evaluation": _evaluate(case, result),
            }
        )

    report_dir = Path("reports")
    report_dir.mkdir(exist_ok=True)
    json_path = report_dir / "audit_agent_cases.json"
    md_path = report_dir / "audit_agent_report.md"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown_report(results), encoding="utf-8")
    print({"cases": len(results), "json": str(json_path), "report": str(md_path)})


if __name__ == "__main__":
    main()
