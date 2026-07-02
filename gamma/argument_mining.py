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


# Pattern esplicativi/inferenziali aggiuntivi (sparano "deduttivo" anche in
# assenza dei connettivi da lessico) e marker conclusivi (fallback tesi/premesse):
# NON esternalizzati come gli altri lessici — alcune entry dipendono dal padding
# di spazi per un boundary-matching approssimato senza regex (" allora " ≠ "allora",
# evita match dentro altre parole). Un file di testo a righe stripperebbe quel
# padding e romperebbe silenziosamente il matching: restano hardcoded per lingua.
_DEDUTTIVI_ESPLICATIVI_IT = (
    "infatti", "appunto", "in effetti", "ne consegue", "ne deriva", "deriva che",
    "mostra che", "dimostra che", "dimostra come", "implica che", "implica una",
    "comporta che", "comporta una", "significa che", "vuol dire che",
    "ciò significa", "questo prova", "questo dimostra", "questo implica",
    "se ", " allora ", " allora,", " allora.",      # condizionali if-then
    "qualora", "purché",
)
_DEDUTTIVI_ESPLICATIVI_EN = (
    "indeed", "in fact", "it follows", "it derives", "shows that", "proves that",
    "implies that", "implies a", "means that", "this means", "this proves",
    "this shows", "this implies", "if ", " then ", "provided that", "as long as",
)
_CONCL_MARKERS_IT = (
    "dunque", "quindi", "perciò", "percio", "pertanto", "ne consegue",
    "ne deriva", "se ne deduce", "allora", "deve", "devono", "dev'",
)
_CONCL_MARKERS_EN = (
    "therefore", "thus", "hence", "consequently", "so", "it follows",
    "it derives", "then", "must", "should",
)

_LEX_CACHE: dict[str, dict] = {}


def _get_lex(lang: str) -> dict:
    """Lessici per lingua: causali/avversativi/induttivi/booster/retorici da
    file esterni (curabili senza toccare codice); deduttivi/concl_markers
    restano hardcoded per il motivo di boundary-matching sopra."""
    if lang not in _LEX_CACHE:
        _LEX_CACHE[lang] = {
            "causali":    _load_lex(f"connettivi_causali_{lang}.txt"),
            "avv":        _load_lex(f"connettivi_avversativi_{lang}.txt"),
            "induttivi":  _load_lex(f"induttivi_{lang}.txt"),
            "booster":    _load_lex(f"booster_{lang}.txt"),
            "retorici":   _load_lex(f"retorici_attributivi_{lang}.txt"),
            "deduttivi":  _DEDUTTIVI_ESPLICATIVI_EN if lang == "en" else _DEDUTTIVI_ESPLICATIVI_IT,
            "concl":      _CONCL_MARKERS_EN if lang == "en" else _CONCL_MARKERS_IT,
        }
    return _LEX_CACHE[lang]

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
    from .. import config
    lex = _get_lex(config.LANG.get())
    low = " " + testo.lower() + " "
    if any(c in low for c in lex["causali"]):
        return "deduttivo"
    if any(q in low for q in lex["induttivi"]):
        return "induttivo"
    if any(b in low for b in lex["booster"]):
        return "retorico"
    if any(r in low for r in lex["retorici"]):
        return "retorico"
    if any(d in low for d in lex["deduttivi"]):
        return "deduttivo"
    if any(a in low for a in lex["avv"]):
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


def _inventario_fallback(frasi: list[str], embeddings: np.ndarray) -> list[Argomento]:
    """Inventario euristico deterministico quando l'NLI non isola premesse
    (frequente su proposizioni brevi). Tesi = ultima unità con marcatore
    conclusivo (o l'ultima in assenza); le altre unità sono premesse. La tesi è
    esclusa dalle `premesse_usate` per non rendere la verifica circolare."""
    from .. import config
    concl_markers = _get_lex(config.LANG.get())["concl"]
    if len(frasi) < 2:
        return []
    tesi_idx = None
    for i, f in enumerate(frasi):
        low = f.lower()
        if any(m in low for m in concl_markers):
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
                confidence      = round(sc, 4),
            ))

    # Fallback deterministico: se l'NLI non isola premesse (frequente su unità
    # proposizionali brevi), costruisci l'inventario per connettivi conclusivi —
    # così la verifica di sequitur ha argomenti su cui operare.
    if not argomenti:
        argomenti = _inventario_fallback(frasi, embeddings)
    return argomenti
