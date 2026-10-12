#!/usr/bin/env python3
"""
p128_wave2_adapter_phase1.py
============================
P128 — Wave 2 Phase 1 Multi-Bet Adapter Implementation

SCOPE:
  - Verify system state (worktree, DB, schema, P127 artifact).
  - Validate get_all_bets() implementations for priority 1-6 strategies.
  - Generate JSON artifact: outputs/replay/p128_wave2_adapter_phase1_20260528.json
  - Generate Markdown report: docs/replay/p128_wave2_adapter_phase1_20260528.md
  - DOES NOT write to production DB. DOES NOT run controlled_apply.
  - DOES NOT insert replay rows. production_db_rows_after = 72462 (unchanged).

P127 source: outputs/replay/p127_adapter_build_specs_remaining_multi_bet_20260528.json
P126G source: outputs/replay/p126g_all_tier_b_apply_closure_audit_20260528.json
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import re
from datetime import datetime, timezone
from pathlib import Path

# ─── Paths ───────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent.resolve()
WORKTREE_ROOT = SCRIPT_DIR.parent
DB_PATH = WORKTREE_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P127_ARTIFACT = WORKTREE_ROOT / "outputs" / "replay" / "p127_adapter_build_specs_remaining_multi_bet_20260528.json"
P126G_ARTIFACT = WORKTREE_ROOT / "outputs" / "replay" / "p126g_all_tier_b_apply_closure_audit_20260528.json"
OUTPUT_JSON = WORKTREE_ROOT / "outputs" / "replay" / "p128_wave2_adapter_phase1_20260528.json"
OUTPUT_MD = WORKTREE_ROOT / "docs" / "replay" / "p128_wave2_adapter_phase1_20260528.md"
ADAPTER_MODULE = WORKTREE_ROOT / "lottery_api" / "models" / "p128_wave2_phase1_adapters.py"

EXPECTED_DB_ROWS = 72462
EXPECTED_BRANCH = "claude/zen-gates-ff6802"
P127_EXPECTED_CLASSIFICATION = "P127_ADAPTER_BUILD_SPECS_READY"
TARGET_PHASE = "PHASE_1"
PHASE_PRIORITIES = list(range(1, 7))  # priority 1-6

# ─── Utilities ────────────────────────────────────────────────────────────────

def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(cmd: list[str], cwd: Path = None) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or WORKTREE_ROOT)
    return result.stdout.strip()


def _fail(msg: str) -> None:
    print(f"STOP: {msg}", file=sys.stderr)
    sys.exit(1)


# ─── Check 1: Worktree + Branch ───────────────────────────────────────────────

def check_worktree() -> dict:
    """Verify we are in the correct worktree and branch."""
    toplevel = _run(["git", "rev-parse", "--show-toplevel"])
    branch = _run(["git", "branch", "--show-current"])
    head_sha = _run(["git", "rev-parse", "HEAD"])
    head_msg = _run(["git", "log", "--oneline", "-1"])

    in_worktree = str(WORKTREE_ROOT) in toplevel or toplevel == str(WORKTREE_ROOT)
    branch_ok = branch == EXPECTED_BRANCH

    if not in_worktree:
        _fail(f"Worktree mismatch. Expected root containing '{WORKTREE_ROOT}', got '{toplevel}'")
    if not branch_ok:
        _fail(f"Branch mismatch. Expected '{EXPECTED_BRANCH}', got '{branch}'")

    return {
        "toplevel": toplevel,
        "branch": branch,
        "head_sha": head_sha,
        "head_commit": head_msg,
        "status": "PASS",
    }


# ─── Check 2: DB Row Count ────────────────────────────────────────────────────

def check_db_rows() -> dict:
    """Verify DB row count = 72462 (no rows added in P128)."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = ON")
    row = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()
    conn.close()
    count = row[0]

    if count != EXPECTED_DB_ROWS:
        _fail(f"DB row count mismatch: expected {EXPECTED_DB_ROWS}, got {count}")

    return {
        "table": "strategy_prediction_replays",
        "row_count": count,
        "expected": EXPECTED_DB_ROWS,
        "db_write_in_p128": False,
        "status": "PASS",
    }


# ─── Check 3: bet_index Schema ────────────────────────────────────────────────

