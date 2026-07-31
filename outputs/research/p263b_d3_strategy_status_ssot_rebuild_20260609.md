# P263B — D3 Strategy Status / Contract Audit SSOT Rebuild

_Read-only API/UI rebuild. No DB write, no replay backfill, no registry/adapter change, no migration._

## Approach — versioned coexistence (per STOP #6)

The existing `GET /api/replay/d3-strategy-status-audit` (P258N) is **contract-locked** by
P258N/P258O/P258P tests outside the P263B editable whitelist: `no_db_query=true`, a fixed
14-field artifact schema, a source token-scan forbidding `sqlite3`/`DatabaseManager`/`database`
after `_load_d3_strategy_status_audit_payload`, and a fixed UI fetch target. Rebuilding it in
place is impossible without breaking that contract. Per STOP condition #6, the existing
contract is **preserved verbatim** and the SSOT rebuild is delivered additively:

- **New endpoint:** `GET /api/replay/d3-strategy-status-coverage` (SSOT: registry ∪ replay store ∪ `rejected/*.json`)
- **New UI section:** `index.html #p263b-d3-ssot-section` (nav `data-section="p263b-d3-ssot"`, label "D3 策略狀態 (SSOT)")
- **Old endpoint + P258O section + P258N artifact:** untouched; their contract tests stay green.

## Coverage before → after

| | Source | Cells | Strategies | Phantom rows |
|---|---|---|---|---|
| Before (P258N) | hand-authored artifact | 8 / 41 | — | 6 |
| After (P263B) | SSOT registry∪DB∪rejected | **41 / 41** | **40** | **0** |

Coverage summary (after): registered 38, unregistered_orphan 2, registry_lottery_mismatch 1,
with_replay_rows 36, without_replay_rows 5, can_open_detail 36.

- **orphans-with-rows (can_open_detail=true):** `midfreq_fourier_mk_3bet`, `pp3_freqort_4bet`
- **registered-without-rows (can_open_detail=false, success rates N/A):** `biglotto_ts3_acb_4bet`, `biglotto_ts3_markov_freq_5bet`, `p1_deviation_2bet_539`, `h6_gate_mk20_ew85`, `power_shlc_midfreq`
- **registry/lottery mismatch:** `POWER_LOTTO:midfreq_fourier_2bet`

## P263A bugs fixed

1. **Lifecycle contradiction** → lifecycle now sourced from the registry for every registered cell (verified equal to the registry on all registered rows; orphans → `UNREGISTERED`).
2. **`replay_row_count` transposition** → per-cell count straight from the replay store. Lottery totals are now correct/un-swapped: DAILY_539 = 34,680 · POWER_LOTTO = 36,104 · BIG_LOTTO = 24,140.

## Success-rate contract (read-only display metric — NOT a promotion gate)

- **Windows:** most recent 30 / 100 / 500 / 1500 distinct `target_draw` per cell, by `CAST(target_draw AS INTEGER) DESC`.
- **Scope:** `strategy_id` + `lottery_type`.
- **draw_success:** a draw counts when ANY `bet_index` for that draw has `hit_count >= 1` OR `special_hit = 1` (no per-lottery threshold weighting — an interpretable "hit ≥ 1 number" rate).
- **success_rate_N** = successes / `available_draws_N`; `available_draws_N = 0` → `null` (rendered N/A); `available_draws_N < N` → still computed, shown as partial (e.g. `73.3% (78/100)`).

Sample (ONLINE): `ts3_regime_3bet` 30/100/500/1500 = 73.3% / 56.0% / 54.6% / 55.9%;
`fourier_rhythm_3bet` = 90.0% / 95.0% / 95.4% / 96.3%.

## New row fields

`registry_status`, `distinct_draw_count`, `max_bet_index`, `available_bet_indices`,
`can_open_detail`, `missing_reason`, `status_reason`, `status_updated_at`, `status_source`,
`reject_reason`, `reject_updated_at`, `reject_source_artifact`,
`success_rate_{30,100,500,1500}`, `available_draws_{30,100,500,1500}`.

- **reject provenance** ← `rejected/{strategy_id}.json` (`failure_reason` / `rejected_date` / path). Missing file → `null`; malformed file (e.g. `p1_deviation_2bet_539.json`) → `unknown` (never fabricated).
- **status provenance** ← `status_source` = `replay_strategy_registry` (registered/mismatch) or `replay_store_rows` (orphan); `status_updated_at` = `null` (the registry carries no per-status timestamp).

## Safety

`d3_contract_status` = `NOT_EVALUATED_BY_D3` for every row. Disclaimers preserved (not a
prediction model, contract validation ≠ strategy evaluation, NOT_YET_REJECTED ≠ approval,
no improved-accuracy claim, success rate is read-only history not betting advice).

## Validation

- P263B tests **29/29 PASS**; regression (p263b/p263a/p262b/p262a/p261a) **135 PASS**.
- CI-gated `test_replay_api_contract.py` **44 PASS**; P258N/O/P contract tests **162 PASS** (pre-commit).
- JS syntax OK; `git diff --check` clean; replay rows unchanged at 94,924 (no DB write).
- Browser check **NOT RUN** locally (no playwright; running backend is stale pre-P263B and not disturbed) — covered by CI `replay-browser-e2e-validation`.

**Final classification:** `P263B_D3_STRATEGY_STATUS_SSOT_REBUILD_IMPLEMENTED_VERSIONED_COEXISTENCE`
