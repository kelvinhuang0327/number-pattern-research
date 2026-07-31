# P213B 3_STAR / 4_STAR Positional Data Recovery Feasibility Design

**Date:** 2026-06-05
**Classification:** `P213B_POSITIONAL_RECOVERY_POSSIBLE_BUT_SOURCE_UNCONFIRMED`
**Final Task Classification:** `P213B_3STAR_4STAR_POSITIONAL_DATA_RECOVERY_FEASIBILITY_COMPLETE`
**Task Type:** Type B (read-only design doc / artifact) under P240D governance simplification rules
**Status:** Feasibility design only — no code changes, no DB write, no schema change, no ingestion
**Authorization:** `Authorize P213B 3_STAR/4_STAR positional data recovery feasibility design (read-only, no DB write)`

---

## 1. Scope and Non-Goals

### In Scope
- Documenting the positional-data problem and its root cause
- Inventorying existing source candidates from actual repo evidence
- Assessing feasibility of recovery
- Defining required gates for any future recovery action
- Same-PR governance closeout under P240D Type B rule

### Explicitly Out of Scope

| Forbidden Item | Status |
|---|---|
| Code changes | Not authorized |
| DB write | Not authorized |
| Schema change | Not authorized |
| Ingestion or re-ingestion | Not authorized |
| Registry mutation | Not authorized |
| Strategy promotion | Not authorized |
| Production / recommendation change | Not authorized |
| Betting advice or wagering recommendation | Never authorized |
| Statistical scan execution | Not authorized |

---

## 2. Current 3_STAR / 4_STAR Status

### Positional Order Loss (Straight-Play Blocker)

**Root cause — confirmed in actual code:**

`lottery_api/database.py:463`:
```python
numbers_json = json.dumps(sorted(numbers))
```

`lottery_api/fetcher/taiwan_lottery_fetcher.py:127–130`:
```python
numbers = sorted(draw_nums[:config["numbers_count"]])
```

Both the fetcher and the DB layer explicitly sort numbers before storage. As a result, all 3_STAR and 4_STAR draw records in the `draws` table store numbers in ascending sorted order.

**Evidence from P226 (2026-06-03):**
- 3_STAR: 4,179 draws. `draws where numbers == sorted(numbers): 4,179 / 4,179 (100%)`.
- 4_STAR: 2,922 draws. `draws where numbers == sorted(numbers): 2,922 / 2,922 (100%)`.

This is unambiguous: positional order is absent from the current DB.

**Straight-play implication:** A straight-play prediction requires knowing the exact position of each ball. `[5, 6, 9]` in position-1/2/3 order is different from a sorted representation that collapses all 6 permutations to a single sorted tuple. Without positional order, straight-play hit computation is impossible.

### Box-Play Underpowered Issue (Separate from Positional)

The box-play underpowered issue is a separate problem from the positional data issue:
- **Box-play** does not require positional order — it matches any permutation (multiset match)
- **Box-play** is blocked by insufficient sample size (4,179 draws for 3_STAR; 2,922 for 4_STAR)
- P227C confirmed: 0 Bonferroni-significant hypotheses; both lotteries UNDERPOWERED_NO_SIGNAL
- Gates: 3_STAR needs ≥10,000 draws; 4_STAR needs ≥17,000 draws

**The positional-data recovery task would only unlock straight-play, not resolve the box-play underpowered issue.**

---

## 3. Evidence Inventory

### 3.1 Confirmed Evidence (from actual repo)

| Evidence | Location | Finding |
|---|---|---|
| Sorting in DB layer | `lottery_api/database.py:463` | `json.dumps(sorted(numbers))` — confirms sort at DB write time |
| Sorting in fetcher | `lottery_api/fetcher/taiwan_lottery_fetcher.py:127–130` | `numbers = sorted(draw_nums[:...])` — confirms sort at fetch time |
| 3_STAR 100% sorted | P226 artifact | 4,179/4,179 draws stored sorted |
| 4_STAR 100% sorted | P226 artifact | 2,922/2,922 draws stored sorted |
| No 3_STAR/4_STAR API endpoint | `lottery_api/fetcher/taiwan_lottery_fetcher.py` SOURCE_CONFIG | Only BIG_LOTTO, POWER_LOTTO, DAILY_539 have API endpoints |
| Straight-play blocked | P226/P227A governance | Confirmed as `BLOCKED_REINGEST_REQUIRED` |

