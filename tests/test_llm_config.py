from src.legal_graph_rag.llm import resolve_llm_config


def test_qwen_direct_model_uses_vllm(monkeypatch) -> None:
    monkeypatch.setenv("activate_model_name", "Qwen/Qwen3.5-122B-A10B")
    monkeypatch.setenv("VLLM_BASE_URL", "http://vllm.example.test/v1")
    monkeypatch.setenv("VLLM_API_KEY", "test-key")
    monkeypatch.delenv("VLLM_ENABLE_THINKING", raising=False)

    config = resolve_llm_config()

    assert config["model"] == "Qwen/Qwen3.5-122B-A10B"
    assert config["base_url"] == "http://vllm.example.test/v1"
    assert config["api_key"] == "test-key"
    assert config["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}
