# Analisi dei bias di resh — codice e auto-coerenza

> Un tool che diagnostica dogmi nascosti non può permettersi di nasconderne di propri.
> Questa analisi applica a resh l'arsenale che resh applica agli altri.

L'indagine si muove su due assi, come richiesto:

- **A — Bias nel codice**: difetti misurabili nella pipeline deterministica (`ε_ऋ`), là dove
  il numero si forma. Sono correggibili con interventi locali e verificabili.
- **B — Auto-coerenza dell'agente con se stesso**: i punti in cui resh viola i principi che
  esso stesso dichiara e pretende dai testi che analizza. Sono i bias più profondi, perché
  toccano la coerenza tra ciò che resh *dice di essere* e ciò che *fa* quando calcola.

Ogni rilievo cita il punto del codice che lo fonda (parità di ruolo: nessun rilievo senza
ancoraggio) e propone una direzione di correzione, senza imporla.

---

## A — Bias nel codice

### A1. Collinearità: un solo marcatore di superficie erode fino a tre componenti di ε

`epsilon.py` calcola ε come media geometrica pesata e ne vanta l'ortogonalità:
`validita_formale` (entailment) e `assenza_fallacie` (MAFALDA) sono dichiarati «assi
ORTOGONALI» (`epsilon.py:21-24`). Ma sotto la superficie tre componenti reagiscono allo
**stesso** segnale lessicale. Una parola come «evidentemente» / «ovviamente» / «chiaramente»
innesca simultaneamente:

1. **`bias_linguistico`** (peso 0.08) — è un booster (`lessici/booster_it.txt`) →
   `BOOSTER_ECCESSIVO` → `_bias_linguistico_score` (`core.py:529`).
2. **`credibilita_fonte`** (peso 0.07) — `bias_autorita.py:166` sottrae `0.20` alla
   credibilità per `booster_ratio > 0.04`.
3. **`assenza_fallacie`** (peso 0.09) — è il pattern `petitio_principii`
   (`lessici/fallacy_patterns_it.json`) marcato `confermata: True` (vedi A2) → erode ε.

La media geometrica è *zero-sensitive* per costruzione (`epsilon.py:5-8`): colpire tre
componenti con un unico segnale amplifica l'erosione in modo non lineare, e la fa apparire
come tre problemi indipendenti nella *Genesi* del report quando è uno solo. Circa il 24% del
peso totale di ε reagisce a un singolo tratto di superficie.

**Correzione proposta.** Consolidare i marcatori di superficie in *un* canale: o togliere la
penalità di `credibilita_fonte` per hedge/boost (già coperta da `bias_linguistico`), o non
far erodere ε ai `petitio` puramente lessicali (declassarli a candidati, non confermati — vedi
A2). L'obiettivo è che ogni segnale conti una volta sola.

### A2. `confermata: True` incondizionato — anche a confidence 0.45

`core.py:351` fa erodere `assenza_fallacie` **solo** alle fallacie `confermata`; è la stessa
promessa del README: «solo le patologie confermate da più segnali indipendenti sono verdetti;
le altre sono candidate». Ma `fallacie.py:125` imposta `"confermata": True` per **ogni** match
regex, con il commento «regex ad alta precisione» — incluso `petitio_principii`, che il file
lessico stesso etichetta a `confidence: 0.45` (bassa, per sua stessa ammissione).

Il risultato: un *singolo* segnale regex a 0.45 diventa un verdetto che abbassa il numero,
mentre il README garantisce che i verdetti richiedono «più segnali indipendenti». È una
contraddizione codice↔documentazione, ed è un bias sistematico contro la prosa enfatica o
sicura di sé (che usa proprio quei marcatori).

**Correzione proposta.** Sganciare `confermata` dal fatto di *essere* regex e legarlo a una
soglia di confidence, o alla co-occorrenza con un secondo segnale (NLI sulla stessa frase).
I pattern ad alta precisione reale (es. `ad_hominem`, conf 0.65) restano confermati; quelli a
0.4–0.45 diventano candidati visibili ma non eroditori.

