# P235A — Lofea Read-Only Feasibility Review For LotteryNew

**Task ID:** P235A
**Date:** 2026-06-04 Asia/Taipei
**Type:** Read-only feasibility review (no implementation, no DB/registry/production write, no strategy, no betting advice, no predictability claim)
**Authorization:** User authorized OPT-B P235A (2026-06-04); consistent with `CEO-Decision.md` → `CEO_DECISION_PARTIALLY_APPROVED`.
**Source:** <https://github.com/JeffMv/Lofea> (fetched and corroborated by two independent researchers)

**Final Classification:** `P235A_LOFEA_FEASIBILITY_REVIEW_COMPLETE_DESIGN_INSPIRATION_ONLY`

---

## 1. Executive Summary

[Confirmed] Lofea is a small, single-author, Python-only open-source toolkit (CC-BY-NC) that **engineers statistical features from lottery draw histories** and emits ready-to-model TSV/CSV tables (features + supervised-learning labels) for a data scientist to feed into an **external** ML environment. It is **not** a predictor and ships **no validated deployable edge**.

[Confirmed] It targets small-universe **"pick 1-out-of-10 per column"** lotteries (Swiss *TrioMagic*, Belgian *Joker+*) whose raw data is positionally-ordered single-digit columns — **structurally different** from LotteryNew's main-numbers+bonus games (BIG_LOTTO 6/49+special, POWER_LOTTO 6 main + 1 second-pool, DAILY_539 5/39).

[Inferred] Lofea's value to LotteryNew is **conceptual only** (feature-design inspiration). Its headline ideas — a "Universe length" distinct-symbol-count feature, gap/ecart trend deltas, an in-frame-vs-out-of-frame frequency split, parity, rolling-window framing, and a binary group-membership reframing — are legitimate design inspiration but **mostly already implemented** in LotteryNew, and **none transfer directly** because of data-structure and statistical-unit mismatches.

**Bottom line: adopt now = NO.** Note as design inspiration only for the already-demoted **P2.4 / Direction F** read-only diagnostics layer. Lofea independently arriving at no validated edge reinforces LotteryNew's own lessons (L82/L86/L89/L90/L91) that small-sample lottery "edges" fail validation and **NULL is a valid successful result.**

---

## 2. Source / Identification Status

**Status: `CONFIRMED`** — source fully identified, fetched, and corroborated by two independent researchers on all material points. **Not** `BLOCKED_NEEDS_SOURCE_OR_CLARIFICATION`.

| Attribute | Finding | Confidence |
|---|---|---|
| URL | <https://github.com/JeffMv/Lofea> | [Confirmed] |
| Language / size | Python-only; 31 commits; 2 open issues; 0 open PRs | [Confirmed] |
| Stars / forks | ~40 / ~17 (handoff figure; one researcher could not independently re-confirm exact counts) | [Inferred] approximate |
| Snapshot | README states it is "a specific snapshot of another project"; parent project **not named** | [Confirmed] snapshot; [Unknown] parent name |
| License | **CC-BY-NC** (Attribution-NonCommercial); README invites contact for commercial licensing | [Confirmed] |
| Last activity | Example data dated 2019-12; exact last-commit date not surfaced | [Inferred] ~2019 / dormant; [Unknown] exact date |
| Disclaimer | **No explicit "does not predict winning numbers" disclaimer**; non-prediction stance is implicit in the binary-classification methodology only | [Confirmed-negative] |

**Handoff correction (noted for honesty):** the original handoff's implicit "Western / main+bonus" framing was **wrong** — direct inspection of `data/example-inputs/TrioMagic-results.txt` shows positional single-digit columns (`gch`/`mil`/`drt`, each 0–9), i.e. a **1/10-per-column** structure.

---

## 3. Fit Assessment — `FIT_AS_DESIGN_INSPIRATION_ONLY`

[Confirmed] **Deployable strategy evidence: NONE.** No backtest, no ROI/Sharpe, no statistical-significance or permutation testing, no walk-forward/OOS, no baseline comparison. The only performance signal is an **anecdotal** personal-play story in the README; the only modeling artifact is a RapidMiner 8 AutoModel demo classifying a binary feature outcome (Universe-length increase).

**Why `FIT_AS_DESIGN_INSPIRATION_ONLY` (not the alternatives):**
- Not `BLOCKED_*` — the source is fully identified and corroborated.
- More than `FIT_AS_DIAGNOSTIC_REFERENCE_ONLY` — Lofea offers **schema/labeling/methodology** ideas (feature/label table separation, group-membership binary reframing), not just ready-made diagnostics.
- Not `NOT_FIT_RANDOM_LOTTERY_DOMAIN` — some genuine conceptual value exists, even though the domain is treated as fair-random.

**Concepts worth noting as inspiration (historical-description only, never predictors):**

| Concept | Note for LotteryNew |
|---|---|
| **Universe length** (distinct-number breadth in a rolling K-draw window) + dynamics | A "breadth of recent number space" diagnostic **not obviously tracked** in that exact framing. Candidate descriptive column. |
| **In-frame vs out-of-frame frequency split** (MeanEffsIn/Out) | A notable framing of frequency; LotteryNew has midfreq/frequency diagnostics but maybe not this split. |
| Gap / ecart trend deltas | **Heavily overlaps** existing LotteryNew gap/cold/recency diagnostics. |
| Parity / odd-even, rolling-window framing | **Already covered** (RSM, draw analyses). |
| Group-membership binary reframing | A labeling/evaluation idea for honest, tractable diagnostic units — **not** a betting method. |
| Trend / horizon appearance labels | A clean way to define diagnostic labels for historical (OOS/walk-forward) description. |
| Per-column positional frequency | Only conceptually relevant to 3_STAR/4_STAR, and even there **blocked** because the DB stores numbers sorted (positional semantics lost). |

