from __future__ import annotations

import os
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
SOURCE_DIR = PACKAGE_DIR.parent
DEFAULT_ROOT = SOURCE_DIR.parent


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_env_file(DEFAULT_ROOT / ".env")
load_env_file(SOURCE_DIR / ".env")


POC_ROOT = Path(os.environ.get("POC_ROOT", str(DEFAULT_ROOT))).resolve()
DATA_DIR = Path(os.environ.get("POC_DATA_DIR", str(POC_ROOT / "data"))).resolve()
ARTIFACTS_DIR = Path(os.environ.get("POC_ARTIFACTS_DIR", str(POC_ROOT / "artifacts"))).resolve()
GRAPH_DIR = ARTIFACTS_DIR / "graph"
WIKI_DIR = ARTIFACTS_DIR / "wiki"
TRACES_DIR = ARTIFACTS_DIR / "traces"

VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1").rstrip("/")
VLLM_API_KEY = os.environ.get("VLLM_API_KEY", "EMPTY")
VLLM_MODEL_NAME = os.environ.get("VLLM_MODEL_NAME", "")
VLLM_ENABLE_THINKING = os.environ.get("VLLM_ENABLE_THINKING", "false").lower() in {"1", "true", "yes", "y"}

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "vllm").strip().lower()
GRAPHIFY_BATCH = os.environ.get("GRAPHIFY_BATCH", os.environ.get("LLM_BATCH", "false")).lower() in {"1", "true", "yes", "y"}
LLM_BATCH_POLL_SECONDS = int(os.environ.get("LLM_BATCH_POLL_SECONDS", "15"))
LLM_BATCH_MAX_WAIT_SECONDS = int(os.environ.get("LLM_BATCH_MAX_WAIT_SECONDS", "0"))

OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL_NAME = os.environ.get("OPENAI_MODEL_NAME", os.environ.get("OPENAI_MODEL", "gpt-5.4-mini"))


def active_model_name() -> str:
    if LLM_PROVIDER == "openai":
        return OPENAI_MODEL_NAME
    return VLLM_MODEL_NAME


def active_base_url() -> str:
    if LLM_PROVIDER == "openai":
        return OPENAI_BASE_URL
    return VLLM_BASE_URL


def active_api_key() -> str:
    if LLM_PROVIDER == "openai":
        return OPENAI_API_KEY
    return VLLM_API_KEY
