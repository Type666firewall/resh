"""resh/encoder.py — Singleton sentence embedder multilingue.

Primary: `BAAI/bge-m3` (https://huggingface.co/BAAI/bge-m3) — italiano nativo,
contesto lungo, multilingue, FP16 su GPU.
Fallback model: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`
Fallback hash-based: bag-of-words sha256→dim (deterministico, AI-free, test-only).

API: `encode(frasi: list[str]) -> np.ndarray` shape (n_frasi, dim), L2-norm.

Override:
  - `P3_RESH_ENCODER_DISABLE=1` → forza fallback hash
  - `P3_RESH_ENCODER_MODEL=<name>` → override modello primary
  - `P3_RESH_ENCODER_DIM=<int>` → dim per fallback hash (default 384)

Singleton: il modello è caricato 1x al primo `encode()`, persistente in RAM/VRAM.
"""

from __future__ import annotations

import hashlib
import os
from typing import Optional

import numpy as np


DEFAULT_MODEL    = "BAAI/bge-m3"
FALLBACK_MODEL   = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
DEFAULT_HASH_DIM = 384


_MODEL = None
_MODEL_NAME: Optional[str] = None
_MODEL_DIM:  Optional[int] = None
_HASH_DIM:   int = int(os.getenv("P3_RESH_ENCODER_DIM", str(DEFAULT_HASH_DIM)))


def _encoder_disabled() -> bool:
    return os.getenv("P3_RESH_ENCODER_DISABLE") == "1"


def _active_dim() -> int:
    """Dimensione del backend ATTIVO: quella del modello se già caricato,
    altrimenti la dim del fallback hash. Evita che `encode([])` annunci 384
    mentre è caricato un modello a 1024 — un array vuoto con dim incoerente
    (W6) rompe le ops dim-specifiche (concatenazioni) a valle."""
    if _MODEL is not None and _MODEL is not False and _MODEL_DIM:
        return _MODEL_DIM
    return _HASH_DIM


def _try_load_model():
    global _MODEL, _MODEL_NAME, _MODEL_DIM
    if _MODEL is not None:
        return _MODEL
    try:
        from sentence_transformers import SentenceTransformer  # noqa: F401
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"

        name = os.getenv("P3_RESH_ENCODER_MODEL", DEFAULT_MODEL)
        # ml_registry: usa lo stesso slot di bge-m3 se è quel modello
        try:
            from ml_registry import acquire as _ml_acquire
            _ml_acquire("bge-m3" if "bge" in name.lower() else "sentence-transformer-other")
        except Exception:
            pass
        try:
            _MODEL = SentenceTransformer(name, device=device)
        except Exception as exc_primary:
            print(f"[resh.encoder] primary {name} failed: {exc_primary} — fallback {FALLBACK_MODEL}")
            _MODEL = SentenceTransformer(FALLBACK_MODEL, device=device)
            name = FALLBACK_MODEL

        if device == "cuda":
            try:
                _MODEL.half()    # FP16
            except Exception:
                pass

        _MODEL_NAME = name
        # API rinominata in sentence-transformers recenti; getattr copre entrambe
        _get_dim = getattr(_MODEL, "get_embedding_dimension", None) or _MODEL.get_sentence_embedding_dimension
        _MODEL_DIM  = _get_dim()
        return _MODEL
    except Exception as exc:
        print(f"[resh.encoder] sentence-transformers non disponibile, fallback hash: {exc}")
        _MODEL = False        # sentinel: tried+failed
        return None


def _hash_encode(text: str, dim: int) -> np.ndarray:
    """Bag-of-words → sha256 token → bucket(dim). L2-normalizzato."""
    v = np.zeros(dim, dtype=np.float32)
    for tok in text.lower().split():
        clean = "".join(c for c in tok if c.isalnum())
        if not clean:
            continue
        idx = int(hashlib.sha256(clean.encode("utf-8")).hexdigest(), 16) % dim
        v[idx] += 1.0
    n = float(np.linalg.norm(v))
    if n == 0.0:
        v[0] = 1.0
    else:
        v /= n
    return v


def encode(frasi: list[str]) -> np.ndarray:
    """Encode list[str] → np.ndarray (n, dim), float32, L2-normalizzato.

    Lazy singleton. Se sentence-transformers assente → hash fallback (dim
    da env `P3_RESH_ENCODER_DIM`, default 384).
    """
    if not frasi:
        return np.zeros((0, _active_dim()), dtype=np.float32)
    if _encoder_disabled():
        return np.stack([_hash_encode(s, _HASH_DIM) for s in frasi]).astype(np.float32)
    model = _try_load_model()
    if model is None or model is False:
        return np.stack([_hash_encode(s, _HASH_DIM) for s in frasi]).astype(np.float32)
    embs = model.encode(
        frasi,
        batch_size            = 32,
        normalize_embeddings  = True,
        show_progress_bar     = False,
        convert_to_numpy      = True,
    )
    return embs.astype(np.float32)


def encode_one(testo: str) -> np.ndarray:
    """Single text → (dim,) vector."""
    return encode([testo])[0]


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity tra due vettori già L2-normalizzati."""
    return float(np.dot(a, b))


def reset_singleton() -> None:
    """Forza ricarica del modello al prossimo encode()."""
    global _MODEL, _MODEL_NAME, _MODEL_DIM
    _MODEL = None
    _MODEL_NAME = None
    _MODEL_DIM = None


def backend_info() -> str:
    if _encoder_disabled():
        return f"hash-fallback (dim={_HASH_DIM}, P3_RESH_ENCODER_DISABLE=1)"
    if _MODEL is None:
        return "lazy (not loaded)"
    if _MODEL is False:
        return f"hash-fallback (sentence-transformers unavailable, dim={_HASH_DIM})"
    return f"{_MODEL_NAME} (dim={_MODEL_DIM})"
