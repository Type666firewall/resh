"""resh/config.py — Hub LLM centralizzato (key, endpoint, modelli, profili).

Punto UNICO di accesso agli LLM per tutto `resh` (e, a tendere, per gli altri
agenti P3). Regola P3 O-18/§5.26: **ogni modulo che chiama un LLM passa da
`config.get_llm_client()` / `config.call_llm_json()`** — mai hardcodare
base_url/api_key/model nei moduli chiamanti. Lo switch di backend è prerogativa
di Σ_w via env `P3_ACTIVE_PROFILE` o `P3_LLM_*`.

Cosa accentra:
  - **Keystore** (`API_KEYS`): le chiavi che possiedo/acquisirò, una per provider.
    Override sempre possibile via env (le env vincono sul valore in file).
  - **Profili** (`PROFILES`): per ogni modello che uso — provider, endpoint,
    nome-modello, reasoning, max_tokens/temperature di default, finestra di
    contesto, note. Aggiungere un modello = aggiungere una riga qui.
  - **LM Studio**: profili locali + auto-detect del modello caricato via
    `/v1/models` (così non devo riscrivere il nome a ogni swap di modello).
  - **Client**: `get_llm_client()` restituisce un client OpenAI-compatibile
    (Gemini, OpenAI e LM Studio espongono tutti l'API OpenAI).

Tutti i backend usati (Google AI Studio / OpenAI / LM Studio / llama.cpp)
parlano il protocollo OpenAI, quindi un solo `openai.OpenAI` li copre cambiando
solo `base_url` + `api_key` + `model`.

HW locale di riferimento (per i profili `local`): i5-13600KF (14C/20T),
32 GB DDR5, RTX 4060 8 GB VRAM. → su LM Studio tenere i pesi entro ~7 GB VRAM
(modelli 7-8B quantizzati Q4/Q5 con GPU offload pieno; oltre, offload parziale CPU).
"""

from __future__ import annotations

import contextvars
import json
import os
import threading
import time
from dataclasses import dataclass, replace
from functools import lru_cache
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Lingua attiva — ContextVar, non un attributo di modulo mutabile: isolata per
# task asyncio, quindi due analisi concorrenti in lingue diverse nello stesso
# processo (es. mcp_server.py con richieste interlacciate) non si pestano i
# piedi. Set all'ingresso (core.analizza/analizza_async, documento.py), letta
# dai gamma con `config.LANG.get()`. Default "it" (env P3_LANG solo come seed
# iniziale del processo, non riletta a ogni call).
# ─────────────────────────────────────────────────────────────────────────────
LANG: contextvars.ContextVar[str] = contextvars.ContextVar(
    "resh_lang", default=os.getenv("P3_LANG", "it"))


# ─────────────────────────────────────────────────────────────────────────────
# Keystore — una chiave per provider. Le env `*_API_KEY` vincono SEMPRE su questi
# default. Le chiavi gratuite (Google AI Studio) hanno quota req/min e req/giorno.
# MAI chiavi hardcoded qui (il file è versionato): metterle in `_keys_local.py`
# (gitignored, dict `KEYS = {provider: key}`) oppure esportarle via env.
# ─────────────────────────────────────────────────────────────────────────────
try:
    from ._keys_local import KEYS as _KEYS_LOCAL    # locale, MAI versionato
except ImportError:
    _KEYS_LOCAL = {}

API_KEYS = {
    # Google AI Studio (Gemini) — chiave gratuita con quota limitata.
    "google":    os.getenv("P3_GEMINI_API_KEY") or _KEYS_LOCAL.get("google", ""),
    # Provider a pagamento — riempire quando acquisto la chiave (o via env).
    "openai":    os.getenv("OPENAI_API_KEY", ""),
    "anthropic": os.getenv("ANTHROPIC_API_KEY", ""),
    "deepseek":  os.getenv("DEEPSEEK_API_KEY", ""),
    "groq":      os.getenv("GROQ_API_KEY", ""),
    "openrouter": os.getenv("OPENROUTER_API_KEY", ""),
    # Backend locali: nessuna chiave reale richiesta.
    "local":     "lm-studio",
}

