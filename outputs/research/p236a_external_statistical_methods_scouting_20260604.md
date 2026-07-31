# P236A — External Statistical Methods Scouting For LotteryNew

**Task ID:** P236A
**Date:** 2026-06-04 Asia/Taipei
**Type:** Read-only scouting (source index + method whitelist/blacklist + candidate feature family + validation rubric). No implementation, no DB/registry/production write, no strategy, no betting advice, no predictability claim.
**Authorization:** User directed "import useful external methods ASAP to improve prediction success rate" and selected **full P236A scouting** (2026-06-04), after being shown — and accepting on record — that hit-rate improvement is closed by the system's own evidence and the honest expected outcome of broad scouting is NULL.
**Source identification:** All external sources below fetched/verified this session.

**Final Classification:** `P236A_EXTERNAL_STAT_METHODS_SCOUTING_COMPLETE_FALSIFICATION_AND_DIAGNOSTICS_ONLY`

---

## 1. Executive Summary

[Confirmed] This is a **falsification-oriented** scout, not an edge hunt. The correct goal (per CTO framing, adopted here) is: *take external methods, run them through LotteryNew's read-only validation gate, and verify whether any beats the random baseline on corrected OOS. If not — and the strong prior is not — formally mark NULL.* NULL is a valid, complete result.

[Confirmed] **Hit-rate prediction is already closed by the project's own evidence and external scouting does not reopen it:**
- **L91** — BIG_LOTTO 49C6 is statistically indistinguishable from a fair random process (6 randomness tests PASS; best margin +0.414% inside the 99th-pct noise band +0.778%).
- **L82** — DAILY_539 signal space exhausted (H001–H008 all REJECT).
- **P178A** — POWER_LOTTO active research closed: 17 candidates all NULL.
- **SZC1** — POWER_LOTTO second-zone special_hit 0.1181 **< 0.125** (below random).
- **L99/L101** — all games ruin_prob = 1.000; selective betting's *unconditional* edge is necessarily negative.

[Confirmed] **Most "external statistical methods" are already in-system.** Per the P234 CEO decision (`active_task.md`), **7 of 8** proposed methods already exist and are enforced: pre-registration anti-overfit gate (**P221F**), Bonferroni/BH multiple-testing correction (**P222/P223B/P227C**), rolling/walk-forward windows (**RSM/P114/P224**), plus three-window validation, permutation testing, McNemar replacement gate, and baseline comparison already in the standard pipeline.

[Inferred] **The honest deliverable of this scout** is therefore not a new predictor but a short, defensible list of what — if anything — is *net-new and importable*. There are exactly **two** such items, and **neither targets hit-rate**:

1. **NIST SP 800-22-style randomness audit as a single-source-of-truth (SSOT) null baseline + continuous tripwire** (the "8th method", the one genuine gap). It cannot predict random draws; it *alerts if the draws ever stop being random* — the only condition under which prediction could ever become possible.
2. **Payout / anti-crowd expected-value lever** (avoid popular numbers). This raises **E[payout | win]**, **not** P(win), and stays negative-EV. Already partially tested (**L102**: ADVISORY_ONLY, perm p=0.257, swap rate 0.7%).

**Bottom line: adopt-now (new predictor) = NO. Recommended net-new import = the randomness-audit SSOT/tripwire (diagnostics-only), as a separately-authorized read-only build.**

---

## 2. Methodology & Boundaries

