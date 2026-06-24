"""Batteria di contrasto — non-regressione di sequitur/chunking.

Esegue la pipeline su testi a output noto e verifica che la rilevazione di
non-sequitur resti corretta: **0 falsi positivi**, veri positivi mantenuti.
Costruita da casi reali (validazione 2026-06): copre sillogismi validi,
non-sequitur con/senza necessità (C₃), circolarità, **entimema valido** (caso
trappola: NON va flaggato) e testo non-argomentativo.

Richiede i modelli reali (Stanza + NLI + encoder). Se l'annotazione cade in
fallback (modelli assenti), i casi NLI-dipendenti sono **SALTATI**, non falliti.

Uso:
    <venv>/python.exe -m resh.tests.test_sequitur_battery
    # oppure
    <venv>/python.exe resh/tests/test_sequitur_battery.py
Esce con codice 1 se una regressione è rilevata.
"""

from __future__ import annotations

import os
import sys

# bootstrap path per esecuzione diretta (aggiunge la cartella che contiene `resh/`)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from resh import analizza


# (id, testo, atteso_non_sequitur, atteso_c3, nota)
#   atteso = intero esatto, oppure "ge1" = ">= 1"
CASI = [
    ("T1 sillogismo valido",
     "Tutti gli uomini sono mortali. Socrate e un uomo. Quindi Socrate e mortale.",
     0, 0, "deduzione valida → nessun salto"),
    ("T2 non-sequitur + necessita (C3)",
     "Alcune mie percezioni non dipendono dalla mia volonta. "
     "Deve dunque esistere uno spirito esterno che le produce.",
     1, 1, "il «deve» non derivato = C₃; UNA conclusione = UN NS (dedup per tesi)"),
    ("T3 non-sequitur senza necessita",
     "Ha piovuto tutta la notte. Quindi il governo cadra entro un mese.",
     1, 0, "salto inferenziale senza modale; una conclusione = un NS"),
    ("T4 circolarita / petitio",
     "Questa legge e giusta perche e cio che la giustizia richiede.",
     0, 0, "circolare: entailment ALTO → sequitur non flagga"),
    ("T5 entimema VALIDO",
     "Socrate e un uomo. Quindi Socrate e mortale.",
     0, 0, "premessa maggiore taciuta → NON va flaggato (no falso positivo)"),
    ("T6 testo non-argomentativo",
     "Il cielo era sereno. Gli uccelli volavano basso sopra il fiume.",
     0, 0, "descrittivo: nessun connettivo conclusivo → nessun argomento"),
    ("T7 modus ponens esplicito",
     "Se piove, la strada si bagna. Piove. Dunque la strada si bagna.",
     0, 0, "MP valido → nessun salto"),
]


def _check(val: int, atteso) -> bool:
    if atteso == "ge1":
        return val >= 1
    return val == atteso


def main(casi=CASI) -> int:
    fails, skipped = [], 0
    print("=" * 64)
    print("Batteria di contrasto sequitur — non-regressione")
    print("=" * 64)
    for tid, testo, exp_ns, exp_c3, nota in casi:
        r = analizza(testo, verbose=False)
        y = r.yaml_output
        if y["backend"]["annotazione"] != "stanza":
            print(f"SKIP {tid} — backend fallback (NLI non valutabile)")
            skipped += 1
            continue
        ns = y.get("n_non_sequitur", 0)
        c3 = y.get("n_c3_candidati", 0)
        ok = _check(ns, exp_ns) and _check(c3, exp_c3)
        if not ok:
            fails.append(tid)
        print(f"{'PASS' if ok else 'FAIL'} {tid}: "
              f"NS={ns} (atteso {exp_ns}) | C3={c3} (atteso {exp_c3})  · {nota}")
    print("-" * 64)
    if fails:
        print(f"REGRESSIONE: {len(fails)} caso/i fallito/i → {', '.join(fails)}")
        return 1
    print(f"OK — {len(casi) - skipped} casi verificati, {skipped} saltati (fallback)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
