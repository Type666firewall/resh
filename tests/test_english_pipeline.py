"""resh/tests/test_english_pipeline.py — smoke test pipeline EN, zero LLM, deterministico.

Verifica che passando lang="en" a `analizza()`:
1. Annotazione UD inglese (Stanza/fallback) avvenga con POS tag inglesi.
2. I lessici inglesi vengano caricati correttamente (stilometria).
3. Epsilon e profiling producano risultati coerenti.

Bozza v0.1: è uno SMOKE test (verifica che nulla esploda e che i lessici si
carichino), non un eval di giudizio. Per il decreto resh, l'inglese non è
dichiarato "supportato" solo perché questo passa — vedi anche
test_english_fallacie_regex.py per un primo eval con casi attesi espliciti.

Uso: python -m resh.tests.test_english_pipeline
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def main() -> int:
    from resh import config
    from resh.gamma.annotazione import annota, reset_singleton
    from resh.core import analizza
    from resh.gamma.stilometria import _get_stilo_lex

    print("=" * 60)
    print("BATTERIA: English pipeline deterministic smoke test")
    print("=" * 60)

    errori: list[str] = []

    token = config.LANG.set("en")
    reset_singleton()

    try:
        lex = _get_stilo_lex()
        if "because" not in lex["causali"] and "therefore" not in lex["causali"]:
            errori.append("Lessici causali inglesi non caricati correttamente")
        if "however" not in lex["avversativ"] and "but" not in lex["avversativ"]:
            errori.append("Lessici avversativi inglesi non caricati correttamente")
        if "although" not in lex["concessivi"]:
            errori.append("Lessici concessivi inglesi non caricati correttamente")
        if "i" not in lex["pron_1p"] or "we" not in lex["pron_1p"]:
            errori.append("Pronomi 1P inglesi non caricati correttamente")
        if "you" not in lex["pron_2p"]:
            errori.append("Pronomi 2P inglesi non caricati correttamente")
        if "he" not in lex["pron_3p"] or "they" not in lex["pron_3p"]:
            errori.append("Pronomi 3P inglesi non caricati correttamente")
        if "can" not in lex["modali"] or "must" not in lex["modali"]:
            errori.append("Modali inglesi non caricati correttamente")
    except Exception as exc:
        errori.append(f"Errore durante _get_stilo_lex(): {exc}")

    testo = "We must therefore claim that language is not a representation. Obviously, it is a substrate."
    try:
        doc = annota(testo)
        if not doc.sentences:
            errori.append("Nessuna frase prodotta dall'annotatore inglese")
        if doc.backend == "fallback":
            words = doc.sentences[0].words
            therefore_word = words[2]
            if therefore_word.upos not in {"SCONJ", "CCONJ"}:
                errori.append(f"Fallback POS errato per 'therefore': {therefore_word.upos}")
            repr_word = [w for s in doc.sentences for w in s.words if "representation" in w.text.lower()]
            if repr_word and repr_word[0].upos != "NOUN":
                errori.append(f"Fallback POS errato per 'representation': {repr_word[0].upos}")
    except Exception as exc:
        errori.append(f"Errore durante l'annotazione: {exc}")

    try:
        r = analizza(testo, induttivo_llm=False, verbose=False, lang="en")
        if r.eps_resh is None or r.eps_resh <= 0:
            errori.append(f"Epsilon nullo o negativo: {r.eps_resh}")
        if r.profilo_linguistico.get("n_token", 0) == 0:
            errori.append("Numero token nullo nel profilo stilistico")
    except Exception as exc:
        errori.append(f"Errore durante l'analisi deterministica core: {exc}")

    config.LANG.reset(token)
    reset_singleton()

    if errori:
        for e in errori:
            print(f"  FAIL  {e}")
        print("VERDETTO: REGRESSIONE English pipeline")
        return 1
    print("  OK    Tutti i test deterministici in inglese sono passati.")
    print("VERDETTO: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
