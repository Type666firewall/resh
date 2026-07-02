"""resh/tests/test_trilemma_predetect.py — batteria pre-detection Trilemma (NO LLM).

Verifica la qualità della pre-detection deterministica (marker regex) sui gold
del dataset Trilemma. Non brucia quota LLM — misura solo la copertura dei marker.

Metriche:
  - RECALL per-corno su record USE: dato un record gold con modo=USE e corno=X,
    almeno un pre-hit ha corno=X?
  - PRECISION su NONE: dato un record gold con corno=NONE, nessun pre-hit?
  - Distribuzione: quanti hit per corno/sottotipo.

Soglie attese (v1, marker iniziali):
  - recall USE ≥ 0.30 (marker lessicali catturano solo i più espliciti)
  - precision NONE ≥ 0.60 (marker non devono sparare su testi non-argomentativi)

Uso:
  python -m resh.tests.test_trilemma_predetect [--verbose]
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import sys
from pathlib import Path

# Permette l'import diretto senza installazione.
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from resh.induttivo import pre_detect_trilemma


_DATASET_DIR = Path(__file__).resolve().parent.parent / "dataset/trilemma"


def _carica_gold() -> list[dict]:
    recs = []
    for f in glob.glob(str(_DATASET_DIR / "gold_*.jsonl")):
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def main(argv: list[str] | None = None) -> None:
    """`argv=[]` per uso da runner (run_batterie): non legge sys.argv globale."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

    recs = _carica_gold()
    print(f"Gold caricati: {recs.__len__()} record\n")

    # Contatori.
    use_tot = use_hit = 0       # recall USE
    none_tot = none_fp = 0      # precision NONE
    mention_tot = mention_fp = 0  # falsi positivi su MENTION
    per_corno_recall = collections.defaultdict(lambda: [0, 0])  # [hit, tot]
    hit_dist = collections.Counter()  # sottotipo dei hit
    errori: list[str] = []

    for r in recs:
        corno_gold = r.get("corno", "NONE").upper()
        modo_gold = r.get("modo", "").upper()
        testo = r.get("testo", "")
        rid = r.get("id", "?")

        hits = pre_detect_trilemma(testo)
        corni_trovati = {h.corno.upper() for h in hits}

        for h in hits:
            hit_dist[h.sottotipo] += 1

        if corno_gold == "NONE":
            none_tot += 1
            if hits:
                none_fp += 1
                if args.verbose:
                    print(f"  FP NONE [{rid}]: {len(hits)} hit → "
                          f"{', '.join(h.sottotipo for h in hits[:3])}")

        elif modo_gold == "USE":
            use_tot += 1
            per_corno_recall[corno_gold][1] += 1
            if corno_gold in corni_trovati:
                use_hit += 1
                per_corno_recall[corno_gold][0] += 1
            else:
                if args.verbose:
                    print(f"  MISS USE [{rid}] gold={corno_gold}: "
                          f"trovati={corni_trovati or '∅'} testo={testo[:80]}…")

        elif modo_gold in ("MENTION", "DIAGNOSIS"):
            mention_tot += 1
            # I marker NON distinguono USE da MENTION — un hit su MENTION non è
            # un falso positivo del marker (che rileva solo presenza lessicale),
            # ma il marker NON dovrebbe essere usato come verdetto USE.
            # Qui contiamo quanti MENTION hanno almeno un hit → informativo.
            if hits:
                mention_fp += 1

    # Stampa risultati.
    print("=" * 60)
    recall_use = use_hit / use_tot if use_tot else 0
    prec_none = 1 - (none_fp / none_tot) if none_tot else 0

    print(f"RECALL USE:      {use_hit}/{use_tot} = {recall_use:.0%}")
    for c in sorted(per_corno_recall):
        h, t = per_corno_recall[c]
        print(f"  {c:<6} {h}/{t} = {h/t:.0%}" if t else f"  {c:<6} -")
    print(f"PRECISION NONE:  {none_tot - none_fp}/{none_tot} = {prec_none:.0%}"
          f"  (FP={none_fp})")
    print(f"MENTION con hit: {mention_fp}/{mention_tot}"
          f" = {mention_fp/mention_tot:.0%}" if mention_tot else "")
    print(f"\nDistribuzione hit (tutti i record):")
    for st, n in hit_dist.most_common():
        print(f"  {st:<35} {n}")

    # Soglie di non-regressione.
    ok = True
    if recall_use < 0.25:
        print(f"\n⚠ RECALL USE sotto soglia 25%: {recall_use:.0%}")
        ok = False
    if prec_none < 0.50:
        print(f"\n⚠ PRECISION NONE sotto soglia 50%: {prec_none:.0%}")
        ok = False
    if ok:
        print("\n✓ Soglie di non-regressione rispettate.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main() or 0)
