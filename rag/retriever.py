"""Retrieve moomoo SG help-centre chunks for citations. OWNER: B."""
from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from contracts import Chunk
from rag.ingest import COLLECTION, INDEX_DIR, build_index

# Calibrated on 14 on-topic queries (lowest best score 0.337) and 12 off-topic (highest 0.333).
# The ranges touch, so this keeps every on-topic query and lets a few off-topic ones through.
SCORE_THRESHOLD = 0.30
RRF_K = 60  # standard reciprocal-rank-fusion constant

_collection = None


def _get_collection():
    """Open the index, building it from rag/corpus/ on first use (it isn't committed)."""
    global _collection
    if _collection is None:
        import chromadb

        client = chromadb.PersistentClient(path=str(INDEX_DIR))
        if COLLECTION in [c.name for c in client.list_collections()]:
            _collection = client.get_collection(COLLECTION)
        else:
            _collection = build_index()
    return _collection


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _keyword_ranks(query: str, ids: list[str], metadatas: list[dict], texts: list[str]) -> dict[str, int]:
    corpus = [_tokens(f"{m['title']} {t}") for m, t in zip(metadatas, texts)]
    scores = BM25Okapi(corpus).get_scores(_tokens(query))
    order = sorted(range(len(ids)), key=lambda i: -scores[i])
    return {ids[i]: rank for rank, i in enumerate(order)}


def retrieve(query: str, product: str | None = "securities_margin", k: int = 5) -> list[dict]:
    """Top-k chunks as [{chunk_id, text, title, url, date, product, score}], best first.
    Ranked by embeddings + BM25, because embeddings alone miss "A vs B" questions. score is the
    cosine similarity. Empty list if nothing clears SCORE_THRESHOLD. product=None searches all."""
    collection = _get_collection()
    where = {"product": product} if product else None
    n = len(collection.get(where=where, include=[])["ids"])
    if n == 0:
        return []
    result = collection.query(query_texts=[query], n_results=n, where=where)
    ids, texts, metadatas = result["ids"][0], result["documents"][0], result["metadatas"][0]
    keyword_rank = _keyword_ranks(query, ids, metadatas, texts)
    hits = []
    for dense_rank, (chunk_id, text, meta, distance) in enumerate(zip(ids, texts, metadatas, result["distances"][0])):
        score = 1 - distance
        if score >= SCORE_THRESHOLD:
            fused = 1 / (RRF_K + dense_rank) + 1 / (RRF_K + keyword_rank[chunk_id])
            hits.append((fused, {"chunk_id": chunk_id, "text": text, **meta, "score": score}))
    hits.sort(key=lambda h: -h[0])
    return [hit for _, hit in hits[:k]]


def search(query: str, k: int = 4) -> list[Chunk]:
    return [
        Chunk(chunk_id=h["chunk_id"], text=h["text"], title=h["title"], url=h["url"], score=h["score"])
        for h in retrieve(query, k=k)
    ]
