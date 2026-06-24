# 𝒫₃ Agente ऋ (Dubbio) — Report di Analisi
**Documento:** `src_strawman.txt`

## Metriche Globali
- **ε_ऋ:** `0.5521`
- **Densità Logica:** `0.0143` (Fascia: *media*)
- **Modificatore Malafede:** `1.0000`

## Profilo Linguistico (Profiling-UD-style)
- `n_token` = `77`
- `n_frasi` = `5`
- `lunghezza_media_frase` = `15.4`
- `ttr` = `0.7662`
- `mtld` = `92.23`
- `densita_lessicale` = `0.4935`
- `profondita_media_albero` = `1.977`
- `subordination_ratio` = `1.2`
- `lunghezza_media_dip` = `2.278`
- `rapporto_nominale_verbale` = `1.7`
- `gulpease` = `59.0`
- `backend` = `stanza`

## Premesse (Score trasparenza: 0.50)
### Implicite
- scienza descrivere realtà

## Inventario Argomenti (1)
**1. [non classificabile]** quando le sue proposizioni corrispondono ai fatti del mondo

## Coerenza Semantica
- `coesione_locale` = `0.499`
- `coesione_globale` = `0.5061`
- `deriva` = `0.0615`
- `n_segmenti_tematici` = `0`
- `coerenza_tematica_score` = `0.8892`

## Autorità e Bias
- **Fonte:** Una
- **Credibilità:** 0.75

## Componenti ε_ऋ
- `validita_formale` = `1.0000`
- `assenza_fallacie` = `1.0000`
- `struttura_argomentativa` = `0.0909`
- `coesione_semantica` = `0.4990`
- `coerenza_tematica` = `0.8892`
- `qualita_sintattica` = `0.6370`
- `bias_linguistico` = `1.0000`
- `credibilita_fonte` = `0.7500`
- `integrita_obiettivo` = `0.7506`

## Profilo Stilistico (Biber subset IT)
- `n_token` = `76`
- `n_frasi` = `5`
- `pron_1p_per1k` = `13.158`
- `pron_2p_per1k` = `0.0`
- `pron_3p_per1k` = `26.316`
- `modali_per1k` = `0.0`
- `subord_per1k` = `78.947`
- `passivi_per1k` = `0.0`
- `nominaliz_per1k` = `52.632`
- `conn_causali_per1k` = `0.0`
- `conn_avversativi_per1k` = `0.0`
- `conn_concessivi_per1k` = `0.0`
- `rapporto_interrog_dichiar` = `0.0`
- `quotes_per1k` = `0.0`

## ⚠ Patologie
- [obiettivo_disperso] sev=0.25 conf=0.62 — tipo=disperso, fwd=0.0005, bwd=0.0066, label_zero_shot=coerenti, p=0.6235, dichiarato=Definire la scienza come l'unico strumento di accesso a una realtà oggettiva e univoca attraverso la corrispondenza tra teoria e fatti., latente=Affermare l'autorità assoluta di un paradigma epistemologico specifico, delegittimando chiunque sostenga prospettive alternative., qualifica=produttiva (ऋ⁵) o dissimulata = giudizio induttivo


## Quadro ε (det ∥ ind — parità di ruolo, nessuna fusione)

**ε_ऋ = 0.5521** (verbatim dal deterministico — i giudizi induttivi AFFIANCANO, non modulano)

**Provenienza componenti (da Λ, `eps_feeds`):**
| componente | valore | γ alimentanti |
|---|---|---|
| `trasparenza_premesse` | — (escluso) | γ_analizza_premesse |
| `validita_formale` | 1.0000 | γ_rileva_circolarita, γ_verifica_sequitur |
| `assenza_fallacie` | 1.0000 | γ_rileva_circolarita, γ_rileva_fallacie |
| `struttura_argomentativa` | 0.0909 | γ_estrai_argomenti |
| `coesione_semantica` | 0.4990 | γ_analizza_coerenza |
| `coerenza_tematica` | 0.8892 | γ_analizza_coerenza |
| `qualita_sintattica` | 0.6370 | γ_qualita_sintattica |
| `bias_linguistico` | 1.0000 | γ_bias_autorita |
| `credibilita_fonte` | 0.7500 | γ_bias_autorita |
| `integrita_obiettivo` | 0.7506 | γ_valuta_integrita_obiettivo |

**Giudizi a parità (non entrano in ε):**
- `trilemma` [ok]
- `inclosura` [ok]
- `malafede_o` [ok]

**Contributi induttivi:** usati: ['arsenale', 'r0', 'r0p', 'r1', 'r2', 'r3', 'r4', 'r5', 'r6', 'r7', 'r8', 'r9']

## μ-Traccia YAML
```yaml
id_sistema: ऋ-analysis
tipo: Distillato
status: 𝛾
cluster: analisi-critica
metodo: SA{ऋ}-pipeline-deterministic
data: '2026-06-11'
agente: resh
ε_vettore:
  Θ_dogma: null
  ऋ_dubbio: 0.5521
  ב_memoria: null
ε_stato: '>δ'
patologie:
- '[obiettivo_disperso] sev=0.25 conf=0.62 — tipo=disperso, fwd=0.0005, bwd=0.0066,
  label_zero_shot=coerenti, p=0.6235, dichiarato=Definire la scienza come l''unico
  strumento di accesso a una realtà oggettiva e univoca attraverso la corrispondenza
  tra teoria e fatti., latente=Affermare l''autorità assoluta di un paradigma epistemologico
  specifico, delegittimando chiunque sostenga prospettive alternative., qualifica=produttiva
  (ऋ⁵) o dissimulata = giudizio induttivo'
n_premesse_implicite: 1
n_premesse_sospette: 0
n_proposizioni: 11
n_argomenti: 1
n_fallacie: 0
n_fallacie_confermate: 0
n_fallacie_sospette: 0
n_circolarita: 0
n_non_sequitur: 0
n_c3_candidati: 0
densita_logica: 0.0143
fascia_densita: media
malafede_mod: 1.0
obiettivo_dichiarato: Definire la scienza come l'unico strumento di accesso a una
  realtà oggettiva e univoca attraverso la corrispondenza tra teoria e fatti.
obiettivo_latente: Affermare l'autorità assoluta di un paradigma epistemologico specifico,
  delegittimando chiunque sostenga prospettive alternative.
obiettivo_fonte: llm
teleologia_coerenza: 1.0
integrita_obiettivo: 0.7506
integrita_obiettivo_tipo: disperso
fonte_credibilita: 0.75
componenti_epsilon:
  validita_formale: 1.0
  assenza_fallacie: 1.0
  struttura_argomentativa: 0.0909
  coesione_semantica: 0.499
  coerenza_tematica: 0.8892
  qualita_sintattica: 0.637
  bias_linguistico: 1.0
  credibilita_fonte: 0.75
  integrita_obiettivo: 0.7506
componenti_esclusi:
- trasparenza_premesse
pesi_epsilon:
  validita_formale: 0.14130434782608697
  assenza_fallacie: 0.09782608695652173
  struttura_argomentativa: 0.16304347826086957
  coesione_semantica: 0.13043478260869565
  coerenza_tematica: 0.08695652173913043
  qualita_sintattica: 0.10869565217391305
  bias_linguistico: 0.08695652173913043
  credibilita_fonte: 0.07608695652173915
  integrita_obiettivo: 0.10869565217391305
backend:
  annotazione: stanza
  fuzzy: fallback (simpful unavailable)
```