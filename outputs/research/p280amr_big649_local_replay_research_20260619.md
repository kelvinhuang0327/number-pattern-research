# P280AM-R — BIG 6/49 Local Replay Research (Research-Only)

> Retrospective historical replay. NOT prediction-success, production readiness, promotion, or activation. No real publication, pre-draw manifest, official target/deadline lookup, or publication PR was performed.

- task_id: `P280AM-R`
- final_classification: `P280AMR_BIG649_LOCAL_REPLAY_RESEARCH_PR_OPEN_NO_PUBLICATION`
- origin/main: `25e7f8520164aaf61f440a866a11eca403bb76a3`
- DB read policy: `READ_ONLY_URI_MODE_RO_PLUS_QUERY_ONLY_ONE_SNAPSHOT`
- DB opened/queried/copied/written: True/True/False/False (query_only=True)
- result_digest: `ecf422f17db35d54dc31eb0be35f59ab4491935d0668c2d40784697ed9e969e3`

## Dataset

- source: BIG_LOTTO canonical view draws_big_lotto_canonical_main
- rows: **2117** (96000001 2007/01/02 → 115000062 2026/06/16)
- ordering: `DATE_ORDER_EQUALS_DRAW_INT_ORDER`; duplicate ids/dates: 0/0; invalid tickets: 0
- min history: 500; eligible targets: 1617; replayed: 1617
- history cutoff rule: history strictly before target draw; cutoff = previous draw id
- outcome-leakage guard: target outcome never passed to adapter; adapter rejects target-in-history and forbidden metadata keys

## Strategies (exact 11)

- `bet2_fourier_expansion_biglotto`
- `biglotto_deviation_2bet`
- `biglotto_echo_aware_3bet`
- `biglotto_triple_strike`
- `biglotto_ts3_markov_4bet_w30`
- `cold_complement_biglotto`
- `coldpool15_biglotto`
- `fourier30_markov30_biglotto`
- `markov_2bet_biglotto`
- `markov_single_biglotto`
- `ts3_regime_3bet`

## Duplicate-ticket reduction (frozen bet_index=1 vs remediated)

- full replay (n=1617): avg frozen unique tickets **6.14** → remediated **10.88** (gain 4.74)
- draws with frozen duplicates: 1617/1617; with remediated duplicates: 190/1617
- adapter resolution: 1427/1617 resolved to 11 unique; 190/1617 would `UNRESOLVED_DUPLICATE_STOP` (best-effort forced duplicate in replay)
- avg frozen duplicate groups/draw: 3.03

Analytic single-ticket random prize-aware win probability: **0.03095** (hit≥3 0.01864 + 2+special 0.01231).

## Horizon results

### short (n=100) 114000078 → 115000062

| combination | k | prize-aware win rate | 95% CI | random mean | p vs random | beats random | beats all_11 |
|---|---|---|---|---|---|---|---|
| all_11_adapter_unique | 11 | 0.1700 | [0.1000,0.2500] | 0.2905 | 1.0000 | no | — |
| top_k_by_historical_training_only | 1 | 0.0100 | [0.0000,0.0300] | 0.0294 | 0.9502 | no | no |
| top_k_by_historical_training_only | 3 | 0.0500 | [0.0100,0.1000] | 0.0873 | 0.9652 | no | no |
| top_k_by_historical_training_only | 5 | 0.1000 | [0.0498,0.1600] | 0.1425 | 0.9353 | no | no |
| top_k_by_historical_training_only | 7 | 0.1200 | [0.0600,0.1900] | 0.1976 | 0.9950 | no | no |
| top_k_by_historical_training_only | 11 | 0.1700 | [0.1000,0.2400] | 0.2905 | 1.0000 | no | no |
| diversity_greedy_overlap_minimized | 3 | 0.0500 | [0.0100,0.0900] | 0.0873 | 0.9652 | no | no |
| diversity_greedy_overlap_minimized | 5 | 0.1200 | [0.0600,0.1900] | 0.1425 | 0.7910 | no | no |
| diversity_greedy_overlap_minimized | 7 | 0.1600 | [0.0900,0.2400] | 0.1976 | 0.8806 | no | no |
| diversity_greedy_overlap_minimized | 11 | 0.1700 | [0.1000,0.2402] | 0.2905 | 1.0000 | no | no |
| per_family_cap_derived_heuristic | 7 | 0.0900 | [0.0400,0.1500] | 0.1976 | 1.0000 | no | no |

### medium (n=300) 112000110 → 115000062

