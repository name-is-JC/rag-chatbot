"""Phase 2 ingestion entry point: fetch -> parse -> chunk -> embed -> store.

Reads the source list from Docs/sources.csv, skips unchanged sources (via
the manifest content hash), and for changed/new sources runs the full
pipeline described in Docs/Ingestion-Architecture.md.
"""
import csv
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

import chunker
import embedder
import fetcher
import manifest
import parser
import store

SOURCES_CSV = Path("Docs/sources.csv")


def load_sources() -> list[dict]:
    with SOURCES_CSV.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def process_source(source: dict, current_manifest: dict) -> str:
    url = source["url"]
    raw_html = fetcher.fetch(url)
    blocks = parser.parse(raw_html)

    # Hash the parsed content, not the raw HTML: some pages embed per-request
    # randomized content unrelated to the actual data (see fetcher.py), which
    # would make a raw-HTML hash falsely "change" on every fetch.
    content_hash = hashlib.sha256(
        "\n".join(b["text"] for b in blocks).encode("utf-8")
    ).hexdigest()

    if not manifest.has_changed(current_manifest, url, content_hash):
        return "unchanged"

    chunks = chunker.chunk_blocks(blocks)

    if chunks:
        vectors = embedder.embed([c["text"] for c in chunks])
        for c, v in zip(chunks, vectors):
            c["embedding"] = v

    fetched_at = datetime.now(timezone.utc).date().isoformat()
    inserted = store.replace_source_chunks(
        source_url=url,
        content_hash=content_hash,
        chunks=chunks,
        source_meta=source,
        last_fetched_at=fetched_at,
    )
    manifest.update(current_manifest, url, content_hash, fetched_at)
    return f"refreshed ({inserted} chunks)"


def main() -> int:
    sources = load_sources()
    current_manifest = manifest.load()

    results = []
    for source in sources:
        try:
            outcome = process_source(source, current_manifest)
            results.append((source["scheme_name"], outcome))
        except Exception as exc:  # noqa: BLE001 - a failed source keeps its last-good data; others still proceed
            results.append((source["scheme_name"], f"FAILED: {exc}"))

    manifest.save(current_manifest)

    print("Ingestion run summary:")
    for scheme_name, outcome in results:
        print(f"  - {scheme_name}: {outcome}")

    # Per-source failures are logged above but don't fail the run: a source that
    # errors keeps serving its last successfully ingested data (RAG-Architecture.md
    # §5), while other sources' successful updates still get committed.
    return 0


if __name__ == "__main__":
    sys.exit(main())