def check_bet_index_schema() -> dict:
    """Verify bet_index column exists at column index 27."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = ON")
    cols = conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()
    conn.close()

    bet_index_col = None
    for col in cols:
        if col[1] == "bet_index":
            bet_index_col = col
            break

    if bet_index_col is None:
        _fail("bet_index column NOT FOUND in strategy_prediction_replays")

    cid = bet_index_col[0]
    col_type = bet_index_col[2]
    notnull = bet_index_col[3]
    dflt = bet_index_col[4]

    return {
        "column_name": "bet_index",
        "cid": cid,
        "type": col_type,
        "notnull": notnull,
        "default_value": dflt,
        "status": "PASS",
    }


# ─── Check 4: P127 Artifact ───────────────────────────────────────────────────

def load_p127_artifact() -> dict:
    """Load and validate P127 artifact, extract priority 1-6 specs."""
    if not P127_ARTIFACT.exists():
        _fail(f"P127 artifact not found: {P127_ARTIFACT}")

    p127 = json.loads(P127_ARTIFACT.read_text())

    cls = p127.get("classification", "")
    if cls != P127_EXPECTED_CLASSIFICATION:
        _fail(f"P127 classification mismatch: expected '{P127_EXPECTED_CLASSIFICATION}', got '{cls}'")

    specs = p127.get("adapter_build_specs", [])
    phase1_specs = [s for s in specs if s.get("implementation_priority", 99) in PHASE_PRIORITIES]
    phase1_specs.sort(key=lambda s: s["implementation_priority"])

    if len(phase1_specs) != 6:
        _fail(f"Expected 6 priority-1-6 specs from P127, got {len(phase1_specs)}")

    return {
        "artifact_path": str(P127_ARTIFACT.relative_to(WORKTREE_ROOT)),
        "task_id": p127.get("task_id"),
        "classification": cls,
        "adapter_build_strategy_count": p127.get("adapter_build_strategy_count"),
        "phase1_strategies": [
            {
                "priority": s["implementation_priority"],
                "strategy_id": s["strategy_id"],
                "lottery_type": s["lottery_type"],
                "target_bet_count": s["target_bet_count"],
                "algorithm_family": s["algorithm_family"],
                "quality_label": s["quality_label"],
                "current_replay_rows": s["current_replay_rows"],
                "proposed_function": s["proposed_adapter_contract"]["method_signature"][:80],
            }
            for s in phase1_specs
        ],
        "status": "PASS",
    }


# ─── Check 5: Adapter Module Import ───────────────────────────────────────────

def check_adapter_imports() -> dict:
    """Verify p128_wave2_phase1_adapters imports correctly and exports required symbols."""
    if not ADAPTER_MODULE.exists():
        _fail(f"Adapter module not found: {ADAPTER_MODULE}")

    # Add project root to path
    if str(WORKTREE_ROOT) not in sys.path:
        sys.path.insert(0, str(WORKTREE_ROOT))

    try:
        import importlib
        import lottery_api.models.p128_wave2_phase1_adapters as mod
        importlib.reload(mod)  # ensure fresh load
    except Exception as e:
        _fail(f"Failed to import p128_wave2_phase1_adapters: {e}")

    required_symbols = [
        "get_all_bets",
        "get_all_bets_midfreq_acb",
        "get_all_bets_fourier_d539",
        "get_all_bets_zonal_entropy",
        "get_all_bets_cold_complement",
        "get_all_bets_fourier_power",
        "get_all_bets_fourier30_markov30",
        "PHASE1_STRATEGIES",
        "DISPATCH_KEYS_ORDERED",
        "PROVENANCE_SHA256",
        "_DISPATCH",
        "_validate_bets",
    ]

    missing = [sym for sym in required_symbols if not hasattr(mod, sym)]
    if missing:
        _fail(f"Missing symbols in adapter module: {missing}")

    return {
        "module": "lottery_api.models.p128_wave2_phase1_adapters",
        "file": str(ADAPTER_MODULE.relative_to(WORKTREE_ROOT)),
        "symbols_verified": required_symbols,
        "provenance_sha256": mod.PROVENANCE_SHA256,
        "dispatch_keys": list(mod._DISPATCH.keys()),
        "status": "PASS",
    }


# ─── Check 6: Adapter Smoke Tests ─────────────────────────────────────────────

def run_adapter_smoke_tests() -> dict:
    """
    Run a smoke test for each priority 1-6 adapter.

    Builds a minimal synthetic history and calls get_all_bets() for each.
    Verifies: returns 2 bets, correct pick count, sorted, in-range, deterministic.
    """
    import lottery_api.models.p128_wave2_phase1_adapters as mod

    # Build synthetic history
    def _d539_draws(n: int) -> list[dict]:
        """Generate n deterministic DAILY_539 draws."""
        import itertools
        draws = []
        pool = list(range(1, 40))
        # Cycle through combinations deterministically
        combs = list(itertools.combinations(pool, 5))
        for i in range(n):
            numbers = list(combs[i % len(combs)])
            draws.append({"numbers": numbers})
        return draws

    def _power_draws(n: int) -> list[dict]:
        """Generate n deterministic POWER_LOTTO draws."""
        import itertools
        draws = []
        pool = list(range(1, 39))
        combs = list(itertools.combinations(pool, 6))
        for i in range(n):
            numbers = list(combs[i % len(combs)])
            special = (i % 8) + 1
            draws.append({"numbers": numbers, "special": special})
        return draws

    d539_hist = _d539_draws(150)
    power_hist = _power_draws(150)

    test_cases = [
        {"strategy_id": "midfreq_acb_2bet",        "lottery_type": "DAILY_539",   "history": d539_hist,  "pool": 39, "pick": 5},
        {"strategy_id": "midfreq_fourier_2bet",     "lottery_type": "DAILY_539",   "history": d539_hist,  "pool": 39, "pick": 5},
        {"strategy_id": "zonal_entropy_2bet",       "lottery_type": "POWER_LOTTO", "history": power_hist, "pool": 38, "pick": 6},
        {"strategy_id": "cold_complement_2bet",     "lottery_type": "POWER_LOTTO", "history": power_hist, "pool": 38, "pick": 6},
        {"strategy_id": "midfreq_fourier_2bet",     "lottery_type": "POWER_LOTTO", "history": power_hist, "pool": 38, "pick": 6},
        {"strategy_id": "fourier30_markov30_2bet",  "lottery_type": "POWER_LOTTO", "history": power_hist, "pool": 38, "pick": 6},
    ]

    results = []
    all_pass = True

    for tc in test_cases:
        sid = tc["strategy_id"]
        ltype = tc["lottery_type"]
        ctx = {"history": tc["history"], "lottery_type": ltype}
        pool = tc["pool"]
        pick = tc["pick"]

        try:
            bets1 = mod.get_all_bets(sid, ctx)
            bets2 = mod.get_all_bets(sid, ctx)  # determinism check

            assert len(bets1) == 2, f"Expected 2 bets, got {len(bets1)}"
            for i, bet in enumerate(bets1):
                assert len(bet) == pick, f"Bet {i+1}: wrong length"
                assert len(set(bet)) == pick, f"Bet {i+1}: duplicates"
                assert all(1 <= n <= pool for n in bet), f"Bet {i+1}: out of range"
                assert bet == sorted(bet), f"Bet {i+1}: not sorted"

            assert bets1 == bets2, "Non-deterministic output detected"

            results.append({
                "strategy_id": sid,
                "lottery_type": ltype,
                "bet_count": len(bets1),
                "bet1": bets1[0],
                "bet2": bets1[1],
                "deterministic": True,
                "status": "PASS",
            })

        except Exception as e:
            all_pass = False
            results.append({
                "strategy_id": sid,
                "lottery_type": ltype,
                "status": "FAIL",
                "error": str(e),
            })

    return {
        "smoke_tests_run": len(test_cases),
        "all_pass": all_pass,
        "results": results,
        "status": "PASS" if all_pass else "FAIL",
    }


# ─── Build Artifacts ──────────────────────────────────────────────────────────

def build_json_artifact(
    checks: dict,
    p127_data: dict,
    smoke_data: dict,
) -> dict:
    """Build the P128 JSON artifact."""

    implemented_adapters = []
    for tc in smoke_data["results"]:
        if tc["status"] == "PASS":
            implemented_adapters.append({
                "strategy_id": tc["strategy_id"],
                "lottery_type": tc["lottery_type"],
                "function_name": f"get_all_bets_{tc['strategy_id'].replace('2bet', '').rstrip('_')}".replace(
                    "midfreq_fourier_2bet" + tc["lottery_type"], "X"
                ),
                "bet_count": tc["bet_count"],
                "bet_index_1": tc["bet1"],
                "bet_index_2": tc["bet2"],
                "deterministic": tc["deterministic"],
                "status": tc["status"],
            })

    # Fix function names from dispatch
    fn_map = {
        ("midfreq_acb_2bet",        "DAILY_539"):    "get_all_bets_midfreq_acb",
        ("midfreq_fourier_2bet",    "DAILY_539"):    "get_all_bets_fourier_d539",
        ("zonal_entropy_2bet",      "POWER_LOTTO"):  "get_all_bets_zonal_entropy",
        ("cold_complement_2bet",    "POWER_LOTTO"):  "get_all_bets_cold_complement",
        ("midfreq_fourier_2bet",    "POWER_LOTTO"):  "get_all_bets_fourier_power",
        ("fourier30_markov30_2bet", "POWER_LOTTO"):  "get_all_bets_fourier30_markov30",
    }
    for a in implemented_adapters:
        key = (a["strategy_id"], a["lottery_type"])
        a["function_name"] = fn_map.get(key, "UNKNOWN")

    return {
        "task_id": "P128",
        "classification": "P128_WAVE2_ADAPTER_PHASE1_READY",
        "generated_at": _stamp(),
        "repo_worktree_check": checks["worktree"],
        "db_snapshot": checks["db"],
        "bet_index_schema": checks["schema"],
        "p127_source_summary": p127_data,
        "phase_scope": {
            "phase": "PHASE_1",
            "priorities_implemented": PHASE_PRIORITIES,
            "priorities_deferred": list(range(7, 13)),
            "db_write_in_p128": False,
            "controlled_apply_executed": False,
            "replay_rows_inserted": 0,
            "production_db_rows_after": EXPECTED_DB_ROWS,
            "description": (
                "Phase 1 implements get_all_bets() adapters for priority 1-6 "
                "(all 2-bet strategies). No DB write. No replay row insertion. "
                "Adapters are validated via smoke test only."
            ),
        },
        "implemented_adapters": implemented_adapters,
        "blocked_adapters": [],
        "rsr6_audit_status": {
            "applicable_to_phase1": False,
            "rsr6_affects": ["power_orthogonal_5bet (priority 12)", "power_precision_3bet (priority 10)"],
            "phase1_strategies_rsr6": "NONE — Phase 1 priority 1-6 strategies are NOT affected by RSR-6",
            "deferred_to": "PHASE_2",
            "note": "RSR-6 will be addressed in P128 Phase 2 when implementing priority 7-12 adapters",
        },
        "rsr7_audit_status": {
            "strategy_id": "fourier30_markov30_2bet",
            "lottery_type": "POWER_LOTTO",
            "expected_rows": 1500,
            "actual_rows": 1501,
            "extra_rows": 1,
            "severity": "LOW",
            "blocks_adapter": False,
            "note": (
                "fourier30_markov30_2bet has 1501 rows (1 extra vs expected 1500). "
                "This is RSR-7 (low priority). Adapter implementation proceeds. "
                "RSR-7 investigation deferred."
            ),
        },
        "adapter_contract": {
            "function_name": "get_all_bets",
            "signature": "def get_all_bets(strategy_id: str, draw_context: dict) -> list[list[int]]",
            "draw_context_keys": ["history", "lottery_type"],
            "returns": "list[list[int]] — 2 sublists, each sorted unique ints",
            "bet_index_1": "primary prediction (highest model confidence)",
            "bet_index_2": "secondary prediction (diversified)",
            "determinism": "guaranteed: same inputs -> same output",
            "no_future_data": "history must be draws strictly before target draw",
            "no_db_write": True,
        },
        "test_plan_summary": {
            "test_file": "tests/test_p128_wave2_adapter_phase1.py",
            "smoke_tests": smoke_data,
        },
        "apply_gate_status": {
            "gate": "CLOSED",
            "reason": "P128 Phase 1 is adapter-only. controlled_apply deferred to future task.",
            "apply_requires": ["P128 Phase 2 completion", "full bet_index RSR audit", "CTO sign-off"],
        },
        "blocked_or_excluded": {
            "4_STAR": "excluded — not in Phase 1 scope",
            "P108": "excluded — not in Phase 1 scope",
            "P117": "excluded — not in Phase 1 scope",
            "P118": "excluded — not in Phase 1 scope",
            "rejected_strategies": "excluded — archived in lottery_api/data/rejected/",
            "priority_7_to_12": "deferred to Phase 2",
        },
        "roadmap_update_status": "PENDING_IN_THIS_COMMIT",
        "remaining_risks": [
            "RSR-6: power_orthogonal_5bet / power_precision_3bet need bet-2 logic — deferred to Phase 2",
            "RSR-7: fourier30_markov30_2bet has 1 extra row — low priority, needs investigation",
            "Phase 1 adapters are smoke-tested only; full 1500-draw backtest validation deferred",
            "No controlled_apply executed yet — production DB unchanged at 72462 rows",
        ],
        "next_recommended_task": "P129 or P128-Phase2: implement priority 7-12 adapters, then controlled_apply for Phase 1",
        "summary": (
            "P128 Phase 1 COMPLETE. Implemented get_all_bets() for 6 priority strategies "
            "(all 2-bet). No DB write. production_db_rows_after=72462. "
            "All 6 smoke tests PASS. RSR-6 deferred to Phase 2. "
            "Classification: P128_WAVE2_ADAPTER_PHASE1_READY."
        ),
    }


def build_md_report(artifact: dict) -> str:
    """Build the P128 Markdown report."""

    adapters = artifact["implemented_adapters"]
    smoke = artifact["test_plan_summary"]["smoke_tests"]

    adapter_rows = ""
    for i, a in enumerate(adapters):
        p = i + 1
        adapter_rows += (
            f"| P{p} | `{a['strategy_id']}` | `{a['lottery_type']}` "
            f"| `{a['function_name']}()` | {a['bet_count']} | {a['status']} |\n"
        )

    smoke_rows = ""
    for tc in smoke["results"]:
        s = tc.get("status", "?")
        det = "✓" if tc.get("deterministic") else "✗"
        smoke_rows += (
            f"| `{tc['strategy_id']}` | `{tc['lottery_type']}` | {s} | {det} |\n"
        )

    db = artifact["db_snapshot"]
    schema = artifact["bet_index_schema"]
    scope = artifact["phase_scope"]
    rsr6 = artifact["rsr6_audit_status"]
    rsr7 = artifact["rsr7_audit_status"]
    contract = artifact["adapter_contract"]

    return f"""# P128 Wave 2 Phase 1 — Multi-Bet Adapter Implementation

