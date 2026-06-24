"""resh/aggregatore.py — QuadroEpsilon: det ∥ ind a parità di ruolo.

Il quadro AFFIANCA i due lati, non li fonde (vincolo Σ_w, ratifica 2026-06-10):
  - `eps_resh` e `componenti_epsilon` sono ripresi VERBATIM dal deterministico —
    mai ricalcolati, mai modulati dai giudizi induttivi;
  - i contributi induttivi in errore sono SCARTATI e CONTATI (scarto binario:
    una call mezza rotta non ha un «peso di fiducia», non esiste base teorica);
  - NESSUN numero unico det+ind: per costruzione i lati vivono in liste separate.

Λ-nativo: ruoli (`eps_role`), provenienza (`eps_feeds`) e forma (`output_kind`)
sono letti dal registry `lambda_space.LAMBDA_RESH`, mai hardcoded. L'unica colla
locale è il puntatore d'estrazione (DOVE nel dict del rapporto vive l'output di
un dato γ/sotto-unità) — dichiarata in `_SOTTO_UNITA_GIUDIZIO`.

API dict-based (come report.py): invocabile sia dagli oggetti vivi sia dal
JSON persistito in DB.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Optional

from ..epsilon import COMPONENTI                      # dato: single source of truth
from ..lambda_space import LAMBDA_RESH                # registry: dato immutabile

SALUTI = ("ok", "bad_json", "error", "assente")

# Sotto-unità induttive che sono GIUDIZI autonomi (affiancano ε) vs gli assi
# dell'arsenale (rilievi per-angolazione). Solo raggruppamento presentazionale:
# l'eps_role resta quello del γ nel registry.
_SOTTO_UNITA_GIUDIZIO = {"trilemma", "inclosura", "sintesi", "malafede_o"}


@dataclass(frozen=True)
class ContributoEpsilon:
    """Un contributo al quadro: chi (γ), cosa (payload verbatim), in che stato."""
    gamma:         str                   # nome γ nel registry
    lato:          str                   # "det" | "ind"
    sotto_unita:   str                   # id asse/sezione induttiva, o "" (det)
    eps_role:      str                   # copiato da Gamma.eps_role
    eps_feeds:     tuple[str, ...]       # copiato da Gamma.eps_feeds
    output_kind:   str                   # copiato da Gamma.output_kind
    payload:       Any                   # output VERBATIM (mai normalizzato)
    salute:        str                   # ok | bad_json | error | assente
    usato:         bool                  # scarto BINARIO
    motivo_scarto: str = ""

    def as_dict(self) -> dict:
        d = {"gamma": self.gamma, "lato": self.lato, "eps_role": self.eps_role,
             "salute": self.salute, "usato": self.usato}
        if self.sotto_unita:
            d["sotto_unita"] = self.sotto_unita
        if self.eps_feeds:
            d["eps_feeds"] = list(self.eps_feeds)
        if self.output_kind:
            d["output_kind"] = self.output_kind
        if self.motivo_scarto:
            d["motivo_scarto"] = self.motivo_scarto
        d["payload"] = self.payload
        return d


@dataclass
class QuadroEpsilon:
    eps_resh:       Optional[float]                  # VERBATIM dal det
    componenti:     dict[str, float]                 # VERBATIM (comp_clamped)
    contributi_det: list[ContributoEpsilon]
    contributi_ind: list[ContributoEpsilon]          # arsenale + assi (usati)
    giudizi_parita: list[ContributoEpsilon]          # trilemma/inclosura/Δε/malafede_o
    scartati:       list[ContributoEpsilon]          # error/bad_json — fuori ma CONTATI
    n_scartati:     int
    copertura:      dict[str, list[str]]             # componente ε → [γ alimentanti]
    meta:           dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "eps_resh": self.eps_resh,
            "componenti": self.componenti,
            "contributi_det": [c.as_dict() for c in self.contributi_det],
            "contributi_ind": [c.as_dict() for c in self.contributi_ind],
            "giudizi_parita": [c.as_dict() for c in self.giudizi_parita],
            "scartati": [c.as_dict() for c in self.scartati],
            "n_scartati": self.n_scartati,
            "copertura": self.copertura,
            "meta": self.meta,
        }


# ─── salute di un output induttivo ───────────────────────────────────────────

def _salute_ind(out: Any) -> tuple[str, str]:
    """(salute, motivo) di un output d'asse/sezione induttiva.

    `non_applicabile` = il giudizio non era valutabile (es. O senza latente):
    è «assente», NON un errore — non entra nel conteggio scartati.
    """
    if not isinstance(out, dict) or not out:
        return "assente", "non eseguito"
    if "errore" in out:
        if out.get("bad_json") or "JSON" in str(out.get("errore", "")):
            return "bad_json", str(out["errore"])
        return "error", str(out["errore"])
    if "non_applicabile" in out:
        return "assente", str(out["non_applicabile"])
    return "ok", ""


# ─── aggregazione ────────────────────────────────────────────────────────────

def aggrega(rapporto_det: Optional[dict], rapporto_ind: Optional[dict]) -> QuadroEpsilon:
    """Costruisce il QuadroEpsilon da rapporto det e ind (entrambi opzionali).

    `rapporto_det`: dict con `eps_resh`, `componenti_epsilon` (clampati,
    SOLO i misurati) e opz. `componenti_esclusi`. `rapporto_ind`:
    `RapportoInduttivo.as_dict()` o None (induttivo non eseguito).
    """
    det = rapporto_det or {}
    ind = rapporto_ind or {}

    eps_resh   = det.get("eps_resh")
    componenti = dict(det.get("componenti_epsilon") or {})
    esclusi    = set(det.get("componenti_esclusi") or [])

    contributi_det: list[ContributoEpsilon] = []
    copertura: dict[str, list[str]] = {c: [] for c in COMPONENTI}

    # ── lato det: γ componente → provenienza dei componenti (da eps_feeds) ──
    for g in sorted(LAMBDA_RESH, key=lambda x: x.name):
        if g.eps_role != "componente":
            continue
        for feed in g.eps_feeds:
            copertura.setdefault(feed, []).append(g.name)
        misurati = {f: componenti[f] for f in g.eps_feeds if f in componenti}
        mancanti = [f for f in g.eps_feeds if f not in componenti]
        if not det:
            salute, usato, motivo = "assente", False, "deterministico non eseguito"
        elif misurati:
            salute, usato = "ok", True
            motivo = (f"feed non misurati (esclusi da ε a monte): {mancanti}"
                      if mancanti else "")
        else:
            salute, usato = "assente", False
            motivo = "nessun feed misurato (esclusi da ε a monte, reweight sui presenti)"
        contributi_det.append(ContributoEpsilon(
            gamma=g.name, lato="det", sotto_unita="",
            eps_role=g.eps_role, eps_feeds=g.eps_feeds, output_kind=g.output_kind,
            payload=misurati or None, salute=salute, usato=usato, motivo_scarto=motivo))

    # ── lato ind: sotto-unità del rapporto induttivo ────────────────────────
    # Il γ portatore è γ_analizza_induttivo (giudizio_parita): gli assi non
    # hanno γ propri — la sotto_unita li distingue. Eccezioni con γ proprio
    # (es. γ_diagnosi_malafede → "malafede_o") mantengono il loro nome.
    g_ind = next((g for g in LAMBDA_RESH if g.name == "γ_analizza_induttivo"), None)
    _gamma_per_unita = {"malafede_o": "γ_diagnosi_malafede"}

    contributi_ind: list[ContributoEpsilon] = []
    giudizi_parita: list[ContributoEpsilon] = []
    scartati:       list[ContributoEpsilon] = []

    def _aggiungi_ind(unita: str, out: Any) -> None:
        salute, motivo = _salute_ind(out)
        if rapporto_ind is None and salute == "assente":
            motivo = "induttivo non eseguito"
        nome_g = _gamma_per_unita.get(unita) or (g_ind.name if g_ind else "γ_analizza_induttivo")
        g = next((x for x in LAMBDA_RESH if x.name == nome_g), g_ind)
        c = ContributoEpsilon(
            gamma=nome_g, lato="ind", sotto_unita=unita,
            eps_role=(g.eps_role if g else "giudizio_parita"),
            eps_feeds=(g.eps_feeds if g else ()),
            output_kind=(g.output_kind if g else ""),
            payload=(out if salute == "ok" else None),
            salute=salute, usato=(salute == "ok"), motivo_scarto=motivo)
        if salute in ("error", "bad_json"):
            scartati.append(c)
        elif unita in _SOTTO_UNITA_GIUDIZIO:
            giudizi_parita.append(c)
        else:
            contributi_ind.append(c)

    _aggiungi_ind("arsenale", ind.get("arsenale"))
    for aid, out in sorted((ind.get("assi") or {}).items()):
        _aggiungi_ind(aid, out)
    _aggiungi_ind("trilemma", (ind.get("trilemma") or {}).get("llm"))
    _aggiungi_ind("inclosura", (ind.get("inclosura") or {}).get("llm"))
    if ind.get("sintesi"):
        _aggiungi_ind("sintesi", {"sintesi": ind["sintesi"]})
    if "malafede_o" in ind:
        _aggiungi_ind("malafede_o", ind.get("malafede_o"))

    # ── anomalie di copertura (verifica runtime, mai eccezione) ─────────────
    anomalie = [c for c in COMPONENTI if not copertura.get(c)]
    meta = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "det_presente": bool(det),
        "ind_presente": rapporto_ind is not None,
        "componenti_esclusi": sorted(esclusi),
        "n_contributi": len(contributi_det) + len(contributi_ind) + len(giudizi_parita),
    }
    if anomalie:
        meta["anomalie_copertura"] = anomalie

    return QuadroEpsilon(
        eps_resh=eps_resh, componenti=componenti,
        contributi_det=contributi_det, contributi_ind=contributi_ind,
        giudizi_parita=giudizi_parita, scartati=scartati,
        n_scartati=len(scartati), copertura=copertura, meta=meta)
