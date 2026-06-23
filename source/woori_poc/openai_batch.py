from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .config import (
    LLM_BATCH_MAX_WAIT_SECONDS,
    LLM_BATCH_POLL_SECONDS,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL_NAME,
)


@dataclass
class BatchTask:
    custom_id: str
    system: str
    user: str
    response_format: dict[str, Any] | None = None


def _client():
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    from openai import OpenAI

    return OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)


def write_batch_jsonl(tasks: Iterable[BatchTask], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as fp:
        for task in tasks:
            body: dict[str, Any] = {
                "model": OPENAI_MODEL_NAME,
                "messages": [
                    {"role": "system", "content": task.system},
                    {"role": "user", "content": task.user},
                ],
                "temperature": 0.1,
            }
            if task.response_format:
                body["response_format"] = task.response_format
            fp.write(
                json.dumps(
                    {
                        "custom_id": task.custom_id,
                        "method": "POST",
                        "url": "/v1/chat/completions",
                        "body": body,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            count += 1
    return count


def submit_batch(input_jsonl: Path, metadata: dict[str, str] | None = None) -> dict[str, Any]:
    client = _client()
    with input_jsonl.open("rb") as fp:
        uploaded = client.files.create(file=fp, purpose="batch")
    batch = client.batches.create(
        input_file_id=uploaded.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata=metadata or {},
    )
    return batch.model_dump()


def retrieve_batch(batch_id: str) -> dict[str, Any]:
    batch = _client().batches.retrieve(batch_id)
    return batch.model_dump()


def maybe_wait_for_batch(batch_id: str, max_wait_seconds: int | None = None) -> dict[str, Any]:
    max_wait = LLM_BATCH_MAX_WAIT_SECONDS if max_wait_seconds is None else max_wait_seconds
    status = retrieve_batch(batch_id)
    if max_wait <= 0:
        return status
    deadline = time.time() + max_wait
    while status.get("status") not in {"completed", "failed", "expired", "cancelled"} and time.time() < deadline:
        time.sleep(LLM_BATCH_POLL_SECONDS)
        status = retrieve_batch(batch_id)
    return status


def download_batch_output(batch_id: str, output_jsonl: Path) -> dict[str, Any]:
    status = retrieve_batch(batch_id)
    output_file_id = status.get("output_file_id")
    if not output_file_id:
        return status
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    content = _client().files.content(output_file_id)
    output_jsonl.write_bytes(content.read())
    return status


def parse_chat_output(output_jsonl: Path) -> dict[str, str]:
    outputs: dict[str, str] = {}
    if not output_jsonl.exists():
        return outputs
    for line in output_jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        custom_id = row.get("custom_id")
        body = row.get("response", {}).get("body", {})
        choices = body.get("choices") or []
        if custom_id and choices:
            outputs[custom_id] = choices[0].get("message", {}).get("content", "")
    return outputs


def submit_or_collect(
    tasks: list[BatchTask],
    batch_dir: Path,
    job_name: str,
    wait: bool = False,
) -> tuple[dict[str, str], dict[str, Any]]:
    batch_dir.mkdir(parents=True, exist_ok=True)
    input_jsonl = batch_dir / f"{job_name}_input.jsonl"
    output_jsonl = batch_dir / f"{job_name}_output.jsonl"
    status_json = batch_dir / f"{job_name}_batch.json"

    if output_jsonl.exists():
        return parse_chat_output(output_jsonl), json.loads(status_json.read_text(encoding="utf-8")) if status_json.exists() else {}

    if status_json.exists():
        status = json.loads(status_json.read_text(encoding="utf-8"))
    else:
        write_batch_jsonl(tasks, input_jsonl)
        status = submit_batch(input_jsonl, {"job": job_name})
        status_json.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    if wait:
        status = maybe_wait_for_batch(status["id"])
        status_json.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    if status.get("status") == "completed":
        status = download_batch_output(status["id"], output_jsonl)
        status_json.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        return parse_chat_output(output_jsonl), status

    return {}, status