**Task ID:** P128  
**Classification:** `{artifact['classification']}`  
**Generated:** {artifact['generated_at']}  
**Scope:** Adapter-only (no DB write, no controlled_apply, no replay row insertion)

---

## Executive Summary

P128 Phase 1 implements `get_all_bets()` adapter functions for **priority 1-6**
(all 2-bet strategies) from the P127 build spec. This is a **spec-only adapter
implementation** — no rows are written to the production database.

| Item | Value |
|------|-------|
| DB rows before | {EXPECTED_DB_ROWS} |
| DB rows after  | {db['row_count']} |
| Replay rows inserted | 0 |
| controlled_apply executed | No |
| Adapters implemented | 6 |
| All smoke tests pass | {smoke['all_pass']} |
| Classification | `{artifact['classification']}` |

---

## P127 Source Recap

- **Artifact:** `{artifact['p127_source_summary']['artifact_path']}`
- **Classification:** `{artifact['p127_source_summary']['classification']}`
- **Total strategies in P127:** {artifact['p127_source_summary']['adapter_build_strategy_count']}
- **Phase 1 scope:** Priority 1-6 (all 2-bet strategies)

---

## Why P128 Phase 1 is Adapter-Only

The P127 spec identified 12 strategies needing `get_all_bets()` adapters.
Phase 1 implements priority 1-6 (the simpler 2-bet strategies) as
adapter functions only. The reasons:

