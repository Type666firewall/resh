"""Campagna di STRESS TEST di resh — comportamento di sistema, dati grezzi, falle.

Livello: STRESS (≠ smoke ≠ batterie ≠ eval). Corpus CONGELATO in
`tests/corpus_stress/` con aspettative PRE-REGISTRATE nel manifest.

Fasi (indipendenti, dati grezzi JSON in tests/eval_out/stress/):
  F0  riproducibilità det ×2 (S1,S2,S3,S6)      0 call   gate: ε+componenti identici
  F2  sanità ordinale ε sul corpus               0 call   gate: coppie manifest rispettate
  F1  stabilità ind ×3 (S1,S2,S3)               ~36 call  gate: corno/forma 3/3 su ≥2/3
  F3  salute call della campagna (trace)         0 call   gate: 0 error; bad_json+trunc ≤5%
  F4  coerenza Quadro (S1,S2,S4)                ~6 call   gate: scartati=errori; copertura ok
  F5  drift documento S5 ×2 (cache SEPARATE)   ~2×60     gate: det identico tra run

Report finale: `python -m resh.tests.stress_resh --report` compone i JSON in
`tests/report_stress_<data>.md` (formatter deterministico, dati grezzi inclusi,
sezione FALLE con triage).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

_BASE = Path(__file__).resolve().parent
_CORPUS = _BASE / "corpus_stress"
_OUT = _BASE / "eval_out" / "stress"
_VENV_PY = sys.executable


def _manifest() -> dict:
    return json.loads((_CORPUS / "manifest.json").read_text(encoding="utf-8"))


def _testo(sid: str) -> str:
    m = _manifest()
    item = next(t for t in m["testi"] if t["id"] == sid)
    p = _CORPUS / item["file"]
    raw = p.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != item["sha256"]:
        raise RuntimeError(f"{sid}: sha256 DIVERGE dal manifest — corpus non congelato!")
    return raw.decode("utf-8", errors="replace")


def _salva(fase: str, dati: dict) -> Path:
    """Salva l'esito di fase: `{fase}.json` resta il puntatore corrente (il
    report lo legge), MA ogni esecuzione viene anche archiviata con timestamp
    in `storico/` — fix 2026-06-12: prima ogni run sovrascriveva la storia
    (falla aperta del report stress 2026-06-11), come per gli eval."""
    _OUT.mkdir(parents=True, exist_ok=True)
    dati["_ts"] = datetime.datetime.now().isoformat(timespec="seconds")
    p = _OUT / f"{fase}.json"
    p.write_text(json.dumps(dati, ensure_ascii=False, indent=2), encoding="utf-8")
    storico = _OUT / "storico"
    storico.mkdir(exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    (storico / f"{fase}_{ts}.json").write_text(
        json.dumps(dati, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def _det(testo: str) -> dict:
    from resh.core import analizza
    r = analizza(testo, verbose=False)
    return {"eps_resh": r.eps_resh, "componenti": r.componenti_epsilon,
            "n_patologie": len(r.patologie_strutturate),
            "malafede_mod": r.malafede_mod}


# ─── F0 — riproducibilità deterministica ─────────────────────────────────────

def fase_f0() -> int:
    print("=" * 66)
    print("F0 — RIPRODUCIBILITÀ DET ×2 (S1,S2,S3,S6) · gate: identici bit-a-bit")
    print("=" * 66)
    esiti, falle = {}, []
    for sid in ("S1", "S2", "S3", "S6"):
        t = _testo(sid)
        a, b = _det(t), _det(t)
        identico = a == b
        esiti[sid] = {"run1": a, "run2": b, "identico": identico}
        print(f"  {sid}: ε={a['eps_resh']} vs {b['eps_resh']} → "
              f"{'IDENTICO' if identico else 'DIVERGE'}")
        if not identico:
            diff = {k: (a["componenti"].get(k), b["componenti"].get(k))
                    for k in set(a["componenti"]) | set(b["componenti"])
                    if a["componenti"].get(k) != b["componenti"].get(k)}
            falle.append({"id": f"F0-{sid}", "evidenza": f"componenti divergenti: {diff}"})
            print(f"     diff: {diff}")
    _salva("F0", {"esiti": esiti, "falle": falle, "gate": not falle})
    print(f"\nVERDETTO F0: {'OK' if not falle else f'{len(falle)} FALLE'}")
    return 0 if not falle else 1


# ─── F2 — sanità ordinale ────────────────────────────────────────────────────

def fase_f2() -> int:
    print("=" * 66)
    print("F2 — SANITÀ ORDINALE ε · gate: coppie pre-registrate nel manifest")
    print("=" * 66)
    m = _manifest()
    eps: dict[str, float] = {}
    for sid in ("S1", "S2", "S3", "S6", "S7"):
        eps[sid] = _det(_testo(sid))["eps_resh"]
        print(f"  {sid}: ε = {eps[sid]}")
    # S5 (126K): valore di riferimento già misurato e persistito (Ψ_fb00ac072cb8_D001).
    eps["S5"] = 0.5147
    print(f"  S5: ε_doc = {eps['S5']} (riferimento persistito Ψ_fb00ac072cb8_D001)")
    falle = []
    for a, b in m["ordine_eps"]:
        ok = eps[a] < eps[b]
        print(f"  ε({a})={eps[a]} < ε({b})={eps[b]} → {'OK' if ok else 'VIOLATA'}")
        if not ok:
            falle.append({"id": f"F2-{a}<{b}", "evidenza": f"ε({a})={eps[a]} ≥ ε({b})={eps[b]}"})
    _salva("F2", {"eps": eps, "coppie": m["ordine_eps"], "falle": falle, "gate": not falle})
    print(f"\nVERDETTO F2: {'OK' if not falle else f'{len(falle)} FALLE'}")
    return 0 if not falle else 1


# ─── F1 — stabilità induttiva ×3 ─────────────────────────────────────────────

def fase_f1(profile: str | None) -> int:
    from resh.lambda_space import G, resolve
    _ind = resolve(G.ANALIZZA_INDUTTIVO)
    print("=" * 66)
    print("F1 — STABILITÀ IND ×3 (S1,S2,S3; arsenale+trilemma+inclosura+O)")
    print("gate: corno 3/3 su ≥2/3 testi · forma 3/3 su ≥2/3 · accordo per-campo riportato")
    print("=" * 66)
    esiti, falle = {}, []
    stab_corno = stab_forma = 0
    for sid in ("S1", "S2", "S3"):
        t = _testo(sid)
        runs = []
        for _ in range(3):
            r = _ind(t, assi=["arsenale", "trilemma", "inclosura"],
                     estrai_o=True, sintesi=False, profile=profile).as_dict()
            runs.append({
                "corno": ((r.get("trilemma") or {}).get("llm") or {}).get("corno"),
                "modo_tri": ((r.get("trilemma") or {}).get("llm") or {}).get("modo"),
                "forma": (r.get("inclosura") or {}).get("forma"),
                "modo_incl": (r.get("inclosura") or {}).get("modo"),
                "o_dichiarato": ((r.get("obiettivo") or {}).get("dichiarato") or "")[:80],
                "errori": [k for k in ("arsenale",) if "errore" in (r.get(k) or {})],
            })
        campi = {c: [x[c] for x in runs] for c in ("corno", "modo_tri", "forma", "modo_incl")}
        st = {c: len(set(v)) == 1 for c, v in campi.items()}
        stab_corno += st["corno"]
        stab_forma += st["forma"]
        esiti[sid] = {"runs": runs, "stabile": st}
        print(f"  {sid}: corno={campi['corno']} {'ST' if st['corno'] else 'INSTAB'} · "
              f"forma={campi['forma']} {'ST' if st['forma'] else 'INSTAB'} · "
              f"modo_tri={campi['modo_tri']} · modo_incl={campi['modo_incl']}")
        for c, ok in st.items():
            if not ok:
                falle.append({"id": f"F1-{sid}-{c}", "evidenza": f"{c}={campi[c]}"})
    gate = stab_corno >= 2 and stab_forma >= 2
    _salva("F1", {"esiti": esiti, "stab_corno": stab_corno, "stab_forma": stab_forma,
                  "falle": falle, "gate": gate})
    print(f"\ncorno stabile: {stab_corno}/3 · forma stabile: {stab_forma}/3")
    print(f"VERDETTO F1: {'OK' if gate else 'GATE NON PASSATO'}")
    return 0 if gate else 1


# ─── F3 — salute call della campagna ─────────────────────────────────────────

def fase_f3(dal_ts: str | None) -> int:
    from resh.cache import CACHE_DIR
    print("=" * 66)
    print("F3 — SALUTE CALL (trace della campagna) · gate: 0 error; bad_json+trunc ≤5%")
    print("=" * 66)
    trace = CACHE_DIR / "llm_trace.jsonl"
    if dal_ts is None:
        # default: finestra = oggi
        dal_ts = datetime.date.today().isoformat()
    righe = []
    if trace.exists():
        for line in trace.read_text(encoding="utf-8").splitlines():
            try:
                j = json.loads(line)
            except json.JSONDecodeError:
                continue
            if j.get("ts", "") >= dal_ts:
                righe.append(j)
    import collections
    flags = collections.Counter(j.get("flag") for j in righe)
    n = len(righe)
    anomalie = [f"{j['ts']} {j.get('tag')} [{j.get('flag')}]" for j in righe
                if j.get("flag") not in ("ok",)]
    err = flags.get("error", 0)
    sporche = flags.get("bad_json", 0) + flags.get("truncated", 0)
    print(f"  finestra dal {dal_ts}: {n} call · flag: {dict(flags)}")
    for a in anomalie[:15]:
        print(f"    ⚠ {a}")
    gate = err == 0 and (n == 0 or sporche / n <= 0.05)
    falle = []
    if not gate:
        falle.append({"id": "F3-salute", "evidenza": f"error={err}, sporche={sporche}/{n}"})
    _salva("F3", {"dal_ts": dal_ts, "n": n, "flags": dict(flags),
                  "anomalie": anomalie, "falle": falle, "gate": gate})
    print(f"\nVERDETTO F3: {'OK' if gate else 'GATE NON PASSATO'}")
    return 0 if gate else 1


# ─── F4 — coerenza Quadro ────────────────────────────────────────────────────

def fase_f4(profile: str | None) -> int:
    from resh.lambda_space import G, resolve
    _ind = resolve(G.ANALIZZA_INDUTTIVO)
    _aggrega = resolve(G.AGGREGA_QUADRO)
    print("=" * 66)
    print("F4 — COERENZA QUADRO (S1,S2,S4) · gate: scartati=errori ind; 0 anomalie copertura;")
    print("     inclosura nei giudizi a parità")
    print("=" * 66)
    esiti, falle = {}, []
    for sid in ("S1", "S2", "S4"):
        t = _testo(sid)
        det = _det(t)
        det_min = {"eps_resh": det["eps_resh"], "componenti_epsilon": det["componenti"]}
        ind = _ind(t, assi=["arsenale", "trilemma", "inclosura"],
                   estrai_o=True, sintesi=False, profile=profile).as_dict()
        q = _aggrega(det_min, ind)
        # errori attesi: dict con 'errore' nelle sotto-unità considerate dal quadro
        unita = [ind.get("arsenale"), (ind.get("trilemma") or {}).get("llm"),
                 (ind.get("inclosura") or {}).get("llm")]
        err_ind = sum(1 for u in unita if isinstance(u, dict) and "errore" in u)
        incl_ok = any(c.sotto_unita == "inclosura" for c in q.giudizi_parita + q.scartati)
        anomalie = (q.meta or {}).get("anomalie_copertura", [])
        problemi = []
        if q.n_scartati != err_ind:
            problemi.append(f"n_scartati={q.n_scartati} ≠ errori ind={err_ind}")
        if anomalie:
            problemi.append(f"anomalie copertura: {anomalie}")
        if not incl_ok:
            problemi.append("inclosura assente dal quadro")
        if q.eps_resh != det["eps_resh"]:
            problemi.append("ε NON verbatim nel quadro!")
        esiti[sid] = {"eps": det["eps_resh"], "n_scartati": q.n_scartati,
                      "err_ind": err_ind, "problemi": problemi}
        print(f"  {sid}: ε={det['eps_resh']} scartati={q.n_scartati} err_ind={err_ind} "
              f"→ {'OK' if not problemi else problemi}")
        for p in problemi:
            falle.append({"id": f"F4-{sid}", "evidenza": p})
    _salva("F4", {"esiti": esiti, "falle": falle, "gate": not falle})
    print(f"\nVERDETTO F4: {'OK' if not falle else f'{len(falle)} FALLE'}")
    return 0 if not falle else 1


# ─── F5 — drift documento (cache SEPARATE via subprocess) ────────────────────

_F5_SCRIPT = r"""
import sys, json
sys.path.insert(0, r"{root}")
sys.stdout.reconfigure(encoding="utf-8")
from resh import documento
testo = open(r"{testo}", encoding="utf-8").read()
rap = documento.analizza_documento_induttivo(
    testo, fonte="S5 stress F5", resume=True, max_call_budget={budget},
    target_char=6000, profile={profile!r})
