"""resh/pulizia_input.py — pulizia/compressione input (OPZIONALE, droppabile).

Mini-preprocessore NATIVO ispirato allo spirito di TokenJuice (OpenHuman) ma SENZA
dipendenza esterna: la libreria OpenHuman è tarata su HTML/output-tool/integrazioni,
fuori dal nostro caso. Qui si tiene solo il kernel utile al nostro input tipico:
**markdown estratto da PDF**, rumoroso (marker di pagina, header/footer ricorrenti,
note isolate, righe spezzate a metà frase).

`compatta(testo) -> (testo_pulito, stats)`. AI-free, deterministico. NON perde
contenuto argomentativo: rimuove solo cornice/rumore e riflette i paragrafi.
`stats` riporta la riduzione MISURATA (mai silenziosa) + la lingua da frontmatter.

Droppabile: è uno stadio a monte. Chi orchestra può bypassarlo (`usa_pulizia=False`)
senza che il resto della pipeline cambi.
"""

from __future__ import annotations

import re
from collections import Counter

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_MARKER_HTML = re.compile(r"<!--.*?-->", re.DOTALL)          # <!-- pagina N -->
_RIGA_NOTA   = re.compile(r"^\s*\d{1,3}\s*$")                # riga = solo numero (nota isolata)
_LINGUA      = re.compile(r"^lingua:\s*(\w+)", re.MULTILINE)
_FINE_FRASE  = (".", "!", "?", ":", ";", "»", '"', ")")      # un blocco "chiude" se finisce così


def _estrai_lingua(frontmatter: str) -> str | None:
    m = _LINGUA.search(frontmatter or "")
    return m.group(1) if m else None


def _reflow(testo: str) -> str:
    """Ricongiunge le righe spezzate a metà frase: i newline singoli dentro un
    paragrafo diventano spazi; i doppi newline (separatori di paragrafo) restano."""
    out_paragrafi = []
    for blocco in re.split(r"\n\s*\n", testo):
        righe = [r.strip() for r in blocco.splitlines() if r.strip()]
        if not righe:
            continue
        # se un blocco è una lista di header/punti, non riflettere troppo: euristica
        # semplice — unisci con spazio, collassa spazi multipli.
        out_paragrafi.append(re.sub(r"\s{2,}", " ", " ".join(righe)))
    return "\n\n".join(out_paragrafi)


def lingua_frontmatter(testo: str) -> str | None:
    """Lingua dal frontmatter YAML, SENZA pulire il documento.

    Esiste perché il flusso documentale ha bisogno solo di questo dato:
    chiamare `compatta` sull'intero documento per poi scartarne il testo
    (com'era in documento.py) è lavoro buttato su input da centinaia di KB.
    """
    m = _FRONTMATTER.match(testo)
    return _estrai_lingua(m.group(1)) if m else None


def righe_ricorrenti(testo: str, *, min_header_freq: int = 3) -> set[str]:
    """Righe brevi che si ripetono ≥ min_header_freq volte = running header/footer
    (rilevamento GLOBALE; va fatto sul documento intero, non sul singolo chunk)."""
    freq = Counter(r.strip() for r in testo.splitlines() if r.strip())
    return {r for r, n in freq.items()
            if n >= min_header_freq and len(r) < 80 and not r.endswith(tuple(".!?"))}


def compatta_chunk(testo: str, ricorrenti: set[str], *, reflow: bool = True) -> str:
    """Pulisce UN chunk dato il set di header ricorrenti globali: toglie marker,
    header ricorrenti e note isolate, riflette i paragrafi. Niente detection locale."""
    testo = _MARKER_HTML.sub("", testo)
    tenute = [r for r in testo.splitlines()
              if r.strip() not in ricorrenti and not _RIGA_NOTA.match(r.strip())]
    testo = "\n".join(tenute)
    if reflow:
        testo = _reflow(testo)
    return re.sub(r"\n{3,}", "\n\n", testo).strip()


def compatta(testo: str, *, min_header_freq: int = 3, reflow: bool = True) -> tuple[str, dict]:
    """Ritorna (testo_pulito, stats). Rimuove cornice PDF + riflette i paragrafi."""
    char_prima = len(testo)
    lingua = None

    # 1. frontmatter: estrai lingua, poi rimuovi
    m = _FRONTMATTER.match(testo)
    if m:
        lingua = _estrai_lingua(m.group(1))
        testo = testo[m.end():]

    # 2. marker html/commenti (<!-- pagina N -->)
    n_marker = len(_MARKER_HTML.findall(testo))
    # 3. header ricorrenti (rilevamento globale) + 4. note isolate → 5. reflow
    ricorrenti = righe_ricorrenti(testo, min_header_freq=min_header_freq)
    righe = _MARKER_HTML.sub("", testo).splitlines()
    tenute, header_rimossi = [], 0
    for r in righe:
        s = r.strip()
        if s in ricorrenti or _RIGA_NOTA.match(s):
            header_rimossi += 1
            continue
        tenute.append(r)
    testo = "\n".join(tenute)
    if reflow:
        testo = _reflow(testo)

    # 6. normalizza spazi finali
    testo = re.sub(r"\n{3,}", "\n\n", testo).strip()

    char_dopo = len(testo)
    stats = {
        "char_prima": char_prima,
        "char_dopo": char_dopo,
        "riduzione_pct": round(100 * (1 - char_dopo / char_prima), 1) if char_prima else 0.0,
        "lingua": lingua,
        "marker_rimossi": n_marker,
        "righe_cornice_rimosse": header_rimossi,
        "header_ricorrenti": sorted(ricorrenti)[:10],
    }
    return testo, stats