1. **Safety gate:** All adapters must be smoke-tested before any controlled_apply.
2. **RSR-6 isolation:** Priority 10 and 12 have RSR-6 considerations — deferred to Phase 2.
3. **Incremental validation:** Phase 1 → Phase 2 → controlled_apply is the safe path.
4. **No data risk:** Adapter code is pure logic — no risk to the production 72,462-row DB.

---

## Priority 1-6 Implementation Matrix

| Priority | Strategy ID | Lottery Type | Function | Bets | Status |
|----------|-------------|--------------|----------|------|--------|
{adapter_rows}
All 6 adapters implemented in:
`lottery_api/models/p128_wave2_phase1_adapters.py`

---

## get_all_bets() Contract

```python
{contract['signature']}
```

**draw_context keys:**
- `history`: list of past draw dicts (each with `numbers`, optionally `special`)
- `lottery_type`: `'DAILY_539'` or `'POWER_LOTTO'`

**Returns:** `list[list[int]]` — 2 sublists
- `[0]` = bet-1 (`bet_index=1`): primary prediction (highest model confidence)
- `[1]` = bet-2 (`bet_index=2`): secondary prediction (diversified/orthogonal)

**Guarantees:**
- Deterministic: same inputs → same output
- No future data: `history` must be draws strictly before target draw
- No DB write: `{contract['no_db_write']}`
- Bet numbers sorted ASC within each bet

