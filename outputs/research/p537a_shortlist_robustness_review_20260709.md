# P537A — Shortlist Robustness Review (Owner/CTO Review Artifact)

> Historical replay review artifact only; not a prediction, betting edge, future-winning, or production-readiness claim.

Derived from: **P536K** (`outputs/research/p536k_lift_candidate_shortlist_20260708.json`), which extends **P536C** (`outputs/research/p536c_success_matrix_lift_extension_20260708.json`).

- hash_chain_verified: **True**
- source_data_hash_sha256 (P536K): `46d49ea1fc20e240205ab6fa87b70800e6dbfabfee927fc06e532b4b61b4c8d2`
- upstream_data_hash_sha256 (P536C): `46d49ea1fc20e240205ab6fa87b70800e6dbfabfee927fc06e532b4b61b4c8d2`

## Counts

- stable_candidates_for_owner_review: **177**
- short_window_spike_caution_list: **90**
- combination_candidates_for_followup: **102**
- cross_lottery_candidates_for_followup: **60**
- insufficient_or_ambiguous_candidates: **31**

## Stable Candidates For Owner Review (window ∈ {300, 750}, positive lift)

| lottery | strategy | family | pick_k | window | support | observed | baseline | lift | log10(lift) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| BIG_LOTTO | `bet2_fourier_expansion_biglotto` | fourier | 1 | 300 | 300 | 13.33% | 12.24% | 1.089x | 0.03698356625316853 |
| BIG_LOTTO | `bet2_fourier_expansion_biglotto` | fourier | 5 | 300 | 300 | 50.67% | 49.52% | 1.023x | 0.009943057097568401 |
| BIG_LOTTO | `bet2_fourier_expansion_biglotto` | fourier | 6 | 300 | 300 | 57.00% | 56.40% | 1.011x | 0.00456878277120338 |
| BIG_LOTTO | `bet2_fourier_expansion_biglotto` | fourier | 1 | 750 | 750 | 12.93% | 12.24% | 1.056x | 0.02375530051941299 |
| BIG_LOTTO | `biglotto_deviation_2bet` | deviation | 1 | 300 | 300 | 13.00% | 12.24% | 1.062x | 0.025988181951705384 |
| BIG_LOTTO | `biglotto_deviation_2bet` | deviation | 2 | 300 | 300 | 24.67% | 23.21% | 1.063x | 0.026355139710679144 |
| BIG_LOTTO | `biglotto_deviation_2bet` | deviation | 3 | 300 | 300 | 34.33% | 33.02% | 1.040x | 0.016982078478762534 |
| BIG_LOTTO | `biglotto_deviation_2bet` | deviation | 4 | 300 | 300 | 46.00% | 41.75% | 1.102x | 0.042063205949135755 |
| BIG_LOTTO | `biglotto_deviation_2bet` | deviation | 5 | 300 | 300 | 53.67% | 49.52% | 1.084x | 0.03492534518464551 |
| BIG_LOTTO | `biglotto_deviation_2bet` | deviation | 6 | 300 | 300 | 60.33% | 56.40% | 1.070x | 0.02925124724823421 |
| BIG_LOTTO | `biglotto_deviation_2bet` | deviation | 1 | 750 | 750 | 12.93% | 12.24% | 1.056x | 0.02375530051941299 |
| BIG_LOTTO | `biglotto_deviation_2bet` | deviation | 2 | 750 | 750 | 25.07% | 23.21% | 1.080x | 0.033341260571339605 |
| BIG_LOTTO | `biglotto_deviation_2bet` | deviation | 3 | 750 | 750 | 33.33% | 33.02% | 1.010x | 0.0041448537735910085 |
| BIG_LOTTO | `biglotto_deviation_2bet` | deviation | 4 | 750 | 750 | 45.07% | 41.75% | 1.079x | 0.03316081115351812 |
| BIG_LOTTO | `biglotto_deviation_2bet` | deviation | 5 | 750 | 750 | 52.40% | 49.52% | 1.058x | 0.024552010856187557 |
| BIG_LOTTO | `biglotto_deviation_2bet` | deviation | 6 | 750 | 750 | 58.67% | 56.40% | 1.040x | 0.017085340193199725 |
| BIG_LOTTO | `biglotto_echo_aware_3bet` | echo | 2 | 300 | 300 | 24.33% | 23.21% | 1.048x | 0.020446280100158826 |
| BIG_LOTTO | `biglotto_echo_aware_3bet` | echo | 3 | 300 | 300 | 33.33% | 33.02% | 1.010x | 0.00414485377359034 |
| BIG_LOTTO | `biglotto_echo_aware_3bet` | echo | 4 | 300 | 300 | 43.00% | 41.75% | 1.030x | 0.012773829847148208 |
| BIG_LOTTO | `biglotto_echo_aware_3bet` | echo | 5 | 300 | 300 | 51.67% | 49.52% | 1.043x | 0.01843116732308738 |
| BIG_LOTTO | `biglotto_echo_aware_3bet` | echo | 6 | 300 | 300 | 57.00% | 56.40% | 1.011x | 0.00456878277120338 |
| BIG_LOTTO | `biglotto_echo_aware_3bet` | echo | 1 | 750 | 750 | 13.07% | 12.24% | 1.067x | 0.028209641945662944 |
| BIG_LOTTO | `biglotto_echo_aware_3bet` | echo | 2 | 750 | 750 | 23.87% | 23.21% | 1.028x | 0.012036442287552908 |
| BIG_LOTTO | `biglotto_echo_aware_3bet` | echo | 3 | 750 | 750 | 33.07% | 33.02% | 1.002x | 0.0006565259277696918 |
| BIG_LOTTO | `biglotto_echo_aware_3bet` | echo | 4 | 750 | 750 | 42.27% | 41.75% | 1.012x | 0.005303373093614874 |

