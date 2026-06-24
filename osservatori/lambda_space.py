"""resh/osservatori/lambda_space.py — Λ_osservatori, registro Σ-6.

Sotto-agente di resh (Dubbio). Dominio: scraping, ricerca, analisi di
pattern, monitoraggio ambientale.

Struttura conforme al template ridotto Σ<9 (no epsilon.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class GammaKind(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM_CHAT      = "llm_chat"
    ORCHESTRATORE = "orchestratore"


class GammaArea(str, Enum):
    RICERCA    = "ricerca"
    SCRAPING   = "scraping"
    PATTERN    = "pattern"
    ORCHESTRA  = "orchestra"


@dataclass(frozen=True)
class Gamma:
    name:          str
    area:          GammaArea
    kind:          GammaKind
    callable_path: str
    target_layer:  str
    llm_required:  bool
    descrizione:   str

    def __str__(self) -> str:
        return f"{self.name} [{self.area.value}/{self.kind.value}]"


LAMBDA_OSSERVATORI: frozenset[Gamma] = frozenset()


_BY_NAME: dict[str, Gamma] = {g.name: g for g in LAMBDA_OSSERVATORI}


def get(name: str) -> Optional[Gamma]:
    return _BY_NAME.get(name)


def by_area(area: GammaArea | str) -> list[Gamma]:
    if isinstance(area, str):
        area = GammaArea(area)
    return sorted([g for g in LAMBDA_OSSERVATORI if g.area is area], key=lambda g: g.name)


def summary() -> str:
    return f"Λ_osservatori — {len(LAMBDA_OSSERVATORI)} γ registrati (scheletro, non popolato)"


def _audit_invariants() -> None:
    for g in LAMBDA_OSSERVATORI:
        if g.kind is GammaKind.LLM_CHAT:
            assert g.target_layer == "prompts", f"{g.name}: LLM_CHAT ma target_layer={g.target_layer}"
            assert g.llm_required, f"{g.name}: LLM_CHAT ma llm_required=False"
        else:
            assert not g.llm_required, f"{g.name}: kind={g.kind.value} ma llm_required=True"
    names = [g.name for g in LAMBDA_OSSERVATORI]
    assert len(set(names)) == len(names), "nomi γ non univoci"


_audit_invariants()
