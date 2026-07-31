# SZC2 — Second-Zone Score Guard Static Audit

## Executive Summary
Lightweight static verification indicates second-zone special fields are currently display/metrics-oriented and do not feed core first-zone `numberScores`, overall recommendation score, ranking, confidence, or candidate selection in inspected scoring paths.

**Final classification: `SECOND_ZONE_DISPLAY_ONLY_CONFIRMED`**

## SZC1 Dependency
- SZC1 final classification: `SECOND_ZONE_NO_SIGNAL_CONFIRMED`
- Governance direction: second-zone display-only, exclude from recommendation score, evaluate separately.

## Pre-flight Snapshot
- Repo: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`
- Branch: `main`
- Git dir: `.git`
- Worktree: dirty (existing unrelated changes present); this audit remained read-only and did not alter production logic.

## Code Path Inventory
- `src/core/App.js`
: special fields (`predictedSpecial`, `actualSpecial`, `special`) are used in simulation/evaluation display payloads.
- `src/core/handlers/UIDisplayHandler.js`
: special is rendered as UI badge/note (display-only behavior).
- `src/core/App.js` and `src/ui/AutoLearningManager.js`
: `numberScores`, sorting, bet ranking, and overall confidence are aggregated from `numbers` and `confidence` only.

## Score Contamination Finding
No static evidence found that `special_hit`, `predicted_special`, or `actual_special` participates in:
- first-zone `numberScores`
- overall recommendation score
- ranking order
- confidence weighting
- candidate selection in inspected core scoring flows

## UI/API Disclosure Risk
No direct contamination signal found. Current inspected behavior is consistent with display-only handling for second-zone special.

## Contract Recommendation
- Keep guard: second-zone special must not enter recommendation score aggregation.
- Keep second-zone metrics separate from first-zone score metrics.
- When presenting second-zone performance, display random baseline `0.125` explicitly.

## Final Classification
`SECOND_ZONE_DISPLAY_ONLY_CONFIRMED`
