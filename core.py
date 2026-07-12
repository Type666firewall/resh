"""resh/core.py — Orchestratore pipeline ऋ.

Coordina i moduli deterministici in 3 fasi:
  1. Substrato (Stanza UD + embedder BGE-M3) — sequenziale, cached
  2. Branch paralleli (asyncio.gather) — moduli AI-free / NLI puri
  3. Aggregation (ε_ऋ + RapportoResh + yaml μ-traccia)

API:
  - `analizza_async(testo, *, verbose=False) -> RapportoResh`
  - `analizza(testo, **kw) -> RapportoResh`  # wrapper sync via asyncio.run
  - `AgenteResh(bus, name, sigma)` — adapter Bus MCP (compat O-6)

ADR-005 (eseguita 2026-06-12): rimossi modulatore malafede (no-op), sintesi
narrativa LLM (la voce spetta al Gateway Σ-7) e fuzzy_logic (fascia a soglie).
§5.27: ortogonale (Salience routing è caller-side).
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import math
import os
from typing import Optional

import numpy as np

# stderr, mai stdout: mcp_server.py parla JSON-RPC su stdio, un print() qui lo romperebbe.
logger = logging.getLogger(__name__)

# TIPI / COSTANTI / DATI: import normali (non sono metodi — vedi regola Λ sotto).
from .gamma.annotazione import AnnotatedDoc
from .epsilon          import COMPONENTI
from .gamma import encoder as _encoder_mod         # solo backend_info() (diagnostica, non γ)
from .gamma import sequitur as _sequitur_mod       # solo backend_info() (diagnostica, non γ)
from .lambda_space     import LAMBDA_RESH, Gamma, G, resolve
from .schemas import (
    Argomento, AutoritaCriteri, Patologia, PremessaAnalisi,
    RapportoResh, Teleologia, TipoPatologia, VerificaLogica,
)

# ─── Λ spina dorsale (Σ_w 2026-06-10) ────────────────────────────────────────
# I METODI si pescano dal registry: un γ non registrato in Λ è irraggiungibile.
# Binding nel preludio = fail-fast a import-time (callable_path rotto → KeyError
# subito), stesso grafo di import di prima. REGOLA self-module: mai resolve di
# γ il cui callable vive in QUESTO modulo (γ_analizza_async/γ_genesi/
# γ_densita_fuzzy) — importlib restituirebbe il modulo a metà import. I γ
# opzionali/LLM (estrai_obiettivo, analizza_induttivo) si risolvono LAZY nei
# rispettivi try.
annota                      = resolve(G.ANNOTA)
encode                      = resolve(G.ENCODE)
segmenta_proposizioni       = resolve(G.SEGMENTA_PROPOSIZIONI)
profilo_linguistico         = resolve(G.PROFILO_LINGUISTICO)
qualita_sintattica          = resolve(G.QUALITA_SINTATTICA)
rileva_fallacie             = resolve(G.RILEVA_FALLACIE)
estrai_argomenti            = resolve(G.ESTRAI_ARGOMENTI)
analizza_coerenza           = resolve(G.ANALIZZA_COERENZA)
analizza_bias_autorita      = resolve(G.BIAS_AUTORITA)
profilo_stilistico          = resolve(G.PROFILO_STILISTICO)
analizza_premesse           = resolve(G.ANALIZZA_PREMESSE)
verifica_sequitur           = resolve(G.VERIFICA_SEQUITUR)
rileva_circolarita          = resolve(G.RILEVA_CIRCOLARITA)
calcola_epsilon             = resolve(G.CALCOLA_EPSILON)
# ADR-005: γ_modulatore_malafede rimosso da Λ (era identità); γ_densita_fuzzy
# ora punta a `fascia_densita` qui sotto (self-module: chiamata diretta).


# Peso del non-sequitur nella penalità di `validita_argomenti` (van Dalen ch01).
# 1.0 = un non-sequitur (severità=1) pesa come una fallacia. Override opzionale
# via config `[resh.sequitur].peso_epsilon`.
def _peso_sequitur() -> float:
    try:
        from .config import CONFIG
        seq = getattr(getattr(CONFIG, "resh", None), "sequitur", None)
        v = getattr(seq, "peso_epsilon", None)
        if isinstance(v, (int, float)):
            return float(v)
    except Exception:
        pass
    return 1.0


PESO_SEQUITUR = _peso_sequitur()


# ─── helpers numerici ────────────────────────────────────────────────────────

def _to_native(obj):
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_native(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def _backend_snapshot(backend_annotazione: str) -> dict:
    """Stato di TUTTI i backend che toccano ε + flag di degradazione.

    `eps_degradato=True` ⇒ almeno un backend gira in fallback/disabled: la ε
    di questo run NON è confrontabile con run a stack pieno. Il flag viaggia
    nel rapporto (e quindi nel record Ψ) — la degradazione silenziosa che
    cambia ε senza dichiararlo è il pattern che questo snapshot elimina.
    `ambiente` certifica interprete e versioni: stessa ε richiede stesso stack.
    """
    import sys
    snap = {
        "annotazione": backend_annotazione,
        "encoder":     _encoder_mod.backend_info(),
        "nli":         _nli_backend(),
        "sequitur":    _sequitur_mod.backend_info().get("stato", "?"),
        "fuzzy":       "soglie fisse (ADR-005: ex Mamdani, stesso output)",
    }
    # fuzzy escluso: fascia descrittiva ⇒ non tocca ε (chiave conservata per
    # compatibilità schema DB/report; il modulo fuzzy_logic è in trash, ADR-005)
    snap["eps_degradato"] = any(
        ("fallback" in str(v).lower()) or ("disabled" in str(v).lower())
        for k, v in snap.items() if k != "fuzzy"
    )
    versioni = {}
    for pkg in ("torch", "transformers", "sentence-transformers", "stanza"):
        try:
            from importlib.metadata import version
            versioni[pkg] = version(pkg)
        except Exception:
            versioni[pkg] = None
    snap["ambiente"] = {"python": sys.executable, "versioni": versioni}
    return snap


def _nli_backend() -> str:
    from .gamma import _nli
    return _nli.backend_info()


def fascia_densita(densita: float) -> str:
    """Fascia linguistica della densità di premesse implicite/sospette.

    ADR-005 (2026-06-12): sostituisce `fuzzy_logic.densita_logica_fuzzy` —
    simpful non era installato e il fallback lineare produceva ESATTAMENTE
    queste soglie; il valore `mf` era scartato (modulatore frozen dal
    2026-05-20). Stesso output, stessa patologia DENSITA_CRITICA.
    Registrata in Λ come γ_densita_fuzzy (chiamata diretta qui: self-module).
    """
    if   densita < 0.01: return "bassa"
    elif densita < 0.03: return "media"
    elif densita < 0.06: return "alta"
    else:                return "critica"


def _densita_logica(testo: str, premesse: PremessaAnalisi) -> tuple[float, str]:
    """Densità premesse implicite/sospette → (densita, fascia).

    Metriche DESCRITTIVE: non modulano ε_ऋ. Il modulatore malafede è stato
    rimosso (ADR-005, era no-op dal freeze Σ_w 2026-05-20); il campo
    `malafede_mod` resta negli schemi a 1.0 fisso («frozen, vedi
    γ_diagnosi_malafede»).
    """
    tokens = max(1, len(testo.split()))
    n_impl = len(premesse.implicite) + len(premesse.sospette)
    densita = round(n_impl / tokens, 4)
    return densita, fascia_densita(densita)


# ─── teleologia (deterministica — euristica) ─────────────────────────────────

def _teleologia_deterministica(doc: AnnotatedDoc) -> Teleologia:
    """Fallback deterministico: obiettivo dichiarato = prima frase non-vuota.
    obiettivo_latente=None, coerenza=0.5. Senza LLM è il massimo onesto."""
    obiettivo = ""
    for s in doc.sentences:
        t = s.text.strip()
        if t and len(t) > 8:
            obiettivo = t
            break
    return Teleologia(
        obiettivo_dichiarato = obiettivo[:200],
        obiettivo_latente    = None,
        coerenza             = 0.5,
        nota                 = "stima deterministica — coerenza neutra senza LLM",
    )


# ─── struttura argomentativa score ───────────────────────────────────────────

def _struttura_score(argomenti: list[Argomento], n_frasi: int) -> float:
    """0-1: rapporto frasi-con-premesse / frasi totali, capped."""
    if n_frasi == 0:
        return 0.0
    coverage = min(1.0, len(argomenti) / n_frasi)
    # bonus se argomenti deduttivi presenti
    bonus = 0.1 if any(a.tipo == "deduttivo" for a in argomenti) else 0.0
    return round(min(1.0, coverage + bonus), 4)


# ─── pipeline async ──────────────────────────────────────────────────────────

async def _run_in_thread(fn, *args, **kwargs):
    """Wrapper anyio/asyncio per esecuzione sincrona in thread separato."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


