# P1 Replay Truth Executable Evidence Report
## 2026-05-13 — CTO Review Submission

---

## 1. 本輪目標

在不寫 production DB、不修改 registry、不做策略 promotion 的前提下，完成
**P1：全策略「程式可執行性實證盤點」** 與 retrospective regeneration readiness report。

目標是以 **實際 evidence**（import check、adapter instantiate、dry-call、artifact scan）
判斷 16 個 canonical strategies 的可執行性，不採用紙上分類。

---

## 2. Baseline / PR #92 Dependency State

| Item | Value |
|------|-------|
| Branch (P1 work) | `audit/p1-replay-truth-executable-evidence-20260513` |
| Branched from | `frontend/p78-configurable-api-base-20260513` (d17da60) |
| main HEAD | `d438fb6` |
| PR #92 state | OPEN / MERGEABLE / **CI ALL CHECKS PASS** |
| PR #92 diff scope | `index.html` + `outputs/replay/p78_configurable_api_base_report_20260513.md` |
| DB hash | `de0e27bb800bc7183773a0dc596d66b8` ✅ |
| Registry hash | `3ea71cfc20c882714f3824ad68202f6e` ✅ |
| Baseline label | **P1_BASELINE_DEPENDS_ON_P78_OPEN_PR** |

> Note: PR #92 CI is fully green and diff is clean. P1 audit is read-only and
> does not depend on PR #92 merge state. Merge gate follows separate `YES merge PR #92` instruction.

---

## 3. 16 Strategy Lifecycle Summary

Source: `lottery_api/models/replay_strategy_registry.py` — `list_strategy_lifecycle_metadata()`

| # | strategy_id | display_name | lifecycle | lottery_type | version |
|---|-------------|-------------|-----------|-------------|---------|
| 1 | `power_precision_3bet` | 威力彩 Precision 3注 | **ONLINE** | POWER_LOTTO | v0.1 |
| 2 | `power_orthogonal_5bet` | 威力彩 Orthogonal 5注 | **ONLINE** | POWER_LOTTO | v0.1 |
| 3 | `biglotto_triple_strike` | 大樂透 Triple Strike | **ONLINE** | BIG_LOTTO | v0.1 |
| 4 | `biglotto_deviation_2bet` | 大樂透 Deviation 2注 | **ONLINE** | BIG_LOTTO | v0.1 |
| 5 | `daily539_f4cold` | 今彩539 F4 Cold | **ONLINE** | DAILY_539 | v0.1 |
| 6 | `daily539_markov_cold` | 今彩539 Markov Cold | **ONLINE** | DAILY_539 | v0.1 |
| 7 | `biglotto_ts3_acb_4bet` | 大樂透 TS3+ACB 4注 | REJECTED | BIG_LOTTO | v0.0 |
| 8 | `biglotto_ts3_markov_freq_5bet` | 大樂透 TS3+Markov 頻率正交 5注 | REJECTED | BIG_LOTTO | v0.0 |
| 9 | `power_shlc_midfreq` | 威力彩 SHLC 中頻指標 | REJECTED | POWER_LOTTO | v0.0 |
| 10 | `p1_deviation_2bet_539` | 今彩539 P1鄰號+偏差互補 2注 | REJECTED | DAILY_539 | v0.0 |
| 11 | `acb_1bet` | 今彩539 ACB 1注 | RETIRED | DAILY_539 | v0.0 |
| 12 | `acb_markov_midfreq` | 今彩539 ACB+Markov 中頻 | RETIRED | DAILY_539 | v0.0 |
| 13 | `acb_markov_midfreq_3bet` | 今彩539 ACB+Markov 中頻 3注 | RETIRED | DAILY_539 | v0.0 |
| 14 | `midfreq_acb_2bet` | 今彩539 中頻 ACB 2注 | RETIRED | DAILY_539 | v0.0 |
| 15 | `midfreq_fourier_2bet` | 今彩539 中頻 Fourier 2注 | RETIRED | DAILY_539 | v0.0 |
| 16 | `h6_gate_mk20_ew85` | 威力彩 H6 Gate mk20 ew85 | OBSERVATION | POWER_LOTTO | v0.0 |

**Total: 16 ✅** — matches expected canonical count.

---

## 4. Per-Strategy Executable Evidence Table

