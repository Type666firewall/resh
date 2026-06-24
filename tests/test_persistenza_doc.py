"""Smoke test persistenza documentale — DB temporaneo, zero call LLM, zero modelli.

Verifica il giro completo: save_run_documento (run_uid Ψ_<doc12>_D<seq>, record di
onestà) → get_run_documento → report rigenerato dal rapporto_json con run_uid in
intestazione → sequenza progressiva al secondo save → list_runs_documento.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


_TESTO = "Testo di prova per l'identità del documento (sha256 del testo)."

_RAP_DOC = {
    "fonte": "smoke_doc.md", "lingua": "it", "n_chunk": 3,
    "obiettivo": {"dichiarato": "Obiettivo di prova", "latente": None, "coerenza": 0.9},
    "chunk": [
        {"id": 0, "loc": "pagina 1", "det": {"eps_resh": 0.51},
         "ind": {"arsenale": {"nota": "ok"}, "assi": {"r2": {"nota": "ok"}},
                 "trilemma": {"llm": {"corno": "C3"}}}},
        {"id": 1, "loc": "pagina 2", "det": {"eps_resh": 0.62},
         # una parte induttiva in errore: deve finire in n_parti_errore=1
         "ind": {"arsenale": {"nota": "ok"}, "assi": {"r2": {"errore": "429 quota"}},
                 "trilemma": {"llm": {"corno": "C2"}}}},
    ],
    "eps_doc": 0.5612,
    "eps_per_chunk": [{"id": 0, "eps": 0.51, "char": 100}, {"id": 1, "eps": 0.62, "char": 100}],
    "sintesi_doc": "Sintesi di prova.",
    "saltati": [2],
    "meta": {"doc_hash": "abc123", "profilo": "test", "model": "nessuno",
             "assi_chunk": ["r2", "trilemma"], "con_astratti": False,
             "call_eseguite": 7, "riparati": [], "ts": "2026-06-10T00:00:00"},
}


def main() -> int:
    from resh import lambda_space, report
    from resh.persistenza import (get_run_documento, list_runs_documento,
                                  save_run_documento)

    print("=" * 60)
    print("BATTERIA: persistenza documentale (smoke, DB temporaneo)")
    print("=" * 60)
    errori: list[str] = []

    # Λ: i γ di persistenza sono registrati e risolvibili.
    for g in ("γ_save_run", "γ_save_run_documento"):
        try:
            lambda_space.resolve(g)
        except Exception as exc:
            errori.append(f"resolve({g}) fallito: {exc}")

    tmp = Path(tempfile.mkdtemp(prefix="resh_smoke_")) / "smoke.db"
    try:
        e1 = save_run_documento(_RAP_DOC, testo=_TESTO, db_path=tmp)
        uid1 = e1["run_uid"]
        if not uid1.startswith("Ψ_") or "_D001" not in uid1:
            errori.append(f"run_uid inatteso: {uid1}")

        run = get_run_documento(run_uid=uid1, db_path=tmp)
        if run is None:
            errori.append("get_run_documento non trova il run appena salvato")
        else:
            if run["eps_doc"] != 0.5612:
                errori.append(f"eps_doc persistito errato: {run['eps_doc']}")
            if run["n_saltati"] != 1:
                errori.append(f"n_saltati atteso 1, trovato {run['n_saltati']}")
            if run["n_parti_errore"] != 1:
                errori.append(f"n_parti_errore atteso 1, trovato {run['n_parti_errore']}")
            md = report.genera_report_documento(run["rapporto"], run_uid=run["run_uid"])
            if uid1 not in md:
                errori.append("run_uid assente dal report rigenerato")
            if "0.5612" not in md:
                errori.append("eps_doc assente dal report rigenerato")

        e2 = save_run_documento(_RAP_DOC, testo=_TESTO, db_path=tmp)
        if "_D002" not in e2["run_uid"]:
            errori.append(f"sequenza run non progressiva: {e2['run_uid']}")

        rows = list_runs_documento(db_path=tmp)
        if len(rows) != 2:
            errori.append(f"list_runs_documento: attesi 2 run, trovati {len(rows)}")
    finally:
        # Il DB temporaneo è un artefatto del test, non memoria dell'agente.
        try:
            for f in tmp.parent.glob("smoke.db*"):
                f.unlink()
            tmp.parent.rmdir()
        except OSError:
            pass

    if errori:
        for e in errori:
            print(f"  FAIL  {e}")
        print("VERDETTO: REGRESSIONE persistenza documentale")
        return 1
    print("  ok    save → get → report(run_uid) → seq D002 → list: tutto verde")
    print("VERDETTO: OK")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