---

## 4. Risks

1. **False-predictability framing** — prediction-flavored columns (`pred*`, `tTarget*`) + anecdotal "2-of-3 hits" story. Importing this language risks an implied win-rate claim that **violates governance**.
2. **Data-snooping / p-hacking** — many candidate features, **no** multiple-testing correction, **no** permutation/walk-forward in Lofea. Naive adoption inflates false positives → must pass the **P221F gate**.
3. **Training-data leakage** — `RelatedDrawId` / within-N-draws / gap-trend labels span multiple draws; careless reimplementation could leak future draws into a historical window → must enforce leakage-prevention rules.
4. **Statistical-unit mismatch** — Lofea's unit is per-symbol-per-column in a 1/10 game; LotteryNew requires strict **row/draw/bet-index/strategy** labels.
5. **Taiwan-lottery data-semantics mismatch** — Lofea assumes 1/10 **positionally-ordered** per-column draws; LotteryNew's `numbers` are stored **ascending-sorted** (e.g. BIG_LOTTO `[8,9,16,20,37,49]`, 4_STAR `[0,1,5,6]`), so positional/per-column features **do not transfer**.
6. **Redundancy** — LotteryNew already implements gap/cold/recency, frequency/midfreq, parity, zone, and markov diagnostics; most Lofea features are duplicative (low marginal value).
7. **CC-BY-NC license / vendoring** — NonCommercial license. **WebComm Technology is a commercial entity**, so vendoring/redistributing Lofea code or derivatives without separate commercial permission would **breach the license**. Prefer independent re-derivation of any concept.
8. **Security / supply-chain** — Lofea pulls a pinned author package (`git+https://github.com/JeffMv/jmm-util-libs.git`) and runs arbitrary CLI; **must not be run** inside the LotteryNew/production environment.
9. **Dormancy / reproducibility** — code/data appear ~2019-era and dormant; the pinned external dependency could disappear, undermining reproducibility (counter to full-traceability).
10. **Promotion-pressure** — risk a reader treats Lofea as a strategy; it must be fenced as design-inspiration only, zero implied edge.

---

## 5. Compatibility With LotteryNew Governance

| Governance rule | Status in this review |
|---|---|
| Historical-only evidence | Respected — Lofea treated as historical/descriptive inspiration only |
| No betting advice | Respected |
| No predictability / win-rate claim | Respected — Lofea has **no** validated edge |
| P221F anti-overfit gate before any reuse | **Required** |
| Multiple-testing correction | **Required** for any multi-feature reuse |
| Walk-forward / OOS before validation use | **Required**; backward-OOS may only falsify |
| Statistical-unit labels (row/draw/bet-index/strategy) | **Required**; Lofea concepts must be relabeled, not lifted |
| Zero DB / registry / production write | Respected (artifact-only) |
| No strategy promotion | Respected |
| P211 `HELD_BY_USER` | Unchanged |
| P234 design-only (P2.4 / Direction F) | Unchanged — Lofea fits *under* this demoted, not-yet-authorized concept |

---

## 6. Explicit Forbidden Boundaries

- **Do NOT** implement Lofea or vendor/copy its code (CC-BY-NC; commercial entity).
- **Do NOT** run Lofea or its pinned external dependency inside the LotteryNew/production environment.
- **Do NOT** create a strategy, hypothesis scan, or predictor from Lofea concepts without separate explicit authorization + full P221F pre-registration.
- **Do NOT** write DB / registry / production / data / recommendation logic.
- **Do NOT** frame Lofea or any borrowed concept as improving win rate or predictability.
- **Do NOT** produce betting advice; **do NOT** promote any candidate; **do NOT** restart P211; **do NOT** start OPT-C without separate authorization.

---

## 7. Recommendation

| Question | Answer |
|---|---|
| Adopt now? | **NO** |
| Design-only future consideration? | **YES** — note as design inspiration for the already-demoted **P2.4 / Direction F** read-only diagnostics layer; **no build** authorized. |
| No further action? | **Acceptable default** — LotteryNew already has equivalent diagnostics and an exhausted-signal reality; doing nothing is a valid outcome. |

**Authorization needed for any next step:** any concept reuse requires (1) separate explicit user authorization, (2) **native re-derivation** in LotteryNew code (no vendoring), (3) fresh **P221F** pre-registration with multiple-testing correction and walk-forward/OOS, (4) read-only / artifact-only scope with **zero** DB/registry/production writes.

If the user wants to go further, the smallest safe next step is **OPT-C** (a read-only P234 statistical-methods diagnostics **inventory** design-doc) that *cites* Lofea's Universe-length and in/out-frequency framings as inspiration — still design-only, no build.

---

## 8. Verification (read-only)

| Check | Value |
|---|---|
| HEAD == origin/main | `8b70aeeb` ✅ |
| DB integrity | ok ✅ |
| Replay rows | 94,924 ✅ |
| bet_index nulls | 0 ✅ |
| Duplicate keys | 0 ✅ |
| Drift guard | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` ✅ |
| JSON parse | PASS (`python3 -m json.tool`) |
| Full pytest suite | **NOT RUN** (artifact-only task) |

No code, DB, registry, production, or recommendation files were changed. This task produced only the two whitelisted artifact files.

**Final Classification:** `P235A_LOFEA_FEASIBILITY_REVIEW_COMPLETE_DESIGN_INSPIRATION_ONLY`
