"""Batteria di contrasto — fallacie: confermate vs sospette, circolarità.

Verifica le mosse A+B (2026-06):
- A: le fallacie zero-shot di rilevanza sono SOSPETTE (nel report, non vetano ε);
     solo le CONFERMATE (regex + circolarità strutturale) penalizzano `assenza_fallacie`.
- B: la circolarità (petitio) è rilevata STRUTTURALMENTE (mutuo entailment premessa↔tesi).

Principio Σ_w: «nessuna fallacia» (verificato) ≠ «non rilevabili» (sospette/induttivo).

Richiede i modelli reali (Stanza + NLI). Backend fallback → casi SALTATI.
Uso: `<venv>/python.exe -m resh.tests.test_fallacie_battery`  (exit 1 se regressione).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from resh import analizza


# (id, testo, atteso_circolarita, atteso_confermate, nota)
#   atteso = intero esatto oppure "ge1"
CASI = [
    ("F1 sillogismo valido",
     "Tutti gli uomini sono mortali. Socrate è un uomo. Quindi Socrate è mortale.",
     0, 0, "valido: nessun circolo; eventuale straw_man è SOSPETTO → 0 confermate"),
    # NB input ACCENTATO: l'italiano reale ha gli accenti; «e»/«è» senza accento è
    # ambiguo (congiunzione vs copula) e Stanza mis-parsa, impedendo lo split
    # tesi|premessa della petitio. Il test riflette l'input di produzione.
    #
    # F2 è una petitio SIMMETRICA (vera↔corretta sinonimi): il detector strutturale
    # a mutuo entailment la cattura (entrambe le direzioni ≥ SOGLIA_CIRCOLARITA).
    # Esercita anche i fix 2026-06: chunking che isola la subordinata copulare
    # «perché è corretta» (clausola copulare non verbale) + ricostruzione del
    # soggetto ellittico per il confronto NLI («Questa tesi è corretta»).
    # NB: la petitio DEFINIZIONALE asimmetrica («X è giusta perché è ciò che la
    # giustizia richiede») è fwd-alta/bwd-bassa → indistinguibile da un'inferenza
    # one-way: NON è strutturalmente rilevabile (sarebbe falso positivo sulle
    # inferenze valide). È un caso del lato INDUTTIVO (sinonimia semantica) — vedi
    # piano §A8, parità di ruolo.
    ("F2 circolarita / petitio",
     "Questa tesi è vera perché è corretta.",
     "ge1", "ge1", "petitio simmetrica: mutuo entailment premessa↔tesi → circular_reasoning CONFERMATO"),
    ("F3 modus ponens valido",
     "Se piove, la strada si bagna. Piove. Dunque la strada si bagna.",
     0, 0, "valido: nessun circolo, nessuna confermata"),
    # F4/F5 — CONTRASTO PERMANENTE per il bug del filtro restatement (2026-06):
    # petitio simmetrica col SOGGETTO LUNGO. Il soggetto è condiviso per costruzione
    # tra premessa-arricchita e tesi; se il Jaccard fosse calcolato sulla premessa
    # arricchita (com'era nel bug), l'alta sovrapposizione del soggetto lungo
    # scatterebbe il filtro >0.5 e SCARTEREBBE la petitio. Atteso: circolarità=1.
    # Non rimuovere: vegliano che il bug non torni silenziosamente.
    ("F4 petitio soggetto lungo (corretta)",
     "Questa lunga e articolata tesi accademica è vera perché è corretta.",
     "ge1", "ge1", "petitio simmetrica, soggetto lungo: NON va scartata dal filtro restatement"),
    ("F5 petitio soggetto lungo (esatta)",
     "L'intera dimostrazione esposta nel capitolo precedente è vera perché è esatta.",
     "ge1", "ge1", "variante vera↔esatta, soggetto lungo: stessa protezione di F4"),
]


def _check(val: int, atteso) -> bool:
    return val >= 1 if atteso == "ge1" else val == atteso


def main(casi=CASI) -> int:
    fails, skipped = [], 0
    print("=" * 66)
    print("Batteria di contrasto fallacie — confermate/sospette + circolarità")
    print("=" * 66)
    for tid, testo, exp_circ, exp_conf, nota in casi:
        r = analizza(testo, verbose=False)
        y = r.yaml_output
        if y["backend"]["annotazione"] != "stanza":
            print(f"SKIP {tid} — backend fallback"); skipped += 1; continue
        circ = y.get("n_circolarita", 0)
        conf = y.get("n_fallacie_confermate", 0)
        sosp = y.get("n_fallacie_sospette", 0)
        af   = round(r.componenti_epsilon.get("assenza_fallacie", -1), 3)
        ok = _check(circ, exp_circ) and _check(conf, exp_conf)
        if not ok:
            fails.append(tid)
        print(f"{'PASS' if ok else 'FAIL'} {tid}: circolarita={circ} (att {exp_circ}) | "
              f"confermate={conf} (att {exp_conf}) | sospette={sosp} | assenza_fallacie={af}")
        print(f"     · {nota}")
    print("-" * 66)
    if fails:
        print(f"REGRESSIONE: {len(fails)} fallito/i → {', '.join(fails)}")
        return 1
    print(f"OK — {len(casi) - skipped} casi verificati, {skipped} saltati")
    return 0


if __name__ == "__main__":
    sys.exit(main())
