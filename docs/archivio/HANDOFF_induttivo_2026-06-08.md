> **⚠ DOCUMENTO STORICO (archiviato 2026-06-10).** La missione di questo handoff è
> compiuta: il lato induttivo è costruito, testato e integrato. Lo stato corrente
> del progetto è nel `README.md` alla radice. Le citazioni «HANDOFF §N» nei
> docstring del codice si riferiscono alle sezioni di questo file.

# HANDOFF — dal deterministico `resh` alla sessione dell'agente induttivo

**Data:** 2026-06-08 · **Autore:** sessione deterministica (Σ_w + Claude) · **Per:** chi svilupperà
il lato **induttivo** (LLM) di ऋ a partire da `P3 - Antonio Giordano/raw/prompts_resh.md`.

Questo documento comunica lo **stato della parte deterministica** dopo un ciclo di sviluppo +
stabilizzazione, e i **punti di aggancio** per il lato induttivo. Leggilo prima di toccare codice.

---

## 🔄 AGGIORNAMENTO 2026-06-09b — pipeline induttiva + pre-detection Trilemma

La pipeline induttiva è **costruita e funzionante**. Il «deliverable centrale rimasto» (§ sotto) è FATTO.

### Pipeline induttiva (`induttivo.py`)

`analizza_induttivo(testo, ...)` esegue l'arsenale come **chiamate LLM** orchestrate (hub `config.py`,
workhorse Gemma 4, 1.5K RPD). Sequenza: O → Arsenale → ऋ²ऋ³ऋ⁴ऋ⁶ → ऋ⁵ऋ⁷ऋ⁸ऋ⁹ → ऋ⁰⁺ऋ⁰ऋ¹ → Trilemma
(+ pre-detection) → Δε (opz.). ~14 call/testo. Graceful: ogni asse che fallisce è isolato (`errore`).

Prompt caricati a runtime da `prompts_resh.md` (single source of truth). Output: `RapportoInduttivo`
con obiettivo, controargomento, arsenale, assi, trilemma, sintesi, profilo, meta.

### Hub LLM (`config.py`)

Centralizza chiavi API, profili, throttle RPM, sanitizzazione `<think>`/`<thought>`, parsing JSON
tollerante. Profili: `gemma-31` (DEFAULT, 15 RPM, 1.5K RPD), `gemini-3.1-lite` (500 RPD),
`gemini-3-flash`/`3.5-flash` (20 RPD — inutilizzabili per la pipeline intera), `local` (LM Studio).

### Trace (`trace.py`)

Osservabilità: ogni call LLM tracciata con flag `ok/empty/truncated/error`, append-only su
`.cache/resh/llm_trace.jsonl`. `P3_LLM_VERBOSE=1` per log su stderr.

### Pre-detection Trilemma (NUOVO 2026-06-09b)

**Parità di ruolo realizzata sul Trilemma.** Il deterministico e l'induttivo convergono sullo stesso
oggetto con segnali propri:

- **`lessici/trilemma_markers_it.json`** (v1.1): 14 marker regex bilingui it/en, tipati per sotto-tipo
  (C1_esplicito, C2_viziosa, C3_dogmatico, C3_modale, C3_teologico, ecc.). Estratti da REPORT §7.
- **`pre_detect_trilemma(testo, rapporto_resh=None)`** in `induttivo.py`: scansiona marker + raccoglie
  segnali det esistenti (`NON_SEQUITUR/C3_candidato` da sequitur, `petitio_principii` da fallacie).
  Funziona SENZA LLM.
- **Iniezione nel prompt LLM**: i pre-hit alimentano il prompt Trilemma come contesto informativo
  (NON autorità). Il modello parte da segnali concreti, con nota esplicita: «marker ≠ USE».
- **Confronto det/ind**: `_confronta_trilemma()` produce convergenze (stesso corno) e divergenze
  (disaccordo). Nessuna riconciliazione automatica — il surfacing È la parità di ruolo.
- **Output arricchito**: `trilemma` in `RapportoInduttivo` ora contiene `{llm, pre_detection, confronto}`.

**Batteria** (`tests/test_trilemma_predetect.py`): 234 gold, recall USE 34% (C3: 40%), precision
NONE 85%. Integrata in `run_batterie.py`.