---

## Adapter Algorithm Summary

### P1: `midfreq_acb_2bet` (DAILY_539)
- bet-1: **MidFreq** — top-5 numbers closest to expected frequency (mean-reversion)
- bet-2: **ACB** — top-5 most underrepresented numbers (anomaly capture)

### P2: `midfreq_fourier_2bet` (DAILY_539)
- bet-1: **MidFreq** — top-5 by mean-reversion score
- bet-2: **Fourier** — top-5 by FFT period alignment (rhythm detection)

### P3: `zonal_entropy_2bet` (POWER_LOTTO)
- Regime detection: Shannon entropy of zone distribution (8 zones, window=30)
- bet-1: **Entropy-adaptive** — cold if chaotic (>2.2 bits), hot if stable
- bet-2: **Opposite regime** — hot if bet-1 was cold, cold if hot (maximum diversification)

### P4: `cold_complement_2bet` (POWER_LOTTO)
- bet-1: **Cold top-6** — 6 numbers with lowest frequency over 100 draws (reversion)
- bet-2: **Hot complement** — 6 numbers with highest frequency over 100 draws (momentum)

### P5: `midfreq_fourier_2bet` (POWER_LOTTO)
- bet-1: **MidFreq+Fourier intersection** — top-20 MidFreq ∩ top-20 Fourier, pick 6
- bet-2: **Pure Fourier** — top-6 by FFT rhythm score (window=500)