async def analizza_async(
    testo:         str,
    *,
    obiettivo_llm: bool = False,
    induttivo_llm: bool = False,
    verbose:       bool = False,
    lang:          Optional[str] = None,
) -> RapportoResh:
    """Pipeline asincrona — ritorna RapportoResh completo.

    `lang`: se specificato, imposta la lingua per questa analisi (ContextVar
    `config.LANG`, isolata per task asyncio — non tocca analisi concorrenti).
    """
    if lang is not None:
        from . import config as _config
        _config.LANG.set(lang)

    if verbose: logger.info("[1/4] Annotazione UD + encoding + chunking proposizionale...")
    doc = await _run_in_thread(annota, testo)
    embs = await _run_in_thread(encode, [s.text for s in doc.sentences])

    # Chunking proposizionale: le unità argomentative sono proposizioni (clausole),
    # non frasi intere → entailment premessa→tesi più isolato (van Dalen ch06).
    proposizioni = await _run_in_thread(segmenta_proposizioni, doc)
    prop_testi   = [p.testo for p in proposizioni]
    prop_embs    = await _run_in_thread(encode, prop_testi)

    if verbose: logger.info("[2/4] Branch paralleli (profilo, fallacie, argomenti, coerenza, bias, stilometria)...")
    (
        profilo,
        fallacie_pats,
        argomenti,
        coerenza_dict,
        bias_tuple,
        stilom,
    ) = await asyncio.gather(
        _run_in_thread(profilo_linguistico, doc),
        _run_in_thread(rileva_fallacie, doc),
        _run_in_thread(estrai_argomenti, prop_testi, prop_embs),
        _run_in_thread(analizza_coerenza, [s.text for s in doc.sentences], embs),
        _run_in_thread(analizza_bias_autorita, testo, doc),
        _run_in_thread(profilo_stilistico, doc),
    )
    autorita, bias_pats = bias_tuple

    if verbose: logger.info("[3/4] Premesse (entailment NLI) + sequitur (validità)...")
    premesse = await _run_in_thread(analizza_premesse, testo, doc, embs)
    # Validità come entailment (van Dalen ch01/ch06): non-sequitur + candidati C₃.
    seq_pats = await _run_in_thread(verifica_sequitur, argomenti)
    circ_pats = await _run_in_thread(rileva_circolarita, argomenti)   # circolarità STRUTTURALE
    ns_args  = {p.dettaglio.get("argomento") for p in seq_pats}

    # Obiettivo O: estrazione INDUTTIVA (LLM) se abilitata, altrimenti placeholder
    # deterministico. O è O-relativo per gli assi a valle, NON entra in ε (parità
    # di ruolo). Graceful: se l'LLM fallisce, ricade sul deterministico.
    teleologia = _teleologia_deterministica(doc)
    obiettivo_fonte = "deterministica"
    if obiettivo_llm or os.getenv("P3_RESH_O_LLM") == "1":
        if verbose: logger.info("[3/4] Estrazione Obiettivo O (LLM, opzionale)...")
        _o_ok = False
        try:
            _estrai_o = resolve(G.ESTRAI_OBIETTIVO)
        except Exception as exc:
            _estrai_o = None
            logger.warning("resolve ESTRAI_OBIETTIVO fallito (graceful): %s", exc)
        if _estrai_o is not None:
            for _o_attempt in range(2):
                try:
                    o_ind = await _run_in_thread(_estrai_o, testo)
                    if o_ind is not None:
                        teleologia = o_ind
                        obiettivo_fonte = "llm"
                    _o_ok = True
                    break
                except Exception as exc:
                    logger.warning("O-extraction tentativo %d fallito: %s", _o_attempt + 1, exc)
        if not _o_ok:
            logger.warning("O-extraction LLM fallita (graceful): uso deterministico")

    # Incoerenza INTRINSECA di O (O fallibile rappresentazione del volere): misura
    # deterministica della relazione dichiarato↔latente. `None` con O deterministico
    # → escluso da eps_resh. Segnale strutturale, non verdetto (qualifica = induttiva).
    _valuta_io = resolve(G.VALUTA_INTEGRITA_OBIETTIVO)   # lazy: trascina obiettivo (LLM-side)
    integrita_io, integrita_dett = await _run_in_thread(_valuta_io, teleologia, fonte=obiettivo_fonte)

    # verifiche logiche: 1 verifica per argomento (fallacia O non-sequitur ⇒ non valido)
    verifiche: list[VerificaLogica] = []
    fallacy_spans = [(p.span_char, p.dettaglio.get("fallacia_l2", "?"))
                     for p in fallacie_pats if p.span_char]
    testo_lower = testo.lower()
    for a in argomenti:
        fallacia = None
        chiave = (a.testo or "")[:60].lower()
        posizioni: list[int] = []
        if chiave:
            pos = testo_lower.find(chiave)
            while pos != -1:
                posizioni.append(pos)
                pos = testo_lower.find(chiave, pos + 1)
        for span, name in fallacy_spans:
            # match grossolano: una qualunque occorrenza dell'argomento nella porzione
            if span and name and any(span[0] <= p <= span[1] + 200 for p in posizioni):
                fallacia = name
                break
        is_ns = a.testo[:200] in ns_args
        if fallacia:
            nota = "auto-derived from fallacy module"
        elif is_ns:
            nota = "non sequitur: premesse non derivano la tesi (van Dalen ch01)"
        else:
            nota = ""
        verifiche.append(VerificaLogica(
            argomento = a.testo,
            tipo      = a.tipo,
            valido    = (fallacia is None) and (not is_ns),
            fallacia  = fallacia,
            nota      = nota,
        ))

    # ─── componenti epsilon ──────────────────────────────────────────────
    # Se NLI non classifica nessuna unità come argomento, usa n_proposizioni come
    # denominatore per evitare che validita_args collassi a 0 con poche fallacie.
    n_argomenti_eff = len(argomenti) if argomenti else len(proposizioni)
    n_argomenti     = max(1, n_argomenti_eff)
    n_fallacie      = len(fallacie_pats)
    # DISCERNERE due assi ortogonali (van Dalen): la validità formale (le premesse
    # derivano la tesi, sequitur) NON è l'assenza di fallacie (MAFALDA). Un
    # non-sequitur «pulito» (entimema / C₃) è invalido pur senza fallacia nominata;
    # un argomento valido può essere fallace. Due componenti distinti, non fusi.
    penalita_seq     = PESO_SEQUITUR * sum(p.severita for p in seq_pats)
    sev_max_seq      = max((p.severita for p in seq_pats), default=0.0)
    # Floor: il peggior non-sequitur conta almeno 50% della sua severità anche su
    # testi lunghi dove la densità (penalita/n_argomenti) lo diluirebbe a zero.
    validita_formale = 1.0 - min(1.0, max(sev_max_seq * 0.5,
                                           penalita_seq / max(1, n_argomenti)))
    # Solo le fallacie CONFERMATE (regex alta-precisione + circolarità strutturale)
    # penalizzano ε. Le zero-shot di rilevanza sono SOSPETTE: restano nel report ma
    # NON vetano ε (il deterministico è inaffidabile su quelle → spettano all'induttivo).
    # «Nessuna confermata» ≠ «non rilevabili»: le sospette restano visibili e distinte.
    n_regex_conf     = sum(1 for p in fallacie_pats if p.dettaglio.get("confermata", False))
    n_fallacie_conf  = n_regex_conf + len(circ_pats)
    n_fallacie_sosp  = n_fallacie - n_regex_conf
    # Usa severità, non solo conteggio: una fallacia(sev=0.92) pesa più di una(sev=0.3).
    sev_fallacie     = ([p.severita for p in fallacie_pats if p.dettaglio.get("confermata", False)]
                        + [p.severita for p in circ_pats])
    sev_max_fal      = max(sev_fallacie, default=0.0)
    penalita_fal     = sum(sev_fallacie) / max(1, n_argomenti) if sev_fallacie else 0.0
    assenza_fallacie = 1.0 - min(1.0, max(sev_max_fal * 0.5, penalita_fal))

    # None = componente NON misurabile → escluso da ε (epsilon.calcola_epsilon
    # ripesa sui presenti). Niente valori finti che falserebbero la metrica.
    n_prem_tot = len(premesse.esplicite) + len(premesse.implicite) + len(premesse.sospette)
    componenti = {
        "trasparenza_premesse":     premesse.score if n_prem_tot >= 2 else None,
        "validita_formale":         validita_formale,
        "assenza_fallacie":         assenza_fallacie,
        "struttura_argomentativa":  _struttura_score(argomenti, len(proposizioni)),
        "coesione_semantica":       coerenza_dict.get("coesione_locale"),          # None se non misurata
        "coerenza_tematica":        coerenza_dict.get("coerenza_tematica_score"),  # None se non misurata
        "qualita_sintattica":       qualita_sintattica(profilo),   # None se testo < 30 token
        "bias_linguistico":         _bias_linguistico_score(bias_pats),
        "credibilita_fonte":        autorita.credibilita,
        "integrita_obiettivo":      integrita_io,   # None con O deterministico → escluso
    }
    eps_raw, comp_clamped, pesi = calcola_epsilon(componenti)

    densita, fascia = _densita_logica(testo, premesse)
    # ADR-005: il modulatore malafede (identità no-op dal 2026-05-20) è rimosso;
    # ε_ऋ = ε grezzo della media geometrica. `mf` resta 1.0 fisso per gli schemi.
    eps_resh = eps_raw
    mf = 1.0

    # ─── patologie (sia struct sia legacy list[str]) ─────────────────────
    pat_struct = list(fallacie_pats) + list(bias_pats) + list(seq_pats) + list(circ_pats)
    if fascia in ("alta", "critica"):
        pat_struct.append(Patologia(
            tipo       = TipoPatologia.DENSITA_CRITICA,
            severita   = min(1.0, densita / 0.06),
            confidence = 0.8,
            dettaglio  = {"densita": densita, "fascia": fascia},
            origine_modulo = "core",
        ))
    deriva = coerenza_dict.get("deriva", 0.0)
    if deriva > 0.25:
        pat_struct.append(Patologia(
            tipo       = TipoPatologia.INCOERENZA_TEMATICA,
            severita   = min(1.0, deriva * 2.5),
            confidence = 0.7,
            dettaglio  = {"deriva": deriva},
            origine_modulo = "coerenza",
        ))
    # Incoerenza intrinseca di O: patologia SOLO se misurata (O induttivo) e scissa.
    # Segnale strutturale, non verdetto — il dettaglio rimette la qualifica all'induttivo.
    if integrita_io is not None and integrita_io < 1.0:
        _tipo_io = {"contraddittorio": TipoPatologia.OBIETTIVO_CONTRADDITTORIO,
                    "disperso":        TipoPatologia.OBIETTIVO_DISPERSO}.get(integrita_dett.get("tipo"))
        if _tipo_io is not None:
            pat_struct.append(Patologia(
                tipo       = _tipo_io,
                severita   = round(1.0 - integrita_io, 4),
                confidence = round(float(integrita_dett.get("p", 0.5)), 4),
                dettaglio  = integrita_dett,
                origine_modulo = "obiettivo",
            ))

    patologie_legacy = [p.as_message() for p in pat_struct]
    if eps_resh > 0.95:
        patologie_legacy.append("ε_ऋ molto alto: verificare bilanciamento con Θ (rischio paralisi)")

    # ─── yaml μ-traccia (formato §6) ─────────────────────────────────────
    yaml_out = {
        "id_sistema":          "ऋ-analysis",
        "tipo":                "Distillato",
        "status":              "𝛾",
        "cluster":             "analisi-critica",
        "metodo":              "SA{ऋ}-pipeline-deterministic",
        "data":                datetime.date.today().isoformat(),
        "agente":              "resh",
        "ε_vettore": {
            "Θ_dogma":   None,
            "ऋ_dubbio":  eps_resh,
            "ב_memoria": None,
        },
        "ε_stato":              ">δ" if eps_resh > 0.3 else "<δ",
        "patologie":            patologie_legacy,
        "n_premesse_implicite": len(premesse.implicite),
        "n_premesse_sospette":  len(premesse.sospette),
        "n_proposizioni":       len(proposizioni),
        "n_argomenti":          len(argomenti),
        "n_fallacie":           n_fallacie,
        "n_fallacie_confermate": n_fallacie_conf,
        "n_fallacie_sospette":  n_fallacie_sosp,
        "n_circolarita":        len(circ_pats),
        "n_non_sequitur":       len(seq_pats),
        "n_c3_candidati":       sum(1 for p in seq_pats if p.dettaglio.get("corno") == "C3_candidato"),
        "densita_logica":       densita,
        "fascia_densita":       fascia,
        "malafede_mod":         mf,
        "obiettivo_dichiarato": teleologia.obiettivo_dichiarato,
        "obiettivo_latente":    teleologia.obiettivo_latente,
        "obiettivo_fonte":      obiettivo_fonte,
        "teleologia_coerenza":  teleologia.coerenza,        # aderenza φ→O (ortogonale a integrita)
        "integrita_obiettivo":      integrita_io,           # incoerenza INTRINSECA di O (None se non misurata)
        "integrita_obiettivo_tipo": integrita_dett.get("tipo"),
        "fonte_credibilita":    autorita.credibilita,
        "componenti_epsilon":   comp_clamped,
        "componenti_esclusi":   [k for k, v in componenti.items() if v is None],
        "pesi_epsilon":         pesi,
        "backend": _backend_snapshot(doc.backend),
    }

    rapporto = RapportoResh(
        testo            = testo[:200] + "…" if len(testo) > 200 else testo,
        premesse         = premesse,
        inventario       = argomenti,
        verifiche        = verifiche,
        teleologia       = teleologia,
        autorita         = autorita,
        eps_resh         = eps_resh,
        patologie        = patologie_legacy,
        yaml_output      = _to_native(yaml_out),
        densita_logica   = densita,
        fascia_densita   = fascia,
        malafede_mod     = mf,
        patologie_strutturate = pat_struct,
        profilo_linguistico   = profilo,
        coerenza_semantica    = coerenza_dict,
        profilo_stilistico    = stilom,
        componenti_epsilon    = comp_clamped,
    )

    # ─── lato induttivo opzionale (LLM, ~14 call: default OFF) ──────────
    # Parità di ruolo: il rapporto induttivo AFFIANCA il deterministico
    # (rapporto.induttivo), non tocca eps_resh. La pre-detection Trilemma
    # riceve il rapporto det (segnali strutturali NON_SEQUITUR/petitio).
    if induttivo_llm or os.getenv("P3_RESH_INDUTTIVO") == "1":
        rapporto.induttivo_richiesto = True
        if verbose: logger.info("[4/4] Arsenale induttivo (LLM, opzionale)...")
        try:
            _analizza_ind = resolve(G.ANALIZZA_INDUTTIVO)   # lazy: LLM-side
            rap_ind = await _run_in_thread(
                _analizza_ind, testo,
                obiettivo=(teleologia if obiettivo_fonte == "llm" else None),
                rapporto_resh=rapporto)
            rapporto.induttivo = rap_ind.as_dict()
            # Diagnosi malafede del nodo O (giudizio a parità, +1 call): ha senso
            # solo con O LLM e scarto dichiarato↔latente — altrimenti il γ stesso
            # ritorna non_applicabile (→ «assente» nel quadro, non un errore).
            _diag_mf = resolve(G.DIAGNOSI_MALAFEDE)
            rapporto.induttivo["malafede_o"] = await _run_in_thread(
                _diag_mf, testo,
                rap_ind.obiettivo if obiettivo_fonte != "llm" else teleologia,
                integrita=integrita_io)
        except Exception as exc:
            logger.warning("induttivo fallito (graceful): %s", exc)
            rapporto.induttivo = {"errore": f"{type(exc).__name__}: {exc}"}

    # ─── QuadroEpsilon (deterministico, SEMPRE: zero quota) ─────────────
    # Con induttivo OFF è il quadro det-only (contributi ind «assente») —
    # così l'aggregatore è esercitato anche dalle batterie no-LLM.
    try:
        _aggrega = resolve(G.AGGREGA_QUADRO)        # lazy: aggregatore on-demand
        det_min = {"eps_resh": eps_resh,
                   "componenti_epsilon": comp_clamped,
                   "componenti_esclusi": [k for k, v in componenti.items() if v is None]}
        rapporto.quadro_epsilon = _aggrega(det_min, rapporto.induttivo).as_dict()
    except Exception as exc:
        logger.warning("quadro ε fallito (graceful): %s", exc)

    # Sintesi narrativa LLM RIMOSSA (ADR-005): la voce spetta al Gateway (Σ-7);
    # il report di resh è «zero giudizio del formatter». legacy_llm.py in trash.

    if verbose:
        _stampa_rapporto(rapporto)
    return rapporto


