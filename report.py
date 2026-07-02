"""resh/report.py — γ_report: rendering DETERMINISTICO del grezzo in markdown.

ZERO giudizio, ZERO selezione, ZERO interpretazione. Prende l'output grezzo
(deterministico + induttivo) e lo rende leggibile: numero, TUTTI i componenti,
TUTTA la genesi, TUTTE le patologie, TUTTI i rilievi di ogni asse, Trilemma +
confronto det/ind, Inclosura, termini astratti, e — quotata com'è — la sintesi
Δε del SISTEMA. Stampa in testa provenienza+scope (fonte, lingua, n caratteri).

Firma dict-based (stessa forma di tests/_report_output.json), così è invocabile
sia dagli oggetti (`.as_dict()`/serializzazione) sia dal JSON salvato.
"""

from __future__ import annotations

from typing import Optional


_COMP_LABELS = {
    "trasparenza_premesse":     "Trasparenza premesse",
    "validita_formale":         "Validità formale (sequitur)",
    "assenza_fallacie":         "Assenza fallacie",
    "struttura_argomentativa":  "Struttura argomentativa",
    "coesione_semantica":       "Coesione semantica",
    "coerenza_tematica":        "Coerenza tematica",
    "qualita_sintattica":       "Qualità sintattica",
    "bias_linguistico":         "Assenza bias retorico (hedging/booster)",
    "credibilita_fonte":        "Credibilità fonte",
    "integrita_obiettivo":      "Integrità obiettivo",
}

_ASSE_LABELS = {
    "asse_1_osservatore":       "Posizione dell'osservatore",
    "asse_2_autoreferenza":     "Autoreferenzialità",
    "asse_3_autosufficienza":   "Autosufficienza semantica",
    "contrasto":                "Contrasto interno",
    "r0":  "Dubbio come metodo (r0)",
    "r0p": "Dubbio come postura (r0')",
    "r1":  "Catene di giustificazione (r1)",
    "r2":  "Presupposti non dichiarati (r2)",
    "r3":  "Autorità e fonti (r3)",
    "r4":  "Coerenza interna (r4)",
    "r5":  "Circolarità argomentativa (r5)",
    "r6":  "Disqualificazione del dissenso (r6)",
    "r7":  "Universalità non giustificata (r7)",
    "r8":  "Naturalizzazione (r8)",
    "r9":  "Immunizzazione (r9)",
}

_CORNO_LABELS = {
    "C1": "C1 — Regresso infinito",
    "C2": "C2 — Circolarità (petitio principii)",
    "C3": "C3 — Arresto dogmatico",
}


def _fascia_eps(eps) -> str:
    if eps is None:
        return ""
    try:
        v = float(eps)
    except (TypeError, ValueError):
        return ""
    if v >= 0.85:
        return "alta"
    if v >= 0.65:
        return "media"
    if v >= 0.40:
        return "bassa"
    return "critica"


def _bar(val, width=20) -> str:
    try:
        v = float(val)
    except (TypeError, ValueError):
        return ""
    filled = round(v * width)
    return "█" * filled + "░" * (width - filled)


def _sec(titolo: str) -> str:
    return f"\n## {titolo}\n"


