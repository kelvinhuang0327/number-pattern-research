# P253G Feature Bottleneck Report Inventory

**Task ID:** P253G  
**Classification:** `FEATURE_BOTTLENECK_REPORT_INVENTORY_COMPLETE`  
**Generated:** 2026-06-08T02:08:36.542172+00:00  

---

## Executive Summary

P253G is a read-only Type B inventory of all existing artifacts, scripts, and metrics related to feature bottleneck analysis, mutual information (MI), entropy diagnostics, and evidence channels in the LotteryNew project.

**Key findings:** P219 M10 provides the only functioning MI implementation (trailing_freq only) with near-zero results for DAILY_539 (8.8e-6 bits) and POWER_LOTTO (1.6e-5 bits). The schema field `feature_bottleneck` exists in `statistical_diagnostics_schema.py` but no module fills it. Six unresolved terminology gaps (TG1-TG6) and six overclaim risks (OR1-OR6) are identified.

**Readiness decision:** `DEFER_PENDING_VOCABULARY_AND_NULL_FRAMEWORK`. M8 is not ready for design start without feature vocabulary SSOT, null MI distribution, and terminology gap resolution.

**No deployable prediction edge. No betting advice. No strategy promotion. No DB write. No registry mutation.**

---

## Existing Feature/Bottleneck Evidence Inventory

Total artifacts inventoried: 11

### A1: `analysis/p219_external_method_diagnostic_sweep.py`
**Task:** P219  
**Classifications:** `FEATURE_BOTTLENECK_LIKE_ARTIFACT`, `MI_OR_CHANNEL_METRIC_PRESENT`, `ENTROPY_OR_COMPRESSION_DIAGNOSTIC`, `NULL_OR_NO_EDGE_EVIDENCE`  
**Description:** External 10-method diagnostic sweep. M6: Shannon entropy + zlib compression ratio diagnostic. M10: feature-bottleneck synthesis — computes MI (bits) between a binned trailing-frequency feature and binary hit outcome via _mutual_information_binary(feat, hit). Also computes pct_of_outcome_entropy and min_detectable_edge_pp.  
**Lottery types covered:** DAILY_539, POWER_LOTTO  
**Key findings:**
- DAILY_539: MI ~= 8.8e-6 bits (near zero)
- POWER_LOTTO: MI ~= 1.6e-5 bits (near zero)
- Both far below min-detectable-edge (~1.7-2.2pp)
- Channel is empty; no bottleneck to widen
- M6 entropy/compression: BIG_LOTTO signals are data contamination artifacts
**Note:** Only one feature tested (trailing_freq). Other feature spaces untested.  

### A2: `outputs/research/p219_external_method_diagnostic_sweep_20260605.json`
**Task:** P219  
**Classifications:** `FEATURE_BOTTLENECK_LIKE_ARTIFACT`, `MI_OR_CHANNEL_METRIC_PRESENT`, `NULL_OR_NO_EDGE_EVIDENCE`, `HISTORICAL_ARTIFACT_DO_NOT_EDIT`  
**Description:** P219 sweep result artifact. Contains M10_bottleneck results including mutual_information dict with trailing_freq_to_next_hit_bits and pct_of_outcome_entropy. Published evidence of near-zero MI for DAILY_539 and POWER_LOTTO.  
**Lottery types covered:** DAILY_539, POWER_LOTTO  
**Key findings:**
- MI near zero for both clean games
- P219 lessons L_P219_A: channel empty, no bottleneck to widen

### A3: `lottery_api/diagnostics/statistical_diagnostics_schema.py`
**Task:** P242  
**Classifications:** `FEATURE_BOTTLENECK_LIKE_ARTIFACT`, `HISTORICAL_ARTIFACT_DO_NOT_EDIT`  
**Description:** Read-only statistical diagnostics schema. Contains 'feature_bottleneck' as a REQUIRED_SCHEMA_FIELD (line 124) alongside companion fields min_detectable_effect, power_at_observed_effect, overfit_ratio. No MI computation -- schema definition only. Safety booleans enforce no_edge_claim semantics.  
**Lottery types covered:** ALL (schema-level, not lottery-specific)  
**Key findings:**
- field is REQUIRED but no implementation exists
- no MI module wired to this field
- safety booleans prevent production/betting claims
**Note:** Schema intent is clear but no module fills the feature_bottleneck field.  

