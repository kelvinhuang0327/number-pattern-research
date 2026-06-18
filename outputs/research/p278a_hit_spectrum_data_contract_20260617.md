# P278A — Hit-Spectrum Data Contract (Read-Only)

**Task:** `P278A_HIT_SPECTRUM_DATA_CONTRACT_AND_READ_ONLY_EXPORT`
**Schema:** `p278a_hit_spectrum_data_contract.v1`
**Generated:** 2026-06-17T00:00:00+00:00
**Source commit:** `8ece9c6b078c6e90a0bc2c340b727c9b7f7909fe`
**Canonical payload digest:** `4ad80e9c84b70a3382161587fabf150da134c8bf416bd7be28fab19c2419062e`

> Read-only, committed-artifact-only data contract for a FUTURE hit-spectrum page. **No DB access. No prediction-success claim. No strategy promotion.** `prediction_success_claim=false`, `strategy_promoted=false`.

## Bottom line — what can and cannot be displayed now

**Can be truthfully displayed now (verified from committed evidence):**

- Per `(cell × window)` denominators: distinct draw count, evaluated ticket count, tickets per draw, distinct ticket count — all cross-source consistent across P273A-primary, P273A-identity, and P275B.
- A draw-level **binary** prize-aware-win count and rate (clearly labelled as an aggregate, **not** an exact-hit spectrum).
- P277 observation classification and dual-gate research status.

**Cannot yet be displayed (recorded as explicit `null`/`NOT_AVAILABLE`):**

- The exact **M0/M1/M2/M3+** hit spectrum — **no committed artifact records it** for the prize-aware endpoints at the primary windows.
- Per-prize-tier counts.
- Special-number (BIG_LOTTO) / second-zone (POWER_LOTTO) component hit counts.

Every one of the 108 `(cell × window)` rows is therefore classified `SOURCE_GAP_HIT_BUCKETS`. This is a fail-closed, truthful result: the page can show verified denominators and the binary prize-aware-win rate, but the exact hit spectrum requires a **separately authorized** read-only DB extraction.

## Counts

- Unique P277 strategy cells: **36**
- Rows (cell × window): **108**

### By game
- BIG_LOTTO: 33
- DAILY_539: 45
- POWER_LOTTO: 30

### By endpoint
- `BIG_ANY_PRIZE_AWARE_WIN`: 33
- `D539_ANY_PRIZE_AWARE_WIN`: 45
- `POWER_ANY_PRIZE_AWARE_WIN`: 30

### By P277 observation class
- HISTORICAL_OBSERVATION_SUPERSEDED_BY_OOS_NULL: 3
- INSUFFICIENT_RANDOM_BASELINE_EVIDENCE: 12
- NO_EVIDENCE_OVER_RANDOM: 45
- OBSERVATION_POTENTIAL_ABOVE_RANDOM: 36
- OBSERVATION_SUPPORTED_ABOVE_RANDOM: 9
- UNDERPOWERED_OBSERVATION_POTENTIAL: 3

### By UI-readiness class
- `SOURCE_GAP_ENDPOINT_MAPPING`: 12
- `SOURCE_GAP_HIT_BUCKETS`: 96

- Full-spectrum identities: **0** (none — no exact spectrum committed)
- Partial-spectrum identities: **0** (none)

## Per-game / per-endpoint readiness

| Game | Endpoint | Condition | Special | Second-zone | Spectrum available |
|------|----------|-----------|---------|-------------|--------------------|
| DAILY_539 | `D539_ANY_PRIZE_AWARE_WIN` | hit_count >= 2 | False | False | NO |
| BIG_LOTTO | `BIG_ANY_PRIZE_AWARE_WIN` | hit_count >= 3 OR (hit_count = 2 AND special_hit = 1) | True | False | NO |
| POWER_LOTTO | `POWER_ANY_PRIZE_AWARE_WIN` | hit_count >= 3 OR (hit_count >= 1 AND special_hit = 1) | False | True | NO |

## Denominator cautions

