# Report STRESS resh — 2026-06-11

firma: modello gemma-4-31b-it (gemma-31) · ts 2026-06-11T15:38:06

> Formatter deterministico. Dati grezzi per fase, criteri pre-dichiarati,
> falle con triage. Livello STRESS: comportamento di sistema, non capacità
> vs gold (per quella: eval_inclosura/eval_trilemma).

## Corpus e aspettative (verbatim dal manifest)

- **S1** `S1_strawman_manipolativo.txt` (459 char, sha256 `e853609903cf5513…`): {"eps": "fascia bassa", "malafede": "marcata (latente autoritario)", "fallacie": ">0"}
- **S2** `S2_dogmatico_corrispondentista.txt` (517 char, sha256 `2b93a44227cb48c6…`): {"trilemma": "C3 USE", "inclosura": "possibile INCL_osservatore", "eps": "medio-basso"}
- **S3** `S3_sonda_inclosura.txt` (354 char, sha256 `0a61fa3dbfa66fc1…`): {"inclosura": "forma presente, modo USE, risposta ACCETTA"}
- **S4** `S4_mu_priest_diagnosis.md` (21677 char, sha256 `f3878c22d65b20ed…`): {"inclosura": "modo DIAGNOSIS (non USE!)", "trilemma": "DIAGNOSIS-heavy"}
- **S5** `S5_cozzo_epistemic_truth_IT.md` (126131 char, sha256 `fb00ac072cb82365…`): {"eps_doc": "~0.51 (riferimento misurato Ψ_fb00ac072cb8_D001)"}
- **S6** `S6_neutro_simboli_logici.md` (5463 char, sha256 `10f0bd043c10dee4…`): {"trilemma": "nessun corno USE", "inclosura": "assente", "eps": "medio-alto"}
- **S7** `S7_narrativo_petit_prince.md` (2344 char, sha256 `6954c9e96f444a53…`): {"nota": "controllo: narrativa, niente patologie gonfiate"}

Ordine ε impegnativo: [['S1', 'S5'], ['S1', 'S6'], ['S2', 'S5']]

