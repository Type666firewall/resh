"""resh/tests/run_pipeline.py — esecuzione e ispezione dell'INTERA pipeline induttiva.

Fa girare `analizza_induttivo` end-to-end su un testo rappresentativo e stampa
ogni sezione (O, Arsenale, tutti gli assi ऋ, Trilemma, sintesi Δε), poi ispeziona
la `trace` per segnalare ogni call che ha «girato a vuoto» (empty/truncated/error).

Obiettivo: verificare la pipeline SENZA intoppi e con output pertinenti — non c'è
gold per gli assi aperti (solo il Trilemma ne ha), quindi qui la validazione è
qualitativa + salute delle chiamate.

Uso:
  python -m resh.tests.run_pipeline [--profile NOME] [--no-sintesi] [--testo-file PATH]
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

from resh import config, induttivo, trace


# Testo rappresentativo: pretesa corrispondentista-isomorfica + autorità + chiusura
# dogmatica → esercita Arsenale (tutti e 3 gli assi), ऋ², ऋ³, ऋ⁴, ऋ⁷, e Trilemma.
_TESTO_DEFAULT = (
    "La scienza descrive la realtà oggettiva esattamente com'è. Una teoria è vera "
    "quando le sue proposizioni corrispondono ai fatti del mondo, e questa "
    "corrispondenza è verificabile da chiunque, indipendentemente dal punto di vista. "
    "Il metodo sperimentale ci dà accesso diretto ai dati, senza mediazioni: i fatti "
    "parlano da sé. Chi nega questo non ha compreso cosa significhi conoscere. "
    "Del resto, è evidente che esista una sola descrizione corretta della natura, "
    "ed è compito della scienza avvicinarvisi progressivamente."
)


def _stampa_dict(titolo: str, d: dict) -> None:
    print(f"\n=== {titolo} ===")
    if not d:
        print("  (vuoto)")
        return
    if "errore" in d:
        print(f"  [ERRORE] {d['errore']}")
        return
    print(json.dumps(d, ensure_ascii=False, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=None)
    ap.add_argument("--no-sintesi", action="store_true")
    ap.add_argument("--testo-file", default=None)
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

    testo = _TESTO_DEFAULT
    if args.testo_file:
        testo = Path(args.testo_file).read_text(encoding="utf-8")

    snap = config.config_snapshot(args.profile)
    print(f"Pipeline induttiva — modello {snap['model']} ({snap['profile']})")
    print(f"Testo ({len(testo)} char): {testo[:120]}…")

    start_ts = datetime.datetime.now().isoformat(timespec="seconds")
    rap = induttivo.analizza_induttivo(
        testo, estrai_o=True, sintesi=not args.no_sintesi, profile=args.profile,
    )
    d = rap.as_dict()

    _stampa_dict("Obiettivo O (agente)", d["obiettivo"] or {})
    _stampa_dict("Arsenale (3 assi + contrasto)", d["arsenale"])
    for gid, out in d["assi"].items():
        _stampa_dict(f"Asse {gid}", out)
    _stampa_dict("Trilemma", d["trilemma"])
    if d["sintesi"]:
        print("\n=== Sintesi Δε ===")
        print(d["sintesi"])
    print(f"\n=== Meta ===\n{d['meta']}")

    # ── salute delle chiamate (SOLO questo run: ts >= start_ts) ────────────────
    anomalie = [r for r in trace.leggi(n=200, solo_anomalie=True)
                if r.get("ts", "") >= start_ts]
    print("\n=== Salute chiamate (trace, solo questo run) ===")
    if not anomalie:
        print("  Nessuna anomalia: tutte le call ok (no empty/truncated/error).")
    else:
        for r in anomalie:
            print(f"  {r['flag']:<9} {r['tag']:<14} {r['model']:<22} "
                  + (r.get('errore') or r.get('out_head', ''))[:90])


if __name__ == "__main__":
    main()