_...and 152 more rows in the JSON artifact._

## Short-Window Spike Caution List (window=50, review-only)

| lottery | strategy | family | pick_k | support | observed | baseline | lift |
|---|---|---|---:|---:|---:|---:|---:|
| BIG_LOTTO | `bet2_fourier_expansion_biglotto` | fourier | 1 | 50 | 16.00% | 12.24% | 1.307x |
| BIG_LOTTO | `bet2_fourier_expansion_biglotto` | fourier | 2 | 50 | 28.00% | 23.21% | 1.206x |
| BIG_LOTTO | `bet2_fourier_expansion_biglotto` | fourier | 4 | 50 | 46.00% | 41.75% | 1.102x |
| BIG_LOTTO | `bet2_fourier_expansion_biglotto` | fourier | 5 | 50 | 58.00% | 49.52% | 1.171x |
| BIG_LOTTO | `bet2_fourier_expansion_biglotto` | fourier | 6 | 50 | 60.00% | 56.40% | 1.064x |
| BIG_LOTTO | `biglotto_deviation_2bet` | deviation | 2 | 50 | 26.00% | 23.21% | 1.120x |
| BIG_LOTTO | `biglotto_deviation_2bet` | deviation | 3 | 50 | 34.00% | 33.02% | 1.030x |
| BIG_LOTTO | `biglotto_deviation_2bet` | deviation | 4 | 50 | 46.00% | 41.75% | 1.102x |
| BIG_LOTTO | `biglotto_deviation_2bet` | deviation | 5 | 50 | 56.00% | 49.52% | 1.131x |
| BIG_LOTTO | `biglotto_deviation_2bet` | deviation | 6 | 50 | 64.00% | 56.40% | 1.135x |
| BIG_LOTTO | `biglotto_echo_aware_3bet` | echo | 2 | 50 | 28.00% | 23.21% | 1.206x |
| BIG_LOTTO | `biglotto_echo_aware_3bet` | echo | 3 | 50 | 38.00% | 33.02% | 1.151x |
| BIG_LOTTO | `biglotto_echo_aware_3bet` | echo | 4 | 50 | 46.00% | 41.75% | 1.102x |
| BIG_LOTTO | `biglotto_echo_aware_3bet` | echo | 5 | 50 | 52.00% | 49.52% | 1.050x |
| BIG_LOTTO | `biglotto_echo_aware_3bet` | echo | 6 | 50 | 60.00% | 56.40% | 1.064x |
| BIG_LOTTO | `biglotto_triple_strike` | other | 1 | 50 | 16.00% | 12.24% | 1.307x |
| BIG_LOTTO | `biglotto_triple_strike` | other | 2 | 50 | 28.00% | 23.21% | 1.206x |
| BIG_LOTTO | `biglotto_triple_strike` | other | 3 | 50 | 34.00% | 33.02% | 1.030x |
| BIG_LOTTO | `biglotto_triple_strike` | other | 4 | 50 | 48.00% | 41.75% | 1.150x |
| BIG_LOTTO | `biglotto_triple_strike` | other | 5 | 50 | 60.00% | 49.52% | 1.212x |
| BIG_LOTTO | `biglotto_triple_strike` | other | 6 | 50 | 62.00% | 56.40% | 1.099x |
| BIG_LOTTO | `biglotto_ts3_markov_4bet_w30` | markov | 1 | 50 | 16.00% | 12.24% | 1.307x |
| BIG_LOTTO | `biglotto_ts3_markov_4bet_w30` | markov | 2 | 50 | 30.00% | 23.21% | 1.292x |
| BIG_LOTTO | `biglotto_ts3_markov_4bet_w30` | markov | 3 | 50 | 34.00% | 33.02% | 1.030x |
| BIG_LOTTO | `biglotto_ts3_markov_4bet_w30` | markov | 4 | 50 | 48.00% | 41.75% | 1.150x |

