# ऋ (resh) — analisi critico-epistemica di testi

[![Licenza: MIT](https://img.shields.io/badge/licenza-MIT-blue)](LICENSE)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![Testi: IT | EN](https://img.shields.io/badge/testi-IT%20%7C%20EN-green)

> 🇬🇧 English version: [README.en.md](README.en.md)

resh legge un testo (o un intero documento) e risponde a una domanda sola: **quanto regge,
epistemicamente, quello che sto leggendo?** Non dice se è vero o falso — cerca dogmi non
dichiarati, premesse occultate, salti logici, fallacie, circolarità, e un punteggio
riproducibile (`ε_ऋ`) che misura la tenuta strutturale dell'argomentazione.

Un assaggio, dall'esempio reale sull'*Introduzione ai Principi* di Berkeley (`examples/`):

> **ε_ऋ = 0.5524** (tenuta epistemica: bassa) · 19 patologie rilevate
> **Trilemma di Münchhausen:** C3 — arresto dogmatico nascosto, in modalità USE
> *«I candidati pre-rilevati come "è evidente che" e "Si deve credere" [Intro, §3]
> rafforzano l'idea che Berkeley stia facendo uso di assunti non giustificati.»*

Utile se: revisioni tra pari, fact-checking strutturale (non fattuale), analisi di paper
filosofici/teorici, o semplicemente per avere un secondo lettore spietato che non si stanca
mai di controllare se un argomento sta in piedi da solo.

## Perché

Lo scettico parla con senso tanto quanto il dogmatico. L'uno pone per agire — è la forza che
costruisce — ma cade nel peccato di assolutizzare ciò che pone; l'altro mette in guardia da
ideologie e assolutismi, ma lasciato a sé paralizza, fagocitando se stesso se non viene
governato e indirizzato. E ancora si combatte lo scetticismo come se fosse un problema, e non
la manifestazione tangibile che ciò che chiamiamo mondo sfugge a ogni determinazione
definitiva.

resh nasce da qui: è un modo di **organizzare il dubbio perché serva la vita**. Non giudica
la verità — chiede a ogni testo di mostrare su che cosa si regge, e dichiara per primo su che
cosa si regge lui.

> «Lo scetticismo è un calmante, il più sicuro che abbia trovato.» — E. M. Cioran

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
git clone https://github.com/Type666firewall/resh
cd resh
pip install -e .          # installa il package + il comando da terminale `resh`
pip install -e ".[full]"  # come sopra, con lo stack ML completo (stanza, torch, NLI, embedding)
python -c "import stanza; stanza.download('it'); stanza.download('en')"
```

Su GPU NVIDIA conviene installare torch con l'indice CUDA prima dello stack completo:

```bash
pip install --upgrade "torch>=2.6" --index-url https://download.pytorch.org/whl/cu124
```

Senza Stanza/embedding installati il pacchetto degrada gracefully (fallback regex/hash) e lo
dichiara nel report (`backend.eps_degradato=True`) — utile per provare la CLI, non per numeri
confrontabili.

Per il lato induttivo serve una chiave API in `config.py` (vedi sotto sui modelli).

## Uso

```bash
# testo singolo, deterministico (zero LLM)
resh mio_testo.md

# con lato induttivo (arsenale critico completo, ~14 call LLM)
resh mio_testo.md --induttivo

# documento intero, map-reduce, resumable
resh documento paper.md --completo

# inglese — aggiungere --lang su entrambi i comandi
resh my_paper.md --lang en
resh documento my_paper.md --completo --lang en
```

(`python -m resh.cli` resta equivalente a `resh` se si preferisce invocare il modulo.)

Uso come libreria:

```python
from resh import analizza
r = analizza("Everyone knows this policy is inevitable, so it must be supported.", lang="en")
print(r.eps_resh, r.patologie)
```

## Come leggere un report

Il report ha due lati, tenuti separati per costruzione — sapere quale numero viene da dove è
metà della lettura.

**ε_ऋ (il numero, lato deterministico).** Media geometrica pesata dei componenti, tra 0 e 1:
più alto = argomentazione strutturalmente più solida. Misura la *tenuta* (fallacie, salti
logici, premesse occultate, coerenza), **non la verità**: un testo falso può reggere bene, uno
vero può reggere male. Fasce indicative: ≥0.85 alta, ≥0.65 media, ≥0.40 bassa, sotto critica.

**Componenti.** Ognuno tra 0 e 1, e **alto è sempre buono** — anche per i componenti nominati
in negativo: "Assenza fallacie" o "Assenza bias retorico" a 1.0 significano testo pulito. La
*Genesi* riordina i componenti per erosione (quanto ciascuno abbassa ε) e vi allega le
patologie che li causano: è il punto da cui partire per capire *perché* ε è quello che è.

**Patologie.** Ogni rilievo porta `sev` (gravità) e `conf` (fiducia) e la fonte che l'ha
prodotto (`regex`, `nli_zeroshot`, `entailment strutturale`...). Attenzione al campo
`confermata`: solo le patologie confermate da più segnali indipendenti sono verdetti; le
altre sono **candidate** — segnalazioni da verificare a occhio, non condanne.

**Densità premesse implicite.** Quante premesse non dichiarate per token. Metrica descrittiva
(non entra in ε): "bassa" per un testo lungo è un buon segno, non un difetto.

**Lato induttivo (solo con `--induttivo`).** Giudizi LLM *a parità di ruolo*: affiancano il
numero, non lo modificano mai. Include: l'**Obiettivo** dichiarato/latente dell'autore con la
loro coerenza; l'**arsenale critico** (posizione dell'osservatore, autoreferenzialità,
autosufficienza semantica) e gli assi r0-r9; il **Trilemma di Münchhausen** — ogni catena di
giustificazione termina in regresso infinito (C1), circolarità (C2) o arresto dogmatico (C3),
con il *modo*: USE = il testo ci cade, MENTION = ne parla, DIAGNOSIS = lo diagnostica in
altri; l'**inclosura** (schema di Priest) sui limiti del pensiero; la **diagnosi di
malafede** sullo scarto dichiarato↔latente — segnale, mai verdetto.

**Il disaccordo è un dato.** Se il lato deterministico e quello induttivo divergono (es. sul
corno del trilemma), il report **mostra** le divergenze con i passi contesi invece di
riconciliarle: nessuno dei due lati ha l'ultima parola.

**Onestà sui fallimenti.** Ogni call LLM fallita compare come "contributo scartato" con
l'errore: un report con 14 errori dichiarati è un report onesto, non un report rotto.

## Questioni aperte

resh è un progetto in evoluzione, e un tool che diagnostica dogmi nascosti non può
permettersi di nasconderne di propri: le scelte dichiaratamente provvisorie stanno qui.

- **L'inventario delle unità argomentative è rumoroso.** La segmentazione in clausole spezza
  i periodi lunghi — la prosa classica ne soffre più di quella contemporanea — e frammenti o
  subordinate isolate finiscono nell'inventario come "premesse candidate". Per questo ogni
  riga mostra la `conf` del classificatore: sotto ~0.7 va presa come segnalazione debole. In
  valutazione: compattare le unità senza connettivi riconosciuti in un conteggio, lasciando
  il dettaglio nel JSON.
- **`struttura_argomentativa` risente dello stile d'epoca.** Su testi a periodi lunghi il
  valore basso è in parte un artefatto della segmentazione, non un difetto del testo: va
  letto insieme agli altri componenti, non da solo.
- **I giudizi LLM possono importare un quadro filosofico non dichiarato** — per esempio
  leggere un idealista dal metro di un realismo implicito. Mitigazione attuale: i candidati
  del pre-detect deterministico vanno giudicati uno per uno e il rigetto va motivato con
  citazione. Resta una questione aperta di prompt design, e i report vanno letti sapendolo.
- **Il carico non è il conteggio.** La densità di premesse implicite conta le premesse
  nascoste, ma non quanto edificio regge ciascuna: un testo può avere un'unica premessa
  indimostrata che sostiene tutto (il caso Berkeley §3). La metrica di *concentrazione
  fondazionale* è in progetto (`docs/roadmap.md`).
- **Calibrazione quasi tutta italiana.** I gold set annotati sono in gran parte IT; il lato
  EN funziona ma è meno calibrato.

Ogni report registra le versioni esatte dello stack (`backend.ambiente`): i numeri sono
confrontabili solo a parità di stack — e resh evolve.

## Modelli — cosa consigliamo

resh parla con qualunque endpoint OpenAI-compatibile (`config.py`, profili in `PROFILES`).

**Cloud** (comodo, quota limitata): i profili Google AI Studio (`gemini-3.1-lite`,
`gemma-31`) sono un buon default — gratuiti entro quota, qualità di giudizio sufficiente per
l'arsenale critico.

**Alibaba Model Studio** (profilo `alibaba`, default `qwen-plus`): 1M token gratuiti *per
modello* alla registrazione. Servono `DASHSCOPE_API_KEY` e, se il workspace è nella regione
eu-central-1 (Francoforte), anche l'endpoint personale:
`DASHSCOPE_BASE_URL=https://<WorkspaceId>.eu-central-1.maas.aliyuncs.com/compatible-mode/v1`.
Cambiare modello (`P3_LLM_MODEL=qwen-max`, ...) attinge alla quota free di quel modello.

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
├── dataset/trilemma/, dataset/astratti/    gold set annotati per calibrazione ed eval
├── tests/                                  batterie di non-regressione ed eval
├── examples/                               testi ed esempi di report reali
└── curate_dataset.py                       curazione manuale run → dataset per calibrazione futura
```

## Configurazione utile

Tutto via variabili d'ambiente — nessun file da modificare:

- `P3_ACTIVE_PROFILE=<nome>` — profilo LLM attivo (vedi `PROFILES` in `config.py`; default
  `gemma-31`). Es.: `local` per LM Studio, o un profilo cloud.
- `P3_LLM_MODEL` / `P3_LLM_BASE_URL` — override esplicito di modello/endpoint, vincono sul
  profilo attivo. Utile per puntare a qualunque endpoint OpenAI-compatibile senza toccare
  `config.py`.
- `P3_LLM_API_KEY` — chiave API esplicita, vince su qualunque chiave del provider
  (`OPENAI_API_KEY`, `P3_GEMINI_API_KEY`, ...).
- `P3_LLM_TIMEOUT=<secondi>` — timeout per singola call LLM (default: il timeout del profilo
  attivo, 120s a livello client). Da alzare con modelli locali lenti o varianti "thinking";
  da abbassare per fallire-veloce su endpoint instabili. Una call che scade viene tracciata
  come `error` e scartata, non blocca la pipeline.
- `P3_LLM_VERBOSE=1` — log delle call su stderr
- `P3_RESH_CACHE=<dir>` / `P3_RESH_DB=<dir>` — override delle directory cache/DB
- `P3_RESH_CACHE_DISABLE=1` — disattiva la cache dei risultati (ogni run ricalcola da zero)
- `P3_RESH_TRACE_DISABLE=1` — disattiva il trace delle call LLM

## Esempi

`examples/` contiene report **reali e non ritoccati** su testi filosofici veri:

- `report_berkeley_intro_IT_pertesto_qwen-max.md` — Berkeley, *Introduzione ai Principi*
  (trad. it.): analisi per-testo con arsenale induttivo completo.
- `report_ioli_gorgia_IT_documento_qwen-max.md` — R. Ioli, introduzione al Gorgia (Carocci
  2013): modalità documento, map-reduce su 11 chunk.
- `report_zilioli_nihilist_EN_documento_qwen-plus.md` — U. Zilioli, *Nihilist arguments in
  Gorgias and Nāgārjuna*: modalità documento su testo inglese.

I testi sorgente non sono inclusi (diritti degli autori/traduttori): ogni report identifica
il documento con hash sha256, dimensione e riferimento bibliografico.

**I report sono prodotti da versioni via via evolute di resh.** resh cambia — anche grazie
a ciò che questi stessi report hanno rivelato: il filtro del paratesto e il caricamento dei
prompt inglesi, per esempio, nascono da difetti *visibili* in due degli esempi qui sopra, che
li dichiarano in una nota di versione in testa invece di nasconderli. Ogni report registra
data, modello LLM e versioni esatte dello stack (`backend.ambiente`): le differenze di
formato tra esempi sono la storia del progetto, non incuria. Per il quadro dei limiti noti,
vedi «Questioni aperte».
