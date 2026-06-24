"""resh/documento.py — `analizza_documento_induttivo`: resh sul DOCUMENTO intero.

Map-reduce coerente su un paper lungo (vedi piano quiet-plotting-parnas):
  pulizia(opz) → chunk per pagina/sezione → O globale (una volta) →
  MAP per chunk (det + induttivo con O globale, resumable + budget) →
  REDUCE (ε aggregata pesata + sintesi finale Δε del documento).

Riusa: `chunking_documento`, `pulizia_input`, `core.analizza`,
`induttivo.analizza_induttivo`, `obiettivo` (prompt O), `config.call_llm_json`.

Onestà/quota: throttle RPM e flag `bad_json` già nell'hub; `max_call_budget` è un
tetto duro → i chunk oltre budget sono LOGGATI in `saltati` (no troncamento
silenzioso) e ripresi al run successivo grazie ai file intermedi (`resume`).
Il resume VALIDA i chunk cachati: parti con `errore` (es. 429 a metà run) vengono
ri-eseguite in modo mirato (`_parti_fallite`), mai ricaricate come complete.
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Optional

from . import config, obiettivo                  # hub LLM + DATI (SYS_OBIETTIVO: prompt=dato)
from .cache import CACHE_DIR as _CACHE           # costante

# ─── Λ spina dorsale: i metodi si pescano dal registry (Σ_w 2026-06-10) ──────
# γ_analizza_async si risolve LAZY in-function (evita il ciclo documento↔core a
# import-time, come il vecchio import locale). ADR-005: γ_analizza de-registrato,
# il metodo d'analisi in Λ è il solo γ_analizza_async (wrap sync qui via asyncio.run).
from .lambda_space import G, resolve
_righe_ricorrenti     = resolve(G.RIGHE_RICORRENTI)
_compatta_chunk       = resolve(G.PULIZIA_CHUNK)
_lingua_frontmatter   = resolve(G.LINGUA_FRONTMATTER)
_segmenta_documento   = resolve(G.SEGMENTA_DOCUMENTO)
_analizza_induttivo   = resolve(G.ANALIZZA_INDUTTIVO)
_diagnosi_astratti    = resolve(G.DIAGNOSI_TERMINI_ASTRATTI)
ASSI_CHUNK_DEFAULT = ["r2", "r4", "r6", "trilemma"]   # concept-level + Trilemma


@dataclass
class RapportoDocumento:
    fonte:        str
    lingua:       Optional[str]
    n_chunk:      int
    obiettivo:    Optional[dict]
    chunk:        list[dict]                 # per-chunk: {id, loc, det, ind}
    eps_doc:      Optional[float]
    eps_per_chunk: list[dict]
    sintesi_doc:  str
    saltati:      list[int]
    meta:         dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return self.__dict__


def _doc_hash(testo: str) -> str:
    return hashlib.sha256(testo.encode("utf-8")).hexdigest()[:16]


def _estrai_O(abstract: str, profile: Optional[str]) -> Optional[dict]:
    """O globale dell'agente, una volta, dalla regione abstract. Riusa il prompt di obiettivo.py.

    NB (cleanup futuro): riusa SYS_OBIETTIVO direttamente via call_llm_json invece di
    passare da γ_estrai_obiettivo — lecito (il prompt è un dato), ma da unificare."""
    try:
        usr = obiettivo._payload_user(abstract)
        # Budget pieno: su gemma-4-31b il ragionamento per l'estrazione O è
        # variabile e supera spesso i 3072 token; a 1500 (e talvolta a 3072)
        # veniva tagliato (finish=length, completion=0) PRIMA del JSON → content
        # vuoto → ValueError. Verificato 2026-06-16 sul testo reale: a 8192 chiude
        # (finish=stop). Gli assi (induttivo) reggono perché emettono ~300 token;
        # qui il modello "pensa" a lungo, quindi serve il tetto degli assi (8192).
        out = config.call_llm_json(obiettivo.SYS_OBIETTIVO, usr,
                                   max_tokens=8192, temperature=0.2, profile=profile,
                                   tag="ऋ-obiettivo-doc")
    except Exception as exc:
        return {"errore": f"{type(exc).__name__}: {exc}"}
    dich = str(out.get("obiettivo_dichiarato", "")).strip()
    if not dich:
        return None
    lat = out.get("obiettivo_latente")
    return {"dichiarato": dich[:300],
            "latente": (str(lat).strip()[:300] if lat not in (None, "", "null") else None),
            "coerenza": out.get("coerenza")}


def _parti_fallite(rec: dict) -> list[str]:
    """Id delle parti induttive con `errore` in un chunk cachato.

    Un run interrotto a metà (es. 429 quota) salvava chunk con assi in errore che
    il resume ricaricava come «completi» → il documento non si completava MAI da
    solo e il report sembrava pieno non essendolo. Questi id vengono ri-eseguiti
    (riparazione mirata: solo le parti fallite, non l'intero chunk)."""
    ind = rec.get("ind") or {}
    out: list[str] = []
    if isinstance(ind.get("arsenale"), dict) and "errore" in ind["arsenale"]:
        out.append("arsenale")
    for aid, a in (ind.get("assi") or {}).items():
        if isinstance(a, dict) and "errore" in a:
            out.append(aid)
    for k in ("trilemma", "inclosura"):
        llm = (ind.get(k) or {}).get("llm")
        if isinstance(llm, dict) and "errore" in llm:
            out.append(k)
    return out


def _nota_sintesi(loc: str, ind_d: dict) -> str:
    """Nota compatta per chunk (per il REDUCE): corno Trilemma + note assi."""
    tri = (ind_d.get("trilemma") or {}).get("llm", {})
    note = [f"[{loc}] corno {tri.get('corno','?')}/{tri.get('modo','?')}"]
    for aid, a in (ind_d.get("assi") or {}).items():
        if isinstance(a, dict) and a.get("nota"):
            note.append(f"{aid}: {a['nota']}")
    return " | ".join(note)


def _aggrega_epsilon(per_chunk: list[dict]) -> Optional[float]:
    """Media geometrica pesata per lunghezza dei chunk (coerente con ε geometrico)."""
    num = den = 0.0
    for c in per_chunk:
        e, w = c.get("eps"), c.get("char", 1)
        if e is None or e <= 0:
            continue
        num += w * math.log(e)
        den += w
    return round(math.exp(num / den), 4) if den else None


_SYS_SINTESI_DOC = """Sono ऋ. Ricevo l'Obiettivo O dell'agente che ha prodotto un documento e una
lista di rilievi/diagnosi già emersi dai miei assi critici applicati ai singoli chunk del documento.
Il mio compito è integrarli in una sintesi UNICA a livello di documento: dove la pretesa di φ regge e
dove cede, quale corno del Trilemma domina nel complesso, le tensioni ricorrenti tra i chunk. NON
produco un punteggio, NON invento rilievi nuovi, NON giudico la verità di φ. Sintetizzo ciò che è
già emerso, a livello dell'intero documento."""


def _sintesi_finale(O: Optional[dict], note_chunk: list[str], profile: Optional[str]) -> str:
    payload = ("Obiettivo O: " + json.dumps(O, ensure_ascii=False) + "\n\n"
               + "Rilievi/diagnosi per chunk (concatenati):\n"
               + "\n".join(f"- {n}" for n in note_chunk if n)
               + '\n\nRispondi ESCLUSIVAMENTE con JSON: {"sintesi": "<6-10 frasi a livello di documento>"}')
    try:
        out = config.call_llm_json(_SYS_SINTESI_DOC, payload, max_tokens=4096,
                                   temperature=0.3, profile=profile, tag="ऋ-sintesi-doc")
        return str(out.get("sintesi", "")).strip()
    except Exception as exc:
        return f"[sintesi documento non disponibile: {exc}]"


def analizza_documento_induttivo(
    testo: str, *, fonte: str = "", fonte_O: str = "abstract",
    assi_chunk: Optional[list[str]] = None, arsenale_completo: bool = False,
    con_astratti: bool = False, profile: Optional[str] = None,
    max_call_budget: Optional[int] = None, resume: bool = True,
    usa_pulizia: bool = True, det: bool = True, target_char: int = 4000,
) -> RapportoDocumento:
    """Analizza un documento intero (map-reduce). Vedi docstring modulo.

    - `arsenale_completo=True`: per ogni chunk gira TUTTI gli assi (Arsenale + ऋ⁰⁺–ऋ⁹
      + Trilemma + Inclosura), non il sottoinsieme `assi_chunk`. Test complessivo.
    - `con_astratti=True`: aggiunge la diagnosi Berkeley dei termini astratti per chunk.
    """
    assi_chunk = assi_chunk or list(ASSI_CHUNK_DEFAULT)
    assi_eff = None if arsenale_completo else assi_chunk   # None = tutti gli assi
    dh = _doc_hash(testo)
    # La chiave-cache include la CONFIG di analisi: analisi diverse (target_char,
    # arsenale completo vs sottoinsieme, astratti, det) NON collidono sullo stesso
    # chunk_<id>.json — evita il bug di ricaricare chunk stale di un'altra config.
    sig_src = f"tc={target_char}|full={arsenale_completo}|assi={sorted(assi_eff) if assi_eff else 'ALL'}|astr={con_astratti}|det={det}"
    sig = hashlib.sha256(sig_src.encode("utf-8")).hexdigest()[:8]
    cdir = _CACHE / f"doc_{dh}_{sig}"
    cdir.mkdir(parents=True, exist_ok=True)

    ricorrenti = _righe_ricorrenti(testo) if usa_pulizia else set()
    lingua = _lingua_frontmatter(testo) if usa_pulizia else None
    chunks = _segmenta_documento(testo, target_char=target_char)

    def _clean(t: str) -> str:
        return _compatta_chunk(t, ricorrenti) if usa_pulizia else t

    # O globale (una volta) dalla regione abstract = primo chunk pulito.
    # CACHATO in cdir: al resume si riusa LO STESSO O dei chunk già analizzati
    # (ri-estrarlo costerebbe 1 call e potrebbe divergere da quello usato nel MAP).
    O_f = cdir / "_obiettivo.json"
    if resume and O_f.exists():
        O = json.loads(O_f.read_text(encoding="utf-8")) or None
    else:
        O = _estrai_O(_clean(chunks[0].testo), profile) if chunks else None
        if O and "errore" not in O:
            O_f.write_text(json.dumps(O, ensure_ascii=False), encoding="utf-8")

    call_count = 0
    per_chunk_out: list[dict] = []
    eps_per_chunk: list[dict] = []
    note_chunk: list[str] = []
    saltati: list[int] = []

    riparati: list[int] = []

    for ch in chunks:
        cache_f = cdir / f"chunk_{ch.id}.json"
        if resume and cache_f.exists():
            rec = json.loads(cache_f.read_text(encoding="utf-8"))
            falliti = _parti_fallite(rec)
            if falliti:
                # riparazione mirata: ri-esegue SOLO le parti in errore (429 ecc.)
                if max_call_budget is not None and call_count + len(falliti) > max_call_budget:
                    saltati.append(ch.id)
                    continue
                fix = _analizza_induttivo(
                    _clean(ch.testo), obiettivo=_teleologia(O), assi=falliti,
                    sintesi=False, profile=profile).as_dict()
                ind_r = rec["ind"]
                if "arsenale" in falliti:
                    ind_r["arsenale"] = fix.get("arsenale")
                for aid in falliti:
                    if aid in (fix.get("assi") or {}):
                        ind_r["assi"][aid] = fix["assi"][aid]
                for k in ("trilemma", "inclosura"):
                    if k in falliti:
                        ind_r[k] = fix.get(k)
                call_count += len(falliti)
                riparati.append(ch.id)
                rec["nota_sintesi"] = _nota_sintesi(ch.loc, ind_r)
                cache_f.write_text(json.dumps(rec, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
            per_chunk_out.append(rec)
            eps_per_chunk.append({"id": ch.id, "loc": ch.loc,
                                  "eps": (rec.get("det") or {}).get("eps_resh"),
                                  "char": len(ch.testo)})
            note_chunk.append(rec.get("nota_sintesi", ""))
            continue

        # budget: se il prossimo chunk sforerebbe il tetto, salta (resumabile)
        costo = (14 if arsenale_completo else len(assi_chunk)) + (1 if con_astratti else 0)
        if max_call_budget is not None and call_count + costo > max_call_budget:
            saltati.append(ch.id)
            continue

        testo_c = _clean(ch.testo)
        det_out = None
        if det:
            try:
                _analizza_async = resolve(G.ANALIZZA_ASYNC)   # lazy: evita ciclo documento↔core
                r = asyncio.run(_analizza_async(testo_c, verbose=False))
                det_out = {"eps_resh": r.eps_resh, "componenti_epsilon": r.componenti_epsilon,
                           "patologie": list(r.patologie)[:10]}
            except Exception as exc:
                det_out = {"errore": f"{type(exc).__name__}: {exc}"}

        ind = _analizza_induttivo(testo_c, obiettivo=_teleologia(O),
                                  assi=assi_eff, sintesi=False, profile=profile)
        ind_d = ind.as_dict()
        astr = None
        if con_astratti:
            astr = _diagnosi_astratti(testo_c, obiettivo=_teleologia(O),
                                      profile=profile)
        call_count += costo

        nota_sintesi = _nota_sintesi(ch.loc, ind_d)

        rec = {"id": ch.id, "loc": ch.loc, "titolo": ch.titolo,
               "det": det_out, "ind": ind_d, "astratti": astr, "nota_sintesi": nota_sintesi}
        cache_f.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        per_chunk_out.append(rec)
        eps_per_chunk.append({"id": ch.id, "loc": ch.loc,
                              "eps": (det_out or {}).get("eps_resh"), "char": len(ch.testo)})
        note_chunk.append(nota_sintesi)

    eps_doc = _aggrega_epsilon(eps_per_chunk)
    sintesi_doc = _sintesi_finale(O, note_chunk, profile) if note_chunk else ""

    return RapportoDocumento(
        fonte=fonte, lingua=lingua, n_chunk=len(chunks), obiettivo=O,
        chunk=per_chunk_out, eps_doc=eps_doc, eps_per_chunk=eps_per_chunk,
        sintesi_doc=sintesi_doc, saltati=saltati,
        meta={"doc_hash": dh, "profilo": config.config_snapshot(profile).get("profile"),
              "model": config.config_snapshot(profile).get("model"),
              "assi_chunk": ("ALL (arsenale_completo)" if arsenale_completo else assi_chunk),
              "con_astratti": con_astratti, "call_eseguite": call_count,
              "riparati": riparati,
              "ts": datetime.datetime.now().isoformat(timespec="seconds")},
    )


def _teleologia(O: Optional[dict]):
    """Converte il dict O in Teleologia per analizza_induttivo (o None)."""
    if not O or "errore" in O or not O.get("dichiarato"):
        return None
    from .schemas import Teleologia
    return Teleologia(obiettivo_dichiarato=O["dichiarato"],
                      obiettivo_latente=O.get("latente"),
                      coerenza=float(O.get("coerenza") or 0.5),
                      nota="O globale del documento")
