# P241B P234 Statistical Diagnostics Inventory

**Date:** 2026-06-05
**Classification:** `P241B_P234_STATISTICAL_DIAGNOSTICS_INVENTORY_COMPLETE`
**Task Type:** Type B (read-only design doc / artifact) under P240D governance simplification rules
**Status:** Design/inventory only — no code implementation, no DB write, no registry mutation
**Authorization:** `Authorize P241B P234 statistical diagnostics inventory (read-only design doc, no code changes)`
**Source:** P234/P234A CEO `CEO_DECISION_PARTIALLY_APPROVED`; P2.4 statistical diagnostics layer authorized as design-only (OPT-C)

---

## 1. Scope and Non-Goals

### In Scope
- Inventory of existing statistical diagnostic methods visible in project history and governance files
- Gap analysis: what is documented vs. standardized vs. missing
- Proposed feature-bottleneck report schema (field definitions only)
- Implementation gate language for future work
- Task classification and same-PR closeout rationale under P240D

### Explicitly Out of Scope

| Forbidden Item | Reason |
|---|---|
| Executable diagnostic module | Requires separate explicit authorization |
| DB write | Not authorized in this task |
| Registry mutation | Not authorized in this task |
| Production / recommendation / monitoring change | Not authorized in this task |
| Controlled apply | Not authorized in this task |
| Strategy promotion or adapter | Not authorized in this task |
| Prediction edge claim | No deployable edge exists in any lottery |
| Betting advice | Never authorized |
| P211 restart | HELD_BY_USER; requires explicit "Start P211" |
| New NIST build | P238B YELLOW is observation-only; no confirmation task authorized |

**This artifact makes no claim about lottery prediction edge, win rate, or betting advice. All classification is retrospective research metadata.**

---

## 2. Inventory of Existing Diagnostic Methods

The following methods are documented and applied across the project's P211A–P241B research chain. Each is annotated with: where it is used, how it is applied, and standardization status.

### 2.1 Multiple-Testing Controls

#### Bonferroni Correction
- **Applied in:** P222 cross-lottery scan (35 strategies × 14 bet-index × 3 lotteries = 1,470 hypotheses), P227C 3_STAR/4_STAR scan (120 hypotheses), P223B candidate OOS validation
- **Method:** α/K threshold where K = number of simultaneous hypotheses
- **Status:** Applied ad hoc per task; threshold recalculated each time without a shared reference constant
- **Gap:** No centralized family-size register; each task re-derives K independently

#### Benjamini-Hochberg FDR
- **Applied in:** P222, P227C (secondary to Bonferroni)
- **Method:** Rank-order p-values; reject H_i if p_(i) ≤ (i/K)·q where q = 0.05
- **Status:** Applied inconsistently; some tasks use BH as secondary only, others omit it
- **Gap:** No agreed q threshold documented in a shared reference

### 2.2 Rolling-Window Validation

#### Short Windows (100 / 125 / 150 draws)
- **Applied in:** P221F (protocol freeze), P222, P223B, P224, P227C
- **Method:** Compute hit rate or other metric over the most recent N draws
- **Status:** Frozen by P221F as canonical short-window set
- **Gap:** Window boundaries are in a governance doc, not enforced by any executable gate

#### Mid Windows (500 / 750 / 1000 draws)
- **Applied in:** P221F, P222, P223B, P224, P227C
- **Status:** Frozen by P221F
- **Gap:** Same as short windows — governance doc only, no code enforcement

#### All-History (reference only)
- **Applied in:** P221F
- **Status:** Demoted to reference-only; must not be used as a gating condition
- **Gap:** No explicit code check preventing it from being used as a primary filter

### 2.3 Out-of-Sample / In-Sample Separation

#### Forward OOS (future draws relative to training period)
- **Applied in:** P224 (clean-slice), P223B (cross-year), P222 (mid/short windows post-training)
- **Method:** Train on historical slice; evaluate on temporally later slice
- **Status:** Applied correctly in P224 clean-slice dedup; prior P223B slice was overlapping (corrected)
- **Gap:** No shared leakage-guard function; each task implements its own temporal split

#### Backward OOS (older draws not seen during forward analysis)
- **Applied in:** P230A plan, P230B1 execution (4,265 draws 2007/05–2021/08), P231B (382 draws 2008–2012)
- **Method:** Extend analysis to older draws that were not part of the forward-OOS window; ordinal predecessor boundary, not numeric subtraction
- **Status:** Implemented as one-off scripts per task
- **Gap:** Leakage guard logic is duplicated across P230B1 and P231B scripts; no shared reference implementation

### 2.4 Permutation / Random Baseline Comparison

