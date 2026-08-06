# Randomness Final Verdict — Minimal Version

<<<<<<< HEAD
**Version:** 1.2<br>
**Effective:** 2026-05-06<br>
**Last verified:** 2026-07-18<br>
**Authority:** wiki/system/governance.md<br>
=======
**Version:** 1.3
**Effective:** 2026-07-18
**Authority:** wiki/system/governance.md  
>>>>>>> archive/p692-r6-superseded-deeb3af-20260719
**Status:** ACTIVE — Source-of-Truth for research position  

> **This document is the trusted source-of-truth for LotteryNew's current assessment of lottery randomness and exploitability.**  
> Prior reports in `outputs/` were inputs to forming this verdict, but are NOT the verdict itself.  
> `outputs/` reports are research artifacts; **this wiki file is the canonical conclusion.**

---

## 1. Current Verdict Summary

| Question | Answer |
|----------|--------|
| What did the current canonical BIG_LOTTO audit observe? | **P246K diagnostic: 5/5 GREEN — not proof of randomness and not an exploitable-edge claim** |
| Is there a validated, exploitable predictive edge? | **NO** |
| Is there a monetizable lottery betting strategy? | **NO** |
| Is H6 signal real? | **YES — but non-monetizable** (see §2) |
| Is edge discovery permanently closed? | **NO** — governed path remains open (see §4) |
| Is ungoverned/biased research permitted? | **NO** — permanently closed (see §5) |

---

## 2. H6 Status

**H6_gate_mk20→ew85 (DAILY_539)** is classified: `VALID_SIGNAL_NON_MONETIZABLE`

Evidence:
- Passed Monte Carlo test (n ≥ 1000, p < 0.05)
- Passed three-window validation (150p / 500p / 1500p)
- Passed McNemar vs baseline
- Payout EV analysis: **negative net ROI** due to structural house edge
- Conclusion: signal is real, but insufficient to overcome payout deficit

This classification does not mean "research failed." It means: "We found the beginning of something real, but it's not enough to act on yet."

---

<!-- P692_CURRENT_EXECUTABLE_AUDIT_BEGIN -->
## 3. Randomness Audit Result

<<<<<<< HEAD
- **Last audit run:** 2026-07-18T13:35:18.685255Z
- **Audit implementation:** `scripts/randomness_audit.py` (`RECONSTRUCTED`; historical implementation parity is not claimed)
- **Audit outputs:** `outputs/randomness_audit/randomness_audit_results.json` and `outputs/randomness_audit/randomness_audit_summary.md`
- **Verified normalized result SHA-256:** `ca097c324970ce06acb1fee29efccb48576b48cb9c34317fc24d341042338616`
=======
**Latest real executable audit:** 2026-07-18T13:37:50Z
**Audit script:** `scripts/randomness_audit.py`  
**Audit outputs:** `outputs/randomness_audit/`  
**Current bounded publication status:** `DIAGNOSTIC_ONLY`
>>>>>>> archive/p692-r6-superseded-deeb3af-20260719

The unchanged P246K source diagnostics report 5 GREEN and 0 YELLOW outcomes across 5 checks for the current canonical BIG_LOTTO population. This bounded diagnostic result does not prove randomness, establish absence of an exploitable edge, validate another lottery, or authorize prediction or betting.

<<<<<<< HEAD
Interpretation:
- The fresh executable audit analyzed 1,929 Power Lotto draws (through 2026-07-16), 2,125 canonical-main Big Lotto draws (through 2026-07-14), and 5,916 Daily 539 draws (through 2026-07-16)
- One of 44 pre-declared confirmatory tests was nominally significant before correction: Big Lotto special-number uniformity, raw p = 0.0459634
- The Big Lotto special-number null uses the full **1..49** marginal domain, consistent with the official sequential six-main-plus-special draw process
- After Bonferroni correction for 44 hypotheses: **none passed threshold**
- After BH-FDR correction: **none passed threshold**
- No ball-level or draw-machine bias confirmed

Limitations:
- Statistical compatibility does not prove physical randomness
- Monte Carlo p-values use 2,000 simulations and therefore have finite resolution
- The confirmatory tests are correlated; Bonferroni remains the conservative family-wise gate
- This result is not a prediction, strategy promotion, or betting recommendation

**What this means for research:**
- The deviations observed are consistent with random fluctuation
- No confirmed structural exploitable bias
- Physical-bias monitoring should continue; if future audit shows Bonferroni + BH-FDR significant deviation, Trigger T4 is activated (see wiki/system/controlled_edge_discovery.md §3)
=======
### Canonical input and execution provenance

