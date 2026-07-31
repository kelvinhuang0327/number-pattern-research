# P3 Retrospective Regeneration Dry-run Report
**Date**: 2026-05-13
**Branch**: `audit/p3-retrospective-regeneration-dryrun-20260513`
**Base**: `main` (`d438fb6`)
**Generated**: 2026-05-13T10:33:38.713363Z

---

## 1. 本輪目標

P3 Retrospective Regeneration Dry-run:
- 針對 P1 判定的 6 個 EXECUTABLE_NOW 策略，在不寫 production DB、不修改 registry、不做 lifecycle promotion 的前提下，
  產出 in-memory / file-based candidate rows。
- 驗證每筆預測只用 target draw 之前的 history（leakage guard）。
- 所有 candidate rows 標記 `truth_level=REGENERATED_RETROSPECTIVE`、`dry_run_only=true`。
- 評估後續 P6 controlled apply 是否可行。

---

## 2. PR Merge Chain State

> **P3_BASELINE_DEPENDS_ON_OPEN_PR_CHAIN**
> No `YES merge` received for any PR. All three remain OPEN.

| PR | Title | Branch | Status | CI |
|----|-------|--------|--------|----|
| #92 | P78 configurable API base | `frontend/p78-configurable-api-base-20260513` | OPEN | ALL PASS ✅ |
| #93 | P1 executable evidence | `audit/p1-replay-truth-executable-evidence-20260513` | OPEN | ALL PASS ✅ |
| #94 | P2 truth-level taxonomy v2 | `frontend/p2-truth-level-taxonomy-v2-20260513` | OPEN | PENDING ⏳ |

P3 execution is **not blocked** by open PRs: registry, adapters, and DB are all on main.

---

## 3. Baseline Hashes

| File | MD5 | Status |
|------|-----|--------|
| `lottery_api/data/lottery_v2.db` | `de0e27bb800bc7183773a0dc596d66b8` | ✅ UNCHANGED |
| `lottery_api/models/replay_strategy_registry.py` | `3ea71cfc20c882714f3824ad68202f6e` | ✅ UNCHANGED |

---

## 4. Historical Draw Source Audit

**Source**: `lottery_api/data/lottery_v2.db` table `draws`
**Connection**: `sqlite3` read-only URI (`?mode=ro`)

**Schema**: `id, draw, date, lottery_type, numbers(JSON), special, created_at, jackpot_amount, sell_amount, total_amount`

| Lottery Type | Row Count | Min Date | Max Date |
|-------------|-----------|----------|----------|
| POWER_LOTTO | 1,906 | 2008/01/24 | 2026/04/27 |
| BIG_LOTTO   | 2,132 | 2007/01/02 | 2026/05/05 |
| DAILY_539   | 5,849 | 2007/01/01 | 2026/04/29 |

**Required fields**: `numbers` (parsed to `List[int]`), `date` (YYYY/MM/DD), `draw` (draw number)
**Schema match**: ✅ all strategies require only `numbers` key from history dicts

---

## 5. Dry-run Method

- **Target window**: last 50 eligible draws per lottery type
- **Min history**: 100 draws per strategy (all 6 share min_history=100)
- **Interface**: `adapter.get_one_bet(history, lottery_type) → (List[int], Optional[int])`
- **History slice**: `draws[:i]` — all draws with index < target index, sorted chronologically

---

## 6. Leakage Guard Design

For each candidate row:
1. `history = draws[:i]` — Python list slice guarantees history < target by sort order
2. `assert (history[-1].date, history[-1].draw) < (target.date, target.draw)` — explicit check
3. `assert all(h.date, h.draw) < (target.date, target.draw) for h in history` — full scan
4. `assert len(history) >= min_history` — belt+suspenders (adapter also raises `InsufficientHistory`)
5. Final: `assert all(r.dry_run_only is True)` and `assert all(r.truth_level == REGENERATED_RETROSPECTIVE)`

**Total leakage assertions passed**: 300

