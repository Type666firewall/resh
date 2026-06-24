"""resh/coerenza.py — Coesione semantica + drift tematico.

Coesione locale  = mean cosine(emb_i, emb_{i+1})
Coesione globale = mean cosine pairwise (tutte le coppie)
Drift tematico   = std cosine di segmenti k=3 vs centro testo
                   + BERTopic n_topics se n_frasi >= 20 (opt)

Output: dict[str, float|int] consumato da epsilon.py come componenti
`coesione_semantica` e `coerenza_tematica`.

Riferimento BERTopic: https://maartengr.github.io/BERTopic/ (opt-in,
modulo grafico — saltato su testi corti).
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np


def _pairwise_mean(embs: np.ndarray) -> float:
    if embs.shape[0] < 2:
        return 1.0
    sim = embs @ embs.T
    n = embs.shape[0]
    mask = np.triu(np.ones((n, n), dtype=bool), k=1)
    return float(sim[mask].mean())


def _local_mean(embs: np.ndarray) -> float:
    if embs.shape[0] < 2:
        return 1.0
    diag = np.sum(embs[:-1] * embs[1:], axis=1)
    return float(diag.mean())


def _segment_drift(embs: np.ndarray, k: int = 3) -> float:
    """Varianza inter-segmento: divide il testo in k segmenti,
    centroide per segmento, ritorna std delle similarità centroide-globale."""
    n = embs.shape[0]
    if n < k:
        return 0.0
    centroide_globale = embs.mean(axis=0)
    centroide_globale /= max(1e-9, float(np.linalg.norm(centroide_globale)))
    seg_size = max(1, n // k)
    sims = []
    for i in range(k):
        seg = embs[i * seg_size : (i + 1) * seg_size if i < k - 1 else n]
        if seg.shape[0] == 0:
            continue
        c = seg.mean(axis=0)
        c /= max(1e-9, float(np.linalg.norm(c)))
        sims.append(float(c @ centroide_globale))
    if len(sims) < 2:
        return 0.0
    return float(np.std(sims))


def _bertopic_n(frasi: list[str], embs: np.ndarray) -> Optional[int]:
    if os.getenv("P3_RESH_BERTOPIC_DISABLE") == "1":
        return None
    if len(frasi) < 20:
        return None
    try:
        from bertopic import BERTopic  # noqa: F401
        from umap import UMAP
        # determinism: BERTopic non accetta random_state direttamente; va
        # iniettato via UMAP. HDBSCAN resta non-seedabile ma riduciamo la
        # varianza inter-run del componente principale di riduzione dim.
        umap_model = UMAP(
            n_neighbors=15, n_components=5, min_dist=0.0,
            metric="cosine", random_state=42,
        )
        model = BERTopic(
            language          = "multilingual",
            calculate_probabilities = False,
            verbose           = False,
            umap_model        = umap_model,
        )
        topics, _ = model.fit_transform(frasi, embeddings=embs.astype(np.float32))
        n = len(set(t for t in topics if t != -1))
        return n
    except Exception as exc:
        print(f"[resh.coerenza] BERTopic skipped: {exc}")
        return None


def analizza_coerenza(frasi: list[str] | str, embeddings: np.ndarray) -> dict:
    """Calcola coesione locale/globale + drift tematico (k=3 + BERTopic opt).

    Args:
      frasi: lista di frasi già tokenizzate (preferibilmente da Stanza UD,
        per allineamento 1:1 con `embeddings`). Per retrocompat accetta
        ancora una stringa, che viene splittata grezzo su `.`.
      embeddings: shape (n_frasi, dim), già L2-normalizzato.

    Returns: dict con chiavi `coesione_locale`, `coesione_globale`,
    `deriva`, `n_segmenti_tematici`, `coerenza_tematica_score`.
    """
    if isinstance(frasi, str):
        # retrocompat: il vecchio caller passava il testo intero
        frasi = [f.strip() for f in frasi.split(".") if f.strip()]

    if embeddings.ndim != 2 or embeddings.shape[0] == 0:
        return {
            "coesione_locale":          1.0,
            "coesione_globale":         1.0,
            "deriva":                   0.0,
            "n_segmenti_tematici":      0,
            "coerenza_tematica_score":  1.0,
        }

    local  = _local_mean(embeddings)
    global_ = _pairwise_mean(embeddings)
    drift  = _segment_drift(embeddings, k=3)

    # BERTopic richiede len(frasi) == embeddings.shape[0]; allineiamo
    # difensivamente per evitare shape mismatch.
    n_frasi_embs = embeddings.shape[0]
    if len(frasi) != n_frasi_embs:
        frasi_aligned = frasi[:n_frasi_embs] if len(frasi) > n_frasi_embs \
                        else frasi + [""] * (n_frasi_embs - len(frasi))
    else:
        frasi_aligned = frasi
    n_topics = _bertopic_n(frasi_aligned, embeddings) or 0

    # coerenza_tematica_score: alta se drift basso E n_topics piccolo
    drift_score  = 1.0 - min(1.0, drift * 3.0)
    topic_score  = 1.0 if n_topics <= 2 else max(0.0, 1.0 - (n_topics - 2) * 0.15)
    coh_tem      = round(0.6 * drift_score + 0.4 * topic_score, 4)

    return {
        "coesione_locale":          round(local, 4),
        "coesione_globale":         round(global_, 4),
        "deriva":                   round(drift, 4),
        "n_segmenti_tematici":      n_topics,
        "coerenza_tematica_score":  coh_tem,
    }