- Scope: canonical BIG_LOTTO `CANONICAL_MAIN_DRAW` only.
- Population: 2125 rows from draw `96000001` through `115000070`.
- Logical store: `canonical_big_lotto_store`.
- SQLite contract: URI `mode=ro&immutable=1&cache=private`; `PRAGMA query_only=ON`; nonempty WAL fails closed.
- Selected-row stream SHA-256: `7d48306f31746ec3ea8976b4d0b88f2577decd52191391ee5c059f2fd4588a09`.
- P246K semantic output SHA-256: `48f72f61764e09de20702a853d124930eb3275ce49eb7e9b4b9e26e84f5d9dd1`.
- No statistic, p-value, threshold, correction, simulation, seed, or verdict value changed.
- P238B contributes only its unchanged population-independent `_connect_ro` helper.

### Non-authoritative P246K source payload

- Status: `UNCHANGED_SOURCE_DIAGNOSTIC_PAYLOAD`.
- The nested P246K payload is an unchanged source diagnostic payload.
- It is non-authoritative for proving randomness and is not equivalent to the historical 44-test audit.
- It is not evidence of no exploitable edge, does not validate another lottery, and authorizes neither prediction nor betting.

### Scientific limitations

1. The fitted-normal KS diagnostic is applied to a discrete draw-sum distribution and is not a fully calibrated goodness-of-fit proof.
2. The entropy threshold is not a p-value.
3. The five P246K diagnostics have no multiplicity correction.
4. Statistical power and minimum-detectable-effect have not been established for the published five-test diagnostic.
5. P246K GREEN does not prove randomness.
6. Earlier JSON and Markdown frequency-extrema values were inconsistent (JSON max/min 285/221; Markdown max/min 284/243). The current migration preserves both as conflicting historical evidence, selects neither historical value, and reports the separately recomputed current canonical extrema 286/222 only as part of the unchanged P246K source diagnostic payload.

### Historical date-conflict disclosure

The wiki historically cited 2026-05-01, while the preserved historical artifact timestamp is 2026-06-02. The protected historical producer is absent, so neither historical date represents a currently reproducible audit. The current executable existing-logic migration is separate; no continuity or direct comparability is claimed.
The historical 44-test evidence remains unreproducible from committed source.

### What this means for research

- The current publication reports the outcomes of five existing P246K diagnostics only.
- It supplies no prediction signal, strategy authorization, betting recommendation, or cross-lottery validation.
- BIG_LOTTO predictive research remains blocked under its existing governance.
<!-- P692_CURRENT_EXECUTABLE_AUDIT_END -->
>>>>>>> archive/p692-r6-superseded-deeb3af-20260719

---

## 4. Edge Discovery Path — Open Under Governance

Despite the current NO_EDGE conclusion, this project does NOT permanently close research:

> **Edge discovery path status: OPEN — under strict governance**

The controlled edge discovery path is defined in:  
→ `wiki/system/controlled_edge_discovery.md`

Future research may proceed when **valid triggers** (T1–T7) are met:
- New external data source (T1)
- New feature family (T2)
- Game rule change (T3)
- Randomness audit deviation after correction (T4)
- Retired strategy reopen criteria (T5)
- User-requested exploratory (T6, advisory only)
- Framework transfer to other domains (T7)

Research that does not meet a trigger condition **cannot proceed**.

---

## 5. Permanently Forbidden (Hard Stops)

The following methods remain permanently forbidden regardless of research status:

- `historical-pool max-hit` (circular-match bias)
- `circular-match bias` in any form
- `post-hoc promotion` (discovering strategy after seeing outcome)
- `in-sample-only success claim` (no OOS)
- `short-window-only edge claim` (< 150 periods)
- `uncorrected grid search`
- `production write without human confirmation`
- `auto rollback`

These bans are **methodological**, not research bans. They block invalid evidence, not valid research.

---

## 6. Source-of-Truth Transition Note

### Why outputs/ reports are NOT the final verdict

Prior research outputs in `outputs/` were generated during active investigation. They contain:
- Intermediate analyses
- Exploratory findings
- False positives (e.g., `outputs/prediction_hit_analysis/` — marked INVALID)
- Provisional conclusions that have since been refined

The transition to wiki/system/ as Source-of-Truth was made because:
1. `outputs/` files can be regenerated and may be overwritten
2. Multiple conflicting versions can exist in `outputs/`
3. Agent trust hierarchy (CLAUDE.md §4) requires wiki-routing for trusted knowledge
4. This document provides the single, governance-locked verdict

### How to read outputs/ safely

- `outputs/prediction_hit_analysis/INVALID.md` → confirmed circular-match bias; do not use any hit analysis from that directory
- `outputs/randomness_audit/` → current P246K executable result plus hash-locked legacy 44-test evidence; verdict is THIS document §3
- `outputs/research_review/` → research inputs to forming this verdict; do NOT treat as the verdict itself
- Any `outputs/` file labeled `SUPERSEDED`, `DEPRECATED`, `ARCHIVED` → do not use

---

## 7. Implications for Active Strategy

Current active strategy state:
- **DAILY_539**: H6_gate_mk20→ew85 → `VALID_SIGNAL_NON_MONETIZABLE` → shadow/observation mode
- **BIG_LOTTO**: `ADVISORY_ONLY` — no active betting strategy
- **POWER_LOTTO**: `ADVISORY_ONLY` — no active betting strategy

