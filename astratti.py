"""resh/astratti.py — stadio induttivo della caccia ai TERMINI ASTRATTI (Berkeley).

Stadio 2 del piano nuovo (lo stadio 1 = `induttivo.pre_detect_abstract`, AI-free).
Dato φ + Obiettivo O + i termini CANDIDATI surfacati dal detector, l'LLM applica
la domanda berkeleyana e classifica l'**occultamento** di ciascun termine secondo
la tassonomia AGGIORNABILE (`lessici/termini_astratti_it.json:tassonomia_occultamento`).

Parità di ruolo: il detector dà PRESENZA (candidati), qui si dà il GIUDIZIO; nessuno
ha l'ultima parola. O-relativo. Una sola call per testo (tutti i candidati insieme).

NB collision-safe: file NUOVO. Il prompt è provvisorio QUI (non in `prompts_resh.md`,
congelato dall'altro agente); a sblocco si potrà spostare là / fondere con gli assi.
"""

from __future__ import annotations

from typing import Optional

from . import config, induttivo
from .schemas import Teleologia


SYS_ASTRATTI = """Sono ऋ, analizzatore critico non-fondazionalista.

Ricevo una rappresentazione φ, l'Obiettivo O dell'agente che l'ha prodotta, e una
lista di TERMINI CANDIDATI (parole che potrebbero nominare idee astratte). Per
ciascun termine, COME È USATO IN φ rispetto a O, applico la critica berkeleyana
delle idee astratte: il termine ha un contenuto particolare/ostensibile, oppure
pretende di nominare una cosa determinata senza tale contenuto — celando così una
definizione normativa o un posito metafisico?

Non giudico la verità di φ. Non propongo alternative. Classifico l'occultamento di
ciascun termine, scegliendo SOLO tra i tipi forniti. Nel dubbio tra «contenuto
determinato» e un occultamento, scelgo il contenuto determinato (più cauto)."""


def _payload(testo: str, O: Optional[Teleologia], candidati: list[str],
             tassonomia: list[dict]) -> str:
    tipi = "\n".join(f"  - {t['tipo']}: {t.get('desc','')}" for t in tassonomia)
    righe = ['Testo φ:', '"""', testo.strip(), '"""', '']
    if O is not None:
        righe.append(f"Obiettivo O (dichiarato): {O.obiettivo_dichiarato}")
        if O.obiettivo_latente:
            righe.append(f"Obiettivo O (latente): {O.obiettivo_latente}")
    righe += [
        "",
        "Termini candidati da classificare: " + ", ".join(candidati),
        "",
        "Tipi di occultamento ammessi (scegli ESATTAMENTE uno per termine):",
        tipi,
        "",
        'Rispondi ESCLUSIVAMENTE con JSON:',
        '{"diagnosi": [{"termine": "<uno dei candidati>", '
        '"occultamento": "<uno dei tipi sopra>", '
        '"motivo": "<una frase che localizza l\'occultamento, o perché è determinato>"}]}',
    ]
    return "\n".join(righe)


def diagnosi_termini_astratti(
    testo: str, *, obiettivo: Optional[Teleologia] = None,
    profile: Optional[str] = None, max_candidati: int = 20,
) -> dict:
    """Classifica l'occultamento dei termini astratti candidati di φ (1 call LLM).

    Ritorna {"candidati": [...], "diagnosi": {termine: {occultamento, motivo}}, "errore"?}.
    I candidati vengono dal detector; l'LLM li giudizia rispetto a O.
    """
    candidati = [h["termine"] for h in induttivo.pre_detect_abstract(testo)][:max_candidati]
    if not candidati:
        return {"candidati": [], "diagnosi": {}}
    tassonomia = induttivo.carica_tassonomia_occultamento()
    user = _payload(testo, obiettivo, candidati, tassonomia)
    try:
        out = config.call_llm_json(SYS_ASTRATTI, user, temperature=0.1,
                                   profile=profile, tag="ऋ-astratti")
    except Exception as exc:
        return {"candidati": candidati, "diagnosi": {}, "errore": f"{type(exc).__name__}: {exc}"}
    diagnosi = {}
    for d in out.get("diagnosi", []):
        t = str(d.get("termine", "")).strip().lower()
        if t:
            diagnosi[t] = {"occultamento": d.get("occultamento", ""),
                           "motivo": d.get("motivo", "")}
    return {"candidati": candidati, "diagnosi": diagnosi}
