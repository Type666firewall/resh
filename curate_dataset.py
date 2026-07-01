"""resh/curate_dataset.py — Curazione manuale dei run per dataset calibrazione RF.

Modulo offline, non registrato in Λ, non parte della pipeline.
Legge il DB in sola lettura, presenta i run all'utente per approvazione,
salva le decisioni in resh/data/curated_labels.jsonl.

Legge da entrambe le tabelle:
  - analisi           (run per-testo, profilo linguistico completo)
  - analisi_documento (run documentali map-reduce, dati per-chunk aggregati)

Uso:
  python -m resh.curate_dataset                # revisiona run non ancora visti
  python -m resh.curate_dataset --export       # estrai dataset piatto dai run approvati
  python -m resh.curate_dataset --stats        # conteggi approvati/scartati/pending
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .persistenza import init_db, _connect

_DATA_DIR = Path(__file__).resolve().parent / "data"
_LABELS_FILE = _DATA_DIR / "curated_labels.jsonl"
_DATASET_FILE = _DATA_DIR / "dataset_rf.csv"

# ── feature da estrarre ──────────────────────────────────────────────────────

_PROFILO_KEYS = [
    "subordination_ratio", "rapporto_nominale_verbale",
    "conn_causali_per1k", "conn_avversativi_per1k", "conn_concessivi_per1k",
    "rapporto_interrog_dichiar", "quotes_per1k",
    "densita_lessicale", "profondita_media_albero", "lunghezza_media_frase",
    "ttr", "mtld", "gulpease", "n_token", "n_frasi",
]

_STILISTICO_KEYS = [
    "pron_1p_per1k", "pron_2p_per1k", "pron_3p_per1k",
    "modali_per1k", "subord_per1k", "passivi_per1k", "nominaliz_per1k",
]

_COMP_KEYS = [
    "trasparenza_premesse", "validita_formale", "assenza_fallacie",
    "struttura_argomentativa", "coesione_semantica", "coerenza_tematica",
    "qualita_sintattica", "bias_linguistico", "credibilita_fonte",
]


def _load_labels() -> dict[str, dict]:
    if not _LABELS_FILE.exists():
        return {}
    out: dict[str, dict] = {}
    for line in _LABELS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        out[rec["run_uid"]] = rec
    return out


def _save_label(rec: dict) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(_LABELS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ── normalizzazione: due formati → struttura comune ──────────────────────────

def _normalize_pertesto(rap: dict) -> dict:
    """Da rapporto per-testo (tabella analisi) → struttura comune."""
    ind = rap.get("induttivo") or {}
    pats = rap.get("patologie_strutturate") or []
    trilemma = ind.get("trilemma") or {}
    tri_llm = trilemma.get("llm") or {}
    inclosura = ind.get("inclosura") or {}
    incl_llm = inclosura.get("llm") or {}
    arsenale = ind.get("arsenale") or {}
    obiettivo = ind.get("obiettivo") or {}

    return {
        "source": "analisi",
        "eps": rap.get("eps_resh"),
        "profilo_linguistico": rap.get("profilo_linguistico") or {},
        "profilo_stilistico": rap.get("profilo_stilistico") or {},
        "componenti_epsilon": rap.get("componenti_epsilon") or {},
        "patologie_strutturate": pats,
        "corno_trilemma": tri_llm.get("corno", ""),
        "inclosura_presente": bool(incl_llm.get("forma")) and incl_llm.get("forma") != "assente",
        "inclosura_modo": incl_llm.get("modo", ""),
        "malafede_grado": (arsenale.get("malafede_o") or {}).get("grado", ""),
        "teleologia_coerenza": obiettivo.get("coerenza"),
        "n_assi_ind": len(ind.get("assi") or {}),
        "arsenale_presente": bool(arsenale) and "errore" not in arsenale,
        "assi_falliti": ind.get("assi_falliti", []),
        "ind_presente": bool(ind) and "errore" not in ind,
    }


def _normalize_documento(rap: dict) -> dict:
    """Da rapporto documentale (tabella analisi_documento) → struttura comune.

    Aggrega i chunk: media dei componenti ε, somma patologie,
    prende trilemma/arsenale/inclosura dal primo chunk che li ha."""
    chunks = rap.get("chunk") or []
    obiettivo = rap.get("obiettivo") or {}

    comp_agg: dict[str, list[float]] = {k: [] for k in _COMP_KEYS}
    all_pats: list[str] = []
    trilemma_corno = ""
    inclosura_presente = False
    inclosura_modo = ""
    malafede_grado = ""
    arsenale_presente = False
    n_assi = 0
    assi_falliti: list[str] = []

    for c in chunks:
        det = c.get("det") or {}
        ind = c.get("ind") or {}

        comp = det.get("componenti_epsilon") or {}
        for k in _COMP_KEYS:
            v = comp.get(k)
            if v is not None:
                comp_agg[k].append(float(v))

        all_pats.extend(det.get("patologie") or [])

        tri = ind.get("trilemma") or {}
        tri_llm = tri.get("llm") or {}
        if not trilemma_corno and tri_llm.get("corno"):
            trilemma_corno = tri_llm["corno"]

        incl = ind.get("inclosura") or {}
        incl_llm = incl.get("llm") or {}
        if not inclosura_presente and incl_llm.get("forma") == "presente":
            inclosura_presente = True
            inclosura_modo = incl_llm.get("modo", "")

        ars = ind.get("arsenale") or {}
        if not arsenale_presente and ars and "errore" not in ars:
            arsenale_presente = True
            mal = (ars.get("malafede_o") or {}).get("grado", "")
            if mal:
                malafede_grado = mal

        chunk_assi = ind.get("assi") or {}
        n_assi = max(n_assi, len(chunk_assi))
        assi_falliti.extend(ind.get("assi_falliti") or [])

    comp_avg = {}
    for k in _COMP_KEYS:
        vals = comp_agg[k]
        comp_avg[k] = sum(vals) / len(vals) if vals else None

    # patologie documentali sono stringhe legacy, contiamo per tipo
    n_fallacie_det = sum(1 for p in all_pats if p.startswith("[fallacia_logica]"))
    n_non_sequitur = sum(1 for p in all_pats if p.startswith("[non_sequitur]"))
    n_confermate = sum(1 for p in all_pats
                       if "[fallacia_logica]" in p and "confermata=True" in p)
    n_regex = sum(1 for p in all_pats
                  if "[fallacia_logica]" in p and "fonte=regex_it" in p)
    n_nli = sum(1 for p in all_pats
                if "[fallacia_logica]" in p and "fonte=nli_zeroshot" in p)

    return {
        "source": "analisi_documento",
        "eps": rap.get("eps_doc"),
        "profilo_linguistico": {},
        "profilo_stilistico": {},
        "componenti_epsilon": comp_avg,
        "patologie_conteggi": {
            "n_fallacie_det": n_fallacie_det,
            "n_fallacie_regex": n_regex,
            "n_fallacie_nli": n_nli,
            "n_fallacie_confermate": n_confermate,
            "n_non_sequitur": n_non_sequitur,
        },
        "corno_trilemma": trilemma_corno,
        "inclosura_presente": inclosura_presente,
        "inclosura_modo": inclosura_modo,
        "malafede_grado": malafede_grado,
        "teleologia_coerenza": obiettivo.get("coerenza"),
        "n_assi_ind": n_assi,
        "arsenale_presente": arsenale_presente,
        "assi_falliti": list(set(assi_falliti)),
        "ind_presente": arsenale_presente,
        "n_chunk": len(chunks),
    }


# ── summary per revisione ───────────────────────────────────────────────────

def _summary_line(norm: dict) -> dict:
    if norm["source"] == "analisi":
        pats = norm.get("patologie_strutturate") or []
        n_fal = sum(1 for p in pats if (p.get("tipo") or "") == "fallacia_logica")
        n_conf = sum(1 for p in pats
                     if (p.get("tipo") or "") == "fallacia_logica"
                     and (p.get("dettaglio") or {}).get("confermata") is True)
        n_nli = sum(1 for p in pats
                    if (p.get("tipo") or "") == "fallacia_logica"
                    and (p.get("dettaglio") or {}).get("fonte") == "nli_zeroshot_v2")
        n_regex = sum(1 for p in pats
                      if (p.get("tipo") or "") == "fallacia_logica"
                      and (p.get("dettaglio") or {}).get("fonte") == "regex_it")
        n_token = (norm.get("profilo_linguistico") or {}).get("n_token", "?")
    else:
        pc = norm.get("patologie_conteggi") or {}
        n_fal = pc.get("n_fallacie_det", 0)
        n_conf = pc.get("n_fallacie_confermate", 0)
        n_nli = pc.get("n_fallacie_nli", 0)
        n_regex = pc.get("n_fallacie_regex", 0)
        n_token = f"{norm.get('n_chunk', '?')} chunk"

    return {
        "eps": norm["eps"],
        "n_token": n_token,
        "n_fallacie_det": n_fal,
        "n_confermate": n_conf,
        "n_nli": n_nli,
        "n_regex": n_regex,
        "arsenale_presente": norm["arsenale_presente"],
        "corno_trilemma": norm["corno_trilemma"],
        "inclosura_presente": norm["inclosura_presente"],
        "assi_falliti": norm["assi_falliti"],
        "source": norm["source"],
    }


# ── extract features per export ──────────────────────────────────────────────

def _extract_features(norm: dict) -> dict:
    row: dict = {}

    pl = norm.get("profilo_linguistico") or {}
    ps = norm.get("profilo_stilistico") or {}
    for k in _PROFILO_KEYS:
        row[k] = pl.get(k)
    for k in _STILISTICO_KEYS:
        row[k] = ps.get(k)

    comp = norm.get("componenti_epsilon") or {}
    for k in _COMP_KEYS:
        row[f"comp_{k}"] = comp.get(k)

    if norm["source"] == "analisi":
        pats = norm.get("patologie_strutturate") or []
        row["n_fallacie_det"] = sum(1 for p in pats
                                     if (p.get("tipo") or "") == "fallacia_logica")
        row["n_fallacie_regex"] = sum(1 for p in pats
                                      if (p.get("tipo") or "") == "fallacia_logica"
                                      and (p.get("dettaglio") or {}).get("fonte") == "regex_it")
        row["n_fallacie_nli"] = sum(1 for p in pats
                                    if (p.get("tipo") or "") == "fallacia_logica"
                                    and (p.get("dettaglio") or {}).get("fonte") == "nli_zeroshot_v2")
        row["n_fallacie_confermate"] = sum(1 for p in pats
                                           if (p.get("tipo") or "") == "fallacia_logica"
                                           and (p.get("dettaglio") or {}).get("confermata") is True)
        row["n_non_sequitur"] = sum(1 for p in pats
                                    if (p.get("tipo") or "") == "non_sequitur")
    else:
        pc = norm.get("patologie_conteggi") or {}
        row["n_fallacie_det"] = pc.get("n_fallacie_det", 0)
        row["n_fallacie_regex"] = pc.get("n_fallacie_regex", 0)
        row["n_fallacie_nli"] = pc.get("n_fallacie_nli", 0)
        row["n_fallacie_confermate"] = pc.get("n_fallacie_confermate", 0)
        row["n_non_sequitur"] = pc.get("n_non_sequitur", 0)

    row["eps"] = norm["eps"]
    row["source"] = norm["source"]

    row["corno_trilemma"] = norm["corno_trilemma"]
    row["inclosura_presente"] = 1 if norm["inclosura_presente"] else 0
    row["inclosura_modo"] = norm["inclosura_modo"]
    row["malafede_grado"] = norm["malafede_grado"]
    row["teleologia_coerenza"] = norm["teleologia_coerenza"]
    row["n_assi_ind"] = norm["n_assi_ind"]
    row["arsenale_presente"] = 1 if norm["arsenale_presente"] else 0

    return row


# ── caricamento run da entrambe le tabelle ───────────────────────────────────

def _load_all_runs(db_path: Optional[Path] = None) -> list[dict]:
    db = init_db(db_path)
    conn = _connect(db)
    runs: list[dict] = []
    try:
        for r in conn.execute(
            "SELECT run_uid, doc_hash, ts_creazione, rapporto_json "
            "FROM analisi ORDER BY ts_creazione ASC"
        ).fetchall():
            rap = json.loads(r["rapporto_json"])
            norm = _normalize_pertesto(rap)
            if not norm["ind_presente"]:
                continue
            runs.append({
                "run_uid": r["run_uid"], "doc_hash": r["doc_hash"],
                "ts": r["ts_creazione"], "norm": norm,
            })

        for r in conn.execute(
            "SELECT run_uid, doc_hash, ts_creazione, rapporto_json "
            "FROM analisi_documento ORDER BY ts_creazione ASC"
        ).fetchall():
            rap = json.loads(r["rapporto_json"])
            norm = _normalize_documento(rap)
            if not norm["ind_presente"]:
                continue
            runs.append({
                "run_uid": r["run_uid"], "doc_hash": r["doc_hash"],
                "ts": r["ts_creazione"], "norm": norm,
            })
    finally:
        conn.close()
    return runs


def _get_pending_runs(db_path: Optional[Path] = None) -> list[dict]:
    labels = _load_labels()
    return [r for r in _load_all_runs(db_path) if r["run_uid"] not in labels]


# ── flusso interattivo ───────────────────────────────────────────────────────

def curate_interactive(db_path: Optional[Path] = None) -> None:
    pending = _get_pending_runs(db_path)
    labels = _load_labels()

    if not pending:
        print(f"Nessun run da revisionare. ({len(labels)} già etichettati)")
        return

    print(f"Run da revisionare: {len(pending)}  |  già etichettati: {len(labels)}\n")

    for run in pending:
        s = _summary_line(run["norm"])
        src = "per-testo" if s["source"] == "analisi" else "documentale"
        eps_str = f"{s['eps']:.4f}" if s['eps'] is not None else "—"
        print("─" * 60)
        print(f"  run_uid:    {run['run_uid']}  ({src})")
        print(f"  doc_hash:   {run['doc_hash'][:16]}…")
        print(f"  data:       {run['ts']}")
        print(f"  ε:          {eps_str}")
        print(f"  dimensione: {s['n_token']}")
        print(f"  fallacie:   {s['n_fallacie_det']} det ({s['n_regex']} regex, "
              f"{s['n_nli']} nli, {s['n_confermate']} confermate)")
        print(f"  arsenale:   {'OK' if s['arsenale_presente'] else 'ASSENTE/ERRORE'}")
        print(f"  trilemma:   {s['corno_trilemma'] or '—'}")
        print(f"  inclosura:  {'presente' if s['inclosura_presente'] else 'assente'}")
        if s["assi_falliti"]:
            print(f"  assi falliti: {s['assi_falliti']}")
        print()

        while True:
            resp = input("  [y] approva  [n] scarta  [s] skip  [q] esci → ").strip().lower()
            if resp in ("y", "n", "s", "q"):
                break
            print("  (y/n/s/q)")

        if resp == "q":
            print("Interrotto.")
            return
        if resp == "s":
            continue

        rec = {
            "run_uid": run["run_uid"],
            "doc_hash": run["doc_hash"],
            "source": run["norm"]["source"],
            "verdict": "approved" if resp == "y" else "rejected",
            "ts_curated": datetime.now().isoformat(timespec="seconds"),
        }
        _save_label(rec)
        print(f"  → {rec['verdict']}\n")

    print("Revisione completata.")


# ── export dataset ───────────────────────────────────────────────────────────

def export_dataset(db_path: Optional[Path] = None) -> Optional[Path]:
    labels = _load_labels()
    approved = {uid for uid, rec in labels.items() if rec["verdict"] == "approved"}

    if not approved:
        print("Nessun run approvato. Lancia prima la curazione interattiva.")
        return None

    all_runs = _load_all_runs(db_path)

    dataset: list[dict] = []
    for run in all_runs:
        if run["run_uid"] not in approved:
            continue
        features = _extract_features(run["norm"])
        features["run_uid"] = run["run_uid"]
        features["doc_hash"] = run["doc_hash"]
        dataset.append(features)

    if not dataset:
        print("Nessun dato estratto.")
        return None

    fieldnames = list(dataset[0].keys())
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(_DATASET_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(dataset)

    # Sidecar di versione/schema — senza, due export in momenti diversi (con
    # _PROFILO_KEYS/_COMP_KEYS cambiati nel frattempo) sono indistinguibili se
    # non rileggendo le colonne a mano: un training su CSV vecchio+nuovo mischiati
    # passerebbe inosservato.
    meta = {
        "generato": datetime.now().isoformat(timespec="seconds"),
        "righe": len(dataset),
        "colonne": fieldnames,
        "profilo_keys": _PROFILO_KEYS,
        "comp_keys": _COMP_KEYS,
    }
    meta_file = _DATASET_FILE.with_suffix(".meta.json")
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Dataset esportato: {_DATASET_FILE.absolute()}")
    print(f"  righe: {len(dataset)}  |  colonne: {len(fieldnames)}")
    print(f"  meta:  {meta_file.absolute()}")
    return _DATASET_FILE


# ── stats ────────────────────────────────────────────────────────────────────

def show_stats(db_path: Optional[Path] = None) -> None:
    labels = _load_labels()
    n_approved = sum(1 for r in labels.values() if r["verdict"] == "approved")
    n_rejected = sum(1 for r in labels.values() if r["verdict"] == "rejected")
    n_pending = len(_get_pending_runs(db_path))

    print(f"Approvati:  {n_approved}")
    print(f"Scartati:   {n_rejected}")
    print(f"Da vedere:  {n_pending}")
    print(f"Totale:     {n_approved + n_rejected + n_pending}")


# ── main ─────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    import argparse
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    ap = argparse.ArgumentParser(
        prog="resh.curate_dataset",
        description="Curazione manuale dei run resh per dataset calibrazione RF.")
    ap.add_argument("--export", action="store_true",
                    help="Esporta dataset piatto dai run approvati")
    ap.add_argument("--stats", action="store_true",
                    help="Mostra conteggi approvati/scartati/pending")
    args = ap.parse_args(argv)

    if args.stats:
        show_stats()
        return 0
    if args.export:
        export_dataset()
        return 0

    curate_interactive()
    return 0


if __name__ == "__main__":
    sys.exit(main())
