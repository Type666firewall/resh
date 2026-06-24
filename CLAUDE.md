# ऋ (resh) — Dubbio

Vale tutto quanto in root `CLAUDE.md`. Qui solo ciò che è specifico di ऋ.
Il README spiega; questo file governa. In caso di conflitto: questo file > README.

## Cosa ऋ è e non è
- Membro Σ-9 della triade: ragiona. Misura quanto un testo regge epistemicamente.
- Due lati a **parità di ruolo**: il deterministico misura (ε_ऋ riproducibile), l'induttivo giudica (diagnosi, MAI un punteggio). Dove guardano lo stesso fenomeno il disaccordo si mostra nel Quadro, non si riconcilia.
- Stato: maturo. Campagna di stabilizzazione CHIUSA (stress F0–F5 2026-06-11, report firmato; falle triaged con Σ_w 2026-06-12; bonifica ADR-005 eseguita).

## Decreti vigenti (violarli = bug, non opinione)
- **Λ vincolante** (Σ_w 2026-06-10): gli orchestratori pescano i metodi SOLO via `resolve(G.NOME)`; un metodo non registrato in `lambda_space.py` è irraggiungibile. Regola self-module: un modulo non risolve un γ che vive in se stesso. Nuovo metodo ⇒ nuova `Gamma` con `eps_role`/`eps_feeds`/`output_kind` dichiarati — l'audit a import-time è il gate.
- **ε mai fuso**: nessun giudizio induttivo modula ε_ऋ. L'aggregatore (`γ_aggrega_quadro`) riporta ε verbatim + giudizi a parità + scartati contati. Vietato reintrodurre modulatori deterministici di ε senza ADR di rifondazione (ADR-005).
- **Prompt solo in `prompts_resh.md`** (caricati a runtime, single source of truth). Vietati prompt inline nel codice.
- **Il dato è canonico, il report è rendering**: zero giudizio del formatter; tutto si rigenera dal DB senza rifare call. Persistenza SQLite append-only con firma Ψ e record di onestà (call, saltati, errori).
- **Call LLM fail-fast**: niente backoff lunghi; ogni tentativo tracciato in `llm_trace.jsonl` (`ok`/`bad_json`/`error`). LLM spento o in errore ⇒ contributo scartato e CONTATO, mai inventato.

## Congelato (con motivo — non riattivare senza ADR)
- Fine-tuning Trilemma (residuo NONE→C₃ non chiudibile a prompt).

## Rimosso (ADR-005, ESEGUITA 2026-06-12 — non reintrodurre senza ADR di rifondazione)
- Modulatore malafede deterministico (era no-op dal 2026-05-20: legame fuzzy densità⇒malafede infondato; la malafede vive come `γ_diagnosi_malafede`, giudizio a parità), `fuzzy_logic.py` (fascia a soglie fisse in core, stesso output), `legacy_llm.py`+`γ_sintesi_llm` (la voce spetta al Gateway Σ-7), `γ_analizza` come entry Λ (resta il wrapper API). Λ_ऋ = 39 γ. Circolarità: `eps_feeds` → solo `assenza_fallacie` (rettifica nell'ADR: il calcolo era già conforme). Tutto in `trash/2026-06-12/resh/`.

## Triage falle F2/M2 (decisioni Σ_w 2026-06-12)
- **Pesi ε ricalibrati**: trasparenza 0.18→0.10, struttura 0.15→0.18 (sanità ordinale ripristinata: S1<S5, S1<S6, S2<S5 sul corpus stress; proposta misurata offline su componenti persistiti). PROVVISORI fino a calibrazione su 30+ testi annotati. **Gli ε pre-2026-06-12 (report stress, Ψ_fb00ac072cb8_D001=0.5147) sono riferimenti storici, non confrontabili coi run successivi.**
- **Prompt Arsenale**: quesito «Squalifica del dissenso» aggiunto (estensione dichiarata, non nel μ-documento fonte) — il lato induttivo nomina la mossa manipolativa che ε non può vedere.
- **Criterio M2 eval inclosura**: FP = `forma=presente ∧ modo=USE` (un negativo riconosciuto MENTION/DIAGNOSIS non è FP — i negativi del gold PARLANO di inclosura). Hardening prompt USE/MENTION severo: eval separato futuro (TODO).

## Verifica (invariante 7 declinato)
- Quattro livelli, mai confusi: **smoke** (cablaggio) ≠ **batterie** (non-regressione, `run_batterie --quick` prima di ogni modifica) ≠ **eval** (capacità vs gold, criteri PRE-dichiarati) ≠ **stress** (comportamento di sistema, corpus congelato sha256 in `tests/corpus_stress/`).
- I gold non si toccano per far passare un eval. Cambiare un criterio (es. M2 inclosura) = decisione di Antonio, registrata.
- Quota: gemma-31 ~1.5K call/giorno, gemini-3.1-lite ~500. Le campagne LLM si lanciano una alla volta (il trace è la finestra di F3: run paralleli la inquinano).

## Ambiente
- venv: `C:\Users\Anton\Desktop\p3_push\.venv\Scripts\python.exe` · `PYTHONPATH=C:\Users\Anton\Desktop\p3_push`.
- **Lanciatori utente** (via d'accesso di Antonio, nel PATH utente): `bin\resh.cmd` = profilo `local` (LM Studio, default `gemma-4-e2b` — Σ_w 2026-06-11: deve girare, qualità dopo; sottocomando `modelli` per lo stato reale) · `bin\resh-google.cmd` = profilo `gemma-31` (Google AI Studio). Non rimuoverli/rinominarli; se la CLI cambia firma, aggiornare lanciatori e README insieme. Le campagne degli agenti scelgono il profilo esplicitamente e non ereditano questi default.
- **Trappola nota LM Studio**: `/v1/models` elenca i modelli SCARICATI, non i caricati — `model="auto"` può pescare un modello spento e il JIT può fallire da guardrail (visto 2026-06-11: 12b-qat rifiutata, ~45 GB stimati col contesto pieno). Preload manuale o `P3_LLM_MODEL` esplicito; lo stato reale è su `/api/v0/models` (`state: loaded/not-loaded`).
- **Trappola budget O** (gemma-4-31b/thinking, verificata 2026-06-16): i modelli con blocco `<thought>` esauriscono il budget nel reasoning prima del JSON → `finish=length`, content vuoto → `ValueError`. Budget minimo sicuro per l'estrazione O: **8192** (fix applicato in `documento._estrai_O()` e `obiettivo._o_via_llm_json()`; allineato a `_call_asse()`).
- **Aperto — frontmatter vault**: `compatta_chunk()` non rimuove il frontmatter YAML del Bibliotecario. File del vault passati a `analizza_documento_induttivo` hanno O estratto dal frontmatter anziché dal corpo. Proposta `separa_frontmatter()` in `pulizia_input.py` + Λ, da approvare Σ_w.
- Pesi ε: `config.toml [resh.epsilon]`. Cache/DB override: `P3_RESH_CACHE`, `P3_RESH_DB`.

## Decisioni che Claude non prende da solo qui
Pesi e componenti di ε (incluso il triage della falla F2: ε premia lo strawman); criteri di accettazione degli eval (M1–M5); modifiche a `prompts_resh.md` che cambiano il giudizio (proposta + eval di conferma, mai silenziose); promozioni nel lessico curato; vocabolari dei dataset gold.
