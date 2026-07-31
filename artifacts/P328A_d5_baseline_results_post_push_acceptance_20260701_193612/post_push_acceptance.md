# P328A Post-Push Acceptance

## Repo / commit state
- Repo: /Users/kelvin/Kelvin-WorkSpace/LotteryNew-p300a-d5-ui (linked worktree, git-common-dir /Users/kelvin/Kelvin-WorkSpace/LotteryNew/.git)
- origin/main HEAD (after `git fetch origin`): ce2c042e7f4967841e6b31e17552d55bf4717f91 — MATCHES expected
- Working tree: clean; no staged files
- lottery_api/data/lottery_v2.db: no changes (git status clean)

## Reproducibility check
- `python3 tools/lottery-d5/build_p326a_baseline_summary.py` re-run: output byte-identical to committed
  `baseline_summary.json` / `source_provenance.json` (git status/diff empty after regeneration).

## Static/syntax checks
- `node --check src/apps/lottery-d5/lottery-d5.js`: PASS (no syntax errors).

## Test suite
- `pytest tests/test_p326a_d5_baseline_results_static_ui.py tests/test_p321a_d5_combination_results_static_ui.py tests/test_p300a_d5_artifact_backed_ui.py -q -p no:cacheprovider`
- Result: 23 passed in 0.15s

## npm tests
- Root `package.json` absent → npm tests correctly NOT RUN.

## Data content verification (via served static file)
`baseline_summary.json` served content confirmed exact match to required values:
- classification: DESCRIPTIVE_ONLY
- baseline_status: COMPUTED ("matched-budget random baseline: computed")
- equal_budget_raw_subsampling_status: INSUFFICIENT_RAW_DATA ("raw per-draw equal-budget subsampling: insufficient raw data")
- mean_matched_budget_delta: hit_at_least_1 = -0.0279, hit_at_least_2 = 0.0075, hit_at_least_3 = -0.0091
- same_budget_example: single_rate = 0.7 (70.0%), triple_rate = 0.498 (49.8%)
- big_lotto_summary.rows_passing_screen: 0
- inferential_screen.signal_carrier_rows: 34, signal_carrier_of_passing: 41, non_carrier_passing: 7
- signal_carrier_strategy: daily539_f4cold_5bet, described as "observed single-strategy signal carrier" / "inherited single-strategy behaviour, not combination synergy" — NOT called "best strategy"
- non_claim field present verbatim: "This is a descriptive baseline check only - not a prediction, not a betting recommendation, and it does not recommend any numbers to play."

## Wording compliance
- No positive occurrences of "best strategy", "betting pick", "recommended numbers", "guaranteed", or
  "production-ready optimizer" within the D5 baseline feature code/markup.
- All "prediction" mentions in the D5 baseline scope are negative caveats.
- One dormant defensive error string exists in the JS (`setError` on fetch failure) but was not
  triggered — all data endpoints served 200 via local static server.

## Final classification
P328A_D5_BASELINE_RESULTS_POST_PUSH_ACCEPTANCE_COMPLETE_WITH_NOTES

Note: see browser_smoke.md for the one deviation from the literal task script (JS-rendered browser
smoke could not be performed with the available tools; a curl/grep-based static-content equivalent
was substituted, with source-level render-logic inspection to bridge the gap).
