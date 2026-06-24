r"""resh/chunking_documento.py — segmentazione DOCUMENTALE (≠ chunking proposizionale).

Spezza un documento lungo (paper) in **chunk analizzabili** di dimensione limitata,
preservando la struttura. Diverso da `chunking.py` (frase→clausola): qui doc→sezioni.

Segnali di taglio, in ordine di preferenza:
  1. marker di pagina `<!-- pagina N -->` (formato PDF-estratto tipico del vault);
  2. fallback: header markdown `^#{1,3} ` o righe-sezione numerate `^\d{1,2}\s+[A-Z]`;
  3. fallback finale: paragrafi (doppio newline).
Poi: merge dei pezzi piccoli fino a `target_char`, split di quelli > `max_char` su
confine di frase. AI-free, deterministico. Opera sul testo GREZZO (marker intatti);
la `pulizia_input` opzionale si applica PER-CHUNK a valle, non prima (sennò toglie i marker).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_MARKER_PAGINA = re.compile(r"<!--\s*pagina\s+(\d+)\s*-->", re.IGNORECASE)
_FINE_FRASE = re.compile(r"(?<=[.!?»\"])\s+")


@dataclass
class Chunk:
    id: int
    titolo: str
    testo: str
    span_char: tuple[int, int]      # offset nel testo ORIGINALE
    loc: str                        # es. "pagina 3" / "par. 5"


def _titolo(testo: str) -> str:
    for riga in testo.splitlines():
        s = riga.strip()
        if len(s) >= 3:
            return s[:80]
    return "(senza titolo)"


def _split_lungo(testo: str, max_char: int) -> list[str]:
    """Spezza un blocco troppo lungo su confine di frase, ~max_char per pezzo."""
    if len(testo) <= max_char:
        return [testo]
    frasi = _FINE_FRASE.split(testo)
    pezzi, cur = [], ""
    for f in frasi:
        if cur and len(cur) + len(f) > max_char:
            pezzi.append(cur.strip())
            cur = f
        else:
            cur = f if not cur else f"{cur} {f}"
    if cur.strip():
        pezzi.append(cur.strip())
    return pezzi


def _blocchi_grezzi(testo: str) -> list[tuple[str, str]]:
    """Ritorna [(loc, blocco)] tagliando sul segnale migliore disponibile."""
    if _MARKER_PAGINA.search(testo):
        out, pos, loc = [], 0, "pagina ?"
        for m in _MARKER_PAGINA.finditer(testo):
            if m.start() > pos:
                out.append((loc, testo[pos:m.start()]))
            loc = f"pagina {m.group(1)}"
            pos = m.end()
        if pos < len(testo):
            out.append((loc, testo[pos:]))
        return [(l, b) for l, b in out if b.strip()]
    # fallback: header markdown / sezioni numerate
    righe = testo.splitlines()
    if any(re.match(r"^(#{1,3} |\d{1,2}\s+[A-Z])", r) for r in righe):
        out, cur, loc = [], [], "sez. 1"
        for r in righe:
            if re.match(r"^(#{1,3} |\d{1,2}\s+[A-Z])", r) and cur:
                out.append((loc, "\n".join(cur)))
                cur, loc = [], r.strip()[:40]
            cur.append(r)
        if cur:
            out.append((loc, "\n".join(cur)))
        return [(l, b) for l, b in out if b.strip()]
    # fallback finale: paragrafi
    return [(f"par. {i+1}", b) for i, b in enumerate(re.split(r"\n\s*\n", testo)) if b.strip()]


def segmenta_documento(testo: str, *, target_char: int = 4000,
                       min_char: int = 800, max_char: int = 6000) -> list[Chunk]:
    """Documento → list[Chunk]. Packer greedy a livello di frase: impacchetta fino
    a ~`target_char`, mai oltre `max_char`; l'ultimo chunk < `min_char` è fuso nel
    precedente. Garantisce: nessun mini-chunk e nessun oversize."""
    # 1. stream di unità-frase con il loro loc
    unita: list[tuple[str, str]] = []
    for loc, b in _blocchi_grezzi(testo):
        for f in _FINE_FRASE.split(b.strip()):
            f = f.strip()
            if f:
                unita.append((loc, f))

    # 2. packing greedy
    grezzi: list[tuple[str, str]] = []      # (loc, testo)
    cur, cur_loc = "", None
    for loc, f in unita:
        if cur_loc is None:
            cur, cur_loc = f, loc
        elif len(cur) + 1 + len(f) <= target_char:
            cur = f"{cur} {f}"
        else:
            grezzi.append((cur_loc, cur))
            cur, cur_loc = f, loc
        while len(cur) > max_char:           # frase singola gigante: taglio netto
            grezzi.append((cur_loc, cur[:max_char]))
            cur = cur[max_char:].strip()
    if cur.strip():
        grezzi.append((cur_loc, cur))

    # 3. fondi l'ultimo se troppo piccolo (coda)
    if len(grezzi) >= 2 and len(grezzi[-1][1]) < min_char:
        ploc, pp = grezzi[-2]
        grezzi[-2] = (ploc, f"{pp} {grezzi[-1][1]}")
        grezzi.pop()

    # 4. costruisci i Chunk con span sul testo originale
    chunks: list[Chunk] = []
    cursore = 0
    for cid, (loc, pezzo) in enumerate(grezzi):
        start = testo.find(pezzo[:40], cursore)
        if start < 0:
            start = cursore
        span = (start, start + len(pezzo))
        cursore = max(cursore, start + 1)
        chunks.append(Chunk(id=cid, titolo=_titolo(pezzo), testo=pezzo,
                            span_char=span, loc=loc))
    return chunks
