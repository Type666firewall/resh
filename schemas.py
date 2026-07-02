"""resh/schemas.py — Dataclass + Enum patologie ऋ.

Preserva i dataclass legacy (PremessaAnalisi, Argomento, VerificaLogica,
Teleologia, AutoritaCriteri, RapportoResh) — compat output §6 yaml_output.

Nuovo: `TipoPatologia` (StrEnum) + `Patologia` (struttura tipata).
Campi nuovi su RapportoResh aggiunti con default → backward-compat.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TipoPatologia(str, Enum):
    """Tassonomia patologie ऋ — riferimento MAFALDA L2 + estensioni."""
    FALLACIA_LOGICA       = "fallacia_logica"
    NON_SEQUITUR          = "non_sequitur"        # premesse ↛ conclusione (van Dalen ch01/ch06)
    PREMESSA_NON_ENTAILED = "premessa_non_entailed"
    INCOERENZA_TEMATICA   = "incoerenza_tematica"
    INCOERENZA_LOCALE     = "incoerenza_locale"
    HEDGING_ECCESSIVO     = "hedging_eccesso"
    BOOSTER_ECCESSIVO     = "booster_eccesso"
    APPELLO_AUTORITA      = "ad_verecundiam"
    DERIVA_REGISTRO       = "deriva_registro"
    DENSITA_CRITICA       = "densita_critica"
    # Incoerenza INTRINSECA dell'Obiettivo O (O fallibile rappresentazione del volere).
    # Segnale strutturale, NON verdetto: la qualifica produttiva (ऋ⁵)/dissimulata è induttiva.
    OBIETTIVO_CONTRADDITTORIO = "obiettivo_contraddittorio"   # dichiarato↔latente in contraddizione (mauvaise foi)
    OBIETTIVO_DISPERSO        = "obiettivo_disperso"          # dichiarato↔latente scollegati (cattiva induzione)


@dataclass
class Patologia:
    tipo:           TipoPatologia
    severita:       float                            # 0-1
    confidence:     float                            # 0-1
    span_char:      Optional[tuple[int, int]] = None
    dettaglio:      dict                      = field(default_factory=dict)
    origine_modulo: str                       = ""

    def __post_init__(self):
        assert 0.0 <= self.severita   <= 1.0, f"severita={self.severita}"
        assert 0.0 <= self.confidence <= 1.0, f"confidence={self.confidence}"

    def as_message(self) -> str:
        """Forma `list[str]` legacy (campo `RapportoResh.patologie`)."""
        s = f"[{self.tipo.value}] sev={self.severita:.2f} conf={self.confidence:.2f}"
        if self.dettaglio:
            kv = ", ".join(f"{k}={v}" for k, v in self.dettaglio.items())
            s += f" — {kv}"
        return s


# ─── Dataclass legacy preservati (compat output) ─────────────────────────────

@dataclass
class PremessaAnalisi:
    esplicite: list[str] = field(default_factory=list)
    implicite: list[str] = field(default_factory=list)
    sospette:  list[str] = field(default_factory=list)
    score:     float     = 0.0


@dataclass
class Argomento:
    testo:           str
    tesi_supportata: str
    tipo:            str
    premesse_usate:  list[str] = field(default_factory=list)
    confidence:      float = 0.0   # score NLI etichetta "premessa"; 0.0 = fallback euristico


@dataclass
class Proposizione:
    """Unità proposizionale (clausola) estratta da una frase via dep-tree.
    Granularità più fine della frase: abilita la valutazione delle singole
    proposizioni (chunking.py)."""
    testo:          str
    span_char:      tuple[int, int]
    frase_idx:      int
    head_lemma:     str = ""
    deprel_origine: str = "root"     # perché scorporata: root/conj/advcl/acl:relcl/…


@dataclass
class VerificaLogica:
    argomento: str
    tipo:      str
    valido:    bool
    fallacia:  Optional[str] = None
    nota:      str = ""


@dataclass
class Teleologia:
    obiettivo_dichiarato: str
    obiettivo_latente:    Optional[str]
    coerenza:             float
    nota:                 str = ""


@dataclass
class AutoritaCriteri:
    fonte:         str
    expertise:     bool
    bias_rilevati: list[str] = field(default_factory=list)
    credibilita:   float = 0.5


@dataclass
class RapportoResh:
    testo:          str
    premesse:       PremessaAnalisi
    inventario:     list[Argomento]
    verifiche:      list[VerificaLogica]
    teleologia:     Teleologia
    autorita:       AutoritaCriteri
    eps_resh:       float
    patologie:      list[str]
    yaml_output:    dict
    densita_logica: float = 0.0
    fascia_densita: str   = "bassa"
    malafede_mod:   float = 1.0   # frozen 1.0, vedi γ_diagnosi_malafede (modulatore rimosso, ADR-005)

    # Campi O-22 (NLP deterministico) — additive, default neutri:
    # NB: TrilemmaHit è definito sotto, fuori da RapportoResh.
    patologie_strutturate: list[Patologia] = field(default_factory=list)
    profilo_linguistico:   dict            = field(default_factory=dict)
    coerenza_semantica:    dict            = field(default_factory=dict)
    profilo_stilistico:    dict            = field(default_factory=dict)
    componenti_epsilon:    dict            = field(default_factory=dict)
    sintesi_narrativa:     Optional[str]   = None     # storico: sempre None dal 2026-06-12 (ADR-005); conservato per i run persistiti

    # Lato induttivo (additivi, default None — popolati solo con induttivo_llm=True):
    # `induttivo` = RapportoInduttivo.as_dict(); `quadro_epsilon` = QuadroEpsilon.as_dict()
    # (quest'ultimo SEMPRE calcolato: con induttivo OFF è il quadro det-only).
    induttivo:             Optional[dict]  = None
    quadro_epsilon:        Optional[dict]  = None
    induttivo_richiesto:   bool            = False  # True se induttivo_llm=True o env P3_RESH_INDUTTIVO=1


# ─── Trilemma pre-detection ─────────────────────────────────────────────────

@dataclass
class TrilemmaHit:
    """Singola rilevazione Trilemma (pre-detection deterministica o LLM).

    `fonte` discrimina l'origine del segnale:
    - "marker_regex"  : match su trilemma_markers_it.json
    - "sequitur"      : NON_SEQUITUR con C3_candidato da sequitur.py
    - "circolarita"   : petitio_principii confermata da fallacie.py
    - "llm"           : classificazione induttiva

    Il MODO (USE/MENTION/DIAGNOSIS) non è determinabile dal solo marker regex —
    richiede contesto (LLM). I hit deterministici hanno modo="" (non assegnato).
    """
    corno:       str                    # "C1"|"C2"|"C3"|"INCL"|"NONE"
    sottotipo:   str                    # da tassonomia SCHEMA v1.2
    confidence:  float                  # 0-1
    span_testo:  str                    # porzione di testo matchata
    fonte:       str                    # "marker_regex"|"sequitur"|"circolarita"|"llm"
    modo:        str = ""               # USE|MENTION|DIAGNOSIS|SELF_DIAGNOSIS (solo llm)
    polarita:    str = ""               # patologica|strumentale|virtuosa|neutra
    dettaglio:   dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        d = {
            "corno": self.corno, "sottotipo": self.sottotipo,
            "confidence": self.confidence, "span_testo": self.span_testo,
            "fonte": self.fonte,
        }
        if self.modo:
            d["modo"] = self.modo
        if self.polarita:
            d["polarita"] = self.polarita
        if self.dettaglio:
            d["dettaglio"] = self.dettaglio
        return d