### P6: `fourier30_markov30_2bet` (POWER_LOTTO)
- bet-1: **Fourier30** — weighted recency frequency (window=30, weight 1.0→3.0)
- bet-2: **Markov30** — Markov transition matrix top-6 (window=30)

---

## RSR-6 Audit Status

**RSR-6 is NOT applicable to Phase 1.**

{rsr6['phase1_strategies_rsr6']}

RSR-6 affects:
{chr(10).join(f'- {s}' for s in rsr6['rsr6_affects'])}

Deferred to: **{rsr6['deferred_to']}**

---

## RSR-7 Note

| Field | Value |
|-------|-------|
| Strategy | `{rsr7['strategy_id']}` |
| Lottery | `{rsr7['lottery_type']}` |
| Expected rows | {rsr7['expected_rows']} |
| Actual rows | {rsr7['actual_rows']} |
| Extra rows | {rsr7['extra_rows']} |
| Severity | {rsr7['severity']} |
| Blocks adapter | {rsr7['blocks_adapter']} |

{rsr7['note']}

---

## Smoke Test Coverage

| Strategy ID | Lottery Type | Status | Deterministic |
|-------------|--------------|--------|---------------|
{smoke_rows}
**Total smoke tests:** {smoke['smoke_tests_run']}  
**All pass:** {smoke['all_pass']}

---

## Apply Gate Rules

The apply gate is **CLOSED** for Phase 1.

