# P230A — DAILY_539 Survivor Backward-OOS Extension Plan & Rehearsal Design

**Date:** 2026-06-03 (Asia/Taipei)
**Task:** `P230A_DAILY539_SURVIVOR_BACKWARD_OOS_EXTENSION_PLAN_AND_REHEARSAL_DESIGN`
**Status:** COMPLETE / PLAN-ONLY / READ-ONLY
**Classification:** `P230A_DAILY539_BACKWARD_OOS_EXTENSION_PLAN_READY`
**Authorized by:** User explicit task prompt 2026-06-03

> **Plan-only.** No DB write, no replay rows created, no registry change, no production / recommendation change, no P225 start, and **no backward replay generation executed**. This document is design + rehearsal architecture only. It is **not betting advice** and **not** a guaranteed predictive edge.
>
> **Branch note:** A repo `PreToolUse` hook blocks file writes on `main` (`⚠️ 無法在 main 分支直接編輯，請切換到開發分支`). The two P230A artifacts were therefore written on branch `p230a-daily539-backward-oos-extension-plan`, **user-authorized for this write only**. No commit / stage / push performed.

---

## 1. Phase 0 Verification — all checks PASS

| Check | Expected | Actual | Result |
|---|---|---|---|
| `git rev-parse --show-toplevel` | repo root | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` | ✅ |
| branch (at verification) | `main` | `main` | ✅ |
| `git rev-parse --git-dir` | `.git` | `.git` | ✅ |
| `HEAD` | = origin/main, includes P229 | `3b9933b…272403` | ✅ |
| `origin/main` | = HEAD | `3b9933b…272403` | ✅ |
| HEAD == origin/main | true | true | ✅ |
| staged files | 0 | 0 | ✅ |
| replay rows (total) | 94924 | 94924 | ✅ |
| DAILY_539 replay rows (all strategies) | 34680 | 34680 | ✅ |
| `bet_index` nulls | 0 | 0 | ✅ |
| duplicate replay keys | 0 | 0 | ✅ |
| `PRAGMA integrity_check` | ok | ok | ✅ |
| drift guard | PASS | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` | ✅ |
| P229 closeout artifacts tracked | tracked | `.md` + `.json` TRACKED | ✅ |

No STOP condition triggered. Pre-existing unrelated dirty/untracked files were left untouched (not staged, not cleaned).

---

## 2. Candidate Recap

| Field | Value |
|---|---|
| strategy_id | `midfreq_fourier_2bet` |
| lottery_type | `DAILY_539` |
| status | **WAIT_FOR_OOS** |
| P224 classification | `P224_SURVIVOR_NEEDS_MORE_OOS` |
| existing rows | 1500 (all `replay_status=PREDICTED`) |
| bet_index values | `1` only |
| replay_run_id | `p31b_wave1_prod_20260523` |
| controlled_apply_id | `P31B_DAILY539_RETIRED_7500_PROD_20260523` |
| source | `P31B_WAVE1_PRODUCTION_APPLY` |
| truth_level | `DAILY539_RETIRED_STRATEGY_BACKFILL_VERIFIED` |
| lifecycle_status | RETIRED (not ONLINE; not in production registry `_ALL_ADAPTERS`) |
| P225 | deferred; separately authorized only |

> **Important semantics:** Only **bet-1** is recorded. In code, bet-1 of `midfreq_fourier_2bet` is **pure MidFreq** (`predict_midfreq`), *not* Fourier — the "fourier" component would be bet-2 and is **never stored**. So the replay evidence is effectively a **single-bet MidFreq signal** despite the `2bet` name. Any backward extension reproduces this same bet-1 MidFreq signal.

---

## 3. Current Evidence Recap (from P224, unchanged)

| Metric | Value |
|---|---:|
| mean hit_count | `0.6693333333333333` |
| baseline used | `0.6410256410256411` |
| 95% CI | `[0.6322371303354622, 0.7064295363312044]` (crosses baseline) |
| one-sided p vs baseline | `0.0673719479414372` (fails 0.05) |
| all-history reference baseline | `0.6251612903225806` |
| w100 / w500 baseline | `0.6096774` / `0.6470968` |
| consensus baseline | `0.68` |
| best competing (`daily539_f4cold`) | `0.678616` |
| M1+ / M2+ / M3+ | `0.524` / `0.13267` / `0.01267` |
| blocks above baseline | `6 / 10` (worst `0.5867`, best `0.76`) |
| 2024 | `0.6146` (below baseline) |
| exclude 19 hit=3 rows | mean `0.6394328` → **below baseline** |