def _bias_linguistico_score(bias_pats: list[Patologia]) -> float:
    """1.0 - max severita patologie BOOSTER (cap a 1.0).

    Solo il boosting (assolutismo / petitio: «ovviamente», «indubbiamente»)
    erode ε: è la mossa che la critica ai dogmi punisce. L'HEDGING
    («forse», «sembra», «potrebbe») è il marcatore della provvisorietà
    fallibilista che l'asse ऋ⁷ *loda* — non è un bias e NON abbassa ε
    (B1, 2026-07). Resta rilevato e visibile come segnale descrittivo; la
    distinzione cautela↔evasività (weasel) spetta all'induttivo
    (diagnosi_malafede), non al conteggio deterministico.
    """
    rilevanti = [p.severita for p in bias_pats
                 if p.tipo is TipoPatologia.BOOSTER_ECCESSIVO]
    if not rilevanti:
        return 1.0
    return round(max(0.0, 1.0 - max(rilevanti)), 4)


# ─── genesi di ε_ऋ (drill-down: «una metrica → poi scavare») ─────────────────

# Mappa componente ε → tipi di Patologia che lo erodono (per attaccare le cause).
_COMPONENTE_PATOLOGIE: dict[str, set] = {
    "validita_formale":     {TipoPatologia.NON_SEQUITUR},
    "assenza_fallacie":     {TipoPatologia.FALLACIA_LOGICA},
    "trasparenza_premesse": {TipoPatologia.PREMESSA_NON_ENTAILED,
                             TipoPatologia.DENSITA_CRITICA},
    "coerenza_tematica":    {TipoPatologia.INCOERENZA_TEMATICA, TipoPatologia.DERIVA_REGISTRO},
    "coesione_semantica":   {TipoPatologia.INCOERENZA_LOCALE},
    "bias_linguistico":     {TipoPatologia.BOOSTER_ECCESSIVO},   # hedging non erode ε (B1)
    "credibilita_fonte":    {TipoPatologia.APPELLO_AUTORITA},
    "integrita_obiettivo":  {TipoPatologia.OBIETTIVO_CONTRADDITTORIO, TipoPatologia.OBIETTIVO_DISPERSO},
}


