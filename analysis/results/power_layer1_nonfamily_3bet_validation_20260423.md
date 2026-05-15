# POWER_LOTTO Layer-1 nonfamily 3bet validation (2026-04-23)

- Final decision: **REJECT_ALL_NONFAMILY_LAYER1_3BET**
- Leakage check: **PASS**
- Best candidate: `residue_structure_stability_3bet` (WATCH)
- Best 150/500/1500 raw edge: +2.17% / +3.23% / +1.77%

| Candidate | Decision | 150 Edge | 500 Edge | 1500 Edge | 150 p | 500 p | 1500 p | 150 d | 500 d | 1500 d | 150 Eff | 500 Eff | 1500 Eff | McNemar |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| dispersion_state_transition_3bet | REJECT | +2.83% | +1.23% | +1.57% | 0.2886 | 0.5473 | 0.3184 | 0.616 | 0.017 | 0.526 | 79.9% | 51.5% | 64.0% | not triggered |
| odd_tail_imbalance_3bet | REJECT | +0.83% | +0.83% | +0.77% | 0.3881 | 0.5871 | 0.4726 | 0.297 | -0.180 | 0.081 | 23.5% | 34.8% | 31.4% | not triggered |
| zone_transition_tensor_3bet | WATCH | +1.50% | +1.43% | +0.97% | 0.2587 | 0.2090 | 0.4030 | 0.785 | 0.802 | 0.307 | 42.3% | 59.8% | 39.5% | not triggered |
| residue_structure_stability_3bet | WATCH | +2.17% | +3.23% | +1.77% | 0.4030 | 0.1194 | 0.2189 | 0.326 | 1.393 | 0.903 | 61.1% | 134.9% | 72.2% | not triggered |

## Failure gates by candidate

- `dispersion_state_transition_3bet` → **REJECT**: recent_150: permutation_p>=0.05, recent_150: cohens_d<=1.0, recent_150: per_bet_efficiency<=80%, recent_500: permutation_p>=0.05, recent_500: cohens_d<=1.0, recent_500: per_bet_efficiency<=80%, recent_1500: permutation_p>=0.05, recent_1500: cohens_d<=1.0, recent_1500: per_bet_efficiency<=80%
- `odd_tail_imbalance_3bet` → **REJECT**: recent_150: permutation_p>=0.05, recent_150: cohens_d<=1.0, recent_150: per_bet_efficiency<=80%, recent_500: permutation_p>=0.05, recent_500: cohens_d<=1.0, recent_500: per_bet_efficiency<=80%, recent_1500: permutation_p>=0.05, recent_1500: cohens_d<=1.0, recent_1500: per_bet_efficiency<=80%
- `zone_transition_tensor_3bet` → **WATCH**: recent_150: permutation_p>=0.05, recent_150: cohens_d<=1.0, recent_150: per_bet_efficiency<=80%, recent_500: permutation_p>=0.05, recent_500: cohens_d<=1.0, recent_500: per_bet_efficiency<=80%, recent_1500: permutation_p>=0.05, recent_1500: cohens_d<=1.0, recent_1500: per_bet_efficiency<=80%
- `residue_structure_stability_3bet` → **WATCH**: recent_150: permutation_p>=0.05, recent_150: cohens_d<=1.0, recent_150: per_bet_efficiency<=80%, recent_500: permutation_p>=0.05, recent_1500: permutation_p>=0.05, recent_1500: cohens_d<=1.0, recent_1500: per_bet_efficiency<=80%
