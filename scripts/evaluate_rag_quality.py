from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import types
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRelevancyMetric,
    FaithfulnessMetric,
)
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase
from datasets import Dataset
from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI, OpenAI

from src.legal_graph_rag.config import Settings
from src.legal_graph_rag.embedding import HashingEmbedder
from src.legal_graph_rag.tools import graph_search, vector_search


def _install_ragas_vertexai_shim() -> None:
    # ragas 0.4.3 imports this legacy path during package initialization even
    # when VertexAI is not used. The actual judge below is OpenAI-compatible vLLM.
    module_name = "langchain_community.chat_models.vertexai"
    if module_name in sys.modules:
        return
    module = types.ModuleType(module_name)

    class ChatVertexAI:  # pragma: no cover - import shim only
        pass

    module.ChatVertexAI = ChatVertexAI
    sys.modules[module_name] = module


class LegalHashingEmbeddings(Embeddings):
    def __init__(self, dim: int) -> None:
        self.embedder = HashingEmbedder(dim)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embedder.embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self.embedder.embed(text)


class VllmDeepEvalModel(DeepEvalBaseLLM):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model_name = os.getenv("VLLM_MODEL_NAME") or os.getenv("LLM_MODEL") or "Qwen/Qwen3.6-35B-A3B-FP8"
        self.base_url = os.getenv("VLLM_BASE_URL")
        self.api_key = os.getenv("VLLM_API_KEY") or "EMPTY"
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        self.async_client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)
        super().__init__(model=self.model_name)

    def load_model(self) -> "VllmDeepEvalModel":
        return self

    def generate(self, prompt: str, schema: Any | None = None, **_: Any) -> str:
        if schema is not None:
            prompt = _schema_prompt(prompt, schema)
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=2048,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        return response.choices[0].message.content or ""

    async def a_generate(self, prompt: str, schema: Any | None = None, **_: Any) -> str:
        if schema is not None:
            prompt = _schema_prompt(prompt, schema)
        response = await self.async_client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=2048,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        return response.choices[0].message.content or ""

    def get_model_name(self) -> str:
        return f"vllm:{self.model_name}"


def _schema_prompt(prompt: str, schema: Any) -> str:
    try:
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    except Exception:
        schema_json = str(schema)
    return (
        f"{prompt}\n\n"
        "Return valid JSON only. Do not wrap it in markdown.\n"
        f"JSON schema: {schema_json}"
    )


def _truncate(text: str, limit: int = 1800) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit] + "..."


def _graph_row_to_context(row: dict[str, Any]) -> str:
    if row.get("kind") == "edge":
        return _truncate(
            "GRAPH EDGE: {source} -[{relation_type}]-> {target}. {description} chunk={chunk}".format(
                source=row.get("source", ""),
                relation_type=row.get("relation_type", ""),
                target=row.get("target", ""),
                description=row.get("description", ""),
                chunk=row.get("source_chunk_id", ""),
            ),
            900,
        )
    return _truncate(
        "GRAPH ENTITY: {name} type={entity_type}. {description} chunk={chunk}".format(
            name=row.get("name", ""),
            entity_type=row.get("entity_type", ""),
            description=row.get("description", ""),
            chunk=row.get("source_chunk_id", ""),
        ),
        900,
    )


def _build_eval_rows(cases: list[dict[str, Any]], cfg: Settings) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        query = case["finding"]
        vector_contexts = [
            _truncate(
                f"VECTOR CHUNK: {row.get('law_name')} {row.get('doc_type')} {row.get('heading')}\n{row.get('text')}",
                1800,
            )
            for row in vector_search(query, 5, cfg)
        ]
        graph_contexts = [_graph_row_to_context(row) for row in graph_search(query, 10, cfg)]
        retrieved_contexts = vector_contexts + graph_contexts
        reference = "핵심 평가 기준: " + ", ".join(case.get("expected_focus") or [])
        rows.append(
            {
                "id": case["id"],
                "user_input": query,
                "response": case["answer"],
                "reference": reference,
                "retrieved_contexts": retrieved_contexts,
            }
        )
    return rows


def _run_ragas(rows: list[dict[str, Any]], cfg: Settings) -> dict[str, Any]:
    _install_ragas_vertexai_shim()
    from ragas import evaluate
    from ragas.metrics import LLMContextPrecisionWithoutReference, answer_relevancy, faithfulness

    llm = ChatOpenAI(
        model=os.getenv("VLLM_MODEL_NAME") or "Qwen/Qwen3.6-35B-A3B-FP8",
        base_url=os.getenv("VLLM_BASE_URL"),
        api_key=os.getenv("VLLM_API_KEY") or "EMPTY",
        temperature=0,
        max_tokens=2048,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    dataset = Dataset.from_list(rows)
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, LLMContextPrecisionWithoutReference()],
        llm=llm,
        embeddings=LegalHashingEmbeddings(cfg.embed_dim),
        raise_exceptions=False,
        show_progress=True,
    )
    dataframe = result.to_pandas()
    records = json.loads(dataframe.to_json(orient="records", force_ascii=False))
    summary: dict[str, float | None] = {}
    for column in dataframe.columns:
        if column in {"user_input", "response", "reference", "retrieved_contexts"}:
            continue
        try:
            summary[column] = float(dataframe[column].mean())
        except Exception:
            summary[column] = None
    return {"summary": summary, "records": records}


