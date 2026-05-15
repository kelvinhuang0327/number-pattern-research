# Strategy Historical Replay Roadmap

**Date:** 2026-05-12  
**Owner:** CTO agent  
**Status:** Recalibrated after P56 merge and P58 truth-taxonomy gate review  
**Current remote main:** `09fa775`  
**Primary objective:** launch a trustworthy strategy historical replay page for every canonical system-developed strategy.

---

## 1. Clarified Product Goal

The product goal is not only lifecycle visibility. The operator must be able to review strategy history with the same practical table shape as the existing historical prediction list.

The page should support:

1. all canonical lifecycle states: `ONLINE`, `OFFLINE`, `REJECTED`, `OBSERVATION`, `RETIRED`;
2. every canonical system-developed strategy currently registered by governance;
3. per-draw predicted-vs-actual comparisons whenever true replay rows exist;
4. explicit truth labels when rows do not exist or are synthetic;
5. no hidden mutation, no strategy mining, no betting recommendation, no edge claim.

---

## 2. Current Implementation Progress

Completed:

| Area | State |
|---|---|
| Replay page shell | Exists in `index.html` with lifecycle, lottery, strategy, status, date filters, table, pagination, and detail rows |
| Lifecycle taxonomy | `ONLINE`, `OFFLINE`, `REJECTED`, `OBSERVATION`, `RETIRED` supported by current `origin/main` registry/API |
| All-lifecycle catalog visibility | Phase A complete for 16 canonical strategies |
| Display-only catalog mode | Non-ONLINE strategies can be shown safely without pretending they have replay rows |
| P56 coverage manifest | Merged by PR #82 at `09fa775` |
| Truth taxonomy memo | PR #83 open, mergeable, clean, 2 pass + 1 skip |
| ONLINE production rows | 6 ONLINE strategies have DB replay rows |
| Safety stance | No production DB write, no backfill, no mining authorized |

Not complete against the full product goal:

| Gap | Current Fact | Product Impact |
|---|---|---|
| Non-ONLINE prediction-vs-actual rows | 0 production rows for REJECTED / RETIRED / OBSERVATION | These can only be display-only or tombstone states today |
| DAILY_539 row quality | 40 `REPLAY_ERROR` rows across 2 ONLINE strategies | ONLINE coverage is not clean; errors must be shown and diagnosed |
| RETIRED strategy history | 5 RETIRED strategies are `NOT_RECONSTRUCTABLE` in P56 | Use tombstone/MISSING_HISTORY unless registry cleanup is approved |
| H6 evidence | `h6_gate_mk20_ew85` evidence remains external-only | OBSERVATION display needs repo-backed evidence if accepted |
| OFFLINE scope | 0 OFFLINE canonical entries | Keep OFFLINE as empty/coming-soon until real candidates exist |
| Local workspace authority | Current branch is dirty/divergent from `origin/main` | Use fresh main/clean worktree for implementation |

---

## 3. Evidence Snapshot

P56 merged manifest:

| Metric | Value |
|---|---:|
| Registered strategies | 16 |
| ONLINE | 6 |
| REJECTED | 4 |
| RETIRED | 5 |
| OBSERVATION | 1 |
| OFFLINE | 0 |
| `strategy_prediction_replays` total rows | 460 |
| `PREDICTED` rows | 420 |
| `REPLAY_ERROR` rows | 40 |
| Strategies with production replay rows | 6 ONLINE only |
| Non-ONLINE strategies with replay rows | 0 |

Truth-level distribution:

| Truth Level | Count | UI Treatment |
|---|---:|---|
| `PRODUCTION_REPLAY` | 6 | Full prediction-vs-actual rows |
| `DISPLAY_ONLY` | 5 | Lifecycle/evidence metadata only |
| `MISSING_HISTORY` | 5 | Tombstone or suppress, pending D4 |
| `REGENERATED_RETROSPECTIVE` | 0 | Future-only, must never be mislabeled as production history |
| `FIXTURE_ONLY` | synthetic | Acceptance/demo lane only |

Replay rows by strategy:

| Strategy | Lifecycle | Rows | PREDICTED | REPLAY_ERROR |
|---|---|---:|---:|---:|
| `biglotto_deviation_2bet` | ONLINE | 70 | 70 | 0 |
| `biglotto_triple_strike` | ONLINE | 70 | 70 | 0 |
| `daily539_f4cold` | ONLINE | 90 | 70 | 20 |
| `daily539_markov_cold` | ONLINE | 90 | 70 | 20 |
| `power_orthogonal_5bet` | ONLINE | 70 | 70 | 0 |
| `power_precision_3bet` | ONLINE | 70 | 70 | 0 |

---

## 4. Roadmap Alignment Decision

P25 remains closed as:

> Phase A: all-lifecycle visibility and display-only catalog safety.

P56/P58 move the project into:

> Phase B: replay truth taxonomy, row-quality repair, and truth-level UI parity.

Therefore the old next step "generate all-lifecycle coverage manifest" is complete. The current next steps are:

