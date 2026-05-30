# P153: Replay Product End-to-End Acceptance Audit

**Classification**: `P153_REPLAY_PRODUCT_ACCEPTANCE_READY_WITH_POLISH_RECOMMENDED`
**Task ID**: P153
**Generated**: 2026-05-30

---

## 1. Executive Summary

P153 confirms the LotteryNew replay product has achieved end-to-end functional closure across P149–P152. The core goal — **all implemented strategies' historical prediction vs actual results are displayable** — is met. 

- **40/40 strategies** visible in all-strategy catalog
- **API** returns all provenance fields (bet_index, truth_level, source, controlled_apply_id, provenance_hash, actual_numbers, hit_count)
- **UI** displays all metadata (multi-bet, no_data_reason, provenance, champion governance boundary clear)
- **DB**: 94924 rows, drift guard PASS, no writes in P153

4 polish items remain (non-blocking, governance-oriented):

1. 22 DB_ONLY_MISSING_LIFECYCLE strategies need formal lifecycle governance
2. h6_gate_mk20_ew85 has 0 replay rows (visible in catalog, needs controlled_apply for history)
3. 100 LEGACY_UNVERIFIED rows (governed baseline, displayed with orange badge)
4. `provenance_source` (DB col 23) not yet in UI

---

## 2. Canonical Repo / Branch Confirmation