- **`TrilemmaHit`** dataclass in `schemas.py`: `corno, sottotipo, confidence, span_testo, fonte, modo,
  polarita, dettaglio`. Fonte discrimina: `marker_regex | sequitur | circolarita | llm`.

### Eval Trilemma LLM — risultati

`tests/eval_trilemma.py` su `gemini-3.1-flash-lite`, 48 record (12 per corno):

| Metrica | Pre-fix prompt | Post-fix prompt |
|---|---|---|
| corno | 48% | 56% (+8) |
| modo | 35% | 50% (+15) |

Residuo strutturale: NONE→C3 11/12 — il modello davanti a definizioni/discussioni di un corno
vede dogma dove non c'è. Ipotesi Σ_w (O a livello-documento migliora modo): eval `--with-o` era
in corso (13/48) quando la sessione ha raggiunto i limiti.

### Correzione concettuale: C₄ soppresso

C₄ NON esiste. Le proposte storiche (Apel, Klein, Haack, Williams) sono fenomenologicamente
riconducibili a C₁/C₂/C₃ — cambia il giudizio di valore, non la struttura. Il campo `polarita`
cattura la differenza. Corretto in SCHEMA v1.2, REPORT v7.1, e gold dataset.

### Come testare ora

```powershell
# batteria combinata (sequitur + fallacie + integrità O + pre-detection Trilemma)
python -m resh.tests.run_batterie [--quick]

# eval Trilemma LLM (brucia quota)
python -m resh.tests.eval_trilemma --n 6 [--with-o]

# pipeline induttiva end-to-end (brucia ~14 call LLM)
python -m resh.tests.run_pipeline [--profile gemma-31]
```

### File nuovi o significativamente modificati (sessione 2026-06-09)

| File | Stato |
|---|---|
| `induttivo.py` | **NUOVO** — orchestratore arsenale induttivo |
| `config.py` | **NUOVO** — hub LLM centralizzato |
| `trace.py` | **NUOVO** — osservabilità chiamate LLM |
| `obiettivo.py` | **AGGIORNATO** — graceful fallback via config.py |
| `prompts_resh.md` | **CORRETTO** — voce 1ª persona, C, USE/MENTION, NONE ammesso |
| `schemas.py` | **AGGIORNATO** — + `TrilemmaHit` dataclass |
| `lessici/trilemma_markers_it.json` | **NUOVO** — 14 marker bilingui pre-detection |
| `tests/eval_trilemma.py` | **NUOVO** — eval LLM su gold con `--with-o` |
| `tests/run_pipeline.py` | **NUOVO** — runner end-to-end pipeline induttiva |
| `tests/test_trilemma_predetect.py` | **NUOVO** — batteria pre-detection (no LLM) |
| `tests/run_batterie.py` | **AGGIORNATO** — + batteria Trilemma pre-detect |
| `Trilemma dataset/SCHEMA.md` | **AGGIORNATO** v1.2 — C₄ soppresso |
| `Trilemma dataset/REPORT.md` | **AGGIORNATO** v7.1 — reclassificazione C₄ |

### Cosa NON è ancora fatto

- **Full pipeline test end-to-end** (`run_pipeline.py`): scritto ma non ancora lanciato con successo.
- **Eval con O** (`--with-o`): interrotto a 13/48 — risultati incompleti.
- **Integrazione `induttivo` in `core.py`**: i due lati (det e ind) vivono separati. L'integrazione
  (campo `induttivo: Optional[RapportoInduttivo]` su `RapportoResh`) è il prossimo passo architetturale.
- **Gate 7** (W7 — premesse_nli da frasi a proposizioni).
- **Gate 8** (inclosure Priest come rilevatore-di-forma).
- **Fine-tuning su gold Trilemma** (234 record) per classificatore dedicato.

---

## 🔄 AGGIORNAMENTO 2026-06-09 — sessione di lavoro (LEGGI PRIMA)

Una sessione di lavoro ha **superato gran parte di questo handoff**. Stato reale ora:

