# P328A Validation Summary

| # | Check | Result |
|---|-------|--------|
| 1 | origin/main HEAD == ce2c042e7f4967841e6b31e17552d55bf4717f91 | PASS (confirmed) |
| 2 | `build_p326a_baseline_summary.py` byte-identical regeneration | PASS (no git diff after run) |
| 3 | `node --check src/apps/lottery-d5/lottery-d5.js` | PASS |
| 4 | pytest (3 D5 static UI test files) | PASS — 23 passed in 0.15s |
| 5 | Browser smoke (D5 baseline section renders required values) | PASS-WITH-NOTES — see browser_smoke.md; Chrome extension unavailable and preview tool would require a forbidden write to the main repo root, so a curl+source-inspection equivalent was substituted; all required data/wording confirmed |
| 6 | No loader-failure string rendered | PASS (dormant error path only, not triggered — all endpoints returned 200) |
| 7 | No positive forbidden wording (best strategy / betting pick / recommended numbers / guaranteed / production-ready optimizer) | PASS — none found in D5 baseline scope |
| 8 | "prediction" only in negative caveats | PASS |
| 9 | `git status --short lottery_api/data/lottery_v2.db` clean | PASS (empty output) |
| 10 | npm tests NOT RUN (no root package.json) | CONFIRMED |
| 11 | Final git status clean | PASS |

## Overall
All required checks PASS. One documented deviation: full JS-rendered browser smoke (Chrome
DOM paint) was not directly observable in this environment; a static-content + source-logic
equivalence check was substituted and gives high confidence of correctness. See browser_smoke.md.

Final classification: **P328A_D5_BASELINE_RESULTS_POST_PUSH_ACCEPTANCE_COMPLETE_WITH_NOTES**