- [Confirmed] Read-only. Sources fetched via web; no code executed from any external repo; no DB/registry/production touched.
- [Confirmed] Every candidate is classified **WHITELIST** (adopt as diagnostic / already-owned methodology), **GRAYLIST** (benchmark / falsification-only), or **BLACKLIST** (do not touch).
- [Confirmed] No method is promoted. No method is claimed to improve win rate. Any future reuse requires separate authorization + native re-derivation + the §6 validation rubric.
- [Confirmed] Statistical unit = **distinct draws**, never replay rows (the project's recurring error; POWER_LOTTO ≈ 1500–1551 draws, not 9000–36104 rows).

---

## 3. Source Index (verified this session)

| # | Method / Source | URL | What it is FOR | Class |
|---|---|---|---|---|
| S1 | **NIST SP 800-22 Rev 1a** — statistical test suite for (P)RNGs; 15 tests; null = "sequence is random" | <https://csrc.nist.gov/pubs/sp/800/22/r1/upd1/final> · <https://csrc.nist.gov/projects/random-bit-generation/documentation-and-software> | **Randomness audit / null SSOT / tripwire.** Detects *non*-randomness; explicitly **not** a predictor. | **WHITELIST (diagnostic)** |
| S2 | **scikit-learn `TimeSeriesSplit`** — walk-forward, expanding training window | <https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html> | Leakage-safe OOS splitting (no training on future). | **WHITELIST (already-owned: RSM/P114/P224)** |
| S3 | **scikit-learn `permutation_test_score`** — permutation p-value vs shuffled-label null | <https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.permutation_test_score.html> | p-hacking guard; null distribution by permutation. *Use Binomial(baseline) Monte-Carlo null where label-shuffle preserves mean (L96).* | **WHITELIST (already-owned)** |
| S4 | **statsmodels `multipletests`** — Bonferroni / BH-FDR correction | <https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html> | Multiple-comparison correction across candidates × windows × thresholds. | **WHITELIST (already-owned: P222/P223B/P227C)** |
| S5 | **Bayesian / Dirichlet-multinomial shrinkage** — frequency smoothing | (standard method; e.g. statsmodels/scipy) | A *benchmark* (smoothed frequency), not a strategy; must beat random baseline. | **GRAYLIST (benchmark-only)** |
| S6 | **ML benchmark family** — Naive Bayes / logistic / tree / XGBoost / sequence models | (scikit-learn / xgboost) | *Falsification* benchmarks only. Project lessons L86/L89/L90 show severe overfit on low-base-rate games. | **GRAYLIST (falsification-only)** |
| S7 | **Lofea** — lottery feature-engineering toolkit (CC-BY-NC) | <https://github.com/JeffMv/Lofea> | Design inspiration ONLY (P235A). No vendoring; native re-derive only. | **GRAYLIST (design-inspiration, per P235A)** |
| S8 | **Unpopular-number / conscious-selection literature** | <http://understandinguncertainty.org/it-possible-improve-your-chances-winning-big-national-lottery.html> · <https://rss.onlinelibrary.wiley.com/doi/full/10.1111/j.1740-9713.2012.00540.x> · <https://www.cambridge.org/core/journals/judgment-and-decision-making/article/number-preferences-in-lotteries/47BA27051627CEED421AD3AEE255521E> | **Payout** lever: avoid crowded numbers → less jackpot-sharing → higher E[payout\|win]. **Not** P(win). | **GRAYLIST (payout-metric, not hit-rate)** |
| S9 | CDM-profit / martingale / betting-progression systems | (various) | Negative-EV amplifiers; ruin_prob = 1.000 (L99). | **BLACKLIST** |
| S10 | Web "lottery predictor" services / number generators claiming edge | (various) | No evidence; scam-adjacent; violate governance. | **BLACKLIST** |

[Confirmed-external] NIST SP 800-22's stated purpose is to **detect non-random patterns** in (P)RNG output for cryptographic validation — i.e. it confirms/falsifies randomness; it does not forecast next values.
[Confirmed-external] The unpopular-number literature consistently finds that choosing unpopular combinations raises *expected winnings via reduced prize-sharing*, not the probability of winning; "7" is universally over-picked.

---

## 4. Already-In-System Audit (maps external methods → what LotteryNew already enforces)

| External method (proposed) | Already in LotteryNew? | Where |
|---|---|---|
| Pre-registered anti-overfit gate | **YES** | P221F |
| Multiple-testing correction (Bonferroni/BH) | **YES** | P222 / P223B / P227C |
| Walk-forward / rolling-window OOS | **YES** | RSM / P114 / P224 |
| Three-window validation (150/500/1500) | **YES** | standard pipeline / CLAUDE.md |
| Permutation test | **YES** (with L96 Monte-Carlo-null fix) | standard pipeline |
| McNemar replacement gate | **YES** | L48/L61, standard pipeline |
| Random/baseline comparison | **YES** | RSM / per-game baselines |
| **Formal randomness-audit SSOT + tripwire (NIST-style)** | **NO — this is the gap** | *(recommended P236-followup, design-only)* |

[Inferred] **7/8 confirmed already-owned**, consistent with the P234 CEO finding. The single net-new diagnostic worth importing is the randomness-audit SSOT/tripwire (§7).

---

## 5. Candidate Feature Families (DESIGN-ONLY, expected NULL)

[Inferred] If a future, separately-authorized diagnostics layer is built, the Lofea-inspired native re-derivations worth *describing* (never as predictors) are:

| Family | Native framing | Status |
|---|---|---|
| **Universe length** | distinct-number breadth in a rolling K-draw window + its dynamics | descriptive only; mostly novel framing; expected NULL under the gate |
| **In-frame vs out-of-frame frequency split** | mean/median frequency of numbers inside vs outside the current rolling frame | descriptive only; partial overlap with midfreq |
| Gap / cold / recency, parity, zone, markov | — | **already implemented**; no new import |

[Confirmed] All such families must be **independently re-derived** in native code (CC-BY-NC bars vendoring), pass §6, and default to NULL.

---

## 6. Mandatory Validation Rubric (the gate every candidate MUST pass before any edge claim)

[Confirmed] Derived from CLAUDE.md + lessons. A candidate may claim edge **only** if it passes **all**:

1. **Pre-registration (P221F):** hypothesis, windows, and statistic fixed *before* touching OOS data.
2. **Null/baseline SSOT:** per-game random baseline is the reference (e.g. DAILY_539 M3+ rate; POWER_LOTTO second-zone 1/8 = 0.125; BIG_LOTTO 6×6/49). State it explicitly.
3. **Three-window validation:** 150 / 500 / 1500, **all** ROI > baseline.
4. **Permutation test p < 0.05**, using a **Binomial(baseline) Monte-Carlo null** (not label-shuffle, which preserves the mean → p=1.0, L96).
5. **Walk-forward / OOS** (TimeSeriesSplit-style expanding window), **≥ 500 OOS draws** (L101); statistical unit = distinct draws.
6. **Multiple-testing correction** (Bonferroni/BH) across candidates × bet-slots × thresholds × windows (L47).
7. **McNemar vs incumbent** — replacement requires p < 0.05 (L48/L61); passing the gate ≠ beating production (L76/L88).
8. **Coverage-normalized** comparison at fixed bet count (no geometric-benefit trap, L37).
9. **Sharpe > 0** *and* honest economic note (all games remain −EV; ruin_prob = 1.000, L99).
10. **Reproducibility:** fixed seed, data snapshot, version tag (CLAUDE.md full-traceability).
11. **NULL = success.** In-sample improvement may never be claimed as generalizable.

---

## 7. The Two Genuinely Net-New Imports (both read-only, neither is hit-rate)

### 7.1 NIST-style Randomness-Audit SSOT + Tripwire — `RECOMMENDED net-new (design-only)`

- [Inferred] **What:** a read-only module that runs an SP 800-22-adapted battery (frequency/monobit, runs, longest-run, serial, approximate-entropy, cumulative-sums, etc.) over each lottery's historical draw stream, producing a single canonical "randomness audit" report that becomes the **SSOT null baseline** all strategy research must cite.
- [Inferred] **Why it matters (the honest reframe of the user's goal):** these lotteries are fair-random *today*, so they cannot be predicted. But if an operator's draw mechanism ever developed a bias (new machine/RNG), prediction would become possible. A continuous randomness audit is a **tripwire**: green = stay closed (no edge possible); a sustained, multiplicity-corrected fail = the *only* evidence-based trigger to reopen prediction research.
- [Confirmed] **What it is NOT:** not a predictor, not an edge, not betting advice. Diagnostics-only.
- [Confirmed] **Boundaries:** read-only; no DB write (or write only to an `outputs/` artifact); per-game; multiple-testing-corrected (15 tests × games → false-positive inflation otherwise); reproducible seed/snapshot.

### 7.2 Payout / Anti-Crowd Expected-Value — `OPTIONAL read-only spike`

- [Confirmed-external] Choosing unpopular numbers raises **E[payout | win]** by reducing jackpot-sharing; it does **not** raise P(win) and does **not** make EV positive.
- [Confirmed] **Already partially tested — L102:** anti-crowd on BIG_LOTTO is **ADVISORY_ONLY** (perm p=0.257 not significant, swap rate 0.7%, w100=+0.00%).
- [Inferred] A read-only spike could extend L102 with the external literature's popularity priors (birthdays ≤31, "lucky 7", sequences/patterns), **strictly labeled payout-not-hit-rate**, gated by §6. Expected: marginal at best.

---

## 8. Risks

1. **False-predictability framing** — the whole exercise risks being read as "we found a way to win." Every artifact must fence this: hit-rate is closed; deliverables are diagnostics/payout only.
2. **Re-treading paid-for NULLs** — broad scouting largely repeats P234 (7/8 owned), P235A (Lofea), P178A (POWER_LOTTO), L82/L91 (539/BIG closed). Cost without new information unless scoped to the §7 net-new items.
3. **Multiple-testing on the audit itself** — running 15 NIST tests × 4 games × windows will *manufacture* failures by chance; the tripwire must be multiplicity-corrected or it becomes a false-alarm generator.
4. **ML overfit (S6)** — low base-rate games overfit catastrophically (L86 +6.5%→+0.12%; L89 ratio 10.35x). ML is falsification-only; never a deploy path.
5. **Payout ≠ hit-rate confusion (S8)** — must never be reported as improving win odds; EV stays negative.
6. **Vendoring / license (S7)** — Lofea CC-BY-NC; concepts must be native re-derived, not copied.
7. **Leakage** — multi-draw labels/windows can leak future draws; enforce data-leakage-prevention.
8. **Scope creep into implementation** — this task is scouting only; building §7 requires separate authorization.

---

## 9. Governance Checks

| Rule | Status |
|---|---|
| Historical/diagnostic-only evidence | respected |
| No betting advice | respected |
| No predictability / win-rate claim | respected — hit-rate explicitly closed |
| P221F anti-overfit gate required for any reuse | required |
| Multiple-testing correction required | required (incl. the audit battery itself) |
| Walk-forward / OOS before any validation use | required (≥500 draws) |
| Statistical unit = distinct draws | enforced |
| Zero DB / registry / production write | respected (artifact-only) |
| No strategy promotion | respected |
| P211 `HELD_BY_USER` | unchanged |
| P234 design-only / diagnostics-only | unchanged; this scout sits under it |
| Lofea = DESIGN_INSPIRATION_ONLY (P235A) | unchanged |

---

## 10. DB Baseline (verified read-only this session)

| Check | Value |
|---|---|
| HEAD == origin/main | `03ba6d1` ✅ |
| DB integrity | ok ✅ |
| Replay rows | 94,924 ✅ |
| bet_index nulls | 0 ✅ |
| Duplicate keys | 0 ✅ |
| Drift guard | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` ✅ |

---

## 11. Recommendation

| Question | Answer |
|---|---|
| Adopt a new predictor now? | **NO** (hit-rate closed; L82/L91/P178A) |
| Net-new external method worth importing? | **ONE** — NIST-style randomness-audit SSOT/tripwire (diagnostics-only), as a separately-authorized read-only build (§7.1) |
| Optional secondary? | Payout/anti-crowd EV read-only spike, labeled payout-not-hit-rate, with L102 caveat (§7.2) |
| Broad ML / Bayesian scouting? | Falsification/benchmark-only; do not deploy |
| Lofea? | DESIGN_INSPIRATION_ONLY (unchanged) |
| Do-nothing? | Valid default — 7/8 methods already enforced |

**Smallest safe next step (if authorized):** a read-only design-doc for the randomness-audit SSOT (§7.1) — still no build, no DB. Any build is a separate authorization.

---

## 12. Verification

| Check | Value |
|---|---|
| External sources fetched/verified | S1–S8 ✅ (this session) |
| JSON parse | PASS (`python3 -m json.tool`) |
| `git diff --check` | PASS |
| Drift guard after | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` |
| DB unchanged | 94,924 / integrity ok |
| Full pytest suite | **NOT RUN** (scouting / artifact-only task) |

No code, DB, registry, production, or recommendation files were changed. This task produced only the two whitelisted artifact files.

**Final Classification:** `P236A_EXTERNAL_STAT_METHODS_SCOUTING_COMPLETE_FALSIFICATION_AND_DIAGNOSTICS_ONLY`
