# P115: BIG_LOTTO Quarantine Governance Design

**Classification**: `P115_BIGLOTTO_QUARANTINE_GOVERNANCE_READY`  
**Task ID**: P115_BIGLOTTO_QUARANTINE_GOVERNANCE  
**Generated**: 2026-05-27  
**Target Strategy**: `fourier30_markov30_biglotto`  
**Target Lottery**: `BIG_LOTTO`  

---

## Scope and Governance Constraints

This task is **governance design only**. No production state was changed.

| Constraint | Status |
|---|---|
| `db_writes` | **false** — DB opened read-only via `mode=ro` URI |
| `no_actual_quarantine_applied` | **true** — no quarantine applied |
| `no_replay_row_delete` | **true** |
| `no_lifecycle_mutation` | **true** |
| `no_strategy_promotion` | **true** |
| `no_registry_mutation` | **true** |
| `no_4star_backtest` | **true** |
| `no_special3_p108_rerun` | **true** (blocked until 37 more 3_STAR draws) |
| `no_powerlotto_p117_execution` | **true** (separate task scope) |
| `replay_rows_before` | 54462 |
| `replay_rows_after` | 54462 |

---

## Negative Evidence Summary

### Evidence Chain: P112 → P113 → P114

| Task | Finding | Value |
|---|---|---|
| P112 classification | `SUB_BASELINE` | edge vs baseline: **-0.013361** |
| P112 primary metric | avg_hit_count_per_draw | 0.721333 |
| P112 baseline metric | hypergeometric_expected_hits | 0.734694 |
| P113 action | `DEMOTE_OR_QUARANTINE_CANDIDATE` | promotion_authorized=false |
| P114 stability_label | `STABLE_NEGATIVE` | decision=READY_FOR_QUARANTINE_GOVERNANCE |

### Temporal Window Analysis (P114)

| Window | Row Count | Avg Hit Count | Baseline | Edge vs Baseline | Positive Edge |
|---|---|---|---|---|---|
| first_third | 500 | 0.718 | 0.734694 | **-0.016694** | ❌ |
| middle_third | 500 | 0.716 | 0.734694 | **-0.018694** | ❌ |
| last_third | 500 | 0.730 | 0.734694 | **-0.004694** | ❌ |
| rolling_100 | 100 | 0.730 | 0.734694 | **-0.004694** | ❌ |
| rolling_250 | 250 | 0.716 | 0.734694 | **-0.018694** | ❌ |

**Result: 5/5 temporal windows show negative edge. Stability = STABLE_NEGATIVE.**

P114 rationale:
> "P113 action=DEMOTE_OR_QUARANTINE_CANDIDATE. Chronological thirds edge: [first_third=-0.0167 | middle_third=-0.0187 | last_third=-0.0047]. Stability=STABLE_NEGATIVE. baseline=0.734694. rows=1500."

---

## Quarantine Governance Design

### Status

| Field | Value |
|---|---|
| `quarantine_status` | **GOVERNANCE_READY** |
| `production_quarantine_applied` | **false** |
| `recommended_operator_label` | `STABLE_NEGATIVE_QUARANTINE_CANDIDATE` |
| `future_quarantine_authorization_required` | **true** |
| `evidence_satisfied` | **true** |

### Recommended Catalog Disclosure

> Strategy has persistent negative edge across all temporal windows (first_third, middle_third, last_third, rolling_100, rolling_250). P112 classified as SUB_BASELINE (edge=-0.013361 vs hypergeometric baseline=0.734694). P113 action=DEMOTE_OR_QUARANTINE_CANDIDATE. P114 stability=STABLE_NEGATIVE across 5/5 temporal windows. Keep visible in catalog but label as not recommended for active use. Do not promote. Actual quarantine requires explicit future authorization.

### Future Quarantine Authorization Phrase

```
YES quarantine strategy fourier30_markov30_biglotto for stable negative evidence
```

This phrase must appear verbatim from the operator before any actual lifecycle mutation is applied.

---

## PASS / HOLD / QUARANTINE_CANDIDATE Criteria

### PASS (Do not quarantine)

Strategy no longer shows negative edge after a future re-test.

- Future temporal audit shows positive edge across majority of windows
- P112 reclassification from SUB_BASELINE to ABOVE_BASELINE or WATCHLIST_CANDIDATE
- P113 action upgraded from DEMOTE_OR_QUARANTINE_CANDIDATE

**Action**: Do not quarantine. Return to observation or watchlist queue.

### HOLD (Continue observation only)

Evidence is mixed or insufficient.

- Mixed temporal windows (some positive, some negative)
- Insufficient replay rows for reliable temporal split
- Data quality concerns (source_unknown or drift issues)
- P113 action is OBSERVATION_QUEUE or CONTINUE_OBSERVATION

**Action**: Do not quarantine yet. Schedule re-audit after more data.

### QUARANTINE_CANDIDATE — Current Assessment ✓

