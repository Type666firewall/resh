"""resh/persistenza.py — Persistenza dei `RapportoResh` su SQLite + firma Ψ §6.

Scopo
-----
Tracciare ogni run di `resh.analizza` su un documento, in modo da poter:
  1. Identificare il documento via sha256 del suo testo (stabile nel tempo).
  2. Comparare run successivi sullo stesso documento (drift di ε_ऋ, evoluzione
     delle patologie rilevate, effetto del cambio di modello/threshold).
  3. Ricostruire la traccia Ψ §6 (frontmatter YAML canonico CLAUDE.md [#VAULT]).

Schema DB (SQLite WAL)
----------------------
  - `documenti`: una riga per file fisico, indicizzata da `doc_hash` sha256.
    Mantiene path, basename, dimensione, prima/ultima visione (bi-temporalità).
  - `analisi`:   una riga per run, con FK su `doc_hash`. Memorizza ε_ऋ,
    fascia/mf, n_premesse/argomenti/fallacie, modello LLM usato, flag sintesi,
    YAML §6 e dump JSON completo per ricostruzione futura.

Soft-delete: nessuno (append-only). Mai DELETE, mai DROP a runtime.

API pubblica
------------
  - `init_db(path=None) -> Path`
  - `save_run(rapporto, *, file_path, model_used=None, synthesis_llm=False) -> dict`
  - `list_runs(doc_hash=None, path=None) -> list[dict]`
  - `compare_runs(doc_hash) -> list[dict]`        # diff sintetico tra run
  - `psi_frontmatter(rapporto, doc_meta) -> str`  # YAML §6 + body markdown

Riferimenti
-----------
  - CLAUDE.md [#MEMORIA]: SQLite WAL + bi-temporalità (`valid_time`+`record_time`).
  - CLAUDE.md [#VAULT]:   schema Ψ canonico.
  - CLAUDE.md [#REGOLE]:  append-only, soft-delete, mai `rm`.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sqlite3
import textwrap
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Optional

from .schemas import RapportoResh


# ─── DB schema & init ──────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documenti (
    doc_hash       TEXT PRIMARY KEY,                  -- sha256(text)
    path_canonico  TEXT NOT NULL,                     -- abs path (ultima vista)
    basename       TEXT NOT NULL,
    size_bytes     INTEGER NOT NULL,
    n_caratteri    INTEGER NOT NULL,
    first_seen     TEXT NOT NULL,                     -- ISO datetime
    last_seen      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analisi (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_hash             TEXT NOT NULL,
    run_uid              TEXT NOT NULL UNIQUE,        -- Ψ_<short>_<seq>
    ts_creazione         TEXT NOT NULL,               -- ISO datetime (record_time)
    eps_resh             REAL NOT NULL,
    eps_stato            TEXT NOT NULL,               -- ">δ" | "<δ"
    fascia_densita       TEXT NOT NULL,
    densita_logica       REAL NOT NULL,
    malafede_mod         REAL NOT NULL,
    n_premesse_esplicite INTEGER NOT NULL,
    n_premesse_implicite INTEGER NOT NULL,
    n_premesse_sospette  INTEGER NOT NULL,
    n_argomenti          INTEGER NOT NULL,
    n_fallacie           INTEGER NOT NULL,
    n_patologie          INTEGER NOT NULL,
    backend_annotazione  TEXT,
    backend_fuzzy        TEXT,
    model_used           TEXT,
    synthesis_llm        INTEGER NOT NULL DEFAULT 0,  -- bool
    sintesi_narrativa    TEXT,
    yaml_psi_frontmatter TEXT NOT NULL,               -- traccia Ψ §6
    componenti_epsilon   TEXT NOT NULL,               -- JSON
    rapporto_json        TEXT NOT NULL,               -- dump completo
    FOREIGN KEY(doc_hash) REFERENCES documenti(doc_hash)
);

CREATE INDEX IF NOT EXISTS idx_analisi_dochash ON analisi(doc_hash);
CREATE INDEX IF NOT EXISTS idx_analisi_ts      ON analisi(ts_creazione);

CREATE TABLE IF NOT EXISTS analisi_documento (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_hash        TEXT NOT NULL,
    run_uid         TEXT NOT NULL UNIQUE,        -- Ψ_<doc12>_D<seq> (D = scope documento)
    ts_creazione    TEXT NOT NULL,
    fonte           TEXT,
    lingua          TEXT,
    n_chunk         INTEGER NOT NULL,
    eps_doc         REAL,                        -- NULL = nessun chunk misurato
    profilo         TEXT,
    model_used      TEXT,
    assi_chunk      TEXT,
    -- onestà del run: un run con buchi li dichiara per sempre nel record
    call_eseguite   INTEGER,
    n_saltati       INTEGER NOT NULL,
    saltati         TEXT NOT NULL,               -- JSON: id chunk non analizzati (budget)
    n_parti_errore  INTEGER NOT NULL,            -- parti induttive rimaste in errore
    prompts_sha256  TEXT,                        -- versione prompts_resh.md usata
    obiettivo_json  TEXT,
    sintesi_doc     TEXT,
    eps_per_chunk   TEXT NOT NULL,               -- JSON
    rapporto_json   TEXT NOT NULL,               -- dump completo (fonte di verità)
    FOREIGN KEY(doc_hash) REFERENCES documenti(doc_hash)
);

CREATE INDEX IF NOT EXISTS idx_analisi_doc_dochash ON analisi_documento(doc_hash);
CREATE INDEX IF NOT EXISTS idx_analisi_doc_ts      ON analisi_documento(ts_creazione);
"""