### A3. Il lessico dei booster contiene operatori logici

`lessici/booster_it.txt` include «tutti», «nessuno», «sempre», «mai», «necessariamente». Non
sono retorica dell'assolutismo: sono i quantificatori e i modali **costitutivi**
dell'argomentazione formale valida. Un sillogismo categorico corretto — «tutti gli uomini sono
mortali; Socrate è un uomo; dunque necessariamente Socrate è mortale» — è denso di queste
parole. Su un testo breve, `booster_ratio` supera facilmente `0.04` e scatta
`BOOSTER_ECCESSIVO`.

Ne segue una tensione *interna* a ε: `validita_formale` premia il sillogismo valido, mentre
`bias_linguistico` e `credibilita_fonte` lo puniscono per l'uso dei quantificatori che lo
rendono valido. Due componenti dello stesso numero tirano in direzioni opposte sullo stesso
tratto.

**Correzione proposta.** Separare i quantificatori/modali logici dai booster retorici (lista a
parte, peso nullo o condizionato alla posizione retorica e non di premessa). L'omologo inglese
(`booster_en.txt`: «all», «none», «always», «never», «necessarily») ha lo stesso difetto.

### A4. `qualita_sintattica`: ottimi hardcoded tarati su un solo registro

`profilo_linguistico.py:180-185` valuta la qualità sintattica con una «curva ad arco» centrata
su ottimi fissi: profondità albero ≈ 4.5, `subordination_ratio` ≈ 0.6, Gulpease ≈ 55. Sono i
valori della prosa espositiva contemporanea. La prosa filosofica classica a periodi lunghi
(Berkeley, le traduzioni di Kant — cioè esattamente il corpus di `examples/`) ha subordinazione
e profondità alte, e viene penalizzata come «barocca».

