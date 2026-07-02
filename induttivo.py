"""resh/induttivo.py — l'Arsenale induttivo di ऋ ESEGUITO (chiamate LLM).

Questo è il deliverable centrale rimasto dall'HANDOFF: i prompt di
`prompts_resh.md` (Arsenale, ऋ⁰⁺–ऋ⁹, Trilemma) finora esistevano solo come
*testo* — qui diventano **chiamate LLM** orchestrate. Tutto passa dall'hub
`config.call_llm_json` (workhorse Gemma, vedi config.py).

**Parità di ruolo** (vincolo architetturale, HANDOFF §0): l'induttivo produce
GIUDIZI, non parametri. NON tocca `eps_resh` né i 9 componenti deterministici. Il
deterministico *rileva* la struttura; l'induttivo la *qualifica* (C₃ strumentale
vs dissimulato, fallacie sospette, assi senza controparte deterministica). Un
futuro meta-giudizio li riconcilia simmetricamente.

**O-relatività** (HANDOFF §5.1): ogni prompt riceve `testo φ + Obiettivo O`. O è
estratto a monte da `obiettivo.estrai_obiettivo` (lato induttivo, LLM). I prompt
diagnostici sintetici (Arsenale, Trilemma) accettano anche un controargomento
candidato C, usato come sonda goal-aware.

**Single source of truth**: i prompt sono CARICATI da `prompts_resh.md` a runtime
(non duplicati in codice) — la voce 1ª persona di ऋ, le citazioni μ e le correzioni
restano là. Qui si aggiunge solo l'involucro JSON di output.

Sequenza (da «Note architetturali» di prompts_resh.md):
  1. O (+ C opzionale)  →  2. Arsenale  →  3. ऋ²ऋ³ऋ⁴ऋ⁶  →  4. ऋ⁵ऋ⁷ऋ⁸ऋ⁹
  →  5. ऋ⁰⁺ऋ⁰ऋ¹  →  6. Trilemma (riceve Arsenale + ऋ¹)  →  7. Δε (sintesi, opz.)

Quota (vedi config): ~14 call/testo. Su Gemma (1.5K RPD) sostenibile; sui Flash
(20 RPD) NO. Default profilo = `gemma-31`.

DEFAULT: eseguibile esplicitamente via `analizza_induttivo(...)`. Graceful: ogni
asse che fallisce è isolato (campo `errore`), non abbatte gli altri.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import config
from .schemas import Teleologia, TrilemmaHit


_PROMPTS_PATH = Path(__file__).parent / "prompts" / "prompts_resh.md"
_MARKERS_PATH = Path(__file__).with_name("lessici") / "trilemma_markers_it.json"
_ABSTRACT_PATH = Path(__file__).with_name("lessici") / "termini_astratti_it.json"

# Cache lazy dei lessici (caricati una sola volta per processo).
_trilemma_markers: list[dict] | None = None
_abstract_lex: dict | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Caricamento prompt da prompts_resh.md (single source of truth).
# Il corpo del prompt = testo dopo l'header `## ` fino a `**Input**` (escluso) —
# così le citazioni μ (blockquote `>`, che seguono `**Output**`) restano fuori.
# ─────────────────────────────────────────────────────────────────────────────
# Titoli EN delle sezioni nominate → prefissi IT cercati dal codice (_corpo).
# Gli assi ऋⁿ hanno lo stesso prefisso in entrambe le lingue: nessun raccordo.
_TITOLI_EN_IT = {
    "Critical Arsenal":            "Arsenale Critico",
    "Münchhausen Trilemma":        "Trilemma di Münchhausen",
    "Inclosure — Priest's Schema": "Inclosura — Schema di Priest",
}


def carica_prompt() -> dict[str, str]:
    """Mappa {titolo_sezione: corpo_prompt} dal file prompt della LINGUA ATTIVA.

    Con `config.LANG` = "en" carica prompts_resh_en.md (i titoli inglesi vengono
    rimappati sui prefissi IT che il codice cerca); fallback sul file IT se il
    file di lingua non esiste. Prima del fix il file IT era caricato SEMPRE:
    i giudizi uscivano in italiano anche su testi inglesi."""
    path = _PROMPTS_PATH
    lang = config.LANG.get()
    if lang and lang != "it":
        cand = _PROMPTS_PATH.with_name(f"prompts_resh_{lang}.md")
        if cand.exists():
            path = cand
    txt = path.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for sec in re.split(r"^## ", txt, flags=re.M)[1:]:
        title = sec.splitlines()[0].strip()
        body = sec.split("**Input**")[0]
        # via l'eventuale riga-titolo residua e spazi
        body = "\n".join(body.splitlines()[1:]).strip()
        out[_TITOLI_EN_IT.get(title, title)] = body
    return out


# id-asse → prefisso del titolo in prompts_resh.md (match per startswith).
_ASSI = [
    ("arsenale", "Arsenale Critico"),
    ("trilemma", "Trilemma di Münchhausen"),
    ("r0p", "ऋ⁰⁺"),
    ("r0",  "ऋ⁰ "),
    ("r1",  "ऋ¹"),
    ("r2",  "ऋ²"),
    ("r3",  "ऋ³"),
    ("r4",  "ऋ⁴"),
    ("r5",  "ऋ⁵"),
    ("r6",  "ऋ⁶"),
    ("r7",  "ऋ⁷"),
    ("r8",  "ऋ⁸"),
    ("r9",  "ऋ⁹"),
]

# gruppi paralleli della sequenza (Note architetturali).
_ASSI_CONCETTUALI = ["r2", "r3", "r4", "r6"]
_ASSI_POSTURA     = ["r5", "r7", "r8", "r9"]
_ASSI_FONDAZIONE  = ["r0p", "r0", "r1"]


def _corpo(prompts: dict[str, str], prefix: str) -> str:
    for title, body in prompts.items():
        if title.startswith(prefix):
            return body
    raise KeyError(f"prompt non trovato per prefisso {prefix!r}")


# ─────────────────────────────────────────────────────────────────────────────
# Involucri di output JSON (aggiunti al payload, non al prompt μ).
# La filosofia dell'arsenale è «rendere visibile la struttura, non produrre tesi»
# → l'output è una lista di RILIEVI che localizzano tensioni, mai un verdetto.
# ─────────────────────────────────────────────────────────────────────────────
_OUT_GENERICO = (
    'Rispondi ESCLUSIVAMENTE con JSON:\n'
    '{"rilievi": ["<frase che localizza UNA tensione specifica nel testo, '
    'senza risolverla, senza valutarla, senza proporre alternative>", ...], '
    '"nota": "<una frase di sintesi strutturale, oppure null>"}\n'
    'Se non emergono rilievi pertinenti a O, usa "rilievi": [].'
)

_OUT_ARSENALE = (
    'Rispondi ESCLUSIVAMENTE con JSON:\n'
    '{"asse_1_osservatore": "<1-2 frasi che localizzano la tensione, o null>", '
    '"asse_2_autoreferenza": "<1-2 frasi, o null>", '
    '"asse_3_autosufficienza": "<1-2 frasi, o null>", '
    '"contrasto": "<1-2 frasi sul termine di contrasto, o null>", '
    # Campo per il quesito «Squalifica del dissenso» (integrazione prompt
    # 2026-06-12, firma Σ_w): senza un posto nello schema il giudice non può
    # nominare la mossa anche volendo.
    '"squalifica_dissenso": "<1-2 frasi SOLO SE φ argomenta una tesi E '
    'squalifica chi dissente o dichiara evidente il controverso; nei testi '
    'narrativi e nel dubbio: null>"}'
)

# Vocabolario allineato a «Trilemma dataset/SCHEMA.md» v1.2. La distinzione di
# MODO (USE vs MENTION/DIAGNOSIS) è anti-falso-positivo: un testo CHE PARLA del
# Trilemma non vi CADE. NB: il campo `inclosura` (Priest) è volutamente ESCLUSO —
# è un modulo ortogonale da sotto-specializzare a parte, accantonato per ora.
_OUT_TRILEMMA = (
    'Rispondi ESCLUSIVAMENTE con JSON (vocabolario SCHEMA Trilemma v1.2):\n'
    '{"corno": "C1|C2|C3|NONE", '
    '"sottotipo": "<es. C1_meta_giustificazione | C2_viziosa_simmetrica | '
    'C2_virtuosa_autopoietica | C3_strumentale_dichiarato | C3_dogmatico_nascosto | …>", '
    '"modo": "USE|MENTION|DIAGNOSIS|SELF_DIAGNOSIS", '
    '"target": "<chi compie/subisce il gesto: agente di φ | posizione_filosofica | '
    'autore_target_specifico | none>", '
    '"polarita": "patologica|strumentale|virtuosa|selezionata_da_valore|neutra", '
    '"descrizione_catena": "<come e dove la catena di giustificazione termina>", '
    '"c3_strumentale_diagnostico": "<dichiarazione di un eventuale C₃ strumentale '
    'che usi tu stesso nella diagnosi, oppure null>"}'
)

# Inclosura (Schema di Priest) come detector di FORMA, parallelo al Trilemma.
# Slot-filling Ω/δ/Trascendenza/Chiusura. La forma è PRESENTE solo se trascendenza
# E chiusura valgono insieme (regola deterministica calcolata a valle, vedi
# _postprocess_inclosura). `risposta_al_limite` è la forcella operativa Kant/Priest/ε.
_OUT_INCLOSURA = (
    'Rispondi ESCLUSIVAMENTE con JSON:\n'
    '{"omega": "<il dominio-totalità Ω che φ pone (totalità del reale/pensiero/'
    'dicibile/esperienza), oppure null se φ non totalizza>", '
    '"delta": "<l\'operazione che genera δ(Ω): atto descrittivo/riflessivo/di '
    'tracciamento del limite, oppure null>", '
    '"trascendenza": {"vale": true|false, "span": "<porzione di φ dove δ(Ω) eccede '
    'Ω, o null>"}, '
    '"chiusura": {"vale": true|false, "span": "<porzione di φ dove δ(Ω) è interno '
    'a Ω, o null>"}, '
    '"modo": "USE|MENTION|DIAGNOSIS|SELF_DIAGNOSIS|NONE", '
    '"risposta_al_limite": "RISOLVE|ACCETTA|PERFORMA|NONE", '
    '"sottotipo": "INCL_osservatore|INCL_auto_referenza|INCL_meta_posizione|'
    'INCL_limite_pensiero|INCL_classica|NONE", '
    '"nota": "<una frase, oppure null>"}'
)


def _payload(testo: str, O: Optional[Teleologia], out_instr: str, *,
            C: Optional[str] = None, extra: str = "") -> str:
    righe = ['Testo φ:', '"""', testo.strip(), '"""', '']
    if O is not None:
        righe.append(f"Obiettivo O (dichiarato): {O.obiettivo_dichiarato}")
        if O.obiettivo_latente:
            righe.append(f"Obiettivo O (latente): {O.obiettivo_latente}")
    if C:
        righe.append(f"Controargomento candidato C a O: {C}")
    if extra:
        righe += ["", extra]
    righe += ["", out_instr]
    return "\n".join(righe)


# ─────────────────────────────────────────────────────────────────────────────
# Dataset Σ_w (append-only, per fine-tuning futuro — coerente con obiettivo.py).
# ─────────────────────────────────────────────────────────────────────────────
from .cache import CACHE_DIR as _CACHE_DIR

_DATASET_PATH = _CACHE_DIR / "induttivo_dataset.jsonl"
_logger = logging.getLogger(__name__)
_dataset_write_failed_warned = False


def _log_dataset(asse: str, system: str, user: str, out) -> None:
    if os.getenv("P3_RESH_IND_DATASET_DISABLE") == "1":
        return
    try:
        _DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "asse": asse,
            "model": config.config_snapshot().get("model"),
            "user_sha256": hashlib.sha256(user.encode("utf-8")).hexdigest()[:16],
            "output": out,
            "feedback_sigma_w": None,
        }
        with _DATASET_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError as exc:
        global _dataset_write_failed_warned
        if not _dataset_write_failed_warned:
            _dataset_write_failed_warned = True
            _logger.warning(
                "induttivo_dataset.jsonl (%s) non scrivibile: %s — dataset RF di "
                "questo processo resterà incompleto da qui in avanti (avviso una tantum)",
                _DATASET_PATH, exc)


# ─────────────────────────────────────────────────────────────────────────────
# Una singola call d'asse.
# ─────────────────────────────────────────────────────────────────────────────
def _call_asse(asse: str, system: str, user: str, *, profile: Optional[str] = None,
              max_tokens: Optional[int] = None,
              fallback_profile: Optional[str] = None) -> dict:
    """Esegue un asse. Ritorna il JSON dell'LLM, o `{"errore": ...}` (isolato).

    `max_tokens` adattivo alla lunghezza dell'input se non specificato: testi lunghi
    generano più rilievi → servono più token in output (i thinking model consumano
    anche budget di ragionamento). Limiti: [3072, 8192].
    `fallback_profile`: se specificato, tentato una volta se il profilo primario fallisce.
    """
    if max_tokens is None:
        max_tokens = min(8192, max(3072, len(user) // 5))
    try:
        out = config.call_llm_json(system, user, max_tokens=max_tokens,
                                   temperature=0.2, profile=profile, tag=f"ऋ-{asse}",
                                   fallback_profile=fallback_profile)
        _log_dataset(asse, system, user, out)
        return out
    except Exception as exc:
        err: dict = {"errore": f"{type(exc).__name__}: {exc}"}
        # Flag onestà per l'aggregatore: parse-fail JSON ≠ errore di trasporto.
        # (la trace ha già il flag `bad_json`; qui lo si propaga nel payload).
        if isinstance(exc, (ValueError, json.JSONDecodeError)) or "JSON" in str(exc):
            err["bad_json"] = True
        return err


# ─────────────────────────────────────────────────────────────────────────────
# Pre-detection deterministica Trilemma (marker regex + segnali deterministici).
# ─────────────────────────────────────────────────────────────────────────────
def _load_trilemma_markers() -> list[dict]:
    global _trilemma_markers
    if _trilemma_markers is None:
        try:
            raw = json.loads(_MARKERS_PATH.read_text(encoding="utf-8"))
            _trilemma_markers = raw.get("markers", [])
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[resh.induttivo] marker Trilemma non caricati: {exc}")
            _trilemma_markers = []
    return _trilemma_markers


def _scan_markers(testo: str, markers: list[dict]) -> list[TrilemmaHit]:
    """Scan regex generico → TrilemmaHit (fonte='marker_regex'), con dedup.

    Macchina condivisa Trilemma/Inclosura (e futuri detector lessicali). Dedup per
    (testo-matchato normalizzato, corno): occorrenze diverse dello stesso marker
    (es. «regresso infinito» 7 volte) = UN hit con conteggio, non 7 righe.
    """
    hits: list[TrilemmaHit] = []
    per_testo: dict[tuple[str, str], TrilemmaHit] = {}
    for m in markers:
        try:
            pattern = re.compile(m["regex"], re.IGNORECASE)
        except re.error:
            continue
        for match in pattern.finditer(testo):
            txt = match.group()
            key = (txt.lower().strip(), m["corno"])
            esistente = per_testo.get(key)
            if esistente is not None:
                esistente.dettaglio["occorrenze"] = esistente.dettaglio.get("occorrenze", 1) + 1
                continue
            hit = TrilemmaHit(
                corno=m["corno"],
                sottotipo=m.get("sottotipo", ""),
                confidence=m.get("confidence", 0.4),
                span_testo=txt,
                fonte="marker_regex",
                dettaglio={"regex_sottotipo": m.get("sottotipo", ""), "occorrenze": 1},
            )
            per_testo[key] = hit
            hits.append(hit)
    return hits


def pre_detect_trilemma(testo: str, rapporto_resh=None) -> list[TrilemmaHit]:
    """Pre-detection deterministica Trilemma: marker regex + segnali det esistenti.

    Funziona SENZA LLM. Se `rapporto_resh` (RapportoResh) è fornito, integra
    i segnali deterministici del pipeline core (NON_SEQUITUR/C3, petitio_principii).
    """
    # 1. Scan marker regex (macchina condivisa).
    hits: list[TrilemmaHit] = _scan_markers(testo, _load_trilemma_markers())

    # 2. Segnali dal deterministico (se disponibile).
    if rapporto_resh is not None:
        for pat in getattr(rapporto_resh, "patologie_strutturate", []):
            tipo_val = getattr(pat.tipo, "value", str(pat.tipo))
            if tipo_val == "non_sequitur":
                det = getattr(pat, "dettaglio", {}) or {}
                if det.get("corno") == "C3_candidato" or "C3" in str(det):
                    hits.append(TrilemmaHit(
                        corno="C3", sottotipo="C3_candidato_sequitur",
                        confidence=pat.confidence * 0.8,
                        span_testo=str(det.get("span", ""))[:200],
                        fonte="sequitur",
                        dettaglio={"patologia": tipo_val},
                    ))
            elif tipo_val == "fallacia_logica":
                det = getattr(pat, "dettaglio", {}) or {}
                if "petitio" in str(det).lower() or "circular" in str(det).lower():
                    hits.append(TrilemmaHit(
                        corno="C2", sottotipo="C2_viziosa_diretta",
                        confidence=pat.confidence * 0.8,
                        span_testo=str(det.get("span", ""))[:200],
                        fonte="circolarita",
                        dettaglio={"patologia": tipo_val},
                    ))

    return hits


def _confronta_trilemma(pre_hits: list[TrilemmaHit], llm_out: dict) -> dict:
    """Confronto det/ind: convergenze e divergenze.

    Non riconcilia — espone. La parità di ruolo si realizza nel surfacing,
    non nel verdetto.
    """
    corno_llm = str(llm_out.get("corno", "")).upper()
    convergenze: list[dict] = []
    divergenze: list[dict] = []

    for h in pre_hits:
        corno_det = h.corno.upper()
        if corno_det == corno_llm:
            convergenze.append({
                "corno": corno_det,
                "fonte_det": h.fonte,
                "sottotipo_det": h.sottotipo,
                "span": h.span_testo[:100],
                "nota": "segnale deterministico confermato dall'LLM",
            })
        else:
            divergenze.append({
                "corno_det": corno_det,
                "corno_llm": corno_llm,
                "fonte_det": h.fonte,
                "sottotipo_det": h.sottotipo,
                "span": h.span_testo[:100],
                "nota": "divergenza det/ind — nessuno dei due ha l'ultima parola",
            })

    # Segnali solo LLM (nessun pre-hit con stesso corno).
    corni_det = {h.corno.upper() for h in pre_hits}
    if corno_llm and corno_llm != "NONE" and corno_llm not in corni_det:
        divergenze.append({
            "corno_det": None,
            "corno_llm": corno_llm,
            "nota": "corno rilevato solo dall'LLM, nessun marker deterministico",
        })

    return {
        "convergenze": convergenze,
        "divergenze": divergenze,
        "n_pre_hits": len(pre_hits),
        "corno_llm": corno_llm,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Inclosura (Schema di Priest) — detector di FORMA, parallelo al Trilemma.
# Pre-detection: i marker INCL_* del lessico condiviso. Macchina = _scan_markers.
# ─────────────────────────────────────────────────────────────────────────────
def pre_detect_inclosura(testo: str) -> list[TrilemmaHit]:
    """Pre-detection deterministica Inclosura: marker INCL_* del lessico condiviso.

    Funziona SENZA LLM. Filtra i marker con corno 'INCL' dal medesimo file dei
    marker Trilemma (l'Inclosura è ortogonale ma vive nello stesso lessico).
    """
    incl = [m for m in _load_trilemma_markers() if m.get("corno") == "INCL"]
    return _scan_markers(testo, incl)


# risposta_al_limite → segnale verso Trilemma/Arsenale (regola deterministica).
_INCL_SEGNALE = {
    "RISOLVE": "C3 dissimulato sospetto: il piano-salvezza (dissoluzione della tensione) "
               "è di norma un assunto non mostrato — verificare in Trilemma/ऋ⁰⁺.",
    "ACCETTA": "Immunizzazione: la contraddizione è dichiarata vera e la logica adattata "
               "perché la regga — collasso della falsificabilità (parente del C3 degenerato).",
    "PERFORMA": "Nessuna patologia: ricorsività costitutiva, non contraddizione. "
                "La tensione è la firma operativa dell'auto-referenzialità, gestita nell'uso.",
}


def _postprocess_inclosura(llm_out: dict, pre_hits: list[TrilemmaHit]) -> dict:
    """Calcola deterministicamente la presenza-forma e il segnale verso altri assi.

    Non riconcilia: ESPONE (parità di ruolo). La forma-inclosura è PRESENTE solo
    se Trascendenza E Chiusura valgono insieme — regola, non giudizio LLM. Se l'LLM
    e la regola divergono, si registra la divergenza senza che nessuno prevalga.
    """
    if not isinstance(llm_out, dict) or "errore" in llm_out:
        return {"llm": llm_out, "pre_detection": [h.as_dict() for h in pre_hits],
                "forma": "indeterminata", "segnale": None}

    def _vale(k: str) -> bool:
        v = llm_out.get(k)
        return bool(v.get("vale")) if isinstance(v, dict) else False

    trasc, chius = _vale("trascendenza"), _vale("chiusura")
    if trasc and chius:
        forma = "presente"
    elif trasc or chius:
        forma = "parziale"
    else:
        forma = "assente"

    modo = str(llm_out.get("modo", "")).upper()
    risposta = str(llm_out.get("risposta_al_limite", "")).upper()
    # Il segnale verso Trilemma/Arsenale ha senso solo se la forma è performata (USE/SELF).
    segnale = None
    if forma == "presente" and modo in ("USE", "SELF_DIAGNOSIS"):
        segnale = _INCL_SEGNALE.get(risposta)

    return {
        "llm": llm_out,
        "pre_detection": [h.as_dict() for h in pre_hits],
        "forma": forma,                       # regola deterministica
        "forma_llm": llm_out.get("forma"),    # eventuale auto-dichiarazione LLM (se presente)
        "modo": modo,
        "risposta_al_limite": risposta,
        "segnale": segnale,
        "n_pre_hits": len(pre_hits),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Pre-detection deterministica TERMINI ASTRATTI (Berkeley) — F1 del piano nuovo.
# Trova CANDIDATI a idea astratta (presenza lessicale/morfologica), NON verdetti.
# Il giudizio (idea astratta illusoria che cela stipulazione normativa / posito
# metafisico?) resta INDUTTIVO. Output = list[dict] (contratto provvisorio: il
# record tipato è una scelta permanente non ancora ratificata).
# ─────────────────────────────────────────────────────────────────────────────
_WORD_RE = re.compile(r"\b[A-Za-zÀ-ÿ][a-zà-ÿ']{2,}\b")


def _load_abstract_lex() -> dict:
    global _abstract_lex
    if _abstract_lex is None:
        try:
            _abstract_lex = json.loads(_ABSTRACT_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[resh.induttivo] lessico termini astratti non caricato: {exc}")
            _abstract_lex = {}
    return _abstract_lex


def carica_tassonomia_occultamento() -> list[dict]:
    """Tipi di occultamento (dato AGGIORNABILE dal JSON, non hardcoded)."""
    return _load_abstract_lex().get("tassonomia_occultamento", [])


# Provenienza delle promozioni (append-only) — chi/perché un termine è entrato.
_PROMOZIONI_PATH = _CACHE_DIR / "promozioni_termini.jsonl"


def _log_promozione(termine: str, motivo: str, canale: str, vaglio: str) -> None:
    try:
        _PROMOZIONI_PATH.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
               "termine": termine, "canale": canale, "vaglio": vaglio, "motivo": motivo}
        with _PROMOZIONI_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def promuovi_termine(termine: str, *, motivo: str = "", canale: str = "richiesta_utente") -> dict:
    """Promuove un termine nella lista curata `termini_metafisici` (espandibile).

    Canali: 'richiesta_utente' (Σ_w lo chiede) | 'feedback' (emerso da un'analisi).
    Il VAGLIO è advisory, non un veto: registra se il termine è morfologicamente
    astratto, ma la richiesta di Σ_w resta autoritativa (può promuovere comunque).
    Aggiorna il JSON, invalida la cache, logga la provenienza.
    """
    global _abstract_lex
    t = (termine or "").strip().lower()
    if not t:
        return {"stato": "vuoto"}
    if len(t) > 64 or "\n" in t or not re.fullmatch(r"[\w\s'’\-]+", t, flags=re.UNICODE):
        return {"stato": "rifiutato_formato", "termine": t[:80]}
    lex = _load_abstract_lex()
    lista = lex.get("termini_metafisici", [])
    if t in {x.lower() for x in lista}:
        return {"stato": "gia_presente", "termine": t}

    # vaglio advisory: il termine è già un candidato morfologico/lessicale?
    candidati = {h["termine"] for h in pre_detect_abstract(t)}
    vaglio = "morfologicamente_astratto" if t in candidati else "da_verificare"

    lista.append(t)
    lex["termini_metafisici"] = lista
    try:
        _ABSTRACT_PATH.write_text(json.dumps(lex, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
    except OSError as exc:
        return {"stato": "errore_scrittura", "termine": t, "exc": str(exc)}
    _abstract_lex = None                       # invalida cache → prossima detection lo vede
    _log_promozione(t, motivo, canale, vaglio)
    return {"stato": "promosso", "termine": t, "vaglio": vaglio, "canale": canale}


def pre_detect_abstract(testo: str) -> list[dict]:
    """Candidati a termine astratto in φ (morfologia + lessico). AI-free.

    Ritorna list[dict] con: termine, fonte ('suffisso'|'lessico'), evidenza,
    occorrenze, span_esempio. PRESENZA, non verdetto — sovra-genera per design
    (l'LLM filtra rispetto a O). Dedup per termine (conta le occorrenze).
    """
    lex = _load_abstract_lex()
    metafisici = {t.lower() for t in lex.get("termini_metafisici", [])}
    stop = {s.lower() for s in lex.get("stopwords_suffisso", [])}

    # forme singolare + plurale per ogni suffisso (recall sui plurali italiani:
    # -zione→-zioni, -ezza→-ezze, -ismo→-ismi, -tudine→-tudini; -ità invariante).
    suffissi: list[tuple[str, int]] = []
    for s in lex.get("suffissi_nominalizzanti", []):
        suf, ml = s["suffisso"], s.get("min_len", 5)
        forme = {suf}
        if suf.endswith("a"):
            forme.add(suf[:-1] + "e")
        elif suf.endswith("e"):
            forme.add(suf[:-1] + "i")
        elif suf.endswith("o"):
            forme.add(suf[:-1] + "i")
        for f in forme:
            suffissi.append((f, ml))

    per_termine: dict[str, dict] = {}

    def _aggiungi(termine: str, fonte: str, evidenza: str) -> None:
        key = termine.lower()
        esistente = per_termine.get(key)
        if esistente is not None:
            esistente["occorrenze"] += 1
            return
        per_termine[key] = {
            "termine": termine.lower(),
            "fonte": fonte,
            "evidenza": evidenza,
            "occorrenze": 1,
            "span_esempio": termine,
        }

    for match in _WORD_RE.finditer(testo):
        w = match.group()
        if "'" in w:                       # elisione it.: l'essere, dell'identità → essere, identità
            w = w.rsplit("'", 1)[-1]
        if len(w) < 3:
            continue
        wl = w.lower()
        if wl in stop:
            continue
        if wl in metafisici:
            _aggiungi(w, "lessico", "termine_metafisico")
            continue
        for suf, ml in suffissi:
            if wl.endswith(suf) and len(wl) >= ml:
                _aggiungi(w, "suffisso", f"-{suf}")
                break

    # ordina per occorrenze decrescenti (i più centrali emergono)
    return sorted(per_termine.values(), key=lambda d: -d["occorrenze"])


def _serialize_pre_hits(pre_hits: list[TrilemmaHit]) -> str:
    """Serializza i pre-hit come CANDIDATI da giudicare nel prompt LLM.

    Non contesto facoltativo: il giudizio deve rendere conto di ogni candidato,
    altrimenti il lessico deterministico viene scavalcato in silenzio (visto
    accadere: il «si deve credere» di Berkeley §3 ignorato da due modelli)."""
    if not pre_hits:
        return ""
    lines = ["Candidati pre-rilevati dal lato deterministico (marker lessicali e "
             "segnali strutturali). NON sono contesto facoltativo: valutali UNO PER UNO."]
    for h in pre_hits[:15]:  # cap a 15 per non gonfiare il prompt
        lines.append(f"  - {h.corno}/{h.sottotipo} (conf={h.confidence:.2f}, "
                     f"fonte={h.fonte}): «{h.span_testo[:80]}»")
    lines.append("NB: i marker indicano PRESENZA lessicale, non MODO (USE/MENTION). "
                 "Un testo che PARLA di un corno contiene i marker senza CADERE nel corno.")
    lines.append("VINCOLO: in `descrizione_catena` rendi conto dei candidati sopra — "
                 "se il corno o il punto di arresto che scegli diverge dal candidato "
                 "più forte, dichiara esplicitamente perché lo rigetti, citando il "
                 "passo. Un candidato ignorato in silenzio è un errore di analisi.")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Rapporto induttivo.
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class RapportoInduttivo:
    obiettivo:  Optional[Teleologia]
    controargomento: Optional[str]
    arsenale:   dict
    assi:       dict           # {id_asse: output_json}
    trilemma:   dict
    inclosura:  dict = field(default_factory=dict)
    sintesi:    Optional[str] = None
    profilo:    str = ""
    meta:       dict = field(default_factory=dict)
    assi_falliti: list = field(default_factory=list)  # id assi che hanno restituito {"errore": ...}

    def as_dict(self) -> dict:
        return {
            "obiettivo": (
                {"dichiarato": self.obiettivo.obiettivo_dichiarato,
                 "latente": self.obiettivo.obiettivo_latente,
                 "coerenza": self.obiettivo.coerenza}
                if self.obiettivo else None
            ),
            "controargomento": self.controargomento,
            "arsenale": self.arsenale,
            "assi": self.assi,
            "trilemma": self.trilemma,
            "inclosura": self.inclosura,
            "sintesi": self.sintesi,
            "profilo": self.profilo,
            "meta": self.meta,
            "assi_falliti": self.assi_falliti,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Orchestratore.
# ─────────────────────────────────────────────────────────────────────────────
def analizza_induttivo(
    testo: str,
    *,
    obiettivo: Optional[Teleologia] = None,
    controargomento: Optional[str] = None,
    estrai_o: bool = True,
    sintesi: bool = False,
    profile: Optional[str] = None,
    fallback_profile: Optional[str] = None,
    assi: Optional[list[str]] = None,
    rapporto_resh=None,
) -> RapportoInduttivo:
    """Esegue l'arsenale induttivo su `testo`.

    - `obiettivo`: se None e `estrai_o`, viene estratto via `obiettivo.estrai_obiettivo`.
    - `controargomento` C: sonda goal-aware opzionale per Arsenale/Trilemma.
    - `assi`: sottoinsieme di id da eseguire (default: tutti). Utile per risparmiare quota.
    - `sintesi`: se True, una call finale Δε integra i rilievi (non incluso nei prompt μ).
    - `profile`: override profilo LLM (default: profilo attivo del config, di norma gemma-31).
    - `rapporto_resh`: RapportoResh deterministico, se disponibile. I segnali strutturali
      (NON_SEQUITUR/C3, petitio_principii) alimentano la pre-detection Trilemma.
    """
    if not (testo or "").strip():
        raise ValueError("testo vuoto")

    prompts = carica_prompt()
    snap = config.config_snapshot(profile)
    prof_name = snap["profile"]

    # 1. Obiettivo O.
    O = obiettivo
    if O is None and estrai_o:
        from .lambda_space import G, resolve
        O = resolve(G.ESTRAI_OBIETTIVO)(testo)    # lazy: Λ spina dorsale

    da_eseguire = assi if assi is not None else [a for a, _ in _ASSI if a not in ("arsenale", "trilemma")]

    # 2. Arsenale (3 assi + contrasto in una call).
    arsenale_out: dict = {}
    if assi is None or "arsenale" in assi:
        sys_ars = _corpo(prompts, "Arsenale Critico")
        usr_ars = _payload(testo, O, _OUT_ARSENALE, C=controargomento)
        arsenale_out = _call_asse("arsenale", sys_ars, usr_ars, profile=profile,
                                  fallback_profile=fallback_profile)

    # 3-5. Assi ऋ (generici). Eseguiti in sequenza (rispetta RPM; isolati su errore).
    assi_out: dict = {}
    for gid in [*_ASSI_CONCETTUALI, *_ASSI_POSTURA, *_ASSI_FONDAZIONE]:
        if gid not in da_eseguire:
            continue
        prefix = dict(_ASSI)[gid]
        sys_a = _corpo(prompts, prefix)
        usr_a = _payload(testo, O, _OUT_GENERICO)
        assi_out[gid] = _call_asse(gid, sys_a, usr_a, profile=profile,
                                   fallback_profile=fallback_profile)

    # 6. Trilemma — riceve Arsenale + ℜ¹ + pre-detection deterministica.
    trilemma_out: dict = {}
    if assi is None or "trilemma" in (assi or []):
        # 6a. Pre-detection deterministica (marker regex + segnali det).
        pre_hits = pre_detect_trilemma(testo, rapporto_resh=rapporto_resh)

        sys_tri = _corpo(prompts, "Trilemma di Münchhausen")
        feed = []
        if arsenale_out and "errore" not in arsenale_out:
            feed.append("Output Arsenale (già applicato):\n" +
                        json.dumps(arsenale_out, ensure_ascii=False))
        if "r1" in assi_out and "errore" not in assi_out["r1"]:
            feed.append("Output ℜ¹ Infondabilità (catene di giustificazione):\n" +
                        json.dumps(assi_out["r1"], ensure_ascii=False))
        # Inietta pre-detection come contesto informativo per l'LLM.
        pre_ctx = _serialize_pre_hits(pre_hits)
        if pre_ctx:
            feed.append(pre_ctx)
        usr_tri = _payload(testo, O, _OUT_TRILEMMA, C=controargomento,
                          extra="\n\n".join(feed))
        llm_tri = _call_asse("trilemma", sys_tri, usr_tri, profile=profile,
                             fallback_profile=fallback_profile)

        # 6b. Confronto det/ind.
        confronto = _confronta_trilemma(pre_hits, llm_tri)
        trilemma_out = {
            "llm": llm_tri,
            "pre_detection": [h.as_dict() for h in pre_hits],
            "confronto": confronto,
        }

    # 6c. Inclosura — detector di FORMA, parallelo al Trilemma (Schema di Priest).
    inclosura_out: dict = {}
    if assi is None or "inclosura" in (assi or []):
        incl_hits = pre_detect_inclosura(testo)
        sys_incl = _corpo(prompts, "Inclosura")
        feed_i = []
        if arsenale_out and "errore" not in arsenale_out:
            # il Primo Asse (Osservatore) è il feed privilegiato: stessa forma.
            feed_i.append("Output Arsenale (Primo Asse / Osservatore già applicato):\n" +
                          json.dumps(arsenale_out, ensure_ascii=False))
        pre_ctx_i = _serialize_pre_hits(incl_hits)
        if pre_ctx_i:
            feed_i.append(pre_ctx_i)
        usr_incl = _payload(testo, O, _OUT_INCLOSURA, C=controargomento,
                            extra="\n\n".join(feed_i))
        llm_incl = _call_asse("inclosura", sys_incl, usr_incl, profile=profile,
                              fallback_profile=fallback_profile)
        inclosura_out = _postprocess_inclosura(llm_incl, incl_hits)

    _assi_falliti = []
    if "errore" in arsenale_out:
        _assi_falliti.append("arsenale")
    for _gid, _out in assi_out.items():
        if isinstance(_out, dict) and "errore" in _out:
            _assi_falliti.append(_gid)
    if trilemma_out and "errore" in trilemma_out.get("llm", {}):
        _assi_falliti.append("trilemma")
    if inclosura_out and "errore" in inclosura_out.get("llm", {}):
        _assi_falliti.append("inclosura")

    rap = RapportoInduttivo(
        obiettivo=O,
        controargomento=controargomento,
        arsenale=arsenale_out,
        assi=assi_out,
        trilemma=trilemma_out,
        inclosura=inclosura_out,
        profilo=prof_name,
        meta={"model": snap.get("model"),
              "n_call": (1 if arsenale_out else 0) + len(assi_out)
                        + (1 if trilemma_out else 0) + (1 if inclosura_out else 0)},
        assi_falliti=_assi_falliti,
    )

    # 7. Δε — sintesi finale opzionale (integra i rilievi; non produce numeri).
    if sintesi:
        rap.sintesi = _sintesi_delta_epsilon(rap, profile=profile)

    return rap


_SYS_DELTA = """Sono ऋ. Ricevo i rilievi già prodotti dai miei assi critici su un
testo φ rispetto a un Obiettivo O. Il mio compito è integrarli in una sintesi
strutturale (Δε): dove φ regge, dove le tensioni convergono, quale corno del
Trilemma domina. NON produco un punteggio. NON invento rilievi nuovi. NON giudico
la verità di φ. Rendo leggibile la mappa delle tensioni già emerse."""


def _sintesi_delta_epsilon(rap: RapportoInduttivo, *, profile: Optional[str] = None) -> str:
    payload = (
        "Rilievi raccolti (JSON):\n"
        + json.dumps(rap.as_dict(), ensure_ascii=False, indent=2)
        + '\n\nRispondi ESCLUSIVAMENTE con JSON: {"sintesi": "<4-7 frasi in italiano>"}'
    )
    try:
        out = config.call_llm_json(_SYS_DELTA, payload, max_tokens=4096,
                                   temperature=0.3, profile=profile, tag="ऋ-delta")
        return str(out.get("sintesi", "")).strip()
    except Exception as exc:
        return f"[sintesi Δε non disponibile: {exc}]"


def should_run() -> bool:
    """Per CLI/orchestratore: env globale (default False)."""
    return os.getenv("P3_RESH_INDUTTIVO") == "1"
