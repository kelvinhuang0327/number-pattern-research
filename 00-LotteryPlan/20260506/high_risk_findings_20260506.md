# LotteryNew — High-Risk Findings (post-review)

**Date:** 2026-05-06
**Authority:** `outputs/research_review/full_system_prediction_opportunity_review_20260506.md`
**Severity convention:** P0 = blocks scientific integrity; P1 = blocks correct closure declaration; P2 = governance hygiene.

---

## H-RISK-01 [P0] — Circular-Match Bias has no CI gate

**Description.** v1's `prediction_hit_analysis.py` produced an apparent 6/6 hit rate at 46× the simulated expectation (POWER_LOTTO max-hit=6 observed 231× vs expected 5×, p=0.001) before being flagged as INVALID due to circular-match bias (L132). The v2 SOP (`scripts/predict_vs_actual.py`) is now the only authorised analysis tool, but **there is no automated detector that prevents v1 patterns from being re-introduced.**

**Risk realisation path.** A future agent unaware of L132 / FP01 writes a new "improved" hit-analysis script that compares predictions to a historical pool. The script appears to break the lottery, gets through review (because the reviewer also doesn't recall the v1 incident), and contaminates downstream conclusions for weeks before someone notices that the corresponding `predict_vs_actual` v2 result remains NO SIGNAL.

**Mitigation today.**
- Documentation only: `wiki/system/predict_vs_actual_sop.md` STOP conditions §9; `outputs/forbidden_strategy_patterns.md` FP01–FP02; `outputs/prediction_hit_analysis/INVALID.md`; lessons L132/L139.

**Mitigation gap.**
- No CI gate. No `tests/test_no_circular_match.py`. No fixture. Detection relies on reviewer attention.

**Recommended fix.**
- Implement `tests/test_no_circular_match.py` (Re-validation Roadmap rank 1). AST-scan `scripts/`, `tools/`, `lottery_api/`. Provide `tests/fixtures/circular_match_violation.py` to verify the gate triggers. Acceptance: current codebase PASS, fixture FAIL, runtime <60s.

---

## H-RISK-02 [P0] — Hypothesis Registry does not exist

**Description.** Retirement policy R09 (post-hoc unregistered hypotheses) is the second-most-cited reason for past failures (alongside short-window promotion). The policy is documented in `wiki/system/strategy_retirement_policy.md` and `outputs/forbidden_strategy_patterns.md` FP04, but there is **no `registry/hypotheses.jsonl`, no `tools/registry/cli.py`, no test gate**. The retirement policy is currently a written promise, not an enforced invariant.

**Risk realisation path.** Following classic p-hacking pattern, a future agent runs 30 backtests, picks the one with raw_p<0.05, writes a strategy.yaml claiming the result, and the strategy reaches T2 before anyone realises the family was never pre-registered.

**Mitigation today.** R09 documented; no enforcement.

**Recommended fix.** Implement `registry/hypotheses.jsonl` + CLI (Re-validation Roadmap rank 2). Then add a CI hook that refuses any `tools/strategy_eval/` invocation without `--hypothesis-id <id>` matching a registered entry.

---

## H-RISK-03 [P0] — Strategy Evaluation Framework does not exist as single CLI

**Description.** Validation today is performed by ad-hoc scripts under `tools/` (over 200 files visible in the listing). Multiple research lessons (L60, L_028, L48, L69) document past mistakes that arose specifically because validation was scripted by hand: missed McNemar gate, missed multiple-correction, mistaken in-sample comparison, "deploy first, validate later". A single CLI that requires `--hypothesis-id` and runs the full eval pipeline (multi-window + perm + Bonferroni + BH-FDR + circular-bias + leakage) does not exist.

**Risk realisation path.** Each new strategy is validated by a slightly different ad-hoc script. Reviewers cannot enforce uniform gates. Bias slips through.

**Recommended fix.** Implement `tools/strategy_eval/cli.py` (Re-validation Roadmap rank 3). Make every gate mandatory; refuse run on missing `--hypothesis-id`.

---

## H-RISK-04 [P1] — Randomness verdict lives in UNTRUSTED `outputs/`

**Description.** Per `CLAUDE.md` Knowledge Gate, `outputs/` is UNTRUSTED. The randomness audit final verdict (`outputs/randomness_audit/randomness_audit_summary.md`) is therefore not part of the trusted decision evidence. `wiki/README.md` line 78 references the verdict but in the format of "last run timestamp", not as routed source-of-truth. This is a process gap: the audit was correctly run, but the conclusion has not been promoted into the trusted layer.

**Risk realisation path.** A new agent reads only `wiki/`, sees H6 still active, sees no closure verdict in `wiki/system/`, and (correctly per the Knowledge Gate) refuses to use the `outputs/` summary as decision evidence. Closure is silently undone because it is not in the trusted layer.

**Recommended fix.** Implement `wiki/system/randomness_final_verdict.md` (Re-validation Roadmap rank 4). Update `wiki/README.md` Source-of-Truth table.

---

## H-RISK-05 [P1] — Leakage detection is opt-in, not enforced

**Description.** `tools/verify_no_data_leakage.py` exists and is run by every per-task script in 2026-04 (e.g. L114, L117, L118, L126), but **is not invoked automatically** by any backtest API. There is no `DataLeakageError` raised by `RollingBacktester` on misuse. A new script that forgets to call the audit will not be flagged.

**Risk realisation path.** Same pattern as H-RISK-01 but for a different bias class (look-ahead instead of circular-match).

**Recommended fix.** Implement `tools/leakage_detector.py` raising `DataLeakageError` (Re-validation Roadmap rank 3, sub-task). Integrate into `tools/strategy_eval/cli.py`.

---

## H-RISK-06 [P2] — Forbidden patterns list lives in UNTRUSTED `outputs/`

**Description.** `outputs/forbidden_strategy_patterns.md` (FP01–FP03+) is the canonical list of forbidden patterns but lives in the UNTRUSTED layer. Same risk shape as H-RISK-04.

**Recommended fix.** Promote to `wiki/system/forbidden_strategy_patterns.md` (inserted task in Re-validation Roadmap §1.1).

---

## H-RISK-07 [P2] — Randomness audit cadence is not enforced

**Description.** `wiki/system/orchestrator.md` and `outputs/research_closure_report.md` specify "every 50 draws" cadence for the audit. There is **no test or scheduled task** that fails if the cadence slips. Last run 2026-05-01; daily_539 averages ~30 new draws/month, so the cadence breach point is ~7–8 weeks. A drift after a hypothetical rule change would not be detected automatically until the next manual audit.

**Recommended fix.** `tests/test_randomness_audit_cadence.py` (Re-validation Roadmap insertion).

---

## H-RISK-08 [P2] — `outputs/randomness_audit/` data-validation warnings unaddressed

**Description.** Per `outputs/randomness_audit/randomness_audit_summary.md`:
- `power_lotto`: 316 draws where special ball appears in main balls.
- `big_lotto`: 243 draws with special out of range [1..43].
- `daily_539`: 33 duplicated ball combinations.

These do **not** change the Bonferroni-corrected verdict (all three games CONSISTENT_WITH_UNIFORM after correction), but they are data-quality bugs that should be triaged. Some may be labelling-format artefacts; some may be genuine schema issues.

**Recommended fix.** Add to `data_correctness_status.md` (already exists in `docs/`); track resolution; do not block Re-validation Roadmap.

---

## H-RISK-09 [P2] — Sandbox-fastapi failure in test_evidence_collector

**Description.** During this review, `python3 -m pytest tests/test_evidence_collector.py` failed 1/23 tests because `fastapi` is not installed in the sandbox. The failure is environmental, not a defect. The local `.venv` should have `fastapi`; the sandbox does not.

**Recommended fix.** No code change. Document in CI section that sandbox-only runs may show this false fail; the local `.venv` and CI environments must include `fastapi`.

---

## Severity Roll-Up

| Severity | Count | Tasks |
|---|---|---|
| P0 | 3 | H-RISK-01 (Circular-Bias Gate), H-RISK-02 (Hypothesis Registry), H-RISK-03 (Strategy Eval CLI) |
| P1 | 2 | H-RISK-04 (Verdict to wiki), H-RISK-05 (Leakage API) |
| P2 | 4 | H-RISK-06 (Forbidden patterns to wiki), H-RISK-07 (Cadence test), H-RISK-08 (Data-quality cleanup), H-RISK-09 (Sandbox doc) |

All P0/P1 risks are addressed by the Re-Validation Roadmap (`00-Plan/LOTTERY_RESEARCH_REVALIDATION_ROADMAP_20260506.md`). P2 items are tracked but not blocking the closure declaration.

---

*End of high-risk findings.*
