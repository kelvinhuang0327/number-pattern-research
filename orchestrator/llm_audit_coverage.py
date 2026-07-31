"""
llm_audit_coverage.py
=====================
靜態稽核覆蓋率檢查器。

掃描已知的 external LLM 呼叫路徑，確認每條路徑是否有 AuditGuard 包裹。
回傳 coverage_status: "FULL" | "PARTIAL" | "FAILED" 供 Decision Card 使用。

已知路徑 (2026-01 Phase A1 基準):
  - worker_tick.py  : execute_task_with_claude   (AuditGuard: ✅)
  - worker_tick.py  : execute_task_with_codex    (AuditGuard: ✅)
  - copilot_daemon.py: _execute_task gh-copilot path (AuditGuard: ✅)
  - copilot_daemon.py: _execute_task codex-fallback  (AuditGuard: ✅, same audit block)
  - telegram_bot/bot.py: OpenAI calls             (AuditGuard: ❌ intentionally excluded)
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import NamedTuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CallPath(NamedTuple):
    file: str          # workspace-relative path
    function: str      # function/method name
    provider: str      # expected LLM provider
    guarded: bool      # True = AuditGuard expected and verified
    excluded: bool     # True = intentionally not guarded (bot / test / etc.)
    note: str


# ─── 靜態基準表 ──────────────────────────────────────────────────────────────
_KNOWN_PATHS: list[CallPath] = [
    CallPath(
        file="orchestrator/worker_tick.py",
        function="execute_task_with_claude",
        provider="claude",
        guarded=True,
        excluded=False,
        note="Claude subprocess guarded by AuditGuard",
    ),
    CallPath(
        file="orchestrator/worker_tick.py",
        function="execute_task_with_codex",
        provider="codex",
        guarded=True,
        excluded=False,
        note="Codex subprocess guarded by AuditGuard",
    ),
    CallPath(
        file="orchestrator/copilot_daemon.py",
        function="_execute_task",
        provider="github-copilot",
        guarded=True,
        excluded=False,
        note="gh copilot + codex-fallback both audited in _execute_task AuditGuard block",
    ),
    CallPath(
        file="telegram_bot/bot.py",
        function="(openai calls)",
        provider="openai",
        guarded=False,
        excluded=True,
        note="Telegram bot: intentionally excluded — not orchestrator-controlled path",
    ),
]


def _check_file_has_audit_guard(rel_path: str, function_name: str) -> bool:
    """Parse the source file and check the named function contains AuditGuard usage."""
    abs_path = PROJECT_ROOT / rel_path
    if not abs_path.exists():
        return False
    try:
        source = abs_path.read_text(encoding="utf-8")
    except OSError:
        return False

    # Quick string scan — faster than full AST for this purpose
    # Search for AuditGuard usage in proximity to the function
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == function_name:
                func_src = ast.get_source_segment(source, node) or ""
                return "AuditGuard" in func_src
    return False


def check_coverage() -> dict:
    """
    檢查所有已知路徑的 AuditGuard 覆蓋狀態。

    Returns:
        {
            "coverage_status": "FULL" | "PARTIAL" | "FAILED",
            "covered_paths":   list[str],
            "uncovered_paths": list[str],
            "excluded_paths":  list[str],
            "warnings":        list[str],
        }
    """
    covered: list[str] = []
    uncovered: list[str] = []
    excluded: list[str] = []
    warnings: list[str] = []

    for cp in _KNOWN_PATHS:
        label = f"{cp.file}::{cp.function} [{cp.provider}]"

        if cp.excluded:
            excluded.append(f"{label} — {cp.note}")
            continue

        if cp.guarded:
            # Dynamic verification: actually check the source
            verified = _check_file_has_audit_guard(cp.file, cp.function)
            if verified:
                covered.append(f"{label} — {cp.note}")
            else:
                uncovered.append(label)
                warnings.append(
                    f"AuditGuard NOT found in {cp.file}::{cp.function} "
                    f"(expected for provider={cp.provider})"
                )
        else:
            uncovered.append(label)
            warnings.append(f"No AuditGuard planned for {label}")

    if not uncovered:
        status = "FULL"
    elif covered:
        status = "PARTIAL"
    else:
        status = "FAILED"

    return {
        "coverage_status": status,
        "covered_paths": covered,
        "uncovered_paths": uncovered,
        "excluded_paths": excluded,
        "warnings": warnings,
    }


if __name__ == "__main__":
    import json
    result = check_coverage()
    print(json.dumps(result, indent=2, ensure_ascii=False))
