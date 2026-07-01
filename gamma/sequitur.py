"""resh/sequitur.py — Verifica di sequitur-ità: la validità come entailment.

Derivato dalla skill `van-dalen-logic` (D. van Dalen, *Logic and Structure*):

  • ch01 — la *validità* di un argomento è `Γ ⊢ ϕ` (le premesse derivano la
    conclusione), una proprietà STRUTTURALE. NON è «assenza di fallacie
    nominate». `epsilon.validita_argomenti = 1 - frac_fallacie` confonde i due
    piani: un *non sequitur* (entimema con premessa occulta) non ha alcuna
    fallacia MAFALDA, eppure è invalido.

  • ch06 — *proprietà di sottoformula*: in una derivazione normale ogni formula
    è sottoformula di un'ipotesi o della conclusione. Una conclusione che
    introduce contenuto NON entailed dalle premesse segnala una **premessa
    occulta** (entimema). Se la tesi reca un modale di necessità («deve»,
    «necessariamente») senza che le premesse la derivino, l'occulta è
    un'**interruzione dogmatica** — candidato corno C₃ del Trilemma di
    Münchhausen (cfr. README «Lavoro aperto»; analisi PHK §26 nel report
    van-dalen del paper Gorgia/Berkeley).

Metodo (per ogni `Argomento` dell'inventario):
  1. contesto-premesse := {arg.testo} ∪ arg.premesse_usate.
  2. p_entail := NLI.entail(contesto-premesse, arg.tesi_supportata) ∈ [0,1].
  3. se `0 < p_entail < soglia` → `Patologia(NON_SEQUITUR)`,
        severità = 1 - p_entail (ampiezza del salto),
        + `dettaglio.corno = "C3_candidato"` se la tesi reca un modale di necessità.

Contratto `_nli`: `entail()` ritorna **0.0 come "sconosciuto"** (fallback /
NLI disabilitato). Perciò `p_entail == 0.0` NON viene mai segnalato: in
fallback il modulo è no-op (nessun falso positivo). Vedi `backend_info()`.

NB calibrazione: `premesse_usate` sono i vicini-coseno (euristici), non le
premesse logiche reali, e l'entailment NLI è in una sola direzione. Il segnale
è *suggestivo*, non una prova di invalidità: confidence è cappata a 0.85
(0.90 per il candidato C₃, segnale strutturale più forte). L'aggancio a
`epsilon.validita_argomenti` è lasciato a Σ_w (decisione di calibrazione, come
il freeze malafede): questo γ è **additivo**, non modula ε di per sé.
"""

from __future__ import annotations

import re

from . import _nli
from ..schemas import Argomento, Patologia, TipoPatologia


# Modali di necessità: la tesi si dichiara necessaria. Quando le premesse NON
# la derivano, il «deve» è la traccia grammaticale di un C₃ (interruzione
# dogmatica travestita da necessità — cfr. Berkeley PHK §26).
_NECESSITA_RE = re.compile(
    r"\b(deve|devono|dev[‘’]|si\s+deve|bisogna|occorre|"
    r"necessariamente|per\s+forza|non\s+pu[òo]\s+che|non\s+possono\s+che|"
    r"è\s+necessario|è\s+inevitabile|inevitabilmente|"
    r"must|necessarily|it\s+is\s+necessary|cannot\s+but|"
    r"have\s+to|has\s+to|need\s+to|needs\s+to|"
    r"inevitably|is\s+inevitable|is\s+required)\b",
    re.IGNORECASE,
)

# Premesse condizionali: il conseguente di un «se… allora» NON è circolarità
# (es. modus ponens). Servono a escludere il falso positivo del rilevatore di petitio.
_CONDIZIONALE_RE = re.compile(
    r"\b(se|qualora|purch[ée]|laddove|nel\s+caso\s+in\s+cui|ammesso\s+che|if)\b",
    re.IGNORECASE,
)

