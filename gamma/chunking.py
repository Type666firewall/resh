"""resh/chunking.py — Segmentazione proposizionale (clausole via dep-tree).

Spezza ogni frase nelle sue **proposizioni** (clausole) usando l'albero delle
dipendenze Stanza già prodotto da `annotazione.annota`. Granularità più fine
della frase → unità singole valutabili da `argument_mining` / `sequitur`
(entailment premessa→tesi su proposizioni isolate, non su frasi multi-clausola).

Tecnologia: **deterministica**, solo Stanza (nessuna nuova dipendenza).

Algoritmo (per ogni frase con dep-tree):
  1. Teste di clausola = token con `upos ∈ {VERB, AUX}` e `deprel` (o suo prefisso
     prima di ':') ∈ {root, conj, advcl, ccomp, acl, relcl, parataxis, csubj}.
     La radice (deprel=root / head=0) è sempre una testa di clausola.
  2. Ogni token è assegnato alla **testa di clausola più vicina risalendo** (clause
     owner): partiziona i token in clausole disgiunte (le subordinate annidate
     escono dalla matrice).
  3. Testo della proposizione = ricostruito dalle run contigue di token-locali
     sugli offset di carattere (Fase 1) → preserva la forma originale e scarta il
     materiale delle clausole annidate incastonate. Fallback: join dei `word.text`.

Fallback (`doc.backend != "stanza"` o frase senza dep): **1 proposizione = 1 frase**
(identità). Degrada gracefully, niente crash.
"""

from __future__ import annotations

from .annotazione import AnnotatedDoc, Sentence, Word
from ..schemas import Proposizione


# deprel (prefisso prima di ':') che introducono una clausola, se la testa è verbale
_CLAUSE_DEPRELS = {
    "root", "conj", "advcl", "ccomp", "acl", "relcl", "parataxis", "csubj",
}
_VERBAL = {"VERB", "AUX"}

# Pronomi "leggeri" / relative fuse: l'antecedente è semanticamente vuoto senza la
# relativa («ciò che…», «quello che…», «colui che…», «chi…»). Staccare la relcl
# frammenterebbe il predicato — es. la petitio «X è ciò che Y» si spezzerebbe in
# «X è ciò» + «che Y», azzerando l'entailment premessa↔tesi (circolarità mancata).
# Lemmi UD-Stanza IT (forme accentate e ASCII-stripped dalle batterie).
_ANTECEDENTE_FUSO = {
    "cio", "ciò", "quello", "quella", "quelli", "quelle",
    "colui", "colei", "coloro", "chi", "quanto", "quanti", "quanta", "quante",
}

_MIN_CHARS = 6     # scarta frammenti (punteggiatura, ausiliari isolati)
_MIN_WORDS = 2


def _deprel_base(deprel: str) -> str:
    return (deprel or "dep").split(":", 1)[0]


def _is_clause_head(w: Word, idx: int, words: list[Word], cop_heads: set[int]) -> bool:
    base = _deprel_base(w.deprel)
    if base == "root" or w.head == 0:
        return True
    if base not in _CLAUSE_DEPRELS:
        return False
    # Relativa fusa: relcl il cui antecedente è un pronome dimostrativo leggero
    # (ciò/quello/colui/chi…) → NON è una clausola autonoma, resta col suo
    # antecedente per non frammentare il predicato (es. petitio «X è ciò che Y»).
    if base == "acl" and 1 <= w.head <= len(words):
        ante = words[w.head - 1]
        if ante.upos == "PRON" and (ante.lemma or ante.text).lower() in _ANTECEDENTE_FUSO:
            return False
    # Testa di clausola: verbale OPPURE predicato copulare (clausola «X è ADJ/NOUN/
    # PRON», testa il predicato col copula come dipendente `cop`). Senza questo, una
    # subordinata copulare — es. la premessa «perché è ciò che la giustizia richiede»
    # — non verrebbe mai isolata, e la petitio resterebbe invisibile (van Dalen ch06).
    return (w.upos in _VERBAL) or (idx in cop_heads)


def _clause_owner(idx: int, words: list[Word], heads_set: set[int]) -> int:
    """Testa di clausola più vicina risalendo l'albero da `idx` (1-based)."""
    cur = idx
    seen: set[int] = set()
    while cur not in seen:
        seen.add(cur)
        if cur in heads_set:
            return cur
        w = words[cur - 1]
        if w.head == 0 or w.head < 1 or w.head > len(words):
            return cur
        cur = w.head
    return cur   # guardia anti-ciclo