## F0
gate: ✅ PASSATO · ts 2026-06-11T02:13:00
```json
{
  "esiti": {
    "S1": {
      "run1": {
        "eps_resh": 0.5318,
        "componenti": {
          "validita_formale": 1.0,
          "assenza_fallacie": 1.0,
          "struttura_argomentativa": 0.0909,
          "coesione_semantica": 0.499,
          "coerenza_tematica": 0.8892,
          "qualita_sintattica": 0.637,
          "bias_linguistico": 1.0,
          "credibilita_fonte": 0.75
        },
        "n_patologie": 0,
        "malafede_mod": 1.0
      },
      "run2": {
        "eps_resh": 0.5318,
        "componenti": {
          "validita_formale": 1.0,
          "assenza_fallacie": 1.0,
          "struttura_argomentativa": 0.0909,
          "coesione_semantica": 0.499,
          "coerenza_tematica": 0.8892,
          "qualita_sintattica": 0.637,
          "bias_linguistico": 1.0,
          "credibilita_fonte": 0.75
        },
        "n_patologie": 0,
        "malafede_mod": 1.0
      },
      "identico": true
    },
    "S2": {
      "run1": {
        "eps_resh": 0.5175,
        "componenti": {
          "validita_formale": 1.0,
          "assenza_fallacie": 1.0,
          "struttura_argomentativa": 0.0769,
          "coesione_semantica": 0.4971,
          "coerenza_tematica": 0.8911,
          "qualita_sintattica": 0.6557,
          "bias_linguistico": 1.0,
          "credibilita_fonte": 0.75
        },
        "n_patologie": 0,
        "malafede_mod": 1.0
      },
      "run2": {
        "eps_resh": 0.5175,
        "componenti": {
          "validita_formale": 1.0,
          "assenza_fallacie": 1.0,
          "struttura_argomentativa": 0.0769,
          "coesione_semantica": 0.4971,
          "coerenza_tematica": 0.8911,
          "qualita_sintattica": 0.6557,
          "bias_linguistico": 1.0,
          "credibilita_fonte": 0.75
        },
        "n_patologie": 0,
        "malafede_mod": 1.0
      },
      "identico": true
    },
    "S3": {
      "run1": {
        "eps_resh": 0.5836,
        "componenti": {
          "validita_formale": 0.751725,
          "assenza_fallacie": 1.0,
          "struttura_argomentativa": 0.1667,
          "coesione_semantica": 0.5662,
          "coerenza_tematica": 0.9278,
          "qualita_sintattica": 0.6609,
          "bias_linguistico": 1.0,
          "credibilita_fonte": 0.75
        },
        "n_patologie": 1,
        "malafede_mod": 1.0
      },
      "run2": {
        "eps_resh": 0.5836,
        "componenti": {
          "validita_formale": 0.751725,
          "assenza_fallacie": 1.0,
          "struttura_argomentativa": 0.1667,
          "coesione_semantica": 0.5662,
          "coerenza_tematica": 0.9278,
          "qualita_sintattica": 0.6609,
          "bias_linguistico": 1.0,
          "credibilita_fonte": 0.75
        },
        "n_patologie": 1,
        "malafede_mod": 1.0
      },
      "identico": true
    },
    "S6": {
      "run1": {
        "eps_resh": 0.4572,
        "componenti": {
          "trasparenza_premesse": 0.1,
          "validita_formale": 0.9551409090909091,
          "assenza_fallacie": 1.0,
          "struttura_argomentativa": 0.2294,
          "coesione_semantica": 0.5544,
          "coerenza_tematica": 0.977,
          "qualita_sintattica": 0.6153,
          "bias_linguistico": 1.0,
          "credibilita_fonte": 0.75
        },
        "n_patologie": 1,
        "malafede_mod": 1.0
      },
      "run2": {
        "eps_resh": 0.4572,
        "componenti": {
          "trasparenza_premesse": 0.1,
          "validita_formale": 0.9551409090909091,
          "assenza_fallacie": 1.0,
          "struttura_argomentativa": 0.2294,
          "coesione_semantica": 0.5544,
          "coerenza_tematica": 0.977,
          "qualita_sintattica": 0.6153,
          "bias_linguistico": 1.0,
          "credibilita_fonte": 0.75
        },
        "n_patologie": 1,
        "malafede_mod": 1.0
      },
      "identico": true
    }
  }
}
```

## F2
gate: ❌ NON PASSATO · ts 2026-06-11T02:13:41
```json
{
  "eps": {
    "S1": 0.5318,
    "S2": 0.5175,
    "S3": 0.5836,
    "S6": 0.4572,
    "S7": 0.2488,
    "S5": 0.5147
  },
  "coppie": [
    [
      "S1",
      "S5"
    ],
    [
      "S1",
      "S6"
    ],
    [
      "S2",
      "S5"
    ]
  ]
}
```