### Evidence Sources
- **registry_present**: Strategy exists in `list_strategy_lifecycle_metadata()`
- **adapter_available**: `get_adapter(strategy_id)` returns without KeyError
- **get_one_bet_callable**: adapter has `get_one_bet()` method
- **dry_call**: `get_one_bet(synthetic_history, lottery_type)` executed — PASS/FAIL
  - PASS results confirmed with venv python (numpy available)
  - N/A = no adapter registered (non-ONLINE strategies — dry-call intentionally skipped)
- **strategy_dir**: `strategies/<lottery>/<name>/` directory exists with `strategy.yaml`
- **rejected_json**: `rejected/<name>.json` artifact exists
- **tool_predict**: `tools/predict_<name>.py` exists

| # | strategy_id | lifecycle | adapter | get_one_bet | dry_call | strategy_dir | rejected_json | tool_predict | **classification** |
|---|-------------|-----------|:-------:|:-----------:|:--------:|:------------:|:-------------:|:------------:|:-------------------|
| 1 | `power_precision_3bet` | ONLINE | ✅ `_PowerPrecision3BetAdapter` | ✅ | ✅ PASS (tuple,2) | ✅ | ❌ | ✅ | **EXECUTABLE_NOW** |
| 2 | `power_orthogonal_5bet` | ONLINE | ✅ `_PowerOrthogonal5BetAdapter` | ✅ | ✅ PASS (tuple,2) | ✅ | ❌ | ✅ | **EXECUTABLE_NOW** |
| 3 | `biglotto_triple_strike` | ONLINE | ✅ `_BigLottoTripleStrikeAdapter` | ✅ | ✅ PASS (tuple,2) | ✅ | ❌ | ✅ | **EXECUTABLE_NOW** |
| 4 | `biglotto_deviation_2bet` | ONLINE | ✅ `_BigLottoDeviation2BetAdapter` | ✅ | ✅ PASS (tuple,2) | ✅ | ❌ | ✅ | **EXECUTABLE_NOW** |
| 5 | `daily539_f4cold` | ONLINE | ✅ `_Daily539F4ColdAdapter` | ✅ | ✅ PASS (tuple,2) | ✅ | ❌ | ✅ | **EXECUTABLE_NOW** |
| 6 | `daily539_markov_cold` | ONLINE | ✅ `_Daily539MarkovColdAdapter` | ✅ | ✅ PASS (tuple,2) | ❌¹ | ❌ | ✅ | **EXECUTABLE_NOW** |
| 7 | `biglotto_ts3_acb_4bet` | REJECTED | ❌ | ❌ | N/A | ✅ (`4bet_ts3_markov_w30`) | ✅ | ❌ | **ARTIFACT_ONLY** |
| 8 | `biglotto_ts3_markov_freq_5bet` | REJECTED | ❌ | ❌ | N/A | ✅ (`5bet_ts3_markov_freq`) | ✅ | ❌ | **ARTIFACT_ONLY** |
| 9 | `power_shlc_midfreq` | REJECTED | ❌ | ❌ | N/A | ❌ | ✅ | ❌ | **ARTIFACT_ONLY** |
| 10 | `p1_deviation_2bet_539` | REJECTED | ❌ | ❌ | N/A | ❌ | ✅² | ❌ | **ARTIFACT_ONLY** |
| 11 | `acb_1bet` | RETIRED | ❌ | ❌ | N/A | ❌ | ❌ | ❌ | **CODE_MISSING** |
| 12 | `acb_markov_midfreq` | RETIRED | ❌ | ❌ | N/A | ❌ | ❌ | ❌ | **CODE_MISSING** |
| 13 | `acb_markov_midfreq_3bet` | RETIRED | ❌ | ❌ | N/A | ❌ | ❌ | ❌ | **CODE_MISSING** |
| 14 | `midfreq_acb_2bet` | RETIRED | ❌ | ❌ | N/A | ❌ | ❌ | ❌ | **CODE_MISSING** |
| 15 | `midfreq_fourier_2bet` | RETIRED | ❌ | ❌ | N/A | ❌ | ❌ | ❌ | **CODE_MISSING** |
| 16 | `h6_gate_mk20_ew85` | OBSERVATION | ❌ | ❌ | N/A | ❌ | ❌ | ❌ | **CODE_MISSING** |

¹ `daily539_markov_cold` has no dedicated `strategies/daily_539/markov_cold/` dir but has production adapter and predict tool — EXECUTABLE_NOW is confirmed.  
² `rejected/p1_deviation_2bet_539.json` exists but has a JSON parse warning (value on line 12 col 25) — content is readable, contains statistics.

