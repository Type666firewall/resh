"""resh/argument_mining.py — Claim/premise classifier via zero-shot NLI.

Per ogni frase del doc → zero-shot classification su 3 etichette italiane:
  - "affermazione/tesi"      → claim
  - "giustificazione/premessa" → premise
  - "né tesi né premessa"    → neither

Mapping `Argomento.tipo` deterministico:
  - presenza connettivi causali (quindi, perciò, ne consegue, ...) → deduttivo
  - presenza quantificatori induttivi (spesso, in genere, molti, talvolta,
    generalmente) → induttivo
  - presenza booster assoluti (ovviamente, certamente, ...) → retorico
  - altrimenti → non classificabile

Fallback (NLI assente): tutte le frasi etichettate "non classificabile" con
confidence=0 — l'inventario sarà vuoto. È accettabile e DICHIARATO
(backend.eps_degradato=True nel rapporto; la sintesi LLM legacy è stata
rimossa con ADR-005).

Reference WRAP arg mining: https://arxiv.org/abs/2505.22137.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from . import _nli
from ..schemas import Argomento


_LESSICI_DIR = Path(__file__).parent.parent / "lessici"

def _load_lex(name: str) -> set[str]:
    p = _LESSICI_DIR / name
    if not p.exists():
        return set()
    return {l.strip().lower() for l in p.read_text(encoding="utf-8").splitlines() if l.strip()}


_CAUSALI = _load_lex("connettivi_causali_it.txt")
_AVV     = _load_lex("connettivi_avversativi_it.txt")
_INDUTTIVI = {"spesso","in genere","talvolta","talora","a volte","generalmente",
              "in linea di massima","grosso modo","molti","molte","la maggior parte",
              "frequentemente","raramente","tendenzialmente","mediamente",
              "nella maggior parte dei casi","in genere"}
_BOOSTER  = {"ovviamente","certamente","chiaramente","evidentemente","indubbiamente",
             "senza dubbio","è ovvio","è chiaro","è evidente","è certo","naturalmente",
             "è palese","è manifesto","senza alcun dubbio"}

# Pattern esplicativi/inferenziali aggiuntivi — sparano "deduttivo" anche
# in assenza dei connettivi scolastici di _CAUSALI.
_DEDUTTIVI_ESPLICATIVI = (
    "infatti", "appunto", "in effetti", "ne consegue", "ne deriva", "deriva che",
    "mostra che", "dimostra che", "dimostra come", "implica che", "implica una",
    "comporta che", "comporta una", "significa che", "vuol dire che",
    "ciò significa", "questo prova", "questo dimostra", "questo implica",
    "se ", " allora ", " allora,", " allora.",      # condizionali if-then
    "qualora", "purché",
)

# Frasi che attribuiscono un'asserzione a terzi → "retorico" (citazione/autorità).
_RETORICI_ATTRIBUTIVI = (
    "afferma che", "sostiene che", "argomenta che", "ritiene che", "scrive che",
    "secondo cui", "a parere di", "a giudizio di", "ad avviso di",
    "come noto", "è noto che", "è risaputo che",
)

LABELS = [
    "affermazione di tesi",
    "giustificazione o premessa",
    "frase non argomentativa",
]


def _classify_tipo(testo: str) -> str:
    """Euristica deterministica sulla forma linguistica.

    Ordine: connettivi causali → induttivi → booster (retorico) → attributivi
    (retorico) → esplicativi/condizionali (deduttivo) → avversativi
    (deduttivo: contrasto = inferenza implicita). Solo se nessuno spara,
    'non classificabile'.
    """
    low = " " + testo.lower() + " "
    if any(c in low for c in _CAUSALI):
        return "deduttivo"
    if any(q in low for q in _INDUTTIVI):
        return "induttivo"
    if any(b in low for b in _BOOSTER):
        return "retorico"
    if any(r in low for r in _RETORICI_ATTRIBUTIVI):
        return "retorico"
    if any(d in low for d in _DEDUTTIVI_ESPLICATIVI):
        return "deduttivo"
    if any(a in low for a in _AVV):
        return "deduttivo"          # contrasto = inferenza implicita
    return "non classificabile"


def _premesse_usate(frase: str, candidate: list[str], embeddings: np.ndarray, idx: int) -> list[str]:
    """Top-3 frasi più simili (cosine) come 'premesse usate' euristiche."""
    if embeddings.ndim != 2 or embeddings.shape[0] == 0 or idx >= embeddings.shape[0]:
        return []
    sim = embeddings @ embeddings[idx]
    sim[idx] = -1.0   # escludi se stessa
    top = np.argsort(-sim)[:3]
    return [candidate[i] for i in top if sim[i] > 0.4]


# Marcatori conclusivi: introducono la tesi/conclusione (per il fallback).
_CONCL_MARKERS = (
    "dunque", "quindi", "perciò", "percio", "pertanto", "ne consegue",
    "ne deriva", "se ne deduce", "allora", "deve", "devono", "dev'",
)


def _inventario_fallback(frasi: list[str], embeddings: np.ndarray) -> list[Argomento]:
    """Inventario euristico deterministico quando l'NLI non isola premesse
    (frequente su proposizioni brevi). Tesi = ultima unità con marcatore
    conclusivo (o l'ultima in assenza); le altre unità sono premesse. La tesi è
    esclusa dalle `premesse_usate` per non rendere la verifica circolare."""
    if len(frasi) < 2:
        return []
    tesi_idx = None
    for i, f in enumerate(frasi):
        low = f.lower()
        if any(m in low for m in _CONCL_MARKERS):
            tesi_idx = i
    if tesi_idx is None:
        return []   # nessun connettivo conclusivo ⇒ testo non-argomentativo, niente argomento
    tesi = frasi[tesi_idx]
    out: list[Argomento] = []
    for i, f in enumerate(frasi):
        if i == tesi_idx:
            continue
        pu = [p for p in _premesse_usate(f, frasi, embeddings, i) if p != tesi]
        out.append(Argomento(
            testo           = f,
            tesi_supportata = tesi,
            tipo            = _classify_tipo(f),
            premesse_usate  = pu,
        ))
    return out


def estrai_argomenti(unita: list[str], embeddings: np.ndarray) -> list[Argomento]:
    """Ritorna lista di Argomento dalle unità testuali (proposizioni o frasi,
    allineate a `embeddings`)."""
    if not unita:
        return []

    frasi  = list(unita)
    results = _nli.classify_zero_shot(
        sequences = frasi,
        labels    = LABELS,
        hypothesis_template = "Questa frase è: {}.",
        multi_label = False,
    )
    if isinstance(results, dict):
        results = [results]

    # Mappa indice frase → tipo prevalente
    classificazioni: list[tuple[int, str, float]] = []
    for i, res in enumerate(results):
        labels_out = res.get("labels", [])
        scores_out = res.get("scores", [])
        if not labels_out:
            classificazioni.append((i, LABELS[2], 0.0))
            continue
        classificazioni.append((i, labels_out[0], float(scores_out[0])))

    # tesi: prima frase classificata come "affermazione di tesi"
    tesi: list[tuple[int, str]] = [(i, frasi[i]) for i, lbl, sc in classificazioni
                                    if lbl.startswith("affermazione") and sc > 0.5]
    tesi_principale = tesi[0][1] if tesi else (frasi[0] if frasi else "")

    argomenti: list[Argomento] = []
    for i, lbl, sc in classificazioni:
        if lbl.startswith("giustificazione") and sc > 0.5:
            frase = frasi[i]
            argomenti.append(Argomento(
                testo           = frase,
                tesi_supportata = tesi_principale,
                tipo            = _classify_tipo(frase),
                premesse_usate  = _premesse_usate(frase, frasi, embeddings, i),
            ))

    # Fallback deterministico: se l'NLI non isola premesse (frequente su unità
    # proposizionali brevi), costruisci l'inventario per connettivi conclusivi —
    # così la verifica di sequitur ha argomenti su cui operare.
    if not argomenti:
        argomenti = _inventario_fallback(frasi, embeddings)
    return argomenti