# Endpoint per provider (OpenAI-compatibili).
ENDPOINTS = {
    "google":     "https://generativelanguage.googleapis.com/v1beta/openai/",
    "openai":     "https://api.openai.com/v1",
    "deepseek":   "https://api.deepseek.com/v1",
    "groq":       "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "lmstudio":   os.getenv("P3_LMSTUDIO_URL", "http://127.0.0.1:1234/v1"),
    "llamacpp":   os.getenv("P3_LLAMACPP_URL", "http://127.0.0.1:8080/v1"),
}


@dataclass(frozen=True)
class Profile:
    """Un modello concreto utilizzabile, con i suoi default operativi."""
    name: str
    provider: str          # chiave di API_KEYS
    base_url: str          # endpoint OpenAI-compatibile
    model: str             # nome-modello passato all'API ("auto" = primo caricato su LM Studio)
    max_tokens: int = 2048
    temperature: float = 0.2
    # reasoning: None = modello non-thinking; 'none'/'low'/'medium'/'high' per i thinking
    # (Gemini 2.5 *richiede* 'none' o budget adeguato, altrimenti l'output può uscire vuoto).
    reasoning: Optional[str] = None
    context: int = 0       # finestra di contesto indicativa (0 = ignota)
    rpm: int = 0           # limite richieste/min (0 = nessun throttle, es. locale)
    timeout: float = 120   # secondi per request; locale alto (inferenza lenta), cloud basso
    note: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Registro profili. La chiave è ciò che metto in `P3_ACTIVE_PROFILE`.
