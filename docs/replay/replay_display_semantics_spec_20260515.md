# Replay Page Display Semantics Specification

**Document type**: Product Spec — READ ONLY  
**Status**: FROZEN (pending CEO decisions in §B)  
**Date**: 2026-05-15  
**Author**: CEO-dispatched Spec Freeze Lead  
**Scope**: Strategy Historical Replay page — lifecycle display semantics only  
**PR**: docs/replay-display-semantics-spec-20260515  

---

## Context

PR #100 (replay lifecycle drift guard CI) has merged.  
Post-merge drift guard: **PASS**.  
DB baseline locked: V1=300 / V2=200 / legacy=460 / total=960 / V3 tombstone=6/6 zero rows.

This document freezes the **display semantics** for the Replay page before any implementation begins.  
No code, DB, strategy, API, UI, or backend changes are made here.

**Registry snapshot at spec freeze (2026-05-15):**

| Lifecycle Status | Count in Registry |
|------------------|-------------------|
| ONLINE           | 6                 |
| REJECTED         | 4                 |
| RETIRED          | 5                 |
| OBSERVATION      | 1                 |
| OFFLINE          | 0                 |
| **Total canonical** | **16**        |
| V3 CODE_MISSING tombstone (zero rows enforced) | 6 |

---

## A. Lifecycle Display Semantics Matrix

### A.1 ONLINE

> *Deployed and active. Currently generating predictions in the replay pipeline.*

| Field | Value |
|-------|-------|
| **Prediction data source** | Live prediction log (DB: `strategy_prediction_replays`, `truth_level = REGENERATED_RETROSPECTIVE` for historical draws; live for current draws) |
| **Comparison method** | Live diff — predicted numbers vs. actual draw results, per draw |
| **UI trust label** | `LIVE` |
| **Show per-draw × per-strategy rows** | ✅ YES — display each draw row showing predicted vs. actual, hit count, special hit |
| **Forbidden** | Must not display rows from other strategies' apply batches. Must not label any row as `LIVE` when `truth_level` is `RETROSPECTIVE`. Must not mix V3 tombstone strategy rows into ONLINE display. |

**Display behaviour**: Full table view. Show `truth_level` badge per row. Rows with `truth_level = REGENERATED_RETROSPECTIVE` show `[RETROSPECTIVE]` badge; live rows (generated post-deployment) show `[LIVE]` badge.

---

### A.2 OFFLINE

> *Previously deployed, now suspended. Prediction generation is paused; existing rows are preserved in DB.*

| Field | Value |
|-------|-------|
| **Prediction data source** | Historical rows only (DB: `strategy_prediction_replays`, rows from the period the strategy was ONLINE). May include `truth_level = REGENERATED_RETROSPECTIVE` or `null` (legacy). |
| **Comparison method** | Retrospective diff — historical predictions vs. actual results for preserved rows only |
| **UI trust label** | `FROZEN` |
| **Show per-draw × per-strategy rows** | ✅ YES — display historical rows up to the suspension date. No new rows will appear. |
| **Forbidden** | Must not generate new prediction rows for OFFLINE strategies. Must not label rows as `LIVE`. Must not hide the `[FROZEN]` status badge. |

**Display behaviour**: Table view with frozen header banner: *"This strategy is suspended. Data shown is historical only."*. No "predict next draw" action available.

---

### A.3 REJECTED

> *Evaluated during governance review and rejected. Strategy was never deployed to production prediction generation.*

| Field | Value |
|-------|-------|
| **Prediction data source** | V2 retrospective artifact only (if exists: `truth_level = ARTIFACT_RECONSTRUCTED_RETROSPECTIVE`). Tombstone metadata from registry. No live prediction log. |
| **Comparison method** | Retrospective diff (artifact-based) — or N/A if no artifact exists |
| **UI trust label** | `RETROSPECTIVE` (when artifact rows exist) or `NO_DATA` (when no rows exist) |
| **Show per-draw × per-strategy rows** | ⚠️ CONDITIONAL — only if V2 artifact rows exist in DB with `truth_level = ARTIFACT_RECONSTRUCTED_RETROSPECTIVE`. If no rows exist: show `NO_DATA` placeholder. |
| **Forbidden** | **Must NOT label artifact rows as live predictions.** Must NOT display rows without the `[RETROSPECTIVE — Artifact Reconstructed]` badge. Must NOT invoke code generation for rejected strategies. Must NOT add new rows. |