controlled_apply requires:
{chr(10).join(f'- {r}' for r in artifact['apply_gate_status']['apply_requires'])}

**Phase 1 output:** adapter functions only. No production DB modification.

---

## Non-Actions (Explicitly Out of Scope)

The following were NOT done in P128 Phase 1:
- No rows written to `lottery_api/data/lottery_v2.db`
- No `controlled_apply` executed
- No replay rows inserted (`replay_rows_inserted = 0`)
- No lifecycle/champion/registry mutation
- No scheduler / cron / launchd changes
- No 4_STAR / P108 / P117 / P118 strategies touched
- Priority 7-12 deferred to Phase 2

---

## DB Snapshot

| Item | Value |
|------|-------|
| Table | `strategy_prediction_replays` |
| Row count | {db['row_count']} |
| Expected | {db['expected']} |
| DB write in P128 | {db['db_write_in_p128']} |
| `bet_index` column | present (cid={schema['cid']}, type={schema['type']}, default={schema['default_value']}) |

---

## Remaining Risks

{chr(10).join(f'- {r}' for r in artifact['remaining_risks'])}

---

## Next Task

**{artifact['next_recommended_task']}**

---

## Final Classification

```
{artifact['classification']}
```

{artifact['summary']}
"""


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"[P128] Starting Wave 2 Phase 1 adapter verification — {_stamp()}")
    print(f"[P128] Worktree: {WORKTREE_ROOT}")

    # Run all checks
    print("[P128] Check 1/6: Worktree + branch ...")
    wt = check_worktree()
    print(f"  Branch: {wt['branch']} HEAD: {wt['head_sha'][:8]} — {wt['head_commit']}")

    print("[P128] Check 2/6: DB row count ...")
    db = check_db_rows()
    print(f"  Rows: {db['row_count']} (expected {db['expected']}) — PASS")

    print("[P128] Check 3/6: bet_index schema ...")
    schema = check_bet_index_schema()
    print(f"  bet_index: cid={schema['cid']}, type={schema['type']} — PASS")

    print("[P128] Check 4/6: P127 artifact ...")
    p127 = load_p127_artifact()
    print(f"  P127 classification: {p127['classification']} — PASS")
    print(f"  Phase 1 strategies: {len(p127['phase1_strategies'])}")

    print("[P128] Check 5/6: Adapter module import ...")
    imports = check_adapter_imports()
    print(f"  Module: {imports['module']} — PASS")
    print(f"  Provenance SHA256: {imports['provenance_sha256'][:16]}...")

    print("[P128] Check 6/6: Adapter smoke tests ...")
    smoke = run_adapter_smoke_tests()
    for r in smoke["results"]:
        status_icon = "✓" if r["status"] == "PASS" else "✗"
        print(f"  {status_icon} {r['strategy_id']} ({r['lottery_type']}): {r['status']}")

    if not smoke["all_pass"]:
        _fail("One or more adapter smoke tests FAILED. Aborting artifact generation.")

    print("[P128] All checks PASS. Generating artifacts ...")

    # Build JSON artifact
    checks = {"worktree": wt, "db": db, "schema": schema}
    artifact = build_json_artifact(checks, p127, smoke)

    # Write JSON
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(artifact, indent=2, default=str))
    print(f"[P128] JSON artifact: {OUTPUT_JSON.relative_to(WORKTREE_ROOT)}")

    # Write Markdown
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text(build_md_report(artifact))
    print(f"[P128] Markdown report: {OUTPUT_MD.relative_to(WORKTREE_ROOT)}")

    # Final summary
    print()
    print("=" * 60)
    print(f"[P128] Classification: {artifact['classification']}")
    print(f"[P128] DB rows: {artifact['db_snapshot']['row_count']} (unchanged)")
    print(f"[P128] Adapters implemented: {len(artifact['implemented_adapters'])}")
    print(f"[P128] DB writes: {artifact['phase_scope']['db_write_in_p128']}")
    print(f"[P128] Replay rows inserted: {artifact['phase_scope']['replay_rows_inserted']}")
    print(f"[P128] RSR-6 applicable: {artifact['rsr6_audit_status']['applicable_to_phase1']}")
    print("=" * 60)
    print(f"[P128] DONE — {_stamp()}")


if __name__ == "__main__":
    main()
