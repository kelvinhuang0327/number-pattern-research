# P18 Replay Product Gap Inventory — 2026-05-11

## 1. 本輪目標

整理 lifecycle baseline 與 replay history 可用性之間的 gap，產出 no-write / no-backfill / no-promotion closure summary。

本輪只做 docs / governance，禁止：
- 寫 DB
- replay backfill
- scheduler / cron
- strategy promotion / retire / replay apply
- runtime code、dashboard、endpoint、config 變更

## 2. Main Latest Commit

- branch: `main`
- latest commit: `f318e4b`
- commit message: `docs(replay): P0 governance baseline cleanup report (#47) (#47)`

工作樹狀態在本輪讀取時為 clean，沒有額外 staged 或 unstaged diff。

## 3. 已落地 Artifacts

已確認存在：
- `outputs/replay/p0_governance_baseline_report_20260511.md`
- `outputs/replay/p17_strategy_history_replay_product_roadmap_20260511.md`

這兩份 artifact 已形成本輪 inventory 的前置基線：
- P0 提供 lifecycle baseline、DB dirt root cause、PR queue triage、UI verification。
- P17 提供策略歷史 replay 產品的 gap 定義與 no-write roadmap。

## 4. P0 / P17 Marker Verification

已確認 marker：
- `P0_DB_DIRT_ROOT_CAUSE`
- `P0_PR_QUEUE_FINAL`
- `P1_DASHBOARD_UI_VERIFIED`
- `P1_OFFLINE_DECISION_DRAFT_READY`

P17 roadmap 也已明確指出：
- lifecycle metadata 與 replay row availability 並不等價
- non-ONLINE strategies 目前仍是 honest empty
- no-write / no-backfill 是本產品線的硬約束

## 5. Gap Inventory Summary

### 5.1 Lifecycle metadata 現況

從 registry JSON smoke 讀到：

| lifecycle_status | count | strategy_ids |
|---|---:|---|
| ONLINE | 6 | `biglotto_deviation_2bet`, `biglotto_triple_strike`, `daily539_f4cold`, `daily539_markov_cold`, `power_orthogonal_5bet`, `power_precision_3bet` |
| REJECTED | 4 | `biglotto_ts3_acb_4bet`, `biglotto_ts3_markov_freq_5bet`, `power_shlc_midfreq`, `p1_deviation_2bet_539` |
| OBSERVATION | 1 | `h6_gate_mk20_ew85` |
| RETIRED | 5 | `acb_1bet`, `acb_markov_midfreq`, `acb_markov_midfreq_3bet`, `midfreq_acb_2bet`, `midfreq_fourier_2bet` |

Total lifecycle strategies: `16`

### 5.2 Replay history row availability

From read-only DB queries:

| replay table | rows |
|---|---:|
| `strategy_prediction_replays` | `460` |
| `strategy_replay_runs` | `7` |

Replay rows by strategy:

| strategy_id | replay_status | rows |
|---|---|---:|
| `biglotto_deviation_2bet` | `PREDICTED` | `70` |
| `biglotto_triple_strike` | `PREDICTED` | `70` |
| `daily539_f4cold` | `PREDICTED` | `70` |
| `daily539_f4cold` | `REPLAY_ERROR` | `20` |
| `daily539_markov_cold` | `PREDICTED` | `70` |
| `daily539_markov_cold` | `REPLAY_ERROR` | `20` |
| `power_orthogonal_5bet` | `PREDICTED` | `70` |
| `power_precision_3bet` | `PREDICTED` | `70` |

Run status:

| status | count |
|---|---:|
| `DONE` | `6` |
| `FAILED_LEGACY` | `1` |

### 5.3 Missing-history strategies

Non-ONLINE strategies currently have honest empty replay coverage:

| lifecycle_status | strategy count | replay rows | gap type |
|---|---:|---:|---|
| REJECTED | 4 | 0 | data gap, but expected under current no-write policy |
| OBSERVATION | 1 | 0 | governance gap / not yet canonical replay history |
| RETIRED | 5 | 0 | archival gap, no replay rows preserved in current product path |
| OFFLINE | 0 | 0 | taxonomy supported, but no canonical OFFLINE strategy exists today |

