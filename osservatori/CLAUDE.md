# osservatori — sotto-agente Σ-6 di resh (Dubbio)

Vale tutto quanto in root `CLAUDE.md` e `resh/CLAUDE.md`. Qui solo ciò che è specifico di osservatori.
In caso di conflitto: questo file > README.

## Cosa osservatori è e non è
- Sotto-agente Σ-6 annidato sotto resh: scraping, ricerca, analisi di pattern, monitoraggio ambientale.
- Template ridotto: `core.py` + `lambda_space.py` + `gamma/` — **senza** `epsilon.py` (solo Σ-9).
- Scheletro non ancora popolato: `LAMBDA_OSSERVATORI` è vuoto fino alla definizione dei γ.

## Regole invarianti
- Un metodo in `gamma/` non importa nulla da `prompts/` e non chiama LLM direttamente.
- Un file in `prompts/` non esegue codice.
- `core.py` mantiene la separazione dei layer.
- Ogni nuovo γ va registrato in `lambda_space.py` con `_audit_invariants()` che passa.

## Ambiente
Stesso venv e PYTHONPATH di resh (vedi `resh/CLAUDE.md`).
