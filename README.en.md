# ऋ (resh) — critical-epistemic analysis of texts

[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![Texts: IT | EN](https://img.shields.io/badge/texts-IT%20%7C%20EN-green)

> 🇮🇹 Versione italiana: [README.md](README.md)

resh reads a text (or an entire document) and answers a single question: **how well does
what I'm reading hold up, epistemically?** It does not say whether it is true or false — it
hunts for undeclared dogmas, hidden premises, logical leaps, fallacies, circularity, and
produces a reproducible score (`ε_ऋ`) measuring the structural soundness of the argument.

A taste, from the real example on Berkeley's *Introduction to the Principles* (`examples/`):

> **ε_ऋ = 0.5524** (epistemic soundness: low) · 19 pathologies detected
> **Münchhausen Trilemma:** C3 — hidden dogmatic arrest, in USE mode
> *«Pre-detected candidates such as "it is evident that" and "We should believe" [Intro, §3]
> reinforce the reading that Berkeley is relying on unjustified assumptions.»*

Useful for: peer review, structural (not factual) fact-checking, analysis of
philosophical/theoretical papers, or simply as a merciless second reader that never gets
tired of checking whether an argument stands on its own.

## Why

The sceptic speaks as sensibly as the dogmatist. The one posits in order to act — it is the
force that builds — but falls into the sin of absolutizing what it posits; the other warns
against ideologies and absolutisms, yet left to itself it paralyzes, devouring itself unless
governed and directed. And scepticism is still fought as if it were a problem, rather than
the tangible manifestation that what we call the world escapes any final determination.

resh was born here: it is a way of **organizing doubt so that it serves life**. It does not
judge truth — it asks every text to show what it stands on, and declares, first of all, what
it stands on itself.

> «Scepticism is a sedative — the surest I have found.» — E. M. Cioran

## How it works, in short

resh looks at every text with **two independent instruments, on equal footing** — they are
never merged into a single verdict:

- **Deterministic side** (zero LLM, always reproducible): linguistic annotation (Stanza UD),
  NLI, embeddings — it produces `ε_ऋ`, a weighted geometric mean of 10 components
  (fallacies, implicit/suspect premises, coherence, rhetorical bias, stylometry, logical
  validity...). Same input → same number, always.
- **Inductive side** (LLM, judgment): it applies a "critical arsenal" of questions —
  observer position, self-reference, semantic self-sufficiency, disqualification of
  dissent — plus a diagnosis of the Münchhausen Trilemma (infinite regress / circularity /
  dogmatic arrest). It is not a score: it is a motivated diagnosis, and when it contradicts
  the deterministic side the disagreement is shown in the report, not hidden.

On a whole document (`documento` in the CLI): cleanup → chunk segmentation → extraction of a
global Objective → per-chunk analysis (resumable, with a call budget) → final aggregation
with a synthesis of the variations.

Every run is traced: every LLM call is classified `ok`/`bad_json`/`error` and never made
up — a model failure produces a discarded, counted contribution, not a silently missing
data point.

## Installation

Requires Python 3.11+.

```bash
git clone https://github.com/Type666firewall/resh
cd resh
pip install -e .          # installs the package + the `resh` terminal command
pip install -e ".[full]"  # same, with the full ML stack (stanza, torch, NLI, embeddings)
python -c "import stanza; stanza.download('it'); stanza.download('en')"
```

On an NVIDIA GPU, install torch from the CUDA index before the full stack:

```bash
pip install --upgrade "torch>=2.6" --index-url https://download.pytorch.org/whl/cu124
```

Without Stanza/embeddings installed the package degrades gracefully (regex/hash fallbacks)
and declares it in the report (`backend.eps_degradato=True`) — fine for trying out the CLI,
not for comparable numbers.

The inductive side needs an API key (see the models section below).

## Usage

```bash
# single text, deterministic (zero LLM)
resh my_text.md --lang en

# with the inductive side (full critical arsenal, ~14 LLM calls)
resh my_text.md --induttivo --lang en

# whole document, map-reduce, resumable
resh documento paper.md --completo --lang en

# Italian is the default language — drop --lang for Italian texts
resh mio_testo.md
```

(`python -m resh.cli` is equivalent to `resh` if you prefer invoking the module.)

Library usage:

```python
from resh import analizza
r = analizza("Everyone knows this policy is inevitable, so it must be supported.", lang="en")
print(r.eps_resh, r.patologie)
```

## How to read a report

The report has two sides, kept separate by construction — knowing which number comes from
where is half the reading.

**ε_ऋ (the number, deterministic side).** A weighted geometric mean of the components,
between 0 and 1: higher = structurally more solid argumentation. It measures *soundness of
structure* (fallacies, logical leaps, hidden premises, coherence), **not truth**: a false
text can hold up well, a true one can hold up badly. Indicative bands: ≥0.85 high, ≥0.65
medium, ≥0.40 low, below that critical.

**Components.** Each between 0 and 1, and **high is always good** — including the
negatively-named ones: "Absence of fallacies" or "Absence of rhetorical bias" at 1.0 mean a
clean text. The *Genesis* section reorders components by erosion (how much each one lowers
ε) and attaches the pathologies causing it: start there to understand *why* ε is what it is.

**Pathologies.** Every finding carries `sev` (severity), `conf` (confidence) and the source
that produced it (`regex`, `nli_zeroshot`, structural entailment...). Mind the `confermata`
field: only pathologies confirmed by multiple independent signals are verdicts; the rest are
**candidates** — flags to check by eye, not convictions.

**Implicit-premise density.** How many undeclared premises per token. A descriptive metric
(it does not enter ε): "low" on a long text is a good sign, not a flaw.

**Inductive side (only with `--induttivo`).** LLM judgments *on equal footing*: they sit
beside the number, they never modify it. It includes: the author's declared/latent
**Objective** with their coherence; the **critical arsenal** (observer position,
self-reference, semantic self-sufficiency) and the r0-r9 axes; the **Münchhausen
Trilemma** — every chain of justification ends in infinite regress (C1), circularity (C2) or
dogmatic arrest (C3), with its *mode*: USE = the text falls into it, MENTION = it talks
about it, DIAGNOSIS = it diagnoses it in others; the **inclosure** (Priest's schema) on the
limits of thought; the **bad-faith diagnosis** on the declared↔latent gap — a signal, never
a verdict.

**Disagreement is data.** When the deterministic and inductive sides diverge (e.g. on the
trilemma horn), the report **shows** the divergences with the contested passages instead of
reconciling them: neither side has the last word.

**Honesty about failures.** Every failed LLM call appears as a "discarded contribution" with
its error: a report declaring 14 errors is an honest report, not a broken one.

## Open questions

resh is an evolving project, and a tool that diagnoses hidden dogmas cannot afford to hide
its own: the deliberately provisional choices live here.

- **The inventory of argumentative units is noisy.** Clause segmentation breaks up long
  periods — classical prose suffers more than contemporary writing — and fragments or
  isolated subordinate clauses end up in the inventory as "candidate premises". That is why
  every line shows the classifier's `conf`: below ~0.7, treat it as a weak flag. Under
  evaluation: collapsing units with no recognizable connectives into a count, keeping the
  detail in the JSON.
- **`struttura_argomentativa` is sensitive to period style.** On long-period texts the low
  value is partly a segmentation artifact, not a defect of the text: read it together with
  the other components, never alone.
- **LLM judgments can smuggle in an undeclared philosophical frame** — for instance reading
  an idealist by the yardstick of an implicit realism. Current mitigation: the deterministic
  pre-detect candidates must be adjudicated one by one, and rejecting one must be motivated
  with a citation. It remains an open prompt-design question, and reports should be read
  knowing it.
- **Load is not count.** Implicit-premise density counts hidden premises, but not how much
  of the edifice each one carries: a text can have a single unproven premise holding up
  everything (the Berkeley §3 case). A *foundational concentration* metric is planned
  (`docs/roadmap.md`).
- **Calibration is mostly Italian.** The annotated gold sets are largely IT; the EN side
  works but is less calibrated.

Every report records the exact stack versions (`backend.ambiente`): numbers are comparable
only across identical stacks — and resh evolves.

## Models — what we recommend

resh talks to any OpenAI-compatible endpoint (`config.py`, profiles in `PROFILES`).

**Cloud** (convenient, limited quota): the Google AI Studio profiles (`gemini-3.1-lite`,
`gemma-31`) are a good default — free within quota, judgment quality sufficient for the
critical arsenal.

**Alibaba Model Studio** (profile `alibaba`, default `qwen-plus`): 1M free tokens *per
model* on registration. You need `DASHSCOPE_API_KEY` and, if your workspace is in the
eu-central-1 (Frankfurt) region, your personal endpoint too:
`DASHSCOPE_BASE_URL=https://<WorkspaceId>.eu-central-1.maas.aliyuncs.com/compatible-mode/v1`.
Switching model (`P3_LLM_MODEL=qwen-max`, ...) draws on that model's own free quota.

**Local (LM Studio)**: profile `local`, model `"auto"` (autodetects whatever you have
loaded). Two things to know before launching:
- **Preload the model manually** in LM Studio before launching resh. Autodetect reads the
  real state from `/api/v0/models`, but an automatic JIT-load of a large model can fail on
  memory guardrails.
- **MoE models like Qwen3-30B-A3B**: only ~3B parameters are active per token (fast
  inference even on CPU), but all 30B weigh on memory — on a consumer GPU with little VRAM
  you need hybrid GPU+CPU offload in LM Studio; don't expect it all to fit in VRAM. With
  **"Thinking"** variants, watch the budget: the reasoning block can exhaust `max_tokens`
  before producing the answer JSON, yielding empty content (it fails "honestly" — the call
  is traced and discarded, not made up, but it's wasted time). Prefer an
  Instruct/non-thinking variant, or raise `max_tokens` in the profile if you use a thinking
  one anyway.

## Structure

```
resh/
├── core.py, induttivo.py, documento.py   orchestrators (deterministic / inductive / whole document)
├── epsilon.py                             ε_ऋ: weighted geometric mean
├── lambda_space.py                        registry of invocable methods + import-time audit
├── config.py, trace.py                    LLM hub (profiles, throttle, call classification) + trace
├── persistenza.py                         append-only SQLite, every run signed and repeatable
├── report.py                              deterministic report formatter
├── gamma/                                 analysis modules (annotation, fallacies, bias, stylometry...)
├── lessici/                                curated IT+EN lexicons (boosters, hedging, connectives, fallacies...)
├── dataset/trilemma/, dataset/astratti/    annotated gold sets for calibration and eval
├── tests/                                  non-regression batteries and evals
├── examples/                               sample texts and the real reports they produce
└── curate_dataset.py                       manual run curation → dataset for future calibration
```

## Useful configuration

Everything via environment variables — no file to edit:

- `P3_ACTIVE_PROFILE=<name>` — active LLM profile (see `PROFILES` in `config.py`; default
  `gemma-31`). E.g. `local` for LM Studio, or a cloud profile.
- `P3_LLM_MODEL` / `P3_LLM_BASE_URL` — explicit model/endpoint override, wins over the
  active profile. Useful to point at any OpenAI-compatible endpoint without touching
  `config.py`.
- `P3_LLM_API_KEY` — explicit API key, wins over any provider key (`OPENAI_API_KEY`,
  `P3_GEMINI_API_KEY`, ...).
- `P3_LLM_TIMEOUT=<seconds>` — per-call LLM timeout (default: the active profile's timeout,
  120s at client level). Raise it for slow local models or "thinking" variants; lower it to
  fail fast on unstable endpoints. A timed-out call is traced as `error` and discarded, it
  does not block the pipeline.
- `P3_LLM_VERBOSE=1` — log calls to stderr
- `P3_RESH_CACHE=<dir>` / `P3_RESH_DB=<dir>` — override the cache/DB directories
- `P3_RESH_CACHE_DISABLE=1` — disable the result cache (every run recomputes from scratch)
- `P3_RESH_TRACE_DISABLE=1` — disable LLM call tracing

## Examples

`examples/` contains **real, untouched reports** on actual philosophical texts:

- `report_berkeley_intro_IT_pertesto_qwen-max.md` — Berkeley, *Introduction to the
  Principles* (It. transl.): per-text analysis with the full inductive arsenal.
- `report_ioli_gorgia_IT_documento_qwen-max.md` — R. Ioli, introduction to Gorgias (Carocci
  2013): document mode, map-reduce over 11 chunks.
- `report_zilioli_nihilist_EN_documento_qwen-plus.md` — U. Zilioli, *Nihilist arguments in
  Gorgias and Nāgārjuna*: document mode on an English text.

Source texts are not included (authors'/translators' rights): every report identifies its
document by sha256 hash, size and bibliographic reference.

**The reports were produced by progressively evolving versions of resh.** resh changes —
partly thanks to what these very reports revealed: the paratext filter and the English
prompt loading, for instance, were born from defects *visible* in two of the examples above,
which declare them in a version note at the top instead of hiding them. Every report records
its date, LLM model and exact stack versions (`backend.ambiente`): format differences between
examples are the project's history, not carelessness. For the map of known limits, see
"Open questions".