### A4: `outputs/research/p244c_diagnostics_integration_plan_20260605.json`
**Task:** P244C  
**Classifications:** `FEATURE_BOTTLENECK_LIKE_ARTIFACT`, `HISTORICAL_ARTIFACT_DO_NOT_EDIT`  
**Description:** Diagnostics integration plan. Maps 'feature_bottleneck' group to fields: [feature_bottleneck, min_detectable_effect, power_at_observed_effect, overfit_ratio]. Provides field mapping and confidence templates. Plan-only -- no code.  
**Lottery types covered:** ALL (plan-level)  
**Key findings:**
- 4-field group identified: feature_bottleneck, min_detectable_effect, power_at_observed_effect, overfit_ratio
- plan-only; implementation deferred

### A5: `outputs/research/p241b_p234_statistical_diagnostics_inventory_20260605.json`
**Task:** P241B  
**Classifications:** `FEATURE_BOTTLENECK_LIKE_ARTIFACT`, `HISTORICAL_ARTIFACT_DO_NOT_EDIT`  
**Description:** P234 statistical diagnostics inventory. Identified 'feature_bottleneck' as one of 16 method gaps. Confirmed it is MISSING implementation and is a gap in the current research infrastructure.  
**Lottery types covered:** ALL (gap assessment)  
**Key findings:**
- feature_bottleneck is one of 16 method gaps from P234 CTO analysis
- no implementation; schema field only

### A6: `outputs/research/p252b_unified_external_method_coverage_audit_20260607.json`
**Task:** P252B  
**Classifications:** `FEATURE_BOTTLENECK_LIKE_ARTIFACT`, `NULL_OR_NO_EDGE_EVIDENCE`, `HISTORICAL_ARTIFACT_DO_NOT_EDIT`  
**Description:** P252B 8-method coverage audit. Classifies M8 Feature Bottleneck Report as PARTIAL / P1. Identifies gaps: no feature_bottleneck_report.py SSOT, no canonical output format for feature-information-rate or MI report, P219 MI analysis exploratory not shareable. Confirms no deployable prediction edge across all research arcs.  
**Lottery types covered:** ALL (audit scope)  
**Key findings:**
- M8 status: PARTIAL -- schema field exists but no module
- gap: no feature vocabulary SSOT
- gap: no canonical MI output format
- recommended next: Type B design + Type C implementation (multi-step)
- no deployable prediction edge from any method

### A7: `outputs/research/p253a_p1_external_method_readiness_triage_20260607.json`
**Task:** P253A  
**Classifications:** `FEATURE_BOTTLENECK_LIKE_ARTIFACT`, `NULL_OR_NO_EDGE_EVIDENCE`, `HISTORICAL_ARTIFACT_DO_NOT_EDIT`  
**Description:** P253A P1 method readiness triage. Classifies M8 as DEFER. Rationale: no feature vocabulary SSOT, no MI null baseline under random draws, HIGH overclaim risk. Blocking issues: missing feature vocabulary, missing MI null distribution, no null comparison framework.  
**Lottery types covered:** ALL (triage scope)  
**Key findings:**
- M8 readiness: DEFER
- blocking_issues: [no feature vocab, no MI null baseline, overclaim risk]
- implementation_risk: HIGH
- edge_claim_risk: HIGH
- module_path: lottery_api/utils/feature_bottleneck.py (future -- deferred)

### A8: `outputs/research/p212_power_lotto_backward_oos_gap_check_20260605.json`
**Task:** P212  
**Classifications:** `ARCHIVED_OR_EXPLORATORY_DEFER`  
**Description:** P212 backward-OOS gap check. Contains a 'feature_bottlenecks' field that lists blocking factors as strings (e.g. 'no_pre_boundary_draws_available'), NOT an MI or channel diagnostic. TERMINOLOGY INCONSISTENCY: 'feature_bottlenecks' here means 'blocking issues' not 'MI per feature'.  
**Lottery types covered:** POWER_LOTTO  
**Key findings:**
- TERMINOLOGY_INCONSISTENCY: 'feature_bottlenecks' used as blocking-factors list, not as MI channel diagnostics
**Note:** Term collision must be resolved in future M8 schema.  