Persistent negative edge across major windows. Full evidence chain supports demotion/quarantine candidate.

- P112 classification is `SUB_BASELINE` ✓
- P113 action is `DEMOTE_OR_QUARANTINE_CANDIDATE` ✓
- P114 stability_label is `STABLE_NEGATIVE` ✓
- Negative edge across at least 3 of 5 temporal windows (actual: 5/5) ✓
- DB invariants unchanged ✓
- No data quality issue explains the negative result ✓

**`fourier30_markov30_biglotto` meets QUARANTINE_CANDIDATE criteria as of P115.**

**Action**: Designate as quarantine candidate. Explicit future authorization still required before any lifecycle mutation.

---

## Minimum Evidence Required Before Actual Quarantine

1. P112 classification is SUB_BASELINE or equivalent negative classification
2. P113 action is DEMOTE_OR_QUARANTINE_CANDIDATE
3. P114 stability_label is STABLE_NEGATIVE
4. Negative edge appears across at least 3 major temporal windows
5. DB invariants unchanged (replay_rows=54462)
6. No source_unknown or data drift issue explains the negative result
7. Explicit user authorization is present using the authorized phrase
8. A separate lifecycle mutation artifact has been produced and reviewed

---

## Future Quarantine Action Requirements

When (and only when) future authorization is granted:

1. Must NOT delete replay rows
2. Must NOT rewrite historical predictions
3. Must NOT alter DB without explicit DB mutation authorization
4. Must produce a separate lifecycle mutation artifact before any mutation
5. Must update catalog/operator disclosure if and only if separately authorized
6. Must re-run DB invariant verification before and after any mutation
7. Must re-run both guards (lifecycle drift + branch governance) after any mutation

---

## Next Task Recommendations

| Task | Lottery | Priority | Blocked? | Prerequisite |
|---|---|---|---|---|
| P117 | POWER_LOTTO | HIGH | No | New POWER_LOTTO draws available (>=30 after P116 design date) |
| P118 (actual quarantine) | BIG_LOTTO | MEDIUM | **YES** | Explicit operator authorization phrase + separate lifecycle mutation artifact |
| P108 | 3_STAR | LOW | **YES** | 37 more prospective 3_STAR draws needed (63/100 as of P107A) |

---

## Artifact References

| Task | Artifact | Classification |
|---|---|---|
| P112 | `outputs/replay/p112_cross_lottery_prediction_helpfulness_audit_20260527.json` | P112_CROSS_LOTTERY_HELPFULNESS_AUDIT_READY |
| P113 | `outputs/replay/p113_p112_action_decision_matrix_20260527.json` | P113_P112_ACTION_DECISION_MATRIX_READY |
| P114 | `outputs/replay/p114_temporal_stability_audit_20260527.json` | P114_TEMPORAL_STABILITY_AUDIT_READY |
| P116 | `outputs/replay/p116_powerlotto_oos_monitoring_design_20260527.json` | P116_POWERLOTTO_OOS_MONITORING_DESIGN_READY |
| **P115** | `outputs/replay/p115_biglotto_quarantine_governance_20260527.json` | **P115_BIGLOTTO_QUARANTINE_GOVERNANCE_READY** |

---

## Governance Chain

| Task | Classification | Commit |
|---|---|---|
| P105 | DB state acceptance (Option A) | ceea6e9 |
| P106 | Special3 Prospective Evaluation Rerun — PARTIAL | bfa2653 |
| P107A | Special3 100-draw monitoring gate — 63/100 | 782e261 |
| P107B | Stale baseline guard repair — READY | e79b5e9 |
| P112 | Cross-lottery prediction-helpfulness audit — READY | 4db894a |
| P113 | P112 action decision matrix — READY | be3716e |
| P114 | Temporal stability audit — READY | 3ffae64 |
| P116 | POWER_LOTTO OOS monitoring design — READY | f4b7ae4 |
| **P115** | **BIG_LOTTO quarantine governance design — READY** | *(this commit)* |

---

## Permanent Holds

- **P108 BLOCKED**: 37 more 3_STAR prospective draws needed (currently 63/100)
- **4_STAR backtest NOT AUTHORIZED**: source unknown issue unresolved
- **POWER_LOTTO P117**: separate task scope, not executed here

---

## Limitations

- This task is governance-design-only. No production state was changed.
- No actual quarantine was applied to `fourier30_markov30_biglotto`.
- No lifecycle, champion, or registry metadata was mutated.
- BIG_LOTTO hypergeometric baseline (0.734694) derived from replay data; prize-tier weighting not applied.
- Temporal window analysis covers historical replay rows only; prospective performance may differ.
- 4_STAR strategies excluded from all analysis (source unknown, backtest unauthorized).
- Special3/3_STAR strategies excluded (P108 blocked until 100 prospective draws).
- POWER_LOTTO P117 OOS execution is a separate task; no OOS draws were consumed here.
- The recommended_catalog_disclosure is advisory only; actual catalog mutation requires separate authorization.