# Sotto questa soglia di entailment: premesse ↛ tesi = non sequitur.
# Calibrata sulla batteria (resh_battery 2026-06): i non-sequitur reali hanno
# p_entail < 0.03, gli entimemi VALIDI (premessa maggiore taciuta) ~0.20. Soglia
# bassa = alta precisione, non flagga gli entimemi (cultura anti-falso-positivo
# di resh). Da ritarare su corpus annotato Σ_w.
SOGLIA_ENTAIL = 0.12

# Circolarità (petitio): mutua derivazione premessa↔tesi. Soglia ALTA perché qui
# serve confidenza di *equivalenza*, non solo di derivazione.
SOGLIA_CIRCOLARITA = 0.70

# Sovrapposizione lessicale oltre la quale prem↔tesi è un *restatement* (stesse
# parole) e non una petitio *semantica* (stessa cosa, parole diverse) → si scarta
# per non confondere ripetizione con circolarità. Scelta, non taratura: da
# ricalibrare su corpus annotato Σ_w.
SOGLIA_JACCARD_RESTATEMENT = 0.5

# `entail` ritorna esattamente 0.0 solo in fallback/eccezione (un modello
# funzionante produce float continui dal softmax): sentinella "sconosciuto".
_UNKNOWN = 0.0

_MAX_CONTEXT_CHARS = 1500   # ~400 token, sotto i 512 del modello NLI


def _contesto_premesse(arg: Argomento) -> str:
    """`{arg.testo} ∪ arg.premesse_usate`, deduplicato, troncato sotto i 512 tok."""
    parti = [arg.testo] + list(arg.premesse_usate or [])
    visti: list[str] = []
    for p in parti:
        p = (p or "").strip()
        if p and p not in visti:
            visti.append(p)
    return " ".join(visti)[:_MAX_CONTEXT_CHARS]


def verifica_sequitur(
    inventario: list[Argomento],
    *,
    soglia: float = SOGLIA_ENTAIL,
) -> list[Patologia]:
    """Patologie `NON_SEQUITUR` per gli argomenti le cui premesse non derivano
    la tesi (validità come entailment, van Dalen ch01/ch06).

    No-op in fallback NLI (`entail == 0.0` → mai segnalato).
    """
    out: list[Patologia] = []
    for arg in inventario:
        tesi = (arg.tesi_supportata or "").strip()
        if not tesi or tesi == (arg.testo or "").strip():
            continue   # tesi assente o coincidente con la premessa → skip
        if len((arg.testo or "").split()) < 5:
            continue   # frammento troppo corto: NLI senza contesto → falso positivo
        contesto = _contesto_premesse(arg)
        if not contesto:
            continue

        p_entail = float(_nli.entail(contesto, tesi))
        if p_entail <= _UNKNOWN:
            continue   # 'sconosciuto' (fallback NLI) → nessun falso positivo
        if p_entail >= soglia:
            continue   # le premesse derivano la tesi → sequitur valido

        gap = 1.0 - p_entail
        n_prem = sum(1 for p in ([arg.testo] + list(arg.premesse_usate or []))
                     if (p or "").strip())
        necessita = bool(_NECESSITA_RE.search(tesi)
                         or _NECESSITA_RE.search(arg.testo or ""))

        dettaglio = {
            "argomento": (arg.testo or "")[:200],   # per mappare su VerificaLogica in core
            "tesi":     tesi[:200],
            "p_entail": round(p_entail, 4),
            "gap":      round(gap, 4),
            "n_premesse": n_prem,
            "fonte":    "nli_entail",
        }
        confidence = min(0.85, gap)
        if necessita:
            # interruzione dogmatica: il «deve» non derivato = corno C₃
            dettaglio["corno"] = "C3_candidato"
            confidence = min(0.90, confidence + 0.10)

        # Tipologia di attacco ASPIC+ (vocabolario, NON re-implementazione): qualifica
        # DOVE colpisce il defeater, per il meta-giudizio a valle. C₃ (necessità
        # asserita ma non derivata) = la regola inferenziale è inapplicabile →
        # UNDERCUT; salto senza modale (entimema, manca una premessa a sostegno) →
        # UNDERMINE. (`rebut` — attacco alla conclusione — non ha analogo
        # intra-argomento: la typology resta parzialmente istanziata, onestamente.)
        dettaglio["attacco_aspic"] = "undercut" if necessita else "undermine"

        out.append(Patologia(
            tipo       = TipoPatologia.NON_SEQUITUR,
            severita   = round(min(1.0, gap), 4),
            confidence = round(confidence, 4),
            span_char  = None,
            dettaglio  = dettaglio,
            origine_modulo = "sequitur",
        ))

    # Dedup per TESI: una conclusione non-derivata è UN non-sequitur, non uno per
    # ogni premessa. Senza questo, lo stesso difetto verrebbe contato N volte (una
    # per premessa che non la deriva) e penalizzerebbe ε N volte. Tiene, per ogni
    # tesi, il più severo (p_entail più basso).
    per_tesi: dict[str, Patologia] = {}
    for p in out:
        k = p.dettaglio.get("tesi", "")
        if k not in per_tesi or p.severita > per_tesi[k].severita:
            per_tesi[k] = p
    return list(per_tesi.values())


