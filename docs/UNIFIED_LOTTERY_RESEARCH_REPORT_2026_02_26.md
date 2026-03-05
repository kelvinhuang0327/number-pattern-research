# Unified Lottery Quant Research Report (2026-02-26)

Scientific protocol: walk-forward OOS, 150/500/1500 stability windows, permutation baseline, Bonferroni correction.

## Taiwan Power Lotto (POWER_LOTTO)
- Draws: 1888 (2008-01-24 -> 2026/02/23)
- Iteration log: start tickets=2 methods=14; mutation add iter_hybrid_entropy_concentration_tail_extreme; stop no significant improvement; start tickets=3 methods=15; mutation add iter_hybrid_entropy_concentration_monte_carlo_baseline; stop no significant improvement

### Top strategies (2-ticket)
| Rank | Method | Valid | HitRate(1500) | Edge(1500) | p_bin | p_perm | z | Stability |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | entropy_concentration | N | 0.0893 | 0.0134 | 0.02991 | 0.05473 | 1.96 | 2.386 |
| 2 | tail_extreme | N | 0.0813 | 0.0054 | 0.226 | 0.1244 | 0.79 | 1.329 |
| 3 | fourier_spectral | N | 0.0800 | 0.0041 | 0.2875 | 0.3383 | 0.60 | 1.629 |
| 4 | markov_transition | N | 0.0773 | 0.0014 | 0.4307 | 0.5224 | 0.21 | 0.000 |
| 5 | cluster_regime | N | 0.0753 | -0.0006 | 0.5469 | 0.5522 | -0.08 | 0.000 |
| 6 | monte_carlo_baseline | N | 0.0747 | -0.0012 | 0.5854 | 0.6418 | -0.18 | 0.000 |
| 7 | feature_interaction | N | 0.0747 | -0.0012 | 0.5854 | 0.6219 | -0.18 | 0.000 |
| 8 | novel_hybrid_lotto | N | 0.0747 | -0.0012 | 0.5854 | 0.597 | -0.18 | 0.000 |
| 9 | iter_hybrid_entropy_concentration_tail_extreme | N | 0.0747 | -0.0012 | 0.5854 | 0.6318 | -0.18 | 0.000 |
| 10 | adaptive_ensemble | N | 0.0727 | -0.0032 | 0.6954 | 0.7264 | -0.47 | 0.000 |

Best 2-ticket method: `entropy_concentration`
- Latest tickets: [[10, 13, 23, 24, 28, 30], [1, 4, 19, 26, 27, 38]]
- Bonferroni alpha: 0.003333

### Top strategies (3-ticket)
| Rank | Method | Valid | HitRate(1500) | Edge(1500) | p_bin | p_perm | z | Stability |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | entropy_concentration | N | 0.1313 | 0.0197 | 0.009832 | 0.0398 | 2.42 | 1.003 |
| 2 | frequency_hotcold | N | 0.1200 | 0.0083 | 0.1623 | 0.2935 | 1.03 | 0.454 |
| 3 | tail_extreme | N | 0.1167 | 0.0050 | 0.2803 | 0.1244 | 0.62 | 0.917 |
| 4 | fourier_spectral | N | 0.1167 | 0.0050 | 0.2803 | 0.3333 | 0.62 | 1.533 |
| 5 | monte_carlo_baseline | N | 0.1240 | 0.0123 | 0.07149 | 0.06468 | 1.52 | 0.147 |
| 6 | feature_interaction | N | 0.1167 | 0.0050 | 0.2803 | 0.2935 | 0.62 | 0.000 |
| 7 | bayesian_posterior | N | 0.1140 | 0.0023 | 0.3987 | 0.592 | 0.29 | 0.000 |
| 8 | markov_transition | N | 0.1133 | 0.0017 | 0.4305 | 0.6119 | 0.21 | 0.000 |
| 9 | cluster_regime | N | 0.1113 | -0.0003 | 0.5281 | 0.6219 | -0.04 | 0.000 |
| 10 | adaptive_ensemble | N | 0.1080 | -0.0037 | 0.6854 | 0.8159 | -0.45 | 0.000 |

Best 3-ticket method: `entropy_concentration`
- Latest tickets: [[10, 13, 23, 24, 28, 30], [1, 4, 19, 26, 27, 38], [2, 3, 22, 29, 33, 36]]
- Bonferroni alpha: 0.003125

#### Three-window stability snapshot (best 2-ticket)
- window 150: hit_rate=0.0800, edge=0.0041, p_bin=0.4683, p_perm=0.4726
- window 500: hit_rate=0.0860, edge=0.0101, p_bin=0.2182, p_perm=0.2239
- window 1500: hit_rate=0.0893, edge=0.0134, p_bin=0.02991, p_perm=0.05473

