"""resh/profilo_linguistico.py — feature deterministiche Profiling-UD-style.

Riferimento: http://www.italianlp.it/demo/profiling-ud/
Paper:       http://www.lrec-conf.org/proceedings/lrec2020/pdf/2020.lrec-1.883.pdf

Calcoli (tutti da AnnotatedDoc; nessun LLM):
  - n_token, n_frasi, lunghezza_media_frase
  - TTR (type-token ratio), MTLD (McCarthy & Jarvis 2010)
  - densità_lessicale = (NOUN+VERB+ADJ+ADV) / n_token
  - profondità_media_albero_dep
  - subordination_ratio = (acl + advcl + ccomp + xcomp) / n_clausole_root
  - lunghezza_media_dipendenza (in token, head distance)
  - rapporto_nominale_verbale = NOUN / max(1, VERB)
  - Gulpease = 89 - (n_lettere/n_parole)*10 + (n_frasi/n_parole)*300

Output: dict[str, float|int]. NO Patologia diretta (epsilon.py decide soglie).
"""

from __future__ import annotations

from collections import Counter
from typing import Optional

from .annotazione import AnnotatedDoc


LEXICAL_POS = {"NOUN", "VERB", "ADJ", "ADV", "PROPN"}
SUBORD_DEPRELS = {"acl", "advcl", "ccomp", "xcomp", "acl:relcl"}


def _mtld(tokens: list[str], threshold: float = 0.72) -> float:
    """McCarthy & Jarvis 2010 — implementazione minimale.

    Calcola il numero di fattori (segmenti che cadono sotto TTR=threshold)
    in avanti e indietro, poi `mtld = n_words / mean(factors)`.
    """
    if not tokens:
        return 0.0

    def _factor_count(seq: list[str]) -> float:
        types: set[str] = set()
        token_count = 0
        factors = 0.0
        for w in seq:
            types.add(w)
            token_count += 1
            ttr = len(types) / token_count
            if ttr <= threshold:
                factors += 1
                types.clear()
                token_count = 0
        # ultimo segmento partial
        if token_count > 0:
            partial_ttr = len(types) / token_count
            partial    = (1.0 - partial_ttr) / (1.0 - threshold) if threshold < 1 else 0.0
            factors   += max(0.0, min(1.0, partial))
        if factors == 0:
            return float(len(seq))
        return len(seq) / factors

    fwd  = _factor_count(tokens)
    bwd  = _factor_count(list(reversed(tokens)))
    return round((fwd + bwd) / 2.0, 2)


def _depth(words, idx: int, memo: dict[int, int]) -> int:
    """Profondità nodo idx (1-indexed UD) — head=0 → root, depth=0."""
    if idx in memo:
        return memo[idx]
    if idx < 1 or idx > len(words):
        return 0
    w = words[idx - 1]
    if w.head == 0:
        memo[idx] = 0
    else:
        memo[idx] = 1 + _depth(words, w.head, memo)
    return memo[idx]


