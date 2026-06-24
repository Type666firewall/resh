"""resh/report.py — γ_report: rendering DETERMINISTICO del grezzo in markdown.

ZERO giudizio, ZERO selezione, ZERO interpretazione. Prende l'output grezzo
(deterministico + induttivo) e lo rende leggibile: numero, TUTTI i componenti,
TUTTA la genesi, TUTTE le patologie, TUTTI i rilievi di ogni asse, Trilemma +
confronto det/ind, Inclosura, termini astratti, e — quotata com'è — la sintesi
Δε del SISTEMA. Stampa in testa provenienza+scope (fonte, lingua, n caratteri).

Confine resh↔gateway (Σ_w): questo NON è «il report con voce» (quello è gateway,
futuro). È il grezzo reso leggibile — input del gateway domani, ispezione oggi.
Nessuna frase è aggiunta dal formatter: se non è nei dati, non compare.

Firma dict-based (stessa forma di tests/_report_output.json), così è invocabile
sia dagli oggetti (`.as_dict()`/serializzazione) sia dal JSON salvato.
"""

from __future__ import annotations

from typing import Optional


def _sec(titolo: str) -> str:
    return f"\n## {titolo}\n"


def _render_det(det: dict) -> list[str]:
    out = [_sec("Lato deterministico — ε_resh")]
    if "errore" in det:
        out.append(f"⚠ deterministico non disponibile: {det['errore']}")
        return out
    eps = det.get("eps_resh")
    out.append(f"**ε_resh = {eps}**  ·  fascia densità: {det.get('fascia_densita')}  ·  "
               f"densità logica: {det.get('densita_logica')}")
    comp = det.get("componenti_epsilon", {})
    if comp:
        out.append("\n**Componenti** (valore grezzo, nessuna interpretazione):")
        for k, v in comp.items():
            out.append(f"- {k}: {v}")
    gen = det.get("genesi", [])
    if gen:
        out.append("\n**Genesi** (componenti ordinati per erosione di ε; cause allegate):")
        for g in gen:
            if not isinstance(g, dict):
                out.append(f"- {g}")
                continue
            riga = (f"- {g.get('componente')}: valore {g.get('valore')}, peso {g.get('peso')}, "
                    f"erosione {g.get('erosione')}")
            out.append(riga)
            for c in g.get("cause", []) or []:
                out.append(f"    · causa [{c.get('tipo')}] sev {c.get('severita')} — "
                           f"{c.get('dettaglio', {})}")
    pat = det.get("patologie", [])
    out.append(f"\n**Patologie ({len(pat)})**:")
    out += [f"- {p}" for p in pat] or ["- (nessuna)"]
    return out