> Baseline derivation: theoretical random hypergeometric mean = `pick(5) × draw(5) / pool(39) = 25/39 = 0.6410256…`, **era-invariant** for DAILY_539 (pool/pick/draw never changed). This is convenient for backward-OOS: the same theoretical anchor applies to every historical era.
>
> **Net:** real survivor, but **not deployable** and **not ready for P225** — edge is weak, CI crosses baseline, and it rests on 19 `hit=3` rows.

---

## 4. Backward-OOS Data Inventory (actual DB counts)

Full DAILY_539 history lives in the `draws` table: **5876** draws, `96000001` (2007/01/01) → `115000132` (2026/05/30).

**Partition of full history relative to the candidate's 1500-row window:**

| Segment | Count | Draw-ID range | Date range |
|---|---:|---|---|
| **Backward** (strictly earlier than window) | **4365** | `96000001`–`110000189` | 2007/01/01 – 2021/08/09 |
| In-window (already replayed, contiguous, **0 gaps**) | 1500 | `110000190`–`115000121` | 2021/08/10 – 2026/05/18 |
| Forward (later than window) | 11 | `115000122`–`115000132` | 2026/05/19 – 2026/05/30 |
| **Sum** | **5876** | — | (4365 + 1500 + 11 = 5876 ✅) |

**Warmup (cannot be replayed):** the first **100** draws (`96000001`–`96000100`) have `<100` prior history (`min_history=100`) → would be `INSUFFICIENT_HISTORY`.

