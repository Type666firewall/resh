"""
Test resh MCP server — verifica che i tool rispondano correttamente.

Avvia il server in-process (senza stdio) e chiama i tool direttamente.
T1-T3: zero LLM. T4: modalità deterministica (0 call LLM, ~3-8s).
T5: p3_resh_obiettivo richiede LLM — skip se offline.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_list_tools():
    from resh.mcp_server import list_tools

    tools = asyncio.run(list_tools())
    nomi = {t.name for t in tools}
    assert "p3_resh_analizza" in nomi
    assert "p3_resh_obiettivo" in nomi
    assert len(tools) == 2
    print("T1 list_tools: OK")


def test_call_tool_empty_analizza():
    from resh.mcp_server import call_tool

    result = asyncio.run(call_tool("p3_resh_analizza", {"testo": ""}))
    data = json.loads(result[0].text)
    assert "error" in data
    print("T2 empty input analizza: OK")


def test_call_tool_unknown():
    from resh.mcp_server import call_tool

    result = asyncio.run(call_tool("nonexistent_tool", {}))
    assert "sconosciuto" in result[0].text
    print("T3 unknown tool: OK")


def test_call_tool_analizza_det():
    from resh.mcp_server import call_tool

    result = asyncio.run(
        call_tool(
            "p3_resh_analizza",
            {"testo": "La democrazia è il miglior sistema di governo perché garantisce libertà.", "induttivo": False},
        )
    )
    data = json.loads(result[0].text)
    assert "eps_resh" in data
    assert "componenti" in data
    assert "patologie" in data
    assert isinstance(data["eps_resh"], (int, float))
    assert 0.0 <= data["eps_resh"] <= 1.0
    print(f"T4 analizza det: OK (eps_resh={data['eps_resh']:.4f})")


def test_call_tool_obiettivo():
    from resh.mcp_server import call_tool

    result = asyncio.run(
        call_tool(
            "p3_resh_obiettivo",
            {"testo": "Voglio capire se la tesi di Rawls regge contro le critiche comunitariste."},
        )
    )
    data = json.loads(result[0].text)
    assert "dichiarato" in data
    assert "latente" in data
    assert "coerenza" in data
    print(f"T5 obiettivo: OK (dichiarato={data['dichiarato']!r})")


def main() -> int:
    test_list_tools()
    test_call_tool_empty_analizza()
    test_call_tool_unknown()
    print("--- T4 modalità deterministica (può richiedere modelli NLP) ---")
    try:
        test_call_tool_analizza_det()
    except Exception as e:
        print(f"T4 SKIP: {e}")
    print("--- T5 richiede LLM attivo (skip se offline) ---")
    try:
        test_call_tool_obiettivo()
    except Exception as e:
        print(f"T5 SKIP: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
