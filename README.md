# Agente ऋ (resh) — analisi critico-epistemica di testi italiani

## Cosa fa, in due frasi

resh riceve un testo (o un intero paper) e risponde alla domanda: **«quanto regge,
epistemicamente, questo testo?»**. Restituisce un punteggio riproducibile
`ε_ऋ ∈ (0,1)`, un catalogo di patologie argomentative (fallacie, premesse occultate,
salti logici, bias), e una serie di diagnosi critiche di livello superiore
(dogmi fondativi, reificazioni, Trilemma di Münchhausen) — il tutto firmato,
tracciato e ripetibile.

## Come funziona (semplice)

resh ha **due lati con pari dignità**, che guardano lo stesso testo con strumenti diversi:

```
                    testo φ
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
  LATO DETERMINISTICO            LATO INDUTTIVO
  (AI-free, riproducibile)       (LLM, giudizio)
        │                             │
  Stanza UD + NLI + BGE-M3      O (obiettivo dell'agente)
  fallacie · premesse ·         → Arsenale critico
  sequitur · coerenza ·         → assi ऋ⁰⁺–ऋ⁹
  stilometria · bias            → Trilemma + Inclosura
        │                       → termini astratti (Berkeley)
        ▼                             ▼
  ε_ऋ = media geometrica        RapportoInduttivo
  pesata di 10 componenti       (diagnosi, MAI un punteggio)
        └──────────────┬──────────────┘
                       ▼
        confronto det ↔ ind (convergenze/divergenze)
        report markdown firmato Ψ + persistenza SQLite
```

- Il **deterministico** misura: produce numeri identici a ogni run (`ε_ऋ` e i suoi
  10 componenti). Zero LLM.
- L'**induttivo** giudica: ~14 call LLM che applicano l'arsenale critico
  (prompt caricati a runtime da `prompts_resh.md`). Non tocca MAI `ε_ऋ`
  (**parità di ruolo**: nessun lato subordina l'altro; dove guardano lo stesso
  fenomeno — es. Trilemma — il disaccordo viene mostrato, non riconciliato).
- Per i **documenti interi** (`documento.py`): pulizia → chunk → O globale →
  map per-chunk (det+ind, resumable, con budget di call) → reduce
  (`ε_doc` + sintesi Δε del documento).

## Λ_ऋ — la spina dorsale (i core pescano da qui)

Ogni metodo invocabile è registrato come **γ** in `lambda_space.py` (oggi **39 γ**,
dopo la potatura ADR-005 del 2026-06-12: −γ_modulatore_malafede, −γ_sintesi_llm,
−γ_analizza), con metadati: natura (`deterministic`/`llm_chat`/…), area, e il rapporto con ε
(`eps_role`: alimenta un componente / affianca a parità / combina / nessuno;
`eps_feeds`: QUALI componenti alimenta). Un audit a import-time verifica gli
invarianti — se il registry è incoerente, il package non si importa nemmeno.

**Λ è vincolante, non descrittiva** (decisione Σ_w 2026-06-10): gli orchestratori
(`core`, `induttivo`, `documento`, `obiettivo`) pescano i metodi via
`resolve(G.NOME)` — un metodo non registrato in Λ è **irraggiungibile** dai core.
`resolve` è memoizzata; le costanti `G` (G.ANNOTA == "γ_annota") rendono un typo
un errore a import-time. Regola self-module: un modulo non risolve mai un γ che
vive in se stesso (chiamata diretta). Restano import normali solo TIPI, COSTANTI
e l'hub LLM (`config.call_llm_json`), che non sono metodi d'analisi.

L'**aggregatore** (`aggregatore.py`, `γ_aggrega_quadro`) legge `eps_role`/`eps_feeds`
dal registry e produce il **QuadroEpsilon**: ε_ऋ verbatim + provenienza dei
componenti + giudizi induttivi a parità + contributi scartati (binario, contati).
Mai una fusione det+ind in un numero unico. È nel rapporto (`quadro_epsilon`),
sempre calcolato (zero quota), e renderizzato nel report.

## Cosa produce (gli output)

| Output | Cos'è | Dove finisce |
|---|---|---|
| `RapportoResh` | misura per-testo: `ε_ऋ`, componenti, patologie, premesse, argomenti | API / DB |
| `genesi(r)` | genealogia di ε: chi l'ha erosa e perché | API |
| `RapportoInduttivo` | diagnosi LLM: O, arsenale, assi, Trilemma con confronto det↔ind | API / DB |
| `RapportoDocumento` | paper intero: `ε_doc`, per-chunk, sintesi Δε documento | API / DB |
| **Report markdown** | rendering **deterministico** del dato (zero giudizio del formatter), firmato `run_uid` | `report.py` |
| **Persistenza** | SQLite append-only (`db/resh_analyses.db`): ogni run ha firma **Ψ** e record di onestà (call, saltati, errori) | `persistenza.py` |
| Trace LLM | salute di ogni call (`ok`/`bad_json`/`error`) | `.cache/resh/llm_trace.jsonl` |
| Dataset Σ_w | estrazioni O e run induttivi, append-only, per fine-tuning futuri | `.cache/resh/*.jsonl` |

