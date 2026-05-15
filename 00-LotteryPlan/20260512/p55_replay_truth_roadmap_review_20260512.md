# P55 Replay Truth Roadmap Review

**Date:** 2026-05-12  
**Agent:** CTO roadmap realignment agent  
**Main SHA:** `186949e`  
**Primary roadmap:** `docs/replay/strategy_history_replay_roadmap.md`

---

## 1. Current State Verified

| Check | Result |
|---|---|
| Branch | `main` |
| HEAD | `186949e` |
| Required closure commits | `186949e`, `20e317c`, `7cc5b1b` present |
| Open PR sweep | `[]` |
| Tracked replay DB | clean |
| Untracked artifact | `data/performance_history.json` |
| Active smoke this round | skipped; no explicit active-smoke request |

Read-only registry/DB snapshot:

- Registered strategies: 16
- ONLINE: 6
- REJECTED: 4
- RETIRED: 5
- OBSERVATION: 1
- OFFLINE: 0
- Production replay rows: 460
- Production replay rows exist only for the 6 ONLINE strategies
- Non-ONLINE production replay rows: 0

## 2. CTO Alignment Finding

P25 Display-Only Catalog is complete for the visibility scope, but the clarified product goal is larger:

> every developed strategy should eventually support historical prediction-vs-actual comparison rows where replay truth can be proven.

Therefore the roadmap has been realigned:

- P25 = Phase A visibility closure
- Next focus = Phase B replay truth coverage

## 3. Key Gap

The current UI can show all lifecycle strategies, but REJECTED / RETIRED / OBSERVATION rows are display-only placeholders when production replay history is empty. They are intentionally not production replay truth.

This is correct safety behavior, but it does not yet satisfy the clarified full historical replay objective.

## 4. Reordered Focus

| Priority | Focus | Decision |
|---|---|---|
| P0 | Roadmap alignment and truth-level language | Completed by `docs/replay/strategy_history_replay_roadmap.md` |
| P1 | All-lifecycle replay coverage manifest | Next best authorized task |
| P2 | Non-ONLINE provenance recovery | Required before any row generation/backfill |
| P3 | No-write replay-row dry-run manifest | Required before production backfill |
| P4 | UI truth-level parity | Ensure table shape is consistent without over-claiming |
| P5 | Storage lane decision | Production DB vs separate evidence store |
| P6 | Controlled production backfill | Deferred until manifest + snapshot + YES |
| P7 | Post-apply smoke and live evidence | Only after P6 |
| P8 | OFFLINE strategy policy | Deferred until candidates exist |
| P9 | Backend startup runbook | Low-risk operational improvement |
| P10 | Strategy mining / lifecycle promotion | Not now |

## 5. Key Blockers

1. Non-ONLINE strategies are registered as lifecycle stubs and are not executable replay adapters.
2. No production replay rows exist for the 10 non-ONLINE strategies.
3. OFFLINE currently has zero canonical strategies.
4. Production DB backfill is not authorized and should remain blocked until a no-write manifest is reviewed.
5. Some historical docs describe pre-merge PR states; they should be treated as historical evidence, not current roadmap truth.

## 6. Next Recommended YES

```text
YES generate all-lifecycle replay coverage manifest
```

This is a no-write planning step. It should produce:

- `outputs/replay/p56_all_lifecycle_replay_coverage_manifest_YYYYMMDD.json`
- `outputs/replay/p56_all_lifecycle_replay_coverage_report_YYYYMMDD.md`

Minimum acceptance:

- lists all 16 registered strategies;
- includes lifecycle, lottery type, production replay row count, and replay status count;
- marks non-ONLINE missing-history reasons;
- records DB read-only/hash-unchanged proof;
- does not execute adapters, generate predictions, write DB, mine strategies, or promote lifecycle.

## 7. Final Markers

- `P55_MAIN_STATE_VERIFIED`
- `P55_OPEN_PR_SWEEP_COMPLETE`
- `P55_ROADMAP_REALIGNED_TO_REPLAY_TRUTH`
- `P55_PASSIVE_MONITORING_BASELINE_COMPLETE`
