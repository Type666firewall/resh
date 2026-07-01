"""resh/tests/test_english_fallacie_regex.py — batteria regex fallacie EN.

Bozza v0.1 — copre SOLO il lato regex deterministico (fallacy_patterns_en.json),
zero LLM/NLI/Stanza: gira ovunque, anche senza lo stack pesante. Non sostituisce
un eval reale con gold annotato da Antonio (quello resta un passo successivo,
come da decreto resh sui gold set) — qui si verifica solo che i pattern EN
sparino sui casi per cui sono stati scritti, non che siano calibrati.

Uso: python -m resh.tests.test_english_fallacie_regex  (exit 1 se regressione)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# (id, testo, tipi_fallacia_attesi)
CASI = [
    ("ad_hominem",
     "He is nothing but a liar, so his argument about the budget is worthless.",
     {"ad_hominem"}),
    ("ad_populum",
     "Everyone knows this policy is right, so there is no need to debate it.",
     {"ad_populum"}),
    ("false_dilemma",
     "You are either with us or against us, there is no other option.",
     {"false_dilemma"}),
    ("slippery_slope",
     "If we allow this exception then it will inevitably lead to total chaos.",
     {"slippery_slope"}),
    ("hasty_generalization",
     "All politicians are corrupt, without exception.",
     {"hasty_generalization"}),
    ("appeal_to_emotion",
     "Think of the children — how can we allow this to continue?",
     {"appeal_to_emotion"}),
    ("circular_reasoning",
     "The theory is true because it is true, we know it is correct.",
     {"circular_reasoning"}),
    ("negativo (nessuna fallacia attesa)",
     "The committee published the quarterly report on Tuesday morning.",
     set()),
]


def main() -> int:
    from resh import config
    from resh.gamma.fallacie import _regex_fallacies

    config.LANG.set("en")

    errori: list[str] = []
    for cid, testo, attesi in CASI:
        trovate = {p.dettaglio["fallacia_l2"] for p in _regex_fallacies(testo)}
        if attesi and not attesi & trovate:
            errori.append(f"{cid}: atteso {attesi}, trovato {trovate or '(niente)'}")
        elif not attesi and trovate:
            errori.append(f"{cid}: atteso nessuna fallacia, trovato {trovate}")
        else:
            print(f"  OK    {cid}: {trovate or '(niente)'}")

    if errori:
        for e in errori:
            print(f"  FAIL  {e}")
        print("VERDETTO: REGRESSIONE regex fallacie EN")
        return 1
    print("VERDETTO: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