## F1
gate: ✅ PASSATO · ts 2026-06-11T14:02:55
```json
{
  "esiti": {
    "S1": {
      "runs": [
        {
          "corno": "C3",
          "modo_tri": "USE",
          "forma": "presente",
          "modo_incl": "USE",
          "o_dichiarato": "Definire la scienza come l'unico strumento di accesso a una realtà oggettiva e u",
          "errori": []
        },
        {
          "corno": "C3",
          "modo_tri": "USE",
          "forma": "presente",
          "modo_incl": "USE",
          "o_dichiarato": "Affermare che la scienza fornisca una descrizione oggettiva, univoca e diretta d",
          "errori": []
        },
        {
          "corno": "C3",
          "modo_tri": "USE",
          "forma": "presente",
          "modo_incl": "USE",
          "o_dichiarato": "Affermare che la scienza descriva la realtà oggettiva in modo univoco e verifica",
          "errori": []
        }
      ],
      "stabile": {
        "corno": true,
        "modo_tri": true,
        "forma": true,
        "modo_incl": true
      }
    },
    "S2": {
      "runs": [
        {
          "corno": "C3",
          "modo_tri": "USE",
          "forma": "presente",
          "modo_incl": "USE",
          "o_dichiarato": "Definire la scienza come l'unico strumento di accesso alla realtà oggettiva attr",
          "errori": []
        },
        {
          "corno": "C3",
          "modo_tri": "USE",
          "forma": "presente",
          "modo_incl": "USE",
          "o_dichiarato": "Affermare che la scienza descriva la realtà oggettiva in modo esatto e verificab",
          "errori": []
        },
        {
          "corno": "C3",
          "modo_tri": "USE",
          "forma": "presente",
          "modo_incl": "USE",
          "o_dichiarato": "Definire la scienza come l'unico strumento capace di descrivere la realtà oggett",
          "errori": []
        }
      ],
      "stabile": {
        "corno": true,
        "modo_tri": true,
        "forma": true,
        "modo_incl": true
      }
    },
    "S3": {
      "runs": [
        {
          "corno": "C2",
          "modo_tri": "SELF_DIAGNOSIS",
          "forma": "presente",
          "modo_incl": "SELF_DIAGNOSIS",
          "o_dichiarato": "Tracciare i limiti del pensiero e sostenere la necessità che la logica accetti l",
          "errori": []
        },
        {
          "corno": "C2",
          "modo_tri": "SELF_DIAGNOSIS",
          "forma": "presente",
          "modo_incl": "SELF_DIAGNOSIS",
          "o_dichiarato": "Tracciare i limiti del pensiero e sostenere la necessità che la logica sia in gr",
          "errori": []
        },
        {
          "corno": "C2",
          "modo_tri": "SELF_DIAGNOSIS",
          "forma": "presente",
          "modo_incl": "SELF_DIAGNOSIS",
          "o_dichiarato": "Tracciare i limiti del pensiero e sostenere la necessità che la logica integri l",
          "errori": []
        }
      ],
      "stabile": {
        "corno": true,
        "modo_tri": true,
        "forma": true,
        "modo_incl": true
      }
    }
  },
  "stab_corno": 3,
  "stab_forma": 3
}
```

## F3
gate: ✅ PASSATO · ts 2026-06-11T15:38:06
```json
{
  "dal_ts": "2026-06-11T13:44:54",
  "n": 27,
  "flags": {
    "ok": 27
  },
  "anomalie": []
}
```

## F4
gate: ✅ PASSATO · ts 2026-06-11T02:43:53
```json
{
  "esiti": {
    "S1": {
      "eps": 0.5318,
      "n_scartati": 2,
      "err_ind": 2,
      "problemi": []
    },
    "S2": {
      "eps": 0.5175,
      "n_scartati": 2,
      "err_ind": 2,
      "problemi": []
    },
    "S4": {
      "eps": 0.5102,
      "n_scartati": 3,
      "err_ind": 3,
      "problemi": []
    }
  }
}
```

