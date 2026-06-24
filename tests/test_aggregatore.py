"""Smoke test aggregatore — QuadroEpsilon, zero LLM, zero modelli.

Verifica i vincoli ratificati: ε verbatim mai ricalcolata, nessuna fusione
det+ind, scarto binario CONTATO (error/bad_json), non_applicabile = assente
(non scartato), copertura componente→γ letta dal registry.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


_DET = {
    "eps_resh": 0.5147,
    "componenti_epsilon": {
        "trasparenza_premesse": 0.6, "validita_formale": 0.9, "assenza_fallacie": 1.0,
        "struttura_argomentativa": 0.4, "coesione_semantica": 0.7, "coerenza_tematica": 0.5,
        "qualita_sintattica": 0.8, "bias_linguistico": 1.0, "credibilita_fonte": 0.65,
    },
    "componenti_esclusi": ["integrita_obiettivo"],
}

_IND = {
    "obiettivo": {"dichiarato": "x", "latente": None, "coerenza": 0.8},
    "arsenale": {"nota": "ok arsenale"},
    "assi": {
        "r2": {"rilievi": ["a"], "nota": "ok"},
        "r4": {"errore": "429 quota", },                       # → error, scartato
        "r6": {"errore": "JSON parse: troncato", "bad_json": True},  # → bad_json, scartato
    },
    "trilemma": {"llm": {"corno": "C3", "modo": "USE"}, "pre_detection": [], "confronto": {}},
    "inclosura": {"llm": {"non_applicabile": "nessuna forma-limite"}},  # → assente, NON scartato
    "sintesi": "Δε di prova.",
    "malafede_o": {"rilievi": ["urgenza fabbricata in §2"], "intento": "persuasivo",
                   "grado": "sospetto", "nota": None},
    "meta": {"model": "test"},
}


def main() -> int:
    from resh.gamma.aggregatore import aggrega
    from resh.epsilon import COMPONENTI

    print("=" * 60)
    print("BATTERIA: aggregatore QuadroEpsilon (smoke, no LLM)")
    print("=" * 60)
    errori: list[str] = []

    # 1. quadro vuoto: non esplode, tutto assente.
    q0 = aggrega(None, None)
    if q0.eps_resh is not None:
        errori.append("aggrega(None,None): eps_resh deve essere None")
    if q0.n_scartati != 0:
        errori.append("aggrega(None,None): n_scartati deve essere 0")

    # 2. quadro pieno.
    q = aggrega(_DET, _IND)
    if q.eps_resh != 0.5147:
        errori.append(f"ε non verbatim: {q.eps_resh}")
    if q.componenti != _DET["componenti_epsilon"]:
        errori.append("componenti non verbatim")
    d = q.as_dict()
    # nessuna fusione: nessun campo numerico globale oltre eps_resh.
    fusi = [k for k, v in d.items() if isinstance(v, (int, float))
            and k not in ("eps_resh", "n_scartati")]
    if fusi:
        errori.append(f"campi numerici fusi inattesi: {fusi}")
    if q.n_scartati != 2:
        errori.append(f"n_scartati atteso 2 (error+bad_json), trovato {q.n_scartati}")
    salute_scartati = sorted(c.salute for c in q.scartati)
    if salute_scartati != ["bad_json", "error"]:
        errori.append(f"salute scartati attesa [bad_json, error], trovata {salute_scartati}")
    incl = [c for c in q.giudizi_parita if c.sotto_unita == "inclosura"]
    if not incl or incl[0].salute != "assente" or incl[0].usato:
        errori.append("inclosura non_applicabile deve essere assente e non usata")
    tri = [c for c in q.giudizi_parita if c.sotto_unita == "trilemma"]
    if not tri or tri[0].salute != "ok" or tri[0].payload.get("corno") != "C3":
        errori.append("trilemma ok atteso nei giudizi a parità, payload verbatim")
    if not any(c.sotto_unita == "r2" and c.usato for c in q.contributi_ind):
        errori.append("asse r2 ok atteso nei contributi_ind")
    mf = [c for c in q.giudizi_parita if c.sotto_unita == "malafede_o"]
    if not mf or mf[0].gamma != "γ_diagnosi_malafede" or mf[0].eps_role != "giudizio_parita":
        errori.append("malafede_o deve portare γ_diagnosi_malafede con eps_role giudizio_parita")
    # 3. copertura: ogni componente di epsilon.COMPONENTI ha ≥1 γ alimentante.
    scoperti = [c for c in COMPONENTI if not q.copertura.get(c)]
    if scoperti:
        errori.append(f"componenti senza γ alimentante: {scoperti}")
    if "anomalie_copertura" in q.meta:
        errori.append(f"anomalie copertura inattese: {q.meta['anomalie_copertura']}")
    # 4. il contributo det del componente escluso è assente ma dichiarato.
    det_io = [c for c in q.contributi_det if "integrita_obiettivo" in c.eps_feeds]
    if not det_io or det_io[0].salute != "assente":
        errori.append("γ di integrita_obiettivo (escluso) deve risultare assente")

    if errori:
        for e in errori:
            print(f"  FAIL  {e}")
        print("VERDETTO: REGRESSIONE aggregatore")
        return 1
    print("  ok    vuoto · ε verbatim · no fusione · scarto binario 2 · "
          "non_applicabile=assente · copertura 10/10")
    print("VERDETTO: OK")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