def _jaccard(a: str, b: str) -> float:
    """Sovrapposizione lessicale (parole-contenuto >2 char). Alta = restatement
    (stesse parole), non petitio *semantico* (stessa cosa, parole diverse)."""
    ta = {w for w in re.findall(r"\w+", a.lower()) if len(w) > 2}
    tb = {w for w in re.findall(r"\w+", b.lower()) if len(w) > 2}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


# Marcatori subordinanti/causali in testa a una premessa: la introducono come
# clausola dipendente con soggetto spesso ellittico (condiviso con la matrice).
_MARCATORE_SUBORD_RE = re.compile(
    r"^\s*(perch[ée]|poich[ée]|giacch[ée]|sicc?ome|dato\s+che|visto\s+che|"
    r"in\s+quanto|dacch[ée]|che)\b[\s,]*",
    re.IGNORECASE,
)
# Copule IT: confine soggetto|predicato in una clausola copulare ed indizio che il
# «resto» di una subordinata è una predicazione priva di soggetto.
_COPULA_RE = re.compile(r"^\s*(è|e'|sono|era|erano|sia|fosse|fossero)\b", re.IGNORECASE)
_COPULA_INTERNA_RE = re.compile(r"\b(è|e'|sono|era|erano|sia|fosse|fossero)\b", re.IGNORECASE)


def _soggetto_di(tesi: str) -> str:
    """Soggetto euristico = porzione prima della copula in una tesi copulare
    («Questa legge è giusta» → «Questa legge»). Vuoto se la tesi non è copulare."""
    m = _COPULA_INTERNA_RE.search(tesi)
    if not m or m.start() == 0:
        return ""
    return tesi[:m.start()].strip().strip(",;:").strip()


def _arricchisci_premessa_ellittica(prem: str, tesi: str) -> str:
    """Per il SOLO confronto di circolarità: se `prem` è una subordinata copulare
    col soggetto ellittico (condiviso con la tesi), ricostruisce «soggetto(tesi) +
    predicato(prem)». Senza il soggetto l'NLI non vede l'equivalenza della petitio
    «S è P₁ perché (S) è P₂» (van Dalen ch06). NON altera la proposizione
    memorizzata: gli offset verbatim restano intatti, è un arricchimento locale."""
    m = _MARCATORE_SUBORD_RE.match(prem)
    if not m:
        return prem
    resto = prem[m.end():].strip()
    if not _COPULA_RE.match(resto):       # il resto deve essere una predicazione (è …)
        return prem
    sogg = _soggetto_di(tesi)
    if not sogg:
        return prem
    return f"{sogg} {resto}"


