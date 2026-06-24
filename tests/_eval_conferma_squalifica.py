# -*- coding: utf-8 -*-
"""Eval di conferma del quesito «Squalifica del dissenso» (prompt Arsenale,
integrazione 2026-06-12, firma Σ_w). Criterio PRE-dichiarato:
  - S1 (strawman manipolativo): l'output dell'asse arsenale DEVE nominare la
    squalifica del dissenso / ovvietà dichiarata (campo dedicato valorizzato
    o lessico nei valori).
  - S6 (neutro simboli logici) e S7 (narrativo): NON deve nominarla.
Profilo via env `P3_EVAL_PROFILE` (default local). ESITO STORICO 2026-06-12:
PASSATO 3/3 con gemma-31 (Google AI Studio); con gemma-4-e4b locale S7 resta
falso positivo (il modello piccolo non tiene la delimitazione narrativa) —
limite noto, rieseguire a cambio modello. 3 call per run (solo asse arsenale,
estrai_o=False)."""
import os
import re
import sys
from pathlib import Path

PROFILE = os.environ.get("P3_EVAL_PROFILE", "local")

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\Users\Anton\Desktop\p3_push")
from resh.lambda_space import G, resolve

analizza_induttivo = resolve(G.ANALIZZA_INDUTTIVO)

CORPUS = Path(r"C:\Users\Anton\Desktop\p3_push\resh\tests\corpus_stress")
CASI = [
    ("S1", CORPUS / "S1_strawman_manipolativo.txt", True),
    ("S6", CORPUS / "S6_neutro_simboli_logici.md", False),
    ("S7", CORPUS / "S7_narrativo_petit_prince.md", False),
]
# Match largo sul lessico del quesito (il giudice è libero nella formulazione).
RE_SQUALIFICA = re.compile(
    r"squalific|dissens|dissenzient|ovviet|travestita\s+da\s+ovvi|"
    r"non\s+ha\s+compreso|illegittim\w*\s+il\s+disaccordo|delegittim",
    re.IGNORECASE)

esiti = []
for sid, path, atteso in CASI:
    testo = path.read_text(encoding="utf-8")[:6000]
    try:
        # estrai_o=False: l'estrazione O usa il profilo default (Google) e non
        # serve al quesito squalifica; l'arsenale gira col placeholder.
        rap = analizza_induttivo(testo, profile=PROFILE, assi=["arsenale"],
                                 estrai_o=False, sintesi=False)
        ars = rap.arsenale or {}
        # Criterio: campo dedicato valorizzato, OPPURE lessico della mossa nei
        # VALORI degli altri campi (mai sui nomi delle chiavi).
        sq = ars.get("squalifica_dissenso")
        sq_valorizzato = bool(sq) and str(sq).strip().lower() not in ("null", "none", "")
        altri_valori = " ".join(str(v) for k, v in ars.items()
                                if k != "squalifica_dissenso" and v)
        hit = sq_valorizzato or bool(RE_SQUALIFICA.search(altri_valori))
        blob = str(ars)
        ok = (hit == atteso)
        esiti.append(ok)
        print(f"{'PASS' if ok else 'FAIL'} {sid}: squalifica_nominata={hit} (atteso {atteso})")
        print(f"  estratto arsenale: {blob[:600]}")
    except Exception as exc:
        esiti.append(False)
        print(f"ERRORE {sid}: {type(exc).__name__}: {exc}")
    print("-" * 60)

print("EVAL CONFERMA SQUALIFICA:", "OK" if all(esiti) else "NON PASSATO")
sys.exit(0 if all(esiti) else 1)