def genesi(rapporto: RapportoResh) -> list[dict]:
    """Genealogia di `ε_ऋ`: per ogni componente, quanto abbassa ε e perché.

    «Una metrica → poi scavare»: ε resta un solo numero, ma da qui si risale alle
    sue cause. Ordina i 9 componenti per contributo *erosivo* (−wᵢ·log cᵢ, coerente
    con la media geometrica) e allega le `patologie_strutturate` che li causano —
    p.es. `validita_formale` ← le `NON_SEQUITUR`/`C3_candidato`, `assenza_fallacie`
    ← le `FALLACIA_LOGICA`. Lista ordinata dal più erosivo al meno.
    """
    comp = rapporto.componenti_epsilon or {}
    pesi = (rapporto.yaml_output or {}).get("pesi_epsilon", {})
    out: list[dict] = []
    for nome, valore in comp.items():
        c = max(1e-3, min(1.0, float(valore)))
        w = float(pesi.get(nome, 0.0))
        erosione = -w * math.log(c)        # ≥0: quanto questo componente abbassa ε
        tipi = _COMPONENTE_PATOLOGIE.get(nome, set())
        cause = [
            {"tipo": p.tipo.value, "severita": p.severita, "dettaglio": p.dettaglio}
            for p in rapporto.patologie_strutturate if p.tipo in tipi
        ]
        out.append({
            "componente": nome,
            "valore":     round(c, 4),
            "peso":       round(w, 4),
            "erosione":   round(erosione, 4),
            "n_cause":    len(cause),
            "cause":      cause,
        })
    out.sort(key=lambda d: d["erosione"], reverse=True)
    return out


