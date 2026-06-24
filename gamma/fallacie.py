"""resh/fallacie.py — Rilevamento fallacie: regex IT + zero-shot NLI (MAFALDA L2).

Tassonomia MAFALDA: https://github.com/ChadiHelwe/MAFALDA, paper
https://arxiv.org/abs/2311.09761.

Pipeline:
  1. Regex su `lessici/fallacy_patterns_it.json` — pattern linguisticamente
     marcati ad alta precisione (confidence 0.4-0.65, severita 0.4-0.7).
  2. Zero-shot NLI (deberta-v3-base-zeroshot-v2.0) su 13 categorie MAFALDA L2
     tradotte in italiano. Applicato solo a frasi con marker argomentativo
     (connettivi causali/avversativi/concessivi o booster/hedge) — threshold
     0.55 (il nuovo modello è più calibrato del precedente mDeBERTa).

Output: list[Patologia(tipo=FALLACIA_LOGICA, dettaglio.fallacia_l2=<str>)].
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import _nli
from .annotazione import AnnotatedDoc
from ..schemas import Patologia, TipoPatologia


_PATTERNS_FILE = Path(__file__).parent.parent / "lessici" / "fallacy_patterns_it.json"


# ─── tassonomia MAFALDA L2 → label italiano per zero-shot ────────────────────

MAFALDA_LABELS_IT = {
    "ad_hominem":           "attacco alla persona",
    "ad_populum":           "appello al senso comune",
    "ad_verecundiam":       "appello all'autorità",
    "false_dilemma":        "falso dilemma",
    "hasty_generalization": "generalizzazione affrettata",
    "post_hoc":             "post hoc ergo propter hoc",
    "slippery_slope":       "china scivolosa",
    "straw_man":            "uomo di paglia",
    "appeal_to_emotion":    "appello all'emozione",
    "red_herring":          "diversione tematica",
    "circular_reasoning":   "ragionamento circolare",
    "false_analogy":        "falsa analogia",
    "equivocation":         "equivoco lessicale",
}


_MARKER_RE = re.compile(
    r"\b(quindi|perciò|pertanto|dunque|allora|poiché|poiche|giacché|"
    r"però|tuttavia|nondimeno|ciononostante|"
    r"sebbene|benché|nonostante|"
    r"ovviamente|certamente|chiaramente|evidentemente)\b",
    re.IGNORECASE,
)


def _load_patterns() -> list[dict]:
    if not _PATTERNS_FILE.exists():
        return []
    data = json.loads(_PATTERNS_FILE.read_text(encoding="utf-8"))
    return data.get("patterns", [])


_REGEX_PATTERNS = [
    (re.compile(p["regex"], re.IGNORECASE | re.UNICODE), p)
    for p in _load_patterns()
]


def _regex_fallacies(testo: str) -> list[Patologia]:
    found: list[Patologia] = []
    seen_spans: set[tuple[int, int, str]] = set()
    for regex, meta in _REGEX_PATTERNS:
        for m in regex.finditer(testo):
            key = (m.start(), m.end(), meta["tipo"])
            if key in seen_spans:
                continue
            seen_spans.add(key)
            found.append(Patologia(
                tipo       = TipoPatologia.FALLACIA_LOGICA,
                severita   = float(meta.get("severita", 0.5)),
                confidence = float(meta.get("confidence", 0.5)),
                span_char  = (m.start(), m.end()),
                dettaglio  = {
                    "fallacia_l2": meta["tipo"],
                    "match":       m.group(0),
                    "fonte":       "regex_it",
                    "confermata":  True,            # regex ad alta precisione
                },
                origine_modulo = "fallacie",
            ))
    return found


def _frasi_con_marker(doc: AnnotatedDoc) -> list[tuple[int, str]]:
    """Ritorna [(idx_frase, text)] solo per frasi che contengono marker
    argomentativi — riduce drasticamente il carico NLI."""
    out = []
    for i, s in enumerate(doc.sentences):
        if _MARKER_RE.search(s.text):
            out.append((i, s.text))
    return out


def _nli_fallacies(doc: AnnotatedDoc, threshold: float = 0.55) -> list[Patologia]:
    candidati = _frasi_con_marker(doc)
    if not candidati:
        return []
    sequences = [c[1] for c in candidati]
    labels    = list(MAFALDA_LABELS_IT.values())

    results = _nli.classify_zero_shot(
        sequences           = sequences,
        labels              = labels,
        hypothesis_template = "Questo argomento contiene la fallacia: {}.",
        multi_label         = True,
    )
    if isinstance(results, dict):
        results = [results]

    label_to_key = {v: k for k, v in MAFALDA_LABELS_IT.items()}

    found: list[Patologia] = []
    for (idx_frase, testo_frase), res in zip(candidati, results):
        labels_out = res.get("labels", [])
        scores_out = res.get("scores", [])
        for lbl, sc in zip(labels_out, scores_out):
            if sc >= threshold:
                key = label_to_key.get(lbl, lbl)
                found.append(Patologia(
                    tipo       = TipoPatologia.FALLACIA_LOGICA,
                    severita   = min(1.0, float(sc)),
                    confidence = float(sc),
                    span_char  = (0, len(testo_frase)),     # frase-level
                    dettaglio  = {
                        "fallacia_l2":  key,
                        "frase":        testo_frase[:200],
                        "idx_frase":    idx_frase,
                        "fonte":        "nli_zeroshot_v2",
                        "confermata":   False,      # zero-shot rumoroso → SOSPETTA
                    },
                    origine_modulo = "fallacie",
                ))
    return found


def _dedup(patologie: list[Patologia]) -> list[Patologia]:
    """Dedup per (fallacia_l2, span_char) — preferisce confidence maggiore."""
    by_key: dict[tuple, Patologia] = {}
    for p in patologie:
        key = (p.dettaglio.get("fallacia_l2"), p.span_char)
        if key not in by_key or p.confidence > by_key[key].confidence:
            by_key[key] = p
    return list(by_key.values())


def _dedup_per_frase(nli_pats: list[Patologia], max_per_frase: int = 2) -> list[Patologia]:
    """Limita a max N fallacie NLI per frase (idx_frase), le più confident.

    Argine al bug multilabel: con 13 label e multi_label=True il modello può
    assegnare molte etichette alla stessa frase. Teniamo solo le top-N per
    frase per non devastare validita_argomenti in epsilon.
    """
    by_frase: dict[int, list[Patologia]] = {}
    for p in nli_pats:
        idx = p.dettaglio.get("idx_frase", -1)
        by_frase.setdefault(idx, []).append(p)
    out: list[Patologia] = []
    for pats in by_frase.values():
        pats.sort(key=lambda x: x.confidence, reverse=True)
        out.extend(pats[:max_per_frase])
    return out


def rileva_fallacie(doc: AnnotatedDoc, *, threshold: float = 0.55) -> list[Patologia]:
    """Ritorna lista deduplicata di patologie FALLACIA_LOGICA.

    threshold: soglia confidence per accettare risultato NLI (default 0.55,
    calibrato per deberta-v3-base-zeroshot-v2.0). Regex sono sempre inclusi
    (precisione alta per costruzione).
    """
    regex_pats = _regex_fallacies(doc.text)
    nli_pats   = _dedup_per_frase(_nli_fallacies(doc, threshold=threshold))
    return _dedup(regex_pats + nli_pats)
