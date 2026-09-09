"""Local embedding generation (Docs/Ingestion-Architecture.md §3.5).

Model cache is redirected inside the project folder (not the OS user-profile
default) to honor the project's storage rule; that folder is gitignored.
"""
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
MODEL_CACHE_DIR = "./.model_cache"
BATCH_SIZE = 32

_model = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME, cache_folder=MODEL_CACHE_DIR)
    return _model


def embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    vectors = _get_model().encode(texts, batch_size=BATCH_SIZE, show_progress_bar=False)
    return vectors.tolist()