| Field | Value | Status |
|-------|-------|--------|
| Canonical repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` | ✅ MATCH |
| Canonical branch | `claude/zen-gates-ff6802` | ✅ MATCH |
| Production DB rows | 94924 | ✅ MATCH |
| Drift guard | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS | ✅ PASS |

---

## 3. Replay Product Boundary

| Principle | Status |
|-----------|--------|
| Historical `actual_numbers` allowed for replay display | ✅ True |
| LIVE_MONITORING_VERIFIED required for champion evaluation only | ✅ True |
| Champion block does NOT block replay product | ✅ True |
| LEGACY_UNVERIFIED display allowed with badge | ✅ True |

**Key clarification**: The replay product displays historical prediction vs actual results using DB-stored `actual_numbers`. This does not require `LIVE_MONITORING_VERIFIED` evidence. Champion evaluation (P147) is a separate governance concern.

---

## 4. P149–P152 Recap

| Task | Classification | Contribution |
|------|---------------|--------------|
| P149 | `P149_REPLAY_PRODUCT_COVERAGE_AUDIT_READY` | Confirmed 40 strategies, 9 gaps, product boundary |
| P150 | `P150_REPLAY_API_ALL_STRATEGY_COVERAGE_READY` | bet_index in API, all-strategy-catalog endpoint, no_data_reason, 22 lifecycle stubs |
| P151 | `P151_REPLAY_UI_MULTI_BET_DISPLAY_READY` | bet_index badge, all-strategy catalog section, no_data_reason badges |
| P151B | `P151B_HISTORICAL_ARTIFACT_POLLUTION_RECONCILED_READY_FOR_P151` | Clean worktree hygiene |
| P152 | `P152_REPLAY_UI_SOURCE_CONTROLLED_APPLY_ID_DISPLAY_READY` | source/controlled_apply_id/provenance in detail panel |

---

## 5. Catalog Acceptance Matrix

| Item | Value | Status |
|------|-------|--------|
| Total strategies in registry | 40 | ✅ MATCH |
| Expected total | 40 | ✅ |
| ONLINE strategies | 8 | ✅ |
| OBSERVATION strategies | 1 (h6_gate_mk20_ew85) | ✅ visible |
| REJECTED strategies | 4 | ✅ visible |
| RETIRED strategies | 5 | ✅ visible |
| DB_ONLY_MISSING_LIFECYCLE | 22 | ✅ visible |
| h6_gate_mk20_ew85 ONLINE_ZERO_REPLAY_ROWS | ✅ | ✅ |
| REJECTED_NO_REPLAY_DATA count | 4 | ✅ |
| Catalog UI section (rp-all-catalog-card) | ✅ | ✅ |

---

## 6. Replay History API Acceptance Matrix

| Field | In DB | Returned by API | Coverage |
|-------|-------|----------------|---------|
| `predicted_numbers` | ✅ | ✅ | 100% |
| `actual_numbers` | ✅ | ✅ | 100% |
| `hit_count` | ✅ | ✅ | 100% |
| `bet_index` | ✅ | ✅ | 100% (max=5) |
| `truth_level` | ✅ | ✅ | varies by source |
| `source` | ✅ | ✅ | 99.7% (320 null = legacy) |
| `controlled_apply_id` | ✅ | ✅ | 99.6% (420 null = legacy) |
| `provenance_hash` | ✅ | ✅ | 99.6% |

**Multi-bet stats**: 40622 rows with bet_index > 1 (max = Bet 5).

---

## 7. All-Strategy Catalog API Acceptance Matrix

| Item | Status |
|------|--------|
| Endpoint `/api/replay/all-strategy-catalog` | ✅ exists |
| Total strategies returned | 40 |
| `lifecycle_status` field | ✅ |
| `replay_row_count` field | ✅ |
| `no_data_reason` field | ✅ |
| DB_ONLY_MISSING_LIFECYCLE returned | ✅ |
| ONLINE_ZERO_REPLAY_ROWS returned | ✅ |
| REJECTED_NO_REPLAY_DATA returned | ✅ |

---

## 8. Replay UI Acceptance Matrix

| UI Feature | Implementation | Status |
|-----------|---------------|--------|
| `bet_index` badge in history row | `rp-bet-index-badge` (P151) | ✅ |
| `bet_index` in detail panel | `rp-detail-bet-index` (P151) | ✅ |
| `no_data_reason` badge | `rpNoDataReasonBadge()` (P151) | ✅ |
| All-strategy catalog section | `rp-all-catalog-card` (P151) | ✅ |
| h6_gate_mk20_ew85 visible | ONLINE_ZERO_REPLAY_ROWS badge (P151) | ✅ |
| REJECTED strategies visible | REJECTED_NO_REPLAY_DATA badge (P151) | ✅ |
| DB_ONLY_MISSING_LIFECYCLE visible | `rp-ndr-db-only` badge (P151) | ✅ |
| `truth_level` in detail panel | `rp-detail-truth-level` (P152) | ✅ |
| `source` in detail panel | `rp-detail-source` (P152) | ✅ |
| `source` in history row | `rp-row-source` subtitle (P152) | ✅ |
| `controlled_apply_id` in detail | `rp-detail-controlled-apply-id` (P152) | ✅ |
| `provenance_hash` in detail | `rp-detail-provenance-hash` (P152) | ✅ |
| LEGACY_UNVERIFIED badge | `rp-truth-legacy-unverified` (P152) | ✅ |
| TIERB_DRYRUN_VALIDATED badge | `rp-truth-tierb` (P152) | ✅ |

---

## 9. Multi-Bet Acceptance

| Item | Value |
|------|-------|
| `bet_index` in DB | ✅ (max=5) |
| Multi-bet rows in DB | 40622 |
| `bet_index` returned by API | ✅ |
| `bet_index` badge in UI (Bet N) | ✅ |
| Multi-bet rows distinguishable | ✅ |
| Detail panel shows bet_index | ✅ |

---

## 10. NO_DATA Acceptance

| Pattern | Registry Count | UI Badge | Status |
|---------|---------------|----------|--------|
| `ONLINE_ZERO_REPLAY_ROWS` | 1 (h6_gate_mk20_ew85) | ⚠️ amber | ✅ |
| `REJECTED_NO_REPLAY_DATA` | 4 | ✕ red | ✅ |
| `DB_ONLY_MISSING_LIFECYCLE` | 22 | ℹ️ blue | ✅ |
| `ARTIFACT_ONLY` | 0 explicit | 📋 gray | ✅ (derived) |
| `NO_REPLAY_DATA` | 0 explicit | — gray | ✅ (fallback) |
| Has rows (row-backed) | 13 | ✓ green | ✅ |

---

## 11. Provenance Metadata Acceptance

| Field | API | UI Detail | UI History Row | Status |
|-------|-----|-----------|----------------|--------|
| `truth_level` | ✅ | ✅ badge | ✅ badge in row | ✅ |
| `source` | ✅ | ✅ code block | ✅ subtitle | ✅ |
| `controlled_apply_id` | ✅ | ✅ code block | — (detail only) | ✅ |
| `provenance_hash` | ✅ | ✅ 8-char | — (detail only) | ✅ |
| `provenance_source` | ✅ in API | ❌ not in UI | — | ⚠️ deferred |

---

## 12. Champion Governance Boundary

| Item | Status |
|------|--------|
| Champion evaluation | BLOCKED (P147) |
| Block reason | Requires LIVE_MONITORING_VERIFIED evidence |
| Replay product affected | ❌ NOT affected |
| P108 trigger | BLOCKED |
| P117 trigger | BLOCKED |
| P118 trigger | BLOCKED |
| 4★ provenance | BLOCKED |

---

## 13. Tests and Verification

| Suite | Result |
|-------|--------|
| `tests/test_p153_replay_product_end_to_end_acceptance_audit.py` | **69 passed** |
| `tests/test_p152_replay_ui_source_controlled_apply_id_display.py` | 57 passed |
| `tests/test_p151_replay_ui_multi_bet_display.py` | 53 passed |
| `tests/test_p151b_historical_artifact_pollution_reconciliation.py` | 30 passed |
| `tests/test_p150_replay_api_all_strategy_coverage.py` | 72 passed |
| `tests/test_p149_replay_product_coverage_audit.py` | 21 passed |
| Drift guard | PASS |
| DB rows | 94924 (unchanged) |

---

## 14. Explicit Non-Actions

All non-actions confirmed false/0. No DB writes, no replay rows, no controlled_apply, no champion/registry promotion, no live API, no scheduler, no P108/P117/P118/4★.

---

## 15. Remaining Risks

| Risk | Severity | Impact on Replay Product |
|------|----------|------------------------|
| 22 DB_ONLY_MISSING_LIFECYCLE need lifecycle governance | Medium | None — UI displays correctly, governance non-blocking |
| h6_gate_mk20_ew85 has 0 replay rows | Low | Visible in catalog with ONLINE_ZERO_REPLAY_ROWS badge |
| 100 LEGACY_UNVERIFIED rows | Low | Governed baseline (P144D), displayed with orange badge |
| `provenance_source` not in UI | Very Low | Available via API, not critical for product |
| Champion evaluation BLOCKED | N/A | Separate governance chain, does not block replay |
| P108/P117/P118/4★ triggers BLOCKED | N/A | Separate governance, not replay product |

---

## 16. Recommended Next Task

Product is functionally complete. Two options:

**Option A (recommended)**: `P154_REPLAY_PRODUCT_RELEASE_CANDIDATE_CLOSURE`
- Formal release candidate declaration
- Changelog / operator documentation

**Option B (if polish needed)**: `P154_REPLAY_UI_POLISH_AND_OPERATOR_REVIEW`
- provenance_source in UI
- 22 DB_ONLY lifecycle governance review

---

## 17. Final Classification

```
P153_REPLAY_PRODUCT_ACCEPTANCE_READY_WITH_POLISH_RECOMMENDED
```

The replay product mainline (P149–P152) is **functionally complete**. Polish items are governance-oriented and non-blocking.
