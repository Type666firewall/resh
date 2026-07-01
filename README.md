# ऋ (resh) — analisi critico-epistemica di testi

resh legge un testo (o un intero documento) e risponde a una domanda sola: **quanto regge,
epistemicamente, quello che sto leggendo?** Non dice se è vero o falso — cerca dogmi non
dichiarati, premesse occultate, salti logici, fallacie, circolarità, e un punteggio
riproducibile (`ε_ऋ`) che misura la tenuta strutturale dell'argomentazione.

Utile se: revisioni tra pari, fact-checking strutturale (non fattuale), analisi di paper
filosofici/teorici, o semplicemente per avere un secondo lettore spietato che non si stanca
mai di controllare se un argomento sta in piedi da solo.

## Come funziona, in breve

resh guarda ogni testo con **due strumenti indipendenti, a pari dignità** — non si fondono
mai in un unico verdetto:

- **Lato deterministico** (zero LLM, sempre riproducibile): annotazione linguistica (Stanza
  UD), NLI, embedding — produce `ε_ऋ`, media geometrica pesata di 10 componenti (fallacie,
  premesse implicite/sospette, coerenza, bias retorico, stilometria, validità logica...).
  Stessi input → stesso numero, sempre.
- **Lato induttivo** (LLM, giudizio): applica un "arsenale critico" di domande — posizione
  dell'osservatore, autoreferenzialità, autosufficienza semantica, disqualificazione del
  dissenso — più una diagnosi del Trilemma di Münchhausen (regresso / circolo / arresto
  dogmatico). Non è un punteggio: è una diagnosi motivata, e se contraddice il lato
  deterministico il disaccordo viene mostrato nel report, non nascosto.

Su un documento intero (`documento` in CLI): pulizia → segmentazione in chunk → estrazione
di un Obiettivo globale → analisi per-chunk (resumable, con budget di call) → aggregazione
finale con sintesi delle variazioni.

Ogni run è tracciato: ogni chiamata LLM viene classificata `ok`/`bad_json`/`error` e mai
inventata — un fallimento del modello produce un contributo scartato e contato, non un dato
silenziosamente assente.

## Installazione

Richiede Python 3.11+.

```bash
pip install -r requirements.txt
pip install --upgrade "torch>=2.6" --index-url https://download.pytorch.org/whl/cu124
python -c "import stanza; stanza.download('it'); stanza.download('en')"
```

Senza Stanza/embedding installati il pacchetto degrada gracefully (fallback regex/hash) e lo
dichiara nel report (`backend.eps_degradato=True`) — utile per provare la CLI, non per numeri
confrontabili.

Per il lato induttivo serve una chiave API in `config.py` (vedi sotto sui modelli).

## Uso

```bash
# testo singolo, deterministico (zero LLM)
python -m resh.cli mio_testo.md

# con lato induttivo (arsenale critico completo, ~14 call LLM)
python -m resh.cli mio_testo.md --induttivo

# documento intero, map-reduce, resumable
python -m resh.cli documento paper.md --completo

# inglese — aggiungere --lang su entrambi i comandi
python -m resh.cli my_paper.md --lang en
python -m resh.cli documento my_paper.md --completo --lang en
```

Uso come libreria:

```python
from resh import analizza
r = analizza("Everyone knows this policy is inevitable, so it must be supported.", lang="en")
print(r.eps_resh, r.patologie)
```

## Modelli — cosa consigliamo

resh parla con qualunque endpoint OpenAI-compatibile (`config.py`, profili in `PROFILES`).

**Cloud** (comodo, quota limitata): i profili Google AI Studio (`gemini-3.1-lite`,
`gemma-31`) sono un buon default — gratuiti entro quota, qualità di giudizio sufficiente per
l'arsenale critico.

**Locale (LM Studio)**: profilo `local`, modello `"auto"` (autodetect di ciò che hai
caricato). Due cose da sapere prima di lanciare:
- **Precarica il modello a mano** in LM Studio prima di lanciare resh. L'autodetect legge lo
  stato reale da `/api/v0/models`, ma un JIT-load automatico su un modello grande può fallire
  per guardrail di memoria.
- **Modelli MoE come Qwen3-30B-A3B**: solo ~3B parametri sono attivi per token (inferenza
  veloce anche su CPU), ma tutti i 30B pesano in memoria — su una GPU consumer con poca VRAM
  serve offload ibrido GPU+CPU in LM Studio, non ci si aspetti di starci tutto in VRAM. Con
  varianti **"Thinking"**, occhio al budget: il blocco di ragionamento può esaurire
  `max_tokens` prima di produrre il JSON di risposta, con contenuto vuoto risultante (fallisce
  "onestamente" — la call viene tracciata e scartata, non inventata, ma è tempo perso).
  Meglio preferire una variante Instruct/non-thinking, o alzare `max_tokens` nel profilo se si
  usa comunque la thinking.

## Struttura

```
resh/
├── core.py, induttivo.py, documento.py   orchestratori (deterministico / induttivo / documento intero)
├── epsilon.py                             ε_ऋ: media geometrica pesata
├── lambda_space.py                        registro dei metodi invocabili + audit a import-time
├── config.py, trace.py                    hub LLM (profili, throttle, classificazione call) + trace
├── persistenza.py                         SQLite append-only, ogni run firmato e ripetibile
├── report.py                              formatter deterministico dei report
├── gamma/                                 moduli di analisi (annotazione, fallacie, bias, stilometria...)
├── lessici/                                lessici curati IT+EN (booster, hedging, connettivi, fallacie...)
├── prompts/                                prompt del lato induttivo (IT + EN), caricati a runtime
├── Trilemma dataset/, Abstract dataset/    gold set annotati per calibrazione ed eval
├── tests/                                  batterie di non-regressione ed eval
├── examples/                               testi ed esempi di report reali
└── curate_dataset.py                       curazione manuale run → dataset per calibrazione futura
```

## Configurazione utile

- `P3_LLM_MODEL` / `P3_LLM_BASE_URL` — override esplicito di modello/endpoint
- `P3_LLM_VERBOSE=1` — log delle call su stderr
- `P3_RESH_CACHE=<dir>` / `P3_RESH_DB=<dir>` — override delle directory cache/DB
- `P3_RESH_TRACE_DISABLE=1` — disattiva il trace delle call LLM

## Esempi

`examples/` contiene testi di prova e i report reali che producono — utile per vedere il
formato di output senza dover lanciare nulla.