### A9: `memory/lessons.md L_P219_A`
**Task:** P219  
**Classifications:** `MI_OR_CHANNEL_METRIC_PRESENT`, `NULL_OR_NO_EDGE_EVIDENCE`, `HISTORICAL_ARTIFACT_DO_NOT_EDIT`  
**Description:** Lessons.md L_P219_A: M10 bottleneck results summarized. MI(trailing-freq->next-hit) approx 8.8e-6 bits (DAILY_539) / 1.6e-5 bits (POWER_LOTTO). Far below min-detectable-edge (~1.7-2.2pp). Lesson: channel is empty, no bottleneck to widen. P219 10-method sweep all predictive-NULL.  
**Lottery types covered:** DAILY_539, POWER_LOTTO  
**Key findings:**
- channel is empty -- no bottleneck to widen
- 10 method families all predictive-NULL after Bonferroni
- anomaly not predictor confirmed (L_P219_C)
**Note:** Gold-standard evidence for DAILY_539 and POWER_LOTTO M10 results.  

### A10: `outputs/research/p245b_bias_gate_layer_20260605.json`
**Task:** P245B  
**Classifications:** `ENTROPY_OR_COMPRESSION_DIAGNOSTIC`, `NULL_OR_NO_EDGE_EVIDENCE`, `HISTORICAL_ARTIFACT_DO_NOT_EDIT`  
**Description:** P245B bias gate layer design. Establishes gate states: 539/POWER/3_STAR/4_STAR = GATE_YELLOW_OBSERVATION_ONLY (P238B), BIG_LOTTO = GATE_RED_DATA_CONTAMINATION (P219). Principle: anomaly detection is NOT prediction. GATE_OPEN requires e-value K>=100 + BOCD + clean data + >=500 OOS draws + independent confirmation + Bonferroni + human authorization -- zero conditions currently met.  
**Lottery types covered:** ALL  
**Key findings:**
- anomaly detection is NOT prediction
- all games currently gated -- no strategy authorized
**Note:** Context for anomaly-not-predictor principle relevant to M8 overclaim risks.  

### A11: `memory/lessons.md (BIG_LOTTO signal boundary study, line ~1365)`
**Task:** P178A / signal_boundary  
**Classifications:** `MI_OR_CHANNEL_METRIC_PRESENT`, `NULL_OR_NO_EDGE_EVIDENCE`, `HISTORICAL_ARTIFACT_DO_NOT_EDIT`  
**Description:** BIG_LOTTO signal boundary study. Best MI = 0.006 bits (window_20), 1.18 pct of baseline entropy. Even this best-observed MI is within noise. Covers BIG_LOTTO only. Different MI metric from M10 (window-based vs trailing-freq). Additional terminology variant.  
**Lottery types covered:** BIG_LOTTO  
**Key findings:**
- Even best-window MI = 0.006 bits -- within noise for BIG_LOTTO
- Different MI metric variant (window-based autocorrelation MI, not feature->hit MI)
**Note:** TERMINOLOGY_INCONSISTENCY: this is window-based MI (sequence autocorrelation), not feature->hit MI as in P219 M10. Both called 'MI' without disambiguation.  

---

## Metric Inventory

Total metrics inventoried: 8

### MI1: mutual_information_binary (feature->hit)
**Status:** `COMPUTED_NEAR_ZERO -- no predictive channel found`  
**Definition:** MI between a binned trailing-frequency feature and binary hit outcome. Computed via _mutual_information_binary(feat, hit) in p219. Unit: bits. Near-zero for DAILY_539 and POWER_LOTTO.  
**Lottery coverage:** DAILY_539, POWER_LOTTO  
**Term variants:** MI(trailing-freq->next-hit) bits, trailing_freq_to_next_hit_bits, mutual_information, M10 bottleneck MI  

### MI2: pct_of_outcome_entropy
**Status:** `COMPUTED_NEAR_ZERO`  
**Definition:** MI as percentage of baseline Bernoulli entropy: mi_bits / h_baseline * 100. Near-zero in all tested games.  
**Lottery coverage:** DAILY_539, POWER_LOTTO  
**Term variants:** pct_of_outcome_entropy, fraction of base entropy  