def _run_deepeval(rows: list[dict[str, Any]], cfg: Settings) -> dict[str, Any]:
    model = VllmDeepEvalModel(cfg)
    metrics = [
        AnswerRelevancyMetric(model=model, threshold=0.5, include_reason=True, async_mode=False),
        FaithfulnessMetric(model=model, threshold=0.5, include_reason=True, async_mode=False),
        ContextualRelevancyMetric(model=model, threshold=0.5, include_reason=True, async_mode=False),
        ContextualPrecisionMetric(model=model, threshold=0.5, include_reason=True, async_mode=False),
    ]
    records: list[dict[str, Any]] = []
    for row in rows:
        test_case = LLMTestCase(
            input=row["user_input"],
            actual_output=row["response"],
            expected_output=row["reference"],
            retrieval_context=row["retrieved_contexts"],
        )
        metric_results: dict[str, Any] = {}
        for metric in metrics:
            name = metric.__class__.__name__
            try:
                score = metric.measure(test_case, _show_indicator=False, _log_metric_to_confident=False)
                metric_results[name] = {
                    "score": score,
                    "success": bool(metric.success),
                    "reason": getattr(metric, "reason", ""),
                }
            except Exception as exc:
                metric_results[name] = {"score": None, "success": False, "reason": f"{type(exc).__name__}: {exc}"}
        records.append({"id": row["id"], "metrics": metric_results})

    summary: dict[str, float | None] = {}
    for metric in metrics:
        name = metric.__class__.__name__
        scores = [record["metrics"][name]["score"] for record in records]
        numeric_scores = [score for score in scores if isinstance(score, (int, float))]
        summary[name] = sum(numeric_scores) / len(numeric_scores) if numeric_scores else None
    return {"summary": summary, "records": records}


def _markdown_report(results: dict[str, Any]) -> str:
    lines = [
        "# RAG Quality Evaluation",
        "",
        f"- Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"- Cases: {len(results['rows'])}",
        "- Judge: vLLM OpenAI-compatible endpoint",
        "",
        "## RAGAS Summary",
        "",
    ]
    for name, score in results["ragas"]["summary"].items():
        lines.append(f"- `{name}`: {_format_score(score)}")
    lines.extend(["", "## DeepEval Summary", ""])
    for name, score in results["deepeval"]["summary"].items():
        lines.append(f"- `{name}`: {_format_score(score)}")
    lines.extend(["", "## Case Details", ""])
    deepeval_by_id = {row["id"]: row for row in results["deepeval"]["records"]}
    ragas_by_id = {
        row.get("id") or results["rows"][index]["id"]: row
        for index, row in enumerate(results["ragas"]["records"])
    }
    for row in results["rows"]:
        lines.extend([f"### {row['id']}", ""])
        lines.append(f"- Contexts: {len(row['retrieved_contexts'])}")
        ragas_row = ragas_by_id.get(row["id"], {})
        for key, value in ragas_row.items():
            if key not in {"user_input", "response", "reference", "retrieved_contexts"}:
                lines.append(f"- RAGAS `{key}`: {_format_score(value)}")
        for metric_name, metric in deepeval_by_id[row["id"]]["metrics"].items():
            lines.append(
                f"- DeepEval `{metric_name}`: {_format_score(metric['score'])} "
                f"success={metric['success']} reason={_truncate(metric.get('reason', ''), 260)}"
            )
        lines.append("")
    return "\n".join(lines)


def _format_score(score: Any) -> str:
    if isinstance(score, (int, float)):
        return f"{float(score):.3f}"
    return "n/a"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="reports/audit_agent_cases.json")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--skip-ragas", action="store_true")
    parser.add_argument("--skip-deepeval", action="store_true")
    args = parser.parse_args()

    cfg = Settings()
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if args.limit:
        cases = cases[: args.limit]
    rows = _build_eval_rows(cases, cfg)

    results: dict[str, Any] = {"rows": rows}
    results["ragas"] = {"summary": {}, "records": []} if args.skip_ragas else _run_ragas(rows, cfg)
    results["deepeval"] = {"summary": {}, "records": []} if args.skip_deepeval else _run_deepeval(rows, cfg)

    report_dir = Path("reports")
    report_dir.mkdir(exist_ok=True)
    json_path = report_dir / "rag_quality_eval.json"
    md_path = report_dir / "rag_quality_eval.md"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown_report(results), encoding="utf-8")
    print({"cases": len(rows), "json": str(json_path), "report": str(md_path)})


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    main()