# Aggiungere un modello = aggiungere una riga.
#
# Quote free tier (Google AI Studio, da dashboard 2026-06 — uso/limite):
#   RPM = richieste/min · TPM = token/min · RPD = richieste/GIORNO (il collo di bottiglia).
# La pipeline induttiva fa ~16 call/testo: con 20 RPD non si completa nemmeno
# UNA analisi. → workhorse = Gemma 4 (1.5K RPD, TPM illimitati); i Flash/Pro
# (20-500 RPD) si riservano alla sola sintesi finale Δε, con parsimonia.
# Modelli esclusi perché non-testo: *-image, *-tts, *-native-audio, *-live,
# computer-use, robotics. Gemini 2.5 Pro escluso: free tier = 0/0 (non disponibile).
# ─────────────────────────────────────────────────────────────────────────────
_G = ENDPOINTS["google"]
PROFILES = {
    # ── WORKHORSE — Gemma 4 (1.5K RPD, TPM illimitati): per le molte call ─────
    "gemma-31":    Profile("gemma-31", "google", _G, "gemma-4-31b-it",
                           max_tokens=4096, reasoning=None, context=131_072, rpm=15,
                           note="DEFAULT — 15 RPM · TPM illimitati · 1.5K RPD; non-thinking"),
    "gemma-26":    Profile("gemma-26", "google", _G, "gemma-4-26b-a4b-it",
                           max_tokens=4096, reasoning=None, context=131_072, rpm=15,
                           note="MoE 26B-a4b: più veloce/leggero — 15 RPM · TPM illimitati · 1.5K RPD"),

    # ── Gemini Flash (thinking) — RPD limitati: riservare a Δε / quesiti chiave ─
    "gemini-3.1-lite": Profile("gemini-3.1-lite", "google", _G, "gemini-3.1-flash-lite",
                               max_tokens=4096, reasoning="none", context=1_048_576, rpm=15,
                               note="15 RPM · 250K TPM · 500 RPD — miglior Gemini per volume"),
    "gemini-3-flash":  Profile("gemini-3-flash", "google", _G, "gemini-3-flash-preview",
                               max_tokens=8192, reasoning="none", context=1_048_576, rpm=5,
                               note="5 RPM · 250K TPM · 20 RPD — scarso, solo sintesi"),
    "gemini-3.5-flash": Profile("gemini-3.5-flash", "google", _G, "gemini-3.5-flash",
                                max_tokens=8192, reasoning="none", context=1_048_576, rpm=5,
                                note="5 RPM · 250K TPM · 20 RPD — Flash più recente, solo sintesi"),
    "gemini":      Profile("gemini", "google", _G, "gemini-2.5-flash",
                           max_tokens=4096, reasoning="none", context=1_048_576, rpm=5,
                           note="5 RPM · 250K TPM · 20 RPD — solo sintesi/spot"),
    "gemini-lite": Profile("gemini-lite", "google", _G, "gemini-2.5-flash-lite",
                           max_tokens=4096, reasoning="none", context=1_048_576, rpm=10,
                           note="10 RPM · 250K TPM · 20 RPD"),
    # Variante con catena di ragionamento esposta (Δε di qualità, quota permettendo).
    "gemini-3.1-pro": Profile("gemini-3.1-pro", "google", _G, "gemini-3.1-pro-preview",
                              max_tokens=8192, reasoning="low", context=1_048_576,
                              note="ragionamento profondo — verificare quota prima dell'uso"),

    # ── LM Studio (locale, http://127.0.0.1:1234) ─────────────────────────────
    # model="auto" → usa il modello attualmente caricato (auto-detect via /v1/models),
    # così non riscrivo il nome a ogni swap. Per fissarlo: P3_LLM_MODEL="<id esatto LM Studio>".
    #
    # Catalogo locale (2026-06) e idoneità su RTX 4060 8 GB VRAM:
    #   - gemma-4 7.5B  Q4_K_M (6.3 GB)  → ✅ full GPU offload — miglior default locale
    #   - gemma-4 4.6B  Q8_0   (6.0 GB)  → ✅ full GPU offload — più veloce
    #   - gemma-4 12b   QAT    (7.15 GB) → al limite, full offload possibile (in download)
    #   - qwen3.5-9b           (6.55 GB) → full offload (in download)
    #   - qwen3.6-35b   Q4_K_M (22.1 GB) → MoE 35B-A3B: solo offload PARZIALE (3B attivi);
    #                                       usabile ma lento, tenere n_gpu_layers gestito da LM Studio.
    "local":       Profile("local", "local", ENDPOINTS["lmstudio"], "auto",
                           max_tokens=4096, temperature=0.2, context=8192, timeout=600,
                           note="LM Studio — modello caricato (auto-detect); su 4060 preferire gemma-4 7.5B/4.6B"),
    "local-embed": Profile("local-embed", "local", ENDPOINTS["lmstudio"], "auto",
                           max_tokens=0, context=8192, timeout=600,
                           note="LM Studio — endpoint /v1/embeddings del modello embedding caricato"),
    # llama.cpp server (./server -c ...), porta 8080 di default.
    "llamacpp":    Profile("llamacpp", "local", ENDPOINTS["llamacpp"], "auto",
                           max_tokens=4096, context=8192, timeout=600,
                           note="llama.cpp server locale"),

    # ── Provider a pagamento (attivi quando la chiave è presente) ─────────────
    "openai":      Profile("openai", "openai", ENDPOINTS["openai"], "gpt-4o-mini",
                           max_tokens=4096, context=128_000),
    "deepseek":    Profile("deepseek", "deepseek", ENDPOINTS["deepseek"], "deepseek-chat",
                           max_tokens=4096, context=64_000),
    "groq":        Profile("groq", "groq", ENDPOINTS["groq"], "llama-3.3-70b-versatile",
                           max_tokens=4096, context=128_000, note="inferenza molto veloce"),
    "openrouter":  Profile("openrouter", "openrouter", ENDPOINTS["openrouter"],
                           "google/gemini-2.0-flash-exp:free", max_tokens=4096,
                           note="gateway multi-provider"),

    # ── Embeddings Google (100 RPM · 30K TPM · 1K RPD) ────────────────────────
    "embed":       Profile("embed", "google", _G, "gemini-embedding-001",
                           max_tokens=0, context=2048,
                           note="embeddings cloud — 100 RPM · 30K TPM · 1K RPD"),
    "embed-2":     Profile("embed-2", "google", _G, "gemini-embedding-2",
                           max_tokens=0, context=2048,
                           note="embeddings cloud (gen 2)"),
}