def _render_det(det: dict) -> list[str]:
    out = [_sec("Lato deterministico — epsilon")]
    if "errore" in det:
        out.append(f"⚠ Deterministico non disponibile: {det['errore']}")
        return out
    eps = det.get("eps_resh")
    fascia = _fascia_eps(eps)
    out.append(f"**ε = {eps}** (tenuta epistemica: {fascia})")
    out.append(f"Densità di premesse implicite: {det.get('densita_logica')} — fascia: {det.get('fascia_densita')} "
               "(premesse non dichiarate per token; descrittiva, non entra in ε)")
    comp = det.get("componenti_epsilon", {})
    if comp:
        out.append("\n### Componenti epsilon\n")
        out.append("| Componente | Valore | Barra |")
        out.append("|---|---|---|")
        for k, v in comp.items():
            label = _COMP_LABELS.get(k, k)
            v_str = f"{v:.3f}" if isinstance(v, (int, float)) else str(v)
            bar = _bar(v)
            out.append(f"| {label} | {v_str} | {bar} |")
    gen = det.get("genesi", [])
    if gen:
        out.append("\n### Genesi (componenti ordinati per erosione di epsilon)\n")
        for g in gen:
            if not isinstance(g, dict):
                out.append(f"- {g}")
                continue
            comp_label = _COMP_LABELS.get(g.get("componente", ""), g.get("componente", ""))
            riga = f"- **{comp_label}**: valore {g.get('valore')}, peso {g.get('peso')}, erosione {g.get('erosione')}"
            out.append(riga)
            for c in g.get("cause", []) or []:
                det_info = c.get("dettaglio", {})
                det_str = ", ".join(f"{dk}={dv}" for dk, dv in det_info.items()) if isinstance(det_info, dict) else str(det_info)
                out.append(f"    - [{c.get('tipo')}] severità {c.get('severita')} — {det_str}")
    pat = det.get("patologie", [])
    out.append(f"\n### Patologie rilevate ({len(pat)})\n")
    if pat:
        for p in pat:
            out.append(f"- {p}")
    else:
        out.append("Nessuna patologia rilevata.")
    return out


def _render_ind(ind: dict) -> list[str]:
    out = [_sec("Lato induttivo — analisi critica (LLM)")]
    if "errore" in ind:
        out.append(f"⚠ Induttivo non disponibile: {ind['errore']}")
        return out
    o = ind.get("obiettivo")
    if o:
        out.append("### Obiettivo dell'agente\n")
        out.append(f"- **Dichiarato:** «{o.get('dichiarato')}»")
        if o.get("latente"):
            out.append(f"- **Latente:** «{o.get('latente')}»")
        out.append(f"- **Coerenza teleologica:** {o.get('coerenza')}")
    ars = ind.get("arsenale") or {}
    if ars and "errore" not in ars:
        out.append("\n### Arsenale critico\n")
        for k in ("asse_1_osservatore", "asse_2_autoreferenza", "asse_3_autosufficienza", "contrasto"):
            if ars.get(k):
                label = _ASSE_LABELS.get(k, k)
                out.append(f"**{label}:** {ars[k]}\n")
    assi = ind.get("assi") or {}
    if assi:
        out.append("\n### Assi di analisi\n")
        for aid, a in assi.items():
            label = _ASSE_LABELS.get(aid, aid)
            if not isinstance(a, dict) or "errore" in a:
                err = a.get("errore") if isinstance(a, dict) else a
                out.append(f"**{label}:** ⚠ {err}\n")
                continue
            out.append(f"**{label}:**")
            for r in a.get("rilievi", []):
                out.append(f"- {r}")
            if a.get("nota"):
                out.append(f"  *Nota:* {a['nota']}")
            out.append("")
    tri = ind.get("trilemma") or {}
    if tri:
        llm = tri.get("llm", tri) if isinstance(tri, dict) else {}
        out.append("\n### Trilemma di Münchhausen\n")
        out.append("> Ogni catena di giustificazione termina in uno di tre modi: "
                   "regresso infinito (C1), circolarità (C2), o arresto dogmatico (C3).\n")
        if "errore" in tri:
            out.append(f"⚠ {tri['errore']}")
        else:
            corno = llm.get("corno", "?")
            corno_label = _CORNO_LABELS.get(corno, corno)
            out.append(f"- **Corno dominante:** {corno_label}")
            if llm.get("sottotipo"):
                out.append(f"- **Sottotipo:** {llm['sottotipo']}")
            if llm.get("modo"):
                out.append(f"- **Modo:** {llm['modo']}")
            if llm.get("descrizione_catena"):
                out.append(f"- **Catena:** {llm['descrizione_catena']}")
            if llm.get("c3_strumentale_diagnostico"):
                out.append(f"- **C3 strumentale:** {llm['c3_strumentale_diagnostico']}")
            conf = tri.get("confronto")
            if conf:
                conv = conf.get("convergenze", [])
                dive = conf.get("divergenze", [])
                out.append(f"- Confronto deterministico/induttivo: "
                           f"convergenze {len(conv)}, divergenze {len(dive)}")
                # Disaccordo mostrato, non solo contato: ogni divergenza con il
                # suo ancoraggio testuale, così il lettore giudica da sé.
                for d in dive[:10]:
                    det_lato = d.get("sottotipo_det") or d.get("corno_det") or "—"
                    llm_lato = d.get("corno_llm") or "—"
                    riga = f"  - ⚡ deterministico: `{det_lato}` vs LLM: `{llm_lato}`"
                    if d.get("span"):
                        riga += f" — «{d['span']}»"
                    if d.get("nota"):
                        riga += f" ({d['nota']})"
                    out.append(riga)
                if len(dive) > 10:
                    out.append(f"  - … e altre {len(dive) - 10} divergenze (vedi JSON)")
    inc = ind.get("inclosura") or {}
    if inc and "errore" not in inc:
        llm = inc.get("llm", {})
        out.append("\n### Inclosura (Schema di Priest)\n")
        out.append("> L'inclosura rileva se il testo affronta un limite del pensiero "
                   "e come risponde: trascendenza, chiusura, o dialettica.\n")
        out.append(f"- **Forma:** {inc.get('forma')}")
        if inc.get("modo"):
            out.append(f"- **Modo:** {inc.get('modo')}")
        if llm.get("omega"):
            out.append(f"- **Omega (limite):** {llm.get('omega')}")
        if llm.get("nota"):
            out.append(f"- *{llm.get('nota')}*")
    mf = ind.get("malafede_o") or {}
    if mf:
        out.append("\n### Diagnosi malafede (scarto dichiarato/latente)\n")
        out.append("> Segnale, non verdetto: un fine egoistico non rende cattivo il prodotto.\n")
        if "errore" in mf:
            out.append(f"⚠ {mf['errore']}")
        elif "non_applicabile" in mf:
            out.append(f"Non applicabile: {mf['non_applicabile']}")
        else:
            out.append(f"- **Intento:** {mf.get('intento')} — **Grado:** {mf.get('grado')}")
            for r in mf.get("rilievi", []):
                out.append(f"- {r}")
            if mf.get("nota"):
                out.append(f"  *{mf['nota']}*")
    sint = ind.get("sintesi")
    if sint:
        out.append("\n### Sintesi (giudizio del sistema)\n")
        out.append(f"> {sint}")
    return out