#### Monte Carlo Null Baseline
- **Applied in:** P227C (Bonferroni threshold derivation), P238B (NIST frequency test comparison)
- **Method:** Shuffle draw labels or generate synthetic draws; compare observed metric to null distribution
- **Status:** Applied in P227C for hypothesis threshold; P238B for randomness audit
- **Gap:** MC baseline parameters (n_simulations, seed policy, shuffle method) undocumented across tasks; L96 lesson records a bug in shuffle-label permutation for RL

#### Binomial Baseline
- **Applied in:** P224 (hit rate vs. baseline 0.6410), P230B1, P231B
- **Method:** Compare observed hit_count mean to theoretical baseline (e.g., 1/C(39,5))
- **Status:** Baseline values are computed per task from DB row counts; no centralized baseline registry
- **Gap:** Baseline value recomputed each task; risk of drift if DB changes

### 2.5 Stability and Robustness Checks

#### Block Stability
- **Applied in:** P224, P230B1, P231B
- **Method:** Divide draws into temporal blocks; check if metric is above baseline in majority of blocks
- **Status:** Applied ad hoc; block count and minimum fraction threshold vary per task
- **Gap:** No agreed block count or minimum-pass fraction defined as a project standard

#### Robustness Checks (exclude outliers)
- **Applied in:** P224 (exclude hit=3 rows), P230B1, P231B (exclude strongest block)
- **Method:** Drop high-influence observations; recompute metric; check sign stability
- **Status:** Applied per task; specific exclusion criteria differ
- **Gap:** No standard robustness battery defined

### 2.6 Drift Detection

#### PSI (Population Stability Index)
- **Applied in:** RSM pipeline (`lottery_api/engine/rolling_strategy_monitor.py`)
- **Method:** Compare distribution across windows; STABLE < 0.1, WARNING 0.1–0.2, DRIFT > 0.2
- **Status:** Operationalized in RSM; threshold constants defined in engine code
- **Gap:** PSI not incorporated into research-phase diagnostic reports; exists only in production RSM

#### Replay Lifecycle Drift Guard
- **Applied in:** All P2xx tasks (Phase 0 verification)
- **Method:** `scripts/replay_lifecycle_drift_guard.py --strict`; checks row count, bet_index nulls, duplicate keys
- **Status:** Standardized across all tasks; enforced in Phase 0
- **Gap:** None — this is the most standardized diagnostic in the project

### 2.7 Randomness Audit

#### NIST SP 800-22 Style Diagnostics
- **Applied in:** P237C (design), P238A (plan), P238B (artifact build)
- **Method:** Frequency (monobit), block frequency, runs, serial, autocorrelation tests on draw sequences
- **Status:** Artifact-only; P238B result is YELLOW (observation-only); ORANGE/RED not observed; no strategy implication
- **Boundary:** This diagnostic does not improve prediction or win rate. YELLOW = observation-only. RED = human diagnostic review only, never strategy or production change.
- **Gap:** Tests use a custom Python implementation; no shared test-vector cross-validation vs. NIST reference

### 2.8 Significance Testing

#### One-Sided Z-Test / T-Test on Hit Rate
- **Applied in:** P224, P230B1, P231B, P227C
- **Method:** Compare observed mean hit rate to theoretical baseline; compute p-value under normal approximation
- **Status:** Applied per task; α threshold = 0.05 project-wide
- **Gap:** No shared significance-test helper; each task re-implements the test

#### McNemar Test (paired comparison)
- **Applied in:** P222/P223B (strategy vs. baseline), referenced in L48/L61
- **Method:** Compare two paired binary outcomes to detect directional improvement
- **Status:** Required before any strategy replacement (L48); applied in P222/P223B
- **Gap:** Gate threshold (p < 0.05) documented in lessons (L48/L61) but not in a shared reference doc

---

## 3. Gap Analysis

### 3.1 Standardization Gaps

| Gap | Description | Risk if Unresolved |
|---|---|---|
| No centralized family-size register | Each task recalculates K for Bonferroni independently | Inconsistent multiple-testing correction across tasks |
| No shared baseline registry | Baseline hit-rate values (e.g., 0.6410 for DAILY_539) recomputed each task | Baseline drift if DB changes; inconsistent comparisons |
| No shared leakage-guard | Temporal split logic duplicated in P230B1, P231B | Subtle leakage could be introduced in future tasks |
| No shared significance-test helper | One-sided z-test re-implemented per task | Copy-paste divergence; risk of bug propagation |
| No agreed block count / robustness battery | Block stability uses different parameters per task | Non-comparable stability results across tasks |
| P221F windows in governance doc only | Short/mid window constants not enforced by code | Future task could silently deviate from frozen protocol |

### 3.2 Documentation Gaps