# Profilo di default: Gemma 4 31B — l'unico free tier che regge una pipeline
# multi-call (1.5K RPD). Override con env P3_ACTIVE_PROFILE.
_DEFAULT_PROFILE = "gemma-31"


# ─────────────────────────────────────────────────────────────────────────────
# Risoluzione profilo attivo + override env.
# ─────────────────────────────────────────────────────────────────────────────
def active_profile_name() -> str:
    name = (os.getenv("P3_ACTIVE_PROFILE") or _DEFAULT_PROFILE).strip()
    return name if name in PROFILES else _DEFAULT_PROFILE


def get_profile(profile: Optional[str] = None) -> Profile:
    """Profilo risolto con override env applicati (`P3_LLM_BASE_URL/MODEL`)."""
    p = PROFILES.get(profile or active_profile_name(), PROFILES[_DEFAULT_PROFILE])
    base_url = os.getenv("P3_LLM_BASE_URL", p.base_url)
    model = os.getenv("P3_LLM_MODEL", p.model)
    if base_url == p.base_url and model == p.model:
        return p
    return replace(p, base_url=base_url, model=model)


def _api_key(provider: str) -> str:
    # env esplicita P3_LLM_API_KEY vince su tutto; poi <PROVIDER>_API_KEY-style già in API_KEYS.
    return os.getenv("P3_LLM_API_KEY") or API_KEYS.get(provider) or "no-key-required"


# ─────────────────────────────────────────────────────────────────────────────
# LM Studio: modelli caricati (auto-detect) — evita di riscrivere il nome a mano.
# ─────────────────────────────────────────────────────────────────────────────
def lmstudio_models(base_url: Optional[str] = None) -> list[str]:
    """ID dei modelli attualmente serviti da LM Studio (lista vuota se offline)."""
    import urllib.request
    import json
    url = (base_url or ENDPOINTS["lmstudio"]).rstrip("/") + "/models"
    try:
        with urllib.request.urlopen(url, timeout=4) as r:
            data = json.loads(r.read().decode("utf-8"))
        return [m.get("id", "") for m in data.get("data", []) if m.get("id")]
    except Exception:
        return []


def _lmstudio_model_loaded(base_url: str, model: str) -> bool:
    """`True` se il modello è `state: loaded` su `/api/v0/models` di LM Studio.

    `/v1/models` elenca i modelli SCARICATI; `/api/v0/models` riporta lo stato reale.
    Se l'endpoint non risponde (versione vecchia di LM Studio) ritorna True (skip).
    """
    import urllib.request
    import json
    # Deriva il base dell'API rimuovendo il suffisso OpenAI-compat (/v1).
    api_base = base_url.rstrip("/")
    if api_base.endswith("/v1"):
        api_base = api_base[:-3]
    url = api_base + "/api/v0/models"
    try:
        with urllib.request.urlopen(url, timeout=4) as r:
            data = json.loads(r.read().decode("utf-8"))
        for entry in data if isinstance(data, list) else []:
            if entry.get("id") == model or entry.get("path", "").endswith(model):
                return entry.get("state") == "loaded"
        return True   # modello non in lista → assume ok (potrebbe essere caricato on-demand)
    except Exception:
        return True   # endpoint non disponibile → skip del check


def _resolve_model(p: Profile) -> str:
    """Sostituisce model='auto' col primo modello caricato sul backend locale."""
    if p.model != "auto":
        return p.model
    models = lmstudio_models(p.base_url)
    if not models:
        raise RuntimeError(
            f"Profilo '{p.name}': nessun modello caricato su {p.base_url}. "
            "Avvia LM Studio e carica un modello, oppure fissa P3_LLM_MODEL."
        )
    return models[0]


# ─────────────────────────────────────────────────────────────────────────────
# Client + helper di chiamata.
# ─────────────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=8)
def _client_cached(base_url: str, api_key: str):
    from openai import OpenAI
    # timeout per-richiesta + retry bassi: un hang o un 429 deve fallire-veloce ed
    # essere tracciato come `error`, non bloccare la pipeline con backoff lunghi.
    timeout = float(os.getenv("P3_LLM_TIMEOUT", "120"))
    return OpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=1)