### MI3: window-based MI (sequence autocorrelation)
**Status:** `COMPUTED_NEAR_ZERO -- within noise floor`  
**Definition:** MI measured via sliding window on number sequences (autocorrelation style), not feature->hit binary. Different concept from MI1.  
**Lottery coverage:** BIG_LOTTO  
**Term variants:** MI = 0.006 bits (window_20), pct of baseline entropy 1.18%  

### ENT1: Shannon entropy (frequency distribution)
**Status:** `COMPUTED_DIAGNOSTIC_ONLY -- anomaly not predictor`  
**Definition:** Shannon entropy of the frequency distribution of drawn numbers. Diagnostic only -- not a predictor. BIG_LOTTO anomalies explained by data contamination (L_P219_B/C).  
**Lottery coverage:** DAILY_539, POWER_LOTTO, BIG_LOTTO  
**Term variants:** freq_distribution_shannon_entropy_bits, entropy, M6 entropy, Shannon entropy normalized  

### ENT2: zlib compression ratio
**Status:** `COMPUTED_DIAGNOSTIC_ONLY`  
**Definition:** Compression ratio of serialized draw sequence as a proxy for redundancy/predictability. Near-random compression ratios across clean games.  
**Lottery coverage:** DAILY_539, POWER_LOTTO, BIG_LOTTO  
**Term variants:** zlib_compression_ratio, compression, M6 compression  

### MDE1: min_detectable_edge_pp
**Status:** `THRESHOLD_ESTABLISHED -- all observed MI far below`  
**Definition:** Minimum prediction advantage (in percentage points) detectable with adequate statistical power. For DAILY_539/POWER_LOTTO: ~1.7-2.2pp. No observed MI or feature-based signal reaches this threshold.  
**Lottery coverage:** DAILY_539, POWER_LOTTO  
**Term variants:** min_detectable_edge_pp, min_detectable_effect, minimum detectable effect  

### FB1: feature_bottleneck (schema field)
**Status:** `SCHEMA_FIELD_ONLY -- no implementation`  
**Definition:** Schema field in statistical_diagnostics_schema.py REQUIRED_SCHEMA_FIELDS. Intended to hold a structured summary of feature-information diagnostics (MI, channel, bottleneck score). No implementation exists.  
**Lottery coverage:** ALL (intended)  
**Term variants:** feature_bottleneck, feature bottleneck, M8 Feature Bottleneck Report  

### BLK1: feature_bottlenecks (blocking factors list)
**Status:** `TERMINOLOGY_COLLISION -- must disambiguate in M8 schema`  
**Definition:** DIFFERENT CONCEPT from MI-based feature bottleneck. In p212, 'feature_bottlenecks' is a list of strings describing why backward-OOS is blocked. NOT an MI or channel metric.  
**Lottery coverage:** POWER_LOTTO  
**Term variants:** feature_bottlenecks  

---

## Lottery-Type Coverage

### DAILY_539
- MI computed: True
- MI value: 8.8e-6 (M10 trailing-freq->next-hit)
- Conclusion: channel empty -- no predictive bottleneck to widen
- Data quality: CLEAN
- Gate state: GATE_YELLOW_OBSERVATION_ONLY (P238B)

### POWER_LOTTO
- MI computed: True
- MI value: 1.6e-5 (M10 trailing-freq->next-hit)
- Conclusion: channel empty -- no predictive bottleneck to widen
- Data quality: CLEAN
- Gate state: GATE_YELLOW_OBSERVATION_ONLY (P238B)

### BIG_LOTTO
- MI computed: True
- MI value: 0.006 bits (window-based MI, P178A signal boundary study)
- Conclusion: MI near zero (signal boundary study); M6 entropy/compression signals are data contamination artifacts (L_P219_B/C, L_P246_A/B). Canonical sample (2,113 rows) not yet M10-tested.
- Data quality: CONTAMINATED (raw); CLEAN (canonical 2,113 rows, P246K GREEN)
- Gate state: GATE_RED_DATA_CONTAMINATION (P219, raw table)
- Note: Canonical sample P246K GREEN is a data quality result, not prediction clearance. M10 should be re-run on canonical 2,113 rows if/when M8 is designed.

