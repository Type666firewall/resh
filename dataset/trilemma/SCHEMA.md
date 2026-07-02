# Schema dataset Trilemma — v1.2

Schema canonico per l'annotazione dei passi rilevanti al Trilemma di Münchhausen nei testi argomentativi. Pensato per essere documento-agnostico: ogni nuovo testo si annota con questi campi, mai con campi ad-hoc.

**Changelog v1.1 → v1.2**: eliminato `C4_proposto`. Le proposte non-trilemmatiche (Apel, Klein, Haack, Williams) sono fenomenologicamente riconducibili ai tre corni: la struttura epistemica (regresso, circolo, arresto) resta identica, cambia solo il giudizio di valore sull'esito — già catturato dal campo `polarita`. `C4` fondeva struttura e giudizio, violando la separazione dello schema. I record ex-C₄ sono riclassificati sotto il corno reale con polarità appropriata (virtuosa/strumentale). §7 estesa con sub-regimi B+, D', D'' (fase 7). §8 invariata.

**Changelog v1.0 → v1.1**: tassonomia §1-§5 invariata. §7 estesa con sub-regimi B+, D', D'' emersi nei documenti di fase 7 (Leibniz, Ioli, Zilioli, Sini). Aggiunta §8 sulla distinzione strutturale tra Trilemma (pattern induttivo) e altre strutture argomentative (tetralemma, élenchos, dilemma eleatico).

## 1. Tassonomia operativa dei corni

### C₁ — Regresso
| Sotto-tipo | Definizione operativa | Marker tipici |
|------------|----------------------|---------------|
| `C1_esplicito` | catena dichiarata che si rimanda all'infinito ("e questo a sua volta...", "all'infinito") | "all'infinito", "ad infinitum", "regresso", "rimanda ancora", "richiede a sua volta", "and so on and so forth", "in a further place" |
| `C1_implicito_catena` | catena di dipendenze epistemiche ≥4 hop senza chiusura, non dichiarata | "presuppone X, che presuppone Y, che..." |
| `C1_ad_verecundiam_concatenato` | appello a autorità che a sua volta cita altra autorità, ≥3 livelli | "X lo dice basandosi su Y che cita Z..." |
| `C1_meta_giustificazione` | giustificazione di principio di giustificazione che richiede a sua volta giustificazione | "perché valutare con X? perché Y. e Y perché Z..." |

### C₂ — Circolarità
| Sotto-tipo | Definizione operativa | Marker tipici |
|------------|----------------------|---------------|
| `C2_viziosa_diretta` | A presuppone B e B presuppone A nello stesso testo | "perché Bibbia dice che" / "perché Dio dice attraverso Bibbia", "circolo vizioso", "pre-comprensione" |
| `C2_viziosa_simmetrica` | il criterio si auto-applica: il criterio X si valuta tramite X stesso | "la verità della corrispondenza è giudicata col criterio della corrispondenza" |
| `C2_costitutiva_apel` | l'atto di negare il principio lo presuppone performativamente (Apel) | "negarlo lo afferma", "élenchos", "performative Selbstbegründung", "altrimenti non si potrebbe dire" |
| `C2_virtuosa_autopoietica` | sistema auto-referenziale che dichiara la propria circolarità come meccanismo generativo | "auto-referenziale", "autopoiesi", "circolarità costitutiva" |

### C₃ — Interruzione dogmatica
| Sotto-tipo | Definizione operativa | Marker tipici |
|------------|----------------------|---------------|
| `C3_dogmatico_nascosto` | asserzione forte senza supporto, presentata come ovvia | "è ovvio", "è evidente", "per definizione", "auto-evidente", "è senz'altro certo", "Eleatic assumption", "dogmatismo", "rovesciato come presupposto" |
| `C3_modale_mascherato` | uso del "deve" / "necessariamente" come ponte non dedotto | "deve esserci", "non può che", "si deve credere", "occorre", "bisognerebbe rinvenire", "would not be", "necessarily" |
| `C3_strumentale_dichiarato` | assioma posto esplicitamente come provvisorio, aperto a revisione | "assumiamo", "poniamo per ipotesi", "per convenzione", "come premessa metodologica", "supremo indizio" |
| `C3_intuizionistico` | appello a facoltà cognitiva che coglie principi (νοῦς, intuizione, Anschauung) | "intuizione immediata", "νοῦς", "principio primo", "evidenza intuitiva", "concetto distinto", "percezione distinta", "aletheia", "manifestatività" |
| `C3_teologico` | arresto a un ente garante (Dio, Spirito, Causa Prima) | "Dio garante", "causa esterna", "spirito che produce", "Causa Sui", "rendergli grazie" |
| `C3_psicologistico` | arresto a evidenza percettiva o sensoriale immediata (Fries) | "conoscenza immediata", "datità percettiva", "evidenza fenomenologica", "giudico senza prova", "immediatamente percepiti dalla mente", "non possono essere comprovati" |

