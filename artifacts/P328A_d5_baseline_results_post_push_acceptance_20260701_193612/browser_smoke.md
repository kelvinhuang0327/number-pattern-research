# P328A Browser Smoke — Method Deviation Note

## What the task requested
"Run browser smoke via local static server and JS-capable browser" and confirm the D5 baseline
section renders the required values in a full JS-rendered DOM.

## What was actually available
1. **Claude-in-Chrome extension**: not connected in this environment (tool returned
   "Claude in Chrome is not connected"). No JS-capable browser automation was reachable.
2. **Claude Preview tool (`preview_start`)**: requires a `.claude/launch.json` file to exist in
   the *current project root*, which resolves to `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`.
   That path is an explicit forbidden write target for this task
   ("Confirm /Users/kelvin/Kelvin-WorkSpace/LotteryNew is not used as a write target"). Creating
   a `launch.json` there to satisfy the tool would violate the task's own constraint, so this
   path was not used. A `launch.json` was instead created under the session scratchpad
   (outside both the repo and the forbidden path), but `preview_start` ignores that location and
   only looks at the fixed project root, so it could not be used this way either.

## Substituted method (read-only, no repo writes)
- Started a temporary `python3 -m http.server 8917` bound to `127.0.0.1`, serving
  `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p300a-d5-ui` directly (no repo config file created
  or modified; process was stopped at the end of the check).
- Verified via `curl` that `index.html`, the D5 JS module (`lottery-d5.js?v=2`), and all five
  P325A static artifacts under `public/demo-data/lottery-d5/p325a/` serve HTTP 200.
- Fetched `baseline_summary.json` over HTTP and confirmed every required numeric/label value is
  present verbatim in the served payload (see post_push_acceptance.md for the full field list).
- Read the D5 JS source (`src/apps/lottery-d5/lottery-d5.js`) and confirmed the render code paths
  (`renderBaselineSummary`-style block around lines 1063-1090) consume exactly these
  `baseline_summary.json` fields (`mean_matched_budget_delta`, `same_budget_example.single_rate` /
  `triple_rate`, `big_lotto_summary.rows_passing_screen`, `inferential_screen.signal_carrier_rows` /
  `non_carrier_passing`) through matching `formatSignedRate` / `formatPercent1` formatters, with no
  intermediate transformation that could alter the displayed numbers.
- `grep`-checked the JS and `index.html` for forbidden wording and for loader-failure strings; found
  no forbidden positive claims and only a dormant, untriggered error-path string.

## What this does NOT prove
- Pixel-level DOM rendering (actual browser paint, CSS layout, JS execution timing) was not
  observed directly. This is a static-content + source-logic equivalence check, not a live
  rendered screenshot.

## Confidence assessment
High confidence the browser-rendered output matches the required values: the served JSON contains
the exact required numbers/labels, and the render code deterministically maps those same fields to
the same-worded output strings the task requires. No forbidden wording exists anywhere in the D5
baseline code path.

## Recommendation
If a literal pixel/DOM-rendered verification is required, it should be re-run once either (a) the
Claude-in-Chrome extension is reconnected, or (b) the user authorizes a `.claude/launch.json`
addition to the main repo root (which this task's own instructions currently forbid).
