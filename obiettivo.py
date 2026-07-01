"""resh/obiettivo.py — Estrazione dell'Obiettivo O (lato INDUTTIVO, LLM).

O-extraction è il **primo nodo del lato induttivo** (HANDOFF §5.1): tutti i prompt
di ऋ sono O-relativi (`testo φ + O`), ma O non è producibile dal deterministico —
il quale ha solo il placeholder `Teleologia.obiettivo_dichiarato = prima frase`
(`coerenza=0.5`). Qui O è estratto da un LLM.

**Parità di ruolo** (vincolo architetturale): O è un GIUDIZIO induttivo; non entra
in ε (i 9 componenti di `epsilon.py` restano deterministici). O alimenta gli assi
e il Trilemma a valle, non i parametri riproducibili.

DEFAULT DISATTIVATO. Attivabile via:
  - `analizza(testo, obiettivo_llm=True)`
  - env `P3_RESH_O_LLM=1`
Graceful degradation: se l'LLM non è raggiungibile → `None` (il chiamante ricade
sul placeholder deterministico). Layer LLM §5.26: client da
`config.get_llm_client()` via `llm_json.call_llm_json`.

Dataset Σ_w: ogni estrazione è loggata append-only (JSONL) come materiale per un
futuro fine-tuning di un LLM piccolo (HANDOFF §5). Disattivabile con
`P3_RESH_O_DATASET_DISABLE=1`.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Optional

from .schemas import Teleologia

# Λ spina dorsale: le primitive NLI si pescano dal registry (regola Σ_w 2026-06-10).
from .lambda_space import G, resolve
_entail            = resolve(G.ENTAIL)
_classify_zero_shot = resolve(G.CLASSIFY_ZERO_SHOT)


SYS_OBIETTIVO = """Sei il modulo di estrazione dell'Obiettivo O di ऋ.

Ricevi una rappresentazione φ (un testo): la traccia di un atto compiuto da un
agente. Il tuo unico compito è identificare l'OBIETTIVO O dell'agente che ha
prodotto φ: ciò che, producendo φ, cerca di stabilire, rappresentare o ottenere.
O NON è un riassunto e NON è la prima frase: è il fine dell'atto di cui φ è traccia.