### NONE — Passo senza trilemma
Per casi negativi nel dataset. Necessari per controllo falsi positivi.

### Nota sulla soppressione di C₄ (v1.2)

Le proposte storiche di «uscita dal Trilemma» non costituiscono un quarto corno: sono riformulazioni degli stessi tre esiti con un giudizio di valore invertito. La struttura epistemica (la fenomenologia del gesto) resta identica:

| Proposta | Struttura reale | Sotto-tipo | Polarità |
|----------|----------------|------------|----------|
| Apel (Selbstbegründung trascendentale-pragmatica) | Circolarità performativa: negare il principio lo riafferma | `C2_costitutiva_apel` | `virtuosa` |
| Klein (infinitismo epistemico) | Regresso accettato come processo giustificativo aperto | `C1_esplicito` | `strumentale` |
| Haack (foundherentismo) | Mutuo supporto a cruciverba = circolarità giudicata produttiva | `C2_virtuosa_autopoietica` | `virtuosa` |
| Williams (default-and-challenge) | Entitlement di default = arresto dichiarato come norma del gioco | `C3_strumentale_dichiarato` | `strumentale` |

Il campo `polarita` cattura già la distinzione rilevante (patologica/strumentale/virtuosa). Un corno separato la duplicava, fondendo struttura e giudizio.

---

## 2. Modi (use vs mention)

Distinzione critica per evitare falsi positivi del modulo: un paper *sull'epistemologia del Trilemma* è pieno di marker linguistici dei corni, ma non *cade* nei corni.

| Modo | Definizione |
|------|-------------|
| `USE` | il passo *istanzia* il corno: l'autore-target compie quel gesto epistemico nel testo |
| `MENTION` | il passo *parla del* corno (terminologia, citazione, discussione meta) senza istanziarlo |
| `DIAGNOSIS` | il passo *diagnostica* il corno in un altro autore/posizione, con argomento esplicito |
| `SELF_DIAGNOSIS` | il passo applica il Trilemma a sé stesso (auto-diagnosi del paper) |

Convenzione: per ogni passo l'annotazione deve scegliere **un solo modo dominante**. Se il passo è ambiguo (es. un esempio che è insieme mention e diagnosis), si annota il modo dominante e si segnala l'ambiguità in `note`.

---

## 3. Target

| Categoria | Esempi |
|-----------|--------|
| `autore_paper` | il paper stesso cade (rilevante per SELF_DIAGNOSIS) |
| `autore_target_specifico` | Berkeley, Cartesio, Gorgia, Popper, Aristotele, ecc. |
| `posizione_filosofica` | corrispondentismo, fondazionalismo, induttivismo, ecc. |
| `lettura_interpretativa` | "lettura nichilista", "interpretazione standard", ecc. |
| `none` | per casi MENTION / NONE |

---

## 4. Polarità del corno

| Polarità | Quando |
|----------|--------|
| `patologica` | corno cui il testo cade senza dichiararlo (default per USE) |
| `strumentale` | arresto/regresso/circolo dichiarato esplicitamente come provvisorio e revisionabile |
| `virtuosa` | circolarità o regresso riconosciuti come auto-referenzialità produttiva / processo aperto |
| `selezionata_da_valore` | corno scelto deliberatamente per proteggere un valore antecedente |
| `neutra` | per MENTION / NONE |

---

## 4-bis. Strumento diagnostico parallelo: Schema di Inclosura (Priest)

L'**Inclosura** è uno strumento diagnostico **ortogonale** al Trilemma, non un quarto corno. Identifica pretese di totalità che generano auto-referenzialità strutturale: dato un dominio Ω e una funzione diagonale δ, l'esito δ(Ω) si trova simultaneamente *dentro* Ω (Chiusura) e *fuori* Ω (Trascendenza).