def get_llm_client(profile: Optional[str] = None):
    """Client OpenAI-compatibile per il profilo attivo (lazy-import di `openai`)."""
    p = get_profile(profile)
    return _client_cached(p.base_url, _api_key(p.provider))


def get_model(profile: Optional[str] = None) -> str:
    """Nome del modello attivo (risolve 'auto' su LM Studio)."""
    return _resolve_model(get_profile(profile))


def config_snapshot(profile: Optional[str] = None) -> dict:
    """Stato del profilo attivo per traccia/diagnostica (senza la chiave)."""
    p = get_profile(profile)
    return {"profile": p.name, "provider": p.provider, "base_url": p.base_url,
            "model": p.model, "reasoning": p.reasoning, "max_tokens": p.max_tokens}


# ─────────────────────────────────────────────────────────────────────────────
# Chiamata LLM centralizzata (testo + JSON robusto, O-18.1).
#
# I modelli "thinking" sporcano l'output in modi diversi a seconda del backend:
#   - Gemini (2.5/3.x): la catena di ragionamento è SEPARATA dal content via API;
#     si governa col parametro `reasoning_effort` ('none' = output diretto).
#   - Gemma 4: inietta `<thought>…</thought>` INLINE nel content (nessun parametro
#     reasoning sull'endpoint OpenAI) → va ripulito a valle.
# `_sanitize` normalizza entrambi + le code-fence markdown ```json … ```.
# ─────────────────────────────────────────────────────────────────────────────
import re as _re

# <thought> = Gemma · <think> = Qwen e altri reasoning model locali.
_THOUGHT_RE = _re.compile(r"<(thought|think)>.*?</(thought|think)>", _re.DOTALL | _re.IGNORECASE)
_FENCE_RE = _re.compile(r"^\s*```(?:json|JSON)?\s*|\s*```\s*$")


def _supports_reasoning_param(p: Profile) -> bool:
    # Solo i Gemini accettano `reasoning_effort` sull'endpoint OpenAI di Google.
    return p.provider == "google" and p.model.startswith("gemini") and p.reasoning is not None


def _sanitize(text: str) -> str:
    """Rimuove blocchi di ragionamento inline (Gemma) e code-fence markdown."""
    if not text:
        return ""
    text = _THOUGHT_RE.sub("", text).strip()
    # toglie un'eventuale singola fence che avvolge tutto
    if text.startswith("```"):
        text = _FENCE_RE.sub("", text).strip()
        if text.endswith("```"):
            text = text[: text.rfind("```")].strip()
    return text


# Raddoppia ogni backslash che NON inizia un'escape JSON valida (\" \\ \/ \b \f
# \n \r \t \uXXXX). I modelli — Gemma in primis — producono `\d`, `\s`, `\(` dentro
# le stringhe (es. regex citate), che fanno fallire json.loads.
def _fix_json_escapes(s: str) -> str:
    return _re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', s)


def _balanced_json_slice(s: str) -> Optional[str]:
    """Isola il primo `{…}` bilanciato (rispettando le stringhe), non "primo apre /
    ultimo chiude" — quest'ultimo si rompe se il modello aggiunge testo di coda con
    una `}` residua dopo un JSON già valido."""
    i = s.find("{")
    if i < 0:
        return None
    depth, in_str, esc = 0, False, False
    for k in range(i, len(s)):
        ch = s[k]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[i : k + 1]
    return None


def _extract_json(text: str) -> dict:
    """Parsing JSON tollerante: diretto → escape sanate → isolando il primo `{…}` bilanciato."""
    s = _sanitize(text)
    candidati = [s]
    slice_bilanciata = _balanced_json_slice(s)
    if slice_bilanciata is not None:
        candidati.append(slice_bilanciata)
    for c in candidati:
        for variante in (c, _fix_json_escapes(c)):
            try:
                return json.loads(variante)
            except Exception:
                continue
    raise ValueError(f"output non-JSON dopo sanitize: {s[:200]!r}")


# Throttle RPM keyed per-MODELLO (la quota Google free tier è per-modello). Un
# pacing minimo tra le call evita i 429 «RPM severo» segnalati da Σ_w. Locale → 0.
_last_call: dict[str, float] = {}
_throttle_lock = threading.Lock()


