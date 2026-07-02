"""Eval CERTIFICANTE del detect Inclosura (Schema di Priest) contro i gold.

Livello: EVAL (capacità vs gold), NON smoke (cablaggio) né batteria (regressione).
Fonte teorica: Priest, *Beyond the Limits of Thought*; Priest (1999) «Semantic
Closure, Descriptions and Non-Triviality» (JPL 28:549-558) — la chiusura
semantica è la Chiusura dello schema; la non-trivialità in LP libera è la
formalizzazione della risposta ACCETTA.

UNITÀ DI CONFRONTO (dichiarazione onesta, stampata anche nel dump): il gold
annota PASSI; questo eval valuta φ = passo isolato (stessa convenzione di
eval_trilemma). Misura la capacità sul passo annotato, NON la pipeline olistica
su documento intero — il gap per-passo/olistico è noto e va dichiarato.

CRITERI DI ACCETTAZIONE (pre-dichiarati, calibrati sullo storico Trilemma 50-60%):
  detector (A3): recall ≥50% · FP ≤25% · nessun marker con FP>5 e zero TP
  M1 forma=="presente" su gold USE/DIAGNOSIS/SELF_DIAGNOSIS: ≥60% (Wilson 95%)
     — per i MENTION (regola pre-decisa) si accetta {presente, parziale}
  M2 falsi positivi su negativi puri: forma=="presente" ∧ modo=="USE" — ≤15%
     (gate duro). CRITERIO RIVISTO da Σ_w al triage 2026-06-12: i negativi del
     gold provengono da documenti che PARLANO di inclosura (Priest, Albert,
     Hume) — riconoscerla nel discorso con modo MENTION/DIAGNOSIS è corretto,
     non un FP; solo l'attribuzione d'USO a chi non la usa è falso positivo.
     (Dato alla revisione: 7 FP/16 col vecchio criterio, NESSUNO con modo=USE.)
  M3 modo: ≥50%
  M4 risposta_al_limite vs mapping polarità→attese: INDICATIVO (il gold non lo
     annota; il mapping è derivato e dichiarato tale)
  M5 sottotipo: indicativo
  stabilità: forma identica 3/3 su ≥4/5 record; vale-trasc/chius 3/3 su ≥4/5; 0 bad_json
  parafrasi: forma stabile in ≥2/3 set; il set negativo mai "presente"

Uso:
  python -m resh.tests.eval_inclosura --detector              # A1/A3, 0 call LLM
  python -m resh.tests.eval_inclosura [--n 40] [--profile gemini-3.1-lite] [--dump]
  python -m resh.tests.eval_inclosura --stability [--profile ...]
  python -m resh.tests.eval_inclosura --paraphrase [--profile ...]
"""
from __future__ import annotations

import argparse
import csv
import datetime
import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from resh import induttivo                                    # _corpo/_payload/_OUT/_call/_postprocess
from resh.tests.eval_trilemma import _wilson

_DIR = Path(__file__).resolve().parent.parent / "dataset/trilemma"
_OUT_DIR = Path(__file__).resolve().parent / "eval_out"

# Mapping DERIVATO polarità gold → risposte al limite attese (M4, indicativo).
_POLARITA_RISPOSTE = {
    "patologica_immunizzata":   {"ACCETTA"},
    "patologica":               {"ACCETTA", "NONE"},
    "riconosciuta_strumentale": {"PERFORMA", "NONE"},
    "riconosciuta_virtuosa":    {"PERFORMA"},
    "dichiarata_e_evitata":     {"RISOLVE", "PERFORMA"},
}


def carica_gold() -> list[dict]:
    """Tutti i record di tutti i gold_*.jsonl (id univoci per costruzione)."""
    out: list[dict] = []
    for gf in sorted(glob.glob(str(_DIR / "gold_*.jsonl"))):
        for line in Path(gf).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


# ─── A1/A3 — eval del pre-detector (0 call LLM) ──────────────────────────────

