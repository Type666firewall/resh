"""resh/tests/run_batterie.py — Runner combinato delle batterie in UN processo.

Perché esiste: Stanza + NLI + BGE-M3 sono singleton di processo, ma vengono
ricaricati a OGNI invocazione separata di `python.exe`. Eseguire le due batterie
come due processi distinti paga DUE volte il caricamento (la parte lenta). Questo
runner le esegue in un **unico processo**: i modelli si caricano una sola volta e
sono condivisi da entrambe.

Uso:
    <venv>/python.exe -m resh.tests.run_batterie           # completo (verifica finale)
    <venv>/python.exe -m resh.tests.run_batterie --quick   # sottoinsieme rappresentativo (check rapido)

`--quick` non salta i modelli (la circolarità/sequitur richiedono l'NLI: senza,
i casi sarebbero SALTATI e non verificherebbero nulla) — riduce i CASI a un nucleo
di non-regressione, così il tempo DOPO il caricamento è minimo. Il caricamento dei
modelli resta il costo dominante e si paga una volta sola.

Esce con codice 1 se una qualsiasi batteria regredisce.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from resh.tests import test_sequitur_battery as SEQ
from resh.tests import test_fallacie_battery as FAL
from resh.tests import test_integrita_obiettivo as INT
from resh.tests import test_trilemma_predetect as TRI
from resh.tests import test_persistenza_doc as PER
from resh.tests import test_aggregatore as AGG
from resh.tests import test_postprocess_inclosura as PPI
from resh.tests import eval_abstract as ABS


def _subset(casi, ids):
    """Casi il cui id inizia con uno dei prefissi in `ids` (preserva l'ordine)."""
    return [c for c in casi if any(c[0].startswith(p) for p in ids)]


# Nucleo di non-regressione per --quick: un vero-positivo + una guardia anti-falso-
# positivo per batteria, più il caso-bug del soggetto lungo (F4).
QUICK_SEQ = ("T2", "T5", "T7")   # C₃ TP · entimema (no FP) · modus ponens (no FP)
QUICK_FAL = ("F1", "F2", "F4")   # sillogismo (no FP) · petitio · soggetto lungo (regressione)
QUICK_INT = ("I1", "I3", "I5")   # contraddittorio · integro · None (O deterministico)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except (AttributeError, OSError):
        pass
    ap = argparse.ArgumentParser(description="Runner combinato batterie resh (1 processo).")
    ap.add_argument("--quick", action="store_true",
                    help="sottoinsieme di non-regressione (modelli caricati comunque 1 volta)")
    args = ap.parse_args()

    seq_casi = _subset(SEQ.CASI, QUICK_SEQ) if args.quick else SEQ.CASI
    fal_casi = _subset(FAL.CASI, QUICK_FAL) if args.quick else FAL.CASI
    int_casi = _subset(INT.CASI, QUICK_INT) if args.quick else INT.CASI

    modo = "QUICK (sottoinsieme)" if args.quick else "COMPLETO"
    print(f"\n########## RUNNER COMBINATO — modo {modo} — 1 processo, modelli 1 caricamento ##########\n")

    # ── Stabilità leggera PRIMA dei modelli (zero LLM, zero ML, <1s) ──
    # Audit Λ: gli invarianti girano all'import di lambda_space; qui si rende
    # esplicito l'esito (un AssertionError sarebbe già esploso all'import).
    from resh import lambda_space
    print(f"Audit Λ: OK — {len(lambda_space.LAMBDA_RESH)} γ, invarianti verdi "
          f"(eps_role/eps_feeds/output_kind)\n")

    rc_per = PER.main()              # smoke persistenza documentale (DB temporaneo)
    print()
    rc_agg = AGG.main()              # smoke aggregatore QuadroEpsilon (no LLM)
    print()
    rc_ppi = PPI.main()              # truth-table regola inclosura (no LLM)
    print()
    print("=" * 60)
    print("BATTERIA: detector termini astratti (recall vs gold, no LLM)")
    print("=" * 60)
    rc_abs = ABS.main([])            # solo lato deterministico
    print()

    rc_seq = SEQ.main(seq_casi)      # il primo analizza() qui scalda i singleton
    print()
    rc_fal = FAL.main(fal_casi)      # riusa gli stessi modelli già in RAM/VRAM
    print()
    rc_int = INT.main(int_casi)      # idem (solo NLI)
    print()

    # Trilemma pre-detection (NO LLM — solo marker regex, veloce).
    print("=" * 60)
    print("BATTERIA: Trilemma pre-detection (marker regex)")
    print("=" * 60)
    rc_tri = TRI.main([]) or 0

    print("\n" + "=" * 66)
    rc = rc_seq | rc_fal | rc_int | rc_tri | rc_per | rc_agg | rc_ppi | rc_abs
    print(f"VERDETTO COMBINATO: {'OK — nessuna regressione' if rc == 0 else 'REGRESSIONE rilevata'}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