def _throttle(model: str, rpm: int) -> None:
    if not rpm:
        return
    min_interval = 60.0 / rpm * 1.05      # piccolo margine sotto il limite
    with _throttle_lock:
        last = _last_call.get(model, 0.0)
        wait = min_interval - (time.monotonic() - last)
        _last_call[model] = time.monotonic() + max(0, wait)
    if wait > 0:
        time.sleep(wait)


def _complete(p: Profile, system: str, user: str,
              max_tokens: Optional[int], temperature: Optional[float]) -> dict:
    """UNA chiamata HTTP. Ritorna i metadati (raw/sanitized/finish/usage/model).

    NON traccia: lo fa il chiamante, che è l'unico a conoscere l'esito del PARSING
    (per il JSON la salute reale dipende anche dal `json.loads`, non solo dal
    content). Solleva su errore HTTP. Esegue il throttle per-modello.
    """
    client = _client_cached(p.base_url, _api_key(p.provider))
    model = _resolve_model(p)
    # BUG-6: per provider locale verifica che il modello sia effettivamente loaded.
    if p.provider == "local" and not _lmstudio_model_loaded(p.base_url, model):
        raise RuntimeError(
            f"LM Studio: il modello '{model}' non è loaded (state != loaded). "
            "Caricarlo manualmente in LM Studio prima di avviare la call."
        )
    kwargs = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "max_tokens": max_tokens if max_tokens is not None else p.max_tokens,
        "temperature": temperature if temperature is not None else p.temperature,
    }
    if _supports_reasoning_param(p):
        kwargs["reasoning_effort"] = p.reasoning
    req_timeout = float(os.getenv("P3_LLM_TIMEOUT", "0")) or p.timeout
    _throttle(model, p.rpm)
    resp = client.chat.completions.create(**kwargs, timeout=req_timeout)
    choice = resp.choices[0]
    raw = choice.message.content or ""
    usage = {}
    if getattr(resp, "usage", None) is not None:
        usage = {"prompt_tokens": getattr(resp.usage, "prompt_tokens", None),
                 "completion_tokens": getattr(resp.usage, "completion_tokens", None),
                 "total_tokens": getattr(resp.usage, "total_tokens", None)}
    return {"raw": raw, "sanitized": _sanitize(raw), "model": model,
            "finish_reason": getattr(choice, "finish_reason", None), "usage": usage}


def call_llm_text(system: str, user: str, *, max_tokens: Optional[int] = None,
                  temperature: Optional[float] = None, profile: Optional[str] = None,
                  tag: str = "") -> str:
    """Chiamata di testo centralizzata. Ritorna il content ripulito (no <thought>).

    `tag` è solo per diagnostica/log del chiamante. I default (max_tokens,
    temperature, reasoning) vengono dal profilo se non specificati.
    """
    p = get_profile(profile)
    from . import trace
    model = _resolve_model(p)
    t0 = time.perf_counter()
    try:
        meta = _complete(p, system, user, max_tokens, temperature)
    except Exception as exc:
        trace.record(tag=tag, profile=p.name, model=model, system=system, user=user,
                     latency_ms=int((time.perf_counter() - t0) * 1000), errore=str(exc))
        raise
    trace.record(tag=tag, profile=p.name, model=meta["model"], system=system, user=user,
                 raw=meta["raw"], sanitized=meta["sanitized"],
                 finish_reason=meta["finish_reason"], usage=meta["usage"],
                 latency_ms=int((time.perf_counter() - t0) * 1000))
    return meta["sanitized"]


# Suffisso di rinforzo iniettato nel RETRY quando il primo output non è JSON valido.
_JSON_RETRY_HINT = (
    "\n\n[RETRY] L'output precedente NON era JSON valido o era troncato. Rispondi con "
    "UN SOLO oggetto JSON valido e COMPLETO: tutte le virgolette e le parentesi chiuse, "
    "nessun testo fuori dall'oggetto, nessun confronto in stile \"A\" vs \"B\" dentro i "
    "valori (usa una sola stringa per valore)."
)