### Classification Summary

| Classification | Count | Strategy IDs |
|----------------|-------|-------------|
| **EXECUTABLE_NOW** | **6** | power_precision_3bet, power_orthogonal_5bet, biglotto_triple_strike, biglotto_deviation_2bet, daily539_f4cold, daily539_markov_cold |
| EXECUTABLE_WITH_FIX | 0 | — |
| **ARTIFACT_ONLY** | **4** | biglotto_ts3_acb_4bet, biglotto_ts3_markov_freq_5bet, power_shlc_midfreq, p1_deviation_2bet_539 |
| **CODE_MISSING** | **6** | acb_1bet, acb_markov_midfreq, acb_markov_midfreq_3bet, midfreq_acb_2bet, midfreq_fourier_2bet, h6_gate_mk20_ew85 |
| TOMBSTONE | 0 | — |
| NEEDS_MANUAL_DECISION | 0 | — |

> **Correction from P78 draft**: P78 classified 10 as CODE_MISSING. P1 evidence-based audit corrects this:
> 4 REJECTED strategies have `rejected/*.json` and/or `strategies/*/` directories → upgraded to **ARTIFACT_ONLY**.
> Only 5 RETIRED + 1 OBSERVATION with zero code/artifact → remain **CODE_MISSING**.

---

## 5. Artifact-Only / Rejected / Retired Evidence Map

### ARTIFACT_ONLY Strategies

#### `biglotto_ts3_acb_4bet` (REJECTED)
- **strategy_dir**: `strategies/big_lotto/4bet_ts3_markov_w30/`
  - Contains: `strategy.yaml`, `sim_result.json`, `backtest_report.md`, `performance_log.json`, `version_tag.txt`
  - `strategy.yaml` status: `ACTIVE` (historical — this was before rejection)
- **rejected_json**: `rejected/ts3_acb_4bet_biglotto.json`
  - verdict: `REJECTED`
  - failure_reasons: Three-window inconsistent (150p=-5.29%), ACB rescue efficiency 73.1% (sub-random), signal overlap 50%
  - statistics: complete (windows, permutation, marginal_rescue, mcnemar)
- **deterministic formula**: YES — TS3 base (bet1-3) is deterministic; ACB component documented
- **retrospective generation**: Possible from strategy.yaml + rejected JSON parameters, but ACB 1-bet formula not encoded as Python adapter
- **blocker**: No Python adapter; formula parameters in YAML/JSON but no executable code path

#### `biglotto_ts3_markov_freq_5bet` (REJECTED)
- **strategy_dir**: `strategies/big_lotto/5bet_ts3_markov_freq/`
  - Contains: `strategy.yaml`, `sim_result.json`, `backtest_report.md`, `performance_log.json`, `stat_test.txt`, `version_tag.txt`
  - status: `ACTIVE` (pre-rejection historical)
- **rejected_json**: `rejected/ts3_markov_freq_5bet_biglotto.json`
  - pattern: `SUPERSEDED` (superseded by P1+偏差互補)
  - failure_reason: Architecture isolation; 4-bet base already replaced; 5th bet cannot extend naturally
  - statistics: complete
- **deterministic formula**: YES — TS3+Markov+頻率正交 fully documented in strategy.yaml
- **retrospective generation**: High feasibility — TS3 base uses same algorithm as `biglotto_triple_strike` ONLINE adapter; Markov+freq5 formula in YAML
- **blocker**: No Python adapter; base TS3 code exists in biglotto_triple_strike adapter (could be extended)

#### `power_shlc_midfreq` (REJECTED)
- **strategy_dir**: None
- **rejected_json**: `rejected/shlc_midfreq_power.json`
  - proposed_date/rejected_date: 2026-03-03 (same day — failed pre-adoption)
  - hypothesis: SHLC = rank_500/rank_100 > 3.0 signal
  - implementation: SHLC Top-6 replacing Fourier 7-12 in PP3 bet2
  - backtest: three_window_pass=false, perm_p=0.595 — clearly failed
  - statistics: complete
- **deterministic formula**: Partially documented (SHLC ratio formula), but no full independent implementation
- **retrospective generation**: Low feasibility — SHLC is a modifier of PP3 bet2, not standalone; formula derivable from rejected JSON
- **blocker**: No strategy_dir, no Python code; formula is a modifier variant of existing strategy

