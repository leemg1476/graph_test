from src.legal_graph_rag.embedding import HashingEmbedder


def test_korean_ngram_embedding_has_overlap_for_compound_terms() -> None:
    embedder = HashingEmbedder(128)
    query = embedder.embed("금융지주 내부통제")
    text = embedder.embed("금융지주회사는 내부통제기준을 마련한다")

    score = sum(a * b for a, b in zip(query, text))

    assert score > 0
