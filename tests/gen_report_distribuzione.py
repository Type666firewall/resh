"""resh/tests/gen_report_distribuzione.py — ricalcola la sezione "Distribuzione
finale" di dataset/trilemma/REPORT.md direttamente dai JSONL (fonte di verità),
invece di tenerla aggiornata a mano nel markdown.

Trovato con questo script (2026-07): i conteggi CORNO/MODO in REPORT.md fase 7.1
combaciano coi JSONL attuali, ma POLARITÀ è già disallineata (neutra: doc dice 66,
reale 73; patologica/strumentale/virtuosa scostate di 1) — esattamente il tipo di
drift silenzioso che il report stesso segnalava come pendente ("aggiornare dopo
verifica sul JSONL" per la riclassificazione ex-C4).

Non riscrive REPORT.md (la parte narrativa/tabellare resta a mano, è materiale
non generabile): stampa il blocco aggiornato da incollare al posto di quello
corrente. Uso: python -m resh.tests.gen_report_distribuzione
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

_DIR = Path(__file__).resolve().parent.parent / "dataset/trilemma"


def _fmt(counter: Counter, totale: int) -> str:
    return "  ".join(f"{k}={v}({v/totale:.0%})" for k, v in counter.most_common())


def main() -> int:
    corno, modo, polarita = Counter(), Counter(), Counter()
    n = 0
    for f in sorted(_DIR.glob("gold_*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            n += 1
            corno[r.get("corno", "?")] += 1
            modo[r.get("modo", "?")] += 1
            polarita[r.get("polarita", "?")] += 1

    print(f"Ricalcolato da {n} record ({len(list(_DIR.glob('gold_*.jsonl')))} file gold_*.jsonl):\n")
    print("```")
    print(f"CORNO:    {_fmt(corno, n)}")
    print(f"MODO:     {_fmt(modo, n)}")
    print(f"POLARITÀ: {_fmt(polarita, n)}")
    print("```")
    return 0


if __name__ == "__main__":
    sys.exit(main())