## Taiwan Big Lotto (BIG_LOTTO)
- Draws: 2108 (2007-01-02 -> 2026/02/25)
- Iteration log: start tickets=2 methods=16; mutation add iter_hybrid_fourier_spectral_frequency_hotcold; stop no significant improvement; start tickets=3 methods=17; mutation add iter_hybrid_frequency_hotcold_cluster_regime; stop no significant improvement

### Top strategies (2-ticket)
| Rank | Method | Valid | HitRate(1500) | Edge(1500) | p_bin | p_perm | z | Stability |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | monte_carlo_baseline | N | 0.0400 | 0.0031 | 0.282 | 0.3383 | 0.63 | 3.966 |
| 2 | frequency_hotcold | N | 0.0407 | 0.0037 | 0.2388 | 0.2388 | 0.77 | 1.452 |
| 3 | gap_interval | N | 0.0373 | 0.0004 | 0.4856 | 0.3731 | 0.08 | 1.122 |
| 4 | fourier_spectral | N | 0.0447 | 0.0077 | 0.0673 | 0.1244 | 1.59 | 0.000 |
| 5 | tail_extreme | N | 0.0407 | 0.0037 | 0.2388 | 0.199 | 0.77 | 0.000 |
| 6 | cluster_regime | N | 0.0367 | -0.0003 | 0.5403 | 0.5672 | -0.05 | 0.241 |
| 7 | bayesian_posterior | N | 0.0360 | -0.0009 | 0.5945 | 0.6567 | -0.19 | 0.000 |
| 8 | markov_transition | N | 0.0347 | -0.0023 | 0.6976 | 0.7164 | -0.46 | 0.834 |
| 9 | adaptive_ensemble | N | 0.0340 | -0.0029 | 0.7447 | 0.7363 | -0.60 | 0.296 |
| 10 | time_series_pattern | N | 0.0333 | -0.0036 | 0.788 | 0.5423 | -0.74 | 0.000 |

Best 2-ticket method: `monte_carlo_baseline`
- Latest tickets: [[10, 26, 28, 33, 34, 47], [2, 6, 15, 37, 39, 45]]
- Bonferroni alpha: 0.002941

### Top strategies (3-ticket)
| Rank | Method | Valid | HitRate(1500) | Edge(1500) | p_bin | p_perm | z | Stability |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | cluster_regime | N | 0.0580 | 0.0031 | 0.313 | 0.3781 | 0.53 | 2.074 |
| 2 | frequency_hotcold | N | 0.0580 | 0.0031 | 0.313 | 0.3632 | 0.53 | 0.801 |
| 3 | entropy_concentration | N | 0.0560 | 0.0011 | 0.4401 | 0.4876 | 0.19 | 1.146 |
| 4 | gap_interval | N | 0.0553 | 0.0005 | 0.4849 | 0.199 | 0.08 | 0.858 |
| 5 | monte_carlo_baseline | N | 0.0573 | 0.0025 | 0.3536 | 0.3632 | 0.42 | 0.000 |
| 6 | fourier_spectral | N | 0.0567 | 0.0018 | 0.3961 | 0.4129 | 0.30 | 0.000 |
| 7 | adaptive_ensemble | N | 0.0540 | -0.0009 | 0.5752 | 0.6617 | -0.15 | 0.558 |
| 8 | bayesian_posterior | N | 0.0533 | -0.0015 | 0.6194 | 0.6866 | -0.26 | 0.000 |
| 9 | tail_extreme | N | 0.0527 | -0.0022 | 0.6623 | 0.6318 | -0.38 | 0.000 |
| 10 | feature_interaction | N | 0.0493 | -0.0055 | 0.8413 | 0.8408 | -0.94 | 0.000 |

Best 3-ticket method: `cluster_regime`
- Latest tickets: [[13, 18, 27, 29, 31, 41], [21, 30, 33, 35, 39, 40], [8, 12, 19, 22, 25, 38]]
- Bonferroni alpha: 0.002778

#### Three-window stability snapshot (best 2-ticket)
- window 150: hit_rate=0.0400, edge=0.0031, p_bin=0.4795, p_perm=0.4876
- window 500: hit_rate=0.0420, edge=0.0051, p_bin=0.3047, p_perm=0.3184
- window 1500: hit_rate=0.0400, edge=0.0031, p_bin=0.282, p_perm=0.3383

## Taiwan 539 (DAILY_539)
- Draws: 5793 (2007-01-01 -> 2026/02/24)
- Iteration log: start tickets=2 methods=18; mutation add iter_hybrid_cluster_regime_bayesian_posterior; stop no significant improvement; start tickets=3 methods=19; mutation add iter_hybrid_entropy_concentration_cluster_regime; stop no significant improvement

