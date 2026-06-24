# Schema dataset Termini Astratti — v0.1 (BOZZA, da vagliare Σ_w)

Schema per annotare i **termini astratti** di un testo e il **tipo di occultamento** che vi si cela,
alla luce della critica berkeleyana delle idee astratte (Treatise, Introd. §§7-25). Documento-agnostico:
ogni testo si annota con questi campi, mai con campi ad-hoc. Gemello del dataset Trilemma.

**Tesi.** Un termine generale che pretende di nominare una cosa *determinata* senza contenuto
particolare/ostensibile è il luogo dove si nascondono **stipulazioni normative** e **positi metafisici**.
Il detector deterministico (`induttivo.pre_detect_abstract`) surface i *candidati* (presenza
morfologica/lessicale); l'annotazione gold dà il **verdetto** sul tipo di occultamento.

## 1. Unità di annotazione
Un record = **un termine** (lemma) come usato in φ rispetto all'Obiettivo O. Occorrenze multiple dello
stesso termine con lo **stesso** ruolo = un record (campo `occorrenze`); se il ruolo cambia, record separati.

## 2. Tassonomia dell'occultamento (= `lessici/termini_astratti_it.json:tassonomia_occultamento`, AGGIORNABILE)
| tipo | quando |
|------|--------|
| `contenuto_determinato`    | il termine ha referente particolare/ostensibile → **non** è astrazione illusoria (classe negativa, anti-falso-positivo) |
| `stipulazione_normativa`   | si dissolve in una definizione che *prescrive* ("X è ciò che deve…", criterio posto come ovvio) |
| `posito_metafisico`        | nomina un'entità *assunta esistente* senza contenuto ostensibile |
| `ostensione_forma_di_vita` | la catena definitoria finisce in gesto ostensivo / uso condiviso (Berkeley→Wittgenstein) |

La tassonomia è **dato espandibile**: nuovi tipi si aggiungono nel JSON, non nel codice.

## 3. Relazione a O
`relativo_a_O`: `centrale` (il termine regge l'obiettivo dell'agente) | `periferico` | `none`.
Gli assi induttivi (ऋ²/ऋ⁴/ऋ⁶ + Asse 3) interrogano per primi i termini **centrali**.

## 4. Campi del record JSONL
```jsonc
{
  "id": "<doc_id>_<seq3>",
  "doc": "<basename sorgente>",
  "loc": "<frase o riferimento>",
  "termine": "<lemma minuscolo>",
  "contesto": "<frase in cui appare, max ~2 frasi>",
  "fonte_candidato": "suffisso|lessico|llm",   // come è stato surfacato (presenza)
  "occultamento": "<da §2>",                    // il VERDETTO
  "relativo_a_O": "centrale|periferico|none",
  "occorrenze": 1,
  "confidence_gold": 0.7,                        // <1.0 = bozza da vagliare, motivare in note
  "note": "<ragione dell'annotazione / contesto>",
  "feedback_sigma_w": null                       // riservato alla correzione di Σ_w
}
```

## 5. Regole (anti-bias)
1. **Presenza ≠ verdetto**: un candidato del detector può essere `contenuto_determinato` (termine sano). I casi negativi sono obbligatori per controllare i falsi positivi del detector.
2. **Dal testo, non dalla biografia**: annotare dall'uso del termine in φ, non da ciò che si sa dell'autore.
3. **Nel dubbio, classe meno impegnativa**: tra `contenuto_determinato` e un occultamento, in caso di dubbio preferire `contenuto_determinato` (cauto, meno falsi positivi) — analogo alla regola USE→MENTION del Trilemma.
4. **`confidence_gold` < 1.0 motivata** in `note`.
5. **Auto-applicazione**: «termine astratto» è esso stesso astratto → strumento operativo (C₃ strumentale), non verità.

## 6. Stato
v0.1 = **seed di bozza** (`gold_strawman.jsonl`). Σ_w vaglia/corregge → confidence_gold→1.0 e il
dataset cresce (anche via `induttivo.promuovi_termine` per arricchire il lessico dei candidati).
