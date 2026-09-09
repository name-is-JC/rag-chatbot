"""Chroma vector store access (Docs/Ingestion-Architecture.md §3.6, RAG-Architecture.md §9).

Delete-and-reinsert per source_url on change, rather than per-chunk upsert,
since chunk boundaries can shift entirely when a page's content changes.
"""
import hashlib

import chromadb

CHROMA_PATH = "data/chroma"
COLLECTION_NAME = "mf_faq_chunks"

_client = None


def _get_collection():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
    return _client.get_or_create_collection(
        name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )


def _chunk_id(source_url: str, chunk_index: int, content_hash: str) -> str:
    raw = f"{source_url}|{chunk_index}|{content_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def replace_source_chunks(
    source_url: str,
    content_hash: str,
    chunks: list[dict],
    source_meta: dict,
    last_fetched_at: str,
) -> int:
    """Deletes any existing chunks for source_url, then inserts the new set. Returns count inserted."""
    collection = _get_collection()
    collection.delete(where={"source_url": source_url})

    if not chunks:
        return 0

    ids = [_chunk_id(source_url, c["chunk_index"], content_hash) for c in chunks]
    documents = [c["text"] for c in chunks]
    embeddings = [c["embedding"] for c in chunks]
    metadatas = [
        {
            "source_url": source_url,
            "doc_type": source_meta["doc_type"],
            "scheme_name": source_meta["scheme_name"],
            "amc_name": source_meta["amc_name"],
            "last_fetched_at": last_fetched_at,
            "chunk_index": c["chunk_index"],
            "token_count": c["token_count"],
            "section_hint": c["section_hint"] or "",
        }
        for c in chunks
    ]

    collection.add(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
    return len(ids)
