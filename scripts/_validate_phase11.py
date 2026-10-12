#!/usr/bin/env python3
"""Phase 11 final verification script."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator.safe_task_executor import (
    DETERMINISTIC_TASK_TYPES,
    execute_safe_task,
    is_deterministic_safe_task,
)
from orchestrator.task_completion_validator import (
    QUALITY_EFFECTIVE_STATES,
    QUALITY_INVALID_STATES,
    validate_completion,
)

print("=== PHASE_11_VERIFICATION ===\n")

# 1 — routing checks
print("1. Routing checks:")
print(f"   is_deterministic(closing_monitor)       : {is_deterministic_safe_task({'task_type': 'closing_monitor'})}")
print(f"   is_deterministic(model_patch_calibration): {is_deterministic_safe_task({'task_type': 'model_patch_calibration'})}")
assert is_deterministic_safe_task({"task_type": "closing_monitor"}) is True
assert is_deterministic_safe_task({"task_type": "model_patch_calibration"}) is False

# 2 — executor produces non-empty artifact
mock_res = {
    "dates_scanned": ["2026-04-30"],
    "total_stats": {
        "total_pending": 14,
        "upgraded": 0,
        "still_pending": 14,
        "stale_closing_rejected": 0,
    },
    "per_date": {},
    "run_at": datetime.now(timezone.utc).isoformat(),
}
with tempfile.TemporaryDirectory() as tmpdir:
    task: dict = {
        "id": 9999,
        "task_type": "closing_monitor",
        "slot_key": "slot-9999",
        "prompt_file_path": None,
    }
    with patch(
        "orchestrator.closing_odds_monitor.run_closing_odds_monitor",
        return_value=mock_res,
    ):
        result = execute_safe_task(task)

print("\n2. Non-empty artifact:")
print(f"   success                : {result['success']}")
print(f"   completed_text length  : {len(result['completed_text'])}")
print(f"   WAITING_FOR_MARKET     : {'WAITING_FOR_MARKET_SETTLEMENT' in result['completed_text']}")
assert result["success"] is True
assert len(result["completed_text"]) >= 50
assert "WAITING_FOR_MARKET_SETTLEMENT" in result["completed_text"]

# 3 — completion quality is effective
quality_result = validate_completion(task, result)
quality = quality_result["quality"]
print("\n3. Completion quality:")
print(f"   quality                : {quality}")
print(f"   is effective           : {quality in QUALITY_EFFECTIVE_STATES}")
print(f"   is NOT invalid         : {quality not in QUALITY_INVALID_STATES}")
assert quality in QUALITY_EFFECTIVE_STATES, f"Expected effective quality, got {quality}"

# 4 — CLV state unchanged (upgraded=0 → no PENDING → COMPUTED without valid odds)
print("\n4. CLV state unchanged:")
print(f"   upgraded_count         : {result['upgraded_count']}")
print(f"   pending_before         : {result['pending_before']}")
print(f"   pending_after          : {result['pending_after']}")
assert result["upgraded_count"] == 0

# 5 — registry
print("\n5. Deterministic task registry:", list(DETERMINISTIC_TASK_TYPES.keys()))
assert "closing_monitor" in DETERMINISTIC_TASK_TYPES

# 6 — worker_tick routing (import-level check without running full tick)
import orchestrator.worker_tick as wt
src = Path(wt.__file__).read_text(encoding="utf-8")
assert "is_deterministic_safe_task" in src, "worker_tick must import is_deterministic_safe_task"
assert "execute_safe_task" in src, "worker_tick must call execute_safe_task"
print("\n6. worker_tick contains deterministic routing: ✅")

print()
print("=== VERDICT: PHASE_11_DETERMINISTIC_SAFE_TASK_EXECUTOR_VERIFIED ===")