### 5.4 OFFLINE / REJECTED / OBSERVATION / RETIRED coverage

- `OFFLINE`: current canonical count is `0`
- `REJECTED`: lifecycle metadata exists, replay rows do not
- `OBSERVATION`: lifecycle metadata exists, replay rows do not
- `RETIRED`: lifecycle metadata exists, replay rows do not

Interpretation:
- `OFFLINE = 0` is not a defect; it is the current correct registry state.
- The product can display the state filter, but there are no canonical OFFLINE entries to surface yet.
- For non-ONLINE states, the current product is still metadata-first rather than row-first.

## 6. Classification of Gaps

### 6.1 Data gaps

- `REJECTED` / `OBSERVATION` / `RETIRED` strategies have no replay rows in `strategy_prediction_replays`.
- Only 6 `ONLINE` strategies are represented in replay history.
- `OFFLINE` has no canonical strategy entry, so there is nothing to backfill or replay.

### 6.2 UI / dashboard gaps

- UI already supports lifecycle filtering and honest empty state, so the remaining gap is not rendering capability.
- The product still needs a clearer inventory / closure view explaining why some lifecycle states have no replay history.
- The page can show metadata filters, but it should keep saying “no history yet” rather than implying replay parity across states.

### 6.3 Governance / no-write gaps

- No-write policy prevents filling missing replay rows directly in this task.
- No-backfill policy prevents using the gap inventory to trigger row creation.
- No-promotion policy prevents converting lifecycle visibility into actionability.

## 7. No-Write Evidence

Evidence gathered in this session:
- DB queries were executed read-only against `lottery_api/data/lottery_v2.db`.
- No runtime write path was invoked.
- `git status --short` returned clean at the end of verification.
- `git status --short data/lottery_v2.db` returned no tracked diff.
- There was no commit of `data/lottery_v2.db`.
- There was no change to runtime code, dashboard code, endpoint code, scheduler code, or dependency config.

## 8. No-Backfill Evidence

Evidence gathered in this session:
- No replay backfill command was run.
- No apply / promote / populate action was run.
- The existing backfill manifest file was only checked for presence, not regenerated or committed.
- P0 and P17 docs both explicitly preserve the no-backfill rule.

## 9. No-Promotion Evidence

Evidence gathered in this session:
- The roadmap keeps replay history work separate from strategy governance action.
- The endpoint contract explicitly treats replay backfill and strategy promotion as prohibited in this path.
- The current task only inventories the gap; it does not promote, retire, or reactivate any strategy.

## 10. Remaining Local Runtime Dirt

- Tracked worktree: clean at verification time.
- Local presence check: `outputs/replay/p2_lifecycle_backfill_dry_run_manifest_20260510.json` exists locally, but was not modified or committed in this task.
- No other local runtime dirt was introduced by this P18 pass.

## 11. Risks / Limitations

1. Replay history is still incomplete for non-ONLINE lifecycle states.
2. `OFFLINE` is supported in taxonomy and UI, but has no canonical strategy instance yet.
3. The current product can inventory the gap, but cannot close it without a separate no-write catalog or data provenance decision.
4. A naive “complete all states” reading would overclaim product completeness; metadata visibility is already complete enough to expose the gap honestly.

## 12. Next Direction

Recommended next P19 direction:

```text
P19 = no-write replay gap policy + inventory-driven UX closure
```

Focus:
- define how the product should label missing-history states
- decide whether future work should remain display-only or introduce a formal dry-run catalog bridge
- keep replay history honest when metadata exists but rows do not

## 13. Final Markers

P18_REPLAY_PRODUCT_GAP_INVENTORY_REVIEWED
P18_NO_DB_WRITE_NO_BACKFILL_CONFIRMED
P18_NO_PROMOTION_ACTION_CONFIRMED