# ANCORATO alla directory del package (come cache.py): `parent.parent` era un
# residuo dell'albero P3 originario (resh/ come sotto-package → ../db cadeva nel
# progetto; con resh/ sul Desktop finiva sul Desktop). Override: env `P3_RESH_DB`.
def _db_root() -> Path:
    env = os.getenv("P3_RESH_DB")
    return Path(env) if env else Path(__file__).resolve().parent / "db"


_DEFAULT_DB = _db_root() / "resh_analyses.db"


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: Optional[Path] = None) -> Path:
    """Crea il DB se non esiste. Idempotente."""
    db_path = Path(path) if path else _DEFAULT_DB
    conn = _connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()
    return db_path


# ─── document metadata ─────────────────────────────────────────────────

def file_metadata(file_path: str | Path) -> dict:
    """Calcola sha256, dimensioni, basename del file."""
    p = Path(file_path).resolve()
    raw = p.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    return {
        "doc_hash":     digest,
        "path":         str(p),
        "basename":     p.name,
        "size_bytes":   len(raw),
        "n_caratteri": len(raw.decode("utf-8", errors="replace")),
        "text":         raw.decode("utf-8", errors="replace"),
    }


def _upsert_documento(conn: sqlite3.Connection, meta: dict) -> None:
    """Insert o aggiorna last_seen + path canonico per doc già visto."""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    row = conn.execute(
        "SELECT doc_hash FROM documenti WHERE doc_hash=?", (meta["doc_hash"],)
    ).fetchone()
    if row is None:
        conn.execute(
            """INSERT INTO documenti
               (doc_hash, path_canonico, basename, size_bytes, n_caratteri,
                first_seen, last_seen)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (meta["doc_hash"], meta["path"], meta["basename"],
             meta["size_bytes"], meta["n_caratteri"], now, now),
        )
    else:
        conn.execute(
            """UPDATE documenti SET path_canonico=?, last_seen=?
                 WHERE doc_hash=?""",
            (meta["path"], now, meta["doc_hash"]),
        )


# ─── ID univoco run (Ψ_<doc_short>_<seq>) ──────────────────────────────

def _next_run_uid(conn: sqlite3.Connection, doc_hash: str) -> str:
    """Costruisce un id_operativo Ψ deterministico per la run corrente.

    Forma: `Ψ_<doc12>_<seq>` dove `doc12` sono i primi 12 char dell'sha256
    del testo (identità del documento) e `seq` è il progressivo della run
    sullo stesso documento. È riproducibile e collegabile (CLAUDE.md
    [#VAULT]: «codice univoco dal simplesso» — qui da hash testo + seq).
    """
    seq_row = conn.execute(
        "SELECT COUNT(*) FROM analisi WHERE doc_hash=?", (doc_hash,)
    ).fetchone()
    seq = int(seq_row[0]) + 1
    return f"Ψ_{doc_hash[:12]}_{seq:03d}"


# ─── Ψ frontmatter §6 ──────────────────────────────────────────────────

def _yaml_escape(s: str) -> str:
    """Quote sicuro per stringhe inline YAML."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def psi_frontmatter(rapporto: RapportoResh, doc_meta: dict, run_uid: str) -> str:
    """Produce il frontmatter YAML §6 (CLAUDE.md [#VAULT]) + body markdown.

    Schema Ψ:
      nome_Ψ, id_operativo, firma=Σ⁸, Λ_𝔄=ऋ, metodo_γ=γ_analizza_async,
      ε_vettore (solo ऋ_dubbio valorizzato, Θ/ב = None → ∅ indeterminato),
      ε_stato in {">δ","<δ","∅"} (δ = 0.3 default), atto_trasformazione,
      G_genealogia, operazioni_applicate, τ_tempo_logico.
    """
    today = datetime.date.today().isoformat()
    eps = float(rapporto.eps_resh)
    eps_stato = ">δ" if eps > 0.3 else ("<δ" if eps > 0 else "∅ indeterminato")

    # Premesse-Conclusioni per atto_trasformazione (sintesi)
    n_esp = len(rapporto.premesse.esplicite)
    n_imp = len(rapporto.premesse.implicite)
    n_sus = len(rapporto.premesse.sospette)
    n_arg = len(rapporto.inventario)
    n_pat = len(rapporto.patologie_strutturate)

    nome = _yaml_escape(f"Analisi ऋ — {doc_meta['basename']}")
    atto = _yaml_escape(
        f"da testo grezzo ({doc_meta['n_caratteri']} char) a rapporto "
        f"ε_ऋ={eps:.4f} | premesse(esp={n_esp},imp={n_imp},sus={n_sus}) | "
        f"argomenti={n_arg} | patologie={n_pat}"
    )

    fm = textwrap.dedent(f"""\
        ---
        # FONDAMENTO
        nome_Ψ:         "{nome}"
        id_operativo:   {run_uid}

        # GERARCHIA E AUTORITÀ
        firma:          "Σ⁸"
        Λ_𝔄:           "ऋ"
        metodo_γ:       "γ_analizza_async"

        # EFFICACIA TRIDIMENSIONALE (ε)
        ε_vettore:
          Θ_dogma:      null
          ऋ_dubbio:     {eps:.4f}
          ב_memoria:    null
        ε_stato:        "{eps_stato}"

        # DINAMICA DELL'ATTO (α)
        atto_trasformazione:   "{atto}"
        G_genealogia:           "[[{doc_meta['doc_hash'][:12]}]]"
        operazioni_applicate:   "[[γ_annota γ_encode γ_profilo_linguistico γ_rileva_fallacie γ_estrai_argomenti γ_analizza_coerenza γ_bias_autorita γ_profilo_stilistico γ_analizza_premesse γ_calcola_epsilon γ_densita_fuzzy]]"

        # EMERGENZA E GENEALOGIA
        τ_tempo_logico:
          VERSIONE:          V.1.0
          CREAZIONE:         {today}
          ULTIMA_MODIFICA:   {today}

        # METADATI DOCUMENTO
        documento:
          basename:    "{_yaml_escape(doc_meta['basename'])}"
          sha256:      "{doc_meta['doc_hash']}"
          size_bytes:  {doc_meta['size_bytes']}
          n_caratteri: {doc_meta['n_caratteri']}

        # METRICHE FUZZY
        fascia_densita:  "{rapporto.fascia_densita}"
        densita_logica:  {rapporto.densita_logica}
        malafede_mod:    {rapporto.malafede_mod}
        ---

        # 𐤑 — Rapporto ऋ sintetico

        - **ε_ऋ** = `{eps:.4f}` ({eps_stato})
        - **Premesse**: esplicite={n_esp} · implicite={n_imp} · sospette={n_sus}
        - **Argomenti** identificati: {n_arg}
        - **Patologie strutturate**: {n_pat}
        - **Fascia densità**: `{rapporto.fascia_densita}` (mf={rapporto.malafede_mod})
        """)
    return fm


# ─── save run ──────────────────────────────────────────────────────────

def _serialize_rapporto(rapporto: RapportoResh) -> dict:
    """Dump RapportoResh in dict serializzabile JSON (gestisce dataclass nested)."""
    def _coerce(v: Any) -> Any:
        if is_dataclass(v) and not isinstance(v, type):
            return {k: _coerce(val) for k, val in asdict(v).items()}
        if isinstance(v, dict):
            return {k: _coerce(val) for k, val in v.items()}
        if isinstance(v, (list, tuple, set, frozenset)):
            return [_coerce(x) for x in v]
        if hasattr(v, "value"):  # Enum / StrEnum
            return v.value
        return v
    return _coerce(rapporto)


def save_run(
    rapporto: RapportoResh,
    *,
    file_path: str | Path,
    model_used: Optional[str] = None,
    synthesis_llm: bool = False,
    db_path: Optional[Path] = None,
) -> dict:
    """Salva la run nel DB. Ritorna dict con `run_uid`, `doc_hash`, `psi`, `db`.

    Idempotenza: ogni run è registrata indipendentemente; il `run_uid` è
    progressivo per documento. Lo stesso file analizzato due volte produce
    due record in `analisi` (per confronto temporale), una riga sola in
    `documenti` (con `last_seen` aggiornato).
    """
    db = init_db(db_path)
    meta = file_metadata(file_path)

    conn = _connect(db)
    try:
        _upsert_documento(conn, meta)
        run_uid = _next_run_uid(conn, meta["doc_hash"])
        psi = psi_frontmatter(rapporto, meta, run_uid)
        now = datetime.datetime.now().isoformat(timespec="seconds")

        eps_stato = ">δ" if rapporto.eps_resh > 0.3 else "<δ"
        rapporto_dict = _serialize_rapporto(rapporto)
        backend_annot = rapporto.yaml_output.get("backend", {}).get("annotazione", "?")
        backend_fuzzy = rapporto.yaml_output.get("backend", {}).get("fuzzy", "?")

        conn.execute(
            """INSERT INTO analisi
               (doc_hash, run_uid, ts_creazione, eps_resh, eps_stato,
                fascia_densita, densita_logica, malafede_mod,
                n_premesse_esplicite, n_premesse_implicite, n_premesse_sospette,
                n_argomenti, n_fallacie, n_patologie,
                backend_annotazione, backend_fuzzy, model_used, synthesis_llm,
                sintesi_narrativa, yaml_psi_frontmatter,
                componenti_epsilon, rapporto_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                meta["doc_hash"], run_uid, now,
                rapporto.eps_resh, eps_stato,
                rapporto.fascia_densita, rapporto.densita_logica, rapporto.malafede_mod,
                len(rapporto.premesse.esplicite),
                len(rapporto.premesse.implicite),
                len(rapporto.premesse.sospette),
                len(rapporto.inventario),
                sum(1 for p in rapporto.patologie_strutturate
                    if (p.tipo.value if hasattr(p.tipo, "value") else str(p.tipo))
                       == "fallacia_logica"),
                len(rapporto.patologie_strutturate),
                backend_annot, backend_fuzzy,
                model_used, int(bool(synthesis_llm)),
                rapporto.sintesi_narrativa or "",
                psi,
                json.dumps(rapporto.componenti_epsilon, ensure_ascii=False),
                json.dumps(rapporto_dict, ensure_ascii=False, default=str),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "run_uid":  run_uid,
        "doc_hash": meta["doc_hash"],
        "psi":      psi,
        "db":       str(db),
    }


# ─── query helpers ─────────────────────────────────────────────────────

def list_runs(
    doc_hash: Optional[str] = None,
    path: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> list[dict]:
    """Elenca le run note. Filtra per `doc_hash` o per `path` (basename match).

    Ritorna dict con campi sintetici (eps_resh, fascia, ts_creazione, run_uid).
    """
    db = init_db(db_path)
    conn = _connect(db)
    try:
        if doc_hash:
            cur = conn.execute(
                """SELECT a.* FROM analisi a WHERE a.doc_hash=?
                   ORDER BY a.ts_creazione DESC""", (doc_hash,))
        elif path:
            cur = conn.execute(
                """SELECT a.* FROM analisi a
                   JOIN documenti d ON a.doc_hash = d.doc_hash
                   WHERE d.path_canonico=? OR d.basename=?
                   ORDER BY a.ts_creazione DESC""", (path, path))
        else:
            cur = conn.execute(
                "SELECT * FROM analisi ORDER BY ts_creazione DESC LIMIT 200")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def compare_runs(doc_hash: str, db_path: Optional[Path] = None) -> list[dict]:
    """Estrae snapshot comparabili (eps, fascia, n_*) ordinati cronologicamente."""
    db = init_db(db_path)
    conn = _connect(db)
    try:
        cur = conn.execute(
            """SELECT run_uid, ts_creazione, eps_resh, fascia_densita, malafede_mod,
                      n_premesse_implicite, n_argomenti, n_fallacie, n_patologie,
                      model_used, synthesis_llm
                 FROM analisi WHERE doc_hash=?
                 ORDER BY ts_creazione ASC""",
            (doc_hash,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# ─── report markdown da DB ─────────────────────────────────────────────

_COMPONENT_NOTES = {
    "trasparenza_premesse":     "esplicite / totale premesse",
    "validita_argomenti":       "1 - n_fallacie / (n_argomenti·2); fallback su n_frasi se inventario vuoto",
    "struttura_argomentativa":  "n_argomenti / n_frasi (floor 1e-3)",
    "coesione_semantica":       "cosine locale tra embedding di frasi consecutive",
    "coerenza_tematica":        "drift k-segmento + BERTopic n_topics",
    "qualita_sintattica":       "Profiling-UD aggregato (TTR, MTLD, profondità albero...)",
    "bias_linguistico":         "1 - severità media patologie hedging/booster",
    "credibilita_fonte":        "baseline 0.65 + bonus 0.10 se testo pulito",
}


def _format_run_markdown(
    run: dict, doc: dict, rapporto: dict, comp: dict, history: list[dict],
    *, include_json_appendix: bool = True,
) -> str:
    """Formatta in markdown una singola run + storico run sul medesimo doc.

    Funzione pura (no I/O DB). Chiamabile su dict già estratti — utile per
    test e per generare report inline senza ri-aprire il DB.
    """
    out: list[str] = []
    add = out.append

    add(f"# Rapporto resh — `{doc['basename']}`")
    add("")
    add(f"> Analisi prodotta dall'agente ऋ (Dubbio Epistemico) — run `{run['run_uid']}`.")
    add("")

    # Documento
    add("## Documento")
    add("")
    add("| Campo | Valore |")
    add("|---|---|")
    add(f"| basename | `{doc['basename']}` |")
    add(f"| path | `{doc['path_canonico']}` |")
    add(f"| sha256 (prefix) | `{doc['doc_hash'][:24]}…` |")
    add(f"| size | {doc['size_bytes']:,} bytes |")
    add(f"| n_caratteri | {doc['n_caratteri']:,} |")
    add(f"| first_seen | {doc['first_seen']} |")
    add(f"| last_seen | {doc['last_seen']} |")
    add("")

    # Storico run
    if history:
        add("## Storico run su questo documento")
        add("")
        add("| run_uid | timestamp | ε_ऋ | mf | n_pat | n_fall |")
        add("|---|---|---|---|---|---|")
        for r in history:
            current = " ←" if r["run_uid"] == run["run_uid"] else ""
            add(f"| {r['run_uid']}{current} | {r['ts_creazione']} | "
                f"{r['eps_resh']:.4f} | {r.get('malafede_mod', 1.0):.4f} | "
                f"{r.get('n_patologie', '-')} | {r.get('n_fallacie', '-')} |")
        add("")

    # Metriche principali
    add("## Metriche principali")
    add("")
    add(f"- **run_uid**: `{run['run_uid']}`")
    add(f"- **ε_ऋ** = `{run['eps_resh']:.4f}` ({run['eps_stato']})")
    add(f"- **densità premesse implicite** = `{run['densita_logica']:.4f}` "
        f"(fascia: {run['fascia_densita']}) — premesse non dichiarate per token; "
        f"descrittiva, non modula ε")
    add(f"- **malafede_mod** = `{run['malafede_mod']:.4f}` "
        f"{'(storico, disattivato: sempre 1.0)' if run['malafede_mod'] == 1.0 else ''}")
    add(f"- **backend annotazione** = `{run.get('backend_annotazione','?')}` · "
        f"**backend fuzzy** = `{run.get('backend_fuzzy','?')}`")
    add(f"- **modello** = `{run.get('model_used','-')}` · "
        f"**synthesis_llm** = {bool(run.get('synthesis_llm', 0))}")
    add("")
    add("### Conteggi")
    add("")
    add("| Metrica | Valore |")
    add("|---|---|")
    add(f"| premesse esplicite | {run['n_premesse_esplicite']} |")
    add(f"| premesse implicite | {run['n_premesse_implicite']} |")
    add(f"| premesse sospette | {run['n_premesse_sospette']} |")
    add(f"| unità argomentative candidate | {run['n_argomenti']} |")
    add(f"| patologie totali | {run['n_patologie']} |")
    add(f"| di cui fallacie | {run['n_fallacie']} |")
    add("")

    # Componenti epsilon
    add("## Componenti ε_ℜ (media geometrica pesata)")
    add("")
    add("| Componente | Valore | Note |")
    add("|---|---|---|")
    for k, v in comp.items():
        add(f"| `{k}` | {v:.4f} | {_COMPONENT_NOTES.get(k, '')} |")
    add("")

    # Patologie strutturate
    pats = rapporto.get("patologie_strutturate", []) or []
    add(f"## Patologie strutturate ({len(pats)})")
    add("")
    if pats:
        add("| # | tipo | fallacia_l2 | fonte | conf | sev | span | match/contesto |")
        add("|---|---|---|---|---|---|---|---|")
        for i, p in enumerate(sorted(pats, key=lambda x: -x.get("confidence", 0)), 1):
            tipo = p.get("tipo", "?")
            det = p.get("dettaglio", {}) or {}
            fl2 = det.get("fallacia_l2", "-")
            fonte = det.get("fonte", "-")
            conf = p.get("confidence", 0)
            sev = p.get("severita", 0)
            span = p.get("span_char")
            span_str = f"{span[0]}-{span[1]}" if span else "-"
            match = (det.get("match") or det.get("frase") or det.get("contesto") or "-")
            match = match.replace("\n", " ").replace("|", "\\|")
            if len(match) > 120:
                match = match[:117] + "…"
            add(f"| {i} | {tipo} | `{fl2}` | {fonte} | {conf:.3f} | {sev:.3f} | "
                f"{span_str} | {match} |")
    else:
        add("*(nessuna)*")
    add("")

    # Premesse
    prem = rapporto.get("premesse", {}) or {}
    add("## Premesse")
    add("")
    for titolo, key in [("Esplicite", "esplicite"),
                        ("Implicite", "implicite"),
                        ("Sospette", "sospette")]:
        lst = prem.get(key, []) or []
        add(f"### {titolo} ({len(lst)})")
        add("")
        if not lst:
            add("*(nessuna)*")
            add("")
            continue
        for i, p in enumerate(lst, 1):
            if isinstance(p, dict):
                txt = p.get("testo", p.get("text", str(p)))
                score = p.get("score_trasparenza", p.get("score"))
            else:
                txt = str(p)
                score = None
            txt = txt.replace("\n", " ")
            if len(txt) > 250:
                txt = txt[:247] + "…"
            prefix = f"*(score={score})* " if score is not None else ""
            add(f"{i}. {prefix}{txt}")
        add("")

    # Autorità
    aut = rapporto.get("autorita", {}) or {}
    add("## Autorità (bias + credibilità)")
    add("")
    add(f"- fonte: `{aut.get('fonte','-')}`")
    add(f"- expertise: `{aut.get('expertise', False)}`")
    cred = aut.get("credibilita", 0) or 0
    add(f"- credibilità: `{cred:.4f}`")
    add(f"- bias rilevati: `{aut.get('bias_rilevati', [])}`")
    add("")

    # Profilo linguistico
    pl = rapporto.get("profilo_linguistico", {}) or {}
    if pl:
        add("## Profilo linguistico (Profiling-UD)")
        add("")
        add("| Feature | Valore |")
        add("|---|---|")
        for k, v in sorted(pl.items()):
            v_str = f"{v:.4f}" if isinstance(v, float) else str(v)
            add(f"| `{k}` | {v_str} |")
        add("")

    # Coerenza semantica
    cs = rapporto.get("coerenza_semantica", {}) or {}
    if cs:
        add("## Coerenza semantica")
        add("")
        for k, v in cs.items():
            v_str = f"{v:.4f}" if isinstance(v, float) else str(v)
            add(f"- `{k}` = {v_str}")
        add("")

    # Stilometria
    ps = rapporto.get("profilo_stilistico", {}) or {}
    if ps:
        add("## Profilo stilometrico (Biber-style)")
        add("")
        add("| Feature | Valore |")
        add("|---|---|")
        for k, v in sorted(ps.items()):
            v_str = f"{v:.4f}" if isinstance(v, float) else str(v)
            add(f"| `{k}` | {v_str} |")
        add("")

    # Patologie legacy (human-readable)
    pat_legacy = rapporto.get("patologie", []) or []
    if pat_legacy:
        add(f"## Patologie legacy ({len(pat_legacy)} messaggi)")
        add("")
        for i, m in enumerate(pat_legacy, 1):
            add(f"{i}. {m}")
        add("")

    # Sintesi narrativa LLM (se synthesis_llm=True alla run)
    sintesi = rapporto.get("sintesi_narrativa") or run.get("sintesi_narrativa") or ""
    if sintesi.strip():
        add("## Sintesi narrativa (LLM)")
        add("")
        add(f"> Generata con `synthesis_llm=True` da `{run.get('model_used','-')}`. "
            f"**Non altera ε_ऋ**: è puramente descrittiva.")
        add("")
        add(sintesi.strip())
        add("")

    # Firma Ψ §6
    if run.get("yaml_psi_frontmatter"):
        add("## Firma Ψ §6 (frontmatter YAML)")
        add("")
        add("```yaml")
        add(run["yaml_psi_frontmatter"].rstrip())
        add("```")
        add("")

    # Appendice JSON
    if include_json_appendix:
        add("## Appendice — RapportoResh JSON completo")
        add("")
        add("<details>")
        add("<summary>Espandi</summary>")
        add("")
        add("```json")
        add(json.dumps(rapporto, ensure_ascii=False, indent=2))
        add("```")
        add("")
        add("</details>")
        add("")

    return "\n".join(out)


def _resolve_run_query(
    conn: sqlite3.Connection,
    *,
    run_uid: Optional[str],
    doc_hash: Optional[str],
    file_path: Optional[str],
    latest: bool,
) -> Optional[tuple[dict, dict, list[dict]]]:
    """Risolve i filtri (`run_uid` | `doc_hash` | `file_path`) in una riga
    `analisi` + relativo `documenti` + storico run sullo stesso doc.

    Priorità: `run_uid` > `doc_hash` > `file_path`. Se più di un filtro
    matcha e `latest=True`, ritorna l'ultima per ts_creazione.
    """
    row = None
    if run_uid:
        row = conn.execute(
            "SELECT * FROM analisi WHERE run_uid=?", (run_uid,)
        ).fetchone()
    elif doc_hash:
        order = "DESC" if latest else "ASC"
        row = conn.execute(
            f"SELECT * FROM analisi WHERE doc_hash=? "
            f"ORDER BY ts_creazione {order} LIMIT 1",
            (doc_hash,),
        ).fetchone()
    elif file_path:
        p = Path(file_path).resolve()
        order = "DESC" if latest else "ASC"
        row = conn.execute(
            f"""SELECT a.* FROM analisi a
                JOIN documenti d ON a.doc_hash = d.doc_hash
                WHERE d.path_canonico=? OR d.basename=?
                ORDER BY a.ts_creazione {order} LIMIT 1""",
            (str(p), p.name),
        ).fetchone()
    if row is None:
        return None
    run = dict(row)
    doc = dict(conn.execute(
        "SELECT * FROM documenti WHERE doc_hash=?", (run["doc_hash"],)
    ).fetchone())
    history_rows = conn.execute(
        """SELECT run_uid, ts_creazione, eps_resh, malafede_mod,
                  n_patologie, n_fallacie
             FROM analisi WHERE doc_hash=? ORDER BY ts_creazione ASC""",
        (run["doc_hash"],),
    ).fetchall()
    history = [dict(r) for r in history_rows]
    return run, doc, history


def report_markdown(
    *,
    run_uid: Optional[str] = None,
    doc_hash: Optional[str] = None,
    file_path: Optional[str] = None,
    latest: bool = True,
    include_json_appendix: bool = True,
    db_path: Optional[Path] = None,
) -> Optional[str]:
    """Genera un report markdown completo da una run salvata nel DB.

    Filtra per `run_uid` (esatto), `doc_hash` (prefisso accettato), o
    `file_path` (path/basename). Se `latest=True` (default) e il filtro
    matcha più run, prende l'ultima per `ts_creazione`.

    Ritorna `None` se nessuna run matcha il filtro. Lo script di formato
    è il medesimo usato da `cli.py` quando si esegue una nuova analisi,
    ma in più aggiunge storico run e tabella patologie strutturate con
    span/confidence/fonte.

    Use cases:
      - ispezione manuale post-hoc senza ri-lanciare l'analisi
      - confronto tra run successive sullo stesso documento
      - dump per audit
    """
    db = init_db(db_path)
    conn = _connect(db)
    try:
        resolved = _resolve_run_query(
            conn, run_uid=run_uid, doc_hash=doc_hash,
            file_path=file_path, latest=latest,
        )
        if resolved is None:
            return None
        run, doc, history = resolved
        rapporto = json.loads(run["rapporto_json"])
        comp = json.loads(run["componenti_epsilon"])
    finally:
        conn.close()
    return _format_run_markdown(
        run, doc, rapporto, comp, history,
        include_json_appendix=include_json_appendix,
    )


def save_report_markdown(
    out_path: str | Path,
    *,
    run_uid: Optional[str] = None,
    doc_hash: Optional[str] = None,
    file_path: Optional[str] = None,
    latest: bool = True,
    include_json_appendix: bool = True,
    db_path: Optional[Path] = None,
) -> Optional[Path]:
    """Comodità: chiama `report_markdown` e scrive il risultato su disco.

    Ritorna il `Path` scritto, o `None` se nessuna run matcha il filtro.
    """
    md = report_markdown(
        run_uid=run_uid, doc_hash=doc_hash, file_path=file_path,
        latest=latest, include_json_appendix=include_json_appendix,
        db_path=db_path,
    )
    if md is None:
        return None
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    return out


# ─── run DOCUMENTALI (RapportoDocumento, scope=paper intero) ───────────


def _next_run_uid_documento(conn: sqlite3.Connection, doc_hash: str) -> str:
    """Come `_next_run_uid`, con marcatore di scope `D` (documento): Ψ_<doc12>_D<seq>.

    Tabella separata ⇒ sequenza separata; il marcatore evita collisioni di uid
    con le run per-testo sullo stesso documento.
    """
    seq_row = conn.execute(
        "SELECT COUNT(*) FROM analisi_documento WHERE doc_hash=?", (doc_hash,)
    ).fetchone()
    return f"Ψ_{doc_hash[:12]}_D{int(seq_row[0]) + 1:03d}"


def _conta_parti_errore(chunk_records: list[dict], obiettivo: Optional[dict]) -> int:
    """Conta le parti induttive rimaste in `errore` nei chunk (+ O globale).

    Stessa fenomenologia di `documento._parti_fallite`, ma qui serve solo il
    CONTO per il record di onestà — replicata in locale per non importare
    `documento` (che trascina lo stack LLM) dentro la persistenza.
    """
    n = 0
    if obiettivo and "errore" in obiettivo:
        n += 1
    for rec in chunk_records or []:
        ind = rec.get("ind") or {}
        if isinstance(ind.get("arsenale"), dict) and "errore" in ind["arsenale"]:
            n += 1
        for a in (ind.get("assi") or {}).values():
            if isinstance(a, dict) and "errore" in a:
                n += 1
        for k in ("trilemma", "inclosura"):
            llm = (ind.get(k) or {}).get("llm")
            if isinstance(llm, dict) and "errore" in llm:
                n += 1
    return n


def _prompts_sha256() -> Optional[str]:
    p = Path(__file__).resolve().parent / "prompts" / "prompts_resh.md"
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return None


def _meta_da_testo(testo: str, fonte: str) -> dict:
    """Identità documento quando non c'è un file fisico: sha256 del testo."""
    raw = testo.encode("utf-8")
    return {
        "doc_hash":    hashlib.sha256(raw).hexdigest(),
        "path":        f"(testo) {fonte}",
        "basename":    fonte or "(testo)",
        "size_bytes":  len(raw),
        "n_caratteri": len(testo),
        "text":        testo,
    }


def save_run_documento(
    rap_doc,
    *,
    file_path: Optional[str | Path] = None,
    testo: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> dict:
    """Salva un run documentale (RapportoDocumento, dataclass o dict) nel DB.

    Identità documento: `file_path` (sha256 dei byte) oppure `testo`
    (sha256 utf-8) — uno dei due è obbligatorio. Append-only come `save_run`.
    Ritorna `{run_uid, doc_hash, db}`.
    """
    if hasattr(rap_doc, "as_dict"):
        rap_doc = rap_doc.as_dict()
    if file_path is None and testo is None:
        raise ValueError("serve file_path o testo per l'identità del documento")

    db = init_db(db_path)
    meta = (file_metadata(file_path) if file_path is not None
            else _meta_da_testo(testo, str(rap_doc.get("fonte", ""))))
    m = rap_doc.get("meta", {}) or {}
    saltati = rap_doc.get("saltati") or []
    assi = m.get("assi_chunk")

    conn = _connect(db)
    try:
        _upsert_documento(conn, meta)
        run_uid = _next_run_uid_documento(conn, meta["doc_hash"])
        now = datetime.datetime.now().isoformat(timespec="seconds")
        conn.execute(
            """INSERT INTO analisi_documento
               (doc_hash, run_uid, ts_creazione, fonte, lingua, n_chunk, eps_doc,
                profilo, model_used, assi_chunk, call_eseguite,
                n_saltati, saltati, n_parti_errore, prompts_sha256,
                obiettivo_json, sintesi_doc, eps_per_chunk, rapporto_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                meta["doc_hash"], run_uid, now,
                rap_doc.get("fonte"), rap_doc.get("lingua"),
                int(rap_doc.get("n_chunk") or 0), rap_doc.get("eps_doc"),
                m.get("profilo"), m.get("model"),
                assi if isinstance(assi, str) else json.dumps(assi, ensure_ascii=False),
                m.get("call_eseguite"),
                len(saltati), json.dumps(saltati, ensure_ascii=False),
                _conta_parti_errore(rap_doc.get("chunk") or [],
                                    rap_doc.get("obiettivo")),
                _prompts_sha256(),
                json.dumps(rap_doc.get("obiettivo"), ensure_ascii=False),
                rap_doc.get("sintesi_doc") or "",
                json.dumps(rap_doc.get("eps_per_chunk") or [], ensure_ascii=False),
                json.dumps(rap_doc, ensure_ascii=False, default=str),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {"run_uid": run_uid, "doc_hash": meta["doc_hash"], "db": str(db)}


def list_runs_documento(
    doc_hash: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> list[dict]:
    """Elenca i run documentali (campi sintetici, senza rapporto_json)."""
    db = init_db(db_path)
    conn = _connect(db)
    try:
        cols = ("run_uid, ts_creazione, doc_hash, fonte, lingua, n_chunk, eps_doc, "
                "profilo, model_used, call_eseguite, n_saltati, n_parti_errore")
        if doc_hash:
            cur = conn.execute(
                f"""SELECT {cols} FROM analisi_documento WHERE doc_hash LIKE ?
                    ORDER BY ts_creazione DESC""", (doc_hash + "%",))
        else:
            cur = conn.execute(
                f"SELECT {cols} FROM analisi_documento ORDER BY ts_creazione DESC LIMIT 200")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_run_documento(
    run_uid: Optional[str] = None,
    doc_hash: Optional[str] = None,
    latest: bool = True,
    db_path: Optional[Path] = None,
) -> Optional[dict]:
    """Recupera un run documentale completo; `rapporto` è il dict ricostruito.

    Da qui il report markdown si RIGENERA con `report.genera_report_documento`
    (il dato è canonico, il report è un rendering deterministico).
    """
    db = init_db(db_path)
    conn = _connect(db)
    try:
        if run_uid:
            row = conn.execute(
                "SELECT * FROM analisi_documento WHERE run_uid=?", (run_uid,)
            ).fetchone()
        elif doc_hash:
            order = "DESC" if latest else "ASC"
            row = conn.execute(
                f"""SELECT * FROM analisi_documento WHERE doc_hash LIKE ?
                    ORDER BY ts_creazione {order} LIMIT 1""", (doc_hash + "%",)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM analisi_documento ORDER BY ts_creazione DESC LIMIT 1"
            ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    out = dict(row)
    out["rapporto"] = json.loads(out.pop("rapporto_json"))
    return out
