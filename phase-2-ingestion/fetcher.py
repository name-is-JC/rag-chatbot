"""Fetches source pages and caches them locally (Docs/Ingestion-Architecture.md §3.1).

Note: change detection does NOT hash this raw HTML (see manifest.py / run_ingestion.py) —
some pages embed per-request randomized content unrelated to the actual data
(e.g. Cloudflare's email-obfuscation script re-randomizes its XOR key on every
request), which would make a raw-HTML hash falsely "change" on every fetch.
Change detection instead hashes the parsed/rendered content, downstream of this.
"""
import re
from pathlib import Path

import requests

RAW_CACHE_DIR = Path("data/raw")
USER_AGENT = "Mozilla/5.0 (compatible; MF-FAQ-Assistant-Ingestion/1.0)"


def _slug_for(url: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", url).strip("-")
    return slug[-150:]


def fetch(url: str) -> str:
    """Downloads a URL and returns the raw HTML text. Caches a copy to data/raw/."""
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    raw_text = response.text

    RAW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = RAW_CACHE_DIR / f"{_slug_for(url)}.html"
    cache_path.write_text(raw_text, encoding="utf-8")

    return raw_text
