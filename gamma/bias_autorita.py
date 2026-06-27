"""resh/bias_autorita.py — NER + lessico hedging/booster + ad verecundiam.

Rileva:
  - hedging_ratio  = #hedges / n_token  → bias verso indeterminatezza
  - booster_ratio  = #boosters / n_token → bias verso assolutismo (petitio)
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


_HEDGES   = _load_lex("hedging_it.txt")
_BOOSTERS = _load_lex("booster_it.txt")

# Multi-word entries: precomputiamo regex per match in testo grezzo
_HEDGE_RE   = re.compile(r"\b(" + "|".join(re.escape(h) for h in sorted(_HEDGES,  key=len, reverse=True)) + r")\b",
                         re.IGNORECASE) if _HEDGES else None
_BOOSTER_RE = re.compile(r"\b(" + "|".join(re.escape(b) for b in sorted(_BOOSTERS, key=len, reverse=True)) + r")\b",
                         re.IGNORECASE) if _BOOSTERS else None

_AD_VEREC_RE = re.compile(
    r"\bcome\s+(?:disse|sostiene|sosteneva|afferma|affermava|dimostra|dimostrò|"
    r"ha\s+detto|scriveva|insegnava)\s+([A-ZÀ-Ý][a-zà-ÿ]+(?:\s+[A-ZÀ-Ý][a-zà-ÿ]+)?)",
    re.UNICODE,
)


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

    n_token = max(1, sum(1 for s in doc.sentences for w in s.words
                         if w.text.isalpha()))

    n_hedges   = _conta_match(testo, _HEDGE_RE)
    n_boosters = _conta_match(testo, _BOOSTER_RE)

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
    av_matches = list(_AD_VEREC_RE.finditer(testo))
    fonti_invocate: list[str] = []
    for m in av_matches:
        nome = m.group(1)
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
    # expertise: euristica conservativa — true solo se citata 1+ PER nominata
    expertise = bool(persone)

    # credibilità: baseline neutro-positivo, penalità per bias, bonus per testo pulito
    credibilita = 0.65
    credibilita -= 0.15 * (hedging_ratio > 0.06)
    credibilita -= 0.20 * (booster_ratio > 0.04)
    credibilita -= 0.20 * (1 if fonti_invocate else 0)
    if not (hedging_ratio > 0.06 or booster_ratio > 0.04 or fonti_invocate):
        credibilita += 0.10   # testo senza bias rilevati → premio epistemico
    credibilita  = max(0.05, min(0.95, credibilita))

    autorita = AutoritaCriteri(
        fonte         = fonte_label,
        expertise     = expertise,
        bias_rilevati = bias_rilevati,
        credibilita   = round(credibilita, 4),
    )
    return autorita, patologie
