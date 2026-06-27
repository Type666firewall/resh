"""resh/cli.py — Entry point CLI per analisi testo via agente ऋ.

Uso (per-testo, deterministico):
  python -m resh.cli <file>                       # default deterministico
  python -m resh.cli <file> --out report.md       # salva markdown
  python -m resh.cli <file> --quiet               # solo verdetto

  # Report markdown da DB persistenza (no re-analisi):
  python -m resh.cli --report-from-db <file_o_uid> --out report.md
  python -m resh.cli --report-from-db <file>      # stampa a stdout

Sottocomandi DOCUMENTALI (map-reduce su paper intero, lato induttivo LLM):
  python -m resh.cli documento <file> [--profile P] [--budget N] [--completo]
         [--astratti] [--assi r2,r4,trilemma] [--target-char N] [--no-resume]
         [--no-save] [--out report.md]
      Analizza il documento (resumable: i chunk cachati si riusano, le parti in
      errore si riparano), persiste il run nel DB (run_uid Ψ_<doc12>_D<seq>) e
      scrive il report markdown firmato.
  python -m resh.cli runs [--doc HASH_PREFIX]
      Elenca i run documentali registrati (onestà inclusa: saltati, errori).
  python -m resh.cli report-doc [RUN_UID] [--doc HASH_PREFIX] [--out report.md]
      RIGENERA il report markdown dal rapporto_json salvato (zero call LLM).
      Senza argomenti: ultimo run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import analizza
from .persistenza import report_markdown, save_report_markdown, save_run


def _build_markdown(rapporto, nome_documento: str) -> str:
    md: list[str] = []
    md.append("# 𝒫₃ Agente ऋ (Dubbio) — Report di Analisi")
    md.append(f"**Documento:** `{nome_documento}`\n")
    md.append("## Metriche Globali")
    md.append(f"- **ε_ऋ:** `{rapporto.eps_resh:.4f}`")
    md.append(f"- **Densità Logica:** `{rapporto.densita_logica:.4f}` (Fascia: *{rapporto.fascia_densita}*)")
    md.append(f"- **Modificatore Malafede:** `{rapporto.malafede_mod:.4f}`\n")

    md.append("## Profilo Linguistico (Profiling-UD-style)")
    for k, v in rapporto.profilo_linguistico.items():
        if isinstance(v, (int, float, str)):
            md.append(f"- `{k}` = `{v}`")
    md.append("")

    md.append(f"## Premesse (Score trasparenza: {rapporto.premesse.score:.2f})")
    if rapporto.premesse.esplicite:
        md.append("### Esplicite")
        md.extend([f"- {p}" for p in rapporto.premesse.esplicite])
    if rapporto.premesse.implicite:
        md.append("### Implicite")
        md.extend([f"- {p}" for p in rapporto.premesse.implicite])
    if rapporto.premesse.sospette:
        md.append("### ⚠ Sospette")
        md.extend([f"- **{p}**" for p in rapporto.premesse.sospette])
    md.append("")

    md.append(f"## Inventario Argomenti ({len(rapporto.inventario)})")
    for i, a in enumerate(rapporto.inventario, 1):
        md.append(f"**{i}. [{a.tipo}]** {a.testo}")
    md.append("")

    md.append("## Coerenza Semantica")
    for k, v in rapporto.coerenza_semantica.items():
        md.append(f"- `{k}` = `{v}`")
    md.append("")

    md.append("## Autorità e Bias")
    md.append(f"- **Fonte:** {rapporto.autorita.fonte}")
    md.append(f"- **Credibilità:** {rapporto.autorita.credibilita}")
    if rapporto.autorita.bias_rilevati:
        md.append(f"- **Bias rilevati:** {', '.join(rapporto.autorita.bias_rilevati)}")
    md.append("")

    md.append("## Componenti ε_ऋ")
    for k, v in rapporto.componenti_epsilon.items():
        md.append(f"- `{k}` = `{v:.4f}`")
    md.append("")

    md.append("## Profilo Stilistico (Biber subset IT)")
    for k, v in rapporto.profilo_stilistico.items():
        if isinstance(v, (int, float)):
            md.append(f"- `{k}` = `{v}`")
    md.append("")

    if rapporto.patologie:
        md.append("## ⚠ Patologie")
        md.extend([f"- {p}" for p in rapporto.patologie])
        md.append("")

    if rapporto.sintesi_narrativa:
        md.append("## Sintesi Narrativa (LLM opzionale)")
        md.append(rapporto.sintesi_narrativa)
        md.append("")

    ind = getattr(rapporto, "induttivo", None)
    ind_richiesto = getattr(rapporto, "induttivo_richiesto", False)
    if ind_richiesto and (ind is None or "errore" in (ind or {})):
        md.append("## ⚠ Lato induttivo — RICHIESTO MA NON DISPONIBILE")
        errore = (ind or {}).get("errore", "nessun output prodotto")
        md.append(f"> Il lato induttivo (LLM) è stato richiesto ma non ha prodotto output: {errore}")
        md.append("")
    elif ind:
        from .report import _render_ind
        md.append("## Lato induttivo (arsenale ऋ — giudizi a parità di ruolo)")
        md.extend(_render_ind(ind))
        md.append("")

    if getattr(rapporto, "quadro_epsilon", None):
        from .report import _render_quadro
        md.extend(_render_quadro(rapporto.quadro_epsilon))
        md.append("")

    md.append("## μ-Traccia YAML")
    md.append("```yaml")
    try:
        import yaml
        md.append(yaml.dump(rapporto.yaml_output, allow_unicode=True, sort_keys=False).strip())
    except ImportError:
        md.append(json.dumps(rapporto.yaml_output, ensure_ascii=False, indent=2))
    md.append("```")
    return "\n".join(md)


def _report_from_db_main(target: str, out: str | None, *, no_json: bool) -> int:
    """Sub-flow `--report-from-db`: target = run_uid | path | basename | doc_hash prefix.

    Niente re-analisi: legge solo da `db/resh_analyses.db`.
    """
    p = Path(target)
    is_file_like = p.exists() or "/" in target or "\\" in target or target.endswith((".md", ".txt"))

    kwargs: dict = {"include_json_appendix": not no_json}
    if target.startswith("Ψ_"):
        kwargs["run_uid"] = target
    elif is_file_like:
        kwargs["file_path"] = target
    elif len(target) >= 6 and all(c in "0123456789abcdef" for c in target.lower()):
        kwargs["doc_hash"] = target
    else:
        kwargs["file_path"] = target   # ultimo tentativo: basename

    if out:
        path = save_report_markdown(out, **kwargs)
        if path is None:
            print(f"[ERRORE] Nessuna run trovata nel DB per: {target}")
            return 1
        print(f"[OK] Report salvato in: {path.absolute()}")
        return 0
    md = report_markdown(**kwargs)
    if md is None:
        print(f"[ERRORE] Nessuna run trovata nel DB per: {target}")
        return 1
    print(md)
    return 0


# ─── sottocomandi documentali ──────────────────────────────────────────


def _documento_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="resh.cli documento",
        description="Analisi induttiva map-reduce di un documento intero + persistenza Ψ.")
    ap.add_argument("file", type=str, help="path al documento (md/txt)")
    ap.add_argument("--profile", type=str, default=None, help="profilo LLM (config.py)")
    ap.add_argument("--budget", type=int, default=None, metavar="N",
                    help="tetto duro di call LLM (chunk oltre budget → saltati, ripresi al resume)")
    ap.add_argument("--target-char", type=int, default=6000)
    ap.add_argument("--completo", action="store_true",
                    help="arsenale completo: TUTTI gli assi per chunk (default: sottoinsieme)")
    ap.add_argument("--astratti", action="store_true",
                    help="aggiungi diagnosi termini astratti (Berkeley) per chunk")
    ap.add_argument("--assi", type=str, default=None,
                    help="sottoinsieme assi per chunk, separati da virgola (es. r2,r4,trilemma)")
    ap.add_argument("--no-resume", action="store_true", help="ignora i chunk cachati")
    ap.add_argument("--no-save", action="store_true", help="non persistere il run nel DB")
    ap.add_argument("--out", type=str, default=None, help="path report markdown (default: <file>.report.md)")
    args = ap.parse_args(argv)

    p = Path(args.file)
    if not p.exists():
        print(f"[ERRORE] File non trovato: {args.file}")
        return 1
    testo = p.read_text(encoding="utf-8")

    from . import documento, report            # import qui: trascina lo stack LLM/NLP
    from .persistenza import save_run_documento

    rap = documento.analizza_documento_induttivo(
        testo, fonte=p.name,
        arsenale_completo=args.completo, con_astratti=args.astratti,
        assi_chunk=(args.assi.split(",") if args.assi else None),
        profile=args.profile, max_call_budget=args.budget,
        resume=not args.no_resume, target_char=args.target_char,
    )

    run_uid = ""
    if not args.no_save:
        esito = save_run_documento(rap, file_path=p)
        run_uid = esito["run_uid"]

    md = report.genera_report_documento(rap, run_uid=run_uid)
    out_path = Path(args.out) if args.out else p.with_suffix(p.suffix + ".report.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")

    d = rap.as_dict()
    print(f"run_uid:  {run_uid or '(non salvato)'}")
    print(f"eps_doc:  {d.get('eps_doc')}  |  chunk: {d.get('n_chunk')}  |  "
          f"saltati: {d.get('saltati')}  |  call: {d.get('meta', {}).get('call_eseguite')}")
    print(f"report:   {out_path.absolute()}")
    return 0


def _runs_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="resh.cli runs",
                                 description="Elenca i run documentali registrati.")
    ap.add_argument("--doc", type=str, default=None, metavar="HASH_PREFIX")
    args = ap.parse_args(argv)

    from .persistenza import list_runs_documento
    rows = list_runs_documento(doc_hash=args.doc)
    if not rows:
        print("(nessun run documentale registrato)")
        return 0
    for r in rows:
        eps = f"{r['eps_doc']:.4f}" if r.get("eps_doc") is not None else "  —  "
        onesta = (f"saltati={r['n_saltati']}" if r.get("n_saltati") else "completo")
        if r.get("n_parti_errore"):
            onesta += f", parti_errore={r['n_parti_errore']}"
        print(f"{r['run_uid']}  {r['ts_creazione']}  ε_doc={eps}  "
              f"chunk={r['n_chunk']}  call={r.get('call_eseguite')}  [{onesta}]  "
              f"{r.get('fonte') or r['doc_hash'][:12]}")
    return 0


def _report_doc_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="resh.cli report-doc",
        description="Rigenera il report markdown di un run documentale dal DB (zero call).")
    ap.add_argument("run_uid", nargs="?", default=None)
    ap.add_argument("--doc", type=str, default=None, metavar="HASH_PREFIX")
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args(argv)

    from . import report
    from .persistenza import get_run_documento
    run = get_run_documento(run_uid=args.run_uid, doc_hash=args.doc)
    if run is None:
        print(f"[ERRORE] Nessun run documentale trovato per: {args.run_uid or args.doc or '(ultimo)'}")
        return 1
    md = report.genera_report_documento(run["rapporto"], run_uid=run["run_uid"])
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"[OK] {run['run_uid']} → {out.absolute()}")
    else:
        print(md)
    return 0


def _obiettivo_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="resh.cli obiettivo",
        description="Estrae l'Obiettivo O (dichiarato/latente/coerenza) da un testo via LLM.")
    ap.add_argument("file", type=str, help="path al testo (md/txt)")
    ap.add_argument("--profile", type=str, default=None, help="profilo LLM (config.py)")
    ap.add_argument("--out", type=str, default=None, help="salva output JSON in questo file")
    args = ap.parse_args(argv)

    p = Path(args.file)
    if not p.exists():
        print(f"[ERRORE] File non trovato: {args.file}")
        return 1
    testo = p.read_text(encoding="utf-8")

    if args.profile:
        import os
        os.environ["P3_ACTIVE_PROFILE"] = args.profile

    from .obiettivo import estrai_obiettivo

    print(f"[resh.obiettivo] estrazione O da {p.name} …")
    tel = estrai_obiettivo(testo)

    if tel is None:
        print("[ERRORE] Estrazione O fallita (LLM non raggiungibile o risposta vuota).")
        return 1

    print(f"\ndichiarato : {tel.obiettivo_dichiarato}")
    print(f"latente    : {tel.obiettivo_latente or '(nessuno scarto)'}")
    print(f"coerenza   : {tel.coerenza:.4f}")

    if args.out:
        import json
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps({
                "fonte": p.name,
                "obiettivo_dichiarato": tel.obiettivo_dichiarato,
                "obiettivo_latente":    tel.obiettivo_latente,
                "coerenza":             tel.coerenza,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n[OK] JSON salvato in: {out.absolute()}")
    return 0


def _curate_main(argv: list[str]) -> int:
    from .curate_dataset import main as curate_main
    return curate_main(argv)


_SUBCOMMANDS = {
    "documento":  _documento_main,
    "obiettivo":  _obiettivo_main,
    "runs":       _runs_main,
    "report-doc": _report_doc_main,
    "curate":     _curate_main,
}


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")    # ε/ऋ/Ψ su console Windows
    except (AttributeError, OSError):
        pass
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in _SUBCOMMANDS:
        return _SUBCOMMANDS[argv[0]](argv[1:])
    parser = argparse.ArgumentParser(
        description="𝒫₃ Agente ऋ — Analisi critica deterministica",
    )
    parser.add_argument("file", nargs="?", type=str, help="Path al file di testo")
    parser.add_argument("--out", type=str, help="Path output Markdown")
    parser.add_argument("--quiet", action="store_true", help="Solo verdetto ε_ऋ")
    parser.add_argument("--induttivo", action="store_true",
                        help="Esegui anche l'arsenale induttivo (~14 call LLM, default OFF)")
    parser.add_argument("--report-from-db", type=str, metavar="TARGET",
                        help="Genera report markdown da una run già salvata nel DB. "
                             "TARGET = run_uid (Ψ_...), path file, basename, o doc_hash prefix. "
                             "Non rilancia l'analisi.")
    parser.add_argument("--no-json-appendix", action="store_true",
                        help="(con --report-from-db) omette l'appendice JSON dal report")
    args = parser.parse_args(argv)

    # --- Modo 2: report da DB (no re-analisi) ---
    if args.report_from_db:
        return _report_from_db_main(
            args.report_from_db, args.out, no_json=args.no_json_appendix,
        )

    # --- Modo 1: analisi (default) ---
    if args.file:
        p = Path(args.file)
        if not p.exists():
            print(f"[ERRORE] File non trovato: {args.file}")
            return 1
        testo = p.read_text(encoding="utf-8")
        nome_doc = p.name
    else:
        testo = "Gorgia sostiene che il logos è un potere sull'anima. Ovviamente la verità non esiste."
        nome_doc = "TESTO_TEST"

    rapporto = analizza(testo, induttivo_llm=args.induttivo, verbose=not args.quiet)

    if args.file:
        esito = save_run(rapporto, file_path=p)
        if not args.quiet:
            print(f"[DB] salvato: {esito['run_uid']}")

    md = _build_markdown(rapporto, nome_doc)
    if not args.quiet:
        print("\n" + "═" * 60)
        print(md)
        print("═" * 60)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8")
        print(f"[OK] Report salvato in: {out_path.absolute()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