def call_llm_json(system: str, user: str, *, max_tokens: Optional[int] = None,
                  temperature: Optional[float] = None, profile: Optional[str] = None,
                  tag: str = "", retries: int = 1,
                  fallback_profile: Optional[str] = None) -> dict:
    """Chiamata che ritorna un dict JSON (sanitize + parsing tollerante).

    Firma compatibile col `llm_json.call_llm_json` canonico di P3 (O-18.1).

    **Stabilità (fix 2026-06-09b):**
    - *retry-on-parse-fail*: se l'output non è JSON valido/completo (tipico di Gemma
      che tronca la struttura), ritenta `retries` volte rinforzando la richiesta
      (JSON unico e completo, temperature 0, token ampi).
    - *trace veritiera*: OGNI tentativo è tracciato; un parse fallito riceve flag
      `bad_json` (non più un falso `ok`), perché la trace ora registra DOPO il
      `json.loads`, non prima.

    **fallback_profile**: se specificato e il profilo primario esaurisce tutti i retry,
    viene effettuato un ultimo tentativo con questo profilo alternativo (tracciato con
    tag suffisso `-fb`). Usato per resilienza su endpoint singolo (es. inclosura).
    """
    p = get_profile(profile)
    from . import trace
    model = _resolve_model(p)
    last_exc: Optional[Exception] = None

    for attempt in range(retries + 1):
        sys_eff, usr_eff = system, user
        mt, temp = max_tokens, temperature
        if attempt > 0:                       # rinforzo del tentativo di recupero
            usr_eff = user + _JSON_RETRY_HINT
            temp = 0.0
            mt = max(max_tokens or p.max_tokens or 4096, p.max_tokens or 4096)
        t0 = time.perf_counter()
        try:
            meta = _complete(p, sys_eff, usr_eff, mt, temp)
        except Exception as exc:              # errore HTTP → trace 'error', ritenta
            trace.record(tag=tag, profile=p.name, model=model, system=sys_eff, user=usr_eff,
                         latency_ms=int((time.perf_counter() - t0) * 1000), errore=str(exc))
            last_exc = exc
            continue
        latency = int((time.perf_counter() - t0) * 1000)
        try:
            data = _extract_json(meta["sanitized"])
        except Exception as pe:               # JSON invalido/incompleto → flag 'bad_json'
            trace.record(tag=tag, profile=p.name, model=meta["model"], system=sys_eff,
                         user=usr_eff, raw=meta["raw"], sanitized=meta["sanitized"],
                         finish_reason=meta["finish_reason"], usage=meta["usage"],
                         latency_ms=latency, parse_ok=False, errore=f"JSON parse: {pe}")
            last_exc = pe
            continue
        trace.record(tag=tag, profile=p.name, model=meta["model"], system=sys_eff,
                     user=usr_eff, raw=meta["raw"], sanitized=meta["sanitized"],
                     finish_reason=meta["finish_reason"], usage=meta["usage"],
                     latency_ms=latency, parse_ok=True)
        return data

    if fallback_profile:
        # Ultimo tentativo con profilo alternativo — tracciato separatamente.
        fb = get_profile(fallback_profile)
        fb_model = _resolve_model(fb)
        t0 = time.perf_counter()
        try:
            meta = _complete(fb, system, user, max_tokens, temperature)
            latency = int((time.perf_counter() - t0) * 1000)
            data = _extract_json(meta["sanitized"])
            trace.record(tag=f"{tag}-fb", profile=fb.name, model=meta["model"],
                         system=system, user=user, raw=meta["raw"],
                         sanitized=meta["sanitized"], finish_reason=meta["finish_reason"],
                         usage=meta["usage"], latency_ms=latency, parse_ok=True)
            return data
        except Exception as fb_exc:
            latency = int((time.perf_counter() - t0) * 1000)
            trace.record(tag=f"{tag}-fb", profile=fb.name, model=fb_model,
                         system=system, user=user, latency_ms=latency, errore=str(fb_exc))
            last_exc = fb_exc

    raise last_exc if last_exc else ValueError("call_llm_json: nessun tentativo riuscito")
