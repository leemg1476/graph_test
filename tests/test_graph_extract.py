from src.legal_graph_rag.graph_extract import (
    _canonical_key,
    _json_from_text,
    _normalize_key,
    _safe_edge_type,
    _safe_label,
)


def test_json_from_markdown_fenced_response() -> None:
    payload = _json_from_text('```json\n{"entities": [], "edges": []}\n```')

    assert payload == {"entities": [], "edges": []}


def test_safe_graph_identifiers() -> None:
    assert _safe_label("금융 회사/기관") == "금융_회사_기관"
    assert _safe_edge_type("보고 대상") == "RELATED_TO"
    assert _safe_edge_type("reports-to") == "RELATED_TO"
    assert _safe_edge_type("changed_to") == "CHANGED_TO"


def test_canonical_key_normalizes_aliases_without_pairwise_matching() -> None:
    assert _normalize_key("금융 위원회") == _normalize_key("금융위원회")
    assert _canonical_key("금융위원회", "감독기관") == _canonical_key("금융 위원회", "감독기관")