#### `p1_deviation_2bet_539` (REJECTED)
- **strategy_dir**: None
- **rejected_json**: `rejected/p1_deviation_2bet_539.json` (JSON parse warning at line 12)
  - failure_reason: Signal does not exist — P1 neighbor + deviation cold is BIG_LOTTO-specific; cannot transfer to 539
  - pattern: `INEFFECTIVE`
  - statistics: 5293-period full backtest, edge≈0%, perm_p=1.000
- **deterministic formula**: Yes (documented algorithm), but confirmed signal = 0
- **retrospective generation**: Not meaningful — strategy has been proven to have no signal; regenerating rows would produce noise
- **blocker**: No Python adapter; no signal; regeneration not recommended

---

### CODE_MISSING Strategies (RETIRED + OBSERVATION)

All 5 RETIRED strategies and `h6_gate_mk20_ew85` share the same pattern:

| strategy_id | lifecycle | Python adapter | strategy_dir | rejected_json | historical ref | note |
|-------------|-----------|:--------------:|:------------:|:-------------:|:------:|------|
| `acb_1bet` | RETIRED | ❌ | ❌ | ❌ | Catalog only | Retired 539 main strategy |
| `acb_markov_midfreq` | RETIRED | ❌ | ❌ | ❌ | Catalog only | Retired |
| `acb_markov_midfreq_3bet` | RETIRED | ❌ | ❌ | ❌ | Catalog only | Retired |
| `midfreq_acb_2bet` | RETIRED | ❌ | ❌ | ❌ | Catalog only | Retired main strategy |
| `midfreq_fourier_2bet` | RETIRED | ❌ | ❌ | ❌ | Catalog only | Retired |
| `h6_gate_mk20_ew85` | OBSERVATION | ❌ | ❌ | ❌ | docs/governance refs | Governance task result NOT committed |

**Evidence of existence**: These strategies appear in `outputs/replay/strategy_catalog_inventory_20260512.md` as `lifecycle_stub` entries.  
**Evidence of code**: None found. `find . -name "*acb*" -o -name "*midfreq*"` yields only:
- `tools/explore_3_midfreq_analysis.py` (unrelated analysis tool)
- `rejected/*.json` entries for similar but distinct strategies

**h6_gate_mk20_ew85 special note**: The p56 report notes: `*(governance task result not committed to repo)*`. The H6 gate result exists externally but is NOT in the repo. No code path exists.

---

## 6. Import / Instantiate / Dry-Call Results

### Import Check
```
from lottery_api.models.replay_strategy_registry import (
    list_strategy_lifecycle_metadata, get_adapter
)
STATUS: OK
```

### Adapter Instantiation

| strategy_id | get_adapter() | class | public_methods | status |
|-------------|:------------:|-------|---------------|--------|
| `power_precision_3bet` | ✅ | `_PowerPrecision3BetAdapter` | `[get_one_bet, meta]` | ADAPTER_FOUND |
| `power_orthogonal_5bet` | ✅ | `_PowerOrthogonal5BetAdapter` | `[get_one_bet, meta]` | ADAPTER_FOUND |
| `biglotto_triple_strike` | ✅ | `_BigLottoTripleStrikeAdapter` | `[get_one_bet, meta]` | ADAPTER_FOUND |
| `biglotto_deviation_2bet` | ✅ | `_BigLottoDeviation2BetAdapter` | `[get_one_bet, meta]` | ADAPTER_FOUND |
| `daily539_f4cold` | ✅ | `_Daily539F4ColdAdapter` | `[get_one_bet, meta]` | ADAPTER_FOUND |
| `daily539_markov_cold` | ✅ | `_Daily539MarkovColdAdapter` | `[get_one_bet, meta]` | ADAPTER_FOUND |
| `biglotto_ts3_acb_4bet` | ❌ | — | — | NO_ADAPTER_REGISTERED |
| `biglotto_ts3_markov_freq_5bet` | ❌ | — | — | NO_ADAPTER_REGISTERED |
| `power_shlc_midfreq` | ❌ | — | — | NO_ADAPTER_REGISTERED |
| `p1_deviation_2bet_539` | ❌ | — | — | NO_ADAPTER_REGISTERED |
| `acb_1bet` | ❌ | — | — | NO_ADAPTER_REGISTERED |
| `acb_markov_midfreq` | ❌ | — | — | NO_ADAPTER_REGISTERED |
| `acb_markov_midfreq_3bet` | ❌ | — | — | NO_ADAPTER_REGISTERED |
| `midfreq_acb_2bet` | ❌ | — | — | NO_ADAPTER_REGISTERED |
| `midfreq_fourier_2bet` | ❌ | — | — | NO_ADAPTER_REGISTERED |
| `h6_gate_mk20_ew85` | ❌ | — | — | NO_ADAPTER_REGISTERED |

