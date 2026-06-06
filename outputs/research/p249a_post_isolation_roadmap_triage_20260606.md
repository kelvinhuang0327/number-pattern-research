# P249A — Post-Isolation Roadmap Triage

**Date:** 2026-06-06 12:55:27  
**Task:** P249A  
**Classification:** ROADMAP_TRIAGE_READ_ONLY  

## Executive Summary

P249A is a read-only triage after completing the P246B–P248A BIG_LOTTO canonical isolation arc. All major research lines (DAILY_539, POWER_LOTTO, 3_STAR/4_STAR, BIG_LOTTO) are closed or NULL. The recommended next task is a low-risk Type B governance sync (roadmap.md + CURRENT_STATE.md label fix). No DB write, no strategy promotion, no betting advice.

## Current State After P248A

| Item | State |
|------|-------|
| BIG_LOTTO canonical isolation | **COMPLETE** (P246B–P248A) |
| DB view `draws_big_lotto_canonical_main` | Exists — 2,113 canonical rows |
| Raw BIG_LOTTO draws | 22,238 (preserved, raw-accessible) |
| ADD_ON_PRIZE_EXCLUDED | 19,100 (raw-accessible) |
| P246K canonical NIST | **GREEN** (random-compatible; no prediction edge) |
| Active research candidates | **NONE** (all lines closed or NULL) |
| active_task.md status | **WAITING_FOR_USER_AUTHORIZATION** |

## Closed Research Lines

| Line | Status | Task |
|------|--------|------|
| DAILY_539 midfreq_fourier_2bet | REJECTED_BY_BACKWARD_OOS | P230C |
| POWER_LOTTO first-zone | NULL | P231B |
| 3_STAR/4_STAR box-play | UNDERPOWERED_NO_SIGNAL | P227C |
| 3_STAR/4_STAR straight-play | NULL | P214C |
| BIG_LOTTO 49C6 signal space | EXHAUSTED | P247G |
| NIST raw-population audit (P238B) | YELLOW_OBSERVATION_ONLY | P238B |

## Candidate Task Table

| ID | Title | Type | Value | Risk | Urgency | Recommended Now |
|----|-------|------|-------|------|---------|-----------------|
| T1 | roadmap.md sync for P246–P248A arc | read-only / doc-only | Medium — governance completeness; preven… | Very low — doc-only, | Low-medium — stale r | YES |
| T2 | CURRENT_STATE.md row-count label clarification | read-only / doc-only | Low-medium — governance accuracy; 'BIG_L… | Very low — doc-only | Low — potential futu | YES (can be combined with T1 in same PR) |
| T3 | Archived BIG_LOTTO script migration (deferred) | code-change | Low — scripts not in active pipeline… | Low — isolated chang | Very low — only need | NO |
| T4 | Annotation table Type D planning/apply | Type D | Low — canonical isolation already comple… | Low-medium — control | Very low — no active | NO |
| T5 | DAILY_539 new hypothesis pre-registration design | research / read-only | Medium-high if good hypothesis found… | Low if read-only; me | Low — all prior cand | NO (unless user has specific hypothesis to test) |
| T6 | POWER_LOTTO new hypothesis pre-registration design | research / read-only | Medium if hypothesis found… | Low if read-only | Low | NO |
| T7 | 3_STAR/4_STAR per-position replay code build | code-change / Type D if DB write | Low-medium — positional data is in DB; P… | Medium — significant | Very low — P214C: 0  | NO |
| T8 | Raw history UI/API add-on labeling | UI/API | Low — no active consumer requesting it… | Medium — requires fr | Very low | NO |

## Recommended Next Task

**T1+T2: roadmap.md sync + CURRENT_STATE.md row-count label clarification**

> Both are zero-risk, Type B doc-only governance cleanup tasks that can be done in a single PR. T1 records the completed P246B–P248A arc in roadmap.md. T2 clarifies that 'BIG_LOTTO rows | 24,140' in CURRENT_STATE.md refers to replay rows, not draw rows (actual BIG_LOTTO draw rows = 22,238). No DB write. No code change. No strategy promotion. No authorization required beyond Type B.

### T1 — roadmap.md sync
- Record P246B–P248A BIG_LOTTO canonical isolation arc in the roadmap phase table.
- roadmap.md last updated P213L (2026-06-05); does not reflect 18 P246/P247/P248 tasks.

### T2 — CURRENT_STATE.md row-count label fix
- 'BIG_LOTTO rows | 24,140' = replay rows, not draw rows (24,140+34,680+36,104=94,924 total replays).
- Actual BIG_LOTTO draw rows = 22,238. Label should say 'BIG_LOTTO replay rows'.
- Fix prevents future agents from misinterpreting the canonical draw count.

## Why Not Annotation Table Immediately

- Canonical isolation is complete via DB view and helper (P247B/P247E).
- No active research consumer requires per-row family labels.
- Annotation table requires Type D authorization (DB write + backup).
- Deferred until a specific use-case justifies it.

## Why Not Prediction-Edge Overclaim

- P246K canonical NIST audit GREEN = data quality confirmation only.
  It confirms 2,113 canonical main-draw rows are statistically random-compatible.
  **It does not imply any exploitable prediction signal.**
- BIG_LOTTO 49C6 signal space is exhausted (L90/L91; P247G confirmed).
- All lottery lines (DAILY_539, POWER_LOTTO, 3_STAR/4_STAR) are NULL or UNDERPOWERED.
- New research requires new pre-registration + P221F gate + explicit authorization.

## Required Authorization

| Candidate | Authorization Required |
|-----------|----------------------|
| T1+T2 (roadmap sync) | None — Type B doc-only |
| T3 (script migration) | None — but user must decide which scripts to reactivate |
| T4 (annotation table) | Explicit Type D phrase |
| T5/T6 (new hypothesis) | Explicit user direction + pre-registration |
| T7 (3/4_STAR replay build) | Explicit authorization + new pre-registration |
| T8 (UI/API labeling) | Frontend/API change authorization |

## Compliance Statements

- **No DB write performed in P249A.**
- **No rows deleted, updated, or inserted.**
- **No strategy promotion or betting advice.**
- **No production recommendation change.**
- GREEN canonical randomness (P246K) does not authorize any new prediction direction.

---
*Generated by P249A — post-isolation roadmap triage*