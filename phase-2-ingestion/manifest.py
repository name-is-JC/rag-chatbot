"""Ingestion manifest: tracks per-source content hash + last fetch time.

Used for change detection (Docs/RAG-Architecture.md §5 step 3) so unchanged
sources are skipped on re-ingestion.
"""
import json
from pathlib import Path

MANIFEST_PATH = Path("data/ingestion_manifest.json")


def load() -> dict:
    if not MANIFEST_PATH.exists():
        return {}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def save(manifest: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def has_changed(manifest: dict, url: str, new_hash: str) -> bool:
    entry = manifest.get(url)
    return entry is None or entry.get("content_hash") != new_hash


def update(manifest: dict, url: str, new_hash: str, fetched_at: str) -> None:
    manifest[url] = {"content_hash": new_hash, "last_fetched_at": fetched_at}