### 3.2 Source Candidates — Present

| Candidate | Location | Status | Positional Order Known? |
|---|---|---|---|
| `draws` DB table | `lottery_api/data/lottery_v2.db` | Present — 4,179 / 2,922 rows | NO — sorted |
| `lottery_api/fetcher/` | `lottery_api/fetcher/taiwan_lottery_fetcher.py` | Present — no 3_STAR endpoint | N/A |
| Ingest log | `lottery_api/data/ingest_log.jsonl` | Present (untracked) | Unknown — not inspected |
| Backfill engine | `lottery_api/fetcher/backfill_engine.py` | Present | Unknown — may sort |

### 3.3 Source Candidates — Missing or Unknown

| Missing Candidate | Reason Not Found |
|---|---|
| 3_STAR / 4_STAR API endpoint | Not in `taiwan_lottery_fetcher.py` SOURCE_CONFIG; mechanism for existing data is unknown |
| Raw positional API response | No 3_STAR/4_STAR fetch was observed; whether Taiwan Lottery API exposes positional order is unconfirmed from repo alone |
| Historical raw CSV/JSON backup with positional data | Not found in repo; `lottery_api/data/` has no 3_STAR-specific raw files |
| Original ingestion script for 3_STAR data | Not found; history unclear |

### 3.4 Key Unknown: Does the Taiwan Lottery API Return Positional Order?

**This is the central unknown.** The Taiwan Lottery (台灣彩券) publishes 3_STAR (三星彩) and 4_STAR (四星彩) results. For this game type, balls are drawn in sequence and the outcome is typically a positional sequence.

- **If the API returns balls in draw order**: Recovery is feasible by adding a 3_STAR/4_STAR endpoint that does NOT sort, re-ingesting historical draws, and storing positional data.
- **If the API returns only sorted data**: Recovery requires a different source (e.g., scraping the official result page, or using a third-party source).

This cannot be confirmed from within the repo without accessing the Taiwan Lottery API or website. **Feasibility is possible but source is unconfirmed.**

---

## 4. Feasibility Classification

**`P213B_POSITIONAL_RECOVERY_POSSIBLE_BUT_SOURCE_UNCONFIRMED`**

**Rationale:**
1. The root cause (code-level sorting) is fully understood and confirmed.
2. The fix is straightforward in principle: add a 3_STAR/4_STAR fetcher endpoint that does NOT sort, then re-ingest.
3. The critical unknown is whether the upstream source (Taiwan Lottery API) returns balls in draw order or already sorted.
4. If the source preserves order, recovery is achievable with a Type B source-audit task followed by a Type D re-ingestion task.
5. If the source is already sorted, recovery may require a scraper or alternative data source — higher risk and complexity.

---

## 5. Future Recovery Plan (If Source Confirmed)

### Phase A — Read-Only Source Audit (Type B)
Before any DB write, confirm:
1. The Taiwan Lottery API has an endpoint for 3_STAR/4_STAR results.
2. The API response includes draw-order (positional) ball values, not just sorted.
3. A sample of 10–20 recent draws can be fetched and confirmed positional order is present.
4. The positional draw IDs match existing sorted draw IDs in the DB.

**Authorization phrase:** `"Authorize P213C 3_STAR/4_STAR source audit (read-only API inspection, no DB write)"`

### Phase B — Schema Design (Type B)
Design the DB schema addition:
1. Add a `numbers_positional` column (TEXT, JSON array in draw order) to `draws` table — or consider a separate `draws_positional` table.
2. Define the relationship between `numbers` (sorted) and `numbers_positional` (draw order).
3. Design a new replay adapter that uses `numbers_positional` for straight-play hit computation.

**Authorization phrase:** `"Authorize P213D 3_STAR/4_STAR positional schema design (read-only design doc, no DB write)"`

### Phase C — Dry-Run Import (Type C)
Without writing to production DB:
1. Implement the fetch-without-sorting in a dry-run branch.
2. Compare fetched positional data against existing sorted data.
3. Verify row counts and draw IDs match.
4. Produce a diff report artifact.

**Authorization phrase:** `"Authorize P213E 3_STAR/4_STAR positional dry-run import (no DB write to production DB)"`

