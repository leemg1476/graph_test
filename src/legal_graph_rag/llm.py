from __future__ import annotations

import os
from typing import Any

from langchain_openai import ChatOpenAI


def _env_value(*keys: str) -> str:
    for key in keys:
        value = os.getenv(key)
        if value and value.strip():
            return value.strip()
    return ""


def _looks_like_vllm_model(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized.startswith(("qwen", "llama", "mistral", "deepseek", "yi", "mixtral", "vllm/"))


def resolve_llm_config(
    *,
    temperature: float = 0,
    max_tokens: int = 4096,
    enable_thinking: bool | None = None,
) -> dict[str, Any]:
    active = _env_value("activate_model_name", "ACTIVATE_MODEL_NAME")
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    model = ""

    if active:
        if ":" in active:
            prefix, selected = active.split(":", 1)
            prefix = prefix.strip().lower()
            if prefix in {"vllm", "local"}:
                provider = "vllm"
                model = selected.strip()
            elif prefix in {"openai", "gpt"}:
                provider = "openai"
                model = selected.strip()
        elif active.lower() in {"vllm", "local"}:
            provider = "vllm"
        elif active.lower() in {"openai", "gpt"}:
            provider = "openai"
        elif _looks_like_vllm_model(active):
            provider = "vllm"
            model = active
        else:
            provider = "openai"
            model = active

    if not provider:
        provider = "vllm" if os.getenv("USE_VLLM", "").lower() in {"1", "true", "yes", "y"} else "openai"

    if provider == "vllm":
        model = model or os.getenv("VLLM_MODEL_NAME") or "Qwen/Qwen3.5-122B-A10B"
        if enable_thinking is None:
            enable_thinking = os.getenv("VLLM_ENABLE_THINKING", "false").lower() in {
                "1",
                "true",
                "yes",
                "y",
                "on",
            }
        return {
            "model": model,
            "base_url": os.getenv("VLLM_BASE_URL"),
            "api_key": os.getenv("VLLM_API_KEY") or "EMPTY",
            "temperature": temperature,
            "max_tokens": max_tokens,
            "extra_body": {"chat_template_kwargs": {"enable_thinking": enable_thinking}},
        }

    model = model or os.getenv("OPENAI_MODEL") or os.getenv("LLM_MODEL") or "gpt-5.4-mini"
    config: dict[str, Any] = {
        "model": model,
        "api_key": os.getenv("OPENAI_API_KEY"),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if os.getenv("OPENAI_BASE_URL"):
        config["base_url"] = os.getenv("OPENAI_BASE_URL")
    return config


def make_chat_model(**overrides: Any) -> ChatOpenAI:
    config = resolve_llm_config(**overrides)
    return ChatOpenAI(**config)

