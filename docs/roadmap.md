# Roadmap — idee di design in coda

Note di progetto: cose decise ma non ancora implementate, con la motivazione
filosofica che le ha generate. Ordine ≈ priorità.

## 1. Concentrazione fondazionale (metrica nuova)

**Problema.** La densità di premesse implicite conta *quante* premesse non
dichiarate ci sono per token — ma non dice nulla su *quanto carico* regge
ciascuna. Un testo foundationalista pulito (caso di calibrazione: Berkeley,
*Introduzione ai Principi*, §3 «Si deve credere che Dio…») ha pochissime
premesse implicite e deduzioni a valle impeccabili, eppure l'intero edificio
poggia su un'unica garanzia indimostrata: densità di dogma bassa per conteggio,
totale per carico.

**Proposta.** Dal grafo argomentativo già calcolato (legami di entailment
premesse→tesi, gli stessi che producono i NON_SEQUITUR): per ogni premessa non
scaricata, la frazione di conclusioni raggiungibili *solo* passando da lei.
Il massimo è il **carico dogmatico** del testo (Berkeley ≈ 1.0: single point
of failure epistemico). Deterministico, zero LLM.

**Calibrazione.** Berkeley §3 deve uscire ≈ 1.0; un testo a dieci premesse
dubbie che reggono ciascuna un pezzo marginale deve uscire basso.

## 2. Ristrutturazione layout (post-pubblicazione)

La root del repo è il package `resh` (layout flat, mappato via pyproject).
Funziona, ma lo standard moderno è `src/resh/`. Da fare con calma: i test
puntano a `Trilemma dataset/` e `Abstract dataset/` relativamente alla root.
Beneficio solo estetico — non urgente.

## 3. Lessici e gold set EN

I marker trilemma/inclosura hanno pattern EN parziali; il gold set è quasi
tutto IT. Per parità piena delle due lingue servirebbe un gold EN annotato
con gli stessi criteri di SCHEMA.md.
