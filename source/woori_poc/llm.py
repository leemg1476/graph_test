from __future__ import annotations

import json
from typing import Any

import httpx

from .config import (
    LLM_PROVIDER,
    VLLM_ENABLE_THINKING,
    active_api_key,
    active_base_url,
    active_model_name,
)


def chat_json(system: str, user: str, timeout: float = 120.0) -> dict[str, Any]:
    content = chat_text(system, user, timeout=timeout)
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(content[start : end + 1])
        except json.JSONDecodeError:
            pass
    return {"raw": content}


def chat_text(system: str, user: str, timeout: float = 120.0) -> str:
    model_name = active_model_name()
    if not model_name:
        raise RuntimeError("active LLM model is not configured")
    payload: dict[str, Any] = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
    }
    if LLM_PROVIDER == "vllm" and not VLLM_ENABLE_THINKING:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    headers = {"Authorization": f"Bearer {active_api_key()}"}
    with httpx.Client(timeout=timeout) as client:
        response = client.post(f"{active_base_url()}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"]
