"""resh/premesse_nli.py — Estrazione premesse implicite via entailment NLI.

Pipeline:
  1. Candidate premise generation: per ogni verbo root nel dep tree (Stanza),
     estrai pattern soggetto-verbo-oggetto → frase canonica candidata.
  2. Per ogni candidata, calcola NLI entailment(testo → candidata).
  3. Classifica:
     - esplicita  se cosine(candidata, qualsiasi frase testo) > 0.85
     - implicita  se entail > 0.6 e non esplicita
     - sospetta   se entail > 0.6 e candidata contiene aggettivi assoluti
                  (booster lex) o quantificatori universali ("tutti","sempre")

Fallback (NLI assente): solo `esplicite` (= prime 5 frasi del testo) e
score=0.5. Risultato neutro per epsilon.

Reference: stesso modello mDeBERTa multilingue di `fallacie.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from . import _nli
from .annotazione import AnnotatedDoc
from .encoder import encode
from ..schemas import PremessaAnalisi


_LESSICI_DIR = Path(__file__).parent.parent / "lessici"


def _load_lex(name: str) -> set[str]:
    p = _LESSICI_DIR / name
    if not p.exists():
        return set()
    return {l.strip().lower() for l in p.read_text(encoding="utf-8").splitlines() if l.strip()}


_BOOSTERS = _load_lex("booster_it.txt")
_UNIV_QUANT = {"tutti","tutte","sempre","mai","ogni","nessuno","nessuna",
               "chiunque","ovunque","qualsiasi","qualunque"}


def _candidate_premises_from_doc(doc: AnnotatedDoc, max_n: int = 8) -> list[str]:
    """Estrae frasi candidate `[soggetto] [verbo-root] [oggetto/complemento]`
    via dep tree. Se backend=fallback (no Stanza), ritorna direttamente le
    prime N frasi come 'candidate' (non utile ma non rompe pipeline)."""
    if doc.backend != "stanza":
        return [s.text for s in doc.sentences[:max_n]]

    candidates: list[str] = []
    for s in doc.sentences:
        # cerca verbo root
        root_idx = None
        for i, w in enumerate(s.words, start=1):
            if w.deprel == "root" and w.upos in {"VERB", "AUX"}:
                root_idx = i
                break
        if root_idx is None:
            continue

        root_w = s.words[root_idx - 1]
        soggetto = ""
        oggetto  = ""
        for i, w in enumerate(s.words, start=1):
            if w.head == root_idx:
                if w.deprel in {"nsubj", "nsubj:pass"}:
                    soggetto = w.lemma or w.text
                elif w.deprel in {"obj", "obl", "ccomp", "xcomp"}:
                    oggetto = w.lemma or w.text

        if soggetto and root_w.lemma:
            cand = f"{soggetto} {root_w.lemma} {oggetto}".strip()
            if len(cand) > 6:
                candidates.append(cand)
        if len(candidates) >= max_n:
            break
    return candidates


def _is_sospetta(candidata: str) -> bool:
    low = candidata.lower()
    if any(q in low.split() for q in _UNIV_QUANT):
        return True
    for b in _BOOSTERS:
        # match parola intera
        if re.search(r"\b" + re.escape(b) + r"\b", low):
            return True
    return False


def analizza_premesse(testo: str, doc: AnnotatedDoc, embeddings: np.ndarray) -> PremessaAnalisi:
    esplicite: list[str] = []
    implicite: list[str] = []
    sospette:  list[str] = []

    # Esplicite: le frasi del testo stesso che funzionano da premessa
    # (heuristic: frasi con connettivi causali o avversativi sono spesso esplicite)
    for s in doc.sentences:
        low = s.text.lower()
        if any(k in low for k in (" quindi ", " perciò ", " poiché ", " dato che ",
                                  " visto che ", " in quanto ", " infatti ")):
            esplicite.append(s.text.strip())

    # Candidate implicite via dep tree
    candidates = _candidate_premises_from_doc(doc)
    if not candidates:
        # nessuna premessa rilevabile: esplicite→1.0, altrimenti NEUTRALE 0.5
        # (evidenza insufficiente, non «zero trasparenza» — W3 stabilizzazione 2026-06)
        score = 1.0 if esplicite else 0.5
        return PremessaAnalisi(esplicite=esplicite[:10], implicite=[],
                                sospette=[], score=round(score, 4))

    # Verifica entailment per ogni candidata
    cand_embs = encode(candidates) if candidates else np.zeros((0, 1), dtype=np.float32)
    sent_embs = embeddings if embeddings.ndim == 2 and embeddings.shape[0] > 0 else None

    # Numero di frasi di contesto da passare al NLI per candidata.
    # Passare l'intero `testo` saturava i 512 token del modello (vedi log
    # 2026-05-20 — incidente "37050 > 512"): ora prendiamo solo le top-K
    # frasi più simili alla candidata (similarità coseno sugli embeddings).
    TOP_K_CONTEXT       = 5
    MAX_CONTEXT_CHARS   = 1500   # ~ 400 token, sotto la soglia del modello

    for i, cand in enumerate(candidates):
        # esplicita se candidata è cosine > 0.85 con una frase del testo
        is_explicit = False
        top_idx: list[int] = []
        if sent_embs is not None and cand_embs.shape[0] > i:
            sims = sent_embs @ cand_embs[i]
            if sims.size and float(np.max(sims)) > 0.85:
                is_explicit = True
            # Top-K frasi più simili come contesto NLI (escludendo identiche)
            if sims.size:
                order = np.argsort(-sims)
                top_idx = [int(j) for j in order[:TOP_K_CONTEXT]]

        if is_explicit:
            # già coperta da loop esplicite-da-connettivi; non duplicare
            continue

        # Contesto locale anziché testo completo (mantiene NLI sotto i 512 tok)
        if top_idx:
            contesto = " ".join(doc.sentences[j].text for j in top_idx)
        else:
            contesto = " ".join(s.text for s in doc.sentences[:TOP_K_CONTEXT])
        if len(contesto) > MAX_CONTEXT_CHARS:
            contesto = contesto[:MAX_CONTEXT_CHARS]

        p_entail = _nli.entail(contesto, cand)
        if p_entail > 0.6:
            if _is_sospetta(cand):
                sospette.append(cand)
            else:
                implicite.append(cand)

    # score trasparenza: 1 = tutte esplicite, basso = molte implicite. Floor a 0.1
    # (niente FALSO veto su ε via media geometrica) e neutrale 0.5 sotto-evidenza.
    # W3, stabilizzazione 2026-06.
    n_tot = len(esplicite) + len(implicite) + len(sospette)
    if n_tot < 2:
        score = 0.5
    else:
        score = max(0.1, len(esplicite) / n_tot)

    return PremessaAnalisi(
        esplicite = esplicite[:20],
        implicite = implicite[:20],
        sospette  = sospette[:20],
        score     = round(score, 4),
    )