### 3_STAR
- MI computed: False
- Conclusion: not computed -- UNDERPOWERED_NO_SIGNAL (P227C); no M10 run
- Data quality: CLEAN (5,850 rows, positional-tagged)
- Gate state: UNDERPOWERED_NO_SIGNAL

### 4_STAR
- MI computed: False
- Conclusion: not computed -- UNDERPOWERED_NO_SIGNAL (P227C); no M10 run
- Data quality: CLEAN (5,850 rows, positional-tagged)
- Gate state: UNDERPOWERED_NO_SIGNAL

---

## Terminology Gaps

Total terminology gaps identified: 6

### TG1: `feature bottleneck`
**Inconsistency:** Three different naming conventions for the same concept: (1) M8 in 8-method P252B audit, (2) M10 in p219 10-method sweep, (3) feature_bottleneck in schema. Method number differs across documents.  
**Risk:** Consumers may not recognize M8=M10 as the same concept, causing duplicate work.  
**Resolution required:** True  
**Variants found:** feature_bottleneck (schema field in statistical_diagnostics_schema.py), M10 bottleneck (p219 sweep method label), M8 Feature Bottleneck Report (P252B/P253A method label)  

### TG2: `feature_bottlenecks`
**Inconsistency:** Homograph collision: 'feature_bottlenecks' in p212 is a list of backward-OOS blocking factors (NOT MI metrics), while 'feature_bottleneck' in schema is intended for MI-based channel diagnostics.  
**Risk:** If M8 schema uses 'feature_bottlenecks' as a field name, it may be confused with the p212 blocking-factors list.  
**Resolution required:** True  
**Variants found:** feature_bottlenecks (p212: list of blocking strings), feature_bottleneck (schema: MI report field)  

### TG3: `mutual information (MI)`
**Inconsistency:** Two structurally different MI concepts both called 'MI': (1) feature->hit binary MI (P219 M10) and (2) window autocorrelation MI (P178A). These measure different things.  
**Risk:** Misinterpretation: near-zero window-MI does not imply near-zero feature->hit MI for all possible features.  
**Resolution required:** True  
**Variants found:** MI(trailing-freq->next-hit) bits (P219 M10: feature->hit binary MI), MI = 0.006 bits window_20 (P178A: window-based autocorrelation MI), mutual_information (P219 result dict key)  

### TG4: `entropy`
**Inconsistency:** Multiple entropy concepts with different denominators and purposes. All called 'entropy' without disambiguation.  
**Risk:** Low M6 entropy (uniform distribution) could be confused with predictive signal, when it is actually a distribution diagnostic.  
**Resolution required:** True  
**Variants found:** M6 entropy: Shannon entropy of frequency distribution (P219), baseline Bernoulli entropy h_base: per-number draw probability entropy (P219 M10), pct_of_outcome_entropy: MI as fraction of baseline entropy (P219 M10)  

### TG5: `feature`
**Inconsistency:** No canonical feature vocabulary SSOT exists. P219 M10 tested only trailing_freq. Strategy code uses many features without formal definitions.  
**Risk:** HIGH: M8 report without feature vocabulary could claim channel is empty based on one feature (trailing_freq) when other features are untested.  
**Resolution required:** True  
**Variants found:** trailing_freq (only feature tested in P219 M10), feature vocabulary (undefined SSOT), features in strategy prediction (gap_score, freq_deficit, boundary, mod3, etc.)  

### TG6: `channel`
**Inconsistency:** Channel is used informally in lessons.md but not formally defined in any schema. The term 'evidence channel' appears in task prompts but not in codebase artifacts.  
**Risk:** Ambiguous: 'channel empty' for trailing_freq is not 'all channels empty' without full feature vocabulary.  
**Resolution required:** True  
**Variants found:** channel empty (channel is empty -- lessons.md L_P219_A), evidence channel (task prompt context), signal channel (informal)  

---

## Overclaim Risks

Total overclaim risks identified: 6

### OR1: `random-compatible-not-edge`
**Random-compatible does not imply prediction edge**  
NIST GREEN result (P246K) for canonical BIG_LOTTO is a data quality / isolation audit result. It does NOT authorize any new strategy, production recommendation, deployment, or betting advice. GREEN randomness does not imply exploitable prediction signal.  
**Mitigation:** M8 schema must include no_edge_claim=True and random_compatible_does_not_imply_predictive_edge=True as required fields.  

