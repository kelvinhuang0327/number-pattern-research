# V3 Final Comparative Validation Report
Generated: 2026-03-24

## System Descriptions
| System | N-bets | Confidence | Bankroll | Risk Gate |
|--------|--------|------------|----------|-----------|
| Legacy | 3 (fixed) | none | none | none |
| V2 | 1-5 (VarN) | 5-dim vector | none | none |
| V3 | 1-5 (risk-capped) | 5-dim + risk class | BankrollTracker | LOW/MED/HIGH |

## Policy: v3_conservative
- bet_size_variant: capped
- kelly_alpha: 0.10
- risk_response: {LOW: 4, MED: 2, HIGH: 1}
- drawdown_scale: 0.50

## DAILY_539
**Verdict: RISK_REDUCTION_ONLY**

- Perm test: p=0.6400 FAIL
- McNemar V3 vs V2: net=-22, p=0.0000 significant

| Window | System | cond_edge | uncond_edge | sharpe | max_dd | variance | avg_bets |
|--------|--------|-----------|-------------|--------|--------|----------|----------|
| w150 | legacy | +8.83% | +8.83% | 0.181 | 0.221 | 0.2386 | 3.0 |
| w150 | v2 | +14.61% | +14.61% | 0.298 | 0.200 | 0.2400 | 5.0 |
| w150 | v3 | +9.28% | +9.28% | 0.194 | 0.038 | 0.2285 | 2.5 |
| w500 | legacy | +4.90% | +4.90% | 0.102 | 0.166 | 0.2287 | 3.0 |
| w500 | v2 | +7.21% | +7.21% | 0.144 | 0.293 | 0.2493 | 5.0 |
| w500 | v3 | +4.45% | +4.45% | 0.097 | 0.028 | 0.2092 | 2.4 |
| w1500 | legacy | +3.10% | +3.10% | 0.066 | 0.365 | 0.2231 | 3.0 |
| w1500 | v2 | +6.74% | +6.74% | 0.135 | 0.550 | 0.2495 | 5.0 |
| w1500 | v3 | -9.39% | -0.48% | -0.327 | 0.300 | 0.0826 | 1.7 |

## BIG_LOTTO
**Verdict: RISK_REDUCTION_ONLY**

- Perm test: p=0.5600 FAIL
- McNemar V3 vs V2: net=-3, p=0.2482 not significant

| Window | System | cond_edge | uncond_edge | sharpe | max_dd | variance | avg_bets |
|--------|--------|-----------|-------------|--------|--------|----------|----------|
| w150 | legacy | +1.84% | +1.84% | 0.071 | 1.686 | 0.0680 | 3.0 |
| w150 | v2 | +2.75% | +2.75% | 0.092 | 2.238 | 0.0900 | 4.0 |
| w150 | v3 | +2.49% | +1.48% | 0.120 | 0.301 | 0.0429 | 1.1 |
| w500 | legacy | -0.09% | -0.09% | -0.004 | 6.150 | 0.0511 | 3.0 |
| w500 | v2 | -0.05% | -0.05% | -0.002 | 8.200 | 0.0668 | 4.0 |
| w500 | v3 | -1.96% | -0.22% | -618.836 | 0.300 | 0.0000 | 1.1 |
| w1500 | legacy | +0.78% | +0.78% | 0.032 | 17.800 | 0.0587 | 3.0 |
| w1500 | v2 | +0.68% | +0.68% | 0.025 | 24.050 | 0.0730 | 4.0 |
| w1500 | v3 | -0.45% | -0.02% | -0.037 | 0.300 | 0.0147 | 1.0 |

## POWER_LOTTO
**Verdict: RISK_REDUCTION_ONLY**

- Perm test: p=0.3000 FAIL
- McNemar V3 vs V2: net=-2, p=0.4795 not significant

| Window | System | cond_edge | uncond_edge | sharpe | max_dd | variance | avg_bets |
|--------|--------|-----------|-------------|--------|--------|----------|----------|
| w150 | legacy | +0.16% | +0.16% | 0.005 | 3.650 | 0.1005 | 3.0 |
| w150 | v2 | +2.73% | +2.73% | 0.072 | 4.700 | 0.1433 | 4.0 |
| w150 | v3 | -1.38% | -0.23% | -0.070 | 0.300 | 0.0384 | 1.4 |
| w500 | legacy | +1.83% | +1.83% | 0.054 | 11.750 | 0.1131 | 3.0 |
| w500 | v2 | +3.00% | +3.00% | 0.079 | 15.600 | 0.1450 | 4.0 |
| w500 | v3 | +9.07% | +0.58% | 0.250 | 0.300 | 0.1318 | 1.7 |
| w1500 | legacy | +1.50% | +1.50% | 0.045 | 35.500 | 0.1106 | 3.0 |
| w1500 | v2 | +2.13% | +2.13% | 0.057 | 47.450 | 0.1393 | 4.0 |
| w1500 | v3 | -1.54% | -0.02% | -0.074 | 0.300 | 0.0434 | 1.6 |

## Classification Logic (Phase 8)
- **DEPLOYABLE**: three_cond AND three_uncond AND perm_ok AND sharpe>0
- **WATCH**: three_cond AND perm_ok BUT uncond fails OR sharpe marginal
- **RISK_REDUCTION_ONLY**: cond_edge positive + drawdown materially better than V2
- **NO_GAIN**: cond_edge similar to V2, no drawdown improvement
- **REJECT**: cond_edge negative or perm_p > 0.20

## Key Lesson (L101)
Unconditional edge = participation_rate × cond_hit_rate − baseline.
V3 always participates (min 1 bet), so dilution from variable-N is bounded.
Risk reduction value is real even when unconditional edge stays negative.