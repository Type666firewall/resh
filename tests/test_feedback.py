"""Batteria di contrasto — feedback (ledger append-only, giudizio utente).

Zero LLM, zero modelli: costruisce un `RapportoResh` a mano, lo persiste in un
DB temporaneo, ed esercita `save_feedback`/`list_feedback`/`feedback_effettivo`/
`export_feedback_dataset` end-to-end — incluse le validazioni e la semantica
append-only (una correzione è una NUOVA riga, mai un UPDATE).

Uso: `python tests/test_feedback.py`  (exit 1 se regressione)
"""

from __future__ import annotations

import csv
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resh.schemas import (
    AutoritaCriteri, Patologia, PremessaAnalisi, RapportoResh, Teleologia,
    TipoPatologia,
)


def _rapporto_minimo() -> RapportoResh:
    pats = [
        Patologia(
            tipo=TipoPatologia.FALLACIA_LOGICA, severita=0.6, confidence=0.55,
            span_char=(10, 40),
            dettaglio={"fallacia_l2": "petitio_principii", "fonte": "regex_it",
                       "match": "ovviamente vero", "confermata": False},
        ),
        Patologia(
            tipo=TipoPatologia.NON_SEQUITUR, severita=0.9, confidence=0.85,
            span_char=(50, 90),
            dettaglio={"argomento": "premessa debole", "tesi": "conclusione forte"},
        ),
    ]
    return RapportoResh(
        testo="Testo di prova per il feedback.",
        premesse=PremessaAnalisi(esplicite=["p1"], score=0.5),
        inventario=[],
        verifiche=[],
        teleologia=Teleologia(obiettivo_dichiarato="dimostrare X",
                              obiettivo_latente=None, coerenza=0.8),
        autorita=AutoritaCriteri(fonte="sconosciuta", expertise=False, credibilita=0.65),
        eps_resh=0.6234,
        patologie=[p.as_message() for p in pats],
        yaml_output={"backend": {"annotazione": "fallback", "fuzzy": "fallback"}},
        patologie_strutturate=pats,
        componenti_epsilon={"validita_formale": 0.7, "assenza_fallacie": 0.6},
    )