Principio: **il dato è canonico, il report è un rendering** — si rigenera dal DB
in qualsiasi momento, senza rifare nessuna call.

## Uso rapido — i comandi `resh` e `resh-google` (per Antonio)

Due comandi gemelli, stessi argomenti, LLM diverso. Da qualunque terminale, da
qualunque cartella (basta aprirne uno NUOVO la prima volta):

```
resh mio_testo.md                       LOCALE: LM Studio, zero quota
resh-google mio_testo.md                CLOUD:  Google AI Studio, gemma-4-31b (~1500 call/dì)

resh documento paper.md --completo      paper intero (LLM, riprende se interrotto)
resh runs                               elenco dei run salvati
resh report-doc Ψ_xxx_D001 --out r.md   rigenera un report dal database (0 call)
resh modelli                            modelli LM Studio: scaricati e quali in memoria
```

Regola pratica: **`resh` (locale) per provare e lavorare senza limiti; `resh-google`
quando serve qualità di giudizio e c'è quota**. L'analisi semplice (`resh file.md`)
è deterministica e non ha bisogno di nessun LLM. Il locale parte col modello leggero
`gemma-4-e2b` (decisione 2026-06-11: deve girare, la qualità si scala dopo); per
cambiarlo: `resh modelli` per vedere cosa c'è, poi `set P3_LLM_MODEL=<id>`. Se LM
Studio è spento le call falliscono in modo onesto (tracciate), mai inventate.

Si può anche **trascinare un file .md/.txt sull'icona** di `bin\resh.cmd` (o
`bin\resh-google.cmd`): si apre una finestra, gira l'analisi, la finestra resta
aperta per leggere il report.

**Cosa sono i file `.cmd`?** *File batch* di Windows: semplici file di testo
(aprili con un editor e vedi tutto quello che fanno) la cui estensione `.cmd` dice
a Windows di eseguirne le righe come comandi. I nostri fanno solo questo: codifica
UTF-8, `PYTHONPATH` del package, scelta del profilo LLM (`local` o `gemma-31`), e
chiamata al Python del venv con `-m resh.cli`. Nessuna magia: la scorciatoia che
evita di digitare ogni volta le righe del blocco qui sotto. La cartella `bin\` è
registrata nel PATH utente, per questo i comandi funzionano ovunque.

## Uso manuale (agenti / debug)

```powershell
# venv con lo stack completo + package sul path
$env:PYTHONPATH = "C:\Users\Anton\Desktop\p3_push"
$PY = "C:\Users\Anton\Desktop\llama.cpp\.venv\Scripts\python.exe"

# equivalenti espliciti del comando resh
& $PY -m resh.cli mio_testo.md
& $PY -m resh.cli documento paper.md --completo --astratti --budget 100
& $PY -m resh.cli runs
& $PY -m resh.cli report-doc Ψ_fb00ac072cb8_D001 --out report.md

# batteria di stabilità (zero LLM, zero quota): audit Λ + persistenza + detector + batterie
& $PY -m resh.tests.run_batterie --quick
```

```python
from resh import analizza
r = analizza("Tutti sanno che questa politica è inevitabile, quindi va sostenuta.")
print(r.eps_resh, r.patologie)

