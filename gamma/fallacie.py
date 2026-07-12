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
import logging
import re
from pathlib import Path
from typing import Optional

from . import _nli
from .annotazione import AnnotatedDoc
from ..schemas import Patologia, TipoPatologia

logger = logging.getLogger(__name__)
_LESSICI_DIR = Path(__file__).parent.parent / "lessici"


# ─── tassonomia MAFALDA L2 → label per zero-shot, per lingua ─────────────────

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
MAFALDA_LABELS_EN = {
    "ad_hominem":           "ad hominem (personal attack)",
    "ad_populum":           "ad populum (common belief)",
    "ad_verecundiam":       "ad verecundiam (appeal to authority)",
    "false_dilemma":        "false dilemma",
    "hasty_generalization": "hasty generalization",
    "post_hoc":             "post hoc (false cause)",
    "slippery_slope":       "slippery slope",
    "straw_man":            "straw man",
    "appeal_to_emotion":    "appeal to emotion",
    "red_herring":          "red herring",
    "circular_reasoning":   "circular reasoning",
    "false_analogy":        "false analogy",
    "equivocation":         "equivocation",
}
_HYPOTHESIS_TEMPLATE_IT = "Questo argomento contiene la fallacia: {}."
_HYPOTHESIS_TEMPLATE_EN = "This argument contains the fallacy: {}."

_MARKER_RE_IT = re.compile(
    r"\b(quindi|perciò|pertanto|dunque|allora|poiché|poiche|giacché|"
    r"però|tuttavia|nondimeno|ciononostante|"
    r"sebbene|benché|nonostante|"
    r"ovviamente|certamente|chiaramente|evidentemente)\b",
    re.IGNORECASE,
)
_MARKER_RE_EN = re.compile(
    r"\b(therefore|thus|hence|consequently|so|because|since|"
    r"however|but|yet|nevertheless|nonetheless|"
    r"although|though|obviously|certainly|clearly|evidently)\b",
    re.IGNORECASE,
)

_PATTERNS_CACHE: dict[str, list] = {}


def _load_patterns(lang: str) -> list[dict]:
    patterns_file = _LESSICI_DIR / f"fallacy_patterns_{lang}.json"
    if not patterns_file.exists():
        return []
    try:
        data = json.loads(patterns_file.read_text(encoding="utf-8"))
        return data.get("patterns", [])
    except Exception as exc:
        logger.warning("errore nel caricamento fallacy_patterns_%s.json: %s", lang, exc)
        return []


def _get_regex_patterns(lang: str) -> list[tuple]:
    if lang not in _PATTERNS_CACHE:
        _PATTERNS_CACHE[lang] = [
            (re.compile(p["regex"], re.IGNORECASE | re.UNICODE), p)
            for p in _load_patterns(lang)
        ]
    return _PATTERNS_CACHE[lang]


def _regex_fallacies(testo: str) -> list[Patologia]:
    from .. import config
    lang = config.LANG.get()
    found: list[Patologia] = []
    seen_spans: set[tuple[int, int, str]] = set()
    for regex, meta in _get_regex_patterns(lang):
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
                    "fonte":       f"regex_{lang}",
                    # A2 (2026-07): un match regex NON è più un verdetto per sé.
                    # `confermata` viene deciso a valle da `_conferma_via_nli`
                    # (co-occorrenza con l'NLI). Default False finché non confermato.
                    "confermata":  False,
                },
                origine_modulo = "fallacie",
            ))
    return found


def _conferma_via_nli(regex_pats: list[Patologia], nli_pats: list[Patologia],
                      sentence_spans: list[tuple[int, int]]) -> None:
    """Marca in-place `confermata` sui regex (A2, 2026-07).

    Un regex è `confermata=True` **iff** l'NLI ha rilevato la STESSA `fallacia_l2`
    nella STESSA frase — il criterio è la conferma indipendente (README: «verdetti
    = più segnali indipendenti»), non l'essere-regex. Era l'intento originale del
    file: «i regex vengono confermate/integrate dal classifier NLI».

    Senza NLI (backend degradato / nessun candidato → `nli_pats` vuoto) nessun
    regex è confermato: niente modello, niente verdetti di fallacia (coerente con
    l'onestà dichiarata di resh in modalità degradata).

    `sentence_spans`: [(start_char, end_char), …] da `doc.sentences`, per mappare lo
    span del match alla frase. Se il mapping fallisce (offset ignoti, es. fallback
    con span 0), si ricade su un confronto doc-level per tipo.
    """
    nli_by_frase: set[tuple[int, str]] = set()
    nli_types: set[str] = set()
    for p in nli_pats:
        l2 = p.dettaglio.get("fallacia_l2")
        if not l2:
            continue
        nli_types.add(l2)
        idx = p.dettaglio.get("idx_frase")
        if idx is not None:
            nli_by_frase.add((int(idx), l2))

    def _frase_di(span: Optional[tuple[int, int]]) -> Optional[int]:
        if not span:
            return None
        start = span[0]
        for i, (s, e) in enumerate(sentence_spans):
            if e > s and s <= start < e:
                return i
        return None

    for p in regex_pats:
        l2 = p.dettaglio.get("fallacia_l2")
        if not l2:
            p.dettaglio["confermata"] = False
            continue
        idx = _frase_di(p.span_char)
        if idx is not None:
            p.dettaglio["confermata"] = (idx, l2) in nli_by_frase
        else:
            p.dettaglio["confermata"] = l2 in nli_types   # fallback doc-level


def _frasi_con_marker(doc: AnnotatedDoc) -> list[tuple[int, str]]:
    """Ritorna [(idx_frase, text)] solo per frasi che contengono marker
    argomentativi — riduce drasticamente il carico NLI."""
    from .. import config
    marker_re = _MARKER_RE_EN if config.LANG.get() == "en" else _MARKER_RE_IT
    out = []
    for i, s in enumerate(doc.sentences):
        if marker_re.search(s.text):
            out.append((i, s.text))
    return out


def _nli_fallacies(doc: AnnotatedDoc, threshold: float = 0.55) -> list[Patologia]:
    from .. import config
    lang = config.LANG.get()
    mafalda_labels = MAFALDA_LABELS_EN if lang == "en" else MAFALDA_LABELS_IT
    hypothesis_template = _HYPOTHESIS_TEMPLATE_EN if lang == "en" else _HYPOTHESIS_TEMPLATE_IT

    candidati = _frasi_con_marker(doc)
    if not candidati:
        return []
    sequences = [c[1] for c in candidati]
    labels    = list(mafalda_labels.values())

    results = _nli.classify_zero_shot(
        sequences           = sequences,
        labels              = labels,
        hypothesis_template = hypothesis_template,
        multi_label         = True,
    )
    if isinstance(results, dict):
        results = [results]

    label_to_key = {v: k for k, v in mafalda_labels.items()}

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
    calibrato per deberta-v3-base-zeroshot-v2.0). Regex sono sempre inclusi come
    CANDIDATI; diventano `confermata` solo se l'NLI conferma la stessa fallacia
    nella stessa frase (`_conferma_via_nli`, A2).
    """
    regex_pats = _regex_fallacies(doc.text)
    nli_pats   = _dedup_per_frase(_nli_fallacies(doc, threshold=threshold))
    sentence_spans = [(s.start_char, s.end_char) for s in doc.sentences]
    _conferma_via_nli(regex_pats, nli_pats, sentence_spans)
    return _dedup(regex_pats + nli_pats)
