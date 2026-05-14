# Replay Lifecycle Drift Guard CI — Rollout Document

**Date:** 2026-05-14  
**Classification:** REPLAY_LIFECYCLE_DRIFT_GUARD_CI_PR_READY  
**Relation to release:** Post-V3 replay lifecycle release tag `post-v3-replay-lifecycle-release-20260514`  
**Merged PRs:** #97 (2ff4422) · #98 (2bb6289) · #99 (d158696)

---

## 1. Purpose

This CI lane provides a **scheduled and manually-triggered read-only drift guard**
for the `strategy_prediction_replays` table. It verifies that the replay row
distribution has not drifted from the Post-V3 baseline established on 2026-05-14:

| Segment | `controlled_apply_id` | Expected count |
|---------|----------------------|---------------|
| V1 | `20260514033100-13acaf34996e` | 300 |
| V2 | `20260514134953-cf683424` | 200 |
| Legacy | `NULL` | 460 |
| **Total** | — | **960** |

Additional invariants checked on every run:
- All 6 known V3 `CODE_MISSING` tombstone strategy IDs have **0 rows** in the table.
- `truth_level` column contains only values from the allowed enum (or NULL).
- `controlled_apply_id` distribution matches the baseline exactly.

---

## 2. Schedule

The workflow runs **nightly at 02:00 UTC** via the GitHub Actions scheduler:

```yaml
schedule:
  - cron: "0 2 * * *"
```

---

## 3. Manual Trigger Command

Trigger a one-off run from the CLI:

```bash
gh workflow run replay-lifecycle-drift-guard.yml --repo <owner>/<repo>
```

Or from the GitHub UI: **Actions → replay-lifecycle-drift-guard → Run workflow**.

---

## 4. PASS Criteria

The run is considered PASS when **all** of the following hold:

1. `python3 -m py_compile scripts/replay_lifecycle_drift_guard.py` exits **0**
2. `python3 scripts/replay_lifecycle_drift_guard.py --strict --json-out ...` exits **0**
3. JSON output contains `"status": "PASS"` and `"final_classification": "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS"`
4. `python3 -m json.tool` confirms the JSON is well-formed (exits **0**)
5. `pytest tests/test_replay_lifecycle_drift_guard.py -q --tb=short` reports **all tests PASS** (exit 0)

---

## 5. FAIL Handling

If any step exits non-zero:

1. GitHub Actions marks the workflow run as **FAILED** (red ✗).
2. Download the artifact `replay-lifecycle-drift-guard-ci-<run_id>` and inspect the JSON `violations` array for the exact drift description.
3. **Do not** manually patch DB rows without explicit governance approval.
4. Open a triage issue referencing the violated invariant and the `violations` array from the JSON.
5. Resolution requires a new PR with explicit human sign-off; do not auto-merge.

---

## 6. Why V3 `CODE_MISSING` → 0 rows is expected

Post-V3 release audit identified 6 strategies whose code was permanently removed
(`CODE_MISSING` classification):

```
acb_1bet
acb_markov_midfreq
acb_markov_midfreq_3bet
midfreq_acb_2bet
midfreq_fourier_2bet
h6_gate_mk20_ew85
```

These strategy IDs were **tombstoned** during the Post-V3 closure. They were
never applied to the replay table (V1 and V2 apply operations deliberately
excluded them). Their presence in `strategy_prediction_replays` with **any** row
count would indicate a rogue apply operation and is treated as a critical violation.

The drift guard asserts `COUNT(*) == 0` for each tombstone strategy ID on every run.

---

## 7. Why legacy `NULL` rows are allowed

The 460 legacy rows pre-date the `controlled_apply_id` column introduction. They
were written before V1/V2 apply operations and have:
- `controlled_apply_id IS NULL`
- `truth_level IS NULL`

This is the expected state for legacy data. The guard verifies the count is
**exactly 460** (not zero, not more, not fewer). Any deviation signals unexpected
legacy row deletion or addition.

---

## 8. Forbidden Actions

The following actions are **strictly forbidden** in this lane and any associated workflows:

| Action | Reason |
|--------|--------|
| DB writes to production `lottery_api/data/lottery_v2.db` | Read-only guard |
| Applying new replay rows | Governance boundary |
| Starting the backend/API server | Not required, adds side effects |
| Strategy mining | Out of scope |
| Modifying `replay_strategy_registry.py` semantics | Registry is frozen post-V3 |
| Committing `.db` / `.sqlite` / `.pid` / runtime logs | Artifact pollution |
| Force-pushing | Destructive history rewrite |
| Auto-merging without explicit user authorization | Human sign-off required |

The CI fixture built during the workflow run is **synthetic and ephemeral** — it
lives only in the GitHub Actions runner workspace and is never committed.

---

## 9. Relation to Post-V3 Release Tag

This CI lane is the **operational continuity mechanism** for the Post-V3 release closure.

Timeline:

| Event | Commit / Tag |
|-------|-------------|
| PR #97 merged (truth-level API contract) | `2ff4422` |
| PR #98 merged (release tag closure docs) | `2bb6289` |
| PR #99 merged (drift guard baseline) | `d158696` |
| Release tag pushed | `post-v3-replay-lifecycle-release-20260514` |
| **This PR** (CI monitoring lane) | `chore/replay-lifecycle-drift-guard-ci-20260514` |

The release tag `post-v3-replay-lifecycle-release-20260514` is the immutable
snapshot of the Post-V3 state. This CI lane watches over that snapshot going
forward. Any drift detected by this guard should be treated as a regression
against the baseline enshrined in that release tag.

---

## 10. Last Known Validated State

```
Drift guard:  PASS  (0 violations)
API regression:  16/16 PASS
pytest suite:  87/87 PASS
Baseline:  V1=300  V2=200  legacy=460  total=960
V3 tombstone strategies:  0 rows each (6/6)
truth_level enum:  clean (REGENERATED / ARTIFACT_RECONSTRUCTED / NULL only)
```