Un passo può istanziare un corno del Trilemma E un'Inclosura simultaneamente. Tipicamente: pretese di totalità (Ω chiaramente identificabile) + arresto dogmatico per gestire l'auto-referenza = INCLOSURA + C₃.

### Sotto-tipi di Inclosura

| Sotto-tipo | Definizione | Marker tipici |
|------------|-------------|---------------|
| `INCL_osservatore` | si afferma una conoscenza della totalità senza posizionamento coerente | "punto di vista di Dio", "totalità del reale", "tutto è X", "sguardo panoramico, panottico" |
| `INCL_auto_referenza` | la teoria T fa parte del dominio U che descrive, ma pretende di esentarsi | "questa teoria descrive tutto", "T ∈ U ma vale per U" |
| `INCL_meta_posizione` | si pretende una posizione meta-teorica che la propria teoria rende impossibile | "tutta la conoscenza è socialmente costruita", "ogni cosa è interpretazione", "lo specchio non rispecchia sé che rispecchia" |
| `INCL_limite_pensiero` | si tenta di pensare/descrivere i limiti del pensiero/dicibile dal di fuori | "oltre i limiti del pensiero", "ineffabile", "indicibile", "tracciare un limite al pensiero", "pensare entrambi i lati del limite" |
| `INCL_classica` | paradossi insiemistici/logici (Russell, Mentitore, Burali-Forti, Cantor) | "insieme di tutti gli insiemi", "Mentitore", "totalità degli ordinali" |

### Polarità dell'Inclosura

| Polarità | Quando |
|----------|--------|
| `patologica_immunizzata` | la teoria neutralizza la propria Inclosura senza elaborarla |
| `patologica_inconsapevole` | la teoria genera Inclosura senza accorgersene (realismo ingenuo, materialismo) |
| `riconosciuta_strumentale` | l'Inclosura è riconosciuta e usata come operatore diagnostico, non come tesi ontologica |
| `dichiarata_e_evitata` | l'autore dichiara il rischio e prende contromisure (apertura del sistema) |

### Modi (riusano la stessa scala USE/MENTION/DIAGNOSIS/SELF_DIAGNOSIS del Trilemma)

---

## 5. Campi del record JSONL

```jsonc
{
  "id": "<doc_id>_<numero_sequenziale_3cifre>",
  "doc": "<basename_file_sorgente>",
  "loc": "<sezione_o_linea>",
  "testo": "<passaggio integrale, max ~5 frasi>",
  "corno": "C1|C2|C3|NONE",
  "sottotipo": "<da tassonomia §1>",
  "modo": "USE|MENTION|DIAGNOSIS|SELF_DIAGNOSIS",
  "target": "<da §3>",
  "polarita": "<da §4>",
  "inclosura": null,                            // null se assente, oppure sotto-oggetto:
  // "inclosura": {
  //   "sottotipo": "<da §4-bis>",
  //   "polarita": "<da §4-bis>",
  //   "modo": "<USE|MENTION|DIAGNOSIS|SELF_DIAGNOSIS>"
  // },
  "marker_linguistico": ["<token o frase chiave>", "..."],
  "confidence_gold": 1.0,
  "note": "<contesto necessario>"
}
```

---

## 6. Regole di annotazione (anti-bias)

1. **Indipendenza dal contenuto filosofico**: due annotatori che disconoscono il contenuto specifico devono poter applicare lo schema solo dai marker linguistici e dal modo. Se per annotare serve sapere chi è Berkeley, è un'annotazione fragile.
2. **Niente over-tagging**: un passo lungo che contiene più corni va spezzato in record separati. Un record = un corno.
3. **Use vs mention prevale su corno**: in caso di dubbio se è USE o MENTION, optare per MENTION (più cauto, meno falsi positivi).
4. **Casi negativi obbligatori**: ogni documento deve contribuire almeno il 30% di record `NONE` per controllare i falsi positivi del modulo.
5. **Confidence_gold < 1.0 documentata**: ogni record con confidence < 1.0 deve avere in `note` la giustificazione dell'inferenza.
6. **Non entrare nel merito della verità degli argomenti** (v1.1): l'annotatore non valuta la fondatezza delle tesi del target. Estrae solo strutture epistemiche. Le tesi interpretative dell'autore-paper si annotano come MENTION/DIAGNOSIS senza prendere posizione.

---