def eval_detector(records: list[dict]) -> int:
    print("=" * 66)
    print("EVAL DETECTOR INCLOSURA (pre-detection, 0 call LLM)")
    print(f"Lessico: {len([m for m in induttivo._load_trilemma_markers() if m.get('corno') == 'INCL'])} "
          f"marker INCL · {len(records)} record gold")
    print("=" * 66)

    pos = [r for r in records if r.get("inclosura")]
    neg = [r for r in records if not r.get("inclosura")]
    per_marker: dict[str, dict] = {}
    righe: list[str] = []
    tp = fp = 0
    fp_ids: list[str] = []
    miss_ids: list[str] = []

    for r in records:
        hits = induttivo.pre_detect_inclosura(r["testo"])
        is_pos = bool(r.get("inclosura"))
        gold_st = (r.get("inclosura") or {}).get("sottotipo", "")
        for h in hits:
            st = h.sottotipo or "?"
            d = per_marker.setdefault(st, {"tp": 0, "fp": 0})
            d["tp" if is_pos else "fp"] += 1
        if hits and is_pos:
            tp += 1
        elif hits:
            fp += 1
            fp_ids.append(r["id"])
        elif is_pos:
            miss_ids.append(r["id"])
        righe.append(f"| {r['id']} | {'POS' if is_pos else 'neg'} | {gold_st or '—'} | "
                     f"{', '.join(sorted({h.sottotipo for h in hits})) or '—'} | "
                     f"{(hits[0].span_testo[:40] if hits else '')} |")

    recall = tp / len(pos) if pos else 0.0
    fp_rate = fp / len(neg) if neg else 0.0
    print(f"\nrecall (≥1 hit su {len(pos)} positivi): {tp}/{len(pos)} = {recall:.0%}  [gate ≥50%]")
    print(f"FP rate (hit su {len(neg)} negativi):    {fp}/{len(neg)} = {fp_rate:.0%}  [gate ≤25%]")
    print("\nPer-marker (TP=hit su positivi, FP=hit su negativi):")
    bad_markers = []
    for st, d in sorted(per_marker.items()):
        flag = ""
        if d["fp"] > 5 and d["tp"] == 0:
            flag = "  ⚠ DA RIMUOVERE (FP>5, zero TP)"
            bad_markers.append(st)
        print(f"  {st:28s} TP={d['tp']:3d}  FP={d['fp']:3d}{flag}")
    if miss_ids:
        print(f"\nMANCATI ({len(miss_ids)}): {miss_ids[:20]}{'…' if len(miss_ids) > 20 else ''}")
    if fp_ids:
        print(f"FP ({len(fp_ids)}): {fp_ids[:20]}{'…' if len(fp_ids) > 20 else ''}")

    _OUT_DIR.mkdir(exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dump = _OUT_DIR / f"detector_inclosura_{ts}.md"
    dump.write_text(
        "# Eval detector Inclosura — per-record\n\n"
        f"ts: {ts} · marker INCL nel lessico · gate: recall≥50% FP≤25%\n\n"
        f"recall={recall:.0%} ({tp}/{len(pos)}) · FP={fp_rate:.0%} ({fp}/{len(neg)})\n\n"
        "| id | gold | sottotipo gold | marker scattati | span |\n|---|---|---|---|---|\n"
        + "\n".join(righe) + "\n", encoding="utf-8")
    print(f"\ndump per-record: {dump}")

    ok = recall >= 0.50 and fp_rate <= 0.25 and not bad_markers
    print(f"\nVERDETTO DETECTOR: {'OK — gate passati' if ok else 'GATE NON PASSATI'}")
    return 0 if ok else 1


# ─── A4 — eval LLM ───────────────────────────────────────────────────────────

def _predici(testo: str, profile: str | None) -> dict:
    """Catena reale: prompt congelato + payload + call + postprocess deterministico."""
    prompts = induttivo.carica_prompt()
    sys_incl = induttivo._corpo(prompts, "Inclosura")
    usr = induttivo._payload(testo, None, induttivo._OUT_INCLOSURA)
    llm = induttivo._call_asse("inclosura", sys_incl, usr, profile=profile)
    pre = induttivo.pre_detect_inclosura(testo)
    return induttivo._postprocess_inclosura(llm, pre)


def _campiona(records: list[dict], n: int) -> tuple[list[dict], list[dict]]:
    """Campione stratificato deterministico: USE/SELF_DIAGNOSIS d'ufficio, stride
    per sottotipo sui positivi; negativi con priorità alle trappole lessicali."""
    pos = [r for r in records if r.get("inclosura")]
    neg = [r for r in records if not r.get("inclosura")]
    sel_pos: list[dict] = [r for r in pos
                           if (r["inclosura"].get("modo") in ("USE", "SELF_DIAGNOSIS"))]
    per_st: dict[str, list[dict]] = {}
    for r in pos:
        if r not in sel_pos:
            per_st.setdefault(r["inclosura"].get("sottotipo", "?"), []).append(r)
    target_pos = max(len(sel_pos), int(n * 0.6))
    while len(sel_pos) < target_pos and any(per_st.values()):
        for st in sorted(per_st):
            if per_st[st] and len(sel_pos) < target_pos:
                sel_pos.append(per_st[st].pop(0))
    # negativi: prima le trappole (hit del detector su gold null), poi stride.
    trappole = [r for r in neg if induttivo.pre_detect_inclosura(r["testo"])]
    lisci    = [r for r in neg if r not in trappole]
    target_neg = max(6, n - len(sel_pos))
    sel_neg = trappole[:max(6, target_neg // 2)]
    stride = max(1, len(lisci) // max(1, target_neg - len(sel_neg)))
    sel_neg += lisci[::stride][: target_neg - len(sel_neg)]
    return sel_pos, sel_neg


def eval_llm(records: list[dict], n: int, profile: str | None, dump: bool) -> int:
    sel_pos, sel_neg = _campiona(records, n)
    print("=" * 66)
    print("EVAL LLM INCLOSURA (catena reale prompt+postprocess vs gold)")
    print(f"campione: {len(sel_pos)} positivi (USE/SELF d'ufficio) + {len(sel_neg)} negativi "
          f"(di cui {sum(1 for r in sel_neg if induttivo.pre_detect_inclosura(r['testo']))} trappole)")
    print("unità: PASSO isolato (gold per-passo; ≠ pipeline olistica su documento)")
    print("=" * 66)

    righe: list[dict] = []
    m1_ok = m1_n = 0          # forma su USE/DIAGNOSIS/SELF
    m1m_ok = m1m_n = 0        # forma su MENTION (regola: {presente, parziale})
    m2_fp = 0                 # falsi positivi su negativi
    m3_ok = m3_n = 0          # modo
    m4_ok = m4_n = 0          # risposta (indicativo)
    m5_ok = m5_n = 0          # sottotipo (indicativo)
    call_err = 0

    for r in sel_pos + sel_neg:
        out = _predici(r["testo"], profile)
        llm = out.get("llm") or {}
        err = isinstance(llm, dict) and "errore" in llm
        if err:
            call_err += 1
        g_incl = r.get("inclosura")
        riga = {"id": r["id"], "doc": r.get("doc", ""), "gold": bool(g_incl),
                "gold_sottotipo": (g_incl or {}).get("sottotipo", ""),
                "gold_modo": (g_incl or {}).get("modo", ""),
                "gold_polarita": (g_incl or {}).get("polarita", ""),
                "forma": out.get("forma"), "modo": out.get("modo"),
                "risposta": out.get("risposta_al_limite"),
                "sottotipo": (llm.get("sottotipo") if isinstance(llm, dict) else ""),
                "trasc": ((llm.get("trascendenza") or {}).get("vale") if isinstance(llm, dict) else None),
                "chius": ((llm.get("chiusura") or {}).get("vale") if isinstance(llm, dict) else None),
                "span_trasc": str(((llm.get("trascendenza") or {}).get("span") or ""))[:80] if isinstance(llm, dict) else "",
                "errore": (llm.get("errore", "") if isinstance(llm, dict) else ""),
                "testo": r["testo"][:200]}
        if err:
            riga["esito"] = "CALL_ERR"
        elif g_incl:
            gm = g_incl.get("modo", "")
            if gm == "MENTION":
                ok = out.get("forma") in ("presente", "parziale")
                m1m_ok += ok; m1m_n += 1
            else:
                ok = out.get("forma") == "presente"
                m1_ok += ok; m1_n += 1
            riga["esito"] = "M1 ok" if ok else "M1 MISS"
            if out.get("modo"):
                m3_ok += (out["modo"] == gm); m3_n += 1
            attese = _POLARITA_RISPOSTE.get(g_incl.get("polarita", ""), set())
            if attese and out.get("risposta_al_limite"):
                m4_ok += (out["risposta_al_limite"] in attese); m4_n += 1
            if riga["sottotipo"]:
                m5_ok += (riga["sottotipo"] == riga["gold_sottotipo"]); m5_n += 1
        else:
            # Criterio M2 rivisto (Σ_w, triage 2026-06-12): FP = il giudice
            # attribuisce l'USO dell'inclosura a un negativo. Un negativo
            # riconosciuto presente-nel-discorso (MENTION/DIAGNOSIS) non è FP.
            fp = out.get("forma") == "presente" and out.get("modo") == "USE"
            m2_fp += fp
            riga["esito"] = "M2 FP!" if fp else "M2 ok"
        righe.append(riga)
        print(f"  {r['id']:14s} {riga['esito']:8s} forma={riga['forma']} modo={riga['modo']} "
              f"(gold: {'+' + riga['gold_sottotipo'] if g_incl else 'null'}/{riga['gold_modo']})")

    n_neg = len(sel_neg)
    lo1, hi1 = _wilson(m1_ok, m1_n)
    lo2, hi2 = _wilson(m2_fp, n_neg)
    lo3, hi3 = _wilson(m3_ok, m3_n)
    print("\n" + "-" * 66)
    print(f"M1 forma=presente su USE/DIAG/SELF: {m1_ok}/{m1_n} = "
          f"{m1_ok / m1_n:.0%} [Wilson {lo1:.0%}-{hi1:.0%}]  gate ≥60%"
          if m1_n else "M1: n=0")
    if m1m_n:
        print(f"M1-MENTION (presente|parziale):     {m1m_ok}/{m1m_n} = {m1m_ok / m1m_n:.0%} (a parte, no gate)")
    print(f"M2 FP su negativi (presente∧USE):   {m2_fp}/{n_neg} = "
          f"{m2_fp / n_neg:.0%} [Wilson {lo2:.0%}-{hi2:.0%}]  gate ≤15%" if n_neg else "M2: n=0")
    print(f"M3 modo:                            {m3_ok}/{m3_n} = "
          f"{m3_ok / m3_n:.0%} [Wilson {lo3:.0%}-{hi3:.0%}]  gate ≥50%" if m3_n else "M3: n=0")
    if m4_n:
        print(f"M4 risposta~polarità (INDICATIVO):  {m4_ok}/{m4_n} = {m4_ok / m4_n:.0%} (mapping derivato, no gate)")
    if m5_n:
        print(f"M5 sottotipo (INDICATIVO):          {m5_ok}/{m5_n} = {m5_ok / m5_n:.0%}")
    print(f"call in errore: {call_err}")
    print("NB: strati USE(7)/SELF_DIAGNOSIS(4) rari → Wilson largo: certificazione DEBOLE su quei modi.")

    if dump:
        _OUT_DIR.mkdir(exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base = _OUT_DIR / f"eval_inclosura_{ts}"
        from resh import config as _cfg
        snap = _cfg.config_snapshot(profile)
        intest = (f"# Eval Inclosura — {ts}\n\nmodello: {snap.get('model')} ({snap.get('profile')}) · "
                  f"campione {len(sel_pos)}+{len(sel_neg)} · unità=passo isolato\n"
                  f"criteri: M1≥60% · M2(presente∧USE)≤15% (rivisto Σ_w 2026-06-12) · M3≥50% · M4/M5 indicativi\n\n")
        cols = ["id", "doc", "gold", "gold_sottotipo", "gold_modo", "gold_polarita",
                "forma", "modo", "risposta", "sottotipo", "trasc", "chius", "esito",
                "span_trasc", "errore", "testo"]
        md = intest + "| " + " | ".join(cols[:13]) + " |\n|" + "---|" * 13 + "\n"
        for x in righe:
            md += "| " + " | ".join(str(x.get(c, "")).replace("|", "\\|") for c in cols[:13]) + " |\n"
        base.with_suffix(".md").write_text(md, encoding="utf-8")
        with base.with_suffix(".csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(righe)
        print(f"\ndump: {base}.md / .csv")

    gate = ((m1_n == 0 or m1_ok / m1_n >= 0.60) and (n_neg == 0 or m2_fp / n_neg <= 0.15)
            and (m3_n == 0 or m3_ok / m3_n >= 0.50) and call_err == 0)
    print(f"\nVERDETTO EVAL LLM: {'OK — gate passati' if gate else 'GATE NON PASSATI'}")
    return 0 if gate else 1


# ─── A5 — stabilità (stesso input × 3 run) ───────────────────────────────────

def eval_stability(records: list[dict], profile: str | None) -> int:
    """5 record fissi (selezione deterministica per modo, id ordinati) × 3 run."""
    pos = sorted([r for r in records if r.get("inclosura")], key=lambda r: r["id"])
    neg = sorted([r for r in records if not r.get("inclosura")], key=lambda r: r["id"])
    use  = [r for r in pos if r["inclosura"].get("modo") == "USE"][:2]
    diag = [r for r in pos if r["inclosura"].get("modo") == "DIAGNOSIS"][:1]
    ment = [r for r in pos if r["inclosura"].get("modo") == "MENTION"][:1]
    sel = use + diag + ment + neg[:1]
    print("=" * 66)
    print(f"STABILITÀ INCLOSURA — {len(sel)} record × 3 run: {[r['id'] for r in sel]}")
    print("gate: forma 3/3 su ≥4/5 · trasc/chius 3/3 su ≥4/5 · 0 bad_json")
    print("=" * 66)
    stabili_forma = stabili_vale = 0
    bad_json = 0
    for r in sel:
        runs = [_predici(r["testo"], profile) for _ in range(3)]
        forme = [x.get("forma") for x in runs]
        vali = [(((x.get("llm") or {}).get("trascendenza") or {}).get("vale"),
                 ((x.get("llm") or {}).get("chiusura") or {}).get("vale")) for x in runs]
        bad_json += sum(1 for x in runs if (x.get("llm") or {}).get("bad_json"))
        f_st = len(set(forme)) == 1
        v_st = len(set(vali)) == 1
        stabili_forma += f_st
        stabili_vale += v_st
        print(f"  {r['id']:14s} forma={forme} {'STABILE' if f_st else 'INSTABILE'} · "
              f"vale={vali} {'STABILE' if v_st else 'INSTABILE'}")
    ok = stabili_forma >= 4 and stabili_vale >= 4 and bad_json == 0
    print(f"\nforma stabile: {stabili_forma}/5 · vale stabile: {stabili_vale}/5 · bad_json: {bad_json}")
    print(f"VERDETTO STABILITÀ: {'OK' if ok else 'GATE NON PASSATI'}")
    return 0 if ok else 1


# ─── A5 — parafrasi (set PRE-SCRITTI, deterministici) ────────────────────────

_PARAFRASI = {
    "sonda_use (atteso: presente in tutte)": [
        # originale = sonda di test_inclosura_e2e
        "Per tracciare i limiti del pensiero devo collocarmi oltre di essi: solo da lì "
        "vedo la totalità di ciò che può essere pensato. Ma io stesso penso mentre lo "
        "dico, e dunque sono dentro quella totalità che pretendo di osservare "
        "dall'esterno. Questa contraddizione non è un errore da dissolvere: è vera, e "
        "la logica deve imparare a contenerla senza esplodere.",
        "Se voglio delimitare ciò che può essere pensato, mi serve un punto di vista "
        "esterno al pensabile; eppure questo stesso delimitare è un atto di pensiero, "
        "quindi resto dentro il confine che pretendo di disegnare da fuori. Non è uno "
        "sbaglio da correggere: la contraddizione è reale e va sostenuta.",
        "Chi disegna il confine del dicibile deve sporgersi oltre il dicibile per "
        "vederlo intero; ma il suo disegnare è già un dire, e così egli abita il "
        "territorio che dichiarava di guardare dall'alto. Accolgo questa tensione "
        "come vera invece di scioglierla.",
    ],
    "chiusura_semantica_use (atteso: presente in tutte)": [
        # ispirato a Priest (1999): teoria semanticamente chiusa che parla di sé.
        "Questa teoria contiene il proprio predicato di verità: ogni suo enunciato, "
        "incluso questo, è valutabile dentro la teoria stessa. Per dirne la verità "
        "non serve un metalinguaggio: la teoria abbraccia la totalità dei propri "
        "enunciati pur essendo uno di essi il presente.",
        "Il linguaggio di cui parlo include 'è vero' e 'denota' applicabili a ogni "
        "sua frase, compresa quella che state leggendo: descrivo da dentro la "
        "totalità delle frasi, e la descrizione è una di loro.",
        "Non esiste un fuori da cui giudicare questi enunciati: il predicato di "
        "verità appartiene allo stesso linguaggio che valuta, e questo enunciato "
        "si valuta da sé mentre valuta tutti gli altri.",
    ],
    "negativo_espositivo (atteso: MAI presente)": [
        "La fotosintesi clorofilliana converte l'energia luminosa in energia chimica: "
        "le piante assorbono anidride carbonica e acqua e producono glucosio e "
        "ossigeno. Il processo avviene nei cloroplasti e dipende dall'intensità "
        "della luce e dalla temperatura.",
        "Nelle piante, la luce solare viene trasformata in energia chimica mediante "
        "la fotosintesi: dall'anidride carbonica e dall'acqua si ottengono zuccheri "
        "e ossigeno, all'interno dei cloroplasti, con efficienza variabile secondo "
        "luce e temperatura.",
        "Il glucosio prodotto dalle piante deriva dalla fotosintesi, che usa la luce "
        "per combinare acqua e anidride carbonica nei cloroplasti, liberando "
        "ossigeno; temperatura e illuminazione ne regolano la resa.",
    ],
}


def eval_paraphrase(profile: str | None) -> int:
    print("=" * 66)
    print("SENSIBILITÀ A PARAFRASI — 3 set pre-scritti × 3 versioni")
    print("gate: forma stabile in ≥2/3 set · set negativo mai 'presente'")
    print("=" * 66)
    set_stabili = 0
    neg_pulito = True
    for nome, versioni in _PARAFRASI.items():
        forme = [_predici(v, profile).get("forma") for v in versioni]
        stabile = len(set(forme)) == 1
        set_stabili += stabile
        if nome.startswith("negativo") and "presente" in forme:
            neg_pulito = False
        print(f"  {nome:48s} forme={forme} {'STABILE' if stabile else 'INSTABILE'}")
    ok = set_stabili >= 2 and neg_pulito
    print(f"\nset stabili: {set_stabili}/3 · negativo pulito: {neg_pulito}")
    print(f"VERDETTO PARAFRASI: {'OK' if ok else 'GATE NON PASSATI'}")
    return 0 if ok else 1


# ─── main ────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--detector", action="store_true", help="solo pre-detector (0 call)")
    ap.add_argument("--stability", action="store_true")
    ap.add_argument("--paraphrase", action="store_true")
    ap.add_argument("--n", type=int, default=40, help="dimensione campione eval LLM")
    ap.add_argument("--profile", default="gemini-3.1-lite")
    ap.add_argument("--dump", action="store_true", help="tabella per-record md+csv")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

    records = carica_gold()
    if args.detector:
        return eval_detector(records)
    rc = 0
    if args.stability:
        rc |= eval_stability(records, args.profile)
    if args.paraphrase:
        rc |= eval_paraphrase(args.profile)
    if not (args.stability or args.paraphrase):
        rc = eval_llm(records, args.n, args.profile, args.dump)
    return rc


if __name__ == "__main__":
    sys.exit(main())