### OR2: `anomaly-not-predictor`
**Entropy anomaly does not imply predictor**  
P219 M6 shows BIG_LOTTO has anomalous entropy/compression signals that passed Bonferroni. L_P219_B/C and L_P246_A/B fully explain all signals as data contamination artifacts. Anomaly detection is NOT prediction.  
**Mitigation:** M8 schema must include anomaly_not_predictor=True and require explanation of anomaly source before flagging as signal-relevant.  

### OR3: `near-zero-mi-not-feature-space-exhausted`
**MI approx 0 for trailing_freq does not exhaust all possible features**  
P219 M10 tested only trailing_freq. MI approx 8.8e-6 bits (539) / 1.6e-5 (POWER) is near zero for this feature. This does NOT prove that gap_score, zone_balance, mod3_count, consecutive_count, calendar features, or other candidates also have near-zero MI. Claiming 'feature space exhausted' from one feature is an overclaim.  
**Mitigation:** M8 report must enumerate all tested features explicitly and list untested features. Scope of 'channel empty' claim must be bounded to tested features only.  

### OR4: `artifact-signal-not-strategy`
**Artifact-only signal cannot become strategy without pre-registration + walk-forward**  
Any non-zero MI found in an M8 report cannot be promoted to a strategy without: pre-registration, multiple testing correction, walk-forward OOS validation, and explicit human authorization. The CLAUDE.md validation pipeline (1500-period three-window) must be completed before any MI finding is treated as a prediction candidate.  
**Mitigation:** M8 schema must include allowed_next_action and forbidden_next_action fields explicitly prohibiting strategy deployment from MI findings alone.  

### OR5: `mi-uncertainty-bands-at-near-zero`
**Near-zero MI has wide uncertainty bands at small N**  
Very small MI values (e.g. 8.8e-6 bits) are within estimation noise for sample sizes of a few thousand draws. Without an established null MI distribution (MC null), the reported MI cannot be compared to a meaningful floor. Reporting MI without null comparison risks misinterpretation as meaningful.  
**Mitigation:** M8 schema must require null_mi_95th_pct and null_mi_99th_pct fields (MC null distribution under random draws) alongside observed MI. Only report is_above_null_floor if MI > null_mi_95th_pct.  

### OR6: `window-based-mi-not-feature-hit-mi`
**Window-based MI (autocorrelation) is not feature->hit MI**  
P178A computed MI on sequence windows (autocorrelation style), finding best MI = 0.006 bits (window_20). This is structurally different from M10 feature->hit MI. Both are near zero but measure different things. Conflating the two in an M8 report would be an overclaim in either direction.  
**Mitigation:** M8 schema must distinguish mi_type: 'feature_to_hit_binary' vs 'sequence_autocorrelation'. Both must use separate null baselines.  

---

## Future M8 Report Schema Recommendation

**Schema name:** `M8FeatureBottleneckReport`  
**Version:** 0.1-proposed  
**Note:** Proposed minimum schema for a future M8 Feature Bottleneck Report. P253G does NOT implement this schema. Implementation requires a separate authorized Type C task following a vocabulary design task.  

**Design prerequisites (must complete before implementation):**
- Feature vocabulary SSOT: enumerate and define all candidate features
- Null MI distribution: MC simulation of MI under random draws for each feature x lottery
- Disambiguation of mi_type: feature_to_hit_binary vs sequence_autocorrelation
- Disambiguation of feature_bottleneck (MI report) vs feature_bottlenecks (blocking list)
- Resolve TG1-TG6 terminology gaps before implementation

**Required fields (first 10 of full list):**
- `task_id` (str) -- P253H
- `report_date` (str (ISO-8601)) -- 
- `lottery_type` (str from LotteryType.ALL) -- 
- `feature_name` (str) -- trailing_freq_50
- `feature_definition` (str) -- Exact formula -- required to bound overclaim scope
- `mi_type` (str) -- Must distinguish to prevent MI1 vs MI3 conflation (TG3)
- `mi_bits` (float) -- Observed MI in bits
- `mi_pct_of_baseline_entropy` (float) -- mi_bits / h_baseline * 100
- `null_mi_95th_pct` (float) -- MC null 95th percentile -- required (OR5 mitigation)
- `null_mi_99th_pct` (float) -- MC null 99th percentile
- *(+ 15 more fields -- see JSON for full list)*

