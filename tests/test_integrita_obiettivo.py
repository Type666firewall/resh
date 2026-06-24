"""Batteria di contrasto — integrita_obiettivo (O fallibile rappresentazione del volere).

Verifica la misura deterministica dell'incoerenza INTRINSECA di O (relazione NLI
dichiarato↔latente), Gate 9/P1′:
- contraddizione dichiarato↔latente → `contraddittorio` (mauvaise foi)
- dichiarato↔latente scollegati     → `disperso` (cattiva induzione)
- entailment (una direzione)        → `integro`
- latente cercato e assente         → `integro` 1.0 (nessuna scissione)
- O non induttivo / estrazione fallita → `None` (ESCLUSO da eps_resh, non 1.0:
  un fallimento non si maschera da integrità — decisione 3 Σ_w)

Usa SOLO l'NLI (nessun LLM): le Teleologia sono sintetiche. Se l'NLI cade in
fallback (modelli assenti), i casi sono SALTATI, non falliti.

Uso: <venv>/python.exe -m resh.tests.test_integrita_obiettivo
Esce con codice 1 se una regressione è rilevata.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from resh.schemas import Teleologia
from resh.obiettivo import valuta_integrita_obiettivo


def _tel(dich, lat):
    return Teleologia(obiettivo_dichiarato=dich, obiettivo_latente=lat, coerenza=0.5)


# (id, teleologia, fonte, tipo_atteso, integrita_attesa: "lt1"=<1.0 / "eq1"=1.0 / "none"=None, nota)
CASI = [
    ("I1 contraddittorio (mauvaise foi)",
     _tel("Bisogna abolire la pena di morte", "Bisogna mantenere la pena di morte"),
     "llm", "contraddittorio", "lt1", "dichiarato↔latente in contraddizione → penalità piena"),
    ("I2 disperso (cattiva induzione)",
     _tel("Spiegare il funzionamento della fotosintesi",
          "Convincere il lettore a comprare un'automobile"),
     "llm", "disperso", "lt1", "latente scollegato dal dichiarato → penalità lieve"),
    ("I3 integro (entailment)",
     _tel("Dimostrare che la Terra è rotonda", "Dimostrare la sfericità del pianeta Terra"),
     "llm", "integro", "eq1", "latente coerente col dichiarato (entailment) → nessuna penalità"),
    ("I4 integro (latente assente)",
     _tel("Sostenere l'abolizione della pena di morte", None),
     "llm", "integro", "eq1", "latente cercato e assente: nessuna scissione → 1.0"),
    ("I5 None (O non induttivo)",
     _tel("x qualunque", "y qualunque"),
     "deterministica", None, "none", "O deterministico → escluso da eps_resh (non 1.0)"),
]


def _check_integrita(val, atteso) -> bool:
    if atteso == "none":
        return val is None
    if atteso == "eq1":
        return val == 1.0
    return val is not None and val < 1.0     # "lt1"


def main(casi=CASI) -> int:
    fails, skipped = [], 0
    print("=" * 70)
    print("Batteria di contrasto integrita_obiettivo — O fallibile (dichiarato↔latente)")
    print("=" * 70)
    for tid, tel, fonte, tipo_att, integ_att, nota in casi:
        val, dett = valuta_integrita_obiettivo(tel, fonte=fonte)
        tipo = dett.get("tipo")
        # fallback NLI: integrità non valutabile su un caso che la richiede → SKIP
        if fonte == "llm" and integ_att != "eq1" and val is None and "NLI" in dett.get("motivo", ""):
            print(f"SKIP {tid} — NLI in fallback"); skipped += 1; continue
        ok = (tipo == tipo_att) and _check_integrita(val, integ_att)
        if not ok:
            fails.append(tid)
        print(f"{'PASS' if ok else 'FAIL'} {tid}: integrita={val} tipo={tipo} "
              f"(atteso tipo={tipo_att}, {integ_att})  · {nota}")
    print("-" * 70)
    if fails:
        print(f"REGRESSIONE: {len(fails)} caso/i fallito/i → {', '.join(fails)}")
        return 1
    print(f"OK — {len(casi) - skipped} casi verificati, {skipped} saltati")
    return 0


if __name__ == "__main__":
    sys.exit(main())