No strategy should be promoted to `T4_DEPLOYABLE` until all gates in  
`wiki/system/validation_gates.md` AND gate G11 (Payout EV) in  
`wiki/system/controlled_edge_discovery.md §4` are satisfied.

---

## 8. Next Steps for Research Resumption

To resume edge discovery legitimately:
1. Identify a valid trigger from `wiki/system/controlled_edge_discovery.md §3`
2. Pre-register hypothesis in Hypothesis Registry (must exist before data access)
3. Run circular-bias CI gate: `pytest tests/test_no_circular_match.py`
4. Follow full gate sequence G1–G11
5. Document classification per `controlled_edge_discovery.md §5`

No shortcuts. No "just a quick check." All gates are mandatory.

---

## 9. Audit Cadence Policy (policy v0.2 — executable-anchor clarification)

**Effective:** 2026-07-18
**Status:** ACTIVE

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Max calendar days between real executable audits | **14 calendar days** | Anchored to execution, never re-attestation |
| Max new draws since last audit | **50 new canonical BIG_LOTTO draws** | Current draws come from an independent canonical DB query |
| Stale threshold | Either condition above | Both checked independently; either triggers failure |

**Enforcement:**
<<<<<<< HEAD
- `tests/test_randomness_audit_cadence.py` CI gate enforces this policy (P0-1, 2026-05-08)
- The cadence anchor is the audit artifact's UTC `run_timestamp`; the summary's `Run timestamp:` line must match it exactly
- Human re-attestation of unchanged evidence does **not** reset either cadence trigger
- The gate validates required audit evidence, immutable dataset digests, and the current canonical draw count; a timestamp without dataset evidence fails closed
- The gate fails if either artifact is absent or unreadable, the audit is more than 14 days old, audited history changed, or 50 new canonical draws accumulated
=======
- The two triggers are 14 calendar days and 50 new canonical draws, **whichever occurs first**.
- Calendar cadence reads `current_executable_audit.cadence_anchor.real_executable_audit_timestamp_utc` from the JSON artifact.
- Draw cadence queries `draws_big_lotto_canonical_main` independently from generated audit outputs and verifies that the prior audited row-stream hash is still a suffix of canonical history.
- Timestamp-only re-attestation is non-gating and resets neither trigger.
- UTC offsets are explicit. Every future timestamp fails closed, including the smallest supported positive offset; equal-to-now remains valid.
- Cadence accepts only the completed P246K canonical BIG_LOTTO executable-audit contract. Missing or incompatible schema, identity, scope, result, boundary, semantic hash, selected-row hash, or anchor/execution timestamp agreement fails closed. Legacy 44-test and human re-attestation objects cannot anchor cadence.
- A generated Markdown/JSON pair is validated before publication, publishes Markdown first and cadence-bearing JSON last, and restores the previous pair on supported replacement failures.
- Missing or malformed provenance, a changed historical row stream, a shrinking population, or a missing canonical view fails closed.
- `tests/test_randomness_audit_cadence.py` enforces boundaries including 49 versus 50 new draws.
>>>>>>> archive/p692-r6-superseded-deeb3af-20260719

**Routing:**  
→ cadence test: `tests/test_randomness_audit_cadence.py`  
→ audit script: `scripts/randomness_audit.py`  
→ raw outputs: `outputs/randomness_audit/`

Operational cadence evaluation requires an explicit canonical DB path and UTC time:

```bash
python scripts/randomness_audit.py cadence \
  --db <runtime-canonical-db-path> \
  --now-utc <evaluation-utc>
```

---

## Version History

| Version | Date | Change |
|---------|------|--------|
| 1.0 (Minimal) | 2026-05-06 | Initial creation as part of P1-Rank1 Governance Lock-in. Establishes minimal trusted verdict; full audit cadence to be defined in future governance tasks. |
| 1.1 | 2026-05-08 | Added §9 Audit Cadence Policy (policy v0.1): 14 calendar days / 50 draws, whichever comes first. CI gate added: tests/test_randomness_audit_cadence.py. |
<<<<<<< HEAD
| 1.2 | 2026-07-18 | Replaced human-only freshness with a verified executable audit bound to current canonical data; retained the verdict after Bonferroni and BH-FDR correction; anchored cadence to `run_timestamp` plus dataset evidence. |
=======
| 1.2 | 2026-07-18 | Added the existing-logic P246K executable path, separated immutable/unreproducible legacy 44-test evidence, and anchored cadence to real execution plus independent canonical draw counts. |
| 1.3 | 2026-07-18 | Added strict duplicate-key rejection, complete fail-closed provenance, bounded P246K containment, six scientific limitations, historical-date disclosure, and one-timestamp JSON/Markdown/wiki publication. |
>>>>>>> archive/p692-r6-superseded-deeb3af-20260719