## F5
gate: ✅ PASSATO · ts 2026-06-11T15:38:06
```json
{
  "run": [
    {
      "eps_doc": 0.5207,
      "eps_per_chunk": [
        {
          "id": 0,
          "loc": "pagina ?",
          "eps": 0.4879,
          "char": 5882
        },
        {
          "id": 1,
          "loc": "pagina 2",
          "eps": 0.4763,
          "char": 5811
        },
        {
          "id": 2,
          "loc": "pagina 3",
          "eps": 0.6048,
          "char": 5954
        },
        {
          "id": 3,
          "loc": "pagina 4",
          "eps": 0.5982,
          "char": 5923
        },
        {
          "id": 4,
          "loc": "pagina 5",
          "eps": 0.532,
          "char": 5966
        },
        {
          "id": 5,
          "loc": "pagina 6",
          "eps": 0.5353,
          "char": 5937
        },
        {
          "id": 6,
          "loc": "pagina 7",
          "eps": 0.5356,
          "char": 5982
        },
        {
          "id": 7,
          "loc": "pagina 8",
          "eps": 0.4773,
          "char": 5595
        },
        {
          "id": 8,
          "loc": "pagina 9",
          "eps": 0.5259,
          "char": 5983
        },
        {
          "id": 9,
          "loc": "pagina 9",
          "eps": 0.458,
          "char": 5892
        },
        {
          "id": 10,
          "loc": "pagina 10",
          "eps": 0.4434,
          "char": 5845
        },
        {
          "id": 11,
          "loc": "pagina 11",
          "eps": 0.6085,
          "char": 5818
        },
        {
          "id": 12,
          "loc": "pagina 12",
          "eps": 0.5844,
          "char": 5968
        },
        {
          "id": 13,
          "loc": "pagina 13",
          "eps": 0.4757,
          "char": 5947
        },
        {
          "id": 14,
          "loc": "pagina 14",
          "eps": 0.503,
          "char": 5848
        }
      ],
      "saltati": [
        15,
        16,
        17,
        18,
        19,
        20,
        21
      ],
      "call": 60
    },
    {
      "eps_doc": 0.5207,
      "eps_per_chunk": [
        {
          "id": 0,
          "loc": "pagina ?",
          "eps": 0.4879,
          "char": 5882
        },
        {
          "id": 1,
          "loc": "pagina 2",
          "eps": 0.4763,
          "char": 5811
        },
        {
          "id": 2,
          "loc": "pagina 3",
          "eps": 0.6048,
          "char": 5954
        },
        {
          "id": 3,
          "loc": "pagina 4",
          "eps": 0.5982,
          "char": 5923
        },
        {
          "id": 4,
          "loc": "pagina 5",
          "eps": 0.532,
          "char": 5966
        },
        {
          "id": 5,
          "loc": "pagina 6",
          "eps": 0.5353,
          "char": 5937
        },
        {
          "id": 6,
          "loc": "pagina 7",
          "eps": 0.5356,
          "char": 5982
        },
        {
          "id": 7,
          "loc": "pagina 8",
          "eps": 0.4773,
          "char": 5595
        },
        {
          "id": 8,
          "loc": "pagina 9",
          "eps": 0.5259,
          "char": 5983
        },
        {
          "id": 9,
          "loc": "pagina 9",
          "eps": 0.458,
          "char": 5892
        },
        {
          "id": 10,
          "loc": "pagina 10",
          "eps": 0.4434,
          "char": 5845
        },
        {
          "id": 11,
          "loc": "pagina 11",
          "eps": 0.6085,
          "char": 5818
        },
        {
          "id": 12,
          "loc": "pagina 12",
          "eps": 0.5844,
          "char": 5968
        },
        {
          "id": 13,
          "loc": "pagina 13",
          "eps": 0.4757,
          "char": 5947
        },
        {
          "id": 14,
          "loc": "pagina 14",
          "eps": 0.503,
          "char": 5848
        }
      ],
      "saltati": [
        15,
        16,
        17,
        18,
        19,
        20,
        21
      ],
      "call": 60
    }
  ],
  "chunk_comuni": [
    0,
    1,
    2,
    3,
    4,
    5,
```

## FALLE EMERSE — triage

| id | fase | evidenza grezza | classe (da triage Σ_w/assistente) |
|---|---|---|---|
| F2-S1<S5 | F2 | ε(S1)=0.5318 ≥ ε(S5)=0.5147 | TRIAGED 2026-06-12 (vedi sotto) |
| F2-S1<S6 | F2 | ε(S1)=0.5318 ≥ ε(S6)=0.4572 | TRIAGED 2026-06-12 (vedi sotto) |
| F2-S2<S5 | F2 | ε(S2)=0.5175 ≥ ε(S5)=0.5147 | TRIAGED 2026-06-12 (vedi sotto) |

### Triage Σ_w 2026-06-12 (sessione dedicata, decisione «sia 1 che 2»)
Classe: **doppia causa strutturale**, non rumore — (a) i pesi premiavano l'elusione:
`trasparenza_premesse` (0.18, il peso massimo) puniva 0.1 la prosa filosofica reale
(S5 e S6) ed ESENTAVA per ripesatura i testi brevi manipolativi dove non è
misurabile (S1/S2); (b) lo strawman è una mossa semantica invisibile ai detector
strutturali (`validita_formale`=1.0, `assenza_fallacie`=1.0 su S1).
Rimedi applicati: **pesi ricalibrati** (trasparenza 0.18→0.10, struttura 0.15→0.18;
proposta misurata offline sui componenti persistiti, harness validato 5/5; ordine
ripristinato: S1=0.4997 < S6=0.5084 < S5=0.5553, S2=0.4838; PROVVISORI fino a
calibrazione 30+ testi) + **quesito «Squalifica del dissenso»** nel prompt Arsenale
(il lato induttivo nomina la mossa, a parità — ε non la vede e non deve fingere di
vederla). Gli ε di QUESTO report restano riferimenti storici pre-ricalibrazione.