### Top strategies (2-ticket)
| Rank | Method | Valid | HitRate(1500) | Edge(1500) | p_bin | p_perm | z | Stability |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | monte_carlo_baseline | N | 0.2333 | 0.0184 | 0.04548 | 0.1542 | 1.73 | 2.159 |
| 2 | bayesian_posterior | N | 0.2387 | 0.0237 | 0.01455 | 0.0597 | 2.24 | 2.984 |
| 3 | entropy_concentration | N | 0.2367 | 0.0217 | 0.02286 | 0.1244 | 2.05 | 3.440 |
| 4 | cluster_regime | N | 0.2407 | 0.0257 | 0.008992 | 0.02985 | 2.42 | 2.751 |
| 5 | frequency_hotcold | N | 0.2193 | 0.0044 | 0.3497 | 0.5622 | 0.41 | 1.671 |
| 6 | novel_hybrid_lotto | N | 0.2193 | 0.0044 | 0.3497 | 0.4726 | 0.41 | 0.515 |
| 7 | iter_hybrid_entropy_concentration_tail_extreme | N | 0.2193 | 0.0044 | 0.3497 | 0.4428 | 0.41 | 0.515 |
| 8 | iter_hybrid_entropy_concentration_monte_carlo_baseline | N | 0.2193 | 0.0044 | 0.3497 | 0.4726 | 0.41 | 0.515 |
| 9 | iter_hybrid_fourier_spectral_frequency_hotcold | N | 0.2193 | 0.0044 | 0.3497 | 0.4876 | 0.41 | 0.515 |
| 10 | iter_hybrid_frequency_hotcold_cluster_regime | N | 0.2193 | 0.0044 | 0.3497 | 0.5274 | 0.41 | 0.515 |

Best 2-ticket method: `monte_carlo_baseline`
- Latest tickets: [[5, 7, 9, 14, 17], [6, 10, 11, 15, 21]]
- Bonferroni alpha: 0.002632

### Top strategies (3-ticket)
| Rank | Method | Valid | HitRate(1500) | Edge(1500) | p_bin | p_perm | z | Stability |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | entropy_concentration | N | 0.3413 | 0.0369 | 0.001148 | 0.0398 | 3.11 | 10.096 |
| 2 | adaptive_ensemble | N | 0.3293 | 0.0249 | 0.01987 | 0.3682 | 2.10 | 6.475 |
| 3 | cluster_regime | N | 0.3373 | 0.0329 | 0.003275 | 0.02488 | 2.77 | 2.385 |
| 4 | bayesian_posterior | N | 0.3373 | 0.0329 | 0.003275 | 0.1443 | 2.77 | 1.863 |
| 5 | monte_carlo_baseline | N | 0.3260 | 0.0216 | 0.03757 | 0.3632 | 1.82 | 1.064 |
| 6 | frequency_hotcold | N | 0.3220 | 0.0176 | 0.07398 | 0.5124 | 1.48 | 1.535 |
| 7 | novel_hybrid_lotto | N | 0.3113 | 0.0069 | 0.2893 | 0.6517 | 0.58 | 2.121 |
| 8 | iter_hybrid_entropy_concentration_tail_extreme | N | 0.3113 | 0.0069 | 0.2893 | 0.6866 | 0.58 | 2.121 |
| 9 | iter_hybrid_entropy_concentration_monte_carlo_baseline | N | 0.3113 | 0.0069 | 0.2893 | 0.6418 | 0.58 | 2.121 |
| 10 | iter_hybrid_fourier_spectral_frequency_hotcold | N | 0.3113 | 0.0069 | 0.2893 | 0.7065 | 0.58 | 2.121 |

Best 3-ticket method: `entropy_concentration`
- Latest tickets: [[7, 9, 20, 26, 39], [4, 14, 17, 19, 21], [2, 13, 33, 35, 37]]
- Bonferroni alpha: 0.002500

#### Three-window stability snapshot (best 2-ticket)
- window 150: hit_rate=0.2867, edge=0.0717, p_bin=0.02341, p_perm=0.03483
- window 500: hit_rate=0.2680, edge=0.0530, p_bin=0.002818, p_perm=0.0199
- window 1500: hit_rate=0.2333, edge=0.0184, p_bin=0.04548, p_perm=0.1542

## Risk and limitations
- Lottery draws are near-random; observed positive edge is generally small and unstable.
- Multiple testing control (Bonferroni) is strict; most methods are expected to fail significance.
- Ticket-independence baseline may slightly overstate random benchmark when tickets overlap.

## Final scientific verdict
- No robust, persistent high edge is expected under strict OOS + permutation + Bonferroni criteria.
- Recommended practical use: only methods marked `Valid=Y`; otherwise treat as entertainment, not investment.