# ─── wrapper sincrono (compat) ───────────────────────────────────────────────

def analizza(testo: str, *, obiettivo_llm: bool = False,
             induttivo_llm: bool = False, verbose: bool = True,
             lang: Optional[str] = None) -> RapportoResh:
    """Pipeline sincrona — wraps `analizza_async` per retrocompatibilità.

    ADR-005: NON registrata in Λ (γ_analizza de-registrato — il metodo
    d'analisi è il solo γ_analizza_async); resta come comodità API."""
    return asyncio.run(analizza_async(testo, obiettivo_llm=obiettivo_llm,
                                      induttivo_llm=induttivo_llm, verbose=verbose,
                                      lang=lang))


# ─── stampa rapporto (output leggibile) ──────────────────────────────────────

def _stampa_rapporto(r: RapportoResh):
    import sys as _sys
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sep = "─" * 52
    print(f"\n{sep}")
    print(f"  ε_ऋ = {r.eps_resh:.4f}   |   Patologie: {len(r.patologie)}")
    print(sep)

    print("\n▸ PREMESSE")
    print(f"  Esplicite ({len(r.premesse.esplicite)}):")
    for p in r.premesse.esplicite[:8]:
        print(f"    + {p[:120]}")
    print(f"  Implicite ({len(r.premesse.implicite)}):")
    for p in r.premesse.implicite[:8]:
        print(f"    ~ {p[:120]}")
    if r.premesse.sospette:
        print(f"  ⚠ Sospette ({len(r.premesse.sospette)}):")
        for p in r.premesse.sospette[:5]:
            print(f"    ! {p[:120]}")

    print(f"\n▸ PROFILO LINGUISTICO  (backend={r.profilo_linguistico.get('backend','?')})")
    pl = r.profilo_linguistico
    print(f"  n_token={pl.get('n_token',0)}  n_frasi={pl.get('n_frasi',0)}  "
          f"MTLD={pl.get('mtld',0)}  Gulpease={pl.get('gulpease',0)}")
    print(f"  dens_lex={pl.get('densita_lessicale',0)}  "
          f"depth={pl.get('profondita_media_albero',0)}  "
          f"sub_ratio={pl.get('subordination_ratio',0)}")

    print(f"\n▸ ARGOMENTI ({len(r.inventario)})")
    for a in r.inventario[:6]:
        print(f"  [{a.tipo}] {a.testo[:100]}")

    print(f"\n▸ COERENZA")
    cs = r.coerenza_semantica
    print(f"  locale={cs.get('coesione_locale',0)}  globale={cs.get('coesione_globale',0)}  "
          f"deriva={cs.get('deriva',0)}  topics={cs.get('n_segmenti_tematici',0)}")

    print(f"\n▸ AUTORITÀ")
    print(f"  Fonte: {r.autorita.fonte}  cred={r.autorita.credibilita:.2f}  expertise={r.autorita.expertise}")
    if r.autorita.bias_rilevati:
        print(f"  Bias: {', '.join(r.autorita.bias_rilevati)}")

    print(f"\n▸ COMPONENTI ε_ऋ")
    for k, v in r.componenti_epsilon.items():
        print(f"  {k:28s} = {v:.4f}")

    if r.patologie:
        print(f"\n▸ PATOLOGIE ({len(r.patologie)})")
        for p in r.patologie[:10]:
            print(f"  ⚠ {p}")

    if r.sintesi_narrativa:
        print(f"\n▸ SINTESI NARRATIVA (LLM)")
        print(f"  {r.sintesi_narrativa}")

    ind = r.induttivo
    if ind is None:
        print("\n▸ LLM INDUTTIVO: non richiesto")
    elif "errore" in ind:
        print(f"\n▸ LLM INDUTTIVO: FALLITO — {ind['errore']}")
    else:
        n_giudizi = len(ind.get("giudizi_parita", []))
        print(f"\n▸ LLM INDUTTIVO: ok — {n_giudizi} giudizi a parità")

    print(sep)


