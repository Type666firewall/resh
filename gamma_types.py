"""gamma_types.py — Contratto I/O per i metodi registrati in lambda_space.py.

Vendorizzato da P3 (libreria condivisa, non un agente): usato da lambda_space.py
per dichiarare input_ports/output_ports di ogni metodo registrato.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet


@dataclass(frozen=True)
class GammaPort:
    """Porta I/O dichiarativa di un metodo registrato.

    nome:        identificativo semantico (es. "testo", "embedding", "score")
    tipo:        stringa del tipo (es. "str", "Path", "list[dict]", "float")
    descrizione: cosa transita
    opzionale:   se True, il metodo funziona anche senza questo input
    """
    nome:        str
    tipo:        str
    descrizione: str
    opzionale:   bool = False


TIPI_COMPATIBILI: dict[str, FrozenSet[str]] = {
    "str":        frozenset({"str", "Path"}),
    "dict":       frozenset({"dict", "RapportoResh", "QuadroEpsilon"}),
    "list":       frozenset({"list", "list[str]", "list[dict]", "list[Path]",
                             "list[GammaPort]"}),
    "list[dict]": frozenset({"list[dict]", "list"}),
    "list[str]":  frozenset({"list[str]", "list"}),
    "float":      frozenset({"float", "int"}),
    "Connection": frozenset({"Connection"}),
    "Path":       frozenset({"Path", "str"}),
    "ndarray":    frozenset({"ndarray"}),
    "Image":      frozenset({"Image"}),
}


def tipi_compatibili(tipo_output: str, tipo_input: str) -> bool:
    """True se un output di tipo_output può alimentare un input di tipo_input."""
    if tipo_output == tipo_input:
        return True
    accettati = TIPI_COMPATIBILI.get(tipo_input)
    if accettati and tipo_output in accettati:
        return True
    accettati_out = TIPI_COMPATIBILI.get(tipo_output)
    if accettati_out and tipo_input in accettati_out:
        return True
    return False


__all__ = [
    "GammaPort",
    "TIPI_COMPATIBILI",
    "tipi_compatibili",
]