### Fatto e verificato (batterie verdi a ogni passo)
- **`prompts_resh.md` CORRETTO** (la «PRIMA AZIONE» qui sotto è FATTA): riga 11
  «fondazionalista»→«non-fondazionalista»; voce uniformata alla 1ª persona di ऋ⁰–ऋ⁹; ऋ⁰ «fondativa»
  preservato; citazioni μ verbatim. Aggiunto il **controargomento candidato C** come input opzionale ad
  Arsenale e Trilemma (goal-aware, Jeong et al.).
- **Loose-end W4 (filtro Jaccard): RISOLTO e ri-verificato.** Non era il colpevole — protegge F3,
  non tocca F2. Il vero bug era nel **chunking** (relative fuse «ciò/quello…che» staccate + clausole
  copulari non isolate): corretto in `chunking.py`. Soglia Jaccard parametrizzata
  (`SOGLIA_JACCARD_RESTATEMENT`).
- **Petitio definizionale (es. «X è giusta perché è ciò che la giustizia richiede»): RICLASSIFICATA.**
  È fwd-alta/bwd-bassa → indistinguibile da inferenza one-way → NON rilevabile dal detector strutturale
  senza falsi positivi → è **lato induttivo** (sinonimia semantica). Il test F2 ora usa una petitio
  *simmetrica*; l'asimmetrica è backlog induttivo. Aggiunti casi di contrasto F4/F5 (soggetto lungo).
- **W5/W6 chiusi** (cache helper opt-in `cache_size`/`prune_cache`; `encode([])` dim coerente).
- **O-extraction COSTRUITA** (`resh/obiettivo.py`): `estrai_obiettivo` via LLM (path canonico
  `llm_json` — ASSENTE in questa copia, gira solo in graceful fallback; validata dal vivo su Gemini
  `gemini-2.5-flash`). Opt-in (`obiettivo_llm=True`/`P3_RESH_O_LLM=1`). γ registrato. **Risolve l'esercizio
  §5.1** (estrazione di O).
- **Tipologia attacchi ASPIC+** come tag (`dettaglio.attacco_aspic`: undercut per C₃, undermine per
  entimema) in `sequitur.py`.
- **`integrita_obiettivo`** (`obiettivo.py:valuta_integrita_obiettivo`): O è rappresentazione
  *fallibile* del volere → `eps_resh` pesa la sua incoerenza intrinseca (relazione NLI dichiarato↔latente:
  contraddittorio/disperso/integro). Segnale strutturale, non verdetto. Backward-compat (con O
  deterministico è escluso).

### Chiarimenti concettuali Σ_w (vincolanti, recepiti)
1. **`eps_resh` ≠ epsilon.** resh produce SOLO l'asse **ऋ** (`eps_resh`) di un futuro ε a tre assi
   (Θ teleologico, ऋ critico, ব mnestico). Θ e ব NON esistono. Mai chiamarlo «epsilon» tout court;
   l'aggregazione dei tre è rappresentazione di 2° livello, fuori fase.
2. **Belnap–Dunn / semantica-aggregazione di ε: RIMANDATA.** Serve a reggere la discordanza *tra i tre
   assi* — inutile finché esiste solo ऋ.
3. **O è FALLIBILE** (vedi `integrita_obiettivo` sopra): non un metro sano da assumere.

### Cosa NON è ancora fatto (il vero prossimo fronte)
- **L'arsenale induttivo vero NON è mai stato eseguito.** Esistono solo i *prompt* (Arsenale 3 assi,
  ऋ⁰–ऋ⁹, Trilemma), ora corretti, ma mai fatti girare come chiamate LLM. O-extraction è il loro *input*,
  non l'arsenale. **Questo è il deliverable centrale rimasto.**
- Aperti: **Gate 7** (W7 — `premesse_nli` da frasi a proposizioni); **Gate 8** (inclosure di Priest come
  rilevatore-di-forma, non verdetto). C₃ strumentale/dissimulato e fallacie sospette restano induttivi.

### Come testare ora
`<venv>/python.exe -m resh.tests.run_batterie` (runner combinato, 1 processo: sequitur 7 + fallacie 5 +
integrità 5). `--quick` per il nucleo di non-regressione. Le singole batterie restano invocabili.

