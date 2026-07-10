# P543B — Scoreboard Validation Feasibility / Minimal Pilot

> 本文件只評估已提交 artifacts 的驗證可行性；不預測未來，也不構成投注建議。
> P543B 僅為 feasibility / pilot；不表示任何候選可正式使用、可上線或已具備正式環境準備。
> 若有 pilot，數值只描述固定輸入與固定 seed 的小型重排比較，不代表未來表現。

## Sources

| artifact | SHA256 | bytes | purpose |
|---|---|---:|---|
| `outputs/research/p543a_scoreboard_stability_packet_20260710.json` | `190fc9f9a8f2d4817a955204b5af1f5d9cf1fb186fa0695713202235f306e0e5` | 987573 | P543A candidate classes and aggregate evidence. |
| `outputs/research/p542a_strategy_pick_combination_scoreboard_20260710.json` | `c23a993c570de2f09c757f8ddbcf0e04b444d3312cd370c915222844ee927d5b` | 1999750 | P542A aggregate metric schema and per-draw availability. |

## Inspected Artifact Inventory

| artifact | usable fields | finding |
|---|---|---|
| `outputs/research/p543a_scoreboard_stability_packet_20260710.json` | candidate_packet, candidate_id, observed_windows, evidence | Provides candidate classes, but not per-draw selected numbers or actual outcomes. |
| `outputs/research/p542a_strategy_pick_combination_scoreboard_20260710.json` | strategy_pick_matrix, combination_leaderboard, power_lotto_zone2_metrics, window_policy | The committed source has aggregate rows but no per_draw_validation_rows section. |

## Feasibility Matrix

| candidate class | source rows | walk-forward possible | permutation possible | aggregate only | missing predictions | missing actual outcomes | unsupported |
|---|---:|---:|---:|---:|---:|---:|---:|
| multi_window_stable | 145 | 0 | 0 | 145 | 145 | 145 | 0 |
| single_window_spike | 222 | 0 | 0 | 222 | 222 | 222 | 0 |
| prize_or_zone2_signal | 35 | 0 | 0 | 35 | 35 | 35 | 0 |
| unknown_or_incomplete | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| not_comparable | 6 | 0 | 0 | 0 | 0 | 0 | 6 |

## Pilot

Computed: NO — No high-stability candidate has complete committed per-draw predictions and actual outcomes.
Required gap: chronological draw ID, candidate ID, selected numbers, and actual drawn numbers in one committed per-draw artifact.

## Recommended Next Task

Create and audit a committed per-draw validation-input contract containing chronological draw IDs, candidate IDs, selected numbers, and actual outcomes. Only after that contract is available should a separate validation task implement walk-forward or permutation analysis.
