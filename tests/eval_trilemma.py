"""resh/tests/eval_trilemma.py — valutazione del prompt Trilemma sui gold.

Verifica la COERENZA del prompt induttivo del Trilemma (caricato da
`prompts_resh.md`, single source of truth) contro le annotazioni gold del
dataset «Trilemma dataset/». Per ogni passo gold usa il `testo` come φ isolato
(coerente con l'annotazione, che è marker-based e O-agnostica) e confronta il
`corno` e il `modo` predetti con quelli annotati.

La distinzione di MODO (USE vs MENTION/DIAGNOSIS) è la prova più severa: un passo
che PARLA di un corno non vi CADE. Un prompt che classifica tutto come USE è
incoerente con l'obiettivo intrinseco del modulo.

Uso:
  python -m resh.tests.eval_trilemma [--n PER_CORNO] [--profile NOME]

Default: 6 record per corno (≈24 call). Selezione deterministica (stride su id
ordinati) → riproducibile.
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import math
import os
from pathlib import Path

from resh import config, induttivo


_DATASET_DIR = Path(__file__).resolve().parent.parent / "Trilemma dataset"


# Obiettivo O a livello-DOCUMENTO (l'obiettivo dell'agente che ha prodotto il testo,
# derivato dal ruolo del documento — NON dalle label). Serve a testare l'ipotesi Σ_w:
# più contesto (O) → il livello meta-riflessivo (parla-di vs cade-in) diventa tracciabile.
_OBIETTIVI = {
    "albert_treatise_on_critical_reason.md": "Esporre criticamente il Trilemma di Münchhausen e argomentare contro il fondazionalismo (trattato meta-epistemologico).",
    "L_Arsenale_Critico.md": "Definire un apparato critico non-fondazionalista (tre assi + Trilemma) come metodo di decostruzione.",
    "Circolarita_Metafisica_e_Valori.md": "Diagnosticare come le metafisiche invertano valori in presupposti ontologici.",
    "descartes_meditations_1641.md": "Stabilire un fondamento primo e indubitabile della conoscenza.",
    "mu_Diario_Rappresentazione_Linguaggio_Vita.md": "Costruire una rappresentazione operativa e non-fondazionalista di vita, linguaggio e mondo.",
    "friedman_divine_consistency_proof_2012.md": "Formalizzare una prova di consistenza dichiarandone gli assiomi assunti.",
    "hilbert_on_the_infinite_1926.pdf": "Fondare la matematica classica trattando l'infinito come elemento ideale.",
    "hume_circolarita_formale.md": "Analizzare la circolarità della giustificazione dell'induzione.",
    "ioli_gorgia_fantasia_rationis.md": "Ricostruire storicamente la nozione di fantasia/ragione in Gorgia e nei pre-classici.",
    "mu_La_Realta.md": "Diagnosticare sistematicamente realismo, idealismo e materialismo.",
    "leibniz_xv_fenomeni_reali_1683.md": "Stabilire un criterio per distinguere i fenomeni reali da quelli immaginari.",
    "mu_Priest_e_Schema_di_Inclosura.md": "Applicare lo Schema di Inclosura per diagnosticare i paradossi di totalità.",
    "sini_wittgenstein_linguaggio_lezione1.md": "Esporre e diagnosticare il problema del linguaggio nel Tractatus di Wittgenstein.",
    "v19_gorgia_berkeley.md": "Diagnosticare le posizioni di Berkeley e Gorgia sul linguaggio.",
    "zilioli_nihilist_gorgia_nagarjuna_2023.md": "Argomentare una lettura nichilista di Gorgia e Nāgārjuna.",
}


def _carica_gold() -> list[dict]:
    recs = []
    for f in glob.glob(str(_DATASET_DIR / "gold_*.jsonl")):
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def _campione(recs: list[dict], per_corno: int) -> list[dict]:
    """Stride deterministico su id ordinati, per_corno per ciascun corno."""
    by = collections.defaultdict(list)
    for r in recs:
        by[r["corno"]].append(r)
    out = []
    for corno, lst in by.items():
        lst = sorted(lst, key=lambda r: r["id"])
        if len(lst) <= per_corno:
            out += lst
        else:
            step = len(lst) / per_corno
            out += [lst[int(i * step)] for i in range(per_corno)]
    return out


def _campione_naturale(recs: list[dict], totale: int) -> list[dict]:
    """Campione che RISPETTA la distribuzione naturale dei corni (non bilanciato).
    Stride deterministico per classe, quote proporzionali."""
    by = collections.defaultdict(list)
    for r in recs:
        by[r["corno"]].append(r)
    n_tot = len(recs)
    out = []
    for corno, lst in by.items():
        k = max(1, round(totale * len(lst) / n_tot))
        lst = sorted(lst, key=lambda r: r["id"])
        if len(lst) <= k:
            out += lst
        else:
            step = len(lst) / k
            out += [lst[int(i * step)] for i in range(k)]
    return out


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervallo di confidenza di Wilson al 95% per una proporzione k/n.
    Onesto su n piccolo: su n=48 l'intervallo è ampio → i delta piccoli sono rumore."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    semi = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centro - semi), min(1.0, centro + semi))


def _predici(testo: str, prompts: dict, profile: str | None,
             obiettivo: str | None = None) -> dict:
    sys = induttivo._corpo(prompts, "Trilemma di Münchhausen")
    blocco_o = f"Obiettivo O dell'agente che ha prodotto φ: {obiettivo}\n\n" if obiettivo else ""
    user = f'Testo φ:\n"""\n{testo.strip()}\n"""\n\n{blocco_o}{induttivo._OUT_TRILEMMA}'
    return config.call_llm_json(sys, user, max_tokens=4096, temperature=0.1,
                                profile=profile, tag="eval-trilemma")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6, help="record per corno (modalità bilanciata)")
    ap.add_argument("--natural", action="store_true",
                    help="campione a DISTRIBUZIONE NATURALE invece che bilanciata")
    ap.add_argument("--total", type=int, default=48,
                    help="record totali in modalità --natural")
    ap.add_argument("--profile", default=None, help="profilo LLM (default: attivo)")
    ap.add_argument("--with-o", action="store_true",
                    help="inietta l'Obiettivo O a livello-documento (test ipotesi contesto)")
    args = ap.parse_args()

    # line-buffering + utf-8: i run in background mostrano il progresso riga-per-riga
    # (lo stdout block-buffered faceva sembrare «appeso» un run solo lento).
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

    prompts = induttivo.carica_prompt()
    gold = _carica_gold()
    sample = _campione_naturale(gold, args.total) if args.natural else _campione(gold, args.n)
    dist = dict(collections.Counter(r["corno"] for r in sample))
    snap = config.config_snapshot(args.profile)
    modo_camp = "naturale" if args.natural else "bilanciato"
    print(f"Modello: {snap['model']} ({snap['profile']}) — {len(sample)} record"
          f" — campione {modo_camp} {dist} — O={'SÌ' if args.with_o else 'no'}\n")

    ok_corno = ok_modo = tot = 0
    conf_corno = collections.Counter()
    per_classe: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])  # corno: [ok, tot]
    for r in sample:
        obiettivo = _OBIETTIVI.get(r.get("doc", "")) if args.with_o else None
        try:
            p = _predici(r["testo"], prompts, args.profile, obiettivo)
        except Exception as exc:
            print(f"[{r['id']}] ERRORE: {exc}")
            continue
        tot += 1
        pc, pm = str(p.get("corno", "?")).upper(), str(p.get("modo", "?")).upper()
        gc, gm = r["corno"].upper(), r["modo"].upper()
        c_ok, m_ok = pc == gc, pm == gm
        ok_corno += c_ok
        ok_modo += m_ok
        conf_corno[(gc, pc)] += 1
        per_classe[gc][1] += 1
        if c_ok:
            per_classe[gc][0] += 1
        flag = "OK" if c_ok else "XX"
        mflag = "OK" if m_ok else "XX"
        print(f"[{r['id']:<10}] corno {flag} gold={gc:<4} pred={pc:<4} | "
              f"modo {mflag} gold={gm:<13} pred={pm:<13} | sub_pred={p.get('sottotipo','')}")

    if tot:
        lo_c, hi_c = _wilson(ok_corno, tot)
        lo_m, hi_m = _wilson(ok_modo, tot)
        print(f"\nAccuratezza corno: {ok_corno}/{tot} = {ok_corno/tot:.0%}"
              f"  (Wilson 95%: {lo_c:.0%}–{hi_c:.0%})")
        print(f"Accuratezza modo:  {ok_modo}/{tot} = {ok_modo/tot:.0%}"
              f"  (Wilson 95%: {lo_m:.0%}–{hi_m:.0%})")
        # NB onestà: su n piccolo l'intervallo è ampio → delta di pochi record = rumore.

        print("\nAccuratezza per-classe (corno gold):")
        macro = []
        for c in ("C1", "C2", "C3", "NONE"):
            ok, n = per_classe.get(c, [0, 0])
            if n:
                macro.append(ok / n)
                print(f"  {c:<4} {ok}/{n} = {ok/n:.0%}")
        if macro:
            print(f"  macro-avg (media non pesata sulle classi): {sum(macro)/len(macro):.0%}")

        print("\nConfusioni corno (gold→pred), solo errori:")
        for (g, pr), n in sorted(conf_corno.items(), key=lambda x: -x[1]):
            if g != pr:
                print(f"  {g:<4} → {pr:<4} : {n}")


if __name__ == "__main__":
    main()
