# P268C: Draw-Order Full-History Feasibility & Hypothesis Design Artifact

**Type**: DESIGN ARTIFACT ONLY — no code run, no full-history fetch, no DB write, no Hypothesis Registry write, no strategy proposed, no hit-rate/success-rate-improvement claim.

Generated: 2026-06-10T13:30:00+00:00

---

## Boundaries

### P267C Conclusion Boundary
P267C (M3+ revalidation) found `NO_VALIDATED_M3_EDGE` across 36/36 cells for the existing replay-backed strategy family. **This does not close the broader success-rate / hit-rate research line.**

### P268B Conclusion Boundary
P268B (PR #407, merged into `main` @ `f3c933b`) is a **diagnostics-only** prototype. Bounded sample (2026-04/2026-05, 5 games, 190 records). `drawNumberAppear` field structurally valid: main-pool records 154/154 present/correct-length/sorted-equal-to-`drawNumberSize`; 3_STAR/4_STAR 52/52 each present and correct length; 0 parse failures. DB alignment = `NO_LOCAL_ROWS` (schema-level only, read-only `mode=ro`). Positional diagnostics (chi2-vs-uniform, adjacent-diff rates) are descriptive only, no p-value gate, **no hit-rate or success-rate claim made**.

### Track B Isolation
winnerCount / prize-distribution / EV (Track B, P268A Direction B) is explicitly **out of scope** for this hit-rate design line and must not be merged into H1/H2/H3 or any P268D plan.

---

## Causal Chain: Order Bias → Hit-Rate Strategy

`drawNumberAppear` positional bias does **NOT** directly equal a hit-rate edge. It must pass through:

1. **Order-bias detection**: within-draw permutation test detects per-ball mean exit-rank heterogeneity vs a fully-exchangeable null.
2. **Earliness-score construction**: if (1) passes, derive a per-ball "earliness score" from the estimation window only.
3. **OOS inclusion prediction**: test whether the earliness score (estimation-window-derived) predicts ball-inclusion-frequency deviations in a disjoint holdout window — single pre-registered direction, not a scan.
4. **Candidate hit-rate strategy**: only if (3) passes (and H3 stability holds) does this become a *candidate* for a future, separately-authorized strategy-design task (P221F + McNemar/L48 + three-window validation). **No strategy is designed in P268C or P268D.**

---

## Diagnostics-Only Conditions

This research line most likely terminates as diagnostics-only (NULL, a valid result) if any of:

- **Pure draw-order effect with uniform inclusion** — exit-rank heterogeneity exists but inclusion-frequency stays uniform; order bias does not transfer to which numbers are drawn.
- **Insufficient effect size given sample depth** — BIG_LOTTO (~2,100 draws), POWER_LOTTO/DAILY_539 depths fall below the L91 minimum-detectable-margin (+0.789% at power=0.80).
- **Non-stationarity across ball-set/machine eras** — P268A confirmed no machine/ball-set ID field exists in the public API; era segmentation is impossible, so a real era-specific bias would average to null when pooled.
- **Field-semantics risk** — if `drawNumberAppear` reflects broadcast/presentation order rather than physical draw order, the entire causal chain is invalid (flagged limitation, not resolvable without video review).
- **Multiple-comparisons collapse** — 5 games × multiple positions × multiple balls; any uncorrected finding is diagnostics-only until it survives the pre-registered design below.

---

## Full-History API Feasibility Plan

- **Endpoints confirmed live** (P268A/P268B): `Lotto649Result`, `SuperLotto638Result`, `Daily539Result`, `3DResult`, `4DResult` — `https://api.taiwanlottery.com/TLCAPIWeB/Lottery/{endpoint}?period&month=YYYY-MM&pageNum=1&pageSize=31`, no auth, history back to 2007-01.
- **Estimated call volume**: ~12 months/year × ~19 years (2007–2026) × 5 games ≈ **1,140 monthly calls** for a full backfill — must be rate-limited, resumable, bounded per run (no single unbounded loop).
- **Transport note**: P268B found Python `urllib` fails TLS verification against this host (`Missing Subject Key Identifier`); curl (validated in `analysis/p268b_official_draw_order_positional_bias_audit.py`) succeeds via the system CA store. P268D fetcher must use the curl-subprocess approach.
- **P268D itself does not execute this fetch** — only documents the plan. Execution requires a separate, explicitly-authorized task.

---

## Artifact-Store Backfill Plan (No Production DB Write)

- **Storage**: `outputs/research/` (JSONL or per-game CSV/JSON), append-only — **NOT** `data/lottery_v2.db`.
- **Checkpoint ledger**: resumable (month × lottery_type) completion ledger.
- **Idempotency unit**: calendar month × lottery_type.
- **Rate limiting**: sequential, single in-flight request, explicit per-run call cap; `PARTIAL` status on instability rather than retries (per P268B precedent).

---

## DB Alignment Plan & NO_LOCAL_ROWS Limitation

- **Current limitation**: P268B found local `data/lottery_v2.db` `draws` table has **0 rows** in this checkout (`NO_LOCAL_ROWS`). Row-level alignment between `drawNumberAppear` (period+lottery_type) and the canonical `draws` table could not be exercised.
- **Plan**: any future alignment check must (a) confirm which DB file/path is the canonical populated instance (not assume the checkout-local empty file), (b) open it strictly read-only (`mode=ro`), (c) match on `(lottery_type, draw=period)`, (d) report match-rate as a data-quality gate input.
- **No DB write in P268D.**
- **Future DB-write scope** (later phase, separately authorized): if H1 → H1_holdout → H2 all pass and a strategy-design task is authorized, a new column or side-table (e.g., `draw_order_sequence`) would be the eventual DB-write candidate.

---

## Hypothesis Registry Draft (NOT written to registry)

> DRAFT ONLY. A future P268D-or-later task would formally register these entries before any full-history fetch begins.

- **Primary game**: `DAILY_539` (largest depth, ~5,880 draws, maximizes power for the within-draw permutation test).
- **Secondary games**: `BIG_LOTTO`, `POWER_LOTTO`, `3_STAR`, `4_STAR`.

### H1 (primary) — `per_ball_exit_rank_heterogeneity`
- **Statement**: Per-ball mean exit-rank (position within `drawNumberAppear`, conditional on the ball being drawn) is heterogeneous across balls, beyond a within-draw fully-exchangeable permutation null.
- **Null model**: within-draw permutation null (condition on the drawn set; all orderings equally likely; ≥10,000 replicates per game).
- **Test statistic**: dispersion of standardized per-ball mean exit-rank across the pool.
- **Window**: estimation window only (see Windows below); **2026-04/05 excluded** (already inspected by P268B).
- **Correction**: Bonferroni across games tested (no cross-game correction needed if DAILY_539-only).
- **Pass**: estimation-window corrected permutation p < 0.01 **and** holdout replication (H1_holdout) p < 0.05.
- **Fail**: estimation-window p ≥ 0.01, or holdout replication fails → NULL / diagnostics-only permanent closure; H2 not opened.

### H1_holdout (primary, gated replication of H1) — `exit_rank_heterogeneity_holdout_replication`
- **Statement**: the H1 estimation-window pattern replicates (same direction, p<0.05) in the disjoint holdout window.
- **Gating**: only computed if H1 estimation-window result passes; holdout sealed/unopened until then.

### H2 (secondary, gated on H1 + H1_holdout pass) — `earliness_score_predicts_inclusion_frequency`
- **Statement**: a per-ball "earliness score" derived strictly from the estimation window predicts the *direction* of inclusion-frequency deviation (vs uniform baseline) in the holdout window.
- **Null model**: inclusion frequency under uniform random draw (closed-form, e.g. C(n-1,k-1)/C(n,k)).
- **Test design**: single pre-registered one-tailed correlation test (e.g. Spearman) — NOT a scan over alternative score definitions.
- **Correction**: none required (single pre-registered test); any deviation from the registered score definition voids the test.
- **Pass**: one-tailed p < 0.05 in the pre-registered direction.
- **Fail**: p ≥ 0.05 or wrong direction → diagnostics-only closure; does NOT reopen H1.

### H3 (secondary) — `earliness_score_temporal_stability`
- **Statement**: the per-ball earliness score is stable across a split-half (or era-split, if segmentation becomes possible) of the estimation window.
- **Test design**: Spearman rank correlation between the two halves.
- **Pass**: ρ > 0, p < 0.05.
- **Fail**: non-significant or negative → treat H1/H2 as fragile/non-stable; do not proceed to strategy design even if H1/H2 nominally pass.
- **Gating**: computed alongside H1_holdout; required input to any future go/no-go, not a hard gate by itself.

### Windows
- **Full-history range**: 2007-01 → most recent available month, **excluding 2026-04 and 2026-05** (already inspected by P268B — excluded to avoid look-ahead contamination).
- **Split**: 70% estimation / 30% holdout, chronological (estimation = earliest 70% of eligible draws, holdout = most recent 30%, both excluding 2026-04/05).
- **Split-half for H3**: estimation window further split chronologically in half.

### Baseline
- **H1 baseline**: within-draw permutation null (exchangeable ordering given the drawn set).
- **H2 baseline**: closed-form uniform inclusion probability per ball given pool size and draw size.

### P221F / p-hacking Guardrails
- All hypotheses, windows, baselines, thresholds frozen **before** any full-history fetch (registry-freeze precedes backfill — P268D step 1).
- 2026-04/05 permanently excluded from confirmatory tests.
- Holdout window sealed until H1 estimation-window result is finalized.
- H2 score definition fixed at registration time; redefinition requires a new hypothesis ID.
- No post-hoc scan over alternative null models, statistics, or windows; any such exploration must be a separate, clearly-labeled exploratory (non-confirmatory) note.
- Single primary game (DAILY_539) for H1 minimizes multiple-testing burden; co-primary additions require Bonferroni across the co-primary set.
- Track B (winnerCount/EV) variables must not enter H1/H2/H3 feature sets.

---

## P268D Implementation Order (≤10 steps)

**Ranking rationale**: registry/pre-registration **first** (no data-driven hypothesis tuning possible) → full-history artifact backfill (data must exist before alignment/testing) → alignment/data-quality (must trust data before testing) → H1 confirmatory test **last**.

1. **freeze_registry_artifact** — formally register H1/H1_holdout/H2/H3 (from this draft) into the Hypothesis Registry, windows/baseline/correction/pass-fail frozen, before any full-history fetch.
2. **bounded_rate_full_history_fetcher** — curl-subprocess fetcher (per P268B precedent) writing per-month per-game results to `outputs/research/` JSONL/CSV. No DB write.
3. **checkpoint_resume_ledger** — (month × lottery_type) completion ledger; resumable, bounded; PARTIAL on instability, no aggressive retries.
4. **structure_validation** — per-record `drawNumberAppear` presence/length/sorted-equivalence checks (per P268B), failures logged.
5. **annual_zip_csv_cross_check_sample** — bounded cross-validation against official annual ZIP/CSV archive (Direction D) to catch transcription drift.
6. **readonly_canonical_db_alignment** — identify canonical populated DB instance, open `mode=ro`, compute `(lottery_type, draw=period)` match-rate vs backfilled artifacts.
7. **data_quality_gate** — coverage/structure-failure-rate gate (e.g., ≥99% coverage, <0.1% structure failures); FAIL halts progression.
8. **h1_estimation_window_test** — run H1 (within-draw permutation test) on the estimation window only, per frozen registry; holdout sealed.
9. **h1_pass_or_fail_branch** — PASS → open holdout for H1_holdout + H3; FAIL → diagnostics-only/NULL closure artifact, H2 not opened, no re-scan.
10. **governance_closeout** — record final classification in `CURRENT_STATE.md` / `active_task.md`. No hit-rate/success-rate-improvement claim regardless of outcome; any strategy-design follow-up requires a separate, future, explicitly-authorized task.

---

## Explicit Non-Claims

- No claim that hit-rate / success-rate has been improved.
- No new strategy proposed.
- No production DB write performed or authorized by this artifact.
- No Hypothesis Registry write performed (draft only).
- No full-history API fetch performed.
- Track B (winnerCount/EV/popularity) is not part of this hit-rate design line.

---

## Final Classification
`P268C_DRAW_ORDER_FULL_HISTORY_FEASIBILITY_AND_HYPOTHESIS_DESIGN_COMPLETE`