def profilo_linguistico(doc: AnnotatedDoc) -> dict:
    """Estrae 12+ feature linguistiche deterministiche da AnnotatedDoc."""

    all_tokens: list[str]   = []
    all_lemmas: list[str]   = []
    pos_counts: Counter     = Counter()
    deprel_counts: Counter  = Counter()
    head_distances: list[int] = []
    depths: list[int] = []

    for s in doc.sentences:
        for i, w in enumerate(s.words, start=1):
            tok = w.text.lower()
            if tok.isalpha() or any(c.isalpha() for c in tok):
                all_tokens.append(tok)
                all_lemmas.append(w.lemma or tok)
                pos_counts[w.upos] += 1
                deprel_counts[w.deprel] += 1
                if w.head > 0:
                    head_distances.append(abs(i - w.head))
        # depth per ogni token della frase
        if s.words:
            memo: dict[int, int] = {}
            for i in range(1, len(s.words) + 1):
                depths.append(_depth(s.words, i, memo))

    n_token = len(all_tokens)
    n_frasi = max(1, len(doc.sentences))

    # TTR
    n_types = len(set(all_tokens))
    ttr = (n_types / n_token) if n_token else 0.0

    # MTLD
    mtld_val = _mtld(all_tokens)

    # densità lessicale
    lex_count = sum(pos_counts.get(p, 0) for p in LEXICAL_POS)
    dens_lex  = (lex_count / n_token) if n_token else 0.0

    # subordination ratio
    subord    = sum(deprel_counts.get(d, 0) for d in SUBORD_DEPRELS)
    n_root    = max(1, deprel_counts.get("root", n_frasi))
    sub_ratio = subord / n_root

    # head distance media
    mean_head_dist = (sum(head_distances) / len(head_distances)) if head_distances else 0.0

    # profondità media albero
    mean_depth = (sum(depths) / len(depths)) if depths else 0.0

    # rapporto nominale/verbale
    n_noun = pos_counts.get("NOUN", 0) + pos_counts.get("PROPN", 0)
    n_verb = max(1, pos_counts.get("VERB", 0))
    ratio_nv = n_noun / n_verb

    # Gulpease
    n_words   = max(1, n_token)
    n_letters = sum(len(t) for t in all_tokens)
    gulpease  = 89.0 - (n_letters / n_words) * 10.0 + (n_frasi / n_words) * 300.0

    lung_frase = n_token / n_frasi

    return {
        "n_token":                  n_token,
        "n_frasi":                  n_frasi,
        "lunghezza_media_frase":    round(lung_frase, 3),
        "ttr":                      round(ttr, 4),
        "mtld":                     round(mtld_val, 2),
        "densita_lessicale":        round(dens_lex, 4),
        "profondita_media_albero":  round(mean_depth, 3),
        "subordination_ratio":      round(sub_ratio, 4),
        "lunghezza_media_dip":      round(mean_head_dist, 3),
        "rapporto_nominale_verbale": round(ratio_nv, 4),
        "gulpease":                 round(gulpease, 2),
        "pos_distribution":         dict(pos_counts.most_common(15)),
        "backend":                  doc.backend,
    }


def qualita_sintattica(profilo: dict) -> Optional[float]:
    """Score 0-1 derivato dal profilo: combina TTR + MTLD + depth equilibrio.

    Usato come componente 'qualità_sintattica' in epsilon.py. Curva ad
    arco: testi troppo semplici (Gulpease>80, MTLD<30) e troppo barocchi
    (depth>8, sub_ratio>1.5) sono entrambi penalizzati.
    """
    # Evidenza insufficiente: la stilometria (MTLD, depth, sub_ratio) non è
    # affidabile sotto ~30 token → ritorna None = «non misurabile», così
    # epsilon.calcola_epsilon lo ESCLUDE dall'aggregazione (≠ riempire con un
    # valore finto che penalizzerebbe ε). Un sillogismo corretto non è
    # «mal scritto»: semplicemente non se ne può giudicare lo stile. W2 (2026-06).
    if profilo.get("n_token", 0) < 30:
        return None

    mtld     = profilo.get("mtld", 0.0)
    sub      = profilo.get("subordination_ratio", 0.0)
    depth    = profilo.get("profondita_media_albero", 0.0)
    gulpease = profilo.get("gulpease", 50.0)

    mtld_score   = min(1.0, max(0.0, (mtld - 30.0) / 60.0))     # 30→0, 90→1
    depth_score  = 1.0 - min(1.0, abs(depth - 4.5) / 4.5)       # ottimo @ ~4.5
    sub_score    = 1.0 - min(1.0, abs(sub - 0.6) / 0.6)         # ottimo @ ~0.6
    gulp_score   = 1.0 - min(1.0, abs(gulpease - 55.0) / 35.0)  # ottimo @ ~55

    return round(0.35 * mtld_score + 0.25 * depth_score
                 + 0.20 * sub_score + 0.20 * gulp_score, 4)