def _render_astratti(astr: dict) -> list[str]:
    out = [_sec("Termini astratti (Berkeley) — occultamento")]
    if "errore" in astr:
        out.append(f"⚠ {astr['errore']}")
        return out
    diag = astr.get("diagnosi", {})
    if not diag:
        out.append("Nessun candidato rilevato.")
        return out
    for termine, d in diag.items():
        out.append(f"- **{termine}** → {d.get('occultamento')}: {d.get('motivo')}")
    return out


def genera_report_documento(rap_doc, *, run_uid: str = "") -> str:
    if hasattr(rap_doc, "as_dict"):
        rap_doc = rap_doc.as_dict()
    meta = rap_doc.get("meta", {})
    O = rap_doc.get("obiettivo") or {}
    saltati = rap_doc.get("saltati") or []
    eps_doc = rap_doc.get("eps_doc")
    sd = rap_doc.get("sintesi_doc")

    head = [
        "# Report resh — Analisi documento",
        "",
        f"**Fonte:** {rap_doc.get('fonte','?')}  ·  **Lingua:** {rap_doc.get('lingua')}  ·  "
        f"**Chunk:** {rap_doc.get('n_chunk')}  ·  **Modello:** {meta.get('model')}  ·  "
        f"**Call LLM:** {meta.get('call_eseguite')}  ·  {meta.get('ts')}"
        + (f"  ·  **Run:** `{run_uid}`" if run_uid else ""),
        "",
    ]

    # Executive summary in testa
    head.append("## Riepilogo\n")
    fascia = _fascia_eps(eps_doc)
    head.append(f"**Epsilon documento: {eps_doc}** (tenuta epistemica: {fascia})")
    if O and "errore" not in O:
        head.append(f"\n**Obiettivo:** «{O.get('dichiarato', '?')}»")
    if sd:
        head.append(f"\n**Sintesi:** {sd}")
    if saltati:
        head.append(f"\n⚠ **Chunk saltati per budget:** {saltati} (ripristinabili al resume)")

    parti = head

    parti.append(_sec("Epsilon per chunk"))
    for e in rap_doc.get("eps_per_chunk", []):
        e_val = e.get("eps")
        bar = _bar(e_val) if e_val else ""
        parti.append(f"- Chunk {e.get('id')} [{e.get('loc')}]: ε={e_val} {bar} ({e.get('char')} char)")

    parti.append(_sec("Diagnosi per chunk"))
    for c in rap_doc.get("chunk", []):
        nota = c.get("nota_sintesi", "")
        parti.append(f"\n**Chunk {c.get('id')}** [{c.get('loc')}] «{(c.get('titolo') or '')[:50]}»\n")
        if " | " in nota:
            for part in nota.split(" | "):
                parti.append(f"- {part.strip()}")
        else:
            parti.append(f"- {nota}")

    return "\n".join(parti) + "\n"