_...and 65 more rows in the JSON artifact._

## Combination Candidates For Followup (present in ≥2 windows, prize-signal lift known)

| lottery | combo_id | budget | windows_present | avg_prize_signal_lift | stability_rank |
|---|---|---:|---|---:|---:|
| BIG_LOTTO | `biglotto_echo_aware_3bet:2 + biglotto_ts3_markov_4bet_w30:1` | 3 | [50, 300] | 0.000x | 1 |
| BIG_LOTTO | `bet2_fourier_expansion_biglotto:2 + biglotto_deviation_2bet:2` | 4 | [50, 300, 750] | 1.543x | 1 |
| BIG_LOTTO | `bet2_fourier_expansion_biglotto:2 + biglotto_deviation_2bet:2 + markov_single_biglotto:1` | 5 | [300, 750] | 0.921x | 1 |
| BIG_LOTTO | `biglotto_deviation_2bet:2 + markov_single_biglotto:2 + ts3_regime_3bet:2` | 6 | [50, 300, 750] | 0.725x | 1 |
| BIG_LOTTO | `bet2_fourier_expansion_biglotto:1 + biglotto_echo_aware_3bet:2` | 3 | [50, 300] | 0.000x | 2 |
| BIG_LOTTO | `biglotto_deviation_2bet:2 + ts3_regime_3bet:2` | 4 | [50, 300, 750] | 1.542x | 2 |
| BIG_LOTTO | `bet2_fourier_expansion_biglotto:2 + biglotto_deviation_2bet:2 + markov_2bet_biglotto:1` | 5 | [300, 750] | 0.921x | 2 |
| BIG_LOTTO | `biglotto_deviation_2bet:2 + markov_2bet_biglotto:2 + ts3_regime_3bet:2` | 6 | [50, 300, 750] | 0.725x | 2 |
| BIG_LOTTO | `biglotto_echo_aware_3bet:2 + ts3_regime_3bet:1` | 3 | [50, 300] | 0.000x | 3 |
| BIG_LOTTO | `biglotto_deviation_2bet:2 + biglotto_ts3_markov_4bet_w30:2` | 4 | [50, 300, 750] | 1.542x | 3 |
| BIG_LOTTO | `biglotto_deviation_2bet:2 + biglotto_echo_aware_3bet:2 + ts3_regime_3bet:2` | 6 | [50, 300] | 0.979x | 3 |
| BIG_LOTTO | `biglotto_echo_aware_3bet:2 + biglotto_triple_strike:1` | 3 | [50, 300] | 0.000x | 4 |
| BIG_LOTTO | `biglotto_deviation_2bet:2 + biglotto_triple_strike:2` | 4 | [50, 300, 750] | 1.542x | 4 |
| BIG_LOTTO | `biglotto_deviation_2bet:2 + biglotto_echo_aware_3bet:2 + biglotto_ts3_markov_4bet_w30:2` | 6 | [50, 300] | 0.979x | 4 |
| BIG_LOTTO | `bet2_fourier_expansion_biglotto:1 + biglotto_deviation_2bet:2` | 3 | [300, 750] | 0.000x | 5 |
| BIG_LOTTO | `biglotto_echo_aware_3bet:2 + biglotto_ts3_markov_4bet_w30:2` | 4 | [50, 300] | 0.270x | 5 |
| BIG_LOTTO | `biglotto_deviation_2bet:2 + biglotto_echo_aware_3bet:2 + biglotto_triple_strike:2` | 6 | [50, 300] | 0.979x | 5 |
| BIG_LOTTO | `biglotto_deviation_2bet:2 + ts3_regime_3bet:1` | 3 | [300, 750] | 0.000x | 6 |
| BIG_LOTTO | `biglotto_echo_aware_3bet:2 + ts3_regime_3bet:2` | 4 | [50, 300] | 0.268x | 6 |
| BIG_LOTTO | `bet2_fourier_expansion_biglotto:2 + biglotto_deviation_2bet:2 + biglotto_echo_aware_3bet:2` | 6 | [50, 300] | 0.979x | 6 |
| BIG_LOTTO | `biglotto_deviation_2bet:2 + biglotto_ts3_markov_4bet_w30:1` | 3 | [300, 750] | 0.000x | 7 |
| BIG_LOTTO | `biglotto_echo_aware_3bet:2 + biglotto_triple_strike:2` | 4 | [50, 300] | 0.268x | 7 |
| BIG_LOTTO | `biglotto_deviation_2bet:2 + biglotto_triple_strike:1` | 3 | [300, 750] | 0.000x | 8 |
| BIG_LOTTO | `bet2_fourier_expansion_biglotto:2 + biglotto_echo_aware_3bet:2` | 4 | [50, 300] | 0.268x | 8 |
| BIG_LOTTO | `bet2_fourier_expansion_biglotto:2 + coldpool15_biglotto:2` | 4 | [300, 750] | 0.000x | 9 |