# ─── adapter Bus MCP (compat O-6) ────────────────────────────────────────────

class AgenteResh:
    """Nodo `resh` per il Bus MCP. Mantiene API identica al legacy.

    Implementa anche lo schema CLAUDE.md [#LAMBDA]:
      - `lambda_space`: i γ che l'agente può invocare autonomamente (Λ_ऋ).
      - `model_profile`: backend LLM selezionabile ('lm_studio'|'llama_cpp'|'openai').
      - `puo_invocare(γ)`: gate registrato; γ fuori-Λ → escalation a Θ.

    Λ è popolato a runtime con `LAMBDA_RESH` (vedi `resh.lambda_space`).
    """

    # spazio logico canonico — evolvibile a runtime con sign-off (CLAUDE.md [#LAMBDA])
    lambda_space: frozenset[Gamma] = LAMBDA_RESH

    def __init__(
        self,
        bus=None,
        name: str = "resh",
        sigma: str = "Σ-9",
        *,
        model_profile: str = "lm_studio",
    ):
        self.bus           = bus
        self.name          = name
        self.sigma         = sigma
        self.model_profile = model_profile

    # ─── Λ ──────────────────────────────────────────────────────────
    def puo_invocare(self, γ) -> bool:
        """True se `γ` (Gamma o nome str) è nello spazio logico dell'agente.

        γ fuori-Λ → caller deve escalare firmando una richiesta a Θ
        (vedi CLAUDE.md [#LAMBDA]). Questo metodo è il solo gate.
        """
        if isinstance(γ, Gamma):
            return γ in self.lambda_space
        if isinstance(γ, str):
            return any(g.name == γ for g in self.lambda_space)
        return False

    def gamma_disponibili(self) -> list[str]:
        """Nomi γ ordinati — utile per introspection / debug bus."""
        return sorted(g.name for g in self.lambda_space)

    # ─── pipeline ───────────────────────────────────────────────────
    def analizza(self, testo: str, verbose: bool = False) -> RapportoResh:
        return analizza(testo, verbose=verbose)

    def handle(self, msg) -> Optional[dict]:
        topic   = getattr(msg, "topic", "")
        payload = getattr(msg, "payload", {}) or {}
        if topic == "analisi.request":
            testo = payload.get("testo", "")
            if not isinstance(testo, str) or not testo.strip():
                return {"error": "payload.testo mancante o vuoto"}
            r = self.analizza(testo, verbose=False)
            return {
                "eps_resh":       r.eps_resh,
                "patologie":      r.patologie,
                "n_argomenti":    len(r.inventario),
                "densita":        r.densita_logica,
                "fascia_densita": r.fascia_densita,
                "agente":         self.name,
            }
        if topic == "ping":
            return {"pong": True, "agente": self.name, "sigma": self.sigma}
        if topic == "lambda.list":
            return {
                "agente":        self.name,
                "sigma":         self.sigma,
                "model_profile": self.model_profile,
                "lambda_space":  self.gamma_disponibili(),
                "n_gamma":       len(self.lambda_space),
            }
        return None
