# Agente: osservatori
**Grado:** Σ-6  
**Autorità di riferimento:** Dubbio (Scraping, ricerca, analisi di pattern, monitoraggio ambientale)  

## Perimetro $\Lambda$ e Scopo
[Definire qui lo scope limitato e le regole di isolamento dell'agente]

## Struttura Modulo
* gamma/ -> Metodi $\gamma$ deterministici, matematici e idempotenti (No LLM, no chiamate esterne dirette).
* prompts/ -> Prompt di sistema e task specifici in formato .md.
* core.py -> Orchestratore locale: importa i metodi $\gamma$ e applica i prompt.

## Regola Invariante di Sviluppo
Un metodo in gamma/ NON può importare nulla da prompts/. Un file in prompts/ non esegue codice. Il file core.py mantiene la separazione dei layer.
