"""resh/_nli.py — Singleton zero-shot NLI (private helper).

Modello: `MoritzLaurer/deberta-v3-base-zeroshot-v2.0`
(https://huggingface.co/MoritzLaurer/deberta-v3-base-zeroshot-v2.0).
Training: MNLI+FEVER+ANLI+WANLI+LingNLI + dati sintetici Mixtral (gen 2025).
Label scheme 2-classi: {entailment, not_entailment} (∼550MB, API HF pipeline).

API:
  - `classify_zero_shot(sequences, labels, hypothesis_template=...) -> list[dict]`
  - `entail(premise, hypothesis) -> float`   # p(ENTAILMENT) ∈ [0,1]

Fallback: se transformers assente o modello non scaricabile, ogni funzione
ritorna struttura neutra (label=None, confidence=0.0) — i moduli consumer
devono gestire `confidence==0.0` come "skip questa rilevazione".

Env: `P3_RESH_NLI_DISABLE=1` forza fallback. `P3_RESH_NLI_MODEL=<hf-id>`
override modello.
"""

from __future__ import annotations

import os
import threading
from typing import Optional


_NLI_PIPELINE = None
_NLI_ENTAIL_PIPELINE = None
_NLI_TRIED  = False
_NLI_MODEL  = "MoritzLaurer/deberta-v3-base-zeroshot-v2.0"

# Lock per il lazy-load dei singleton: la pipeline gira sotto `asyncio.gather`
# (fallacie + argomenti chiamano classify_zero_shot in thread paralleli). Senza
# lock, al PRIMO call entrambi tentano il load → uno cade in fallback (uniform)
# mentre l'altro carica. Double-checked locking: fast-path senza lock, load serializzato.
_LOAD_LOCK = threading.Lock()


def _disabled() -> bool:
    return os.getenv("P3_RESH_NLI_DISABLE") == "1"


def _try_load_zero_shot():
    global _NLI_PIPELINE, _NLI_TRIED
    if _NLI_PIPELINE is not None:                 # fast-path senza lock
        return _NLI_PIPELINE
    with _LOAD_LOCK:
        if _NLI_PIPELINE is not None:             # re-check sotto lock
            return _NLI_PIPELINE
        if _NLI_TRIED:                            # già tentato+fallito
            return None
        _NLI_TRIED = True
        if _disabled():
            return None
        # ml_registry: prenota VRAM per deberta NLI (~1.2 GB)
        try:
            from ml_registry import acquire as _ml_acquire
            _ml_acquire("deberta-v3-nli")
        except Exception:
            pass
        try:
            from transformers import pipeline
            try:
                import torch
                device = 0 if torch.cuda.is_available() else -1
            except Exception:
                device = -1
            model = os.getenv("P3_RESH_NLI_MODEL", _NLI_MODEL)
            _NLI_PIPELINE = pipeline(
                "zero-shot-classification",
                model      = model,
                device     = device,
                truncation = True,         # safety net: troncamento a max_length del modello
            )
            return _NLI_PIPELINE
        except Exception as exc:
            print(f"[resh._nli] zero-shot pipeline non disponibile: {exc}")
            return None


def _try_load_entail():
    global _NLI_ENTAIL_PIPELINE
    if _NLI_ENTAIL_PIPELINE is not None:          # fast-path senza lock
        return _NLI_ENTAIL_PIPELINE
    if _disabled():
        return None
    with _LOAD_LOCK:
        if _NLI_ENTAIL_PIPELINE is not None:      # re-check sotto lock
            return _NLI_ENTAIL_PIPELINE
        # ml_registry: stesso modello del zero-shot (acquire idempotente)
        try:
            from ml_registry import acquire as _ml_acquire
            _ml_acquire("deberta-v3-nli")
        except Exception:
            pass
        try:
            from transformers import pipeline
            try:
                import torch
                device = 0 if torch.cuda.is_available() else -1
            except Exception:
                device = -1
            model = os.getenv("P3_RESH_NLI_MODEL", _NLI_MODEL)
            _NLI_ENTAIL_PIPELINE = pipeline(
                "text-classification",
                model      = model,
                device     = device,
                top_k      = None,
                truncation = True,         # safety net: troncamento a 512 token
            )
            return _NLI_ENTAIL_PIPELINE
        except Exception as exc:
            print(f"[resh._nli] text-classification pipeline non disponibile: {exc}")
            return None


def classify_zero_shot(
    sequences:           list[str] | str,
    labels:              list[str],
    hypothesis_template: str = "Questo testo è un esempio di {}.",
    multi_label:         bool = False,
) -> list[dict] | dict:
    """Zero-shot classify.

    Returns:
      Se input è list → list[dict{labels, scores, sequence}]
      Se input è str  → dict
      Su fallback: stessa shape ma scores=[1/N]*N, labels invariate.
    """
    pipe = _try_load_zero_shot()
    if pipe is None:
        # fallback: distribuzione uniforme
        def _uniform(seq: str) -> dict:
            n = max(1, len(labels))
            return {"sequence": seq, "labels": list(labels), "scores": [1.0 / n] * n}
        if isinstance(sequences, str):
            return _uniform(sequences)
        return [_uniform(s) for s in sequences]

    out = pipe(
        sequences,
        candidate_labels    = labels,
        hypothesis_template = hypothesis_template,
        multi_label         = multi_label,
    )
    return out


def entail(premise: str, hypothesis: str) -> float:
    """p(ENTAILMENT) ∈ [0,1] via text-classification head NLI.

    Compatibile sia con modelli 3-classi (entailment|neutral|contradiction)
    sia con il nuovo zeroshot-v2.0 a 2-classi (entailment|not_entailment).
    In entrambi i casi `entailment` ha `label_id=0`.

    Fallback: ritorna 0.0 (consumer dovrebbe trattare come 'sconosciuto').
    """
    pipe = _try_load_entail()
    if pipe is None:
        return 0.0
    text_pair = f"{premise} [SEP] {hypothesis}"
    try:
        scores = pipe(text_pair)
        # output può essere list[dict] o list[list[dict]] a seconda della versione
        if scores and isinstance(scores, list) and scores and isinstance(scores[0], list):
            scores = scores[0]
        for s in scores:
            label = str(s.get("label", "")).lower()
            if label in {"entailment", "label_0", "0"}:
                return float(s.get("score", 0.0))
        return 0.0
    except Exception:
        return 0.0


def backend_info() -> str:
    if _disabled():
        return "disabled (P3_RESH_NLI_DISABLE=1)"
    if _NLI_PIPELINE is None and not _NLI_TRIED:
        return "lazy (not loaded)"
    if _NLI_PIPELINE is None:
        return "fallback (transformers unavailable)"
    return _NLI_MODEL