d = rap.as_dict()
out = {{"eps_doc": d["eps_doc"], "eps_per_chunk": d["eps_per_chunk"],
       "saltati": d["saltati"], "call": d["meta"].get("call_eseguite")}}
open(r"{out}", "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False))
print("F5 run done:", out["eps_doc"])
"""


def fase_f5(profile: str | None, budget: int) -> int:
    print("=" * 66)
    print(f"F5 — DRIFT DOCUMENTO S5 ×2 run, cache SEPARATE, budget {budget}/run")
    print("gate: ε det per-chunk IDENTICO tra i run (sui chunk analizzati da entrambi)")
    print("=" * 66)
    item = next(t for t in _manifest()["testi"] if t["id"] == "S5")
    testo_path = _CORPUS / item["file"]
    _OUT.mkdir(parents=True, exist_ok=True)
    risultati = []
    for i in (1, 2):
        cache = Path(tempfile.mkdtemp(prefix=f"resh_f5_run{i}_"))
        outj = _OUT / f"F5_run{i}.json"
        script = _F5_SCRIPT.format(root=str(_BASE.parent.parent), testo=str(testo_path),
                                   budget=budget, profile=profile, out=str(outj))
        env = dict(os.environ, P3_RESH_CACHE=str(cache),
                   PYTHONPATH=str(_BASE.parent.parent))
        print(f"  run {i} (cache {cache.name})...")
        r = subprocess.run([_VENV_PY, "-c", script], env=env,
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            print(f"  run {i} FALLITO:\n{(r.stderr or '')[-800:]}")
            _salva("F5", {"errore": (r.stderr or "")[-2000:], "gate": False})
            return 1
        risultati.append(json.loads(outj.read_text(encoding="utf-8")))
        print(f"  run {i}: ε_doc={risultati[-1]['eps_doc']} call={risultati[-1]['call']}")
    e1 = {c["id"]: c["eps"] for c in risultati[0]["eps_per_chunk"]}
    e2 = {c["id"]: c["eps"] for c in risultati[1]["eps_per_chunk"]}
    comuni = sorted(set(e1) & set(e2))
    diff = {cid: (e1[cid], e2[cid]) for cid in comuni if e1[cid] != e2[cid]}
    falle = ([{"id": "F5-drift-det", "evidenza": f"chunk det divergenti: {diff}"}]
             if diff else [])
    print(f"  chunk comuni: {len(comuni)} · divergenti det: {len(diff)}")
    _salva("F5", {"run": risultati, "chunk_comuni": comuni, "diff_det": diff,
                  "falle": falle, "gate": not diff})
    print(f"\nVERDETTO F5: {'OK' if not diff else 'DRIFT DET RILEVATO'}")
    return 0 if not diff else 1


# ─── report ──────────────────────────────────────────────────────────────────

def report() -> int:
    from resh import config as _cfg
    snap = _cfg.config_snapshot(None)
    m = _manifest()
    oggi = datetime.date.today().isoformat()
    out = [f"# Report STRESS resh — {oggi}", "",
           f"firma: modello {snap.get('model')} ({snap.get('profile')}) · "
           f"ts {datetime.datetime.now().isoformat(timespec='seconds')}",
           "", "> Formatter deterministico. Dati grezzi per fase, criteri pre-dichiarati,",
           "> falle con triage. Livello STRESS: comportamento di sistema, non capacità",
           "> vs gold (per quella: eval_inclosura/eval_trilemma).", "",
           "## Corpus e aspettative (verbatim dal manifest)", ""]
    for t in m["testi"]:
        out.append(f"- **{t['id']}** `{t['file']}` ({t['char']} char, sha256 "
                   f"`{t['sha256'][:16]}…`): {json.dumps(t['aspettative'], ensure_ascii=False)}")
    out.append(f"\nOrdine ε impegnativo: {m['ordine_eps']}")
    tutte_falle = []
    for fase in ("F0", "F2", "F1", "F3", "F4", "F5"):
        p = _OUT / f"{fase}.json"
        out.append(f"\n## {fase}")
        if not p.exists():
            out.append("*(non eseguita)*")
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        out.append(f"gate: {'✅ PASSATO' if d.get('gate') else '❌ NON PASSATO'} · ts {d.get('_ts')}")
        out.append("```json")
        d_compatto = {k: v for k, v in d.items() if k not in ("falle", "gate", "_ts")}
        out.append(json.dumps(d_compatto, ensure_ascii=False, indent=2)[:4000])
        out.append("```")
        for f in d.get("falle", []):
            tutte_falle.append({**f, "fase": fase})
    out.append("\n## FALLE EMERSE — triage")
    if not tutte_falle:
        out.append("\nNessuna falla nelle fasi eseguite.")
    else:
        out.append("\n| id | fase | evidenza grezza | classe (da triage Σ_w/assistente) |")
        out.append("|---|---|---|---|")
        for f in tutte_falle:
            out.append(f"| {f['id']} | {f['fase']} | {str(f['evidenza'])[:160]} | DA CLASSIFICARE |")
    dst = _BASE / f"report_stress_{oggi}.md"
    dst.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"report: {dst}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fase", default=None,
                    choices=["F0", "F1", "F2", "F3", "F4", "F5", "all"])
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--profile", default=None, help="default: profilo attivo (gemma-31)")
    ap.add_argument("--budget", type=int, default=60, help="budget call F5 per run")
    ap.add_argument("--dal-ts", default=None, help="F3: inizio finestra trace (ISO)")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass
    if args.report:
        return report()
    rc = 0
    fasi = ["F0", "F2", "F1", "F3", "F4", "F5"] if args.fase == "all" else [args.fase]
    for f in fasi:
        if f == "F0":
            rc |= fase_f0()
        elif f == "F2":
            rc |= fase_f2()
        elif f == "F1":
            rc |= fase_f1(args.profile)
        elif f == "F3":
            rc |= fase_f3(args.dal_ts)
        elif f == "F4":
            rc |= fase_f4(args.profile)
        elif f == "F5":
            rc |= fase_f5(args.profile, args.budget)
    return rc


if __name__ == "__main__":
    sys.exit(main())
