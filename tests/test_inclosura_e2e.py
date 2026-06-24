"""resh/tests/test_inclosura_e2e.py — test end-to-end BREVE del detector Inclosura.

Fa girare SOLO Arsenale (feed: Primo Asse) + Inclosura su un passo compatto che
*performa* un'inclosura in 1ª persona (totalità del pensabile + dialeteismo
esplicito). Verifica che la macchina pre-detect → LLM → postprocess produca:
  - forma = "presente"   (Trascendenza ∧ Chiusura)
  - modo  = "USE"        (φ la performa, non ne parla)
  - risposta_al_limite = "ACCETTA"  → segnale «immunizzazione»

Due sole call → adatto ai profili a quota bassa (Gemini Flash).

Uso:
  python -m resh.tests.test_inclosura_e2e [--profile gemini-3.1-lite] [--testo-file PATH]
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys

from resh import config, induttivo, trace


# Passo-sonda: Ω = totalità del pensabile; δ = atto di osservarla; trascendenza
# («oltre i limiti») ∧ chiusura («sono dentro»); risposta = ACCETTA (dialeteismo).
_TESTO_SONDA = (
    "Per tracciare i limiti del pensiero devo collocarmi oltre di essi: solo da lì "
    "vedo la totalità di ciò che può essere pensato. Ma io stesso penso mentre lo "
    "dico, e dunque sono dentro quella totalità che pretendo di osservare "
    "dall'esterno. Questa contraddizione non è un errore da dissolvere: è vera, e "
    "la logica deve imparare a contenerla senza esplodere."
)


def _stampa(titolo: str, d) -> None:
    print(f"\n=== {titolo} ===")
    if not d:
        print("  (vuoto)")
        return
    print(json.dumps(d, ensure_ascii=False, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="gemini-3.1-lite")
    ap.add_argument("--testo-file", default=None)
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

    testo = _TESTO_SONDA
    if args.testo_file:
        from pathlib import Path
        testo = Path(args.testo_file).read_text(encoding="utf-8")

    snap = config.config_snapshot(args.profile)
    print(f"Test Inclosura E2E — modello {snap['model']} ({snap['profile']})")
    print(f"Testo ({len(testo)} char): {testo[:110]}…")

    # Pre-detection deterministica (no LLM) — mostrata a parte per chiarezza.
    pre = induttivo.pre_detect_inclosura(testo)
    print("\n=== Pre-detection deterministica (marker INCL) ===")
    if not pre:
        print("  (nessun marker INCL — la sonda è povera di lessico, l'LLM lavora comunque)")
    for h in pre:
        print(f"  {h.corno}/{h.sottotipo}: «{h.span_testo}»")

    start_ts = datetime.datetime.now().isoformat(timespec="seconds")
    rap = induttivo.analizza_induttivo(
        testo, estrai_o=True, sintesi=False, profile=args.profile,
        assi=["arsenale", "inclosura"],
    )
    d = rap.as_dict()

    _stampa("Obiettivo O (agente)", d["obiettivo"] or {})
    _stampa("Arsenale — Primo Asse (Osservatore)", d["arsenale"].get("asse_1_osservatore")
            if isinstance(d["arsenale"], dict) else d["arsenale"])
    _stampa("Inclosura (detector di forma)", d["inclosura"])

    # Verifica esiti attesi.
    incl = d["inclosura"]
    llm = incl.get("llm", {}) if isinstance(incl, dict) else {}
    print("\n=== Esito ===")
    if isinstance(llm, dict) and "errore" in llm:
        print(f"  [ERRORE LLM] {llm['errore']}")
    else:
        print(f"  forma            = {incl.get('forma')}  (atteso: presente)")
        print(f"  modo             = {incl.get('modo')}  (atteso: USE)")
        print(f"  risposta_limite  = {incl.get('risposta_al_limite')}  (atteso: ACCETTA)")
        print(f"  segnale          = {(incl.get('segnale') or '—')[:80]}")

    print(f"\n=== Meta ===\n{d['meta']}")

    anomalie = [r for r in trace.leggi(n=200, solo_anomalie=True)
                if r.get("ts", "") >= start_ts]
    print("\n=== Salute chiamate (trace, solo questo run) ===")
    if not anomalie:
        print("  Nessuna anomalia: call ok (no empty/truncated/error).")
    else:
        for r in anomalie:
            print(f"  {r['flag']:<9} {r['tag']:<14} {r['model']:<22} "
                  + (r.get('errore') or r.get('out_head', ''))[:90])


if __name__ == "__main__":
    main()
