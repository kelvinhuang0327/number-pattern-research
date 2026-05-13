# P2 Truth-Level Taxonomy v2 — Implementation Report
**Date**: 2026-05-13  
**Branch**: `frontend/p2-truth-level-taxonomy-v2-20260513`  
**Base**: `main` (`d438fb6`)  
**Ticket**: P2 (follows P1 evidence audit, PR #93)

---

## 1. Motivation

P1 evidence audit (PR #93) reclassified 16 strategies into three executable tiers:

| Tier | Count | Strategy IDs |
|------|-------|-------------|
| EXECUTABLE_NOW | 6 | All 6 ONLINE strategies |
| ARTIFACT_ONLY | 4 | `biglotto_ts3_acb_4bet`, `biglotto_ts3_markov_freq_5bet`, `power_shlc_midfreq`, `p1_deviation_2bet_539` |
| CODE_MISSING | 6 | 5 RETIRED + `h6_gate_mk20_ew85` (OBSERVATION) |

The existing `deriveTruthLevelForStrategy()` in `index.html` mapped:
- `REJECTED / OBSERVATION && !exec` → `DISPLAY_ONLY`  (too generic — no signal that artifact evidence exists)
- `RETIRED && !exec && totalRows === 0` → `MISSING_HISTORY`  (too generic — no signal that code is unrecoverable)

P2 introduces two new truth-level badges to surface finer provenance signals:

- **`ARTIFACT_PROVENANCE_ONLY`** — strategy has rejected artifact JSON / backtest records but no runnable adapter
- **`TOMBSTONE_NO_SOURCE`** — strategy has been retired with zero source code or artifact; prediction records cannot be regenerated

---

## 2. Changes Made

### File: `index.html`

#### 2a. CSS — New Badge Classes (line ~270)
```css
/* P2: new truth-level badges */
.rp-truth-artifact-prov { background:#d1680b; color:#fff; }
.rp-truth-tombstone     { background:#6e7681; color:#fff; }
/* P2: new disclaimer row backgrounds */
.rp-row-artifact-prov        { background:#fff4ec; border-bottom:1px solid #30363d; }
.rp-row-tombstone-no-source  { background:#f6f8fa; border-bottom:1px solid #30363d; }
```

#### 2b. `deriveTruthLevelForStrategy()` — Updated Routing
| Condition | v1 (old) | v2 (new) |
|-----------|----------|----------|
| `REJECTED && !exec` | `DISPLAY_ONLY` | `ARTIFACT_PROVENANCE_ONLY` |
| `OBSERVATION && !exec` | `DISPLAY_ONLY` | `ARTIFACT_PROVENANCE_ONLY` |
| `RETIRED && !exec && totalRows === 0` | `MISSING_HISTORY` | `TOMBSTONE_NO_SOURCE` |
| `ONLINE && totalRows > 0` | `PRODUCTION_REPLAY` | `PRODUCTION_REPLAY` (unchanged) |
| `RETIRED && totalRows > 0` | `PRODUCTION_REPLAY` | `PRODUCTION_REPLAY` (unchanged) |
| fallback | `UNKNOWN` | `UNKNOWN` (unchanged) |

`DISPLAY_ONLY` and `MISSING_HISTORY` are retained in the badge map and routing for backward-compatibility (e.g., if a new lifecycle status is added in future that cannot be classified more finely).

#### 2c. `renderTruthLevelBadge()` — Two New Entries
```javascript
'ARTIFACT_PROVENANCE_ONLY': '<span class="rp-truth-badge rp-truth-artifact-prov"
  title="僅有證據檔：此策略有 rejected artifact 或回測記錄，但無可執行的 Python adapter"
  aria-label="ARTIFACT ONLY: Rejected artifact or backtest record exists, no executable adapter">僅有證據檔</span>',

'TOMBSTONE_NO_SOURCE': '<span class="rp-truth-badge rp-truth-tombstone"
  title="無原始碼封存：此策略已退役且無任何可執行 code 或 artifact，不可重建預測記錄"
  aria-label="TOMBSTONE: No source code or artifact exists, prediction records cannot be regenerated">無原始碼封存</span>',
```

#### 2d. Disclaimer Row Expansion (lifecycle table)
Two new conditional rows appended below each strategy row:
- `ARTIFACT_PROVENANCE_ONLY` → amber row with 📋 provenance-only explanation (TC zh-TW + EN)
- `TOMBSTONE_NO_SOURCE` → gray row with 🪦 unrecoverable-source explanation (TC zh-TW + EN)

---

## 3. API / Serializer Contract Check

**Finding**: `TRUTH_LEVEL` is **not** present in any backend response. The frontend `deriveTruthLevelForStrategy()` computes it entirely from `lifecycle_status` (string) and `is_executable` (boolean) returned by `/api/replay/strategy-lifecycle`.

**Backend change required**: ❌ None  
**Evidence**: Grep of `lottery_api/routes/replay.py`, `lottery_api/models/replay_strategy_registry.py` returned zero matches for `truth_level`, `ARTIFACT_PROVENANCE_ONLY`, `TOMBSTONE_NO_SOURCE`, `DISPLAY_ONLY`, `MISSING_HISTORY`, `PRODUCTION_REPLAY`. Backend is pass-through string.

---

## 4. Static Verification

| Check | Expected | Actual | Pass? |
|-------|----------|--------|-------|
| `ARTIFACT_PROVENANCE_ONLY` occurrences | ≥ 4 | 6 | ✅ |
| `TOMBSTONE_NO_SOURCE` occurrences | ≥ 4 | 7 | ✅ |
| `rp-truth-artifact-prov` (CSS + HTML) | ≥ 2 | 2 | ✅ |
| `rp-truth-tombstone` (CSS + HTML) | ≥ 2 | 2 | ✅ |
| `REGENERATED_RETROSPECTIVE` (unchanged) | 2 | 2 | ✅ |
| `DISPLAY_ONLY` retained (backward compat) | ≥ 4 | 5 | ✅ |
| `MISSING_HISTORY` retained (backward compat) | ≥ 4 | 5 | ✅ |

---

## 5. Safety Invariants

| Check | Hash / Result | Pass? |
|-------|--------------|-------|
| `lottery_api/data/lottery_v2.db` | `de0e27bb800bc7183773a0dc596d66b8` | ✅ UNCHANGED |
| `lottery_api/models/replay_strategy_registry.py` | `3ea71cfc20c882714f3824ad68202f6e` | ✅ UNCHANGED |
| Files changed | `index.html` + this report only | ✅ |
| No DB write | n/a — frontend-only change | ✅ |
| No registry mutation | n/a — frontend-only change | ✅ |
| No lifecycle promotion | n/a — read-only display change | ✅ |

---

## 6. Expected Runtime Behavior After Merge

### Lifecycle table badge rendering (16 strategies):

| Strategy ID | Lifecycle | is_executable | New Badge |
|-------------|-----------|--------------|-----------|
| `biglotto_ts3_acb_4bet` | REJECTED | false | 僅有證據檔 (amber) |
| `biglotto_ts3_markov_freq_5bet` | REJECTED | false | 僅有證據檔 (amber) |
| `power_shlc_midfreq` | REJECTED | false | 僅有證據檔 (amber) |
| `p1_deviation_2bet_539` | REJECTED | false | 僅有證據檔 (amber) |
| `h6_gate_mk20_ew85` | OBSERVATION | false | 僅有證據檔 (amber) |
| `acb_1bet` | RETIRED | false | 無原始碼封存 (gray) |
| `acb_markov_midfreq` | RETIRED | false | 無原始碼封存 (gray) |
| `acb_markov_midfreq_3bet` | RETIRED | false | 無原始碼封存 (gray) |
| `midfreq_acb_2bet` | RETIRED | false | 無原始碼封存 (gray) |
| `midfreq_fourier_2bet` | RETIRED | false | 無原始碼封存 (gray) |
| 6× ONLINE strategies | ONLINE | true | LIVE (green) — unchanged |

---

## 7. Dependencies on Open PRs

| PR | Status | Contains |
|----|--------|---------|
| #92 (P78) | OPEN / CI GREEN | `window.API_BASE` configurable variable |
| #93 (P1) | OPEN / CI GREEN | P1 evidence audit scripts + inventory |
| This PR (P2) | TBD | `index.html` badge taxonomy v2 |

P2 is based on `main` (`d438fb6`) — zero contamination from #92 or #93.  
Merge order: #92 → #93 (may need rebase) → P2.

---

## 8. Known Limitations

1. `ARTIFACT_PROVENANCE_ONLY` routing applies to ALL `REJECTED`/`OBSERVATION && !exec` strategies. If a future REJECTED strategy has no artifact, it will display the amber badge. This is an acceptable conservative choice — artifact exists for all 4 current REJECTED strategies (confirmed by P1 dry-call scan). A future P5 task could add `has_artifact_provenance` to the lifecycle API to make this explicit.
2. `TOMBSTONE_NO_SOURCE` routing applies to ALL `RETIRED && !exec && totalRows === 0` strategies. All 5 current RETIRED strategies confirmed to have no source code (P1). Same caveat applies.
3. `DISPLAY_ONLY` and `MISSING_HISTORY` are retained in badge map for backward-compatibility but are no longer returned by `deriveTruthLevelForStrategy()` under normal operation.

---

**P2_TRUTH_LEVEL_TAXONOMY_V2_COMPLETE**
