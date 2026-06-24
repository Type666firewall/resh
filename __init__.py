"""resh — Agente ऋ (dubbio epistemico) — pipeline deterministica + LLM opzionale.

Refactor 2026-05-16: monolite LLM-dipendente → package modulare AI-free.
  - 5 chiamate LLM legacy sostituite da moduli deterministici
    (Stanza UD + mDeBERTa NLI + BGE-M3 embeddings + lexicon-based)
ADR-005 (eseguita 2026-06-12): potatura — via modulatore malafede (no-op),
sintesi narrativa LLM (la voce spetta al Gateway Σ-7), fuzzy_logic (soglie
fisse in core); γ_analizza de-registrato (resta wrapper API).

Riferimenti tecnici:
  - Profiling-UD          http://www.italianlp.it/demo/profiling-ud/
  - MAFALDA (fallacie L2) https://arxiv.org/abs/2311.09761
  - mDeBERTa NLI          https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7
  - BGE-M3 embed          https://huggingface.co/BAAI/bge-m3
  - BERTopic              https://github.com/MaartenGr/BERTopic
  - BiberPlus             https://github.com/davidjurgens/biberplus

Re-export API legacy:
  - `analizza(testo, **kw) -> RapportoResh`
  - `analizza_async(testo, **kw) -> coroutine RapportoResh`
  - `AgenteResh(bus, name, sigma)` (Bus MCP adapter)
  - `RapportoResh`, `PremessaAnalisi`, `Argomento`, `VerificaLogica`,
    `Teleologia`, `AutoritaCriteri` (dataclass legacy)
  - `Patologia`, `TipoPatologia` (nuovi, additive)
"""

from .core import (
    AgenteResh,
    analizza,
    analizza_async,
    genesi,
)
from .schemas import (
    Argomento,
    AutoritaCriteri,
    Patologia,
    PremessaAnalisi,
    Proposizione,
    RapportoResh,
    Teleologia,
    TipoPatologia,
    VerificaLogica,
)
from .lambda_space import (
    Gamma,
    GammaArea,
    GammaKind,
    LAMBDA_RESH,
)


__all__ = [
    "analizza",
    "analizza_async",
    "genesi",
    "AgenteResh",
    "RapportoResh",
    "PremessaAnalisi",
    "Argomento",
    "Proposizione",
    "VerificaLogica",
    "Teleologia",
    "AutoritaCriteri",
    "Patologia",
    "TipoPatologia",
    "Gamma",
    "GammaArea",
    "GammaKind",
    "LAMBDA_RESH",
]