def main() -> int:
    from resh.persistenza import (
        export_feedback_dataset, feedback_effettivo, list_feedback,
        run_summary, save_feedback, save_run,
    )

    print("=" * 66)
    print("Batteria di contrasto — feedback (ledger append-only)")
    print("=" * 66)

    errori: list[str] = []
    tmp_dir = Path(tempfile.mkdtemp(prefix="resh_feedback_"))
    db_path = tmp_dir / "feedback.db"
    testo_path = tmp_dir / "prova.md"
    testo_path.write_text("Testo di prova per il feedback.", encoding="utf-8")

    try:
        rapporto = _rapporto_minimo()
        esito = save_run(rapporto, file_path=testo_path, db_path=db_path)
        run_uid = esito["run_uid"]

        # ── run_summary: esistenza + eps + patologie ────────────────────
        summ = run_summary(run_uid, db_path=db_path)
        if summ is None or summ["source"] != "analisi" or len(summ["patologie"]) != 2:
            errori.append(f"run_summary inatteso: {summ}")
        if run_summary("Ψ_nonexistent_999", db_path=db_path) is not None:
            errori.append("run_summary: atteso None per run inesistente")

        # ── 1) feedback eps + patologia valida ──────────────────────────
        save_feedback(run_uid, "eps", "troppo_basso", nota="il sillogismo regge", db_path=db_path)
        fb = save_feedback(run_uid, "patologia", "falso_positivo", target=0, db_path=db_path)
        if not fb["ancora"] or "petitio_principii" not in fb["ancora"]:
            errori.append(f"ancora patologia inattesa: {fb['ancora']!r}")

        eff = feedback_effettivo(run_uid, db_path=db_path)
        if eff["eps"] is None or eff["eps"]["verdetto"] != "troppo_basso":
            errori.append("feedback_effettivo: eps non risolto correttamente")
        if "0" not in eff["patologie"] or eff["patologie"]["0"]["verdetto"] != "falso_positivo":
            errori.append("feedback_effettivo: patologia #0 non risolta correttamente")

        # ── 2) correzione: append-only, l'ultima riga vince ─────────────
        save_feedback(run_uid, "patologia", "valida", target=0, nota="mi correggo", db_path=db_path)
        storia = list_feedback(run_uid=run_uid, ambito="patologia", db_path=db_path)
        if len(storia) != 2:
            errori.append(f"list_feedback: attese 2 righe (append-only), trovate {len(storia)}")
        eff2 = feedback_effettivo(run_uid, db_path=db_path)
        if eff2["patologie"]["0"]["verdetto"] != "valida":
            errori.append("feedback_effettivo: la correzione non ha vinto sull'ultima riga")

        # ── 3) validazioni ──────────────────────────────────────────────
        casi_invalidi = [
            ("run inesistente",
             lambda: save_feedback("Ψ_nonexistent_999", "eps", "ok", db_path=db_path)),
            ("target fuori range",
             lambda: save_feedback(run_uid, "patologia", "valida", target=99, db_path=db_path)),
            ("verdetto fuori vocabolario",
             lambda: save_feedback(run_uid, "eps", "boh", db_path=db_path)),
            ("ambito ignoto",
             lambda: save_feedback(run_uid, "non_esiste", "x", db_path=db_path)),
            ("target non applicabile per eps",
             lambda: save_feedback(run_uid, "eps", "ok", target=0, db_path=db_path)),
        ]
        for label, fn in casi_invalidi:
            try:
                fn()
                errori.append(f"atteso ValueError per: {label}")
            except ValueError:
                pass

        # ── 4) patologia_mancante + nota (log, non correzioni) ──────────
        save_feedback(run_uid, "patologia_mancante", "petitio al §2 non rilevata", db_path=db_path)
        save_feedback(run_uid, "nota", "run interessante per calibrazione", db_path=db_path)

        # ── 5) export dataset (out_dir = tmp, NON la resh/data/ reale) ──
        out_csv = export_feedback_dataset(db_path=db_path, out_dir=tmp_dir)
        if out_csv is None or not out_csv.exists():
            errori.append("export_feedback_dataset: CSV non prodotto")
        else:
            with out_csv.open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))

            righe_pat = [r for r in rows if r["ambito"] == "patologia" and r["run_uid"] == run_uid]
            if len(righe_pat) != 1:
                errori.append(f"export: attesa 1 riga patologia, trovate {len(righe_pat)}")
            else:
                r = righe_pat[0]
                if r["label"] != "valida":
                    errori.append(f"export: label attesa 'valida' (ultimo verdetto), trovata {r['label']!r}")
                if r["n_revisioni"] != "2":
                    errori.append(f"export: n_revisioni atteso '2', trovato {r['n_revisioni']!r}")
                if r["contraddetta"] != "1":
                    errori.append(f"export: contraddetta atteso '1', trovato {r['contraddetta']!r}")
                if r["fallacia_l2"] != "petitio_principii":
                    errori.append(f"export: fallacia_l2 attesa 'petitio_principii', trovata {r['fallacia_l2']!r}")

            mancanti = [r for r in rows if r["ambito"] == "patologia_mancante"]
            if len(mancanti) != 1:
                errori.append(f"export: attesa 1 riga patologia_mancante, trovate {len(mancanti)}")

            meta_file = out_csv.with_suffix(".meta.json")
            if not meta_file.exists():
                errori.append("export: sidecar .meta.json mancante")

        # ── feedback per-patologia su run documentale: non supportato v1 ─
        try:
            save_feedback("Ψ_finto12345678_D001", "patologia", "valida", target=0, db_path=db_path)
            errori.append("atteso ValueError per feedback patologia su run inesistente/documentale")
        except ValueError:
            pass

    finally:
        try:
            for f in tmp_dir.glob("*"):
                f.unlink()
        except OSError:
            pass
        try:
            tmp_dir.rmdir()
        except OSError:
            pass

    print("-" * 66)
    if errori:
        for e in errori:
            print(f"  FAIL  {e}")
        print(f"REGRESSIONE: {len(errori)} problema/i")
        return 1
    print("OK — feedback: save/list/effettivo/append-only/validazioni/export tutti verdi")
    return 0


if __name__ == "__main__":
    sys.exit(main())
