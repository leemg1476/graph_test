from src.legal_graph_rag.tools import _normalize_key, _query_terms, _rank_seed_entities


def test_query_terms_extracts_korean_legal_entities() -> None:
    query = "\uc900\ubc95\uac10\uc2dc\uc778 \uac1c\uc120\uad8c\uace0 \uc774\uc0ac\ud68c \uac10\uc0ac\uc704\uc6d0\ud68c \ubcf4\uace0 \ub204\ub77d"

    terms = _query_terms(query)

    assert "\uc900\ubc95\uac10\uc2dc\uc778" in terms
    assert "\uac10\uc0ac\uc704\uc6d0\ud68c" in terms
    assert "\ubcf4\uace0" not in terms


def test_normalize_key_keeps_hangul_and_removes_spacing() -> None:
    assert _normalize_key("\uc900\ubc95 \uac10\uc2dc\uc778") == "\uc900\ubc95\uac10\uc2dc\uc778"


def test_rank_seed_entities_uses_query_vector_similarity() -> None:
    entities = [
        {
            "id": 1,
            "name": "\uac00\uc0c1\uc790\uc0b0\uc0ac\uc5c5\uc790",
            "canonical_name": "\uac00\uc0c1\uc790\uc0b0\uc0ac\uc5c5\uc790",
            "entity_type": "\uae08\uc735\ud68c\uc0ac",
            "description": "\uac00\uc0c1\uc790\uc0b0 \ubcf4\uad00 \ubc0f \uc774\uc6a9\uc790 \ubcf4\ud638",
            "aliases": [],
            "alias_keys": [],
            "source_chunk_id": 1,
        },
        {
            "id": 2,
            "name": "\uc900\ubc95\uac10\uc2dc\uc778",
            "canonical_name": "\uc900\ubc95\uac10\uc2dc\uc778",
            "entity_type": "\ub0b4\ubd80\ud1b5\uc81c",
            "description": "\uc774\uc0ac\ud68c \ubcf4\uace0 \ubc0f \uac1c\uc120\uad8c\uace0 \uc774\ud589 \uc810\uac80",
            "aliases": ["\uc900\ubc95 \uac10\uc2dc\uc778"],
            "alias_keys": ["\uc900\ubc95\uac10\uc2dc\uc778"],
            "source_chunk_id": 2,
        },
    ]

    ranked = _rank_seed_entities(
        entities,
        "\uc900\ubc95\uac10\uc2dc\uc778 \uc774\uc0ac\ud68c \ubcf4\uace0 \ub204\ub77d",
        ["\uc900\ubc95\uac10\uc2dc\uc778", "\uc774\uc0ac\ud68c", "\ub204\ub77d"],
        dim=128,
        limit=2,
    )

    assert ranked[0]["id"] == 2
    assert ranked[0]["vector_score"] > 0
