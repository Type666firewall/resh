"""resh/tests/eval_abstract.py — eval LATO DETERMINISTICO del detector di termini astratti.

Valuta `induttivo.pre_detect_abstract` contro il gold `dataset/astratti/` (F4 parziale,
collision-safe). Misura SOLO ciò che il detector *può* fare: la **recall** sui termini
gold che gli competono (fonte_candidato suffisso|lessico) e la **sovra-generazione**.
La classificazione del tipo di occultamento è induttiva (LLM) → eval separata, dopo F3.

Convenzione: `gold_<nome>.jsonl` ↔ `src_<nome>.txt` nella stessa cartella.

Onestà metodologica:
- I termini gold con `fonte_candidato == "llm"` (impliciti, es. 'immediatezza') sono ESCLUSI
  dalla recall: il detector morfologico non può catturarli per design.
- Il gold è un SEED parziale → i candidati extra del detector NON sono falsi positivi certi
  (potrebbero essere termini veri non ancora annotati). Si listano per ispezione, non si
  contano come errori.

Uso:  python -m resh.tests.eval_abstract
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import argparse

from resh import astratti, induttivo

_DIR = Path(__file__).resolve().parent.parent / "dataset/astratti"


def _carica(gold_path: Path) -> tuple[str, list[dict]]:
    src = gold_path.with_name(gold_path.name.replace("gold_", "src_")).with_suffix(".txt")
    testo = src.read_text(encoding="utf-8") if src.exists() else ""
    recs = [json.loads(l) for l in gold_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return testo, recs


def _eval_llm(testo: str, recs: list[dict], profile: str | None) -> None:
    """Confronta l'occultamento predetto (astratti.diagnosi) vs gold, per termine.
    Solo sui termini gold che il detector può surfacare (no impliciti llm). 1 call."""
    out = astratti.diagnosi_termini_astratti(testo, profile=profile)
    if out.get("errore"):
        print(f"  [LLM] ERRORE: {out['errore']}")
        return
    diag = out["diagnosi"]
    valutabili = [r for r in recs if r.get("fonte_candidato") in ("suffisso", "lessico")]
    ok = n = 0
    for r in valutabili:
        t = r["termine"]
        pred = diag.get(t, {}).get("occultamento", "—")
        gold = r["occultamento"]
        if pred == "—":
            continue
        n += 1
        c = pred == gold
        ok += c
        print(f"  [LLM] {('OK' if c else 'XX')} {t:<16} gold={gold:<24} pred={pred}")
    if n:
        print(f"  [LLM] accuratezza occultamento: {ok}/{n} = {ok/n:.0%}  (n piccolo → indicativo)")


def main(argv: list[str] | None = None) -> int:
    """`argv=[]` per uso da runner (run_batterie): solo detector, exit code 0/1."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true",
                    help="esegue anche lo stadio LLM (occultamento) e confronta col gold")
    ap.add_argument("--profile", default=None)
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

    gold_files = sorted(glob.glob(str(_DIR / "gold_*.jsonl")))
    if not gold_files:
        print("Nessun gold in", _DIR)
        return 1

    tot_attesi = tot_trovati = 0
    for gf in gold_files:
        gp = Path(gf)
        testo, recs = _carica(gp)
        if not testo:
            print(f"[{gp.name}] SALTATO: manca src_*.txt")
            continue

        rilevati = {h["termine"] for h in induttivo.pre_detect_abstract(testo)}
        gold_terms = {r["termine"] for r in recs}
        # termini che il detector DEVE catturare (morfologici/lessicali), no impliciti llm
        attesi = {r["termine"] for r in recs if r.get("fonte_candidato") in ("suffisso", "lessico")}
        esclusi_llm = {r["termine"] for r in recs if r.get("fonte_candidato") == "llm"}

        trovati = attesi & rilevati
        mancati = attesi - rilevati
        extra = rilevati - gold_terms          # candidati non annotati (NON falsi positivi certi)

        tot_attesi += len(attesi)
        tot_trovati += len(trovati)

        print(f"\n=== {gp.name} ({len(recs)} record, {len(testo)} char) ===")
        rec = (len(trovati) / len(attesi)) if attesi else 1.0
        print(f"  recall detector (su {len(attesi)} attesi): {len(trovati)}/{len(attesi)} = {rec:.0%}")
        if mancati:
            print(f"  MANCATI: {sorted(mancati)}")
        if esclusi_llm:
            print(f"  esclusi (impliciti/llm, non competono al detector): {sorted(esclusi_llm)}")
        if extra:
            print(f"  extra non annotati (da ispezionare, non err. certi): {sorted(extra)}")

        if args.llm:
            _eval_llm(testo, recs, args.profile)

    if tot_attesi:
        print(f"\nTOTALE recall detector: {tot_trovati}/{tot_attesi} = {tot_trovati/tot_attesi:.0%}")
    return 0 if tot_trovati == tot_attesi else 1


if __name__ == "__main__":
    main()
