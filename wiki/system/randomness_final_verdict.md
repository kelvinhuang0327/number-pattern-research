# Randomness Final Verdict — Minimal Version

**Version:** 1.2
**Effective:** 2026-07-18
**Authority:** wiki/system/governance.md  
**Status:** ACTIVE — Source-of-Truth for research position  

> **This document is the trusted source-of-truth for LotteryNew's current assessment of lottery randomness and exploitability.**  
> Prior reports in `outputs/` were inputs to forming this verdict, but are NOT the verdict itself.  
> `outputs/` reports are research artifacts; **this wiki file is the canonical conclusion.**

---

## 1. Current Verdict Summary

| Question | Answer |
|----------|--------|
| Are canonical BIG_LOTTO draws compatible with randomness under the current executable audit? | **YES — with qualification** (P246K existing logic: 5/5 checks GREEN; this is not an exploitable-edge claim) |
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

## 3. Randomness Audit Result

**Latest real executable audit:** 2026-07-18T08:43:47Z
**Audit script:** `scripts/randomness_audit.py`  
**Audit outputs:** `outputs/randomness_audit/`  

**Current executable classification:** `P246K_CANONICAL_BIG_LOTTO_RANDOMNESS_AUDIT_GREEN_RANDOM_COMPATIBLE`

Interpretation:
- P246K controls the canonical BIG_LOTTO population and existing BIG_LOTTO statistical behavior.
- The current audit selected 2,125 `CANONICAL_MAIN_DRAW` rows through draw `115000070` from logical store `canonical_big_lotto_store` using SQLite URI `mode=ro&immutable=1&cache=private` plus `PRAGMA query_only=ON`; a nonempty WAL fails closed and no runtime path is published.
- P246K's five existing checks are GREEN. No statistic, p-value rule, threshold, correction, simulation, seed, or verdict rule was added or changed.
- P238B's raw BIG_LOTTO population and all P238B statistical/correction/verdict helpers are excluded. Only its committed, population-independent `_connect_ro` helper is reused.
- This is an existing-logic migration, not a reproduction or substitute for the historical 44-test audit.

### Historical 44-test evidence

The historical 44-test JSON and Markdown values remain immutable legacy evidence in
`outputs/randomness_audit/`. They are **unreproducible from committed source** because
their producing implementation was not committed. Their historical verdict remains
`WEAK_DEVIATIONS_NOT_SIGNIFICANT_AFTER_CORRECTION`; it is kept separate from the
current P246K executable result, with no equivalence claim.

**What this means for research:**
- Canonical BIG_LOTTO is compatible with the existing P246K randomness checks.
- GREEN randomness is not a prediction signal, strategy authorization, or betting recommendation.
- BIG_LOTTO predictive research remains blocked under its existing governance; no strategy or production implication changes here.

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
- The two triggers are 14 calendar days and 50 new canonical draws, **whichever occurs first**.
- Calendar cadence reads `current_executable_audit.cadence_anchor.real_executable_audit_timestamp_utc` from the JSON artifact.
- Draw cadence queries `draws_big_lotto_canonical_main` independently from generated audit outputs and verifies that the prior audited row-stream hash is still a suffix of canonical history.
- Timestamp-only re-attestation is non-gating and resets neither trigger.
- UTC offsets are explicit. Every future timestamp fails closed, including the smallest supported positive offset; equal-to-now remains valid.
- Cadence accepts only the completed P246K canonical BIG_LOTTO executable-audit contract. Missing or incompatible schema, identity, scope, result, boundary, semantic hash, selected-row hash, or anchor/execution timestamp agreement fails closed. Legacy 44-test and human re-attestation objects cannot anchor cadence.
- A generated Markdown/JSON pair is validated before publication, publishes Markdown first and cadence-bearing JSON last, and restores the previous pair on supported replacement failures.
- Missing or malformed provenance, a changed historical row stream, a shrinking population, or a missing canonical view fails closed.
- `tests/test_randomness_audit_cadence.py` enforces boundaries including 49 versus 50 new draws.

**Routing:**  
→ cadence test: `tests/test_randomness_audit_cadence.py`  
→ audit script: `scripts/randomness_audit.py`  
→ raw outputs: `outputs/randomness_audit/`

Operational cadence evaluation requires an explicit canonical DB path and UTC time:

```bash
python scripts/randomness_audit.py cadence \
  --db <runtime-canonical-db-path> \
  --now-utc 2026-07-18T08:43:47Z
```

---

## Version History

| Version | Date | Change |
|---------|------|--------|
| 1.0 (Minimal) | 2026-05-06 | Initial creation as part of P1-Rank1 Governance Lock-in. Establishes minimal trusted verdict; full audit cadence to be defined in future governance tasks. |
| 1.1 | 2026-05-08 | Added §9 Audit Cadence Policy (policy v0.1): 14 calendar days / 50 draws, whichever comes first. CI gate added: tests/test_randomness_audit_cadence.py. |
| 1.2 | 2026-07-18 | Added the existing-logic P246K executable path, separated immutable/unreproducible legacy 44-test evidence, and anchored cadence to real execution plus independent canonical draw counts. |