def _render_ind(ind: dict) -> list[str]:
    out = [_sec("Lato induttivo — arsenale ऋ")]
    if "errore" in ind:
        out.append(f"⚠ induttivo non disponibile: {ind['errore']}")
        return out
    o = ind.get("obiettivo")
    if o:
        out.append(f"**Obiettivo O dell'agente** — dichiarato: «{o.get('dichiarato')}»")
        if o.get("latente"):
            out.append(f"  · latente: «{o.get('latente')}»")
        out.append(f"  · coerenza teleologica: {o.get('coerenza')}")
    ars = ind.get("arsenale") or {}
    if ars and "errore" not in ars:
        out.append("\n**Arsenale Critico:**")
        for k in ("asse_1_osservatore", "asse_2_autoreferenza", "asse_3_autosufficienza", "contrasto"):
            if ars.get(k):
                out.append(f"- *{k}*: {ars[k]}")
    assi = ind.get("assi") or {}
    if assi:
        out.append("\n**Assi ऋ** (tutti i rilievi, non selezionati):")
        for aid, a in assi.items():
            if not isinstance(a, dict) or "errore" in a:
                out.append(f"- {aid}: ⚠ {a.get('errore') if isinstance(a, dict) else a}")
                continue
            out.append(f"- **{aid}**:")
            for r in a.get("rilievi", []):
                out.append(f"    · {r}")
            if a.get("nota"):
                out.append(f"    nota: {a['nota']}")
    tri = ind.get("trilemma") or {}
    if tri:
        llm = tri.get("llm", tri) if isinstance(tri, dict) else {}
        out.append("\n**Trilemma di Münchhausen:**")
        if "errore" in tri:
            out.append(f"- ⚠ {tri['errore']}")
        else:
            out.append(f"- corno: {llm.get('corno')} · sottotipo: {llm.get('sottotipo')} · "
                       f"modo: {llm.get('modo')} · target: {llm.get('target')} · "
                       f"polarità: {llm.get('polarita')}")
            if llm.get("descrizione_catena"):
                out.append(f"- catena: {llm['descrizione_catena']}")
            if llm.get("c3_strumentale_diagnostico"):
                out.append(f"- C₃ strumentale dichiarato in diagnosi: {llm['c3_strumentale_diagnostico']}")
            conf = tri.get("confronto")
            if conf:
                out.append(f"- confronto det↔ind: convergenze {conf.get('convergenze')} · "
                           f"divergenze {conf.get('divergenze')} · pre-hit det: {conf.get('n_pre_hits')}")
    inc = ind.get("inclosura") or {}
    if inc and "errore" not in inc:
        llm = inc.get("llm", {})
        out.append("\n**Inclosura (Schema di Priest):**")
        out.append(f"- forma: {inc.get('forma')} · modo: {inc.get('modo')} · "
                   f"risposta al limite: {inc.get('risposta_al_limite')}")
        if llm.get("omega"):
            out.append(f"- Ω: {llm.get('omega')}")
        if llm.get("nota"):
            out.append(f"- nota: {llm.get('nota')}")
    mf = ind.get("malafede_o") or {}
    if mf:
        out.append("\n**Malafede del nodo O (scarto dichiarato↔latente — segnale, non verdetto):**")
        if "errore" in mf:
            out.append(f"- ⚠ {mf['errore']}")
        elif "non_applicabile" in mf:
            out.append(f"- non applicabile: {mf['non_applicabile']}")
        else:
            out.append(f"- intento: {mf.get('intento')} · grado: {mf.get('grado')}")
            for r in mf.get("rilievi", []):
                out.append(f"    · {r}")
            if mf.get("nota"):
                out.append(f"- nota: {mf['nota']}")
    sint = ind.get("sintesi")
    if sint:
        out.append("\n**Sintesi Δε (giudizio del SISTEMA — LLM, prompt versionato; non del formatter):**")
        out.append(f"> {sint}")
    return out


def _render_astratti(astr: dict) -> list[str]:
    out = [_sec("Termini astratti (Berkeley) — occultamento")]
    if "errore" in astr:
        out.append(f"⚠ {astr['errore']}")
        return out
    diag = astr.get("diagnosi", {})
    if not diag:
        out.append("- (nessun candidato)")
        return out
    for termine, d in diag.items():
        out.append(f"- **{termine}** → {d.get('occultamento')}: {d.get('motivo')}")
    return out


def genera_report_documento(rap_doc, *, run_uid: str = "") -> str:
    """Rende un RapportoDocumento (dataclass o .as_dict()) in markdown. Scope=paper, zero giudizio.

    `run_uid`: firma Ψ del run persistito (persistenza.save_run_documento) —
    stampata in intestazione, così ogni report risale al suo dato nel DB."""
    if hasattr(rap_doc, "as_dict"):
        rap_doc = rap_doc.as_dict()
    meta = rap_doc.get("meta", {})
    O = rap_doc.get("obiettivo") or {}
    saltati = rap_doc.get("saltati") or []
    head = [
        "# Report ऋ — DOCUMENTO (grezzo, formatter deterministico)",
        "",
        f"**Fonte:** {rap_doc.get('fonte','?')}  ·  **lingua:** {rap_doc.get('lingua')}  ·  "
        f"**chunk:** {rap_doc.get('n_chunk')}  ·  **modello:** {meta.get('model')}  ·  "
        f"**assi/chunk:** {meta.get('assi_chunk')}  ·  **call:** {meta.get('call_eseguite')}  ·  {meta.get('ts')}"
        + (f"  ·  **run:** `{run_uid}`" if run_uid else ""),
        "",
        "> Rendering deterministico, scope=intero documento. Nessuna selezione/giudizio; "
        "la sintesi è del sistema (LLM).",
    ]
    if saltati:
        head.append(f"\n⚠ **chunk SALTATI per budget** (non analizzati, ripristinabili al resume): {saltati}")
    parti = head
    parti.append(_sec("Obiettivo O dell'agente (globale)"))
    if "errore" in O:
        parti.append(f"⚠ {O['errore']}")
    else:
        parti.append(f"- dichiarato: «{O.get('dichiarato')}»")
        if O.get("latente"):
            parti.append(f"- latente: «{O.get('latente')}»")
    parti.append(_sec("ε aggregata (deterministico)"))
    parti.append(f"**ε_doc = {rap_doc.get('eps_doc')}** (media geometrica pesata per lunghezza chunk)")
    parti.append("\nε per chunk:")
    for e in rap_doc.get("eps_per_chunk", []):
        parti.append(f"- chunk {e.get('id')} [{e.get('loc')}]: ε={e.get('eps')} ({e.get('char')} char)")
    parti.append(_sec("Diagnosi per chunk (note di sintesi)"))
    for c in rap_doc.get("chunk", []):
        parti.append(f"- **chunk {c.get('id')}** [{c.get('loc')}] «{(c.get('titolo') or '')[:50]}»: "
                     f"{c.get('nota_sintesi','')}")
    sd = rap_doc.get("sintesi_doc")
    if sd:
        parti.append(_sec("Sintesi Δε del DOCUMENTO (giudizio del SISTEMA — LLM, prompt versionato)"))
        parti.append(f"> {sd}")
    return "\n".join(parti) + "\n"


