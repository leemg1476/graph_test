from src.legal_graph_rag.chunking import LegalDocument, chunk_document


def test_chunk_document_preserves_metadata() -> None:
    doc = LegalDocument(
        law_name="금융회사의지배구조에관한법률",
        doc_type="법률",
        source_path="kr/sample/법률.md",
        text="# 제목\n제1조 목적\n금융회사의 내부통제와 준법감시를 정한다." * 20,
        sha256="x",
    )

    chunks = chunk_document(doc, max_chars=100, overlap_chars=10)

    assert chunks
    assert chunks[0].law_name == doc.law_name
    assert chunks[0].source_path == doc.source_path
    assert all(chunk.token_estimate > 0 for chunk in chunks)