| combination | k | prize-aware win rate | 95% CI | random mean | p vs random | beats random | beats all_11 |
|---|---|---|---|---|---|---|---|
| all_11_adapter_unique | 11 | 0.2400 | [0.1900,0.2900] | 0.2895 | 0.9652 | no | — |
| top_k_by_historical_training_only | 1 | 0.0333 | [0.0167,0.0534] | 0.0304 | 0.4478 | no | no |
| top_k_by_historical_training_only | 3 | 0.0933 | [0.0600,0.1267] | 0.0892 | 0.4527 | no | no |
| top_k_by_historical_training_only | 5 | 0.1400 | [0.1033,0.1800] | 0.1436 | 0.6517 | no | no |
| top_k_by_historical_training_only | 7 | 0.1767 | [0.1333,0.2200] | 0.1960 | 0.8706 | no | no |
| top_k_by_historical_training_only | 11 | 0.2400 | [0.1900,0.2900] | 0.2895 | 0.9652 | no | no |
| diversity_greedy_overlap_minimized | 3 | 0.0933 | [0.0600,0.1267] | 0.0892 | 0.4527 | no | no |
| diversity_greedy_overlap_minimized | 5 | 0.1433 | [0.1033,0.1800] | 0.1436 | 0.5721 | no | no |
| diversity_greedy_overlap_minimized | 7 | 0.1867 | [0.1433,0.2300] | 0.1960 | 0.7114 | no | no |
| diversity_greedy_overlap_minimized | 11 | 0.2400 | [0.1933,0.2900] | 0.2895 | 0.9652 | no | no |
| per_family_cap_derived_heuristic | 7 | 0.1767 | [0.1367,0.2201] | 0.1960 | 0.8706 | no | no |

### long (n=750) 108000106 → 115000062

| combination | k | prize-aware win rate | 95% CI | random mean | p vs random | beats random | beats all_11 |
|---|---|---|---|---|---|---|---|
| all_11_adapter_unique | 11 | 0.2467 | [0.2160,0.2787] | 0.2905 | 0.9950 | no | — |
| top_k_by_historical_training_only | 1 | 0.0320 | [0.0200,0.0440] | 0.0308 | 0.4577 | no | no |
| top_k_by_historical_training_only | 3 | 0.0960 | [0.0760,0.1174] | 0.0901 | 0.3184 | no | no |
| top_k_by_historical_training_only | 5 | 0.1520 | [0.1267,0.1787] | 0.1457 | 0.3582 | no | no |
| top_k_by_historical_training_only | 7 | 0.1867 | [0.1573,0.2147] | 0.1965 | 0.7562 | no | no |
| top_k_by_historical_training_only | 11 | 0.2467 | [0.2173,0.2787] | 0.2905 | 0.9950 | no | no |
| diversity_greedy_overlap_minimized | 3 | 0.1040 | [0.0827,0.1253] | 0.0901 | 0.1144 | no | no |
| diversity_greedy_overlap_minimized | 5 | 0.1507 | [0.1240,0.1760] | 0.1457 | 0.3831 | no | no |
| diversity_greedy_overlap_minimized | 7 | 0.1947 | [0.1667,0.2227] | 0.1965 | 0.5373 | no | no |
| diversity_greedy_overlap_minimized | 11 | 0.2467 | [0.2160,0.2773] | 0.2905 | 0.9950 | no | no |
| per_family_cap_derived_heuristic | 7 | 0.1773 | [0.1493,0.2040] | 0.1965 | 0.9353 | no | no |

## Best observation-only candidates (beat equal-budget random)

- None. No combination beat the equal-budget random baseline (above its 97.5 pct).

## Multiple-testing warning

Many combinations x k x horizons were compared. Monte-Carlo p-values are uncorrected; apply Bonferroni/BH before any inferential claim. Treat all results as observation-only research.

## Limitations

- Retrospective replay against historical outcomes is not prospective/future-only validation.
- Multiple combinations x k x horizons were compared; p-values are uncorrected (multiple-testing risk).
- top_k_by_historical_training_only uses expanding-window training but remains susceptible to limited training tails.
- Random baselines estimate expected portfolio behaviour via 200 seeded replicates, not exhaustively.
- BIG 6/49 first-zone signal has prior NULL findings (L82/L90/L91); replay edges may be statistical noise.
- Adapter candidate selection is deterministic canonical-order, not outcome-aware; this is preserved unchanged.

## Next recommended research step

If any observation-only candidate beats both the equal-budget random baseline and all_11_adapter_unique with stability across horizons, request separate Owner authorization for an independent leakage/multiple-testing audit before any future-only/OOS evaluation. No publication or activation is implied.

## Governance flags

- prediction_success_claim: False
- strategy_promoted: False
- activation_authorized: False
- registry_mutated: False
- production_write: False
- real_publication_performed: False
- official_target_lookup: False
- official_deadline_lookup: False
- pre_draw_manifest_created: False
- publication_pr_created: False
- post_draw_evaluation_of_real_publication: False