- The success denominator is the **distinct draw count**, not the ticket-row count. Success is a **draw-level any-bet union** over the governed endpoint; draw-level and ticket-row denominators must not be collapsed.
- `evaluated_ticket_count = distinct_draw_count × tickets_per_draw` is recorded for traceability only.

## Special-number and second-zone cautions

- BIG_LOTTO encodes a special-number component and POWER_LOTTO a second-zone component **inside** the prize-aware win condition. The committed evidence only exposes the combined ANY_PRIZE_AWARE_WIN aggregate — the per-component (special / second-zone) hit counts are `NOT_AVAILABLE` and must not be inferred.
- POWER_LOTTO **missing-predicted-second-zone exclusions exist** at the primary windows (50/300/750). 12 cell-window rows across 4 strategies (`fourier_rhythm_3bet`, `power_fourier_rhythm_2bet`, `power_orthogonal_5bet`, `power_precision_3bet`) have zero scoreable draws and are classified `SOURCE_GAP_ENDPOINT_MAPPING` — these strategies are completely unscoreable across all three primary windows. Additional scoreable POWER_LOTTO rows may still contain excluded bet rows where only a subset of bets had a stored predicted second-zone. Second-zone component hit counts remain unavailable. This correction does not establish any exact M0/M1/M2/M3+ hit spectrum.

## Prize-aware availability

- Only the lowest **ANY** prize-aware threshold per game is committed; there is no per-prize-tier breakdown → `SOURCE_GAP_PRIZE_FIELDS`.

## Source gaps

- `SOURCE_GAP_HIT_BUCKETS` — exact M0/M1/M2/M3+ spectrum not committed (all 108 rows).
- `SOURCE_GAP_PRIZE_FIELDS` — no per-tier / per-component counts (all 108 rows).
- P267C M3+ (main-number, 1-bet, window-1500, reference-only) is a **different endpoint/window** and is deliberately **not** collapsed into these prize-aware rows.

## Scientific no-claim boundaries

- This contract does NOT claim improved future prediction success.
- This contract does NOT promote, deploy, activate, or recommend any strategy.
- UI readiness does NOT imply prediction success.
- UI readiness does NOT imply strategy promotion.
- UI readiness does NOT imply recommendation, deployment, or ONLINE authorization.
- Observation support does NOT imply UI readiness.
- Retrospective evidence is NOT confirmatory; it can only surface or falsify candidates.
- Missing hit buckets are recorded as explicit null / NOT_AVAILABLE and are never fabricated as zero.

## Proposed P278B page contract (NOT authorized by this task)

- Authorization status: **NOT_AUTHORIZED_BY_THIS_TASK**
- The page **may** display now:
  - Per (cell x window) verified denominators: distinct_draw_count, evaluated_ticket_count, tickets_per_draw, distinct_ticket_count.
  - Draw-level binary prize-aware-win count and rate (clearly labelled as an aggregate, NOT an exact-hit spectrum).
  - P277 observation classification and dual-gate research status.
  - Endpoint definitions and applicability flags.
- The page **must not** display yet:
  - Any M0/M1/M2/M3+ exact-hit spectrum (not committed; would be fabrication).
  - Per-prize-tier counts (not committed).
  - Special-number / second-zone component hit counts (not committed).
  - Any prediction-success, promotion, or deployment claim.
- To unlock the full spectrum: A separately authorized, read-only DB extraction (or replay re-scoring) that records the exact per-draw hit_count distribution for the prize-aware endpoints at the primary windows. This task does NOT perform or authorize it.

## Source artifact manifest

- `outputs/research/p267c_m3plus_strategy_revalidation_20260610.json`
- `outputs/research/p273a_distinct_ticket_identity_20260615.json`
- `outputs/research/p273a_primary_window_observed_counts_20260615.json`
- `outputs/research/p273a_prize_aware_inferential_validation_20260615.json`
- `outputs/research/p275b_unified_prize_aware_success_matrix_20260616.json`
- `outputs/research/p277a_historical_observation_status_reclassification_20260617.json`

- Canonical payload digest: `4ad80e9c84b70a3382161587fabf150da134c8bf416bd7be28fab19c2419062e`
