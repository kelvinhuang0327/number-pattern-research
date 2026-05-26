# P86 — Live Monitoring / Source Decision Guard

**Classification:** `P86_LIVE_MONITORING_SOURCE_DECISION_GUARD_READY`  
**Date:** 2026-05-26  
**Policy version:** p86-v1  

---

## 1. Purpose

P86 adds a read-only live monitoring layer to the Strategy Historical Replay system.  
It detects when new POWER_LOTTO draws may exist beyond the current DB max draw (115000041) and enforces an **explicit operator decision** before any ingestion or replay apply occurs.

**P86 never writes to the DB, never inserts replay rows, never calls official API for writes.**

---

## 2. Current Baseline

| Metric | Value |
|--------|-------|
| POWER_LOTTO max_draw (DB) | **115000041** |
| replay_rows | **46,962** |
| Batch A coverage | 100.0% |
| P82 freshness guard | FRESHNESS_PASS |
| P85 launch status | P85_REPLAY_LAUNCH_CLOSURE_OPERATOR_PACKAGE_READY |

---

## 3. Source Decision Policy

### 3.1 Classification States

| Classification | Condition | Action Required |
|----------------|-----------|-----------------|
| `STABLE_NO_NEW_DRAW` | source max draw == DB max draw | None — continue monitoring |
| `SOURCE_DECISION_REQUIRED` | source max draw > DB max draw | **Operator must decide before any ingestion** |
| `SOURCE_STALE` | source max draw < DB max draw | Investigate source provider |
| `SOURCE_UNAVAILABLE` | no source provided, network not authorized or failed | Provide snapshot or authorize network read |

### 3.2 Forbidden Automatic Behavior

The following actions are **never performed automatically** by P86:

- Auto DB insert of new draws
- Auto replay row application
- Fallback to official API without explicit operator decision
- New staging table creation

### 3.3 Allowed Source Decision Outcomes (when SOURCE_DECISION_REQUIRED)

When new draws are detected, the operator must choose one of:

| Decision | Description |
|----------|-------------|
| `uploaded_source_provided_by_operator` | Operator uploads verified source file |
| `official_api_explicitly_authorized` | Operator explicitly authorizes API ingestion |
| `hold_no_action` | No action — monitoring continues |
| `manual_verification_required` | Draw data needs manual verification first |

---

## 4. Script Usage

```bash
# Default mode — read DB only, no source comparison
python scripts/p86_live_monitoring_source_decision_guard.py

# Compare against a source snapshot file
python scripts/p86_live_monitoring_source_decision_guard.py \
  --source-snapshot /path/to/snapshot.json

# Allow read-only local API call (no writes)
python scripts/p86_live_monitoring_source_decision_guard.py \
  --allow-network-read

# Custom output path
python scripts/p86_live_monitoring_source_decision_guard.py \
  --output /tmp/p86_check.json
```

### Source Snapshot File Format

```json
{
  "lottery_type": "POWER_LOTTO",
  "max_draw": 115000042,
  "source": "operator_upload",
  "as_of": "2026-05-27"
}
```

---

## 5. Sample Outputs

### 5.1 STABLE_NO_NEW_DRAW

```
classification : STABLE_NO_NEW_DRAW
db_max_draw    : 115000041
source_max_draw: 115000041
replay_rows    : 46962
db_writes      : False
```

### 5.2 SOURCE_DECISION_REQUIRED

```
classification : SOURCE_DECISION_REQUIRED
db_max_draw    : 115000041
source_max_draw: 115000042
replay_rows    : 46962
db_writes      : False
```

Exit code 2 — operator must make a decision before any ingestion.

### 5.3 SOURCE_UNAVAILABLE (default, no source provided)

```
classification : SOURCE_UNAVAILABLE
db_max_draw    : 115000041
source_max_draw: None
replay_rows    : 46962
db_writes      : False
```

---

## 6. Integration with P82 Freshness Guard

P86 is complementary to P82:

| Guard | What it checks | When to use |
|-------|---------------|-------------|
| P82 `p82_replay_freshness_guard.py` | Whether all Batch A draws have replay coverage | After any new replay rows are applied |
| P86 `p86_live_monitoring_source_decision_guard.py` | Whether new draws exist beyond the DB max | Before considering any new ingestion |

Run both together:
```bash
python scripts/p82_replay_freshness_guard.py --lottery POWER_LOTTO
python scripts/p86_live_monitoring_source_decision_guard.py
```

---

## 7. Operator Instructions

1. **Run P86 daily or when new draws are expected.**

2. **If `STABLE_NO_NEW_DRAW`:** no action required.

3. **If `SOURCE_DECISION_REQUIRED`:**  
   - Do NOT ingest automatically.  
   - Choose a source decision from the allowed list (see §3.3).  
   - Document the decision and obtain authorization.  
   - Only then proceed with ingestion via the appropriate phase (P87+).

4. **If `SOURCE_STALE`:**  
   - Check that the source file or API is returning current data.  
   - Verify `as_of` date in the source snapshot.

5. **If `SOURCE_UNAVAILABLE`:**  
   - Provide `--source-snapshot` or `--allow-network-read`.

---

## 8. Governance

| Control | State |
|---------|-------|
| DB writes | **false** |
| Replay row insertions | **0** |
| Official API writes | **none** |
| New tables created | **none** |
| Ingestion | **none** |
| Branch | `p86-live-monitoring-source-decision-guard` |
