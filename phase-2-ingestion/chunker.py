"""Generic fixed-size, boundary-aware chunking (Docs/Ingestion-Architecture.md §3.3).

Confirmed 2026-09-06: generic fixed-size chunking, applied uniformly to all
source types. Splits on paragraph boundaries first, then sentence boundaries,
then falls back to a hard token cutoff — while staying "generic" (no
field/label-aware logic). Token counts use the actual embedding model's
tokenizer so the 256-token model limit is respected exactly, not estimated.
"""
import re

from transformers import AutoTokenizer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_CACHE_DIR = "./.model_cache"

CHUNK_SIZE_TOKENS = 200
OVERLAP_TOKENS = 40
MIN_CHUNK_TOKENS = 20

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z₹])")

_tokenizer = None


def _get_tokenizer():
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, cache_dir=MODEL_CACHE_DIR)
    return _tokenizer


def count_tokens(text: str) -> int:
    return len(_get_tokenizer().encode(text, add_special_tokens=False))


def _split_sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]


def _hard_cut(text: str, max_tokens: int) -> list[str]:
    """Last-resort split for a single sentence longer than max_tokens."""
    tokenizer = _get_tokenizer()
    ids = tokenizer.encode(text, add_special_tokens=False)
    pieces = []
    for i in range(0, len(ids), max_tokens):
        pieces.append(tokenizer.decode(ids[i : i + max_tokens]))
    return pieces


def _units_for_block(block: dict) -> list[dict]:
    """Breaks one parsed block into sentence-level (or smaller) units, each tagged with section_hint."""
    text, section_hint = block["text"], block["section_hint"]
    if count_tokens(text) <= CHUNK_SIZE_TOKENS:
        return [{"text": text, "section_hint": section_hint}]

    units = []
    for sentence in _split_sentences(text):
        if count_tokens(sentence) <= CHUNK_SIZE_TOKENS:
            units.append({"text": sentence, "section_hint": section_hint})
        else:
            for piece in _hard_cut(sentence, CHUNK_SIZE_TOKENS):
                units.append({"text": piece, "section_hint": section_hint})
    return units


def chunk_blocks(blocks: list[dict]) -> list[dict]:
    """Packs parsed blocks into ~CHUNK_SIZE_TOKENS chunks with OVERLAP_TOKENS overlap."""
    units = [u for block in blocks for u in _units_for_block(block)]
    if not units:
        return []

    chunks: list[dict] = []
    current_units: list[dict] = []
    current_tokens = 0

    def flush():
        if not current_units:
            return
        text = " ".join(u["text"] for u in current_units)
        chunks.append(
            {
                "text": text,
                "token_count": count_tokens(text),
                "section_hint": current_units[0]["section_hint"],
            }
        )

    for unit in units:
        unit_tokens = count_tokens(unit["text"])
        if current_tokens + unit_tokens > CHUNK_SIZE_TOKENS and current_units:
            flush()
            # Carry overlap: keep trailing units worth ~OVERLAP_TOKENS from the chunk just flushed.
            overlap_units, overlap_tokens = [], 0
            for u in reversed(current_units):
                t = count_tokens(u["text"])
                if overlap_tokens + t > OVERLAP_TOKENS:
                    break
                overlap_units.insert(0, u)
                overlap_tokens += t
            current_units = overlap_units
            current_tokens = overlap_tokens

        current_units.append(unit)
        current_tokens += unit_tokens

    flush()

    # Merge a too-small trailing chunk into the previous one.
    if len(chunks) > 1 and chunks[-1]["token_count"] < MIN_CHUNK_TOKENS:
        last = chunks.pop()
        merged_text = chunks[-1]["text"] + " " + last["text"]
        chunks[-1] = {
            "text": merged_text,
            "token_count": count_tokens(merged_text),
            "section_hint": chunks[-1]["section_hint"],
        }

    for i, c in enumerate(chunks):
        c["chunk_index"] = i

    return chunks