**Display behaviour**: If artifact rows exist, show table with mandatory `[RETROSPECTIVE — Artifact Reconstructed]` per-row badge. If no rows: show tombstone card with rejection reason from registry. Rejection reason from registry metadata must be visible.

**Open CEO decision**: See §B-1.

---

### A.4 RETIRED

> *Formally retired after lifecycle end. Previously deployed; prediction rows preserved in DB.*

| Field | Value |
|-------|-------|
| **Prediction data source** | Historical rows from active deployment period (DB: `strategy_prediction_replays`). May include `truth_level = REGENERATED_RETROSPECTIVE`, `ARTIFACT_RECONSTRUCTED_RETROSPECTIVE`, or `null` (legacy). Registry metadata (retirement reason, retirement date). |
| **Comparison method** | Retrospective diff — historical predictions vs. actual results for the preserved trajectory |
| **UI trust label** | `FROZEN` |
| **Show per-draw × per-strategy rows** | ✅ YES — display historical trajectory up to retirement date. |
| **Forbidden** | Must not generate new rows. Must not label as `LIVE`. Must not hide retirement date / reason. |

**Display behaviour**: Table with frozen header banner: *"This strategy is retired. Data shown is the historical prediction trajectory only."*. Show retirement date and reason from registry metadata.

**Open CEO decision**: See §B-2 (how many periods of history to show).

---

### A.5 OBSERVATION

> *Under shadow evaluation — running in parallel with production but results not used for live output.*

| Field | Value |
|-------|-------|
| **Prediction data source** | Shadow prediction log if available (DB rows with `truth_level = REGENERATED_RETROSPECTIVE` generated during observation window). May have zero rows if observation just started or is metadata-only. Registry metadata. |
| **Comparison method** | Retrospective diff if shadow rows exist; N/A if no rows |
| **UI trust label** | `RETROSPECTIVE` (when shadow rows exist) or `NO_DATA` (when no rows exist) |
| **Show per-draw × per-strategy rows** | ⚠️ CONDITIONAL — only if shadow prediction rows exist. If no rows: show `NO_DATA` placeholder. |
| **Forbidden** | Must not display shadow rows as live predictions. Must not label `[LIVE]`. Must not claim observation results affect live output. |

**Display behaviour**: If rows exist, show table with `[OBSERVATION — Shadow Evaluation]` banner. If no rows: show observation metadata card with `NO_DATA` placeholder and message: *"No prediction rows recorded during observation period."*

**Open CEO decision**: See §B-3 (no-data display: show placeholder vs. hide).

---

### A.6 Summary Matrix

| Lifecycle | Trust Label | Show Rows | Row Badge | No-Data Behaviour | New Rows Allowed |
|-----------|-------------|-----------|-----------|-------------------|-----------------|
| ONLINE | `LIVE` | ✅ Always | `[LIVE]` or `[RETROSPECTIVE]` per row | N/A (always has rows) | ✅ Yes |
| OFFLINE | `FROZEN` | ✅ Historical | `[FROZEN]` header | N/A (rows from active period) | ❌ No |
| REJECTED | `RETROSPECTIVE` / `NO_DATA` | ⚠️ Conditional | `[RETROSPECTIVE — Artifact Reconstructed]` | Show tombstone card + rejection reason | ❌ No |
| RETIRED | `FROZEN` | ✅ Historical | `[FROZEN]` header | N/A (rows from deployment period) | ❌ No |
| OBSERVATION | `RETROSPECTIVE` / `NO_DATA` | ⚠️ Conditional | `[OBSERVATION — Shadow Evaluation]` | Show `NO_DATA` placeholder | ❌ No (shadow only, not production) |

---

## B. CEO Decision Questions

### B-1: REJECTED rows — mandatory RETROSPECTIVE badge at row level?

**Question**: REJECTED 策略的 V2 artifact row，是否在 UI row level 強制標註「事後重現 Retrospective」？

**CTO Recommendation**: **YES — mandatory per-row badge.**  
每個 artifact row 必須顯示 `[RETROSPECTIVE — Artifact Reconstructed]` badge，不允許 section-level 標籤替代。否則使用者無法分辨 row 是否來自真實預測，存在語義欺騙風險。

**Risk**: 若只在 section header 標示而非 per-row，使用者可能截圖單行 row 誤導為 live prediction 紀錄。

*(≤100字)*

---

### B-2: RETIRED 策略顯示多少期歷史預測軌跡？

**Question**: RETIRED 策略在 UI 顯示退役前的最後 N 期預測軌跡，N 應為何值？