### Phase D — Production Re-ingestion (Type D)
**Only after Phases A–C complete and pass:**
1. Immutable backup of current `draws` table.
2. Add `numbers_positional` column or schema change.
3. Backfill historical draws with positional data from API.
4. Verify: count unchanged, positional ≠ sorted for expected fraction of draws.
5. Run drift guard.

**Authorization phrase:** `"Authorize 3_STAR/4_STAR positional data re-ingestion (DB write authorized, backup confirmed, dry-run passed)"`

### Required Gates for Phase D

| Gate | Requirement |
|---|---|
| Source confirmed | API returns positional order for historical draws |
| Backup | Immutable backup of `draws` table before any write |
| Schema review | Schema change reviewed and approved |
| Dry-run passed | Phase C diff report shows no anomalies |
| Row count guard | Re-ingestion must not change row count |
| Drift guard | `replay_lifecycle_drift_guard.py --strict` must PASS after ingestion |
| Test battery | Straight-play hit semantics tests must PASS |
| Explicit authorization phrase | User must provide the Phase D phrase above |

---

## 6. Future Authorization Phrases

| Phase | Authorization Phrase |
|---|---|
| A — Source audit | `"Authorize P213C 3_STAR/4_STAR source audit (read-only API inspection, no DB write)"` |
| B — Schema design | `"Authorize P213D 3_STAR/4_STAR positional schema design (read-only design doc, no DB write)"` |
| C — Dry-run import | `"Authorize P213E 3_STAR/4_STAR positional dry-run import (no DB write to production DB)"` |
| D — Production re-ingest | `"Authorize 3_STAR/4_STAR positional data re-ingestion (DB write authorized, backup confirmed, dry-run passed)"` |
| STOP / No-action | *(no phrase needed — system remains WAITING_FOR_USER_AUTHORIZATION)* |

---

## 7. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Source data is already sorted | Read-only source audit (Phase A) confirms before any Phase D commitment |
| Digit order ambiguity | Each API field in the response must be verified as draw-order, not sorted |
| Legacy sorted storage | Adding `numbers_positional` column avoids breaking existing sorted `numbers` column |
| Duplicated draw IDs | Re-ingestion must verify unique (draw, lottery_type) keys unchanged |
| Mismatch between source and current DB | Diff report in Phase C catches any discrepancy before Phase D |
| Accidental DB write | Phase C is explicitly dry-run only; Phase D requires separate explicit authorization |
| Strategy overclaiming | Straight-play analysis is underpowered for P213B's data volume; any future scan must inherit P221F gates |

---

## 8. P2.4 Diagnostic Vocabulary

Applied using the P242/P244C schema:

| Field | Value |
|---|---|
| `feature_bottleneck` | `positional_order_lost_in_sorted_db_storage` |
| `blocker_classification` | `POSITIONAL_REINGEST_REQUIRED_SOURCE_UNCONFIRMED` |
| `allowed_next_action` | `read_only_source_audit_phase_a`, `schema_design_phase_b`, `remain_hold` |
| `forbidden_next_action` | `db_write_without_authorization`, `strategy_promotion`, `betting_advice`, `skip_dry_run` |
| `confidence_language` | "Positional data recovery is architecturally possible. Source confirmation required. Historical evidence only; not a wagering recommendation." |

---

## 9. Recommendation

**Recommended next direction: Phase A — Read-Only Source Audit**

The source audit (Phase A) is the minimal-risk, maximum-information step. It answers the central unknown (does the Taiwan Lottery API return positional order?) with a read-only inspection. If source confirms positional order, the full recovery path is clear. If source does not confirm, we stop before any DB write commitment.

**Authorization phrase for recommended next step:**
```
Authorize P213C 3_STAR/4_STAR source audit (read-only API inspection, no DB write)
```

**If user prefers HOLD:** No action. System remains `WAITING_FOR_USER_AUTHORIZATION`.

---

## 10. Type B Same-PR Closeout Rationale

This task is **Type B** under P240D §Task Type Classification because:
- It produces only Markdown and JSON artifact files (no code changes)
- Governance changes affect ≤4 files and add ≤120 governance lines
- CI passes on a single PR
- No merge conflict

**Same-PR governance closeout is allowed. No separate P213B-closeout PR is required.**
