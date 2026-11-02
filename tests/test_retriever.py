"""OWNER: B. Retrieval quality checks."""
import pytest

from rag.retriever import search


@pytest.mark.skip(reason="TODO(B): enable once real index exists")
@pytest.mark.parametrize("query,expected_chunk_prefix", [
    ("what happens if I stay below maintenance margin for 2 days", "margin-call"),
    ("can I be liquidated immediately", "soft-edge"),
])
def test_top_hit(query, expected_chunk_prefix):
    assert search(query, k=1)[0].chunk_id.startswith(expected_chunk_prefix)
