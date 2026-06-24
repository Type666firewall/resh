"""resh/stilometria.py — feature stilistiche Biber-style (subset IT).

Riferimento: BiberPlus / Neurobiber (https://github.com/davidjurgens/biberplus,
paper https://arxiv.org/abs/2502.18590).

Subset di 20+ feature italiane calcolabili da AnnotatedDoc UD:
  - pronomi 1ª/2ª/3ª persona (frequenza per 1000 token)
  - costrutti passivi (Voice=Pass o aux:pass)
  - modali (potere/dovere/volere)
  - subordinate (acl, advcl, ccomp, xcomp)
  - nominalizzazioni (suffissi -zione/-mento/-tà/-ezza)
  - frequenza connettivi (causali/avversativi/concessivi da lessici)
  - rapporto frasi dichiarative vs interrogative
  - densità citazioni dirette (virgolette)

Output: dict[str, float] — feature normalizzate per 1000 token. Usato come
componente diagnostico e per `deriva_registro` (Patologia) se varianza
intra-testo > soglia (TODO: futura comparazione multi-testo).
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .annotazione import AnnotatedDoc


_LESSICI_DIR = Path(__file__).parent.parent / "lessici"


def _load_lex(name: str) -> set[str]:
    p = _LESSICI_DIR / name
    if not p.exists():
        return set()
    return {ln.strip().lower() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()}


_CAUSALI    = _load_lex("connettivi_causali_it.txt")
_AVVERSATIV = _load_lex("connettivi_avversativi_it.txt")
_CONCESSIVI = _load_lex("connettivi_concessivi_it.txt")

_MODALI       = {"potere", "dovere", "volere", "sapere"}    # lemma forms
_PRONOMI_1P   = {"io","me","mi","noi","ci","mio","mia","miei","mie","nostro","nostra","nostri","nostre"}
_PRONOMI_2P   = {"tu","te","ti","voi","vi","tuo","tua","tuoi","tue","vostro","vostra","vostri","vostre"}
_PRONOMI_3P   = {"egli","ella","esso","essa","essi","esse","lui","lei","loro","gli","le","si",
                 "suo","sua","suoi","sue","loro"}

_NOMINALIZ_SUFFIX = ("zione", "mento", "tà", "ità", "ezza", "anza", "enza")


def profilo_stilistico(doc: AnnotatedDoc) -> dict:
    counts: Counter = Counter()
    n_token = 0
    n_frasi = max(1, len(doc.sentences))
    n_quotes = 0

    for s in doc.sentences:
        # citazioni dirette: virgolette nel testo
        n_quotes += len(re.findall(r"[\"«»“”]", s.text))

        # interrogative
        if s.text.rstrip().endswith("?"):
            counts["sent_interrog"] += 1
        else:
            counts["sent_dichiar"] += 1

        for w in s.words:
            tok   = w.text.lower()
            lemma = (w.lemma or tok).lower()
            # stesso predicato di profilo_linguistico (almeno una lettera:
            # entrano le forme elise tipo "l'") — i due n_token devono coincidere
            if not any(c.isalpha() for c in tok):
                continue
            n_token += 1

            if tok in _PRONOMI_1P:
                counts["pron_1p"] += 1
            elif tok in _PRONOMI_2P:
                counts["pron_2p"] += 1
            elif tok in _PRONOMI_3P:
                counts["pron_3p"] += 1

            if lemma in _MODALI and w.upos == "VERB":
                counts["modali"] += 1

            if w.deprel in {"acl", "advcl", "ccomp", "xcomp", "acl:relcl"}:
                counts["subord"] += 1

            if w.deprel == "aux:pass" or w.deprel == "nsubj:pass":
                counts["passivi"] += 1

            if w.upos == "NOUN" and any(tok.endswith(sfx) for sfx in _NOMINALIZ_SUFFIX):
                counts["nominalizzazioni"] += 1

            if tok in _CAUSALI:
                counts["conn_causali"] += 1
            elif tok in _AVVERSATIV:
                counts["conn_avversativi"] += 1
            elif tok in _CONCESSIVI:
                counts["conn_concessivi"] += 1

    n_token = max(1, n_token)
    norm = 1000.0 / n_token

    out = {
        "n_token":          n_token,
        "n_frasi":          n_frasi,
        "pron_1p_per1k":    round(counts["pron_1p"]   * norm, 3),
        "pron_2p_per1k":    round(counts["pron_2p"]   * norm, 3),
        "pron_3p_per1k":    round(counts["pron_3p"]   * norm, 3),
        "modali_per1k":     round(counts["modali"]    * norm, 3),
        "subord_per1k":     round(counts["subord"]    * norm, 3),
        "passivi_per1k":    round(counts["passivi"]   * norm, 3),
        "nominaliz_per1k":  round(counts["nominalizzazioni"] * norm, 3),
        "conn_causali_per1k":     round(counts["conn_causali"]     * norm, 3),
        "conn_avversativi_per1k": round(counts["conn_avversativi"] * norm, 3),
        "conn_concessivi_per1k":  round(counts["conn_concessivi"]  * norm, 3),
        "rapporto_interrog_dichiar": round(
            counts["sent_interrog"] / max(1, counts["sent_dichiar"]), 4),
        "quotes_per1k":     round(n_quotes * norm, 3),
    }
    return out