### `get_one_bet()` Signature
```python
# All 6 ONLINE adapters share the same signature:
(history: List[dict], lottery_type: str) -> Tuple[List[int], Optional[int]]
```

### Dry-Call Results (synthetic history, 104 records, no DB write)

**Python interpreter**: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.venv/bin/python` (numpy available)  
**System python3**: `ModuleNotFoundError: No module named 'numpy'` — documented as env note, not blocker for production replay

| strategy_id | dry_call_result | output_type | output_len |
|-------------|:---------------:|:-----------:|:----------:|
| `power_precision_3bet` | **PASS** | tuple | 2 |
| `power_orthogonal_5bet` | **PASS** | tuple | 2 |
| `biglotto_triple_strike` | **PASS** | tuple | 2 |
| `biglotto_deviation_2bet` | **PASS** | tuple | 2 |
| `daily539_f4cold` | **PASS** | tuple | 2 |
| `daily539_markov_cold` | **PASS** | tuple | 2 |
| *(REJECTED × 4)* | N/A (no adapter) | — | — |
| *(RETIRED × 5)* | N/A (no adapter) | — | — |
| `h6_gate_mk20_ew85` | N/A (no adapter) | — | — |

**All 6 ONLINE adapters: DRY_CALL_PASS ✅**

Output tuple: `(List[int], Optional[int])` where index 0 = predicted ball numbers, index 1 = predicted special/bonus (None for DAILY_539).

> Note: System Python dry-call fails with `ModuleNotFoundError: No module named 'numpy'`. This is an environment gap (not a code defect) — production backend uses venv with numpy installed.

---

## 7. Retrospective Regeneration Readiness Classification

| strategy_id | can_regenerate_now | regeneration_source | required_fix | proposed_truth_level | p3_candidate |
|-------------|:-----------------:|---------------------|:------------:|:--------------------:|:------------:|
| `power_precision_3bet` | **true** | `production_adapter` | none | **PRODUCTION_REPLAY** | **true** |
| `power_orthogonal_5bet` | **true** | `production_adapter` | none | **PRODUCTION_REPLAY** | **true** |
| `biglotto_triple_strike` | **true** | `production_adapter` | none | **PRODUCTION_REPLAY** | **true** |
| `biglotto_deviation_2bet` | **true** | `production_adapter` | none | **PRODUCTION_REPLAY** | **true** |
| `daily539_f4cold` | **true** | `production_adapter` | none | **PRODUCTION_REPLAY** | **true** |
| `daily539_markov_cold` | **true** | `production_adapter` | none | **PRODUCTION_REPLAY** | **true** |
| `biglotto_ts3_acb_4bet` | false | `rejected_artifact` | `artifact_parser` | **ARTIFACT_PROVENANCE_ONLY** | false |
| `biglotto_ts3_markov_freq_5bet` | false | `rejected_artifact` | `artifact_parser` | **ARTIFACT_PROVENANCE_ONLY** | false |
| `power_shlc_midfreq` | false | `rejected_artifact` | `artifact_parser` | **ARTIFACT_PROVENANCE_ONLY** | false |
| `p1_deviation_2bet_539` | false | `rejected_artifact` | `artifact_parser` | **ARTIFACT_PROVENANCE_ONLY** | false |
| `acb_1bet` | false | `none` | `missing_source_code` | **TOMBSTONE_NO_SOURCE** | false |
| `acb_markov_midfreq` | false | `none` | `missing_source_code` | **TOMBSTONE_NO_SOURCE** | false |
| `acb_markov_midfreq_3bet` | false | `none` | `missing_source_code` | **TOMBSTONE_NO_SOURCE** | false |
| `midfreq_acb_2bet` | false | `none` | `missing_source_code` | **TOMBSTONE_NO_SOURCE** | false |
| `midfreq_fourier_2bet` | false | `none` | `missing_source_code` | **TOMBSTONE_NO_SOURCE** | false |
| `h6_gate_mk20_ew85` | false | `none` | `missing_source_code` | **TOMBSTONE_NO_SOURCE** | false |

### Notes on ARTIFACT_PROVENANCE_ONLY
These 4 strategies have rejected artifacts and/or strategy directories but no executable Python path.
They can be displayed in UI with an `ARTIFACT_PROVENANCE_ONLY` badge, but **cannot produce replay rows** without:
1. Writing a new Python adapter
2. Implementing formula-to-code from artifact parameters
3. Obtaining explicit P2 authorization for retrospective generation

### Notes on TOMBSTONE_NO_SOURCE
These 6 strategies have zero code provenance. RETIRED strategies were previously main strategies but their source was never preserved. `h6_gate_mk20_ew85` has external governance documentation (not committed).  
**Rule: Do not reconstruct from memory. Tombstone is final unless source code emerges.**

---

## 8. P2 Truth-Level Taxonomy / UI Badge Gap

### Current Badge Support (index.html)

| truth_level | CSS class | Display label | Present? |
|-------------|-----------|--------------|:--------:|
| `PRODUCTION_REPLAY` | `rp-truth-production` | LIVE | ✅ |
| `DISPLAY_ONLY` | `rp-truth-display` | METADATA ONLY | ✅ |
| `MISSING_HISTORY` | `rp-truth-missing` | NO HISTORY | ✅ |
| `FIXTURE_ONLY` | `rp-truth-fixture` | FIXTURE | ✅ |
| `LEGACY_ERROR` | `rp-truth-legacy-err` | LEGACY ERROR | ✅ |
| `REGENERATED_RETROSPECTIVE` | `rp-truth-retro` | RETROSPECTIVE | ✅ |
| `REPLAY_ERROR` | — | REPLAY_ERROR (filter) | ✅ (partial) |
| `ARTIFACT_PROVENANCE_ONLY` | — | — | ❌ **MISSING** |
| `TOMBSTONE_NO_SOURCE` | — | — | ❌ **MISSING** |

### P2 Required Changes (read-only identification — no UI change this round)

#### Missing Badge: `ARTIFACT_PROVENANCE_ONLY`
```javascript
// Proposed addition to renderTruthLevelBadge() map:
'ARTIFACT_PROVENANCE_ONLY': '<span class="rp-truth-badge rp-truth-artifact-prov"
  title="ARTIFACT: 策略僅有 rejected/backtest artifact，無可執行 Python code"
  aria-label="ARTIFACT: Strategy has rejected artifact only, no executable code">
  ARTIFACT ONLY</span>',
