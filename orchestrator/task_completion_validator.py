"""
Phase 10 — Task Completion Quality Validator

Classifies completed task output into quality states so that empty or no-op
completions are not counted as effective improvements in the Phase 9 ops report.

Quality states
--------------
COMPLETED_VALID          — meaningful content produced (text, artifact, or changed files)
COMPLETED_DIAGNOSTIC_ONLY — diagnostic artifact present but no learning/state change
COMPLETED_EMPTY_ARTIFACT — artifact file exists but is empty; completed_text is also empty
COMPLETED_NOOP           — no text, no artifact, no changed files, duration < threshold
FAILED_EXECUTION         — maps to existing status=FAILED (not used here; included for completeness)
NEEDS_RETRY              — transient failure; retry would likely succeed

HARD RULES:
  - Does not modify CLV state
  - Does not mark PENDING_CLOSING as COMPUTED
  - Does not delete artifacts
  - Does not change task status (quality is stored separately as completion_quality)
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# ── Quality state constants ───────────────────────────────────────────────

QUALITY_VALID            = "COMPLETED_VALID"
QUALITY_DIAGNOSTIC_ONLY  = "COMPLETED_DIAGNOSTIC_ONLY"
QUALITY_EMPTY_ARTIFACT   = "COMPLETED_EMPTY_ARTIFACT"
QUALITY_NOOP             = "COMPLETED_NOOP"
QUALITY_FAILED           = "FAILED_EXECUTION"
QUALITY_NEEDS_RETRY      = "NEEDS_RETRY"

# States that count as effective improvements in ops reports
QUALITY_EFFECTIVE_STATES = {QUALITY_VALID, QUALITY_DIAGNOSTIC_ONLY}

# States that do NOT count as effective
QUALITY_INVALID_STATES = {QUALITY_EMPTY_ARTIFACT, QUALITY_NOOP}

# ── Per-task-type minimum content requirements ────────────────────────────

# Keywords that indicate valid closing_monitor output
_CLOSING_MONITOR_VALID_KEYWORDS = {
    "pending", "computed", "stale", "closing", "odds",
    "no valid closing odds", "freshness", "pending_count",
    "computed_count", "stale_count", "diagnostic",
}

# Minimum completed_text length for a task to be considered VALID (generic)
_MIN_TEXT_LENGTH_VALID = 50

# Maximum duration (seconds) below which a task with no output is NOOP not VALID
_MAX_NOOP_DURATION_SECONDS = 10

# Minimum artifact file size (bytes) to count as non-empty
_MIN_ARTIFACT_SIZE_BYTES = 10


def _has_valid_text(completed_text: str | None) -> bool:
    """Return True if completed_text is substantive (above minimum length)."""
    return bool(completed_text) and len(completed_text.strip()) >= _MIN_TEXT_LENGTH_VALID


def _artifact_is_nonempty(file_path: str | None) -> bool:
    """Return True if artifact file exists and is at least _MIN_ARTIFACT_SIZE_BYTES bytes."""
    if not file_path:
        return False
    try:
        return os.path.isfile(file_path) and os.path.getsize(file_path) >= _MIN_ARTIFACT_SIZE_BYTES
    except OSError:
        return False


def _has_changed_files(changed_files_json: str | None) -> bool:
    """Return True if changed_files_json is a non-empty list."""
    if not changed_files_json:
        return False
    try:
        files = json.loads(changed_files_json)
        return isinstance(files, list) and len(files) > 0
    except (json.JSONDecodeError, TypeError):
        return False


def _closing_monitor_valid(completed_text: str | None, artifact_path: str | None) -> bool:
    """
    closing_monitor minimum valid completion.
    Requires at least one of:
    - pending/computed/stale count summary in text
    - non-empty artifact file
    - explicit "no valid closing odds found" statement
    """
    text = (completed_text or "").lower()
    if any(kw in text for kw in _CLOSING_MONITOR_VALID_KEYWORDS):
        return True
    if _artifact_is_nonempty(artifact_path):
        return True
    return False


# ── Main public API ───────────────────────────────────────────────────────

def validate_completion(task: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """
    Inspect a completed task's output and classify its quality.

    Args:
        task: DB task row (id, title, task_type, worker_type, etc.)
        result: execution_result dict from execute_task_with_provider()
                  Keys: success, completed_text, completed_file_path,
                        changed_files, execution_log

    Returns:
        {
          "quality": str,          # one of the QUALITY_* constants
          "reason": str,           # human-readable explanation
          "valid": bool,           # True if quality in QUALITY_EFFECTIVE_STATES
          "checks": dict[str, bool] # individual check results for tests
        }
    """
    task_type     = (task.get("task_type") or "").lower().strip()
    duration      = int(result.get("duration_seconds") or task.get("duration_seconds") or 0)
    completed_text = result.get("completed_text") or task.get("completed_text") or ""
    artifact_path  = result.get("completed_file_path") or task.get("completed_file_path")
    changed_files_json = (
        json.dumps(result.get("changed_files", []))
        if "changed_files" in result
        else (task.get("changed_files_json") or "")
    )

    checks = {
        "has_valid_text":      _has_valid_text(completed_text),
        "artifact_nonempty":   _artifact_is_nonempty(artifact_path),
        "has_changed_files":   _has_changed_files(changed_files_json),
        "duration_nonzero":    duration > _MAX_NOOP_DURATION_SECONDS,
    }

    # ── Task-type-specific validation ────────────────────────────────────
    if task_type == "closing_monitor":
        if _closing_monitor_valid(completed_text, artifact_path):
            return _result(
                QUALITY_VALID,
                "closing_monitor: valid diagnostic content found",
                checks,
            )
        # artifact exists but is empty — the worst case we saw in validation
        if artifact_path and os.path.isfile(artifact_path):
            return _result(
                QUALITY_EMPTY_ARTIFACT,
                f"closing_monitor: artifact file exists but is empty ({artifact_path}); "
                "no diagnostic content produced",
                checks,
            )
        if not any(checks.values()):
            return _result(
                QUALITY_NOOP,
                "closing_monitor: no text, no artifact, no changed files, short duration",
                checks,
            )
        return _result(
            QUALITY_EMPTY_ARTIFACT,
            "closing_monitor: no minimum valid content (pending/computed/stale counts missing)",
            checks,
        )

    # ── Generic task validation ──────────────────────────────────────────
    # Tier 1: changed_files with non-empty content → VALID
    if checks["has_changed_files"] and checks["has_valid_text"]:
        return _result(QUALITY_VALID, "changed files + substantive text output", checks)

    # Tier 2: changed_files alone → DIAGNOSTIC_ONLY (state changed but minimal narration)
    if checks["has_changed_files"]:
        return _result(
            QUALITY_DIAGNOSTIC_ONLY,
            "changed files recorded but completed_text is sparse",
            checks,
        )

    # Tier 3: substantial text alone → VALID
    if checks["has_valid_text"]:
        return _result(QUALITY_VALID, "substantive completed_text output", checks)

    # Tier 4: non-empty artifact → DIAGNOSTIC_ONLY
    if checks["artifact_nonempty"]:
        return _result(
            QUALITY_DIAGNOSTIC_ONLY,
            "artifact file has content but no completed_text",
            checks,
        )

    # Tier 5: empty artifact + long duration → EMPTY_ARTIFACT (provider ran but produced nothing)
    if artifact_path and os.path.isfile(artifact_path):
        return _result(
            QUALITY_EMPTY_ARTIFACT,
            f"artifact file exists but is empty ({artifact_path}); completed_text also empty",
            checks,
        )

    # Tier 6: nothing at all + very short duration → NOOP
    if duration <= _MAX_NOOP_DURATION_SECONDS:
        return _result(
            QUALITY_NOOP,
            f"no text, no artifact, no changed files, duration={duration}s (≤{_MAX_NOOP_DURATION_SECONDS}s threshold)",
            checks,
        )

    # Tier 7: nothing but took time → EMPTY_ARTIFACT (provider ran long enough but no output)
    return _result(
        QUALITY_EMPTY_ARTIFACT,
        f"no output produced despite duration={duration}s",
        checks,
    )


def _result(quality: str, reason: str, checks: dict[str, bool]) -> dict[str, Any]:
    return {
        "quality": quality,
        "reason": reason,
        "valid": quality in QUALITY_EFFECTIVE_STATES,
        "checks": checks,
    }


def quality_label(quality: str | None) -> str:
    """Human-readable short label for a quality state."""
    labels = {
        QUALITY_VALID:           "Valid",
        QUALITY_DIAGNOSTIC_ONLY: "Diagnostic Only",
        QUALITY_EMPTY_ARTIFACT:  "Empty Artifact",
        QUALITY_NOOP:            "No-Op",
        QUALITY_FAILED:          "Failed",
        QUALITY_NEEDS_RETRY:     "Needs Retry",
    }
    return labels.get(quality or "", quality or "Unknown")