def _render_quadro(quadro: dict) -> list[str]:
    """Sezione QuadroEpsilon: det ∥ ind a parità, zero giudizio del formatter."""
    out = [_sec("Quadro ε (det ∥ ind — parità di ruolo, nessuna fusione)")]
    eps = quadro.get("eps_resh")
    out.append(f"**ε_ऋ = {eps}** (verbatim dal deterministico — i giudizi induttivi "
               "AFFIANCANO, non modulano)")

    cop = quadro.get("copertura") or {}
    if cop:
        out.append("\n**Provenienza componenti (da Λ, `eps_feeds`):**")
        out.append("| componente | valore | γ alimentanti |")
        out.append("|---|---|---|")
        comp = quadro.get("componenti") or {}
        for c, gammas in cop.items():
            v = comp.get(c)
            v_str = f"{v:.4f}" if isinstance(v, (int, float)) else "— (escluso)"
            out.append(f"| `{c}` | {v_str} | {', '.join(gammas) or '⚠ NESSUNO'} |")

    giudizi = quadro.get("giudizi_parita") or []
    if giudizi:
        out.append("\n**Giudizi a parità (non entrano in ε):**")
        for c in giudizi:
            stato = c.get("salute")
            extra = f" — {c.get('motivo_scarto')}" if c.get("motivo_scarto") else ""
            out.append(f"- `{c.get('sotto_unita')}` [{stato}]{extra}")

    usati_ind = quadro.get("contributi_ind") or []
    if usati_ind:
        ok_ids = [c.get("sotto_unita") for c in usati_ind if c.get("usato")]
        ass_ids = [c.get("sotto_unita") for c in usati_ind if c.get("salute") == "assente"]
        out.append(f"\n**Contributi induttivi:** usati: {ok_ids or '—'}"
                   + (f" · assenti: {ass_ids}" if ass_ids else ""))

    n_sc = quadro.get("n_scartati", 0)
    if n_sc:
        out.append(f"\n⚠ **Contributi SCARTATI: {n_sc}** (scarto binario, contati — mai pesati):")
        for c in quadro.get("scartati") or []:
            out.append(f"- `{c.get('sotto_unita') or c.get('gamma')}` "
                       f"[{c.get('salute')}]: {c.get('motivo_scarto')}")
    anomalie = (quadro.get("meta") or {}).get("anomalie_copertura")
    if anomalie:
        out.append(f"\n⚠ **Anomalia copertura Λ:** componenti senza γ alimentante: {anomalie}")
    return out


def genera_report(det: Optional[dict] = None, ind: Optional[dict] = None,
                  astratti: Optional[dict] = None, *, fonte: str = "",
                  lingua: str = "", testo: str = "", model: str = "",
                  ts: str = "", run_uid: str = "", quadro: Optional[dict] = None) -> str:
    """Rende il grezzo (det/ind/astratti) in markdown. Nessun giudizio aggiunto.

    `fonte`/`lingua`/`testo` stampano provenienza+scope in intestazione (così lo
    scope — es. "abstract" vs "paper intero" — è inchiodato, non vago)."""
    n_arg = (det or {}).get("n_argomenti")
    head = [
        "# Report ऋ (grezzo, formatter deterministico)",
        "",
        f"**Fonte:** {fonte or '?'}  ·  **lingua:** {lingua or '?'}  ·  "
        f"**input:** {len(testo)} caratteri" + (f"  ·  **argomenti:** {n_arg}" if n_arg is not None else "")
        + (f"  ·  **modello LLM:** {model}" if model else "")
        + (f"  ·  **run:** `{run_uid}`" if run_uid else "")
        + (f"  ·  {ts}" if ts else ""),
        "",
        "> Rendering deterministico: nessuna selezione né interpretazione. "
        "L'unico giudizio è la sintesi Δε del sistema, quotata verbatim.",
    ]
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