def _render_quadro(quadro: dict) -> list[str]:
    out = [_sec("Quadro epsilon (deterministico e induttivo a confronto)")]
    eps = quadro.get("eps_resh")
    out.append(f"**ε = {eps}** (dal lato deterministico — il lato induttivo affianca, non modula)")

    cop = quadro.get("copertura") or {}
    if cop:
        out.append("\n### Provenienza componenti\n")
        out.append("| Componente | Valore | Moduli |")
        out.append("|---|---|---|")
        comp = quadro.get("componenti") or {}
        for c, gammas in cop.items():
            label = _COMP_LABELS.get(c, c)
            v = comp.get(c)
            v_str = f"{v:.4f}" if isinstance(v, (int, float)) else "— (escluso)"
            out.append(f"| {label} | {v_str} | {', '.join(gammas) or '⚠ nessuno'} |")

    giudizi = quadro.get("giudizi_parita") or []
    if giudizi:
        out.append("\n### Giudizi a parità (non entrano in epsilon)\n")
        for c in giudizi:
            stato = c.get("salute")
            extra = f" — {c.get('motivo_scarto')}" if c.get("motivo_scarto") else ""
            label = _ASSE_LABELS.get(c.get("sotto_unita", ""), c.get("sotto_unita", ""))
            out.append(f"- {label} [{stato}]{extra}")

    n_sc = quadro.get("n_scartati", 0)
    if n_sc:
        out.append(f"\n⚠ **Contributi scartati: {n_sc}**")
        for c in quadro.get("scartati") or []:
            su = c.get("sotto_unita") or c.get("gamma")
            label = _ASSE_LABELS.get(su, su)
            out.append(f"- {label} [{c.get('salute')}]: {c.get('motivo_scarto')}")
    return out


def genera_report(det: Optional[dict] = None, ind: Optional[dict] = None,
                  astratti: Optional[dict] = None, *, fonte: str = "",
                  lingua: str = "", testo: str = "", model: str = "",
                  ts: str = "", run_uid: str = "", quadro: Optional[dict] = None) -> str:
    n_arg = (det or {}).get("n_argomenti")
    eps = (det or {}).get("eps_resh")
    fascia = _fascia_eps(eps)

    head = [
        "# Report resh — Analisi epistemica",
        "",
        f"**Fonte:** {fonte or '?'}  ·  **Lingua:** {lingua or '?'}  ·  "
        f"**Input:** {len(testo)} caratteri" + (f"  ·  **Argomenti:** {n_arg}" if n_arg is not None else "")
        + (f"  ·  **Modello LLM:** {model}" if model else "")
        + (f"  ·  **Run:** `{run_uid}`" if run_uid else "")
        + (f"  ·  {ts}" if ts else ""),
        "",
    ]

    # Executive summary
    if eps is not None:
        head.append("## Riepilogo\n")
        head.append(f"**Epsilon: {eps}** (tenuta epistemica: {fascia})")
        pat = (det or {}).get("patologie", [])
        if pat:
            head.append(f"  ·  Patologie rilevate: {len(pat)}")
        sint = (ind or {}).get("sintesi")
        if sint:
            head.append(f"\n**Sintesi:** {sint}")

    parti = head
    if det is not None:
        parti += _render_det(det)
    if ind is not None:
        parti += _render_ind(ind)
    if astratti is not None:
        parti += _render_astratti(astratti)
    if quadro is not None:
        parti += _render_quadro(quadro)
    return "\n".join(parti) + "\n"
