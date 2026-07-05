# P280AW — BIG 6/49 Private Ticket Decision Runner

**Task ID:** P280AW
**Date:** 2026-06-19
**Final Classification:** `P280AW_PRIVATE_TICKET_DECISION_RUNNER_PR_OPEN_NO_PUBLICATION_NO_CLAIM`

---

## Safety Notice

> **P280AT NULL:** No BIG 6/49 strategy has demonstrated reliable edge over
> equal-budget diversified random (Bonferroni-corrected, k≥3).
> Strategy tickets are included for **observation/tracking ONLY**.
> This runner does **NOT** claim improved winning probability.

---

## What This Is

`tools/p280aw_big649_private_ticket_decision_runner.py` is a local-only CLI tool
that consumes the frozen P280AQ strategy adapter output and the P280AT ranking
results to produce private BIG 6/49 ticket decision packs on demand.

It answers:
1. If budget is 3 / 5 / 7 / 11 tickets, which private pack should I use?
2. Which tickets are strategy-derived reference tickets?
3. Which tickets are diversified-random coverage tickets?
4. Which tickets are hybrid strategy + diversified-random?
5. Which tickets are redundant / high-overlap / coverage-positive?
6. What is the honest warning from P280AT NULL?

---

## What This Does NOT Do

- Claim improved future winning probability
- Perform official target lookup
- Perform official deadline lookup
- Write or copy the database
- Create a pre-draw manifest
- Create a publication PR
- Activate any strategy
- Promote any strategy
- Commit current live/private ticket numbers to the repo

---

## Reconciliation

| Checkpoint | Value |
|---|---|
| P280AV final classification | `P280AV_PR464_MERGED_VERIFIED_NULL_NO_PUBLICATION_NOT_ACTIVATED` |
| origin/main after P280AV | `3fdc07fd2e27e64460c134acc433b5cfe0dd2da3` |
| P280AT final classification | `P280AT_BIG649_STRATEGY_RANKING_REPLAY_PR_OPEN_NULL_NO_PUBLICATION` |
| P280AT canonical digest | `a905cc7646f54f1e8ec4d64c8a07dce529e5b5455c70baf4c9f09e40a9d3e5db` |
| P280AQ adapter digest | `b8ceac657f081bbf2be6ae0fabe6adbce564ea3a4b4cb77ab610035d0e4a800a` |
| P280AQ adapter digest verified | ✓ PASS |
| P280AO / PR #462 touched | NO |

---

## DB Access

| Field | Value |
|---|---|
| DB opened | YES |
| DB queried | YES |
| DB copied | NO |
| DB written | NO |
| DB hash before | `539efda5874b08f7b7e25b36cd0c70e4d4d582c8df9541eec73eaa0e373650d2` |
| DB hash after | `539efda5874b08f7b7e25b36cd0c70e4d4d582c8df9541eec73eaa0e373650d2` |
| DB drift | NONE |
| Latest local draw | `115000062` (local read-only) |
| Private local ref id | `115000063` — **NOT official target, NOT official deadline** |

---

## Runner Design

**Tool:** `tools/p280aw_big649_private_ticket_decision_runner.py`
**Tests:** `tests/test_p280aw_big649_private_ticket_decision_runner.py`

### Output Modes

| Mode | Description | Default recommendation |
|---|---|---|
| `strategy_reference_pack` | 11 strategy-derived tickets (P280AQ frozen pack) | OBSERVATION TRACKING ONLY |
| `diversified_random_pack` | k low-overlap random tickets, deterministic seed | **DEFAULT for k≥3** |
| `hybrid_pack` | Conservative mix of strategy + random | Use when tracking is desired |
| `contribution_report` | Coverage, overlap, marginal contribution metrics | Diagnostic only |
| `summary_recommendation` | Practical guidance based on P280AT NULL | Default mode |
| `all` | Run all modes | — |

### Hybrid Pack Conservative Defaults (P280AT NULL respected)

| Budget k | Strategy tickets | Diversified random |
|---|---|---|
| 3 | 0 | 3 |
| 5 | 1 | 4 |
| 7 | 1 | 6 |
| 11 | 2 | 9 |

**Rationale:** P280AT shows the equal-budget random baseline outperforms the
strategy pack at k≥3 because frozen primaries are internally redundant. Strategy
slots are reference/tracking only; diversified random provides better coverage.

---

## How to Run

```bash
# Default (summary recommendation, budget 5, seed 42):
python3 tools/p280aw_big649_private_ticket_decision_runner.py \
    --db /path/to/lottery_api/data/lottery_v2.db

# All modes, JSON output:
python3 tools/p280aw_big649_private_ticket_decision_runner.py \
    --mode all --budget 5 --seed 42 \
    --db /path/to/lottery_api/data/lottery_v2.db \
    --json

# Write output to /tmp (never commit runtime output):
python3 tools/p280aw_big649_private_ticket_decision_runner.py \
    --mode all --json \
    --db /path/to/lottery_api/data/lottery_v2.db \
    > /tmp/p280aw_output.json
```

**Always write runtime output to `/tmp` or stdout. Never commit live draw numbers.**

---

## Smoke Test Summary (Task E)

| Metric | Value |
|---|---|
| Strategy pack coverage | 35/49 unique numbers |
| Strategy pack max pair overlap | 5 |
| Strategy pack duplicates | 0 |
| Diversified random k=5 coverage | 24/49 unique numbers |
| Diversified random k=5 max pair overlap | 2 |
| Adapter digest verified | ✓ PASS |
| DB drift | NONE |
| DB copied/written | NO/NO |

---

## Tests (Task C) — 52 PASS / 8 SKIPPED (artifact schema)

Tests cover:
- Deterministic output with synthetic DB fixture
- No official target/deadline fields
- No pre-draw manifest output
- No publication artifact path
- No prediction_success_claim / strategy_promoted / activation
- No DB write/copy (mocked fixture)
- Diversified random low-overlap (max overlap ≤ 3 enforced)
- Hybrid pack budget shape for k=3/5/7/11
- Strategy pack digest reconciliation (exact P280AQ digest)
- Contribution metrics (coverage, overlap, marginal, duplicates)
- P280AT NULL warning in every output mode
- Committed artifact schema (final_classification, safety flags)
- No live/current ticket numbers in committed artifact

---

## Safety Flags

| Flag | Value |
|---|---|
| `prediction_success_claim` | false |
| `strategy_promoted` | false |
| `activation` | false |
| `real_publication_performed` | false |
| `pre_draw_manifest_created` | false |
| `publication_pr_created` | false |
| `official_target_lookup_performed` | false |
| `official_deadline_lookup_performed` | false |
| `current_live_ticket_numbers_committed` | false |

---

## P280AO / PR #462

Status: **OPEN / UNTOUCHED / SEPARATE** — not touched by P280AW.

---

## Next Steps (Require Separate Owner Authorization)

1. **Independent audit of P280AW PR** before merge.
2. **P280AX merge-only** after audit PASS.
3. **Private runtime use**: to print current live numbers from runner, request separately after runner exists; do not commit those numbers.
4. **First real publication**: requires official target/deadline and separate risk gate — remains unauthorized.
5. **Post-draw evaluation**: affects strategy retention/promotion — remains separate.
6. **Branch/worktree cleanup**: remains unauthorized unless Owner explicitly requests.