_...and 77 more rows in the JSON artifact._

## Cross-Lottery Candidates For Followup (≥2 lotteries, side-by-side, never pooled)

| family | window | pick_k | lotteries present |
|---|---:|---:|---|
| cold | 50 | 1 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| cold | 50 | 2 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| cold | 50 | 3 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| cold | 50 | 4 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| cold | 50 | 5 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| cold | 300 | 1 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| cold | 300 | 2 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| cold | 300 | 3 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| cold | 300 | 4 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| cold | 300 | 5 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| cold | 750 | 1 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| cold | 750 | 2 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| cold | 750 | 3 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| cold | 750 | 4 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| cold | 750 | 5 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| fourier | 50 | 1 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| fourier | 50 | 2 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| fourier | 50 | 3 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| fourier | 50 | 4 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| fourier | 50 | 5 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| fourier | 300 | 1 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| fourier | 300 | 2 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| fourier | 300 | 3 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| fourier | 300 | 4 | BIG_LOTTO, DAILY_539, POWER_LOTTO |
| fourier | 300 | 5 | BIG_LOTTO, DAILY_539, POWER_LOTTO |

_...and 35 more rows in the JSON artifact._

## Insufficient Or Ambiguous Candidates (missing fields, not safely classifiable)

| lottery | combo_id | budget | windows_present | reason |
|---|---|---:|---|---|
| BIG_LOTTO | `ts3_regime_3bet:1` | 1 | [50, 300, 750] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| BIG_LOTTO | `biglotto_deviation_2bet:2` | 2 | [50, 300, 750] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| BIG_LOTTO | `biglotto_ts3_markov_4bet_w30:1` | 1 | [50, 300, 750] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| BIG_LOTTO | `biglotto_ts3_markov_4bet_w30:2` | 2 | [50, 300] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| BIG_LOTTO | `biglotto_triple_strike:1` | 1 | [50, 300, 750] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| BIG_LOTTO | `biglotto_echo_aware_3bet:2` | 2 | [50, 300] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| BIG_LOTTO | `bet2_fourier_expansion_biglotto:1` | 1 | [50, 300, 750] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| BIG_LOTTO | `bet2_fourier_expansion_biglotto:2` | 2 | [50, 300] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| BIG_LOTTO | `markov_single_biglotto:1` | 1 | [50, 300, 750] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| BIG_LOTTO | `bet2_fourier_expansion_biglotto:1 + biglotto_deviation_2bet:1` | 2 | [300, 750] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| BIG_LOTTO | `markov_2bet_biglotto:1` | 1 | [50, 300, 750] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| BIG_LOTTO | `bet2_fourier_expansion_biglotto:1 + coldpool15_biglotto:1` | 2 | [300, 750] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| BIG_LOTTO | `biglotto_deviation_2bet:1` | 1 | [50, 300, 750] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| BIG_LOTTO | `bet2_fourier_expansion_biglotto:1 + cold_complement_biglotto:1` | 2 | [300, 750] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| BIG_LOTTO | `biglotto_echo_aware_3bet:1` | 1 | [50, 300, 750] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| BIG_LOTTO | `coldpool15_biglotto:1` | 1 | [50, 300, 750] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| BIG_LOTTO | `fourier30_markov30_biglotto:1` | 1 | [50, 300] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| DAILY_539 | `p0c_539_3bet_f_cold_x2:1` | 1 | [50, 300, 750] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| DAILY_539 | `p0b_539_3bet_f_cold_fmid:1` | 1 | [50, 300, 750] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| DAILY_539 | `daily539_f4cold_5bet:1` | 1 | [50, 300, 750] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| DAILY_539 | `daily539_f4cold_3bet:1` | 1 | [50, 300, 750] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| DAILY_539 | `daily539_f4cold:1` | 1 | [50, 300, 750] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| DAILY_539 | `midfreq_fourier_2bet:1` | 1 | [50, 300, 750] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| DAILY_539 | `midfreq_acb_2bet:1` | 1 | [50, 300, 750] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |
| DAILY_539 | `acb_markov_midfreq:1` | 1 | [50, 300, 750] | avg_prize_signal_lift_across_present_windows is null in the source P536K row; the primary combination metric (prize_signal_and_any_main_hit_per_window) is not fully computable from existing fields, even though a secondary any_main_hit_lift value may still be present per-window. Not classified into combination_candidates_for_followup to avoid overstating robustness. |