Il README dichiara questo *epoch-bias* per `struttura_argomentativa` («risente dello stile
d'epoca», sezione Questioni aperte) ma **non** per `qualita_sintattica`, che soffre dello stesso
difetto in costanti fisse non dichiarate.

In più: il Gulpease è una formula di leggibilità tarata **sull'italiano** (`89 - lettere/parole
*10 + frasi/parole*300`, `profilo_linguistico.py:139`), eppure `qualita_sintattica` la usa con
ottimo 55 **a prescindere dalla lingua**. Sui testi EN il `gulp_score` è quindi
sistematicamente miscalibrato — un caso concreto del «lato EN meno calibrato» che il README
menziona solo in astratto.

**Correzione proposta.** Rendere gli ottimi funzione di lingua/registro, o escludere il Gulpease
dal ramo EN, o dichiarare `qualita_sintattica` inaffidabile sui registri classici (come già si
fa con la soglia `< 30 token → None`).

### A5. `expertise = bool(persone)` — proxy grossolano spacciato per criterio

`bias_autorita.py:159-161`: `expertise` diventa `True` se nel testo compare *un qualunque* nome
proprio di persona — anche il soggetto stesso del testo («Berkeley», «Socrate»), non una fonte
autorevole citata. Il fallback su capitalizzazione (`_persone_da_doc`) è ancora più rumoroso.
È un segnale debole presentato come criterio di autorità.

**Correzione proposta.** O rimuovere `expertise`, o legarlo a un segnale reale (nome + riferimento
bibliografico / citazione), o marcarlo esplicitamente come euristica inaffidabile nel report.

---

## B — Auto-coerenza dell'agente con se stesso

### B1. Il bias centrale: ε *punisce* il dubbio che la filosofia di resh *premia*

È la contraddizione più profonda, ed è verificabile riga per riga.

**Ciò che resh dichiara di essere:**
- Il manifesto (README, «Perché»): resh è «un modo di **organizzare il dubbio perché serva la
  vita**»; l'epigrafe è Cioran sullo scetticismo come «calmante».
- L'assioma `ऋ⁰` (`prompts_resh.md`): il dubbio è «meccanismo attivo», non «difetto da
  eliminare».
- L'assioma `ऋ⁷`: la fallibilità sistemica è una virtù; le affermazioni «definitive» *senza*
  clausole di revisione sono «chiusure epistemiche» da segnalare come patologia.

**Ciò che ε fa:**
- `bias_autorita.py:111-120`: `hedging_ratio > 0.06` genera la patologia `HEDGING_ECCESSIVO`.
- `bias_autorita.py:164`: la credibilità perde `0.15` per lo stesso hedging.
- Le parole penalizzate sono `lessici/hedging_it.txt`: «forse», «sembra», «probabilmente»,
  «potrebbe», «si direbbe», «non è escluso che» — cioè i **marcatori linguistici della
  provvisorietà fallibilista** che `ऋ⁷` loda.

**La contraddizione.** Un testo che marca onestamente la propria incertezza viene *punito dal
numero* per la stessa umiltà epistemica che l'asse `ऋ⁷` *premia* a parole. I due lati di resh
danno verdetti opposti sul marcare il dubbio — e solo ε cambia il numero in testa al report.
Un tool che si presenta come modo di «organizzare il dubbio» scala punti a chi dubita ad alta
voce. Il codice *sa* che boosting e hedging non sono equivalenti — usa soglie diverse (0.04 vs
0.06) — ma poi penalizza comunque entrambi, anziché trarne la conseguenza.

**Correzione proposta.** Asimmetrizzare davvero i due tratti. Il boosting va bene dov'è ora: è
petitio / assolutismo, coerente con la critica ai dogmi. L'hedging **non** è un bias di per sé:
è fallibilismo, coerente con `ऋ⁷`. Andrebbe penalizzato *solo* nella sua forma evasiva
(hedging fitto **insieme** ad assenza di impegno e a beneficio dell'agente — il «weasel», non
la «cautela»), non come tratto lessicale isolato. La distinzione cautela↔evasività è
esattamente quella che l'induttivo sa già fare (cfr. `diagnosi_malafede`): il deterministico la
appiattisce.

### B2. resh non applica a sé il proprio `ऋ⁷`: precisione spuria e auto-esenzione dalla revisione

`ऋ⁷` chiede a *ogni* testo: «applica la stessa fallibilità a se stesso o si esenta dalla
revisione che prescrive ad altri?». Applichiamolo a resh.

Il lato **induttivo** è esemplare: dichiara i propri C₃ strumentali, ammette un possibile C₄
(«affermarlo chiuso sarebbe esso stesso un C₃», `prompts_resh.md`), porta il caveat
auto-applicativo di «termine astratto» (`lessici/termini_astratti_it.json`: «"termine astratto"
è esso stesso astratto → strumento C3 strumentale»). Qui resh *è* coerente.

Il lato **deterministico** no. Il report presenta `ε_ऋ = 0.5524` — quattro decimali — con fasce
categoriche nette (`≥0.85 alta, ≥0.65 media, ≥0.40 bassa`, README). Ma i commenti nel codice
sanno che quei numeri non reggono quella precisione:
- `epsilon.py:53-62`: i pesi sono «PROVVISORIA fino alla calibrazione su 30+ testi annotati
  (TODO)».
- `obiettivo.py:169-170`, `epsilon.py:72`: soglie e pesi sono «scelta, non taratura».

Quattro decimali e fasce secche sono una **precisione spuria**: proiettano una certezza che il
codice stesso dichiara di non avere. È, alla lettera, la «certezza operativa non dichiarata»
che `ऋ⁰` e `ऋ⁷` segnalano come patologia negli *altri* testi. Auto-coerenza parziale:
l'induttivo confessa, il numero no.

**Correzione proposta.** Portare la provvisorietà che vive nei commenti-codice dentro il report
visibile: banda di incertezza su ε (o meno decimali), e una riga esplicita «pesi provvisori,
non ancora calibrati» accanto alle fasce. È ciò che resh pretenderebbe da qualsiasi testo che
espone un numero con quattro cifre.

### B3. La lente non-fondazionalista è un C₃ dichiarato *dentro*, ma non *in testa al report*

resh accusa i testi di dogmi nascosti mentre poggia su una posizione metafisica forte e assunta,
non dimostrata: `ऋ¹` (nessuna conoscenza è giustificabile in assoluto), `ऋ²` (vuoto ontologico
alla Nāgārjuna: niente essenze), `ऋ⁶` (ogni significato è contingente). Sono la lente, non un
risultato.

I prompt lo dichiarano onestamente (fonti `SA{ऋ}` citate, `ऋ⁰⁺` meta-contingente). Ma il README
lo tratta come *rischio dell'LLM* — «i giudizi LLM possono importare un quadro filosofico non
dichiarato» (Questioni aperte) — e non come **postura costitutiva di resh stesso**. Un idealista,
o un fondazionalista, analizzato da resh viene letto con il metro dell'anti-fondazionalismo, e
il report non porta *in testa*, accanto a ε, la dichiarazione «resh legge da questo punto» con la
stessa evidenza con cui pretende che i testi dichiarino il proprio fondamento.

Il README promette che resh «dichiara per primo su che cosa si regge lui». Lo fa a metà: la
lente è dichiarata nei prompt e nei lessici, ma non si propaga all'intestazione di ogni report
come resh esige dai testi.

**Correzione proposta.** Una riga in testa al report, accanto a ε: «Postura di resh: analisi
non-fondazionalista; il framework `SA{ऋ}` è un C₃ strumentale dichiarato, non un fondamento».
Non cambia i numeri; rende resh soggetto alla stessa regola che impone.

---

## Sintesi e priorità

| # | Bias | Asse | Tipo | Correzione |
|---|------|------|------|------------|
| B1 | ε punisce l'hedging (dubbio) che `ऋ⁷` premia | auto-coerenza | contraddizione di principio | asimmetrizzare hedge↔boost; hedging non è bias |
| A1 | un marcatore erode 3 componenti (collinearità) | codice | amplificazione non lineare | consolidare i segnali di superficie in un canale |
| A2 | `confermata: True` per ogni regex, anche a 0.45 | codice | contraddice il README | gate su confidence / co-occorrenza NLI |
| B2 | precisione spuria di ε; auto-esenzione da `ऋ⁷` | auto-coerenza | certezza non dichiarata | banda d'incertezza + nota «pesi provvisori» nel report |
| A3 | quantificatori logici nel lessico booster | codice | tensione interna a ε | separare operatori logici da booster retorici |
| B3 | lente non-fondazionalista non dichiarata nel report | auto-coerenza | dichiarazione a metà | riga di postura in testa al report |
| A4 | ottimi sintattici hardcoded; Gulpease su EN | codice | epoch/lang bias | ottimi per lingua/registro; no Gulpease su EN |
| A5 | `expertise = bool(persone)` | codice | proxy grossolano | legare a segnale reale o marcare inaffidabile |

**Il filo conduttore.** I bias di codice (A) e quelli di auto-coerenza (B) non sono separati: A1,
A3 e B1 sono la stessa cosa vista da angoli diversi — resh ha costruito il lato deterministico
attorno a un'idea di «buona scrittura» (sicura, asciutta, senza esitazioni, senza subordinate)
che è un *registro*, non una virtù epistemica, e che a tratti contraddice la sua stessa filosofia
del dubbio. La correzione più densa è B1: distinguere, nel numero, la cautela dall'assolutismo —
perché è lì che resh, oggi, tradisce se stesso.

Nessuna di queste correzioni è stata applicata: modificano il comportamento di `ε_ऋ` e vanno
decise (quali, con che pesi) e verificate sul corpus di stress prima di toccare la metrica.
Questa analisi le individua e le motiva; l'implementazione è il passo successivo.
