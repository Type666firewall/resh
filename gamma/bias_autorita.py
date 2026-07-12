"""resh/bias_autorita.py — NER + lessico hedging/booster + ad verecundiam.

Rileva:
  - hedging_ratio  = #hedges / n_token  → SEGNALE DESCRITTIVO (provvisorietà
    fallibilista, non un bias): rilevato e visibile, ma NON erode ε (B1, 2026-07)
  - booster_ratio  = #boosters / n_token → bias verso assolutismo (petitio) → ε
  - pattern ad_verecundiam non-citato (NER PER + verbo dicendi + no quote)
  - bias multipli accumulati → flag su `AutoritaCriteri.bias_rilevati`

Lessici caricati da `resh/lessici/*.txt`. NER da `AnnotatedDoc.entities`
(Stanza NER it) se backend=='stanza'; altrimenti euristica capitalizzazione.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .annotazione import AnnotatedDoc
from ..schemas import AutoritaCriteri, Patologia, TipoPatologia


_LESSICI_DIR = Path(__file__).parent.parent / "lessici"


def _load_lex(name: str) -> set[str]:
    p = _LESSICI_DIR / name
    if not p.exists():
        return set()
    return {
        line.strip().lower()
        for line in p.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


_AD_VEREC_RE_IT = re.compile(
    r"\bcome\s+(?:disse|sostiene|sosteneva|afferma|affermava|dimostra|dimostrò|"
    r"ha\s+detto|scriveva|insegnava)\s+([A-ZÀ-Ý][a-zà-ÿ]+(?:\s+[A-ZÀ-Ý][a-zà-ÿ]+)?)",
    re.UNICODE,
)
_AD_VEREC_RE_EN = re.compile(
    r"\b(?:as\s+(?:said|argued|claimed|argues|claims|demonstrated|demonstrates|wrote|stated)\s+by\s+"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)|"
    r"as\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:said|argued|claims|argues|wrote|stated))\b"
)

_LEX_CACHE: dict[str, tuple] = {}


def _get_lexicons(lang: str) -> tuple:
    """(hedge_re, booster_re, ad_verec_re) per lingua — cache per processo."""
    if lang not in _LEX_CACHE:
        hedges   = _load_lex(f"hedging_{lang}.txt")
        boosters = _load_lex(f"booster_{lang}.txt")
        hedge_re   = re.compile(r"\b(" + "|".join(re.escape(h) for h in sorted(hedges,   key=len, reverse=True)) + r")\b",
                                re.IGNORECASE) if hedges else None
        booster_re = re.compile(r"\b(" + "|".join(re.escape(b) for b in sorted(boosters, key=len, reverse=True)) + r")\b",
                                re.IGNORECASE) if boosters else None
        ad_verec_re = _AD_VEREC_RE_EN if lang == "en" else _AD_VEREC_RE_IT
        _LEX_CACHE[lang] = (hedge_re, booster_re, ad_verec_re)
    return _LEX_CACHE[lang]


def _conta_match(testo: str, regex: re.Pattern | None) -> int:
    if regex is None:
        return 0
    return len(regex.findall(testo))


def _persone_da_doc(doc: AnnotatedDoc) -> list[str]:
    """Estrae nomi propri di persona — Stanza NER se disponibile, altrimenti
    cattura sequenze di token capitalizzati (euristica conservativa)."""
    if doc.entities:
        return [e.text for e in doc.entities
                if e.type in {"PER", "PERSON"} and e.text.replace(" ", "").isalpha()]
    # fallback: token consecutivi capitalizzati
    persone = []
    for s in doc.sentences:
        buf: list[str] = []
        for w in s.words:
            if w.text and w.text[0].isupper() and w.text.isalpha():
                buf.append(w.text)
            else:
                if len(buf) >= 1 and not (len(buf) == 1 and buf[0] in {"Il", "La", "Lo", "I", "Le"}):
                    persone.append(" ".join(buf))
                buf = []
        if buf:
            persone.append(" ".join(buf))
    return persone


def analizza_bias_autorita(testo: str, doc: AnnotatedDoc) -> tuple[AutoritaCriteri, list[Patologia]]:
    """Ritorna (AutoritaCriteri legacy, list[Patologia] strutturato)."""

    from .. import config
    hedge_re, booster_re, ad_verec_re = _get_lexicons(config.LANG.get())

    n_token = max(1, sum(1 for s in doc.sentences for w in s.words
                         if w.text.isalpha()))

    n_hedges   = _conta_match(testo, hedge_re)
    n_boosters = _conta_match(testo, booster_re)

    hedging_ratio  = n_hedges   / n_token
    booster_ratio  = n_boosters / n_token

    patologie: list[Patologia] = []
    bias_rilevati: list[str] = []

    if hedging_ratio > 0.06:
        sev = min(1.0, hedging_ratio / 0.15)
        patologie.append(Patologia(
            tipo       = TipoPatologia.HEDGING_ECCESSIVO,
            severita   = sev,
            confidence = 0.8,
            dettaglio  = {"ratio": round(hedging_ratio, 4), "n": n_hedges},
            origine_modulo = "bias_autorita",
        ))
        bias_rilevati.append(f"hedging_eccesso({hedging_ratio:.3f})")

    if booster_ratio > 0.04:
        sev = min(1.0, booster_ratio / 0.12)
        patologie.append(Patologia(
            tipo       = TipoPatologia.BOOSTER_ECCESSIVO,
            severita   = sev,
            confidence = 0.8,
            dettaglio  = {"ratio": round(booster_ratio, 4), "n": n_boosters},
            origine_modulo = "bias_autorita",
        ))
        bias_rilevati.append(f"booster_eccesso({booster_ratio:.3f})")

    # ad verecundiam non citato: PER + verbo dicendi, senza virgolette nelle ~80 char dopo
    av_matches = list(ad_verec_re.finditer(testo))
    fonti_invocate: list[str] = []
    for m in av_matches:
        _nomi = [g for g in m.groups() if g]   # IT: 1 gruppo; EN: 2 alternativi, uno solo valorizzato
        nome = _nomi[0] if _nomi else ""
        fine = m.end()
        finestra = testo[fine : fine + 100]
        ha_virgolette = bool(re.search(r"[\"«»“”']", finestra))
        ha_riferimento = bool(re.search(r"\((?:cf|cfr|vedi|in)\.?\s+", finestra, re.I))
        if not (ha_virgolette or ha_riferimento):
            patologie.append(Patologia(
                tipo       = TipoPatologia.APPELLO_AUTORITA,
                severita   = 0.6,
                confidence = 0.65,
                span_char  = (m.start(), m.end()),
                dettaglio  = {"persona": nome, "contesto": testo[max(0, m.start()-30):m.end()+30]},
                origine_modulo = "bias_autorita",
            ))
            fonti_invocate.append(nome)
    if fonti_invocate:
        bias_rilevati.append(f"ad_verecundiam:{','.join(fonti_invocate[:3])}")

    # AutoritaCriteri legacy
    persone = _persone_da_doc(doc)
    fonte_label = persone[0] if persone else "sconosciuta"
    # expertise (A5, 2026-07): un nome proprio da solo NON è expertise — anche il
    # soggetto del testo («Berkeley», «Socrate») è un nome. Serve un nome NOMINATO
    # con un segnale di citazione (virgolette o riferimento bibliografico), non la
    # sua mera presenza. Riusa i marcatori già rilevati sul testo.
    ha_citazione = bool(re.search(r"[\"«»“”']", testo) or
                        re.search(r"\((?:cf|cfr|vedi|in)\.?\s+", testo, re.I))
    expertise = bool(persone) and ha_citazione

    # credibilità: baseline neutro-positivo, penalità SOLO per autorità non citata
    # (ad_verecundiam), bonus per testo pulito. NON reagisce più a hedge/booster
    # (B1+A1, 2026-07): l'hedging è fallibilismo (non bias), e il booster è già
    # penalizzato una volta sola in `bias_linguistico` — qui era doppio conteggio
    # su due componenti di ε. `credibilita_fonte` misura ora SOLO l'autorità/fonte,
    # coerente col suo nome.
    credibilita = 0.65
    credibilita -= 0.20 * (1 if fonti_invocate else 0)
    if not fonti_invocate:
        credibilita += 0.10   # nessuna autorità non citata → premio epistemico
    credibilita  = max(0.05, min(0.95, credibilita))

    autorita = AutoritaCriteri(
        fonte         = fonte_label,
        expertise     = expertise,
        bias_rilevati = bias_rilevati,
        credibilita   = round(credibilita, 4),
    )
    return autorita, patologie