| Gap | Description |
|---|---|
| No feature-bottleneck report schema | No standard format for explaining why a strategy failed (e.g., pool size, sample size, signal dilution) |
| No promotion-blocker vocabulary | No standard set of allowed_next_action / forbidden_next_action labels |
| No confidence-language template | No agreed phrasing for YELLOW / MARGINAL / NULL results in reports |
| No McNemar gate reference doc | L48/L61 in MEMORY.md, but no governance doc with the threshold |
| PSI thresholds only in production code | PSI constants (STABLE/WARNING/DRIFT) not documented in research governance |

### 3.3 Overclaiming Risks

| Risk | Description | Mitigation |
|---|---|---|
| YELLOW misread as signal | P238B YELLOW observation is not a prediction edge | P238B boundary language in all governance files; `predictability_claim: false` in JSON |
| Weak p-value elevated | p=0.067 (P224) or p=0.055 (P231B P1 edge) cited as near-significant | Required Completion Check must state p-value explicitly; L76 lesson: pass gate ≠ better than existing |
| Underpowered sample over-promoted | 3_STAR/4_STAR 0 Bonferroni promoted as "weak signal" | UNDERPOWERED_NO_SIGNAL classification; sample-size field in report schema |
| MC null comparison not documented | Observed p=0.005 not compared to expected null distribution | MC null baseline required field in report schema |

---

## 4. Proposed Feature-Bottleneck Report Schema

This schema defines the fields for a standardized per-strategy, per-task diagnostic report. **No implementation is authorized in P241B.** The schema is a design specification only.

### 4.1 Identity Fields

| Field | Type | Description |
|---|---|---|
| `task_id` | string | Canonical task identifier (e.g., `P241B`) |
| `report_date` | ISO-8601 | Date of report generation |
| `lottery_type` | enum | `BIG_LOTTO`, `DAILY_539`, `POWER_LOTTO`, `3_STAR`, `4_STAR` |
| `strategy_id` | string | Strategy identifier or `null` for lottery-level diagnostics |
| `diagnostic_subject` | string | Human-readable description of what is being tested |
| `lifecycle_status` | enum | `ONLINE`, `RETIRED`, `REJECTED`, `OBSERVATION`, `DRY_RUN`, `NON_EXECUTABLE_STUB` |

### 4.2 Sample and Window Fields

| Field | Type | Description |
|---|---|---|
| `sample_size` | integer | Number of draws or bet-rows analyzed |
| `window_definition` | string | E.g., `short_150`, `mid_500`, `full_1500`, `backward_oos_4265` |
| `is_oos` | boolean | True if window is out-of-sample relative to any optimization |
| `split_boundary` | string | Ordinal draw ID at the IS/OOS boundary |
| `family_size_k` | integer | Number of simultaneous hypotheses tested |

### 4.3 Baseline and Metric Fields

| Field | Type | Description |
|---|---|---|
| `baseline_method` | string | How baseline was computed: `theoretical` (1/C(n,k)), `empirical_full`, `monte_carlo` |
| `baseline_value` | float | Numerical baseline hit rate or metric value |
| `observed_metric` | float | Observed hit rate or metric value |
| `delta_vs_baseline` | float | `observed_metric - baseline_value` |
| `n_blocks` | integer | Number of temporal blocks used for stability check |
| `blocks_above_baseline` | integer | Count of blocks where metric > baseline |

### 4.4 Statistical Fields

| Field | Type | Description |
|---|---|---|
| `p_value_raw` | float | Raw (uncorrected) p-value |
| `correction_method` | enum | `bonferroni`, `benjamini_hochberg`, `none` |
| `corrected_threshold` | float | Adjusted significance threshold after correction |
| `is_corrected_significant` | boolean | `p_value_raw <= corrected_threshold` |
| `mc_null_99th_pct` | float | 99th percentile of null distribution from MC simulation (or `null`) |
| `is_above_mc_noise_floor` | boolean | `observed_metric > mc_null_99th_pct` |

### 4.5 Robustness Fields

| Field | Type | Description |
|---|---|---|
| `robustness_check_description` | string | E.g., "exclude hit≥3 rows", "exclude strongest block" |
| `robustness_metric` | float | Metric value after robustness exclusion |
| `robustness_sign_stable` | boolean | True if robustness metric remains above baseline |
| `drift_guard_result` | enum | `PASS`, `FAIL`, `NOT_RUN` |
| `psi_value` | float | PSI value if available; `null` otherwise |
| `psi_status` | enum | `STABLE`, `WARNING`, `DRIFT`, `NOT_RUN` |

### 4.6 Feature-Bottleneck Fields

| Field | Type | Description |
|---|---|---|
| `feature_bottleneck` | string | Primary explanation for null/weak result. Examples: `pool_too_large_49C6`, `sample_too_small`, `signal_diluted_by_multiple_testing`, `historical_artifact`, `cross_year_unstable`, `regime_change` |
| `min_detectable_effect` | float | Minimum edge detectable at current sample size with power=0.80 |
| `power_at_observed_effect` | float | Statistical power at observed delta |
| `overfit_ratio` | float | train_metric / oos_metric (>2 indicates overfit concern) |