1. close truth taxonomy decisions through PR #83 or explicit CTO D1-D5 response;
2. diagnose DAILY_539 `REPLAY_ERROR` rows;
3. implement UI truth-level parity using the accepted taxonomy.

---

## 5. Reordered P0-P10 Roadmap

| Priority | Phase | Focus | Acceptance Criteria | Gate |
|---|---|---|---|---|
| P0 | Decision closure | Accept truth taxonomy decisions D1-D5 | PR #83 merged or D1-D5 recorded: show `REPLAY_ERROR`; tombstone MISSING_HISTORY; h6 evidence future PR; DAILY_539 errors P1 | `YES merge PR #83` or CTO decision |
| P1 | Row quality | Investigate DAILY_539 40 `REPLAY_ERROR` rows | Root cause report identifies draw/run/error pattern and whether adapter fix is possible; DB unchanged | `YES investigate DAILY_539 REPLAY_ERROR root cause` |
| P2 | UI truth parity | Render all truth levels safely in the replay table/catalog | Same table pattern; clear badges for `PRODUCTION_REPLAY`, `DISPLAY_ONLY`, `MISSING_HISTORY`, `FIXTURE_ONLY`; no hidden errors | Frontend PR |
| P3 | H6 evidence | Commit h6 evidence as read-only artifact | OBSERVATION strategy has repo-backed evidence link; registry unchanged | `YES commit h6 evidence artifact` |
| P4 | Historical prediction inventory | Search true historical prediction logs before regeneration | Import-only candidates identified; existing logs mapped to strategy IDs; no adapter execution | No-write report |
| P5 | Dry-run retrospective plan | Produce candidate manifest only for safe regeneratable/importable strategies | Candidate rows include truth level, hashes, blocked reasons, `runtime_write_allowed=false` | Separate YES |
| P6 | Storage decision | Choose production DB vs separate evidence store vs artifact-only | Schema, rollback, labeling, SOP approved | CTO YES |
| P7 | Controlled apply | Apply retrospective/evidence rows only if approved | Snapshot, transaction log, row counts, rollback test, browser smoke | Explicit apply YES |
| P8 | Operator hardening | Runbook and SOP | Startup, DB dirty handling, truth-level reading guide, screenshots | Docs PR |
| P9 | OFFLINE policy | Keep deferred until real candidates exist | OFFLINE entries require owner, transition rules, lottery type, and no false rows | Deferred |
| P10 | Strategy growth | Mining / promotion / lifecycle changes | Only after replay truth surface is stable | Separate research YES |

---

## 6. Key Blockers

| Blocker | Severity | Resolution Path |
|---|---|---|
| 40 DAILY_539 `REPLAY_ERROR` rows | HIGH | P1 read-only investigation, then adapter/report fix if safe |
| Non-ONLINE rows are absent | HIGH | Keep display-only/tombstone until provenance supports import/regeneration |
| RETIRED histories are not reconstructable | HIGH | Tombstone UI or separate registry cleanup decision |
| P57/PR #83 decision not closed | MEDIUM | Merge PR #83 or record D1-D5 choices |
| h6 evidence external-only | MEDIUM | YES-gated evidence artifact PR |
| Dirty/divergent workspace | HIGH | Use `origin/main` or clean worktree for implementation |
| OFFLINE has 0 strategies | LOW | Honest empty state; do not invent entries |

---

## 7. Most Valuable System Optimization

The highest-value optimization is **Replay Truth Quality**:

- finish taxonomy decision;
- diagnose current error rows;
- make the UI impossible to misread.

This is more valuable than strategy mining because the operator's trust depends on knowing whether a row is production replay, generated retrospective, fixture-only, display-only, or missing history. The system should not add more strategies until the existing strategy history surface is truthful and stable.

---

## 8. Recommended Next Commands

Preferred next step:

```text
YES merge PR #83.
```

Then:

```text
YES investigate DAILY_539 REPLAY_ERROR root cause.
```

Optional evidence cleanup:

```text
YES commit h6 evidence artifact.
```

---

## 9. Explicit Non-Goals Until Further YES

- No production DB write.
- No replay backfill.
- No retrospective rows labeled as production history.
- No hiding `REPLAY_ERROR` rows.
- No strategy mining.
- No lifecycle promotion/demotion.
- No OFFLINE strategy creation.
- No registry cleanup unless explicitly approved.
- No use of `outputs/replay/` as runtime source.

---

## 10. CTO Summary

The project has moved beyond the old YES gate for PR #82. P56 is now merged, and the work should no longer repeat read-only coverage gates. The next meaningful progress is policy closure via PR #83, then DAILY_539 error diagnosis, then UI truth-level parity. The full product goal remains feasible, but only if the page distinguishes actual replay truth from display-only catalog and missing-history states.

Final markers:

- `P56_COVERAGE_MANIFEST_MERGED`
- `P58_TRUTH_TAXONOMY_GATE_REVIEWED`
- `ROADMAP_REALIGNED_AFTER_PR82_MERGE`
- `NEXT_FOCUS_REPLAY_TRUTH_QUALITY`
