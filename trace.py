"""resh/trace.py — osservabilità delle chiamate LLM (salva + rende visibile).

Ogni chiamata che passa dall'hub (`config.call_llm_text`) viene tracciata qui:
request (system/user troncati + sizes), output grezzo e sanificato, `finish_reason`,
token usati, latenza, e soprattutto un FLAG di salute:

  - `ok`        : output non vuoto, terminato normalmente E (se JSON) parsabile
  - `empty`     : dopo sanitize il content è vuoto → la call ha «girato a vuoto»
                  (tipico dei reasoning model che esauriscono i token in <think>)
  - `truncated` : finish_reason == 'length' → tagliato (alza max_tokens)
  - `bad_json`  : content presente ma `json.loads` fallito (JSON invalido/incompleto)
                  → la call NON è sana benché il modello abbia risposto. Distinto da
                  `error` (che è un fallimento HTTP/eccezione, non di parsing).
  - `error`     : eccezione/HTTP error (es. modello non caricato su LM Studio)

«Salva»: append-only su `<package>/.cache/resh/llm_trace.jsonl` (ancorato al
package via `cache.CACHE_DIR`, non al cwd; override radice: env `P3_RESH_CACHE`).
«Rende visibile»: con env `P3_LLM_VERBOSE=1` stampa una riga di sintesi su stderr
ad ogni call; `python -m resh.trace` mostra riassunto + ultime anomalie.

Disattivabile del tutto con `P3_RESH_TRACE_DISABLE=1`.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

from .cache import CACHE_DIR

TRACE_PATH = CACHE_DIR / "llm_trace.jsonl"


def classifica(*, sanitized: str, raw: str, finish_reason: str | None,
               errore: str | None, parse_ok: bool | None = None) -> str:
    # `parse_ok` è valorizzato solo dalle call JSON: False = json.loads fallito.
    # Ha precedenza su `errore` (che qui porta solo il dettaglio del parse), così
    # un parse fallito risulta `bad_json` e non si confonde con un errore HTTP.
    if parse_ok is False:
        return "bad_json"
    if errore:
        return "error"
    if finish_reason == "length" and not (sanitized or "").strip():
        return "truncated"          # tagliato E vuoto: ha ragionato senza concludere
    if not (sanitized or "").strip():
        return "empty"
    if finish_reason == "length":
        return "truncated"
    return "ok"


def record(*, tag: str, profile: str, model: str, system: str, user: str,
           raw: str = "", sanitized: str = "", finish_reason: str | None = None,
           usage: dict | None = None, latency_ms: int = 0,
           errore: str | None = None, parse_ok: bool | None = None) -> str:
    """Registra una call e ritorna il flag di salute. Mai solleva (best-effort).

    `parse_ok` (solo call JSON): True/False = esito di `json.loads`. None = call di
    testo (parsing non pertinente). Un False produce flag `bad_json`.
    """
    flag = classifica(sanitized=sanitized, raw=raw, finish_reason=finish_reason,
                      errore=errore, parse_ok=parse_ok)
    if os.getenv("P3_RESH_TRACE_DISABLE") == "1":
        return flag
    rec = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "flag": flag,
        "tag": tag,
        "profile": profile,
        "model": model,
        "finish_reason": finish_reason,
        "latency_ms": latency_ms,
        "usage": usage or {},
        "len_user": len(user or ""),
        "len_raw": len(raw or ""),
        "len_out": len(sanitized or ""),
        "system_head": (system or "")[:120],
        "user_head": (user or "")[:160],
        "out_head": (sanitized or "")[:200],
        "errore": (errore or "")[:300] or None,
    }
    if parse_ok is not None:
        rec["parse_ok"] = parse_ok
    try:
        TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TRACE_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass
    if os.getenv("P3_LLM_VERBOSE") == "1":
        u = rec["usage"]
        tok = f"{u.get('completion_tokens','?')}tok" if u else "?tok"
        print(f"[ऋ-llm] {flag:<9} {tag:<16} {model:<22} "
              f"{latency_ms:>6}ms {tok:>8} out={rec['len_out']}"
              + (f"  ERR: {rec['errore'][:80]}" if errore else ""),
              file=sys.stderr, flush=True)
    return flag


# ─── lettura / visibilità ─────────────────────────────────────────────────────

def leggi(n: int = 20, solo_anomalie: bool = False) -> list[dict]:
    if not TRACE_PATH.exists():
        return []
    out = []
    for line in TRACE_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if solo_anomalie and r.get("flag") == "ok":
            continue
        out.append(r)
    return out[-n:]


def riassunto() -> dict:
    """Conteggi per modello × flag su tutta la traccia."""
    import collections
    per_modello = collections.defaultdict(lambda: collections.Counter())
    tot = collections.Counter()
    for r in leggi(n=10**9):
        per_modello[r.get("model", "?")][r.get("flag", "?")] += 1
        tot[r.get("flag", "?")] += 1
    return {"totale": dict(tot), "per_modello": {m: dict(c) for m, c in per_modello.items()}}


def _main() -> None:
    rias = riassunto()
    print("=== Riassunto traccia LLM ===")
    print("totale:", rias["totale"])
    for m, c in rias["per_modello"].items():
        print(f"  {m:<26} {c}")
    anom = leggi(n=15, solo_anomalie=True)
    if anom:
        print("\n=== Ultime anomalie (empty/truncated/error) ===")
        for r in anom:
            print(f"  {r['ts']} {r['flag']:<9} {r['tag']:<16} {r['model']:<22} "
                  + (r.get("errore") or r.get("out_head", ""))[:90])
    else:
        print("\nNessuna anomalia registrata.")


if __name__ == "__main__":
    _main()