### Riferimento completo
Piano dettagliato per-gate + impostazione `integrita_obiettivo`:
`C:\Users\Anton\.claude\plans\inizia-sviluppando-un-piano-shimmering-shell.md`.

*(Le sezioni sotto sono l'handoff originale 2026-06-08: ancora valide per architettura e punti di
aggancio, ma vedi sopra per lo stato superato — in particolare la «PRIMA AZIONE» è già eseguita.)*

---

## ⚠️ PRIMA AZIONE — il file di partenza `prompts_resh.md` è CORROTTO ✅ FATTO (vedi aggiornamento)

Il file da cui parti (`P3 - Antonio Giordano/raw/prompts_resh.md`) ha **errori di elaborazione** di
un'IA precedente. **Correggili PRIMA di costruirci sopra**, usando gli **originali μ** come fonte:

- **Errore critico (riga 11):** «Sei un analizzatore critico **fondazionalista**» → è l'OPPOSTO.
  L'arsenale serve un'epistemologia **NON-fondazionalista** e *decostruisce* la pretesa
  fondazionalista. Nell'originale «Fondazionalista» è il *bersaglio* (la «pretesa fondazionalista»
  che gli assi attaccano), non l'identità dell'analizzatore. → correggere in «**non-fondazionalista**».
- **Incoerenza di voce:** Arsenale + Trilemma in 2ª persona («Sei… Ricevi… Diagnostica»), mentre
  ऋ⁰–ऋ⁹ in 1ª («Ricevo… il mio compito»). Uniformare (la 1ª persona è la maggioranza). La voce NON è
  dettata dagli originali (in voce accademica «noi») → scelta libera, ma deve essere coerente.

**Originali μ (fonti autorevoli — progetto attivo P3):**
- Arsenale → `…\Aleph - 𐤀\{∴} -  Incontro\ऋ\Dubbio\arsenale critico\μ - L'Arsenale Critico per un'Epistemologia Non-Fondazionalista.md`
- Trilemma → `…\Paper\1.5 - Trilemma\μ_Trilemma.md` (modulo canonico v3.0)

Il resto di `prompts_resh.md` (ऋ⁰–ऋ⁹, corni del Trilemma, Note architetturali) è coerente. NB: ऋ⁰
«Attivazione *Fondativa* del Dubbio» — «fondativa» è VOLUTO (il dubbio come funzione fondativa
*non-fondazionale*), non un errore.

---

## 0. Principio architetturale (vincolante)

**Parità di RUOLO, non di assi.** Il deterministico (`resh/`, AI-free) e l'induttivo
(`prompts_resh.md`: Arsenale, ऋ⁰–ऋ⁹, Trilemma) hanno **pari rango**: nessuno alimenta-e-subordina
l'altro. Il deterministico produce **parametri riproducibili di primo rango**; l'induttivo produce
**giudizi**. Un futuro **meta-giudizio** li riconcilia *simmetricamente*. NON si è cercata (e non si
deve cercare) una corrispondenza estetica 1:1 tra i componenti di ε e gli assi ऋ⁰–ऋ⁹.

Conseguenza pratica già rispettata: il deterministico si ferma alla **rilevazione** strutturale; gli
**esercizi difficili** restano induttivi (vedi §5).

---

## 1. Cosa fa oggi il deterministico (in una riga)

Mandi un testo → `resh.analizza(testo)` → `RapportoResh` con **una metrica** `ε_ऋ ∈ (0,1)` +
inventario strutturato (argomenti, premesse, **non-sequitur/C₃**, fallacie, coerenza, bias) +
traccia YAML §6. Pipeline 3 fasi (substrato → 6 branch paralleli → aggregazione ε), 21 γ nel
registro Λ (`lambda_space.py`).

`from resh import analizza, genesi`:
- `r = analizza(testo)` → `r.eps_resh`, `r.componenti_epsilon`, `r.patologie_strutturate`, `r.verifiche`.
- `genesi(r)` → **drill-down**: «una metrica → poi scava». Lista dei 9 componenti ordinati per
  *erosione* di ε (`−wᵢ·log cᵢ`), ciascuno con le patologie-causa allegate.

---

## 2. Punti di aggancio deterministico ↔ induttivo