**Options**:
- A. 顯示全部（退役前所有 rows）
- B. 最後 30 期
- C. 只顯示 tombstone 卡片（不顯示 rows）

**CTO Recommendation**: **Option A — 顯示全部歷史 rows，預設排序最新在前，加分頁。**  
退役策略的完整軌跡是盤點與審計的核心資產。截斷 30 期會遺失早期 pattern。顯示全部 + 分頁不增加 DB 壓力。

**Risk**: Option C 會讓退役策略完全不可審計，無法支援 CEO 策略全集盤點目標。

*(≤100字)*

---

### B-3: OBSERVATION 策略無 prediction row 時，顯示 "no data" 還是隱藏？

**Question**: OBSERVATION 期間若無 prediction row，UI 應顯示 "no data" placeholder 還是直接隱藏該策略？

**Options**:
- A. 顯示 "no data" placeholder（策略卡片可見，rows 區域顯示提示訊息）
- B. 隱藏（從列表過濾掉）

**CTO Recommendation**: **Option A — 顯示 "no data" placeholder。**  
OBSERVATION 策略的存在本身即是資訊。隱藏會造成策略全集盤點缺口，CEO 無法知道有多少策略在觀測期但尚未有資料。

**Risk**: Option B 造成盤點盲點；一旦 observation 期間結束，未來審計無法溯源「曾有觀測期」。

*(≤100字)*

---

## C. P1 策略全集盤點輸入需求

下一輪 P1 inventory 可直接掃描以下來源，建立完整的 strategy universe：

### C.1 DB Tables

```sql
-- 主要來源
strategy_prediction_replays         -- 所有 replay rows (V1/V2/legacy/V3-tombstone)
strategy_replay_runs                -- replay run metadata

-- 關鍵欄位
strategy_id                         -- strategy identifier
lifecycle_status (from registry)    -- ONLINE/OFFLINE/REJECTED/RETIRED/OBSERVATION
truth_level                         -- REGENERATED_RETROSPECTIVE / ARTIFACT_RECONSTRUCTED_RETROSPECTIVE / NULL
controlled_apply_id                 -- V1: 20260514033100-13acaf34996e / V2: 20260514134953-cf683424
```

**Known DB baseline at spec freeze:**

| Group | controlled_apply_id | truth_level | Count |
|-------|---------------------|-------------|-------|
| V1 | `20260514033100-13acaf34996e` | `REGENERATED_RETROSPECTIVE` | 300 |
| V2 | `20260514134953-cf683424` | `ARTIFACT_RECONSTRUCTED_RETROSPECTIVE` | 200 |
| Legacy | NULL | NULL | 460 |
| V3 tombstone | — | — | 0 (enforced) |

### C.2 Replay Artifact Paths

```
outputs/replay/                          # All replay output artifacts
outputs/replay/replay_lifecycle_drift_guard_ci_baseline_20260514.json
outputs/replay/replay_lifecycle_drift_guard_ci_validation_20260514.json
outputs/replay/replay_lifecycle_drift_guard_post_pr100_20260514.json
outputs/replay/post_v3_release_completion_summary_20260514.md
outputs/replay/p6_lite_preapply_snapshot_20260514.md
outputs/relay/                           # Note: typo in existing path (relay vs replay)
```

### C.3 Prediction Log Paths

```
lottery_api/data/lottery_v2.db           # Primary DB
lottery_api/data/                        # All data files
data/lottery_v2.db                       # Repo root data copy (may be stale)
```

### C.4 Registry / Catalog Files

```
lottery_api/models/replay_strategy_registry.py   # Primary registry (16 canonical strategies)
scripts/p1_replay_truth_executable_inventory.py  # Inventory script
scripts/replay_lifecycle_drift_guard.py          # V3 tombstone list (6 strategy IDs)
```

**V3 CODE_MISSING tombstone strategy IDs** (must have 0 DB rows):
```
acb_1bet
acb_markov_midfreq
acb_markov_midfreq_3bet
midfreq_acb_2bet
midfreq_fourier_2bet
h6_gate_mk20_ew85
```

### C.5 outputs/replay Existing Artifacts to Cross-Reference

```
outputs/replay/p59_code_vs_registry_crosscheck_20260512.md
outputs/replay/p59_replay_truth_quality_coordination_final_report_20260512.md
outputs/replay/p59_truth_taxonomy_d6_regenerated_retrospective_20260512.md
outputs/replay/p60_ui_truth_level_parity_scope_lock_20260512.md
docs/replay/strategy_lifecycle_endpoint_contract.md
docs/replay/strategy_lifecycle_live_smoke_decision.md
docs/replay/strategy_historical_replay_roadmap_20260515.md
```