## 7. Aspettative per documento

| Tipo documento | Ratio atteso USE/MENTION/NONE | Note |
|----------------|-------------------------------|------|
| Paper meta-epistemologico (μ_Trilemma) | 5/70/25 | Pieno di MENTION, pochissimi USE — è il test di robustezza più severo |
| Paper filosofico applicativo (v19) | 25/40/35 | Mix bilanciato di DIAGNOSIS e MENTION |
| Saggio argomentativo non-filosofico | 30/5/65 | Pochi MENTION, alcuni USE patologici, molti NONE |
| Testo divulgativo / opinione | 40/0/60 | USE patologico dominante |
| Testo narrativo / fiction | 5/0/95 | Soglia di controllo: dovrebbe essere quasi tutto NONE |

### Regimi epistemici del corpus (v1.1)

```
REGIME A: Testi meta-consapevoli (DIAGNOSIS/MENTION)
REGIME B: Testi-target livello-zero (USE patologici nascosti)
  - B  : Cartesio, Hilbert (USE patologico puro)
  - B+ : Leibniz (USE patologico + SELF_DIAGNOSIS interna del limite)
REGIME C: Testi-target livello-zero (USE strumentali dichiarati)
REGIME D: Testi terziari (DIAGNOSIS sistematica)
  - D  : Albert (enciclopedico-canonico)
  - D' : Ioli, Zilioli (paper accademici filosofici/storici)
  - D'': Sini (lezione orale teoretica trascritta — alta densità DIAGNOSIS continentale)
```

### Provenienza dei testi (v1.3 — dichiarazione di trasparenza)

Non tutti i testi-sorgente dei gold sono opere pubblicate: una parte del corpus è
stata prodotta dall'autore del dataset, da solo o in loop uomo↔IA, come **materiale
di contrasto** deliberatamente ricco di strutture-bersaglio. L'annotazione segue gli
stessi criteri per tutti; la provenienza va però tenuta presente nel leggere le
metriche, perché su testi nati vicino al lessico dei marker il rischio di
circolarità (marker calibrati sugli stessi testi che li validano) è più alto.

| Gold file | Provenienza |
|---|---|
| `gold_arsenale_critico` | sintetico, loop uomo↔IA (testo dell'autore) |
| `gold_v19_gorgia_berkeley` | sintetico, loop uomo↔IA (paper dell'autore) |
| `gold_circolarita_metafisica` | sintetico, loop uomo↔IA (testo dell'autore) |
| `gold_diario_rappresentazione` | ~90% testo umano dell'autore, rifinitura in loop |
| `gold_la_realta` | generato da IA |
| `gold_priest_inclosura` | loop uomo↔IA su idee di Priest (ritenuto conforme dall'annotatore) |
| tutti gli altri | testi pubblicati (Descartes, Hume, Leibniz, Hilbert, Albert, Sini, Ioli, Zilioli, Friedman, trad. Berkeley) |

---

## 8. Strutture argomentative ≠ corni del Trilemma (v1.1)

Distinzione operativa per il modulo, per evitare falsi positivi terminologici:

| Struttura | Natura | Rapporto col Trilemma |
|-----------|--------|------------------------|
| **Trilemma di Agrippa/Sesto** | Pattern induttivo di esaustione dei modi di fallimento giustificativo | È storicamente la stessa struttura del Trilemma di Münchhausen (Albert lo ricalca) |
| **Trilemma di Münchhausen** (Albert) | Formalizzazione moderna del trilemma di Agrippa | Oggetto centrale del dataset |
| **Tetralemma** (catuṣkoṭi) | Strategia confutativa dialettica: nega tutte e 4 le opzioni logiche per ridurre l'avversario all'assurdo | Strumento di confutazione, NON istanza di corno |
| **Élenchos** (Aristotele/Parmenide) | Strategia che mostra che negare la tesi la riafferma performativamente | Coincide con `C2_costitutiva_apel` quando istanziato |
| **Dilemma eleatico** | Esaustione esaustiva di due alternative (è/non-è, uno/molti) | Strumento di confutazione, NON istanza di corno |

Regola: una struttura argomentativa è uno **strumento** che può essere usato per istanziare, confutare o diagnosticare un corno; non è essa stessa un corno. Annotazione `sottotipo` riflette la struttura; `modo` riflette se è USE/MENTION/DIAGNOSIS rispetto al corno.
