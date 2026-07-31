# P250A — Cross-Lottery Strategy Replay Inventory

**Date:** 2026-06-07 11:11:47  
**Task:** `P250A`  
**Classification:** `CROSS_LOTTERY_STRATEGY_REPLAY_INVENTORY`  

## Executive Summary

This inventory reconciles the current registry with the historical P232A replay scoreboard so that every developed strategy appears in replay/catalog views regardless of lifecycle status. Lifecycle is shown as a label or badge, not as an exclusion filter.

- Current registry entries: `38`
- Historical inventory entries: `41`
- Artifact-only entries: `3`
- Replay rows total: `94924`
- Draw rows total: `64361`
- Canonical BIG_LOTTO rows: `2113`

## Phase 0

- Repo: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`
- Branch: `p252b-unified-external-method-coverage-audit`
- HEAD short: `9131353`
- `origin/main` short: `9131353`
- P249B merge visible: `False`
- Active task: `WAITING_FOR_USER_AUTHORIZATION`
- Canonical DB: `lottery_api/data/lottery_v2.db`

### Tolerated Dirty Items

- `backend.pid`
- `frontend.pid`
- `claude-code-showcase`
- `claude-code-showcase.worktrees/`
- `runtime/`
- `data/lottery_v2.db metadata-only same-size touch`

## DB Read Status

- Integrity check: `ok`
- `strategy_prediction_replays` rows: `94924`
- `draws` rows: `64361`
- `draws_big_lotto_canonical_main` rows: `2113`

### Tables Found

- `table` `agent_locks`
- `table` `agent_task_runs`
- `table` `agent_tasks`
- `table` `draws`
- `table` `prediction_explanations`
- `table` `prediction_items`
- `table` `prediction_results`
- `table` `prediction_review_status`
- `table` `prediction_runs`
- `table` `review_actions`
- `table` `review_findings`
- `table` `review_hypotheses`
- `table` `review_sessions`
- `table` `shadow_experiments`
- `table` `snapshot_schedule`
- `table` `sqlite_sequence`
- `table` `strategy_prediction_replays`
- `table` `strategy_replay_runs`
- `view` `draws_big_lotto_canonical_main`

## Replay Coverage by Lottery

| Lottery | Developed entries | Replay entries | Replay rows | Draw rows | Distinct replay draws | Canonical rows |
|---|---:|---:|---:|---:|---:|---:|
| BIG_LOTTO | 13 | 11 | 24140 | 22238 | 1552 | 2113 |
- BIG_LOTTO: replay rows are strategy_prediction_replays rows, not draw rows
- BIG_LOTTO: raw BIG_LOTTO draw rows remain 22,238; canonical main-draw rows are 2,113
- BIG_LOTTO: 19,100 add-on/special-prize rows stay raw-accessible and are excluded from canonical 6/49 research
- BIG_LOTTO: P249B fixes the replay-row vs draw-row label ambiguity
| DAILY_539 | 16 | 15 | 34680 | 5879 | 1550 |  |
- DAILY_539: replay rows are strategy_prediction_replays rows, not draw rows
- DAILY_539: no canonical/raw split currently tracked beyond the draw table count
- DAILY_539: P230C closed the prior DAILY_539 survivor as rejected/historical artifact
| POWER_LOTTO | 12 | 10 | 36104 | 1916 | 1551 |  |
- POWER_LOTTO: replay rows are strategy_prediction_replays rows, not draw rows
- POWER_LOTTO: three P47 artifact-only strategies remain in the historical inventory
- POWER_LOTTO: current registry has no active deployable candidate

## Strategy Inventory

### BIG_LOTTO

| Strategy ID | Current lifecycle | Historical snapshot | Latest classification | Replay rows | Source |
|---|---|---|---|---:|---|
| bet2_fourier_expansion_biglotto | REJECTED | LIFECYCLE_UNRESOLVED | rejected | 1500 | MAIN_REGISTRY |
- note: historical snapshot=LIFECYCLE_UNRESOLVED; current registry=REJECTED
| biglotto_deviation_2bet | ONLINE | ONLINE | active | 1570 | MAIN_REGISTRY |
| biglotto_echo_aware_3bet | RETIRED | LIFECYCLE_UNRESOLVED | retired | 4500 | MAIN_REGISTRY |
- note: historical snapshot=LIFECYCLE_UNRESOLVED; current registry=RETIRED
| biglotto_triple_strike | ONLINE | ONLINE | active | 1570 | MAIN_REGISTRY |
| biglotto_ts3_acb_4bet | REJECTED | REJECTED | no-data | 0 | MAIN_REGISTRY |
| biglotto_ts3_markov_4bet_w30 | RETIRED | LIFECYCLE_UNRESOLVED | retired | 6000 | MAIN_REGISTRY |
- note: historical snapshot=LIFECYCLE_UNRESOLVED; current registry=RETIRED
| biglotto_ts3_markov_freq_5bet | REJECTED | REJECTED | no-data | 0 | MAIN_REGISTRY |
| cold_complement_biglotto | REJECTED | LIFECYCLE_UNRESOLVED | rejected | 1500 | MAIN_REGISTRY |
- note: historical snapshot=LIFECYCLE_UNRESOLVED; current registry=REJECTED
| coldpool15_biglotto | REJECTED | LIFECYCLE_UNRESOLVED | rejected | 1500 | MAIN_REGISTRY |
- note: historical snapshot=LIFECYCLE_UNRESOLVED; current registry=REJECTED
| fourier30_markov30_biglotto | REJECTED | LIFECYCLE_UNRESOLVED | rejected | 1500 | MAIN_REGISTRY |
- note: historical snapshot=LIFECYCLE_UNRESOLVED; current registry=REJECTED
| markov_2bet_biglotto | REJECTED | LIFECYCLE_UNRESOLVED | rejected | 1500 | MAIN_REGISTRY |
- note: historical snapshot=LIFECYCLE_UNRESOLVED; current registry=REJECTED
| markov_single_biglotto | REJECTED | LIFECYCLE_UNRESOLVED | rejected | 1500 | MAIN_REGISTRY |
- note: historical snapshot=LIFECYCLE_UNRESOLVED; current registry=REJECTED
| ts3_regime_3bet | ONLINE | ONLINE | active | 1500 | MAIN_REGISTRY |

### DAILY_539

| Strategy ID | Current lifecycle | Historical snapshot | Latest classification | Replay rows | Source |
|---|---|---|---|---:|---|
| 539_3bet_orthogonal | REJECTED | LIFECYCLE_UNRESOLVED | rejected | 1500 | MAIN_REGISTRY |
- note: historical snapshot=LIFECYCLE_UNRESOLVED; current registry=REJECTED
| acb_1bet | RETIRED | RETIRED | retired | 1500 | MAIN_REGISTRY |
| acb_markov_midfreq | RETIRED | RETIRED | retired | 1500 | MAIN_REGISTRY |
| acb_markov_midfreq_3bet | RETIRED | RETIRED | retired | 4500 | MAIN_REGISTRY |
| acb_single_539 | REJECTED | LIFECYCLE_UNRESOLVED | rejected | 1500 | MAIN_REGISTRY |
- note: historical snapshot=LIFECYCLE_UNRESOLVED; current registry=REJECTED
| daily539_f4cold | ONLINE | ONLINE | active | 1590 | MAIN_REGISTRY |
| daily539_f4cold_3bet | RETIRED | LIFECYCLE_UNRESOLVED | retired | 4500 | MAIN_REGISTRY |
- note: historical snapshot=LIFECYCLE_UNRESOLVED; current registry=RETIRED
| daily539_f4cold_5bet | RETIRED | LIFECYCLE_UNRESOLVED | retired | 7500 | MAIN_REGISTRY |
- note: historical snapshot=LIFECYCLE_UNRESOLVED; current registry=RETIRED
| daily539_markov_cold | ONLINE | ONLINE | active | 1590 | MAIN_REGISTRY |
| markov_1bet_539 | REJECTED | LIFECYCLE_UNRESOLVED | rejected | 1500 | MAIN_REGISTRY |
- note: historical snapshot=LIFECYCLE_UNRESOLVED; current registry=REJECTED
| midfreq_acb_2bet | RETIRED | RETIRED | retired | 1500 | MAIN_REGISTRY |
| midfreq_fourier_2bet | RETIRED | RETIRED | retired | 1500 | MAIN_REGISTRY |
| p0b_539_3bet_f_cold_fmid | REJECTED | LIFECYCLE_UNRESOLVED | rejected | 1500 | MAIN_REGISTRY |
- note: historical snapshot=LIFECYCLE_UNRESOLVED; current registry=REJECTED
| p0c_539_3bet_f_cold_x2 | REJECTED | LIFECYCLE_UNRESOLVED | rejected | 1500 | MAIN_REGISTRY |
- note: historical snapshot=LIFECYCLE_UNRESOLVED; current registry=REJECTED
| p1_deviation_2bet_539 | REJECTED | REJECTED | no-data | 0 | MAIN_REGISTRY |
| zone_gap_3bet_539 | REJECTED | LIFECYCLE_UNRESOLVED | rejected | 1500 | MAIN_REGISTRY |
- note: historical snapshot=LIFECYCLE_UNRESOLVED; current registry=REJECTED

### POWER_LOTTO

| Strategy ID | Current lifecycle | Historical snapshot | Latest classification | Replay rows | Source |
|---|---|---|---|---:|---|
| cold_complement_2bet | RETIRED | LIFECYCLE_UNRESOLVED | retired | 1500 | MAIN_REGISTRY |
- note: historical snapshot=LIFECYCLE_UNRESOLVED; current registry=RETIRED
| fourier30_markov30_2bet | RETIRED | LIFECYCLE_UNRESOLVED | retired | 1501 | MAIN_REGISTRY |
- note: historical snapshot=LIFECYCLE_UNRESOLVED; current registry=RETIRED
| fourier_rhythm_3bet | ONLINE | ONLINE | active | 4503 | MAIN_REGISTRY |
| h6_gate_mk20_ew85 | OBSERVATION | OBSERVATION | no-data | 0 | MAIN_REGISTRY |
| midfreq_fourier_2bet | ARTIFACT_ONLY | DRY_RUN | artifact-only | 1500 | P47_WAVE4 artifact-only |
- note: historical snapshot=DRY_RUN; current registry=ARTIFACT_ONLY
| midfreq_fourier_mk_3bet | ARTIFACT_ONLY | DRY_RUN | artifact-only | 4500 | P47_WAVE4 artifact-only |
- note: historical snapshot=DRY_RUN; current registry=ARTIFACT_ONLY
| power_fourier_rhythm_2bet | RETIRED | LIFECYCLE_UNRESOLVED | retired | 3000 | MAIN_REGISTRY |
- note: historical snapshot=LIFECYCLE_UNRESOLVED; current registry=RETIRED
| power_orthogonal_5bet | ONLINE | ONLINE | active | 7550 | MAIN_REGISTRY |
| power_precision_3bet | ONLINE | ONLINE | active | 4550 | MAIN_REGISTRY |
| power_shlc_midfreq | REJECTED | REJECTED | no-data | 0 | MAIN_REGISTRY |
| pp3_freqort_4bet | ARTIFACT_ONLY | DRY_RUN | artifact-only | 6000 | P47_WAVE4 artifact-only |
- note: historical snapshot=DRY_RUN; current registry=ARTIFACT_ONLY
| zonal_entropy_2bet | RETIRED | LIFECYCLE_UNRESOLVED | retired | 1500 | MAIN_REGISTRY |
- note: historical snapshot=LIFECYCLE_UNRESOLVED; current registry=RETIRED

### 3_STAR / 4_STAR

No registry entries and no replay rows are present in the current replay inventory. P227C and P214C remain the controlling historical references.

## Research State

- **big_lotto**: GREEN_CANONICAL_RANDOMNESS_NO_PREDICTION_EDGE — P246K canonical NIST audit is GREEN on 2,113 canonical rows; this is a data-quality result, not a strategy signal.
- **daily_539**: REJECTED_BY_BACKWARD_OOS — P230C closed the prior survivor; no active candidate remains.
- **power_lotto**: NULL_OR_BASELINE_LIKE — P231B first-zone backward-OOS dry-run was NULL; any new hypothesis would require fresh pre-registration.
- **star_3_4**: UNDERPOWERED_NO_SIGNAL_AND_STRAIGHT_PLAY_BLOCKED — P227C box-play was underpowered; P214C straight-play was NULL and positional order is lost in sorted storage.
- **inventory_note**: Current registry is the live SSOT; P232A historical scoreboard is retained as a replay snapshot and is reconciled here rather than used as the sole current-state source.

## Candidate Next Directions

### 1. Cross-lottery null/positive evidence dashboard

- Value: High — one place to compare active / rejected / retired / artifact-only rows, replay coverage, and historical classifications.
- Risk: Low — read-only reporting and view composition only.
- Urgency: Medium — the current inventory spans multiple lifecycle labels and benefits from a single honest view.
- Prerequisites: Read-only access to current registry + replay snapshot; no DB write.

### 2. Replay/catalog lifecycle badge and filter refresh

- Value: High — makes lifecycle visible without hiding historical replay rows.
- Risk: Low-medium — UI/API behavior change only if surfaced to users.
- Urgency: Medium — current state already contains active, rejected, retired, observation, and artifact-only entries.
- Prerequisites: Define the exact badge vocabulary and keep historical rows visible by default.

### 3. Canonical replay refresh and stale-label cleanup

- Value: Medium-high — rebuild the current scoreboard from the current registry so the historical snapshot is not mistaken for live state.
- Risk: Low — read-only unless a new artifact is written.
- Urgency: Medium — the 20260604 scoreboard is historically useful but stale relative to the current registry.
- Prerequisites: Use the current registry as SSOT; keep P232A as historical evidence only.

### 4. Raw history add-on labeling for user-facing views

- Value: Medium — clarifies the BIG_LOTTO raw/canonical split and similar label semantics.
- Risk: Medium — touches UI/API display behavior.
- Urgency: Low-medium — useful for truthfulness, but not required for current research governance.
- Prerequisites: Frontend/API authorization and explicit display contract.

### 5. Archived script reactivation / migration only when a script is revived

- Value: Low-medium — keeps dormant code aligned with canonical helpers when reactivated.
- Risk: Low — narrow code migration, but only worth doing when a script is truly in use again.
- Urgency: Low — no active deployable candidate depends on it today.
- Prerequisites: Explicit reactivation decision for the specific archived script.

### 6. Annotation table Type D only if a downstream consumer appears

- Value: Low-medium — would label row families without mutating strategy logic.
- Risk: Medium — requires a controlled DB write and backup discipline.
- Urgency: Low — the current inventory does not require it.
- Prerequisites: Explicit Type D authorization and a concrete consumer need.

## Compliance

- read_only: `True`
- no_db_write: `True`
- no_registry_mutation: `True`
- no_strategy_logic_change: `True`
- no_production_recommendation_change: `True`
- no_betting_advice: `True`

## Sources

- current_registry: `lottery_api/models/replay_strategy_registry.py`
- historical_scoreboard: `outputs/research/p232a_all_catalog_strategy_replay_scoreboard_20260604.json`
- current_state: `00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md`
- roadmap: `00-Plan/roadmap/roadmap.md`
- active_task: `00-Plan/roadmap/active_task.md`

Final Classification: `P250A_CROSS_LOTTERY_STRATEGY_REPLAY_INVENTORY_COMPLETE`