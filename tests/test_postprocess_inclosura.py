"""Truth-table di `_postprocess_inclosura` — regressione DETERMINISTICA (no LLM).

La forma-inclosura è una REGOLA, non un giudizio LLM: presente ⟺ trascendenza ∧
chiusura; parziale ⟺ XOR; assente altrimenti. Il segnale verso Trilemma/Arsenale
scatta SOLO se forma=presente ∧ modo ∈ {USE, SELF_DIAGNOSIS}, mappato dalla
risposta al limite. Questa batteria inchioda la regola.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _llm(trasc: bool, chius: bool, modo: str, risposta: str) -> dict:
    return {"omega": "X", "delta": "Y",
            "trascendenza": {"vale": trasc, "span": "t"},
            "chiusura": {"vale": chius, "span": "c"},
            "modo": modo, "risposta_al_limite": risposta, "nota": None}


# (trasc, chius, modo, risposta) → (forma attesa, segnale atteso: None | chiave presente)
CASI = [
    # forma: tabella di verità trasc×chius
    ("P1", True,  True,  "USE",            "ACCETTA",  "presente", True),
    ("P2", True,  False, "USE",            "ACCETTA",  "parziale", False),
    ("P3", False, True,  "USE",            "ACCETTA",  "parziale", False),
    ("P4", False, False, "USE",            "ACCETTA",  "assente",  False),
    # segnale: solo USE/SELF_DIAGNOSIS con forma presente
    ("S1", True,  True,  "SELF_DIAGNOSIS", "RISOLVE",  "presente", True),
    ("S2", True,  True,  "MENTION",        "ACCETTA",  "presente", False),
    ("S3", True,  True,  "DIAGNOSIS",      "ACCETTA",  "presente", False),
    ("S4", True,  True,  "NONE",           "ACCETTA",  "presente", False),
    # risposta PERFORMA: ricorsività costitutiva, segnale presente ma non patologico
    ("R1", True,  True,  "USE",            "PERFORMA", "presente", True),
    ("R2", True,  True,  "USE",            "RISOLVE",  "presente", True),
    ("R3", True,  True,  "USE",            "NONE",     "presente", False),  # risposta ignota → nessun segnale
    # casi degeneri
    ("D1", False, False, "NONE",           "NONE",     "assente",  False),
]


def main() -> int:
    from resh.induttivo import _postprocess_inclosura

    print("=" * 60)
    print("BATTERIA: truth-table _postprocess_inclosura (regola, no LLM)")
    print("=" * 60)
    errori: list[str] = []

    for cid, t, c, modo, risp, forma_att, segnale_att in CASI:
        out = _postprocess_inclosura(_llm(t, c, modo, risp), [])
        if out["forma"] != forma_att:
            errori.append(f"{cid}: forma={out['forma']!r}, attesa {forma_att!r}")
        ha_segnale = out.get("segnale") is not None
        if ha_segnale != segnale_att:
            errori.append(f"{cid}: segnale={'sì' if ha_segnale else 'no'}, atteso "
                          f"{'sì' if segnale_att else 'no'} (modo={modo}, risposta={risp})")

    # errore LLM → forma indeterminata, mai 'presente' per sbaglio
    out = _postprocess_inclosura({"errore": "429"}, [])
    if out["forma"] != "indeterminata" or out.get("segnale") is not None:
        errori.append(f"errore-LLM: forma={out['forma']!r}, attesa 'indeterminata' senza segnale")

    if errori:
        for e in errori:
            print(f"  FAIL  {e}")
        print("VERDETTO: REGRESSIONE regola inclosura")
        return 1
    print(f"  ok    {len(CASI)} casi + errore-LLM: regola inchiodata")
    print("VERDETTO: OK")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
