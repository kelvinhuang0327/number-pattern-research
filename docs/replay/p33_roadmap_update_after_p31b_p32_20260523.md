# P33: Roadmap Update After P31B + P32

## Summary

Phase P33 updates the project roadmap and CTO analysis documents to reflect the completion of P31A, P31B, and P32. No production database writes, no strategy lifecycle changes, no registry mutations, and no CEO-Decision.md modifications were made in this phase.

## Date

2026-05-23 Asia/Taipei

## Branch

`p33-roadmap-update-after-p31b-p32` (from `main` @ `e704154`)

## Input State (Pre-P33)

| Item | Value |
|---|---|
| HEAD | `e704154` (P32 squash merge) |
| Production replay rows | 19960 |
| Drift guard | PASS |
| Governance guard | PASS |
| roadmap.md state | Described P31A/P31B as blocked; production rows 12460 |
| CTO-Analysis.md state | Post-P30 analysis only |

## Changes Made

### `00-Plan/roadmap/roadmap.md`

- Updated `Last Updated` date and label to P33.
- Phase table: added P31A (PR #166), P31B (PR #167), P32 (PR #168) as `[Confirmed] Complete and merged`.
- Production row baseline: updated from 12460 to 19960.
- Row-backed strategies: updated from 8 to 13 (8 ONLINE + 5 RETIRED replay-backed).
- Catalog label summary: added note clarifying RETIRED replay-backed behavior.
- Strategy row-backed distribution table: added 5 RETIRED entries with 1500 rows each.
- Replaced "Recommended P31 Wave 1 candidates" with "P31B Wave 1 — completed DAILY_539 retired strategies" table.
- Roadmap Alignment Assessment: updated all P31A/P31B/P32 entries to `[Aligned]`; updated Wave 2 and missing UX items.
- Reprioritized P0-P10: P0=P34 UI usability, P1=P35 Wave 2 planning, P2=P36 dry-run, P3-P10 as documented.
- Items-to-downgrade table: reflected all P31A/P31B/P32 as retired as active items.
- Critical Blockers: updated to post-P32 state (4 blockers, not 5).
- Most Valuable System Optimization Directions: updated to post-P32 state.
- Today's Focus: updated to P34 Replay UI Usability Gap Closure.
- Final marker: `CTO_ROADMAP_AFTER_P31B_P32_P33_20260523`.

### `00-Plan/roadmap/CTO-Analysis.md`

- CTO Review Date: updated to P33 date.
- Input Sources: added P31A/P31B/P32 evidence references and P33 pre-flight verification.
- Roadmap Alignment Assessment: all P31A/P31B/P32 now `[Aligned]`.
- Completed Work Assessment: added P31A/P31B/P32 confirmed evidence.
- Unfinished Work Assessment: replaced old P31A-blocked items with post-P32 gaps.
- P0-P10 Reprioritization: P0=P34, P1=P35, P2=P36.
- Critical Blockers: replaced P31A/P31B blockers with P34/P35/P36 blockers.
- Recommended System Optimization Directions: updated to post-P32 state.
- Roadmap Changes Applied: replaced P29/P30-era changes with P31A/P31B/P32/P33 changes.
- Risks/Unknowns: replaced P31A-era risks with post-P32 risks.
- CTO Final Recommendation: proceed with P34 next.
- CTO Summary In 10 Lines: updated to reflect post-P32 state.
- Final Classification: `P33_ROADMAP_UPDATE_AFTER_P31B_P32_MERGED_TO_MAIN`.

## P31B Wave 1 Summary (From P33 Perspective)

| Strategy | Lifecycle | Rows (P31B) | P32 API Verification |
|---|---|---:|---|
| `acb_1bet` | RETIRED (replay-backed) | 1500 | ✅ total=1500 |
| `acb_markov_midfreq` | RETIRED (replay-backed) | 1500 | ✅ total=1500 |
| `acb_markov_midfreq_3bet` | RETIRED (replay-backed) | 1500 | ✅ total=1500 |
| `midfreq_acb_2bet` | RETIRED (replay-backed) | 1500 | ✅ total=1500 |
| `midfreq_fourier_2bet` | RETIRED (replay-backed) | 1500 | ✅ total=1500 |

Total RETIRED rows (P32 lifecycle filter): **7500**

## New Prioritization

| Priority | Phase | Focus |
|---|---|---|
| P0 | P34 | UI usability gap: half-year date default + RETIRED replay-backed labeling clarity |
| P1 | P35 | Wave 2 candidate planning (19 remaining `needs_promotion`) |
| P2 | P36 | Wave 2 dry-run / temp rehearsal (production rows remain 19960) |
| P3 | — | Catalog freshness guard |
| P4 | — | Incremental replay refresh design |
| P5 | — | Manual-review strategy resolution (15 strategies) |

## Critical Blockers (Post-P32)

1. Date-range default half-year absent → P0 (P34)
2. RETIRED replay-backed strategy labeling unclear → P0 (P34)
3. Wave 2 candidate plan missing → P1 (P35)
4. Wave 2 dry-run / temp rehearsal not done → P2 (P36)

## Governance Verification

| Check | Result |
|---|---|
| Production rows | 19960 (unchanged) |
| Drift guard | PASS |
| Governance guard | PASS |
| CEO-Decision.md modified | NO |
| Production DB write | NO |
| Strategy lifecycle promotion | NO |
| Registry mutation | NO |

## Artifacts

| Type | Path |
|---|---|
| Output JSON | `outputs/replay/p33_roadmap_update_after_p31b_p32_20260523.json` |
| This doc | `docs/replay/p33_roadmap_update_after_p31b_p32_20260523.md` |

## Classification

```text
P33_ROADMAP_UPDATE_AFTER_P31B_P32_MERGED_TO_MAIN
```