```
- Required CSS: `.rp-truth-artifact-prov { background: #f39c12; color: #fff; }`
- Required in `determineTruthLevel()` mapping: `REJECTED + !exec + has_artifact → ARTIFACT_PROVENANCE_ONLY`

#### Missing Badge: `TOMBSTONE_NO_SOURCE`
```javascript
// Proposed addition to renderTruthLevelBadge() map:
'TOMBSTONE_NO_SOURCE': '<span class="rp-truth-badge rp-truth-tombstone"
  title="TOMBSTONE: 無任何可執行 code 或 artifact，無法重建"
  aria-label="TOMBSTONE: No source code or artifact exists">
  TOMBSTONE</span>',
```
- Required CSS: `.rp-truth-tombstone { background: #7f8c8d; color: #fff; }`
- Required in `determineTruthLevel()`: `RETIRED/OBSERVATION + !exec + !has_artifact → TOMBSTONE_NO_SOURCE`

#### API Response Gap
Current `/api/replay/strategy-lifecycle` returns `lifecycle_status` but not `has_artifact_provenance`.
P2 API addition needed:
```json
{
  "strategy_id": "biglotto_ts3_acb_4bet",
  "lifecycle_status": "REJECTED",
  "has_artifact_provenance": true,
  "artifact_paths": ["rejected/ts3_acb_4bet_biglotto.json", "strategies/big_lotto/4bet_ts3_markov_w30/"],
  "proposed_truth_level": "ARTIFACT_PROVENANCE_ONLY"
}
```

#### Backwards Compatibility
- Current `DISPLAY_ONLY` badge already covers `REJECTED + !exec` — safe to add new badge for rejected-with-artifact
- `MISSING_HISTORY` covers `RETIRED` — `TOMBSTONE_NO_SOURCE` would be more precise sub-classification
- No existing rows use new badge types → zero backwards compat risk

---

## 9. P3 Dry-Run Regeneration Candidate List

**P3 Authorized candidates (EXECUTABLE_NOW + p3_candidate=true):**

| # | strategy_id | lottery_type | adapter_class | get_one_bet_sig | dry_call |
|---|-------------|-------------|---------------|----------------|----------|
| 1 | `power_precision_3bet` | POWER_LOTTO | `_PowerPrecision3BetAdapter` | `(history, lottery_type) → Tuple` | ✅ PASS |
| 2 | `power_orthogonal_5bet` | POWER_LOTTO | `_PowerOrthogonal5BetAdapter` | `(history, lottery_type) → Tuple` | ✅ PASS |
| 3 | `biglotto_triple_strike` | BIG_LOTTO | `_BigLottoTripleStrikeAdapter` | `(history, lottery_type) → Tuple` | ✅ PASS |
| 4 | `biglotto_deviation_2bet` | BIG_LOTTO | `_BigLottoDeviation2BetAdapter` | `(history, lottery_type) → Tuple` | ✅ PASS |
| 5 | `daily539_f4cold` | DAILY_539 | `_Daily539F4ColdAdapter` | `(history, lottery_type) → Tuple` | ✅ PASS |
| 6 | `daily539_markov_cold` | DAILY_539 | `_Daily539MarkovColdAdapter` | `(history, lottery_type) → Tuple` | ✅ PASS |

**P3 next prompt template:**
```
P3 Mission: For each of the 6 EXECUTABLE_NOW strategies, call
  reg.get_adapter(strategy_id).get_one_bet(historical_data_up_to_date, lottery_type)
for a specific dry-run draw_date (e.g., 2026-01-01).
Verify output schema: numbers=List[int], special=Optional[int].
Log call timestamp and input draw_date.
DO NOT write to DB.
Report P3_DRY_RUN_PASS or P3_DRY_RUN_FAIL per strategy.
```

---

## 10. 不可重建 / Tombstone Candidates

**Permanently CODE_MISSING (no source code, no rejected artifact):**

| strategy_id | lifecycle | reason | recommendation |
|-------------|-----------|--------|----------------|
| `acb_1bet` | RETIRED | No Python adapter, no strategy_dir, no rejected JSON | **TOMBSTONE** — display `TOMBSTONE_NO_SOURCE` badge |
| `acb_markov_midfreq` | RETIRED | Same | **TOMBSTONE** |
| `acb_markov_midfreq_3bet` | RETIRED | Same | **TOMBSTONE** |
| `midfreq_acb_2bet` | RETIRED | Same | **TOMBSTONE** |
| `midfreq_fourier_2bet` | RETIRED | Same | **TOMBSTONE** |
| `h6_gate_mk20_ew85` | OBSERVATION | No code, governance task result not committed | **TOMBSTONE pending governance decision** |

**Rule applied**: RETIRED = cannot reconstruct from memory; source code never preserved in repo.  
**h6 exception**: If governance task result is committed to repo in future, reclassify from TOMBSTONE → ARTIFACT_PROVENANCE_ONLY. Current state = TOMBSTONE.

---

## 11. DB / Registry Unchanged Verification

| Verification | Expected | Actual | Status |
|-------------|----------|--------|--------|
| `lottery_api/data/lottery_v2.db` MD5 | `de0e27bb800bc7183773a0dc596d66b8` | `de0e27bb800bc7183773a0dc596d66b8` | ✅ UNCHANGED |
| `lottery_api/models/replay_strategy_registry.py` MD5 | `3ea71cfc20c882714f3824ad68202f6e` | `3ea71cfc20c882714f3824ad68202f6e` | ✅ UNCHANGED |
| DB files staged | — | `git diff --cached` shows no *.db | ✅ NOT STAGED |
| Registry mutation | — | No edit to registry file | ✅ NOT MUTATED |
| Lifecycle status changed | — | No lifecycle promotion | ✅ NOT CHANGED |
| Production replay rows written | — | No backfill/apply executed | ✅ NOT WRITTEN |

---

## 12. Risk / Uncertainty

| Risk | Severity | Detail |
|------|----------|--------|
| System Python missing numpy | LOW | System `python3` fails dry-call with `ModuleNotFoundError: No module named 'numpy'`. Venv python succeeds. Production backend uses venv — this is an env documentation gap, not a production risk. |
| `p1_deviation_2bet_539.json` parse warning | LOW | JSON has a parse issue at line 12 col 25 (trailing comma or similar). Content is readable; statistics are complete. Does not affect classification. |
| `biglotto_ts3_markov_freq_5bet` strategy_dir mapping | MEDIUM | strategy_dir mapped to `strategies/big_lotto/5bet_ts3_markov_freq/` which has `status: ACTIVE` (pre-rejection). This is historical. The rejected JSON explicitly marks it `SUPERSEDED`. Treat `strategies/` dir as historical artifact, not live. |
| RETIRED strategies have no source | MEDIUM | ACB and midfreq strategies show `min_history: 0` in registry (never ran live) suggesting they were tombstoned before any production data was collected. Their `lifecycle_stub` in strategy catalog confirms no replay rows ever existed. |
| `h6_gate_mk20_ew85` lottery_type mismatch | MEDIUM | Wiki references h6 as DAILY_539 strategy; registry has `POWER_LOTTO`. p59 crosscheck flagged this discrepancy. Governance decision needed before any action. |
| P1 investigation branched from P78 (not main) | LOW | P1 branch was created from `frontend/p78-configurable-api-base-20260513` (not main). This is safe for read-only audit — PR #92 changes are limited to index.html and one report. No registry or DB content differs from main. |

---

## 13. Next 24h Prompt

### P2 — UI Badge + API Extension
```
P2 Mission: Add ARTIFACT_PROVENANCE_ONLY and TOMBSTONE_NO_SOURCE badges to index.html.
Extend /api/replay/strategy-lifecycle to return has_artifact_provenance and proposed_truth_level.
Do NOT change lifecycle_status.
Do NOT write DB.
Do NOT promote/retire any strategy.
Expected: 4 REJECTED → show ARTIFACT ONLY badge; 6 CODE_MISSING → show TOMBSTONE badge.
Branch: frontend/p2-truth-level-badge-extension-20260513
```

### P3 — Dry-Run Retrospective Replay
```
P3 Mission: For each of 6 EXECUTABLE_NOW strategies, execute get_one_bet() against
real historical data (read-only DB query), for a specified dry-run date range.
Validate output schema. Report per-strategy PASS/FAIL.
Do NOT write to DB. Do NOT commit prediction rows.
Branch: audit/p3-retrospective-replay-dry-run-20260513
```

---

## 14. Final Markers

| Marker | Status |
|--------|--------|
| `P1_BASELINE_VERIFIED` | ✅ main=d438fb6, DB=de0e27bb, registry=3ea71fc |
| `P1_PR92_STATE_RECORDED` | ✅ OPEN / MERGEABLE / CI ALL PASS / diff scope=2 files |
| `P1_BASELINE_DEPENDS_ON_P78_OPEN_PR` | ✅ noted — P1 is read-only, no dependency on merge |
| `P1_16_STRATEGIES_ENUMERATED` | ✅ all 16 from registry API confirmed |
| `P1_PER_STRATEGY_ARTIFACT_MAP_CREATED` | ✅ adapter, strategy_dir, rejected_json, tool_predict all checked |
| `P1_IMPORT_CHECKS_COMPLETED` | ✅ all 16 strategies import-checked |
| `P1_DRY_CALL_CHECKS_COMPLETED_OR_SKIPPED_WITH_REASON` | ✅ 6 ONLINE = PASS; 10 non-ONLINE = N/A (no adapter registered) |
| `P1_RETROSPECTIVE_READINESS_CLASSIFIED` | ✅ 6 PRODUCTION_REPLAY, 4 ARTIFACT_PROVENANCE_ONLY, 6 TOMBSTONE_NO_SOURCE |
| `P1_TRUTH_LEVEL_GAP_IDENTIFIED` | ✅ 2 missing badges: ARTIFACT_PROVENANCE_ONLY, TOMBSTONE_NO_SOURCE |
| `P1_DB_UNCHANGED` | ✅ hash verified |
| `P1_REGISTRY_UNCHANGED` | ✅ hash verified |
| `P1_REPORT_CREATED` | ✅ `outputs/replay/p1_replay_truth_executable_evidence_report_20260513.md` |
| `P1_PR_OPENED` | ⏳ pending Task I |
| `P1_READY_FOR_CTO_REVIEW` | ✅ |