---

## Readiness Decision

**Decision:** `DEFER_PENDING_VOCABULARY_AND_NULL_FRAMEWORK`  

P219 M10 provides one functioning MI implementation (trailing_freq only) with near-zero results for DAILY_539 and POWER_LOTTO. However: (1) Only one feature tested -- near-zero MI does not exhaust feature space. (2) No feature vocabulary SSOT -- 'feature' is undefined as shared contract. (3) No null MI distribution established -- cannot confirm near-zero MI is above or below the noise floor. (4) HIGH overclaim risk without null framework and feature vocabulary. (5) 6 unresolved terminology gaps (TG1-TG6) would cause schema confusion. M8 is not READY_FOR_DESIGN until terminology and vocabulary prerequisites are resolved. DEFER remains the correct status.

**Preconditions for design start:**
- Resolve TG1: unify M8/M10/feature_bottleneck naming (single term)
- Resolve TG2: disambiguate feature_bottlenecks (blocking list) from feature_bottleneck (MI report)
- Resolve TG3: define mi_type taxonomy (feature_to_hit_binary vs sequence_autocorrelation)
- Resolve TG5: define feature vocabulary SSOT with at least 5 candidate features
- Establish null MI distribution via MC simulation for trailing_freq as baseline
- Confirm BIG_LOTTO canonical M10 run is separate from contaminated raw-table M10

---

## Recommended Next Task or HOLD

**Recommendation:** `HOLD_OR_P253H_FEATURE_VOCABULARY_DESIGN`  

If authorized: **P253H Feature Vocabulary Design** (Type B -- design document only)  
- Define feature vocabulary SSOT (enumerate candidate features with exact formulas)  
- Resolve TG1-TG6 terminology gaps  
- Establish null MI distribution design  
- Authorization phrase: `Authorize P253H M8 feature vocabulary design`  

If HOLD: M8 remains DEFER. P253G inventory is the terminal artifact.  

---

## Explicit Non-Actions

P253G did NOT:
- Implement a feature_bottleneck report module
- Compute new MI values
- Modify any DB (no DB write)
- Modify strategy registry (no registry mutation)
- Promote any strategy (no strategy promotion)
- Modify API or frontend
- Modify existing historical artifacts
- Modify parser code, controlled_apply scripts, or production config

---

## Explicit No-Overclaim Statement

- Near-zero MI (8.8e-6 bits for DAILY_539, 1.6e-5 for POWER_LOTTO) does NOT prove all possible features are non-predictive. Only trailing_freq was tested.
- Random-compatible (NIST GREEN) does NOT imply predictive edge.
- Entropy anomaly does NOT imply predictor (anomaly = data contamination in BIG_LOTTO, per L_P219_B/C).
- No artifact-only signal can become strategy without pre-registration, correction, and walk-forward OOS.
- This report does NOT claim any deployable prediction edge.
- No betting advice is given or implied.

---

## Explicit No DB Write

No database was written, read for strategy decisions, or queried for MI computation in P253G.

---

## Explicit No Strategy Promotion / No Betting Advice

No strategy was promoted, modified, or deployed. No betting advice is given or implied.

---

## Final Classification

`FEATURE_BOTTLENECK_REPORT_INVENTORY_COMPLETE`

*P253G inventory complete. M8 Feature Bottleneck Report readiness: DEFER_PENDING_VOCABULARY_AND_NULL_FRAMEWORK. Existing evidence: P219 M10 near-zero MI for DAILY_539 (8.8e-6 bits) and POWER_LOTTO (1.6e-5 bits) for trailing_freq feature only. Schema field 'feature_bottleneck' exists but no module fills it. 6 terminology gaps (TG1-TG6) require resolution. 6 overclaim risks (OR1-OR6) identified with mitigations. 3_STAR/4_STAR: no MI computed. BIG_LOTTO canonical M10 not yet run. No deployable prediction edge. No betting advice. No strategy promotion. System remains WAITING_FOR_USER_AUTHORIZATION. Next: HOLD or authorize P253H feature vocabulary design.*