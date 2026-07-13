"""resh/epsilon.py — Calcolo ε_ऋ ∈ (0,1) come media geometrica pesata.

Formula:
    ε_ऋ = exp( Σ w_i · log(max(c_i, 1e-3)) )

dove Σ w_i = 1. La media geometrica pesata è zero-sensitive (un componente
≈0 abbatte ε): clamp inferiore a 1e-3 evita -inf ma preserva il segnale di
veto parziale.

Componenti (9) e pesi default (ricalibrati Σ_w 2026-06-12, triage F2):
  trasparenza_premesse      0.10    (PremessaAnalisi.score; era 0.18)
  validita_formale          0.13    (sequitur: 1 - penalità_non_sequitur; van Dalen ⊢)
  assenza_fallacie          0.09    (MAFALDA: 1 - frac_fallacie)
  struttura_argomentativa   0.18    (n_argomenti normalizzato + densità; era 0.15)
  coesione_semantica        0.12    (coerenza.coesione_locale)
  coerenza_tematica         0.08    (coerenza.coerenza_tematica_score)
  qualita_sintattica        0.10    (profilo_linguistico.qualita_sintattica)
  bias_linguistico          0.08    (1 - booster_ratio/0.1; hedging NON erode — B1)
  credibilita_fonte         0.07    (autorita.credibilita)

NB: `validita_formale` (entailment) e `assenza_fallacie` (MAFALDA) sono assi
ORTOGONALI — un non-sequitur «pulito» non ha fallacia; un argomento valido può
essere fallace. Discernerli preserva *quale* dimensione cede (vs il vecchio
`validita_argomenti = 1 - frac_fallacie` che li fondeva).

Σ w_i = 1.00 — verificato a init time.

Pesi configurabili via `CONFIG.resh.epsilon.<key>` (TOML `[resh.epsilon]`).
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np


COMPONENTI = (
    "trasparenza_premesse",
    "validita_formale",         # sequitur/entailment (van Dalen ⊢)
    "assenza_fallacie",         # MAFALDA
    "struttura_argomentativa",
    "coesione_semantica",
    "coerenza_tematica",
    "qualita_sintattica",
    "bias_linguistico",
    "credibilita_fonte",
    "integrita_obiettivo",      # incoerenza INTRINSECA di O (None con O deterministico → escluso)
)


PESI_DEFAULT: dict[str, float] = {
    # Ricalibrazione Σ_w 2026-06-12 (triage falla F2 sanità ordinale, «si» su
    # proposta misurata offline): trasparenza 0.18→0.10 (puniva 0.1 la prosa
    # filosofica reale — S5 e S6 — ed esentava per ripesatura i testi brevi
    # manipolativi dove non è misurabile), struttura 0.15→0.18 (unico
    # componente che discrimina S1/S2≈0.08 dai testi argomentati ≥0.23).
    # Ripristina S1<S5, S1<S6, S2<S5 sul corpus stress. PROVVISORIA fino alla
    # calibrazione su 30+ testi annotati (TODO [#RESH]). I riferimenti ε
    # pre-2026-06-12 (report stress F0/F5, Ψ_fb00ac072cb8_D001=0.5147) restano
    # storici: non confrontabili coi run successivi.
    "trasparenza_premesse":     0.10,
    "validita_formale":         0.13,   # ex validita_argomenti 0.22, ripartita…
    "assenza_fallacie":         0.09,   # …in 0.13 (sequitur) + 0.09 (fallacie)
    "struttura_argomentativa":  0.18,
    "coesione_semantica":       0.12,
    "coerenza_tematica":        0.08,
    "qualita_sintattica":       0.10,
    "bias_linguistico":         0.08,
    "credibilita_fonte":        0.07,
    # Peso NON tarato (scelta, Σ_w corpus). I 9 pesi sopra sommano già a 1; con
    # questo la somma è 1.10 → `_validate_pesi` normalizza, e il reweight su
    # `presenti` di `calcola_epsilon` fa sì che con O deterministico (componente
    # None → escluso) eps_resh sia IDENTICO a prima (backward-compat).
    "integrita_obiettivo":      0.10,
}


def _pesi_from_config() -> dict[str, float]:
    try:
        from config import CONFIG
    except Exception:
        return dict(PESI_DEFAULT)
    resh_cfg = getattr(CONFIG, "resh", None)
    if resh_cfg is None:
        return dict(PESI_DEFAULT)
    eps_cfg = getattr(resh_cfg, "epsilon", None)
    if eps_cfg is None:
        return dict(PESI_DEFAULT)
    out = dict(PESI_DEFAULT)
    for k in COMPONENTI:
        v = getattr(eps_cfg, k, None)
        if isinstance(v, (int, float)):
            out[k] = float(v)
    return out


def _validate_pesi(pesi: dict[str, float]) -> dict[str, float]:
    """Normalizza pesi a Σ=1 se la somma diverge (clamp +/-2%)."""
    s = sum(pesi.values())
    if s <= 0:
        return dict(PESI_DEFAULT)
    if abs(s - 1.0) > 1e-6:
        return {k: v / s for k, v in pesi.items()}
    return pesi


def calcola_epsilon(
    componenti: dict[str, float],
    pesi:       Optional[dict[str, float]] = None,
) -> tuple[float, dict[str, float], dict[str, float]]:
    """Calcola ε_ऋ come media geometrica pesata sui componenti MISURATI.

    Un componente con valore `None` è «non misurabile» → **escluso** (non
    riempito con un valore finto, che falserebbe la metrica). I pesi vengono
    ripesati sui componenti presenti (somma=1).

    Returns:
      (eps, componenti_clamped, pesi_normalizzati)
      - eps: float ∈ (0, 1]   (0.5 nel caso degenere: nulla di misurabile)
      - componenti_clamped: dict — SOLO i presenti, clampati a [1e-3, 1.0]
      - pesi_normalizzati: dict — pesi dei presenti, ripesati (somma=1)
    """
    pesi = pesi if pesi is not None else _pesi_from_config()
    pesi = _validate_pesi(pesi)

    # Includi SOLO i componenti misurati: `None` = «non misurabile» → ESCLUSO
    # dall'aggregazione (non riempito con un valore finto). ε si calcola su ciò
    # che si è potuto misurare, ripesando i pesi sui presenti. Così un componente
    # assente non ha effetto su ε (≠ 0.5, che penalizzerebbe con log 0.5·w).
    presenti = [k for k in COMPONENTI if componenti.get(k) is not None]
    if not presenti:
        # nulla di misurabile (testo degenere): nessun giudizio possibile
        return 0.5, {}, {}

    w_sum     = sum(pesi[k] for k in presenti) or 1.0
    pesi_norm = {k: pesi[k] / w_sum for k in presenti}     # Σ=1 sui presenti

    clamped = {k: max(1e-3, min(1.0, float(componenti[k]))) for k in presenti}
    log_sum = sum(pesi_norm[k] * math.log(clamped[k]) for k in presenti)
    eps = math.exp(log_sum)
    return round(eps, 4), clamped, pesi_norm


# `applica_modulatore_malafede` RIMOSSA (ADR-005, eseguita 2026-06-12): era un
# no-op dal freeze Σ_w 2026-05-20. In trash/2026-06-12/resh/ con nota. Vietato
# reintrodurre modulatori deterministici di ε senza ADR di rifondazione.