def rileva_circolarita(
    inventario: list[Argomento],
    *,
    soglia: float = SOGLIA_CIRCOLARITA,
) -> list[Patologia]:
    """Rileva circolarità (`circular_reasoning`/petitio) **strutturale**: premessa
    e tesi si derivano A VICENDA (mutuo entailment) → la tesi è già assunta nelle
    premesse. Riusa `_nli.entail` nelle due direzioni.

    È **confermata** (non «sospetta» come lo zero-shot di rilevanza), perché è una
    proprietà *strutturale* verificabile. Distinta dalla validità: un argomento
    valido ha `premesse→tesi` alta ma `tesi→premesse` BASSA (non si recuperano le
    premesse dalla conclusione); il circolo ha **entrambe** alte. Direction-agnostica
    (non importa quale unità sia etichettata «tesi»). No-op in fallback NLI.

    Confronta la conclusione con OGNI premessa singola, **escludendo le premesse
    condizionali**: il conseguente di un «se… allora» (es. modus ponens) ha mutuo
    entailment alto per sovrapposizione (e perché `B ⊨ (A→B)`), ma NON è petitio.
    La circolarità è: una premessa *asserisce* (non condiziona) la conclusione.

    Dedup per tesi: un circolo = una patologia.
    """
    per_tesi: dict[str, Patologia] = {}
    for arg in inventario:
        tesi = (arg.tesi_supportata or "").strip()
        if not tesi:
            continue
        for prem in [arg.testo] + list(arg.premesse_usate or []):
            prem = (prem or "").strip()
            if not prem or prem == tesi:
                continue
            if _CONDIZIONALE_RE.search(prem):
                continue       # premessa condizionale → conseguente non è petitio
            # Jaccard sulla premessa ORIGINALE: il restatement è una proprietà del
            # contenuto. Usare la premessa arricchita (vedi sotto) gonfierebbe la
            # sovrapposizione col soggetto — condiviso per costruzione con la tesi —
            # e scarterebbe per errore una petitio genuina col soggetto lungo.
            if _jaccard(prem, tesi) > SOGLIA_JACCARD_RESTATEMENT:
                continue       # sovrapposizione lessicale = restatement, non petitio semantico
            # Soggetto ellittico ricostruito per il SOLO confronto NLI (proposizione
            # verbatim invariata): la petitio «S è P₁ perché (S) è P₂» è invisibile
            # all'NLI senza S nella premessa.
            prem_cmp = _arricchisci_premessa_ellittica(prem, tesi)
            fwd = float(_nli.entail(prem_cmp, tesi))     # premessa → tesi
            bwd = float(_nli.entail(tesi, prem_cmp))      # tesi → premessa (equivalenza?)
            if fwd <= _UNKNOWN or bwd <= _UNKNOWN:     # fallback NLI → no-op
                continue
            if fwd >= soglia and bwd >= soglia:
                sev = round(min(fwd, bwd), 4)
                k = tesi[:200]
                if k in per_tesi and per_tesi[k].severita >= sev:
                    break
                per_tesi[k] = Patologia(
                    tipo       = TipoPatologia.FALLACIA_LOGICA,
                    severita   = sev,
                    confidence = sev,
                    span_char  = None,
                    dettaglio  = {
                        "fallacia_l2": "circular_reasoning",
                        "fonte":       "strutturale_entailment",
                        "confermata":  True,        # struttura verificabile (≠ zero-shot)
                        "tesi":        tesi[:200],
                        "premessa":    prem[:200],
                        "fwd":         round(fwd, 4),
                        "bwd":         round(bwd, 4),
                        "argomento":   (arg.testo or "")[:200],
                    },
                    origine_modulo = "sequitur",
                )
                break        # un circolo per tesi basta
    return list(per_tesi.values())


def backend_info() -> dict:
    """Stato del backend NLI sotteso (per traccia §6 / degradazione controllata)."""
    nli = _nli.backend_info()
    if "disabled" in nli or "fallback" in nli:
        stato = "fallback"       # verifica_sequitur è no-op
    elif "lazy" in nli:
        stato = "lazy"
    else:
        stato = "attivo"
    return {"modulo": "sequitur", "nli": nli, "stato": stato}
