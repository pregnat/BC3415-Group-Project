"""Retrieve moomoo SG help-centre chunks for citations. OWNER: B."""
from __future__ import annotations

from contracts import Chunk

_STUB_CHUNKS = [
    Chunk(
        chunk_id="margin-call#1",
        text=(
            "If your account stays below the maintenance margin for more than 48 hours, "
            "your positions may be liquidated at any time."
        ),
        title="What is a margin call?",
        url="https://www.moomoo.com/sg/support/topic-TODO",
        score=0.9,
    ),
    Chunk(
        chunk_id="soft-edge#1",
        text=(
            "If your equity falls below the soft edge margin, your positions may be "
            "liquidated immediately. The soft edge may be raised before weekends or holidays."
        ),
        title="What is soft edge margin?",
        url="https://www.moomoo.com/sg/support/topic-TODO",
        score=0.8,
    ),
]


def search(query: str, k: int = 4) -> list[Chunk]:
    # TODO(B): replace with real index built by rag/ingest.py. Keep chunk_id stable across rebuilds.
    return _STUB_CHUNKS[:k]