def _detok(tokens: list[str]) -> str:
    """Detokenizer leggero IT (fallback senza offset): punteggiatura attaccata,
    nessuno spazio dopo apostrofo o dopo parentesi/virgolette aperte."""
    out = ""
    for t in tokens:
        if not out:
            out = t
        elif t in {",", ".", ";", ":", "!", "?", ")", "]", "»", "”", "…", "%"}:
            out += t
        elif out[-1] in {"(", "[", "«", "“"} or out.endswith(("'", "’")):
            out += t
        else:
            out += " " + t
    return out


def _ricostruisci(local_idx: list[int], words: list[Word], testo: str) -> tuple[str, tuple[int, int]]:
    """Testo + span da indici locali (1-based, ordinati). Usa gli offset di
    carattere unendo le run contigue (scarta il materiale annidato in mezzo);
    fallback al join dei token se gli offset mancano."""
    have_offsets = bool(local_idx) and all(
        words[i - 1].end_char > words[i - 1].start_char for i in local_idx)
    if have_offsets:
        # fonde le run i cui token sono consecutivi nella sequenza locale
        merged: list[list[int]] = []
        prev_word_idx = None
        for i in local_idx:
            w = words[i - 1]
            if prev_word_idx is not None and i == prev_word_idx + 1 and merged:
                merged[-1][1] = w.end_char
            else:
                merged.append([w.start_char, w.end_char])
            prev_word_idx = i
        pezzi = [testo[a:b] for a, b in merged if 0 <= a < b <= len(testo)]
        text = " ".join(p.strip() for p in pezzi if p.strip())
        span = (merged[0][0], merged[-1][1]) if merged else (0, 0)
        if text.strip():
            return text.strip(), span
    # fallback: join dei token
    return _detok([words[i - 1].text for i in local_idx]), (0, 0)


def _segmenta_frase(s: Sentence, frase_idx: int, testo: str) -> list[Proposizione]:
    words = s.words
    if not words or not any(w.head for w in words):
        # nessun dep-tree utile → frase intera come unica proposizione
        return [Proposizione(testo=s.text.strip(), span_char=(s.start_char, s.end_char),
                             frase_idx=frase_idx, deprel_origine="frase")]

    # Predicati con copula `cop` dipendente: teste di clausola copulare anche se
    # non verbali (ADJ/NOUN/PRON). UD attacca la copula al predicato.
    cop_heads = {w.head for w in words
                 if _deprel_base(w.deprel) == "cop" and 1 <= w.head <= len(words)}
    heads_set = {i for i, w in enumerate(words, start=1)
                 if _is_clause_head(w, i, words, cop_heads)}
    if not heads_set:
        return [Proposizione(testo=s.text.strip(), span_char=(s.start_char, s.end_char),
                             frase_idx=frase_idx, deprel_origine="frase")]

    # partiziona i token per clause owner
    gruppi: dict[int, list[int]] = {}
    for i in range(1, len(words) + 1):
        owner = _clause_owner(i, words, heads_set)
        gruppi.setdefault(owner, []).append(i)

    props: list[Proposizione] = []
    for head_idx, local_idx in gruppi.items():
        local_idx.sort()
        text, span = _ricostruisci(local_idx, words, testo)
        text = text.strip().strip(",;:").strip()     # ripulisce punteggiatura ai bordi
        n_words = sum(1 for i in local_idx if any(c.isalnum() for c in words[i - 1].text))
        if len(text.strip()) < _MIN_CHARS or n_words < _MIN_WORDS:
            continue
        head_w = words[head_idx - 1]
        props.append(Proposizione(
            testo          = text.strip(),
            span_char      = span,
            frase_idx      = frase_idx,
            head_lemma     = head_w.lemma or head_w.text,
            deprel_origine = _deprel_base(head_w.deprel),
        ))
    if not props:
        return [Proposizione(testo=s.text.strip(), span_char=(s.start_char, s.end_char),
                             frase_idx=frase_idx, deprel_origine="frase")]
    # ordine di superficie
    props.sort(key=lambda p: p.span_char[0])
    return props


def segmenta_proposizioni(doc: AnnotatedDoc) -> list[Proposizione]:
    """Lista di `Proposizione` (clausole) di tutto il documento.

    Con dep-tree Stanza: spezza ogni frase nelle sue clausole. In fallback
    (`backend != "stanza"`): 1 proposizione per frase (identità)."""
    out: list[Proposizione] = []
    if doc.backend != "stanza":
        for i, s in enumerate(doc.sentences):
            t = s.text.strip()
            if t:
                out.append(Proposizione(testo=t, span_char=(s.start_char, s.end_char),
                                        frase_idx=i, deprel_origine="frase"))
        return out
    for i, s in enumerate(doc.sentences):
        out.extend(_segmenta_frase(s, i, doc.text))
    return out


def backend_info() -> dict:
    return {"modulo": "chunking", "metodo": "dep-tree clausale (Stanza) / fallback frase"}
