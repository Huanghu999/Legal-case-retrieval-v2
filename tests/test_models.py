from src.legal_case_rag.retrieval.models import ChunkHit


def test_chunk_hit_accepts_constructor_arguments():
    hit = ChunkHit(
        chunk_id="c1",
        doc_id="d1",
        score=1.5,
        chunk_text="hello",
    )

    assert hit.chunk_id == "c1"
    assert hit.doc_id == "d1"
    assert hit.score == 1.5
    assert hit.chunk_text == "hello"