Distingui due livelli:
- obiettivo_dichiarato: il fine che l'agente enuncia apertamente in φ.
- obiettivo_latente: il fine sottostante non dichiarato che l'agente persegue di
  fatto (o null se non c'è scarto tra dichiarato e latente).

Valuta inoltre la coerenza teleologica (0.0–1.0): quanto φ converge su O.
1.0 = ogni parte serve O; valori bassi = φ deriva, si disperde, o reca segni di
fini incompatibili.

NON giudichi la verità né la qualità di φ. NON proponi alternative. Identifichi O,
non lo valuti — la valutazione spetta agli assi a valle (parità di ruolo)."""


def _payload_user(testo: str) -> str:
    return (
        "Testo φ:\n"
        f"\"\"\"\n{testo.strip()}\n\"\"\"\n\n"
        "Rispondi ESCLUSIVAMENTE con JSON nella forma:\n"
        '{"obiettivo_dichiarato": "<una frase>", '
        '"obiettivo_latente": "<una frase o null>", '
        '"coerenza": <float 0..1>}'
    )


def _o_via_llm_json(testo: str) -> dict:
    try:
        from llm_json import call_llm_json          # P3 canonico (tree completo)
    except ImportError:
        from .config import call_llm_json           # copia standalone resh
    # Budget pieno (8192): su gemma-4-31b il ragionamento per l'estrazione O
    # supera spesso i 3072 token e a 1500 veniva tagliato prima del JSON
    # (finish=length, content vuoto → ValueError). Vedi documento._estrai_O.
    return call_llm_json(SYS_OBIETTIVO, _payload_user(testo),
                         max_tokens=8192, temperature=0.2, tag="ऋ-obiettivo")


# ─── dataset Σ_w (append-only, per fine-tuning futuro) ────────────────────────

from .cache import CACHE_DIR as _CACHE_DIR

_DATASET_PATH = _CACHE_DIR / "obiettivo_dataset.jsonl"
_logger = logging.getLogger(__name__)
_dataset_write_failed_warned = False


def _log_dataset(testo: str, out: dict) -> None:
    if os.getenv("P3_RESH_O_DATASET_DISABLE") == "1":
        return
    try:
        _DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts":            datetime.datetime.now().isoformat(timespec="seconds"),
            "testo_sha256":  hashlib.sha256(testo.encode("utf-8")).hexdigest()[:16],
            "testo":         testo[:4000],
            "obiettivo_dichiarato": out.get("obiettivo_dichiarato", ""),
            "obiettivo_latente":    out.get("obiettivo_latente"),
            "coerenza":             out.get("coerenza"),
            # campo riservato al feedback Σ_w (correzione), riempito a mano in seguito
            "feedback_sigma_w":     None,
        }
        with _DATASET_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        global _dataset_write_failed_warned
        if not _dataset_write_failed_warned:
            _dataset_write_failed_warned = True
            _logger.warning(
                "obiettivo_dataset.jsonl (%s) non scrivibile: %s — dataset di questo "
                "processo resterà incompleto da qui in avanti (avviso una tantum)",
                _DATASET_PATH, exc)


# ─── API ──────────────────────────────────────────────────────────────────────

def estrai_obiettivo(testo: str) -> Optional[Teleologia]:
    """Estrae O da φ via LLM → `Teleologia`. `None` se l'LLM non è raggiungibile
    (graceful: il chiamante ricade sul placeholder deterministico)."""
    if not (testo or "").strip():
        return None
    try:
        out = _o_via_llm_json(testo)
    except Exception as exc:
        print(f"[resh.obiettivo] estrazione O fallita (graceful): {exc}")
        return None

    dichiarato = str(out.get("obiettivo_dichiarato", "")).strip()
    if not dichiarato:
        return None
    latente_raw = out.get("obiettivo_latente")
    latente = str(latente_raw).strip() if latente_raw not in (None, "", "null") else None
    try:
        coerenza = float(out.get("coerenza", 0.5))
    except (TypeError, ValueError):
        coerenza = 0.5
    coerenza = max(0.0, min(1.0, coerenza))

    _log_dataset(testo, out)
    return Teleologia(
        obiettivo_dichiarato = dichiarato[:200],
        obiettivo_latente    = (latente[:200] if latente else None),
        coerenza             = round(coerenza, 4),
        nota                 = "estrazione induttiva (LLM) — O-relativo",
    )


# ─── integrità di O: O come rappresentazione FALLIBILE del volere ─────────────
#
# O non è un metro fisso da assumere: può essere contraddittorio (mauvaise foi),
# mal-indotto (disperso) o con dichiarato ≠ latente. `eps_resh` deve pesare
# l'incoerenza INTRINSECA di O — distinta dall'aderenza φ→O (`teleologia.coerenza`).
# Parità di ruolo: l'induttivo PRODUCE O (estrai_obiettivo); qui il deterministico
# MISURA la relazione dichiarato↔latente. SEGNALE STRUTTURALE, non verdetto: se la
# scissione sia produttiva (ऋ⁵) o dissimulata resta giudizio induttivo.
#
# Vincolo HW: il modello NLI è a 2 classi {entailment, not_entailment} — niente
# «contradiction» nativa. Ibrido (opzione A): *integro* = entailment (strutturale);
# lo split contraddittorio/disperso è zero-shot (soft, grado «sospetto» come W4).

# Soglia di entailment per dichiarare O integro. Bassa per CALIBRAZIONE del modello
# NLI (lo stesso `deberta-v3-zeroshot` dà entailment ~0.17 su parafrasi chiare e
# ~0.001 su frasi slegate): allineata a `sequitur.SOGLIA_ENTAIL=0.12`. Scelta, non
# taratura (Σ_w corpus).
SOGLIA_INTEGRO_O   = 0.12    # entailment (una direzione) per dichiarare O integro
PESO_CONTRADDIZIONE = 1.0    # mauvaise foi: penalità piena
PESO_DISPERSIONE    = 0.4    # cattiva induzione: penalità lieve (< contraddizione)  [decisione 2]
_LABELS_REL_O = ["coerenti", "contraddittori", "scollegati"]


def valuta_integrita_obiettivo(teleologia: Teleologia, *, fonte: str):
    """Incoerenza intrinseca di O via relazione NLI dichiarato↔latente.

    Ritorna `(integrita: float|None, dettaglio: dict)`:
      - `fonte != "llm"` (O placeholder / estrazione fallita) → `(None, …)` →
        ESCLUSO da eps_resh (decisione 3: un fallimento non si maschera da integrità).
      - latente assente o ≡ dichiarato → `(1.0, integro)` (nessuna scissione).
      - latente distinto → ibrido NLI: entailment (una direzione) ≥ soglia → integro;
        altrimenti split zero-shot contraddittorio (peso alto) / disperso (peso basso).
    """
    if fonte != "llm":
        return None, {"motivo": "O non induttivo / non valutato"}
    dich = (teleologia.obiettivo_dichiarato or "").strip()
    lat  = (teleologia.obiettivo_latente or "").strip()
    if not dich:
        return None, {"motivo": "dichiarato assente"}
    if not lat or lat == dich:
        return 1.0, {"tipo": "integro", "motivo": "latente cercato e assente: nessuna scissione"}

    fwd = float(_entail(dich, lat))
    bwd = float(_entail(lat, dich))
    if fwd <= 0.0 and bwd <= 0.0:
        return None, {"motivo": "NLI non disponibile (fallback)"}     # non valutabile → escluso
    if max(fwd, bwd) >= SOGLIA_INTEGRO_O:
        return 1.0, {"tipo": "integro", "fwd": round(fwd, 4), "bwd": round(bwd, 4),
                     "motivo": "entailment: latente coerente col dichiarato"}

    # né entailment né (con 2 classi) contraddizione distinguibile strutturalmente →
    # split del TIPO via zero-shot (soft, grado «sospetto» — coerente con W4).
    premise = f"Obiettivo dichiarato: {dich}. Obiettivo latente: {lat}."
    res = _classify_zero_shot(premise, _LABELS_REL_O,
                              hypothesis_template="Dichiarato e latente sono {}.")
    labels = res.get("labels", []) if isinstance(res, dict) else []
    scores = res.get("scores", []) if isinstance(res, dict) else []
    top = labels[0] if labels else "scollegati"
    p   = float(scores[0]) if scores else 0.0
    base = {"fwd": round(fwd, 4), "bwd": round(bwd, 4), "label_zero_shot": top, "p": round(p, 4),
            "dichiarato": dich[:200], "latente": lat[:200],
            "qualifica": "produttiva (ऋ⁵) o dissimulata = giudizio induttivo"}
    # Post-fallimento dell'entailment, l'integrità strutturale è già esclusa: lo
    # zero-shot serve SOLO a isolare la contraddizione (mauvaise foi). «coerenti» qui
    # è rumore inaffidabile dello zero-shot (W4) — non riabilita l'integrità: resta
    # dispersione (il latente non si aggancia strutturalmente al dichiarato).
    if top == "contraddittori":
        return round(max(0.0, 1.0 - PESO_CONTRADDIZIONE * p), 4), {"tipo": "contraddittorio", **base}
    return round(max(0.0, 1.0 - PESO_DISPERSIONE * p), 4), {"tipo": "disperso", **base}


def should_run() -> bool:
    """Per CLI/orchestratore: env globale (default False)."""
    return os.getenv("P3_RESH_O_LLM") == "1"


# ─── diagnosi malafede del nodo O (giudizio a parità, Σ_w 2026-06-11) ─────────
# La malafede RINASCE qui come diagnosi induttiva sullo SCARTO O dichiarato↔
# latente — NON è un asse dell'arsenale (prompts_resh.md resta intatto; prompt
# provvisorio in-modulo, modello astratti.py) e NON modula MAI ε: il modulatore
# deterministico, no-op dal 2026-05-20, è stato RIMOSSO con ADR-005 (2026-06-12);
# vietato reintrodurne senza ADR di rifondazione.
# È un SEGNALE in più: «fini egoistici ≠ cattivo prodotto».

SYS_MALAFEDE = """Sono ऋ. Ricevo un testo φ e l'Obiettivo O dell'agente che lo ha
prodotto (dichiarato + latente). Il mio compito è diagnosticare se nello SCARTO
tra obiettivo dichiarato e obiettivo latente si manifestano segnali di intento
manipolatorio, persuasivo occulto o puramente egoistico: appello emotivo non
argomentato, urgenza fabbricata, asimmetria informativa deliberata, chiusura
preventiva delle alternative, beneficio dell'agente occultato come beneficio
del lettore.

Vincoli:
- Diagnostico un SEGNALE, non emetto un verdetto: un fine egoistico o persuasivo
  NON rende cattivo il prodotto — lo annoto e basta.
- Ogni rilievo cita il punto di φ che lo fonda. Niente rilievi senza ancoraggio.
- Se lo scarto dichiarato↔latente non mostra segnali, dico «nessuno» senza
  inventare."""


def _payload_malafede(testo: str, dich: str, lat: str,
                      integrita: Optional[float]) -> str:
    extra = (f"\nIntegrità strutturale dichiarato↔latente (deterministico): {integrita}"
             if integrita is not None else "")
    return (
        f"Testo φ:\n\"\"\"\n{testo.strip()}\n\"\"\"\n\n"
        f"Obiettivo dichiarato: {dich}\nObiettivo latente: {lat}{extra}\n\n"
        "Rispondi ESCLUSIVAMENTE con JSON nella forma:\n"
        '{"rilievi": ["<rilievo ancorato a φ>", ...], '
        '"intento": "manipolatorio|persuasivo|egoistico|nessuno", '
        '"grado": "assente|sospetto|marcato", "nota": "<una frase o null>"}'
    )


def diagnosi_malafede(testo: str, obiettivo: Optional[Teleologia], *,
                      profile: Optional[str] = None,
                      integrita: Optional[float] = None) -> dict:
    """Diagnosi induttiva di malafede sullo scarto O dichiarato↔latente.

    Ritorna il JSON dell'LLM `{rilievi, intento, grado, nota}`, oppure
    `{"non_applicabile": ...}` se O manca o non ha latente distinto (senza
    scarto non c'è materia), oppure `{"errore": ...}` (isolato, graceful).
    Giudizio a PARITÀ di ruolo: il chiamante non lo usa mai su ε.
    """
    if obiettivo is None or not (obiettivo.obiettivo_dichiarato or "").strip():
        return {"non_applicabile": "O non disponibile (estrazione LLM assente/fallita)"}
    dich = obiettivo.obiettivo_dichiarato.strip()
    lat = (obiettivo.obiettivo_latente or "").strip()
    if not lat or lat == dich:
        return {"non_applicabile": "nessuno scarto dichiarato↔latente: niente da diagnosticare"}
    try:
        from .config import call_llm_json
        out = call_llm_json(SYS_MALAFEDE, _payload_malafede(testo, dich, lat, integrita),
                            max_tokens=2048, temperature=0.2, profile=profile,
                            tag="ऋ-malafede-o")
        return out
    except Exception as exc:
        err: dict = {"errore": f"{type(exc).__name__}: {exc}"}
        if isinstance(exc, (ValueError,)) or "JSON" in str(exc):
            err["bad_json"] = True
        return err