### C.6 Repo Strategy File Search Rules

To enumerate non-canonical strategies (beyond registry's 16):

```bash
# Search for strategy-like Python files
find lottery_api/ -name "strategy_*.py" -o -name "*_strategy.py"
find scripts/ -name "*strategy*" -o -name "*predict*" -o -name "*replay*"

# Search for strategy class definitions
grep -rn "class.*Strategy\|def generate_prediction\|def predict" lottery_api/ --include="*.py"

# Search for JSON strategy catalogs / rejected logs
find . -name "rejected_*.json" -o -name "strategy_catalog*.json" -o -name "*.strategy.json"

# Check backtest result files for unreferenced strategy IDs
find . -name "backtest_*.json" | xargs grep -l "strategy_id" 2>/dev/null
```

---

## D. Non-Goals

The following are **explicitly out of scope** for this spec and any implementation derived from it:

| Non-Goal | Reason |
|----------|--------|
| Do not add new strategies | Strategy universe is frozen; new strategies require separate governance |
| Do not add / backfill replay rows | DB baseline is locked at V1=300/V2=200/legacy=460/total=960 |
| Do not write to DB | Read-only display spec; no persistence changes |
| Do not modify API / routes | No changes to `lottery_api/routes/replay.py` or any backend |
| Do not modify UI / frontend | Display semantics spec only; UI implementation is a separate PR |
| Do not modify replay_strategy_registry.py | Registry is frozen for this spec cycle |
| Do not run backtest | No strategy evaluation; this is a display spec |
| Do not label retrospective rows as live predictions | Core integrity rule; violation = spec breach |
| Do not force-push or bypass branch protection | Repo governance rules apply |
| Do not commit .db / .sqlite / .pid / runtime artifacts | Clean repo policy |

---

## E. Acceptance Criteria

This document is accepted when all of the following are true:

| Criterion | Status |
|-----------|--------|
| All 5 lifecycle statuses have explicit display semantics defined | ✅ Defined in §A |
| REJECTED semantics are unambiguous (artifact vs. live, badge mandatory) | ✅ §A.3 + §B-1 |
| RETIRED semantics are unambiguous (frozen historical, no new rows) | ✅ §A.4 + §B-2 |
| OBSERVATION semantics are unambiguous (shadow, conditional rows, no-data handling) | ✅ §A.5 + §B-3 |
| 3 CEO decision questions are written and actionable | ✅ §B-1, §B-2, §B-3 |
| P1 inventory can start directly from this document | ✅ §C lists all scan sources |
| No DB diff in this PR | ✅ docs-only change |
| No code diff in this PR | ✅ docs-only change |
| No strategy diff in this PR | ✅ docs-only change |
| Retrospective rows never labeled as live predictions | ✅ enforced in §A forbidden rules |
| V3 tombstone display rule explicit | ✅ zero rows → tombstone card, no row table |

---

## F. V3 Tombstone Display Rule (Appendix)

V3 CODE_MISSING strategies (6 total) have **zero rows in DB by design**.

Display rule:
- Do NOT render a prediction row table for these strategies.
- Render a tombstone card showing:
  - Strategy ID
  - Classification: `CODE_MISSING`
  - Message: *"This strategy's implementation code is not available. No prediction rows exist."*
  - Trust label: `NO_DATA`

This rule is enforced by the drift guard (PR #100). Any V3 tombstone strategy appearing with DB rows is a `DRIFT_VIOLATION`.

---

## G. Glossary

| Term | Definition |
|------|------------|
| `LIVE` | Prediction generated at draw time by active strategy code |
| `RETROSPECTIVE` | Prediction regenerated or reconstructed after the draw date |
| `FROZEN` | Strategy is inactive; existing rows are read-only |
| `NO_DATA` | No prediction rows exist for this strategy in the relevant period |
| `REGENERATED_RETROSPECTIVE` | V1 truth_level: code re-ran on historical draws retrospectively |
| `ARTIFACT_RECONSTRUCTED_RETROSPECTIVE` | V2 truth_level: reconstructed from saved artifact, no live code run |
| `CODE_MISSING` | V3 classification: strategy code unavailable; zero DB rows enforced |
| Tombstone | Registry entry for a V3 strategy with zero rows; metadata-only |
| Drift Guard | CI script (PR #100) enforcing DB baseline row counts and V3 zero-row invariant |
