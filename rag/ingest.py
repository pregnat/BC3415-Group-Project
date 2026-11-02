"""Chunk rag/corpus/ and build the Chroma index. OWNER: B.  Run: python -m rag.ingest"""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).parent
CORPUS = ROOT / "corpus"
MANIFEST = ROOT / "corpus_manifest.csv"
INDEX_DIR = ROOT / "index"
COLLECTION = "help_centre"
MAX_CHARS = 600
OVERLAP_MAX_CHARS = 250


def _blocks(text: str) -> list[str]:
    """Split into lines, keeping each table whole so a row never loses its header."""
    blocks: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if " | " in line and blocks and " | " in blocks[-1]:
            blocks[-1] += "\n" + line
        else:
            blocks.append(line)
    return blocks


def chunk_text(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    """Greedy chunks of whole blocks, deterministic so chunk ids stay stable across rebuilds.
    A short last block is repeated at the start of the next chunk, so a list keeps its lead-in."""
    chunks: list[str] = []
    current: list[str] = []
    for block in _blocks(text):
        if current and len("\n".join(current + [block])) > max_chars:
            chunks.append("\n".join(current))
            last = current[-1]
            current = [last] if len(last) <= OVERLAP_MAX_CHARS and " | " not in last else []
        current.append(block)
    if current:
        chunks.append("\n".join(current))
    return chunks


def load_chunks() -> list[dict]:
    with MANIFEST.open(newline="", encoding="utf-8") as f:
        sources = list(csv.DictReader(f))
    chunks = []
    for source in sources:
        path = CORPUS / source["chunk_source_file"]
        for i, text in enumerate(chunk_text(path.read_text(encoding="utf-8"))):
            chunks.append({
                "chunk_id": f"{path.stem}#{i}",
                "text": text,
                "title": source["title"],
                "url": source["url"],
                # Help-centre pages show no publish date, so this is the date we fetched them.
                "date": source["fetched_on"],
                "product": source["product"],
            })
    return chunks


def build_index():
    """Rebuild the index from scratch and return the collection."""
    import chromadb
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

    client = chromadb.PersistentClient(path=str(INDEX_DIR))
    if COLLECTION in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION)
    collection = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
    chunks = load_chunks()
    # Embed with the title so chunks that never name their topic still match; store the raw text.
    embeddings = DefaultEmbeddingFunction()([f"{c['title']}\n{c['text']}" for c in chunks])
    collection.add(
        ids=[c["chunk_id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        embeddings=embeddings,
        metadatas=[{k: c[k] for k in ("title", "url", "date", "product")} for c in chunks],
    )
    return collection


if __name__ == "__main__":
    print(f"{build_index().count()} chunks -> {INDEX_DIR}")