**➡ Replayable backward-OOS = 4265 draws** (ordinals #101–#4365):
- first replayable: `96000101` @ 2007/05/21
- last backward: `110000189` @ 2021/08/09
- span: ~14.2 years (2007/05 → 2021/08)

**Reconciliation of the cited "~4,376 un-replayed older draws":**
`un-replayed = 4365 backward + 11 forward = 4376` (exact). The truly-backward count is **4365**; after the 100-draw warmup the **replayable** backward count is **4265** (not 4376). The "~4,376" figure folded in the 11 forward draws.

**Note on the 34,680 figure:** those DAILY_539 replay rows span *many* strategies; the candidate `midfreq_fourier_2bet` has exactly **1500** rows and currently **0** backward rows — the backfill target is clean.

**Proposed era split (replayable backward, ~balanced):**

| Era | ~Draws | Note |
|---|---:|---|
| Early 2007/05–2011 | 1258 | 2007 partial (161 after warmup) + 2008–2011 |
| Middle 2012–2016 | 1566 | |
| Late / pre-P224-boundary 2017–2021/08 | 1441 | ends at `110000189`, immediately before window boundary `110000190` |
| **Sum** | **4265** | ✅ |

**Draw-order validation:** ordering `date ASC, CAST(draw AS INTEGER) ASC` has **0 date inversions** → `CAST(draw AS INTEGER)` order is perfectly monotonic with date. Leakage-safe chronological ordering is confirmed. (Never use string `ORDER BY draw` — project DB rule.)

---

## 5. Feasibility Analysis

**Can existing code generate backward predictions? YES.**

| Item | Detail |
|---|---|
| Strategy adapter | `lottery_api/models/p31a_wave1_retired_adapters.py :: MidfreqFourier2BetAdapter` (`min_history=100`; `_predict → predict_midfreq`; `predict_midfreq → _midfreq_scores` window=100) |
| Generator template | `scripts/p31b_wave1_daily539_retired_production_apply.py` (causal-slice loop, single-draw runner `_run_one_prediction`, provenance hashing, transactional apply) |
| Registry safety | The adapter is a P31A **dry-run wrapper**, NOT in `replay_strategy_registry._ALL_ADAPTERS` → reusable with no registry side-effects |
| DB tables **read** | `draws` |
| DB tables **write** (future P230B only) | `strategy_prediction_replays` |

**Feature reconstruction without leakage — feasible.** `predict_midfreq` is pure-functional on `history[-100:]` (frequency mean-reversion). It reads **no external state** (DB/files/env) during prediction → deterministic → reproducible → leakage-free when `history` is a strict causal slice. Constraint: needs ≥100 prior draws ⇒ first 100 draws excluded ⇒ effective backward window = **4265**.

**Determinism / provenance:** same algorithm + fixed historical data ⇒ byte-stable predictions; `provenance_hash = sha256("strategy_id|target_draw|sorted(numbers)")[:16]`. Identical to the adapter that produced the 1500 in-window rows.

**Isolation preference:** **artifact-only dry-run first (no DB)** → then, only if authorized, temp-table / backup-DB rehearsal → production apply last and only with explicit DB-write authorization. Precedent for isolated rehearsal exists: `outputs/research/power_lotto/p184_rehearsal/…`, `…/p185_rehearsal/…`, and backup `backups/p188_lottery_v2_backup_20260601_153821.db`.

---

## 6. Leakage Guard

- **Cutoff rule:** `history_cutoff_draw` = the **immediately preceding** DAILY_539 draw of `target_draw` in `(date ASC, draw ASC)` ordinal order.
- **⚠ "target_draw − 1" must mean ORDINAL PREDECESSOR, not numeric subtraction.** DAILY_539 draw IDs reset across ROC-year boundaries (e.g. `110000313 → 111000001`), so numeric `target_draw-1` is **wrong** at year boundaries. Use `history = all_draws[:target_idx]; cutoff = history[-1]['draw']` — exactly what P31B already does.
- **No same-draw / future outcome:** history is `all_draws[:target_idx]` (strictly before target); `actual_numbers` comes only from the target row and is never fed into prediction.
- **Draw-order validation:** assert 0 date inversions under integer order before any run (verified now: 0).
- **Duplicate target protection:** `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`; pre-run guard asserts 0 existing backward rows for this `strategy_id`.
- **Post-generation assertions:** `cutoff_ordinal ≥ target_ordinal` count = 0; `prediction_cutoff_date ≥ target_date` count = 0; rows = distinct target_draw; every bet = exactly 5 distinct ints in `[1..39]`; `predicted_special` is NULL.
- **Unique-key strategy (if DB write authorized):** reuse the existing UNIQUE key; backward rows differ only by `target_draw`, so no collision with the 1500 in-window rows.
- **Rollback / backup (if DB write authorized):** full timestamped backup first → pre-flight assert total = 94924 → `BEGIN EXCLUSIVE` + rollback on any exception → post assert total = 94924 + inserted, inserted = expected, duplicates = 0 → drift guard `--strict` must remain PASS.

---

## 7. Proposed Dry-Run / Backfill Architecture

**Principle:** artifact-only before any DB write; deterministic reuse of the existing adapter; full provenance separability of backward rows from in-window rows.

1. **P230B1 — artifact-only dry-run** *(requires code-change authorization; ZERO DB writes)*
   - New read-only script: `scripts/p230b1_daily539_backward_oos_artifact_dryrun.py`
   - Reads `draws` (DAILY_539, ordered); reuses `MidfreqFourier2BetAdapter` + P31B causal-slice loop.
   - Writes only `outputs/research/p230b1_daily539_backward_oos_artifact_<date>.jsonl` + `…_manifest_<date>.json` (counts, hashes, leakage assertions).
   - Expected: exactly **4265** PREDICTED records (recommend skipping the 100 warmup draws).
2. **P230C — validation** *(read-only; no production write)* → `outputs/research/p230c_daily539_backward_oos_validation_<date>.{md,json}`.
3. **P230B2 — temp-table / backup-DB rehearsal** *(requires explicit DB-write authorization)* — load into an **isolated temp DB copy** (P184/P185 precedent) or a temp table with `dry_run=1`; mirror P31B guards (pre-flight count, duplicate guard by `controlled_apply_id`, `BEGIN EXCLUSIVE`, rollback, post verification, drift guard).
4. **P230D — governance & commit** *(separate authorization)*. **Production apply (`dry_run=0` into `lottery_v2.db`) is OUT OF SCOPE** for the whole chain unless a distinct explicit DB-write/backfill authorization is given.

**Provenance separability (proposed markers, distinct from P31B):** `replay_run_id=p230b_backward_oos_<date>`, `controlled_apply_id=P230B_DAILY539_BACKWARD_OOS_<N>_<MODE>_<date>`, `source=P230B_DAILY539_BACKWARD_OOS_EXTENSION`, `truth_level=DAILY539_BACKWARD_OOS_EXTENSION` — so analysis can always separate backward-OOS rows from the original 1500.

---

## 8. Validation Metrics & Gates

> **Caveat:** Backward-OOS is a **historical extension across older regimes**, **not true future OOS**. It tests robustness across earlier regimes but **cannot replace** the P224B future 300/500-draw monitoring gate.

- **Required splits:** early era (2007/05–2011), middle era (2012–2016), late/pre-P224-boundary era (2017–2021/08), and non-overlapping **100/150/300-draw blocks**.
- **Comparison baselines:** P224 theoretical baseline `0.6410256` (era-invariant primary anchor); all-history reference `0.6251613`; `daily539_f4cold` (needs its own backward replay for a fair comparison); consensus `0.68` (reconstructable only if competing strategies are also backfilled backward).
- **Required metrics:** mean hit_count, M1+, M2+, M3+, 95% CI (explicit bounds), one-sided p-value, per-era + per-block stability, robustness excluding `hit_count=3` rows, robustness excluding the strongest block.

**Decision gates for P230B / P230C:**

| Backward-OOS outcome | Action |
|---|---|
| Below baseline | Classify survivor as **historical artifact** |
| Mixed | Keep **WAIT_FOR_OOS**; do **not** start P225 |
| Above baseline but CI/p weak | Keep **NEEDS_MORE_OOS** |
| Above baseline + block-stable + robust (hit=3 & strongest-block removal) + competitive | CTO **may** consider P230C deeper validation |
| Any pass | **Hard ceiling:** no production promotion; P225 remains separately authorized only |

---

## 9. Authorization Matrix

| Action | Status |
|---|---|
| Read-only inventory (this task) | ✅ ALLOWED |
| Artifact-only dry-run (P230B1) | ⛔ NOT YET — needs separate **code-change** authorization (no DB write) |
| DB write / backfill (P230B2 / production) | ⛔ NOT AUTHORIZED — needs explicit **"YES DB write/backfill"** |
| Registry mutation | ⛔ NOT AUTHORIZED |
| Production / recommendation change | ⛔ NOT AUTHORIZED |
| P225 model design | ⛔ NOT AUTHORIZED (separate only) |
| Branch creation (this artifact write) | ✅ user-authorized **for this write only** |
| Commit / stage / push / merge | ⛔ NOT AUTHORIZED |

---

## 10. Recommended Next Step

1. **Authorize P230B1** — a new **read-only** artifact dry-run generator emitting backward-OOS predictions for the **4265** replayable draws to an artifact file, with full leakage assertions and provenance, **zero DB rows**.
2. Then **P230C** read-only validation on that artifact against the era/block splits and gates above.
3. **Defer P230B2** (temp/backup rehearsal) until after P230B1 review **and** explicit DB-write authorization. Production apply (`dry_run=0`) stays out of scope pending a distinct explicit DB-write/backfill authorization.
4. **Parallel reminder:** backward-OOS does **not** substitute for the P224B future-OOS gate (≥300, preferred 500, **new** DAILY_539 draws); passive monitoring continues regardless.

*If a future production apply is ever separately authorized:* DB effect would be `94924 → up to 99189` rows (`+4265`).

---

## 11. Final Classification

### `P230A_DAILY539_BACKWARD_OOS_EXTENSION_PLAN_READY`

**Rationale:** data sufficient (**4265** replayable backward draws ≫ 0), schema intact and supportive (UNIQUE key present, `dry_run` flag, full provenance columns, integrity ok), code feasibility confirmed (adapter + generator template reusable, deterministic, leakage-safe), no blockers. Therefore **not** `BLOCKED_INSUFFICIENT_DATA`, **not** `BLOCKED_SCHEMA`, **not** `BLOCKED`.