Dove il lato induttivo si può incrociare con i parametri deterministici (per il meta-giudizio):

| Parametro deterministico | Asse induttivo corrispondente | Come incrociarlo |
|---|---|---|
| `C3_candidato` (sequitur) | **Trilemma C₃** | il deterministico *rileva* «necessità asserita ma non derivata»; l'induttivo *qualifica* C₃ **strumentale vs dissimulato** (la distinzione che richiede lettura pragmatica) |
| `validita_formale` + `NON_SEQUITUR` | **ऋ¹ Infondabilità** (catene → regresso/circolo/dogma) | parametro riproducibile della «catena che non chiude» |
| `assenza_fallacie` + `FALLACIA_LOGICA` | Arsenale / fallacie informali | rilevanza/retorica |
| `genesi(r)` | input strutturato per il meta-giudizio | «dove ε è eroso e perché», pronto da spiegare |
| `bias_autorita` (ad verecundiam) | Arsenale Asse 1 (osservatore) | fonte/autorità |
| **Obiettivo O** | **TUTTI** i prompt induttivi sono O-relativi | ⚠️ vedi §5: O **non** è prodotto dal deterministico |

---

## 3. Cosa è STABILE (verificato end-to-end)

- **Chunking proposizionale** (`chunking.py`): spezza le frasi in clausole via dep-tree Stanza
  (root/conj/advcl/ccomp/acl:relcl/parataxis/csubj); fallback 1-proposizione/frase. Unità più fini
  per arg-mining/sequitur.
- **Validità come entailment** (`sequitur.py`, van Dalen ch01/ch06): `NON_SEQUITUR` quando le
  premesse non derivano la tesi; `C3_candidato` se la tesi reca un modale di necessità non derivato.
  **Dedup per tesi**: una conclusione non-derivata = UN non-sequitur (no doppio conteggio).
- **Discernimento** `validita_formale` (sequitur) vs `assenza_fallacie` (MAFALDA): assi ortogonali,
  componenti ε distinti. ε resta **una** metrica, drillabile con `genesi()`.
- **Test di contrasto**: `python -m resh.tests.test_sequitur_battery` → **7/7 PASS** (sillogismi,
  non-sequitur con/senza C₃, circolarità, entimema valido che NON va flaggato, testo
  non-argomentativo). Protegge la rilevazione da regressioni.
- **Concorrenza**: lazy-load NLI ora con **lock double-checked** (era una race sotto `asyncio.gather`).
- **Degradazione graceful**: `P3_RESH_NLI_DISABLE=1` → sequitur no-op; `P3_RESH_STANZA_DISABLE=1` →
  chunking a frase; nessun crash.
- **ε non collassa più su testi brevi** (vedi §4, W2/W3 stabilizzati).

**Ambiente:** venv `C:\Users\Anton\Desktop\llama.cpp\.venv` (torch+CUDA, transformers,
sentence-transformers, **Stanza** installato il 2026-06-08, deberta-v3-zeroshot NLI, BGE-M3).

---

## 4. Cosa è FRAGILE — caveat di calibrazione (NON fidarsi delle magnitudini assolute)

I **segnali** (rileva/non-rileva) sono solidi; le **magnitudini** no — non ancora tarate su corpus:

- `SOGLIA_ENTAIL = 0.12` (sequitur), `PESO_SEQUITUR = 1.0`, pesi ε (`validita_formale` 0.13,
  `assenza_fallacie` 0.09, …): **scelte, non tarature**. Da ottimizzare su corpus annotato Σ_w.
- **W2/W3 stabilizzati (2026-06-08):** `qualita_sintattica` e `trasparenza_premesse` collassavano a
  ~0 su testi brevi → falso veto su ε. **Fix corretto (esclusione, non valore-tappo):** quando un
  componente **non è misurabile** (n_token<30 / <2 premesse) ritorna `None` ed è **escluso** da ε —
  `epsilon.calcola_epsilon` ripesa i pesi sui presenti (Σ=1) e la traccia §6 espone
  `componenti_esclusi`. *(Un primo tentativo con `0.5` fisso era sbagliato: nella media geometrica
  0.5 NON è neutro, `log 0.5·w` penalizza comunque.)* Effetto: ε su un sillogismo breve valido
  0.16 → 0.67.