---

## 7. Candidate Row Schema

```json
{
  "strategy_id":         "power_precision_3bet",
  "lottery_type":        "POWER_LOTTO",
  "draw_date":           "2026/04/01",
  "draw_id":             "113000070",
  "predicted_numbers":   [3, 12, 19, 24, 33, 38],
  "predicted_special":   null,
  "actual_numbers":      [5, 12, 17, 24, 31, 38],
  "actual_special":      5,
  "hit_count":           3,
  "special_hit":         null,
  "truth_level":         "REGENERATED_RETROSPECTIVE",
  "source":              "p3_dryrun",
  "adapter_class":       "_PowerPrecision3BetAdapter",
  "adapter_file_hash":   "<md5>",
  "history_window_start": "2007/01/04",
  "history_window_end":   "2026/03/30",
  "history_window_size":  1905,
  "generated_at":        "2026-05-13T...",
  "dry_run_only":        true
}
```

---

## 8. Per-Strategy Results

| Strategy | Lottery Type | Adapter | Target Draws | Succeeded | Skipped(hist) | Skipped(err) | Leakage Assert |
|----------|-------------|---------|-------------|-----------|--------------|-------------|----------------|
| `power_precision_3bet` | POWER_LOTTO | `_PowerPrecision3BetAdapter` | 50 | 50 | 0 | 0 | 50 |
| `power_orthogonal_5bet` | POWER_LOTTO | `_PowerOrthogonal5BetAdapter` | 50 | 50 | 0 | 0 | 50 |
| `biglotto_triple_strike` | BIG_LOTTO | `_BigLottoTripleStrikeAdapter` | 50 | 50 | 0 | 0 | 50 |
| `biglotto_deviation_2bet` | BIG_LOTTO | `_BigLottoDeviation2BetAdapter` | 50 | 50 | 0 | 0 | 50 |
| `daily539_f4cold` | DAILY_539 | `_Daily539F4ColdAdapter` | 50 | 50 | 0 | 0 | 50 |
| `daily539_markov_cold` | DAILY_539 | `_Daily539MarkovColdAdapter` | 50 | 50 | 0 | 0 | 50 |

---

## 9. Candidate Row Counts

**Total candidate rows**: 300

| Lottery Type | Row Count | Strategies |
|-------------|-----------|-----------|
| POWER_LOTTO | 100 | power_orthogonal_5bet, power_precision_3bet |
| BIG_LOTTO | 100 | biglotto_deviation_2bet, biglotto_triple_strike |
| DAILY_539 | 100 | daily539_markov_cold, daily539_f4cold |

**Total skipped (insufficient history)**: 0
**Total skipped (adapter error)**: 0

---

## 10. ARTIFACT_ONLY Non-regeneration Rationale

The following 4 ARTIFACT_ONLY strategies are **not** regenerated in P3.
No formula inference from rejected artifact. No memory-based reconstruction.

| Strategy | Lottery Type | Lifecycle | Artifact Path | Required Fix |
|----------|-------------|-----------|--------------|-------------|
| `biglotto_ts3_acb_4bet` | BIG_LOTTO | REJECTED | `rejected/ts3_acb_4bet_biglotto.json` | artifact_parser |
| `biglotto_ts3_markov_freq_5bet` | BIG_LOTTO | REJECTED | `rejected/ts3_markov_freq_5bet_biglotto.json` | artifact_parser |
| `power_shlc_midfreq` | POWER_LOTTO | REJECTED | `rejected/shlc_midfreq_power.json` | artifact_parser |
| `p1_deviation_2bet_539` | DAILY_539 | REJECTED | `rejected/p1_deviation_2bet_539.json` | artifact_parser |

