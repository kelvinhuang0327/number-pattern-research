# P262B — Replay Overview Coverage Remediation — Show All Known Strategies Without Backfill

- Generated: `2026-06-09`
- Based on: P262A audit, main `931ea93abd75acb5bedb91e6524409c0c8116cd9`
- Type: implementation (read-only overview endpoint + UI) + 29 targeted tests + this artifact
- **READ-ONLY** — no DB write, no replay backfill, no migration, no strategy adapter change, no strategy registry change

## Problem (from P262A audit)

`GET /api/replay/history-overview` (P259A) walked **only the strategy registry** and
defaulted to `bet_index=1`, so it could not show every known strategy:

| Root gap | Effect |
|---|---|
| Registry-only walk | DB **orphan** strategies (replay rows but unregistered) never appeared |
| Registry/lottery mismatch | Rows under a `lottery_type` not in the registry's `supported_lottery_types` never appeared |
| Default `bet_index=1` | All multi-bet strategies hidden — only **13** of 38 reachable strategies visible by default |

## Solution — opt-in `coverage_mode` (backward compatible)

A new `coverage_mode: bool = false` query param. The legacy P259A behaviour is
**byte-for-byte preserved** when the param is absent/false (default `bet_index=1`,
registry-only walk). When `coverage_mode=true`:

- The cell universe becomes `UNION(registry-supported cells, DB cells)` — so orphan
  and registry/lottery-mismatch cells are surfaced.
- Every row is annotated with coverage metadata.
- The frontend overview now defaults to `coverage_mode=true&bet_index=0`, so multi-bet
  strategies are visible by default; the bet tabs still narrow the view, and the
  explicit `bet_index` filter still works.

### New per-row fields (additive, present in both modes)

`has_replay_rows`, `distinct_draw_count`, `max_bet_index`, `available_bet_indices`,
`registry_status`, `can_open_detail`, `missing_reason`, `coverage_warning`.

- `registry_status` ∈ `registered` | `unregistered_orphan` | `registry_lottery_mismatch`
- `missing_reason` ∈ `registered_without_rows` | `artifact_only` | `observation_no_data` | `no_production_replay` | `null`
- `can_open_detail == has_replay_rows` — the P259B/P261A detail endpoints scope purely
  by `lottery_type` + `strategy_id` and return rows whenever they exist (orphans included).

## Coverage — before vs after

| Metric | Before (default) | After (`coverage_mode=true&bet_index=0`) |
|---|---:|---:|
| Distinct strategies visible | 13 | **40** |
| Total cells | 13 | **41** |
| Registered cells | 13 | 38 |
| Unregistered orphan cells | 0 | **2** |
| Registry/lottery mismatch cells | 0 | **1** |
| Cells with replay rows | — | 36 |
| Cells without replay rows | — | 5 |
| Multi-bet strategies visible | ❌ | ✅ |

### Known surfaced cells

- **Orphans (unregistered, have rows, can open detail):** `midfreq_fourier_mk_3bet`, `pp3_freqort_4bet`
- **Registry/lottery mismatch:** `POWER_LOTTO:midfreq_fourier_2bet`
- **Registered without rows (`can_open_detail=false`, reason shown):**
  - `biglotto_ts3_acb_4bet` → `artifact_only`
  - `biglotto_ts3_markov_freq_5bet` → `artifact_only`
  - `h6_gate_mk20_ew85` → `observation_no_data`
  - `p1_deviation_2bet_539` → `artifact_only`
  - `power_shlc_midfreq` → `artifact_only`

## Files changed

- `lottery_api/routes/replay.py` — coverage helpers + `coverage_mode` param + enhanced DB
  aggregate query (`distinct_draw_count`, `max_bet_index`, `GROUP_CONCAT(DISTINCT bet_index)`,
  db `strategy_name`) + registry walk / coverage-universe expansion + `coverage_summary`.
- `index.html` — P259A overview gains 4 coverage columns (註冊狀態 / 不重複期數 / 可用注 index /
  缺漏原因), registry-status + reason badges, coverage summary counts; JS fetches
  `coverage_mode=true` and defaults to `bet_index=0`. **P261A detail expand untouched.**
- `tests/test_p262b_replay_overview_coverage_remediation.py` — 29 read-only tests.

## Validation

- `pytest tests/test_p262b_...` → **29 passed**
- Regression: P262A 14 · P261A 50 · P260C 29 · P259C 33 · P259B 38 · P259A 46 — **all PASS** (239 total)
- `git diff --check` → clean
- **Read-only proof:** `strategy_prediction_replays` row count identical before/after coverage
  calls; registry size unchanged (38); no DB write / backfill / adapter / registry mutation.
- **Browser E2E:** NOT RUN locally (the running backend is stale pre-P262B and was not
  disturbed). Covered by CI `replay-browser-e2e-validation`; equivalent behaviours verified at
  the API (TestClient against this branch) and DOM-construction level.

## Remaining gaps (out of scope — no backfill / no registry change here)

The audit's underlying data issues are **surfaced, not fixed** (by design):
the 2 orphans remain unregistered, the mismatch cell remains a registry inconsistency,
and the 5 registered-without-rows strategies still have no production replay rows.
Resolving those would require registry edits or replay generation — both explicitly
forbidden for this task.
