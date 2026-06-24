"""resh/cache.py — Disk cache deterministica per moduli deterministici.

Chiave = sha256(testo || module_version). Valori serializzati come JSON
(numpy convertito a list). Decoratore `@cached(module_version="v1")` per
funzioni pure che ritornano dict / list / scalari.

Path: `<package>/.cache/resh/{hash}.json` — ANCORATO alla directory del package
(non al cwd: due lanci da directory diverse usavano due cache distinte → falsi
"0 call"/trace frammentato). Override esplicito: env `P3_RESH_CACHE` (radice).
`CACHE_DIR` qui è l'unica fonte: trace/documento/obiettivo/induttivo la importano.
No cleanup automatico nel
flusso di `cache_set`. La cache è un artefatto di test (non infrastruttura
agenti); per la gestione manuale dello spazio: `cache_size()` (report read-only)
e `prune_cache(max_files=…, max_age_days=…)` (cancellazione OPT-IN, mai automatica).
"""

from __future__ import annotations

import hashlib
import json
import os
from functools import wraps
from pathlib import Path
from typing import Any, Callable

import numpy as np


def _cache_root() -> Path:
    env = os.getenv("P3_RESH_CACHE")
    return Path(env) if env else Path(__file__).resolve().parent / ".cache"


CACHE_DIR = _cache_root() / "resh"


def _ensure_dir() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def _key(testo: str, module_version: str, extra: str = "") -> str:
    h = hashlib.sha256()
    h.update(module_version.encode("utf-8"))
    h.update(b"\x00")
    h.update(testo.encode("utf-8"))
    if extra:
        h.update(b"\x00")
        h.update(extra.encode("utf-8"))
    return h.hexdigest()[:48]


def _to_native(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_native(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def cache_get(testo: str, module_version: str, extra: str = "") -> Any | None:
    if os.getenv("P3_RESH_CACHE_DISABLE") == "1":
        return None
    path = _ensure_dir() / f"{_key(testo, module_version, extra)}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def cache_set(testo: str, module_version: str, value: Any, extra: str = "") -> None:
    if os.getenv("P3_RESH_CACHE_DISABLE") == "1":
        return
    path = _ensure_dir() / f"{_key(testo, module_version, extra)}.json"
    try:
        path.write_text(json.dumps(_to_native(value), ensure_ascii=False),
                        encoding="utf-8")
    except OSError:
        pass


def cache_size() -> dict:
    """Report della cache su disco (`.cache/resh/`): n. file e byte totali.
    Read-only — non cancella nulla."""
    if not CACHE_DIR.exists():
        return {"files": 0, "bytes": 0, "path": str(CACHE_DIR)}
    files = list(CACHE_DIR.glob("*.json"))
    return {"files": len(files),
            "bytes": sum(f.stat().st_size for f in files),
            "path": str(CACHE_DIR)}


def prune_cache(max_files: int | None = None, max_age_days: float | None = None) -> int:
    """Pulizia OPT-IN della cache (artefatto di test, non infrastruttura agenti):
    cancella SOLO se invocata esplicitamente — mai automatica nel flusso di
    `cache_set`. Rimuove i file più vecchi oltre `max_files` e/o più vecchi di
    `max_age_days`. Ritorna il numero di file rimossi."""
    if not CACHE_DIR.exists():
        return 0
    files = sorted(CACHE_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime)
    da_rimuovere: list[Path] = []
    if max_age_days is not None:
        import time
        limite = time.time() - max_age_days * 86400.0
        da_rimuovere += [f for f in files if f.stat().st_mtime < limite]
    if max_files is not None and len(files) > max_files:
        # i più vecchi in eccesso (escludendo già marcati)
        eccesso = files[: len(files) - max_files]
        da_rimuovere += [f for f in eccesso if f not in da_rimuovere]
    n = 0
    for f in da_rimuovere:
        try:
            f.unlink()
            n += 1
        except OSError:
            pass
    return n


def cached(module_version: str = "v1") -> Callable:
    """Decoratore per funzioni `(testo: str, ...) -> dict|list|scalar`.

    Cache key = sha256(testo + module_version). Args/kwargs extra non entrano
    nella chiave — usare solo per funzioni in cui il primo argomento è il
    contenuto canonico (testo).
    """
    def deco(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(testo: str, *args, **kwargs):
            hit = cache_get(testo, module_version, extra=fn.__name__)
            if hit is not None:
                return hit
            out = fn(testo, *args, **kwargs)
            cache_set(testo, module_version, out, extra=fn.__name__)
            return out
        return wrapper
    return deco