### 4.7 Classification and Gate Fields

| Field | Type | Description |
|---|---|---|
| `classification` | string | Final classification (e.g., `REJECTED_BY_BACKWARD_OOS`, `UNDERPOWERED_NO_SIGNAL`, `WAIT_FOR_OOS`, `OBSERVATION_ONLY`) |
| `blocker_classification` | string | Specific blocker label (e.g., `P221F_GATE_NOT_PASSED`, `MCNEMAR_NOT_SIGNIFICANT`, `DB_WRITE_NOT_AUTHORIZED`) |
| `allowed_next_action` | list[string] | Permitted actions given current evidence |
| `forbidden_next_action` | list[string] | Explicitly forbidden actions given current evidence |

### 4.8 Confidence and Safety Fields

| Field | Type | Description |
|---|---|---|
| `confidence_language` | string | Required phrasing for communicating this result. Example: `"Historical hit-rate evidence only; not a betting recommendation; edge not independently confirmed."` |
| `human_review_required` | boolean | True if result warrants human review before any downstream use |
| `db_write_authorized` | boolean | Whether DB write is currently authorized for this strategy |
| `registry_write_authorized` | boolean | Whether registry change is authorized |
| `production_authorized` | boolean | Whether production/recommendation change is authorized |
| `betting_advice` | boolean | Always false; this system produces no betting advice |
| `nist_alert_level` | enum | `GREEN`, `YELLOW`, `ORANGE`, `RED`, `NOT_RUN`; YELLOW = observation-only; RED = human review only |

---

## 5. Implementation Gate Language

Any future implementation of this schema as an executable module requires **separate explicit user authorization** beyond this design document.

Specifically, the following actions are **not authorized by P241B**:

1. Building a `statistical_diagnostics.py` module or any diagnostic runner script
2. Adding a new API endpoint for diagnostic reports
3. Writing diagnostic results to the DB
4. Modifying `replay_strategy_registry.py` to add schema fields
5. Running PSI or rolling-window checks in production code
6. Creating any cron/monitoring job for diagnostic reporting
7. Changing any recommendation or confidence logic

**Proposed future task (requires separate authorization):**

> *"Authorize P242 read-only statistical diagnostics schema implementation (no DB write, no production change)"*
>
> P242 would implement the schema as a read-only Python module with targeted tests, following P240D Type C rules (additive code, no DB write, no existing production path modification).

---

## 6. Task Classification (P240D Type B)

### Why This is Type B

This task produces read-only Markdown and JSON artifacts only. No code is added. No DB write. No registry mutation. Under P240D §Task Type Classification:

- **Type B** applies when a task produces read-only design doc or artifact files with no code changes.
- **Same-PR closeout is allowed** because:
  - All changes are read-only (no DB, registry, or production code)
  - Governance changes affect ≤4 files and add ≤120 governance lines
  - CI passes on a single PR
  - No merge conflict

### Why No Separate Closeout PR is Needed

Under P240D Type B rules, the artifact creation PR (`p241b-p234-statistical-diagnostics-inventory`) includes governance closeout updates to `active_task.md`, `CURRENT_STATE.md`, `roadmap.md`, and `CEO-Decision.md` in the same commit. No P241C closeout PR is required.

---

## 7. Recommended Next Options After P241B

After P241B is merged, the system returns to `WAITING_FOR_USER_AUTHORIZATION`. The following options are available, each requiring separate explicit authorization:

| Option | Authorization Phrase | Type | Priority |
|---|---|---|---|
| Adopt no implementation; remain WAITING | *(none needed — system waits)* | — | Default |
| Authorize P242 diagnostics schema implementation | `"Authorize P242 read-only statistical diagnostics schema implementation (no DB write, no production change)"` | C | Medium |
| Start P211 short/mid-window diagnostic | `"Start P211"` | C | User-triggered |
| NIST confirmation design (if new draws available) | `"Authorize P242 NIST confirmation design (read-only, observation-only)"` | B | Low |
| Remain HOLD | *(none needed)* | — | Valid |

**Recommended:** If the user wants to make the diagnostics schema actionable, authorize P242 as a Type C additive implementation (no DB write). If the user wants new statistical research, authorize P211 restart.

---

## 8. No-Claim Attestation

This artifact:
- Makes **no claim** about lottery number predictability
- Makes **no claim** about improved win rate
- Provides **no betting advice**
- Does not authorize any strategy, production, recommendation, monitoring, or DB change
- Does not escalate P238B NIST YELLOW result
- Does not restart P211
- Represents research governance metadata only
