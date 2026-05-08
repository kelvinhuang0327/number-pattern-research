# Randomness Final Verdict — Minimal Version

**Version:** 1.0 (Minimal)  
**Effective:** 2026-05-06  
**Authority:** wiki/system/governance.md  
**Status:** ACTIVE — Source-of-Truth for research position  

> **This document is the trusted source-of-truth for LotteryNew's current assessment of lottery randomness and exploitability.**  
> Prior reports in `outputs/` were inputs to forming this verdict, but are NOT the verdict itself.  
> `outputs/` reports are research artifacts; **this wiki file is the canonical conclusion.**

---

## 1. Current Verdict Summary

| Question | Answer |
|----------|--------|
| Are lottery draws verifiably random (pass all audit tests)? | **YES — with qualification** (weak deviations not significant after Bonferroni + BH-FDR correction) |
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

**Last audit run:** 2026-05-01T23:39:17  
**Audit script:** `scripts/randomness_audit.py`  
**Audit outputs:** `outputs/randomness_audit/`  

**Verdict:** `WEAK_DEVIATIONS_NOT_SIGNIFICANT_AFTER_CORRECTION`

Interpretation:
- Some raw p-values showed marginal deviations
- After Bonferroni correction for multiple hypotheses: **none passed threshold**
- After BH-FDR correction: **none passed threshold**
- No ball-level or draw-machine bias confirmed

**What this means for research:**
- The deviations observed are consistent with random fluctuation
- No confirmed structural exploitable bias
- Physical-bias monitoring should continue; if future audit shows Bonferroni + BH-FDR significant deviation, Trigger T4 is activated (see wiki/system/controlled_edge_discovery.md §3)

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
- `outputs/randomness_audit/` → raw audit data; verdict is THIS document §3
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

## 9. Audit Cadence Policy (policy v0.1)

**Effective:** 2026-05-08  
**Status:** policy v0.1 — first formal definition  

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Max calendar days between audits | **14 days** | Ensures draws from the past two weeks are sampled |
| Max new draws since last audit | **50 draws** | Whichever threshold is hit first triggers a re-run |
| Stale threshold | Either condition above | Both checked independently; either triggers failure |

**Enforcement:**
- `tests/test_randomness_audit_cadence.py` CI gate enforces this policy (P0-1, 2026-05-08)
- Summary file: `outputs/randomness_audit/randomness_audit_summary.md` — `Run timestamp:` line is parsed
- Gate fails if summary is absent, unreadable, or timestamp is stale per policy

**Routing:**  
→ cadence test: `tests/test_randomness_audit_cadence.py`  
→ audit script: `scripts/randomness_audit.py`  
→ raw outputs: `outputs/randomness_audit/`

---

## Version History

| Version | Date | Change |
|---------|------|--------|
| 1.0 (Minimal) | 2026-05-06 | Initial creation as part of P1-Rank1 Governance Lock-in. Establishes minimal trusted verdict; full audit cadence to be defined in future governance tasks. |
| 1.1 | 2026-05-08 | Added §9 Audit Cadence Policy (policy v0.1): 14 calendar days / 50 draws, whichever comes first. CI gate added: tests/test_randomness_audit_cadence.py. |