### Debolezze NOTE ma NON risolte (per la nuova sessione)
- **W4 — MAFALDA rumoroso → PARZIALMENTE affrontato (2026-06-08, Mosse A+B):**
  - **A (fatto):** le fallacie zero-shot di *rilevanza* (straw_man, ad hominem…) sono ora **SOSPETTE**
    (`dettaglio.confermata=False`): restano nel report (`n_fallacie_sospette`) ma **NON penalizzano ε**.
    Solo le **confermate** (regex + circolarità strutturale) entrano in `assenza_fallacie` → il FP
    `straw_man` non veta più ε.
  - **B (fatto):** `circular_reasoning` rilevato **strutturalmente** (`sequitur.rileva_circolarita`:
    mutuo entailment premessa↔tesi, escludendo premesse condizionali e sovrapposizione lessicale Jaccard).
  - ⚠️ **LOOSE END:** il filtro Jaccard (anti-FP su modus ponens, caso F3) è **applicato ma NON
    ri-verificato** (sessione interrotta). **Ri-eseguire** `python -m resh.tests.test_fallacie_battery`
    — atteso: F1 confermate=0, F2 circolarità=1, **F3 modus ponens circolarità=0**.
  - Il *giudizio autoritativo* sulle fallacie di rilevanza spetta ora all'**induttivo** (Arsenale/assi).
- **W5 — cache illimitata** (`cache.py`): `.cache/resh/` cresce senza cleanup (per design, gestione
  manuale Σ_w).
