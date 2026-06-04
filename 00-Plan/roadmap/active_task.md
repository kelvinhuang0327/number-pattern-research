# Active Task — Today (2026-06-04 PM)

> **STATUS: `WAITING_FOR_USER_AUTHORIZATION`**
> CEO Second Review 2026-06-04 (PM): `CEO_DECISION_PARTIALLY_APPROVED`
> (see `00-Plan/roadmap/CEO-Decision.md` → "CEO Second Review — 2026-06-04 (PM)").
> System at clean steady state. No worker dispatched. No DB / registry / production write.

---

## Context (verified read-only, 2026-06-04 PM)
- repo `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`; branch was `main` at review; HEAD == origin/main == `6cf2e1a`.
- DB `strategy_prediction_replays` = 94,924 rows; integrity `ok`; drift guard `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS`.
- `LIFECYCLE_UNRESOLVED = 0` (P233B). No deployable candidate in any lottery.
- [Risk] `roadmap.md` + `CTO-Analysis.md` carry UNCOMMITTED P234 edits on main; user elected to leave them untouched this round (CTO follow-up).

## CEO Decision Summary
- CTO P234 statistical-methods adoption: ADOPT diagnostics-only framing; REJECT P0.5 urgency (demote to P2 design-only); 7/8 methods already exist + enforced (P221F gate; Bonferroni/BH in P222/P223B/P227C; rolling windows in RSM/P114/P224).
- Namespace: stat-methods = P234; Lofea review = **P235A**.

## Authorized-on-request options (NONE auto-started — require explicit user authorization)
- **OPT-A (recommended): HOLD + (later) reconcile.** Keep clean state. Optionally PR-or-revert the dirty `roadmap.md` / `CTO-Analysis.md` as a separate CTO follow-up.
- **OPT-B: P235A Lofea read-only feasibility review.** Analysis artifact only — no clone into repo, no vendored code, no DB / registry / production write.
  - Output: `outputs/research/p235a_lofea_readonly_feasibility_review_20260604.md`
- **OPT-C: P234 stat-methods diagnostics INVENTORY (design-only).** Read-only inventory artifact; no module build, no code, no DB.
  - Output: `outputs/research/p234_statistical_diagnostics_inventory_20260604.md`

## Hard guards for ANY authorized task
- Phase 0: repo == LotteryNew; branch is a **dev branch (NOT main — `.claude/settings.json` Edit|Write hook blocks main)**; HEAD == origin/main; `git diff --cached --name-only` empty; DB 94,924 / integrity ok; drift guard PASS.
- Forbidden: DB / registry / production / runtime writes; controlled apply; deployment; strategy promotion; betting advice; new repo; `git add -A` / `git add .` over the dirty tree (narrow allowlist only).
- STOP if any guard fails or scope would require any forbidden action.

## Required Completion Check (for the authorized task)
1. 是否真的完成
2. 測試結果 PASS / FAIL / NOT RUN
3. 仍卡住的唯一問題
4. 修改檔案清單
5. staged / commit / push 狀態
6. 是否允許進入下一輪
7. Final Classification

Final Classification (this file): `WAITING_FOR_USER_AUTHORIZATION`
