"""resh/lambda_space.py — Λ_ऋ, spazio logico dell'agente Σ-9 ऋ.

Registra ogni metodo γ invocabile dall'agente come `Gamma` immutabile.
Conforme a CLAUDE.md [#LAMBDA]:

  «Λ è una classe per-agente, non una partizione globale. Ogni agente
   definisce il proprio Λ_𝔄 = insieme dei metodi γ che può invocare
   autonomamente. Λ evolve: si aggiungono γ nuovi, l'agente cresce.»

La **separazione fisica obbligatoria** (`gamma/` deterministici · `prompts/`
template LLM · `core.py` orchestrazione) per ora **non** è applicata sul
filesystem di `resh/` (refactor mid-flight). Ogni γ porta tuttavia un campo
`target_layer` che dichiara dove dovrà migrare quando il refactor fisico
verrà completato. La registry serve da mappa logica autoritativa nel
frattempo.

API pubblica
------------
  - `LAMBDA_RESH: frozenset[Gamma]`        — tutti i γ registrati
  - `Gamma`, `GammaArea`, `GammaKind`      — dataclass + enum
  - `get(name) -> Gamma | None`            — lookup per nome
  - `by_area(area) -> list[Gamma]`
  - `by_kind(kind) -> list[Gamma]`
  - `by_layer(layer) -> list[Gamma]`       — "gamma" | "prompts" | "core"
  - `resolve(name) -> Callable`            — importa e ritorna il callable
  - `summary() -> str`                     — testo diagnostico

Regola d'oro CLAUDE.md: «un γ non importa `prompts/`, un prompt non
chiama codice». `kind == LLM_CHAT` ⇔ `target_layer == "prompts"` ⇔
`llm_required is True`.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Callable, Optional

from gamma_types import GammaPort


# ─── tassonomia γ ─────────────────────────────────────────────────────


class GammaKind(str, Enum):
    """Natura computazionale del γ."""
    DETERMINISTIC = "deterministic"   # pura logica / lessici / regex / matematica
    NLP_SINGLETON = "nlp_singleton"   # usa modello ML preloaded (Stanza, BGE-M3)
    NLI_ZEROSHOT  = "nli_zeroshot"    # usa head NLI zero-shot
    LLM_CHAT      = "llm_chat"        # chiama chat completion LLM
    ORCHESTRATORE = "orchestratore"   # composizione di altri γ


class GammaArea(str, Enum):
    """Area funzionale CLAUDE.md [#LAMBDA] — orientativa, non gabbia."""
    IO_CORE       = "io_core"           # ingest testo + encoding
    NLI_HELPER    = "nli_helper"        # primitive zero-shot / entailment
    PROFILING     = "profiling"         # Profiling-UD
    STILOMETRIA   = "stilometria"       # Biber-style
    BIAS_AUTORITA = "bias_autorita"
    FALLACIE      = "fallacie"
    ARG_MINING    = "argument_mining"
    PREMESSE      = "premesse"
    COERENZA      = "coerenza"
    EPSILON       = "epsilon"
    FUZZY         = "fuzzy"           # ex Mamdani; dal 2026-06-12 (ADR-005) soglie fisse in core
    OBIETTIVO     = "obiettivo"
    # ── lato induttivo (arsenale ऋ) ──────────────────────────────────────
    INDUTTIVO     = "induttivo"         # orchestratore arsenale (selettore assi)
    TRILEMMA      = "trilemma"          # pre-detection Münchhausen
    INCLOSURA     = "inclosura"         # pre-detection Schema di Priest
    ASTRATTI      = "astratti"          # termini astratti (Berkeley)
    ORCHESTRA     = "orchestra"
    PERSISTENZA   = "persistenza"       # memoria run: SQLite append-only + firma Ψ


@dataclass(frozen=True)
class Gamma:
    """Metodo γ registrato nello spazio Λ di un agente.

    `name` è univoco. `callable_path` è in forma dotted `pkg.mod:attr`.
    `target_layer ∈ {"gamma", "prompts", "core"}` indica la cartella di
    destinazione quando la separazione fisica CLAUDE.md [#LAMBDA] sarà
    applicata.
    """
    name:           str
    area:           GammaArea
    kind:           GammaKind
    callable_path:  str
    target_layer:   str
    llm_required:   bool
    descrizione:    str
    input_ports:    tuple[GammaPort, ...] = ()
    output_ports:   tuple[GammaPort, ...] = ()
    # ── metadati per l'aggregatore ε (ratificati Σ_w 2026-06-09) ──────────
    # eps_role: come il γ si relaziona a eps_resh (l'aggregatore legge questo).
    #   "componente"      → entra in ε come fattore (alimenta ≥1 componente)
    #   "feed_canale"     → alimenta un componente/confronto, peso 0 proprio
    #   "giudizio_parita" → giudizio che AFFIANCA ε, NON vi entra (parità det↔ind)
    #   "combinatore"     → combina i componenti/lati, non ne alimenta alcuno
    #   "nessuno"         → infrastruttura/manutenzione, fuori da ε
    # Mappatura fine componente↔γ ASSEGNATA 2026-06-10 (design aggregatore,
    # vaglio Σ_w): vedi `eps_feeds` sui γ con eps_role="componente".
    eps_role:       str = "nessuno"
    # eps_feeds: nomi dei componenti ε (epsilon.COMPONENTI) che questo γ
    # alimenta. Non vuoto ⇔ eps_role=="componente" (invariante). Descrittivo:
    # dichiara la provenienza per l'aggregatore, NON cambia il calcolo di ε.
    eps_feeds:      tuple[str, ...] = ()
    # output_kind: forma dell'output, per il routing dei contributi.
    #   "metrica" | "lista" | "giudizio" | "rilievi" | "" (n/a)
    output_kind:    str = ""

    def __str__(self) -> str:
        return f"{self.name} [{self.area.value}/{self.kind.value}]"


# ─── registry Λ_ऋ ──────────────────────────────────────────────────────

LAMBDA_RESH: frozenset[Gamma] = frozenset({

    # ─── I/O core ────────────────────────────────────────────────────
    Gamma(
        name="γ_annota",
        area=GammaArea.IO_CORE,
        kind=GammaKind.NLP_SINGLETON,
        callable_path="resh.gamma.annotazione:annota",
        target_layer="gamma",
        llm_required=False,
        descrizione="Annotazione UD italiano (Stanza, tokenize+mwt+pos+lemma+depparse+ner); fallback regex.",
        input_ports=(
            GammaPort("testo", "str", "testo da annotare"),
        ),
        output_ports=(
            GammaPort("doc_annotato", "dict", "annotazione UD: tokens, pos, lemma, dep, ner"),
        ),
        eps_role="feed_canale",
    ),
    Gamma(
        name="γ_encode",
        area=GammaArea.IO_CORE,
        kind=GammaKind.NLP_SINGLETON,
        callable_path="resh.gamma.encoder:encode",
        target_layer="gamma",
        llm_required=False,
        descrizione="Embedding frasi BGE-M3 FP16 L2-norm; fallback hash bag-of-words.",
        input_ports=(
            GammaPort("frasi", "list[str]", "lista di frasi da embeddare"),
        ),
        output_ports=(
            GammaPort("embeddings", "ndarray", "matrice embeddings (n_frasi × dim)"),
        ),
        eps_role="feed_canale",
    ),
    Gamma(
        name="γ_segmenta_proposizioni",
        area=GammaArea.IO_CORE,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.gamma.chunking:segmenta_proposizioni",
        target_layer="gamma",
        llm_required=False,
        descrizione="Segmentazione proposizionale (clausole via dep-tree Stanza); fallback 1 proposizione/frase.",
        input_ports=(
            GammaPort("testo", "str", "testo da segmentare"),
            GammaPort("doc_annotato", "dict", "annotazione UD (da γ_annota)", opzionale=True),
        ),
        output_ports=(
            GammaPort("proposizioni", "list[dict]", "lista proposizioni con span e testo"),
        ),
        eps_role="feed_canale",
        output_kind="lista",
    ),

    # ─── NLI helpers (primitive condivise) ───────────────────────────
    Gamma(
        name="γ_classify_zero_shot",
        area=GammaArea.NLI_HELPER,
        kind=GammaKind.NLI_ZEROSHOT,
        callable_path="resh.gamma._nli:classify_zero_shot",
        target_layer="gamma",
        llm_required=False,
        descrizione="Zero-shot classification (deberta-v3-base-zeroshot-v2.0); fallback uniforme.",
        input_ports=(
            GammaPort("testo", "str", "testo da classificare"),
            GammaPort("labels", "list[str]", "etichette candidate"),
        ),
        output_ports=(
            GammaPort("scores", "dict", "mappa label→score"),
        ),
        eps_role="feed_canale",
    ),
    Gamma(
        name="γ_entail",
        area=GammaArea.NLI_HELPER,
        kind=GammaKind.NLI_ZEROSHOT,
        callable_path="resh.gamma._nli:entail",
        target_layer="gamma",
        llm_required=False,
        descrizione="p(entailment) premise→hypothesis ∈ [0,1]; fallback 0.0.",
        input_ports=(
            GammaPort("premise", "str", "proposizione premessa"),
            GammaPort("hypothesis", "str", "proposizione ipotesi"),
        ),
        output_ports=(
            GammaPort("p_entailment", "float", "probabilità di entailment ∈ [0,1]"),
        ),
        eps_role="feed_canale",
        output_kind="metrica",
    ),

    # ─── Profiling-UD ────────────────────────────────────────────────
    Gamma(
        name="γ_profilo_linguistico",
        area=GammaArea.PROFILING,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.gamma.profilo_linguistico:profilo_linguistico",
        target_layer="gamma",
        llm_required=False,
        descrizione="12+ feature Profiling-UD (TTR, MTLD, densità lessicale, Gulpease, depth, sub_ratio).",
        input_ports=(
            GammaPort("doc_annotato", "dict", "annotazione UD"),
        ),
        output_ports=(
            GammaPort("profilo", "dict", "metriche linguistiche (12+ feature)"),
        ),
        eps_role="feed_canale",
        output_kind="metrica",
    ),
    Gamma(
        name="γ_qualita_sintattica",
        area=GammaArea.PROFILING,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.gamma.profilo_linguistico:qualita_sintattica",
        target_layer="gamma",
        llm_required=False,
        descrizione="Score sintattico ∈ [0,1] derivato dal profilo (componente ε).",
        input_ports=(
            GammaPort("doc_annotato", "dict", "annotazione UD"),
        ),
        output_ports=(
            GammaPort("qualita_sintattica", "float", "score ∈ [0,1]"),
        ),
        eps_role="componente",
        eps_feeds=("qualita_sintattica",),
        output_kind="metrica",
    ),

    # ─── Stilometria ─────────────────────────────────────────────────
    Gamma(
        name="γ_profilo_stilistico",
        area=GammaArea.STILOMETRIA,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.gamma.stilometria:profilo_stilistico",
        target_layer="gamma",
        llm_required=False,
        descrizione="Feature Biber-style IT (pronomi, modali, passivi, connettivi, nominalizzazioni).",
        input_ports=(
            GammaPort("doc_annotato", "dict", "annotazione UD"),
        ),
        output_ports=(
            GammaPort("profilo_stilistico", "dict", "feature stilistiche Biber-style"),
        ),
    ),

    # ─── Bias & autorità ─────────────────────────────────────────────
    Gamma(
        name="γ_bias_autorita",
        area=GammaArea.BIAS_AUTORITA,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.gamma.bias_autorita:analizza_bias_autorita",
        target_layer="gamma",
        llm_required=False,
        descrizione="Hedging/booster ratio + ad verecundiam (NER + verbo dicendi + lessici).",
        input_ports=(
            GammaPort("doc_annotato", "dict", "annotazione UD"),
        ),
        output_ports=(
            GammaPort("bias", "dict", "hedging/booster ratio + marcatori autorità"),
        ),
        eps_role="componente",
        eps_feeds=("bias_linguistico", "credibilita_fonte"),
        output_kind="metrica",
    ),

    # ─── Fallacie ────────────────────────────────────────────────────
    Gamma(
        name="γ_rileva_fallacie",
        area=GammaArea.FALLACIE,
        kind=GammaKind.NLI_ZEROSHOT,
        callable_path="resh.gamma.fallacie:rileva_fallacie",
        target_layer="gamma",
        llm_required=False,
        descrizione="Regex IT + zero-shot NLI 13 etichette MAFALDA L2 (threshold 0.55).",
        input_ports=(
            GammaPort("testo", "str", "testo da analizzare"),
            GammaPort("doc_annotato", "dict", "annotazione UD", opzionale=True),
        ),
        output_ports=(
            GammaPort("fallacie", "list[dict]", "fallacie rilevate con tipo/span/score"),
        ),
        eps_role="componente",
        eps_feeds=("assenza_fallacie",),
        output_kind="lista",
    ),

    # ─── Argument mining ─────────────────────────────────────────────
    Gamma(
        name="γ_estrai_argomenti",
        area=GammaArea.ARG_MINING,
        kind=GammaKind.NLI_ZEROSHOT,
        callable_path="resh.gamma.argument_mining:estrai_argomenti",
        target_layer="gamma",
        llm_required=False,
        descrizione="Claim/premise classifier zero-shot + euristica connettivi per tipo.",
        input_ports=(
            GammaPort("testo", "str", "testo da analizzare"),
            GammaPort("proposizioni", "list[dict]", "proposizioni segmentate"),
        ),
        output_ports=(
            GammaPort("argomenti", "list[dict]", "struttura argomentativa: claim/premise con relazioni"),
        ),
        eps_role="componente",
        eps_feeds=("struttura_argomentativa",),
        output_kind="lista",
    ),
    Gamma(
        name="γ_verifica_sequitur",
        area=GammaArea.ARG_MINING,
        kind=GammaKind.NLI_ZEROSHOT,
        callable_path="resh.gamma.sequitur:verifica_sequitur",
        target_layer="gamma",
        llm_required=False,
        descrizione="Validità come entailment premesse→tesi (van Dalen ch01/ch06): NON_SEQUITUR + candidato C₃. No-op in fallback NLI.",
        input_ports=(
            GammaPort("argomenti", "list[dict]", "struttura argomentativa da γ_estrai_argomenti"),
        ),
        output_ports=(
            GammaPort("verdetti_sequitur", "list[dict]", "verdetti: SEQUITUR/NON_SEQUITUR per coppia"),
        ),
        eps_role="componente",
        eps_feeds=("validita_formale",),
        output_kind="lista",
    ),
    Gamma(
        name="γ_rileva_circolarita",
        area=GammaArea.ARG_MINING,
        kind=GammaKind.NLI_ZEROSHOT,
        callable_path="resh.gamma.sequitur:rileva_circolarita",
        target_layer="gamma",
        llm_required=False,
        descrizione="Circolarità strutturale (petitio): mutuo entailment premessa↔tesi → circular_reasoning confermato. No-op in fallback NLI.",
        input_ports=(
            GammaPort("argomenti", "list[dict]", "struttura argomentativa"),
        ),
        output_ports=(
            GammaPort("circolarita", "list[dict]", "coppie circolari rilevate"),
        ),
        eps_role="componente",
        # ADR-005 punto 5 (triage 2026-06-12): la petitio È una fallacia — alimenta
        # SOLO assenza_fallacie (la validità resta a γ_verifica_sequitur). La vecchia
        # dichiarazione doppia non corrispondeva al calcolo (core eroda già solo
        # assenza_fallacie): fix dichiarativo, ε identico per costruzione.
        eps_feeds=("assenza_fallacie",),
        output_kind="lista",
    ),

    # ─── Premesse ────────────────────────────────────────────────────
    Gamma(
        name="γ_analizza_premesse",
        area=GammaArea.PREMESSE,
        kind=GammaKind.NLI_ZEROSHOT,
        callable_path="resh.gamma.premesse_nli:analizza_premesse",
        target_layer="gamma",
        llm_required=False,
        descrizione="Entailment NLI + dep tree per premesse esplicite/implicite/sospette.",
        input_ports=(
            GammaPort("testo", "str", "testo originale"),
            GammaPort("proposizioni", "list[dict]", "proposizioni segmentate"),
            GammaPort("argomenti", "list[dict]", "struttura argomentativa"),
        ),
        output_ports=(
            GammaPort("premesse", "dict", "premesse esplicite/implicite/sospette + score trasparenza"),
        ),
        eps_role="componente",
        eps_feeds=("trasparenza_premesse",),
        output_kind="metrica",
    ),

    # ─── Coerenza ────────────────────────────────────────────────────
    Gamma(
        name="γ_analizza_coerenza",
        area=GammaArea.COERENZA,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.gamma.coerenza:analizza_coerenza",
        target_layer="gamma",
        llm_required=False,
        descrizione="Cosine locale/globale + drift k-segmento + BERTopic opt.",
        input_ports=(
            GammaPort("testo", "str", "testo da analizzare"),
            GammaPort("embeddings", "ndarray", "embeddings delle frasi (da γ_encode)"),
        ),
        output_ports=(
            GammaPort("coerenza", "dict", "metriche coerenza: locale, globale, drift"),
        ),
        eps_role="componente",
        eps_feeds=("coesione_semantica", "coerenza_tematica"),
        output_kind="metrica",
    ),

    # ─── Epsilon ─────────────────────────────────────────────────────
    Gamma(
        name="γ_calcola_epsilon",
        area=GammaArea.EPSILON,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.epsilon:calcola_epsilon",
        target_layer="gamma",
        llm_required=False,
        descrizione="ε_ℜ = exp(Σ wᵢ·log(cᵢ)) media geometrica pesata sui componenti presenti (None esclusi, reweight).",
        input_ports=(
            GammaPort("componenti", "dict", "mappa nome_componente→score ∈ [0,1]"),
        ),
        output_ports=(
            GammaPort("eps_resh", "float", "ε_ℜ aggregato ∈ [0,1]"),
        ),
        eps_role="combinatore",
        output_kind="metrica",
    ),
    Gamma(
        name="γ_aggrega_quadro",
        area=GammaArea.EPSILON,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.gamma.aggregatore:aggrega",
        target_layer="gamma",
        llm_required=False,
        descrizione="QuadroEpsilon: affianca det e ind a parità di ruolo. ε_ऋ verbatim, mai "
                    "ricalcolato; nessuna fusione det+ind; scarto binario CONTATO dei contributi "
                    "induttivi in errore/bad_json; copertura componente→γ letta da eps_feeds.",
        input_ports=(
            GammaPort("risultati_det", "dict", "risultati deterministici"),
            GammaPort("risultati_ind", "dict", "risultati induttivi", opzionale=True),
            GammaPort("eps_resh", "float", "ε_ℜ calcolato"),
        ),
        output_ports=(
            GammaPort("quadro", "QuadroEpsilon", "quadro completo det+ind a parità"),
        ),
        eps_role="combinatore",
        output_kind="rilievi",
    ),
    Gamma(
        name="γ_genesi",
        area=GammaArea.EPSILON,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.core:genesi",
        target_layer="gamma",
        llm_required=False,
        descrizione="Genealogia di ε: componenti ordinati per erosione (−wᵢ·log cᵢ) + patologie causa. «Una metrica → scava».",
        input_ports=(
            GammaPort("componenti", "dict", "mappa nome_componente→score"),
            GammaPort("eps_resh", "float", "ε_ℜ calcolato"),
        ),
        output_ports=(
            GammaPort("genesi", "dict", "genealogia: componenti ordinati per erosione + patologie"),
        ),
    ),
    # γ_modulatore_malafede RIMOSSO (ADR-005, eseguita 2026-06-12): no-op dal
    # 2026-05-20, identità con clamp. La malafede vive come γ_diagnosi_malafede
    # (giudizio a parità). Funzione in trash/2026-06-12/resh/.

    # ─── Fascia densità (ex fuzzy logic) ─────────────────────────────
    Gamma(
        name="γ_densita_fuzzy",
        area=GammaArea.FUZZY,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.core:fascia_densita",
        target_layer="gamma",
        llm_required=False,
        descrizione="Fascia densità a soglie fisse (ADR-005: ex Mamdani/simpful, stesso output): densita → fascia.",
        input_ports=(
            GammaPort("densita", "float", "valore densità lessicale"),
        ),
        output_ports=(
            GammaPort("fascia", "str", "fascia: bassa|media|alta"),
        ),
    ),

    # γ_sintesi_llm RIMOSSO (ADR-005): residuo dell'agente pre-rifondazione;
    # la voce narrativa spetta al Gateway (Σ-7). legacy_llm.py in trash/.

    # ─── Obiettivo O (induttivo, opzionale) ──────────────────────────
    Gamma(
        name="γ_estrai_obiettivo",
        area=GammaArea.OBIETTIVO,
        kind=GammaKind.LLM_CHAT,
        callable_path="resh.obiettivo:estrai_obiettivo",
        target_layer="prompts",
        llm_required=True,
        descrizione="Estrazione Obiettivo O da φ (default OFF). O-relativo per gli assi a valle, NON entra in ε (parità di ruolo).",
        input_ports=(
            GammaPort("testo", "str", "testo da cui estrarre l'obiettivo"),
        ),
        output_ports=(
            GammaPort("obiettivo_O", "dict", "obiettivo dichiarato + latente + contesto"),
        ),
        eps_role="feed_canale",
        output_kind="giudizio",
    ),
    Gamma(
        name="γ_valuta_integrita_obiettivo",
        area=GammaArea.OBIETTIVO,
        kind=GammaKind.NLI_ZEROSHOT,
        callable_path="resh.obiettivo:valuta_integrita_obiettivo",
        target_layer="gamma",
        llm_required=False,
        descrizione="Incoerenza INTRINSECA di O (dichiarato↔latente via NLI): contraddittorio/disperso/integro. Segnale strutturale in eps_resh, non verdetto.",
        input_ports=(
            GammaPort("obiettivo_O", "dict", "obiettivo estratto"),
            GammaPort("testo", "str", "testo originale"),
        ),
        output_ports=(
            GammaPort("integrita_O", "dict", "verdetto + score integrita"),
        ),
        eps_role="componente",
        eps_feeds=("integrita_obiettivo",),
        output_kind="metrica",
    ),
    Gamma(
        name="γ_diagnosi_malafede",
        area=GammaArea.OBIETTIVO,
        kind=GammaKind.LLM_CHAT,
        callable_path="resh.obiettivo:diagnosi_malafede",
        target_layer="prompts",
        llm_required=True,
        descrizione="Diagnosi induttiva di malafede sullo SCARTO O dichiarato↔latente: intento "
                    "manipolatorio/persuasivo/egoistico. SEGNALE a parità di ruolo, MAI verdetto "
                    "né modulatore di ε (il modulatore fuzzy resta frozen no-op). "
                    "«Fini egoistici ≠ cattivo prodotto» (Σ_w 2026-06-11).",
        input_ports=(
            GammaPort("obiettivo_O", "dict", "obiettivo con dichiarato/latente"),
            GammaPort("testo", "str", "testo originale"),
        ),
        output_ports=(
            GammaPort("diagnosi_malafede", "dict", "diagnosi: tipo intento + confidenza"),
        ),
        eps_role="giudizio_parita",
        output_kind="giudizio",
    ),

    # ─── Orchestratori ───────────────────────────────────────────────
    # γ_analizza DE-REGISTRATO (ADR-005): era una seconda entry per lo stesso
    # metodo. Il wrapper sincrono `core.analizza` resta come comodità API;
    # Λ registra il solo γ_analizza_async come metodo d'analisi.
    Gamma(
        name="γ_analizza_async",
        area=GammaArea.ORCHESTRA,
        kind=GammaKind.ORCHESTRATORE,
        callable_path="resh.core:analizza_async",
        target_layer="core",
        llm_required=False,
        descrizione="Pipeline asincrona 3-fase (substrato → 6 branch paralleli → ε_ऋ).",
        input_ports=(
            GammaPort("testo", "str", "testo da analizzare"),
        ),
        output_ports=(
            GammaPort("rapporto", "RapportoResh", "rapporto completo (det + ind + ε)"),
        ),
        eps_role="giudizio_parita",
        output_kind="giudizio",
    ),

    # ─── Arsenale induttivo (orchestratore + selettore assi) ─────────────
    Gamma(
        name="γ_analizza_induttivo",
        area=GammaArea.INDUTTIVO,
        kind=GammaKind.ORCHESTRATORE,
        callable_path="resh.induttivo:analizza_induttivo",
        target_layer="core",
        llm_required=True,
        descrizione="Orchestratore arsenale LLM: O → Arsenale → 11 assi ऋ → Trilemma → Δε. "
                    "Asse singolo via assi=[id] (selettore). Prompt da prompts_resh.md.",
        input_ports=(
            GammaPort("testo", "str", "testo da analizzare"),
            GammaPort("obiettivo_O", "dict", "obiettivo O estratto", opzionale=True),
        ),
        output_ports=(
            GammaPort("risultati_ind", "dict", "risultati 11 assi + trilemma + Δε"),
        ),
        eps_role="giudizio_parita",
        output_kind="giudizio",
    ),

    # ─── Pre-detection deterministiche (feed dei confronti, peso 0 proprio) ─
    Gamma(
        name="γ_pre_detect_trilemma",
        area=GammaArea.TRILEMMA,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.induttivo:pre_detect_trilemma",
        target_layer="gamma",
        llm_required=False,
        descrizione="Pre-detection Trilemma: marker regex (C₁/C₂/C₃) + segnali det (NON_SEQUITUR/petitio). "
                    "Presenza lessicale, non MODO. Dedup per testo con contatore occorrenze.",
        input_ports=(
            GammaPort("testo", "str", "testo da analizzare"),
            GammaPort("argomenti", "list[dict]", "struttura argomentativa", opzionale=True),
        ),
        output_ports=(
            GammaPort("hit_trilemma", "list[dict]", "marker C₁/C₂/C₃ con span e segnali"),
        ),
        eps_role="feed_canale",
        output_kind="lista",
    ),
    Gamma(
        name="γ_pre_detect_inclosura",
        area=GammaArea.INCLOSURA,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.induttivo:pre_detect_inclosura",
        target_layer="gamma",
        llm_required=False,
        descrizione="Pre-detection Schema di Inclosura (Priest): forma Ω/δ. Output list[TrilemmaHit] corno='INCL'. "
                    "Detector di forma ortogonale al Trilemma.",
        input_ports=(
            GammaPort("testo", "str", "testo da analizzare"),
        ),
        output_ports=(
            GammaPort("hit_inclosura", "list[dict]", "forme Ω/δ rilevate"),
        ),
        eps_role="feed_canale",
        output_kind="lista",
    ),
    Gamma(
        name="γ_pre_detect_abstract",
        area=GammaArea.ASTRATTI,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.induttivo:pre_detect_abstract",
        target_layer="gamma",
        llm_required=False,
        descrizione="Pre-detection termini astratti (Berkeley): morfologia (nominalizzazioni+plurali) + "
                    "lessico metafisico aggiornabile. Candidati (presenza), non verdetto. Sub-lente di ऋ⁴.",
        input_ports=(
            GammaPort("testo", "str", "testo da analizzare"),
        ),
        output_ports=(
            GammaPort("candidati_astratti", "list[dict]", "termini astratti candidati con span"),
        ),
        eps_role="feed_canale",
        output_kind="lista",
    ),

    # ─── Diagnosi induttiva termini astratti (occultamento) ──────────────
    Gamma(
        name="γ_diagnosi_termini_astratti",
        area=GammaArea.ASTRATTI,
        kind=GammaKind.LLM_CHAT,
        callable_path="resh.astratti:diagnosi_termini_astratti",
        target_layer="prompts",
        llm_required=True,
        descrizione="Classifica l'occultamento dei termini astratti (stipulazione/posito/ostensione/determinato) "
                    "rispetto a O. Tassonomia dal JSON. Feed di ऋ⁴ (no doppio conteggio).",
        input_ports=(
            GammaPort("candidati_astratti", "list[dict]", "candidati da γ_pre_detect_abstract"),
            GammaPort("obiettivo_O", "dict", "obiettivo O", opzionale=True),
            GammaPort("testo", "str", "testo originale"),
        ),
        output_ports=(
            GammaPort("diagnosi_astratti", "dict", "classificazione occultamento per termine"),
        ),
        eps_role="feed_canale",
        output_kind="giudizio",
    ),

    # ─── Reporting (rendering deterministico del grezzo, confine col gateway) ─
    Gamma(
        name="γ_report",
        area=GammaArea.ORCHESTRA,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.report:genera_report",
        target_layer="core",
        llm_required=False,
        descrizione="Rende il grezzo (det+ind+astratti) in markdown leggibile. ZERO giudizio/"
                    "selezione: stampa provenienza+scope, tutti i componenti/rilievi, e la Δε del "
                    "sistema verbatim. NON è il report-con-voce (= gateway): è il grezzo leggibile.",
        input_ports=(
            GammaPort("rapporto", "RapportoResh", "rapporto completo da γ_analizza_async"),
        ),
        output_ports=(
            GammaPort("markdown", "str", "report markdown leggibile"),
        ),
        eps_role="nessuno",
        output_kind="",
    ),

    # ─── Manutenzione lessico (interazione/promozione, fuori da ε) ───────
    Gamma(
        name="γ_promuovi_termine",
        area=GammaArea.ASTRATTI,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.induttivo:promuovi_termine",
        target_layer="gamma",
        llm_required=False,
        descrizione="Promuove un termine nel lessico astratti curato (canale feedback/richiesta, vaglio "
                    "advisory, provenienza loggata). Manutenzione del dato, non analisi.",
        input_ports=(
            GammaPort("termine", "str", "termine da promuovere"),
            GammaPort("canale", "str", "canale di provenienza"),
        ),
        output_ports=(
            GammaPort("esito_promozione", "dict", "esito: aggiunto/già presente/rifiutato"),
        ),
        eps_role="nessuno",
        output_kind="",
    ),

    # ─── Flusso DOCUMENTALE (paper intero, map-reduce) ───────────────────
    Gamma(
        name="γ_pulizia_input",
        area=GammaArea.IO_CORE,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.gamma.pulizia_input:compatta",
        target_layer="gamma",
        llm_required=False,
        descrizione="Pulizia/compressione input OPZIONALE (ispirata a TokenJuice, nativa): rimuove "
                    "marker pagina/header ricorrenti/note isolate, riflette i paragrafi. Riduzione misurata.",
        input_ports=(
            GammaPort("testo", "str", "testo grezzo da pulire"),
        ),
        output_ports=(
            GammaPort("testo_pulito", "str", "testo compattato"),
        ),
        eps_role="nessuno",
        output_kind="",
    ),
    Gamma(
        name="γ_righe_ricorrenti",
        area=GammaArea.IO_CORE,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.gamma.pulizia_input:righe_ricorrenti",
        target_layer="gamma",
        llm_required=False,
        descrizione="Individua le righe ricorrenti (header/footer di pagina) di un documento — "
                    "feed per la pulizia per-chunk. Registrato per il decreto Λ spina dorsale.",
        input_ports=(
            GammaPort("testo", "str", "testo documento intero"),
        ),
        output_ports=(
            GammaPort("righe_ricorrenti", "list[str]", "header/footer ricorrenti individuati"),
        ),
        eps_role="nessuno",
        output_kind="lista",
    ),
    Gamma(
        name="γ_pulizia_chunk",
        area=GammaArea.IO_CORE,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.gamma.pulizia_input:compatta_chunk",
        target_layer="gamma",
        llm_required=False,
        descrizione="Pulizia di un singolo chunk dato l'insieme delle righe ricorrenti del documento.",
        input_ports=(
            GammaPort("chunk", "str", "testo del chunk"),
            GammaPort("righe_ricorrenti", "list[str]", "righe ricorrenti da γ_righe_ricorrenti"),
        ),
        output_ports=(
            GammaPort("chunk_pulito", "str", "chunk compattato"),
        ),
        eps_role="nessuno",
        output_kind="",
    ),
    Gamma(
        name="γ_lingua_frontmatter",
        area=GammaArea.IO_CORE,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.gamma.pulizia_input:lingua_frontmatter",
        target_layer="gamma",
        llm_required=False,
        descrizione="Estrae la lingua dal frontmatter YAML senza pulire il documento — feed del "
                    "flusso documentale (evita una compatta intera buttata via).",
        input_ports=(
            GammaPort("testo", "str", "testo con frontmatter YAML"),
        ),
        output_ports=(
            GammaPort("lingua", "str", "codice lingua (es. 'it', 'en', 'de')"),
        ),
        eps_role="nessuno",
        output_kind="",
    ),
    Gamma(
        name="γ_segmenta_documento",
        area=GammaArea.IO_CORE,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.gamma.chunking_documento:segmenta_documento",
        target_layer="gamma",
        llm_required=False,
        descrizione="Segmentazione DOCUMENTALE (doc→chunk per pagina/sezione, packer greedy a frase; "
                    "né mini né oversize). Distinta dal chunking proposizionale.",
        input_ports=(
            GammaPort("testo", "str", "testo documento intero"),
        ),
        output_ports=(
            GammaPort("chunks", "list[dict]", "chunks con indice/span/testo"),
        ),
        eps_role="nessuno",
        output_kind="lista",
    ),
    Gamma(
        name="γ_analizza_documento_induttivo",
        area=GammaArea.INDUTTIVO,
        kind=GammaKind.ORCHESTRATORE,
        callable_path="resh.documento:analizza_documento_induttivo",
        target_layer="core",
        llm_required=True,
        descrizione="Orchestratore map-reduce sul DOCUMENTO: pulizia→chunk→O globale→MAP (det+arsenale "
                    "per chunk, resumable+budget)→REDUCE (ε pesata + Δε documento). File intermedi idempotenti.",
        input_ports=(
            GammaPort("testo", "str", "testo documento completo o path al file .md"),
        ),
        output_ports=(
            GammaPort("rapporto_doc", "RapportoDocumento", "rapporto map-reduce completo"),
        ),
        eps_role="giudizio_parita",
        output_kind="giudizio",
    ),
    Gamma(
        name="γ_report_documento",
        area=GammaArea.ORCHESTRA,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.report:genera_report_documento",
        target_layer="core",
        llm_required=False,
        descrizione="Rende un RapportoDocumento in markdown (scope=paper, ε_doc + per-chunk + Δε doc). "
                    "Zero giudizio del formatter.",
        input_ports=(
            GammaPort("rapporto_doc", "RapportoDocumento", "rapporto documento completo"),
        ),
        output_ports=(
            GammaPort("markdown", "str", "report documento markdown"),
        ),
        eps_role="nessuno",
        output_kind="",
    ),

    # ─── Persistenza (memoria dei run: SQLite WAL append-only, firma Ψ §6) ────
    Gamma(
        name="γ_save_run",
        area=GammaArea.PERSISTENZA,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.persistenza:save_run",
        target_layer="core",
        llm_required=False,
        descrizione="Persiste un RapportoResh (per-testo): run_uid Ψ_<doc12>_<seq>, frontmatter Ψ §6, "
                    "dump JSON completo. Append-only, mai DELETE. compare_runs per il drift di ε.",
        input_ports=(
            GammaPort("rapporto", "RapportoResh", "rapporto da persistere"),
        ),
        output_ports=(
            GammaPort("run_meta", "dict", "run_uid + path del file persistito"),
        ),
        eps_role="nessuno",
        output_kind="",
    ),
    Gamma(
        name="γ_save_run_documento",
        area=GammaArea.PERSISTENZA,
        kind=GammaKind.DETERMINISTIC,
        callable_path="resh.persistenza:save_run_documento",
        target_layer="core",
        llm_required=False,
        descrizione="Persiste un RapportoDocumento: run_uid Ψ_<doc12>_D<seq> + record di onestà "
                    "(call_eseguite, saltati, n_parti_errore, sha256 prompt). Il report si RIGENERA "
                    "dal rapporto_json salvato (il dato è canonico, il markdown è rendering).",
        input_ports=(
            GammaPort("rapporto_doc", "RapportoDocumento", "rapporto documento da persistere"),
        ),
        output_ports=(
            GammaPort("run_meta", "dict", "run_uid + path del file persistito"),
        ),
        eps_role="nessuno",
        output_kind="",
    ),
})


# ─── lookup helpers ────────────────────────────────────────────────────

_BY_NAME: dict[str, Gamma] = {g.name: g for g in LAMBDA_RESH}


def get(name: str) -> Optional[Gamma]:
    """Lookup γ per nome univoco. `None` se non registrato."""
    return _BY_NAME.get(name)


def by_area(area: GammaArea | str) -> list[Gamma]:
    if isinstance(area, str):
        area = GammaArea(area)
    return sorted([g for g in LAMBDA_RESH if g.area is area], key=lambda g: g.name)


def by_kind(kind: GammaKind | str) -> list[Gamma]:
    if isinstance(kind, str):
        kind = GammaKind(kind)
    return sorted([g for g in LAMBDA_RESH if g.kind is kind], key=lambda g: g.name)


def by_layer(layer: str) -> list[Gamma]:
    """`"gamma"` (deterministici) · `"prompts"` (LLM) · `"core"` (orchestratori)."""
    return sorted([g for g in LAMBDA_RESH if g.target_layer == layer], key=lambda g: g.name)


@lru_cache(maxsize=None)
def resolve(name: str) -> Callable:
    """Importa e ritorna il callable registrato sotto `name`.

    È LA VIA OBBLIGATA dei core (decisione Σ_w 2026-06-10: Λ spina dorsale —
    un metodo non registrato in Λ è irraggiungibile, non solo non documentato).
    Memoizzata: l'import dinamico si paga una volta per γ, non per chiamata.

    Solleva `KeyError` se il γ non è registrato o se il `callable_path` è
    malformato / non importabile.
    """
    g = _BY_NAME.get(name)
    if g is None:
        raise KeyError(f"γ non registrato: {name}")
    module_path, _, attr = g.callable_path.partition(":")
    if not module_path or not attr:
        raise KeyError(f"callable_path malformato per {name}: {g.callable_path}")
    mod = importlib.import_module(module_path)
    fn = getattr(mod, attr, None)
    if fn is None:
        raise KeyError(f"attr `{attr}` non trovato in `{module_path}`")
    return fn


class _GammaNomi:
    """Nomi γ come attributi: `G.ANNOTA == "γ_annota"`.

    I core NON scrivono stringhe magiche: `resolve(G.ANNOTA)`. Un nome
    sbagliato è `AttributeError` immediato (a import del modulo chiamante),
    non un `KeyError` a metà run. Generata dal registry → mai divergente."""

    def __init__(self) -> None:
        for g in LAMBDA_RESH:
            attr = g.name.removeprefix("γ_").upper()
            if hasattr(self, attr):
                raise RuntimeError(f"collisione nome costante γ: {attr}")
            object.__setattr__(self, attr, g.name)

    def __setattr__(self, k: str, v) -> None:        # immutabile dopo init
        raise AttributeError("G è di sola lettura (registry → costanti)")


G = _GammaNomi()


def summary() -> str:
    """Testo diagnostico ordinato per area, utile in debug / verbose."""
    lines = [f"Λ_ऋ — {len(LAMBDA_RESH)} γ registrati"]
    for area in GammaArea:
        items = by_area(area)
        if not items:
            continue
        lines.append(f"\n  [{area.value}]")
        for g in items:
            llm = "  llm" if g.llm_required else ""
            lines.append(
                f"    {g.name:26s} {g.kind.value:14s} → {g.callable_path}{llm}"
            )
    return "\n".join(lines)


# ─── invariante di consistenza ─────────────────────────────────────────

def _audit_invariants() -> None:
    """Verifica regola CLAUDE.md: kind==LLM_CHAT ⇔ target_layer=='prompts'
    ⇔ llm_required is True. Solleva AssertionError se violata."""
    for g in LAMBDA_RESH:
        if g.kind is GammaKind.LLM_CHAT:
            assert g.target_layer == "prompts", f"{g.name}: LLM_CHAT ma target_layer={g.target_layer}"
            assert g.llm_required, f"{g.name}: LLM_CHAT ma llm_required=False"
        else:
            assert g.target_layer in {"gamma", "core"}, f"{g.name}: target_layer={g.target_layer} non ammesso per kind={g.kind.value}"
            if g.kind is not GammaKind.ORCHESTRATORE:
                assert not g.llm_required, f"{g.name}: kind={g.kind.value} ma llm_required=True"
    names = [g.name for g in LAMBDA_RESH]
    assert len(set(names)) == len(names), "nomi γ non univoci"
    _EPS_ROLES = {"componente", "feed_canale", "giudizio_parita", "combinatore", "nessuno"}
    _OUT_KINDS = {"metrica", "lista", "giudizio", "rilievi", ""}
    for g in LAMBDA_RESH:
        assert g.eps_role in _EPS_ROLES, f"{g.name}: eps_role={g.eps_role!r} non valido"
        assert g.output_kind in _OUT_KINDS, f"{g.name}: output_kind={g.output_kind!r} non valido"
    # eps_feeds ⇔ eps_role=="componente"; ogni nome deve esistere in epsilon.COMPONENTI
    # (single source of truth dei componenti ε). Import locale: epsilon trascina numpy,
    # e lambda_space deve restare importabile anche in ambienti minimi.
    try:
        from .epsilon import COMPONENTI as _EPS_COMPONENTI
    except ImportError:
        _EPS_COMPONENTI = None     # ambiente minimo: si salta solo il subset-check
    for g in LAMBDA_RESH:
        if g.eps_role == "componente":
            assert g.eps_feeds, f"{g.name}: eps_role='componente' ma eps_feeds vuoto"
            if _EPS_COMPONENTI is not None:
                for c in g.eps_feeds:
                    assert c in _EPS_COMPONENTI, f"{g.name}: eps_feeds contiene {c!r} ∉ epsilon.COMPONENTI"
        else:
            assert g.eps_feeds == (), f"{g.name}: eps_feeds assegnato ma eps_role={g.eps_role!r}"


_audit_invariants()
