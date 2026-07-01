"""resh/annotazione.py — Singleton Stanza UD italiano + fallback regex.

API canonica: `annota(testo: str) -> AnnotatedDoc`.

`AnnotatedDoc` è un dataclass interno che esporta SOLO i campi consumati
dai moduli `profilo_linguistico` / `stilometria` / `bias_autorita` /
`coerenza` / `argument_mining`. Non è `stanza.Document` (deliberato:
isola le dip pesanti dietro un contratto stabile).

Backend:
  1. Stanza UD italiano (https://stanfordnlp.github.io/stanza/) se installato
     e modelli scaricati. Processors: tokenize,mwt,pos,lemma,depparse,ner.
     GPU automatico se `torch.cuda.is_available()`.
  2. Fallback regex-based se stanza assente — degrada gracefully:
     tokenizza su whitespace+punctuation, POS=X, deprel=dep, NER vuoto.
     Sufficiente per pipeline-smoke deterministica.

Setup primo avvio (manuale, Σ_w):
    >>> import stanza
    >>> stanza.download('it', processors='tokenize,mwt,pos,lemma,depparse,ner')

Override env: `P3_RESH_STANZA_DISABLE=1` forza fallback (utile per CI).
Cache: il modulo Stanza è caricato 1x (singleton); il risultato di annota()
è cached via `cache.cached("v1")` se P3_RESH_CACHE_DISABLE != "1".
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

from ..cache import cache_get, cache_set

logger = logging.getLogger(__name__)


# ─── dataclass API canonica ──────────────────────────────────────────────────

@dataclass
class Word:
    text:   str
    lemma:  str = ""
    upos:   str = "X"        # UD POS tag
    head:   int = 0          # 1-indexed in UD (0 = root)
    deprel: str = "dep"
    start_char: int = 0      # offset nel testo originale (0 = ignoto/fallback)
    end_char:   int = 0      # abilita span di clausola precisi (chunking.py)


@dataclass
class Sentence:
    text:  str
    words: list[Word] = field(default_factory=list)
    start_char: int = 0
    end_char:   int = 0


@dataclass
class Entity:
    text:    str
    type:    str            # PER, ORG, LOC, MISC
    start_char: int = 0
    end_char:   int = 0


@dataclass
class AnnotatedDoc:
    text:      str
    sentences: list[Sentence] = field(default_factory=list)
    entities:  list[Entity]   = field(default_factory=list)
    backend:   str            = "fallback"   # "stanza" | "fallback"


# ─── singleton Stanza (lazy, uno per lingua) ─────────────────────────────────

_STANZA_PIPELINES: dict[str, object] = {}
_STANZA_AVAILABLE: dict[str, bool] = {}


def _stanza_disabled() -> bool:
    return os.getenv("P3_RESH_STANZA_DISABLE") == "1"


def _try_load_stanza():
    from .. import config
    lang = config.LANG.get()
    if _STANZA_AVAILABLE.get(lang) is False:
        return None
    if lang in _STANZA_PIPELINES:
        return _STANZA_PIPELINES[lang]
    try:
        import stanza  # noqa: F401
        use_gpu = False
        try:
            import torch
            use_gpu = bool(torch.cuda.is_available())
        except Exception:
            pass
        # ml_registry: stanza-it/stanza-en ~700 MB (mix GPU/CPU)
        try:
            from ml_registry import acquire as _ml_acquire
            _ml_acquire(f"stanza-{lang}")
        except Exception:
            pass
        # mwt (multi-word token expansion) è un processor italiano-specifico:
        # l'inglese non ne ha bisogno e stanza rifiuta il processor se richiesto.
        processors = ("tokenize,pos,lemma,depparse,ner" if lang == "en"
                      else "tokenize,mwt,pos,lemma,depparse,ner")
        _STANZA_PIPELINES[lang] = stanza.Pipeline(
            lang       = lang,
            processors = processors,
            use_gpu    = use_gpu,
            verbose    = False,
            download_method = None,   # NO download automatici (Σ_w controlla)
        )
        _STANZA_AVAILABLE[lang] = True
        return _STANZA_PIPELINES[lang]
    except Exception as exc:
        # Stanza non installato o modelli non scaricati per questa lingua → fallback silente
        logger.warning("stanza non disponibile per lang=%s, fallback regex: %s", lang, exc)
        _STANZA_AVAILABLE[lang] = False
        return None


# ─── Fallback regex-based ────────────────────────────────────────────────────

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-ÝΑ-Ω])")
_TOKEN_RE   = re.compile(r"\w+|[^\w\s]", re.UNICODE)


# Euristiche POS grossolane del fallback regex, per lingua — deliberatamente
# minimali (nessuna morfologia reale): degradano gracefully, non sostituiscono Stanza.
_FALLBACK_POS_IT = {
    "det":   {"il","la","lo","i","le","gli","un","uno","una","del","della"},
    "cconj": {"e","o","ma"},
    "sconj": {"quindi","perché","se","mentre"},
    "adv":   {"non","mai","sempre","molto","poco","più","meno"},
    "verb_suffix": ("are","ere","ire","ato","uto","ito","ando","endo"),
    "noun_suffix": ("zione","mento","tà","ità","ezza","anza","enza"),
}
_FALLBACK_POS_EN = {
    "det":   {"the","a","an","this","that","these","those","my","your","his","her","its","our","their"},
    "cconj": {"and","or","but"},
    "sconj": {"yet","so","because","if","while","although","though","therefore","thus","hence","consequently"},
    "adv":   {"not","never","always","very","often","quite","too","more","less"},
    "verb_suffix": ("ing","ed"),
    "noun_suffix": ("tion","ment","ity","ness","ism","ance","ence"),
}


def _annota_fallback(testo: str) -> AnnotatedDoc:
    """Tokenizzazione/segmentazione minimal — niente POS reali."""
    from .. import config
    pos = _FALLBACK_POS_EN if config.LANG.get() == "en" else _FALLBACK_POS_IT
    sentences: list[Sentence] = []
    cursor = 0
    for raw in _SENT_SPLIT.split(testo):
        if not raw.strip():
            continue
        start = testo.find(raw, cursor)
        end   = start + len(raw)
        cursor = end
        words: list[Word] = []
        for m in _TOKEN_RE.finditer(raw):
            tok = m.group(0)
            # Euristica grossolana POS:
            if tok.isalpha():
                low = tok.lower()
                if low in pos["det"]:
                    upos = "DET"
                elif low in pos["cconj"]:
                    upos = "CCONJ"
                elif low in pos["sconj"]:
                    upos = "SCONJ"
                elif low in pos["adv"]:
                    upos = "ADV"
                elif low.endswith(pos["verb_suffix"]):
                    upos = "VERB"
                elif low.endswith(pos["noun_suffix"]):
                    upos = "NOUN"
                else:
                    upos = "NOUN"     # default conservativo
            elif tok.isdigit():
                upos = "NUM"
            else:
                upos = "PUNCT"
            words.append(Word(text=tok, lemma=tok.lower(), upos=upos))
        sentences.append(Sentence(text=raw, words=words,
                                  start_char=start, end_char=end))
    return AnnotatedDoc(text=testo, sentences=sentences, entities=[],
                        backend="fallback")


# ─── Stanza adapter (real backend) ───────────────────────────────────────────

def _word_char_span(w) -> tuple[int, int]:
    """Offset (start,end) di una Word Stanza. Diretti se presenti, altrimenti
    via token parent (MWT: le sub-word condividono lo span del token). (0,0) se
    ignoti — chunking degraderà gracefully su quella parola."""
    sc = getattr(w, "start_char", None)
    ec = getattr(w, "end_char", None)
    if sc is None or ec is None:
        parent = getattr(w, "parent", None)
        if parent is not None:
            sc = getattr(parent, "start_char", None) if sc is None else sc
            ec = getattr(parent, "end_char", None)   if ec is None else ec
    return (int(sc) if sc is not None else 0,
            int(ec) if ec is not None else 0)


def _annota_stanza(testo: str, pipeline) -> AnnotatedDoc:
    doc = pipeline(testo)
    sentences: list[Sentence] = []
    for s in doc.sentences:
        words: list[Word] = []
        for w in s.words:
            wsc, wec = _word_char_span(w)
            words.append(Word(
                text   = w.text,
                lemma  = (w.lemma or w.text).lower(),
                upos   = w.upos or "X",
                head   = int(w.head) if w.head is not None else 0,
                deprel = w.deprel or "dep",
                start_char = wsc,
                end_char   = wec,
            ))
        start = s.tokens[0].start_char if s.tokens and s.tokens[0].start_char is not None else 0
        end   = s.tokens[-1].end_char  if s.tokens and s.tokens[-1].end_char  is not None else 0
        sentences.append(Sentence(text=s.text, words=words,
                                  start_char=start, end_char=end))
    entities: list[Entity] = []
    for ent in getattr(doc, "entities", []) or []:
        entities.append(Entity(
            text       = ent.text,
            type       = ent.type,
            start_char = ent.start_char or 0,
            end_char   = ent.end_char   or 0,
        ))
    return AnnotatedDoc(text=testo, sentences=sentences, entities=entities,
                        backend="stanza")


# ─── API pubblica ────────────────────────────────────────────────────────────

def annota(testo: str) -> AnnotatedDoc:
    """Annota un testo con UD POS + lemma + deprel + NER (se Stanza disponibile).

    Fallback degradato a regex tokenizer + POS euristica. Cache disk attiva
    (chiave sha256(testo+'v1')).
    """
    return _annota(testo)


def _annota(testo: str) -> dict:
    """Wrapper cached: serializza AnnotatedDoc → dict per cache JSON.

    Cache SOLO per risultati Stanza: un'annotazione fallback in cache
    avvelenerebbe i run successivi a stack pieno (backend diverso ⇒ ε diversa,
    silenziosamente). Il fallback regex costa nulla: si ricalcola sempre.
    """
    hit = cache_get(testo, "annota_v2", extra="_annota")
    if hit is not None and hit.get("backend") == "stanza":
        return hit
    if _stanza_disabled():
        doc = _annota_fallback(testo)
    else:
        pipe = _try_load_stanza()
        doc = _annota_stanza(testo, pipe) if pipe is not None else _annota_fallback(testo)
    d = _doc_to_dict(doc)
    if d.get("backend") == "stanza":
        cache_set(testo, "annota_v2", d, extra="_annota")
    return d


# Ma per usabilità: annota() ritorna AnnotatedDoc, non dict.
def annota(testo: str) -> AnnotatedDoc:  # noqa: F811
    d = _annota(testo)
    return _doc_from_dict(d)


def _doc_to_dict(doc: AnnotatedDoc) -> dict:
    return {
        "text":     doc.text,
        "backend":  doc.backend,
        "sentences": [
            {
                "text": s.text,
                "start_char": s.start_char,
                "end_char":   s.end_char,
                "words": [
                    {"text": w.text, "lemma": w.lemma, "upos": w.upos,
                     "head": w.head, "deprel": w.deprel,
                     "start_char": w.start_char, "end_char": w.end_char}
                    for w in s.words
                ],
            } for s in doc.sentences
        ],
        "entities": [
            {"text": e.text, "type": e.type,
             "start_char": e.start_char, "end_char": e.end_char}
            for e in doc.entities
        ],
    }


def _doc_from_dict(d: dict) -> AnnotatedDoc:
    sentences = [
        Sentence(
            text       = s["text"],
            start_char = s.get("start_char", 0),
            end_char   = s.get("end_char", 0),
            words      = [Word(**w) for w in s.get("words", [])],
        )
        for s in d.get("sentences", [])
    ]
    entities = [Entity(**e) for e in d.get("entities", [])]
    return AnnotatedDoc(
        text=d.get("text", ""), sentences=sentences,
        entities=entities, backend=d.get("backend", "fallback"),
    )


def reset_singleton() -> None:
    """Forza ricarica delle pipeline al prossimo annota() — test-utility."""
    _STANZA_PIPELINES.clear()
    _STANZA_AVAILABLE.clear()


def backend_info() -> str:
    from .. import config
    lang = config.LANG.get()
    if _stanza_disabled():
        return "fallback (P3_RESH_STANZA_DISABLE=1)"
    if lang not in _STANZA_AVAILABLE:
        return "lazy (not loaded)"
    return "stanza" if _STANZA_AVAILABLE[lang] else "fallback (stanza unavailable)"