_...and 6 more rows in the JSON artifact._

## Provenance & Limits

- derived_from_task_id: **P536K**
- upstream_task_id: **P536C**
- source_generated_at: `2026-07-08T13:12:26.151998+00:00`
- upstream_source_generated_at: `2026-07-08T07:42:01.782116+00:00`
- selection_method: Deterministic relabeling and re-bucketing over fields already present in the committed P536K shortlist artifact only. No database access, no route/API/UI change, no new statistical metric, and no recomputation from P536C or raw replay rows — every numeric value here is copied verbatim from the P536K source artifact. Combination rows are split into combination_candidates_for_followup / insufficient_or_ambiguous_candidates purely on whether avg_prize_signal_lift_across_present_windows is present.
- limitations:
  - Retrospective replay evidence only; does not imply future performance.
  - Short-window (50-draw) spike rows are especially prone to reversal; treat as review-only, not a stable pattern.
  - Combination rows are an enrichment over P333's existing top-10-per-bucket leaderboard, not an independent re-search of the full combination space.
  - Cross-lottery rows compare normalized lift only; raw hit rates are never pooled across games because each game has a different hypergeometric baseline.
  - No strategy promotion, ranking formula, or new metric is introduced by this shortlist; it is a read-only view over already-computed P536C fields.
  - This review only relabels and re-buckets rows already selected by P536K; it does not re-run P536K's own selection filters against P536C, so any future drift between the two committed artifacts is not detected by this module alone (see hash_chain_verified for the one provenance check this module does perform).
  - insufficient_or_ambiguous_candidates contains only combination rows where avg_prize_signal_lift_across_present_windows is null in the P536K source; other sections (stable/spike/cross-lottery) had no rows with missing required fields at generation time and so contribute nothing to this bucket.

> Historical replay review artifact only; not a prediction, betting edge, future-winning, or production-readiness claim.