from resh.induttivo import analizza_induttivo      # lato LLM (brucia quota)
from resh.documento import analizza_documento_induttivo
```

## Mappa della directory

```
resh/
├── README.md                ← questo file (spiega; le norme stanno in CLAUDE.md)
├── CLAUDE.md                ← norme operative ऋ (decreti, congelato, livelli di verifica)
├── prompts_resh.md          ← prompt induttivi, SINGLE SOURCE OF TRUTH (runtime!)
│
│  ORCHESTRAZIONE
├── core.py                  orchestratore deterministico (analizza, genesi)
├── induttivo.py             orchestratore induttivo (arsenale, assi, Trilemma)
├── documento.py             map-reduce su paper interi (resumable, budget)
├── lambda_space.py          Λ_ऋ: registry dei 39 γ + audit invarianti
│
│  LATO DETERMINISTICO (γ)
├── annotazione.py encoder.py profilo_linguistico.py stilometria.py
├── fallacie.py sequitur.py argument_mining.py premesse_nli.py
├── coerenza.py bias_autorita.py _nli.py
├── epsilon.py               ε_ऋ: media geometrica pesata (10 componenti)
│
│  LATO INDUTTIVO (LLM)
├── obiettivo.py             estrazione O (primo nodo induttivo, default OFF)
├── astratti.py              termini astratti alla Berkeley
├── config.py trace.py       hub LLM (profili, throttle, flag bad_json) + trace
│
│  INFRASTRUTTURA
├── persistenza.py           SQLite append-only, firma Ψ, memoria dei run
├── report.py                formatter deterministico (report firmati)
├── cache.py chunking.py chunking_documento.py pulizia_input.py
├── schemas.py cli.py · persistenza in db/
│
│  DATI
├── lessici/                 lessici curati (marker Trilemma, termini astratti…)
├── Trilemma dataset/        234 gold annotati (SCHEMA v1.2, REPORT v7.1)
├── Abstract dataset/        gold termini astratti (SCHEMA v0.1)
├── tests/                   batterie non-regressione + eval + report d'esempio
└── docs/                    fonte teorica (arsenale critico) + archivio storico
```

## Installazione (sintesi)

Python 3.11+, poi:

```powershell
pip install -r resh/requirements.txt
pip install --upgrade "torch>=2.6" --index-url https://download.pytorch.org/whl/cu124
python -c "import stanza; stanza.download('it')"
```

Al primo `analizza()` si scaricano DeBERTa-NLI (~550 MB) e BGE-M3 (~2.4 GB).
Dipendenze opzionali con fallback controllato: `bertopic`, `simpful`.
Per il lato induttivo: chiave API nei profili di `config.py`
(workhorse `gemma-31`, 1.5K call/giorno; `gemini-3.1-lite`, 500/giorno).

## Configurazione essenziale

- Pesi di ε: `config.toml [resh.epsilon]` (default in `epsilon.PESI_DEFAULT`)
- `P3_RESH_O_LLM=1` — estrazione O via LLM nel flusso per-testo (default OFF)
- `P3_RESH_CACHE=<dir>` — override radice cache · `P3_RESH_DB=<dir>` — override dir DB
- `P3_LLM_VERBOSE=1` — log call su stderr
- `P3_RESH_O_DATASET_DISABLE=1` — disattiva il logging dataset Σ_w

## Stato e roadmap

**Fix 2026-06-16 — budget estrazione O**: `documento._estrai_O()` e `obiettivo._o_via_llm_json()` avevano `max_tokens=1500` fisso. I modelli thinking (gemma-4-31b) esaurivano il budget nel blocco `<thought>` prima del JSON → `ValueError`. Fix: `max_tokens=8192` (allineato a `_call_asse()`). Verificato su Provaresh.txt: O corretto, 56 call, ε_doc=0.4489.

**Aperto — frontmatter vault**: `compatta_chunk()` non rimuove il frontmatter YAML del Bibliotecario. Se il file proviene dal vault, O viene estratto dal frontmatter invece che dal corpo del testo. Soluzione proposta (`separa_frontmatter()` in `pulizia_input.py` + Λ) da approvare.

**Attivo ma non ancora misurato:** Inclosura di Priest — il detector di forma
(`pre_detect_inclosura` + call LLM + `_postprocess_inclosura`) gira end-to-end in
`analizza_induttivo` e ha il suo γ in Λ; mancano un dataset gold dedicato e un
`eval_inclosura.py` (oggi le annotazioni `INCL_*` vivono di passaggio nei gold Trilemma).

**Congelato (con motivazione, vedi docstring):** fine-tuning Trilemma (residuo
NONE→C₃ non chiudibile a prompt).

**Rimosso con ADR-005 (eseguita 2026-06-12):** modulatore malafede deterministico
(era no-op dal 2026-05-20: il legame fuzzy densità⇒malafede è infondato — la
malafede vive come γ_diagnosi_malafede, giudizio a parità; VIETATO reintrodurre
modulatori deterministici di ε senza ADR di rifondazione) · `fuzzy_logic.py`
(fascia densità ora a soglie fisse in core, stesso output) · `legacy_llm.py` +
γ_sintesi_llm (la voce narrativa spetta al Gateway Σ-7) · γ_analizza come entry
Λ separata (il wrapper sincrono resta in core come comodità API). Tutto in
`trash/2026-06-12/resh/`.

**Prossimo fronte (Fase 4 parte 2, scelte da ratificare):** aggregatore ε che
legge Λ — `QuadroEpsilon` = ε_ऋ + giudizi induttivi a parità + convergenze,
scarto binario dei contributi `bad_json`, NESSUNA fusione det+ind in un numero unico.

**Storia del progetto:** `docs/archivio/` (HANDOFF del passaggio det→ind,
README precedente con storico bug-fix). Fonte teorica dell'arsenale:
`docs/arsenale_critico_fonte_teorica.md`.
