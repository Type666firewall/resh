"""
resh.mcp_server — server MCP stdio per ऋ (Dubbio).

Espone l'analisi epistemica di resh a Ody in sola lettura.
Avvio: python -m resh.mcp_server

Tools:
  p3_resh_analizza(testo, induttivo)  → as_dict() di RapportoResh
  p3_resh_obiettivo(testo)            → {dichiarato, latente, coerenza}
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("resh-dubbio")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="p3_resh_analizza",
            description=(
                "Analisi epistemica ε_resh su testo arbitrario. "
                "Misura coerenza, premesse, obiettivo, fallacie (9-10 componenti). "
                "Modalità deterministica 0 call LLM; opzionale induttivo=true per diagnosi LLM. "
                "Informativo, non bloccante."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "testo": {
                        "type": "string",
                        "description": "Testo da analizzare",
                    },
                    "induttivo": {
                        "type": "boolean",
                        "description": "Se true attiva il lato induttivo LLM (più lento)",
                        "default": False,
                    },
                },
                "required": ["testo"],
            },
        ),
        Tool(
            name="p3_resh_obiettivo",
            description=(
                "Estrae l'obiettivo (dichiarato e latente) da un testo via LLM. "
                "Richiede LLM attivo; se non raggiungibile ritorna null gracefully."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "testo": {
                        "type": "string",
                        "description": "Testo da cui estrarre l'obiettivo",
                    },
                },
                "required": ["testo"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "p3_resh_analizza":
        testo = arguments.get("testo", "")
        if not testo.strip():
            return [TextContent(type="text", text='{"error": "testo vuoto"}')]
        induttivo = bool(arguments.get("induttivo", False))

        from resh.core import analizza_async

        rapporto = await analizza_async(
            testo, induttivo_llm=induttivo, verbose=False
        )
        tel = rapporto.teleologia
        risultato = {
            "eps_resh": rapporto.eps_resh,
            "componenti": rapporto.componenti_epsilon,
            "quadro": rapporto.quadro_epsilon,
            "teleologia": (
                {
                    "dichiarato": tel.obiettivo_dichiarato,
                    "latente":    tel.obiettivo_latente,
                    "coerenza":   tel.coerenza,
                }
                if tel is not None
                else None
            ),
            "patologie": rapporto.patologie,
        }
        return [TextContent(type="text", text=json.dumps(risultato, ensure_ascii=False))]

    if name == "p3_resh_obiettivo":
        testo = arguments.get("testo", "")
        if not testo.strip():
            return [TextContent(type="text", text='{"error": "testo vuoto"}')]

        from resh.obiettivo import estrai_obiettivo

        tel = await asyncio.to_thread(estrai_obiettivo, testo)
        if tel is None:
            risultato = {"dichiarato": None, "latente": None, "coerenza": None}
        else:
            risultato = {
                "dichiarato": tel.obiettivo_dichiarato,
                "latente": tel.obiettivo_latente,
                "coerenza": tel.coerenza,
            }
        return [TextContent(type="text", text=json.dumps(risultato, ensure_ascii=False))]

    return [TextContent(type="text", text=f"tool sconosciuto: {name}")]


async def _main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(_main())