**P4 future work** (per strategy):
- `biglotto_ts3_acb_4bet`: No executable Python adapter registered. Artifact exists as rejected JSON, but deterministic replay formula cannot be inferred from artifact without an artifact_parser wrapper. P4 task required: implement artifact_parser + adapter_wrapper.
- `biglotto_ts3_markov_freq_5bet`: No executable Python adapter registered. Artifact exists as rejected JSON + strategies dir. P4 task required: implement artifact_parser + adapter_wrapper.
- `power_shlc_midfreq`: No executable Python adapter registered and no strategies/ dir. Only rejected artifact JSON exists. P4 task required: implement artifact_parser + reconstruct formula from JSON.
- `p1_deviation_2bet_539`: No executable Python adapter registered and no strategies/ dir. Only rejected artifact JSON exists. P4 task required: implement artifact_parser + reconstruct formula from JSON.

---

## 11. Errors / Blockers

No errors or blockers encountered.

---

## 12. DB / Registry Unchanged Verification

| Check | Hash | Status |
|-------|------|--------|
| `lottery_api/data/lottery_v2.db` | `de0e27bb800bc7183773a0dc596d66b8` | ✅ UNCHANGED |
| `lottery_api/models/replay_strategy_registry.py` | `3ea71cfc20c882714f3824ad68202f6e` | ✅ UNCHANGED |
| No DB writes | `sqlite3 mode=ro` + no INSERT/UPDATE/DELETE | ✅ VERIFIED |
| No registry mutations | Script never imports registry with write intent | ✅ VERIFIED |
| No lifecycle mutations | `lifecycle_status` never modified | ✅ VERIFIED |

---

## 13. P6 Controlled Apply Readiness

| Criterion | Status |
|-----------|--------|
| ≥1 EXECUTABLE_NOW strategy succeeded | ✅ |
| Candidate rows > 0 | ✅ |
| All rows carry truth_level=REGENERATED_RETROSPECTIVE | ✅ |
| All rows carry dry_run_only=true | ✅ |
| All rows carry adapter_file_hash (provenance) | ✅ |
| Leakage guard: 0 failures | ✅ |
| DB unchanged | ✅ |
| Registry unchanged | ✅ |

P6 controlled apply is **feasible** subject to:
1. CTO authorization (`YES apply P6`)
2. PR #92 / #93 / #94 merge chain completion
3. Additional review of edge cases (draw gaps, special number handling)

---

## 14. Next 24h Prompt (P4/P6)

```text
# After P3 is merged and #92/#93/#94 are merged:
# P4 Mission: ARTIFACT_ONLY artifact_parser
#   - For each ARTIFACT_ONLY strategy, inspect rejected artifact JSON
#   - Determine if deterministic replay formula can be reconstructed
#   - If yes: implement artifact_parser + adapter_wrapper
#   - If no: maintain TOMBSTONE classification
#   - Strict rule: no formula inference from memory; artifact must explicitly contain formula
#
# P6 Mission (after P4, with CTO authorization): controlled DB apply
#   - Apply P3 candidate rows to production DB
#   - Use INSERT with truth_level=REGENERATED_RETROSPECTIVE
#   - Verify row counts before and after
#   - Create rollback snapshot
#   - Requires explicit YES apply P6 from user/CTO
```

---

## 15. Final Markers

```
P3_RETROSPECTIVE_DRYRUN_COMPLETE

P3_PR_CHAIN_VERIFIED
P3_BASELINE_VERIFIED
P3_HISTORICAL_SOURCE_AUDITED
P3_EXECUTABLE_NOW_STRATEGIES_LOADED
P3_DRYRUN_SCRIPT_CREATED
P3_LEAKAGE_GUARD_IMPLEMENTED
P3_CANDIDATE_ROWS_GENERATED
P3_PER_STRATEGY_COUNTS_REPORTED
P3_ARTIFACT_ONLY_STRATEGIES_NOT_REGENERATED
P3_DB_UNCHANGED
P3_REGISTRY_UNCHANGED
P3_REPORT_CREATED
P3_PR_OPENED
P3_READY_FOR_CTO_REVIEW
P3_BASELINE_DEPENDS_ON_OPEN_PR_CHAIN
```