- **W6 — encoder empty-dim** (`encoder.py`): `encode([])` ritorna dim 384 anche con modello 1024
  caricato (latente, innocuo finché nessuno fa ops dim-specifiche sull'array vuoto).
- **W7 — incoerenza unità**: `premesse_nli.py` opera su **frasi**, mentre arg-mining/sequitur su
  **proposizioni**. Da allineare.

---

## 5. Esercizi DIFFICILI → lato induttivo + ML futuro (NON deterministici)

Decisione di Σ_w: questi restano induttivi, e i **feedback di Σ_w vanno raccolti come dataset** per
un futuro fine-tuning di un LLM piccolo.

1. **Estrazione dell'Obiettivo O.** Tutti i prompt induttivi ricevono `testo φ + O`. Il deterministico
   ha solo `Teleologia.obiettivo_dichiarato = prima frase` (placeholder, `coerenza=0.5`). **O-extraction
   è il primo nodo da risolvere lato induttivo** — ne dipende l'intero arsenale.
2. **Qualifica C₃ strumentale vs dissimulato.** Il deterministico dà `C3_candidato`; distinguere
   l'arresto *dichiarato/provvisorio* (legittimo) dal *dissimulato* (fallimento fondativo) richiede
   lettura pragmatica → induttivo.
3. **Giudizio sulle fallacie di rilevanza (sospette).** Il deterministico declassa straw_man,
   ad hominem, appeal-to-emotion ecc. a **sospette** (non penalizzano ε): le rileva ma non le
   *conferma* (zero-shot inaffidabile). **L'induttivo deve confermarle/scartarle** — è la sua forza
   (pragmatica/retorica). Input: `r.patologie_strutturate` con `dettaglio.confermata=False`.
4. **C₃ nascosto nel condizionale (dal Diario di Σ_w, 31/03/2026).** Ogni `se… allora` stabilizzato
   come legge presume una **chiusura di contesto** *ceteris paribus* non dichiarata (es. «se il ragno
   tesse, la farfalla cade» ignora il secondo ragno a 10 cm). È un **C₃ dissimulato invisibile** (non
   sta nel testo, sta nell'assunzione) → il deterministico non lo vede: l'induttivo (ऋ³/ऋ⁸/Trilemma)
   deve cercare la clausola di chiusura indebita dietro i condizionali normativizzati. *(La faccia
   formale — «negazione dell'antecedente»: «il ragno non ha tessuto → la farfalla non è caduta» — è
   invece STRUTTURALE e potrebbe diventare una «Mossa C» deterministica.)*
5. **Assi senza controparte deterministica** (ऋ² reificazione, ऋ⁴ non-rappresentabilità, ऋ⁵
   contraddizioni produttive, ऋ⁶ genealogia, ऋ⁹ economia): vivono solo lato induttivo. Va bene —
   parità di ruolo, non di assi.

---

## 6. Diagnosi aperta sull'aggregatore ε (ripensamento, parz. eseguito)

Σ_w ha chiesto di non perdere valori informativi. Fatto: discernimento validità/fallacie + `genesi`.
**Resta annotato (non risolto)**, da «smussare mano a mano»:
- ε fonde **generi eterogenei** (logica / coerenza / retorica) in un numero — `qualita_sintattica` è
  un asse di *qualità testuale*, non *argomentativa* (category mix). `genesi` mitiga rendendo
  scavabile il *perché*, ma il numero resta un misto.
- ridondanza parziale `coesione_semantica` / `coerenza_tematica` (locale vs globale).
- `teleologia` placeholder (vedi §5.1).
- Vincolo da rispettare nei refactor: **ε resta UNA metrica** (niente «frastagliature»); ogni
  complessità nel calcolo è accettabile purché *drillabile*.

---

## 7. Cronologia modifiche di questa sessione (2026-06)

1. `sequitur.py` (+ `TipoPatologia.NON_SEQUITUR`, `γ_verifica_sequitur`): validità=entailment.
2. `chunking.py` (+ `Proposizione`, `γ_segmenta_proposizioni`) + offset di carattere su `Word`
   (`annotazione.py`, cache `annota_v2`).
3. `argument_mining.py` opera su proposizioni + fallback inventory per connettivi conclusivi.
4. `core.py`: chunking nel substrato; sequitur in ε; **discernimento** `validita_formale` +
   `assenza_fallacie`; helper **`genesi`**.
5. `epsilon.py`: 8→9 componenti (split di `validita_argomenti` 0.22 → 0.13 + 0.09), Σ=1 invariata.
6. Correzioni da batteria: soglia 0.50→0.12 (no falsi positivi su entimemi), fallback richiede
   connettivo (no falso positivo su testo descrittivo), **dedup per tesi**.
7. **Stabilizzazione:** W1 lock NLI (race); W2/W3 **esclusione** dei componenti non misurabili da ε
   (ripesatura sui presenti + `componenti_esclusi` nella traccia) — niente valore-tappo.
8. Test permanente `resh/tests/test_sequitur_battery.py`. README aggiornato.
9. **W4 Mosse A+B (2026-06-08):** fallacie *confermate vs sospette* (solo le confermate vetano ε);
   circolarità strutturale `sequitur.rileva_circolarita` (+ `γ_rileva_circolarita`); batteria
   `resh/tests/test_fallacie_battery.py`. ⚠️ filtro Jaccard anti-FP modus ponens applicato ma **da
   ri-verificare**. Inoltre: individuata e documentata la **corruzione di `prompts_resh.md`**
   (vedi §PRIMA AZIONE) con gli originali μ.

---

## 8. Come ripartire (comandi)

```powershell
# pipeline su un testo
$env:PYTHONIOENCODING="utf-8"
& "C:\Users\Anton\Desktop\llama.cpp\.venv\Scripts\python.exe" -c "import sys; sys.path.insert(0, r'C:\Users\Anton\Desktop'); from resh import analizza, genesi; r=analizza('...'); print(r.eps_resh); [print(d) for d in genesi(r)]"

# test di non-regressione (deve dare 7/7)
cd C:\Users\Anton\Desktop
& "C:\Users\Anton\Desktop\llama.cpp\.venv\Scripts\python.exe" -m resh.tests.test_sequitur_battery

# test fallacie (Mosse A+B) — RI-VERIFICARE il filtro Jaccard (F3 modus ponens = 0)
& "C:\Users\Anton\Desktop\llama.cpp\.venv\Scripts\python.exe" -m resh.tests.test_fallacie_battery
```

**Regola d'oro per chi continua:** ogni modifica che tocca la *rilevazione* va ri-passata dalla
batteria di contrasto (`test_sequitur_battery.py`); ogni modifica all'aggregazione di ε è libera
(Σ_w: «si può sempre aggiornare») purché ε resti **una metrica drillabile**.
