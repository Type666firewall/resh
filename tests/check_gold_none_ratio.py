"""resh/tests/check_gold_none_ratio.py — verifica la regola 30% NONE minimo sui gold Trilemma.

SCHEMA.md §6 impone un minimo di 30% record `corno=NONE` per gold set, come
anti-bias (evita che il detector si tari solo su testi "positivi"). Nessun
controllo automatico la applicava finora: questo script SEGNALA soltanto le
violazioni, non tocca i JSONL — rietichettare un gold set è una decisione di
Antonio (resh/CLAUDE.md: "vocabolari dei dataset gold" non è delega Claude).

Uso: python -m resh.tests.check_gold_none_ratio [--soglia 0.30]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

_DIR = Path(__file__).resolve().parent.parent / "Trilemma dataset"


def _conta(path: Path) -> Counter:
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return Counter(r.get("corno", "?") for r in recs), len(recs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--soglia", type=float, default=0.30, help="quota minima NONE (default 0.30)")
    args = ap.parse_args(argv)

    violazioni = []
    print(f"{'file':<45} {'n':>4} {'NONE':>5} {'quota':>7}")
    print("-" * 65)
    for path in sorted(_DIR.glob("gold_*.jsonl")):
        conta, n = _conta(path)
        if n == 0:
            continue
        n_none = conta.get("NONE", 0)
        quota = n_none / n
        flag = "  <-- SOTTO SOGLIA" if quota < args.soglia else ""
        print(f"{path.name:<45} {n:>4} {n_none:>5} {quota:>6.1%}{flag}")
        if quota < args.soglia:
            violazioni.append((path.name, quota, n))

    print()
    if violazioni:
        print(f"VERDETTO: {len(violazioni)} gold set sotto la soglia {args.soglia:.0%} NONE "
              f"(SCHEMA.md §6) — solo segnalazione, nessuna modifica applicata:")
        for name, quota, n in violazioni:
            print(f"  - {name}: {quota:.1%} su {n} record")
        return 1
    print("VERDETTO: tutti i gold set rispettano la soglia NONE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
