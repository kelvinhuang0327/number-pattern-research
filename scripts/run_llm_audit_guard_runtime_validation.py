#!/usr/bin/env python3
"""
scripts/run_llm_audit_guard_runtime_validation.py
==================================================
Phase A2 — LLM Audit Guard Runtime Validation

執行四項無外部配額消耗的驗證：
  1. Audit Coverage Checker     — 確認 FULL coverage
  2. Blocked-Call Smoke         — 確認 BLOCKED 事件正確寫入，無 subprocess 呼叫
  3. Allowed Mocked-Call Smoke  — 確認 ATTEMPT + RESULT + Usage 生命週期
  4. API Schema Check           — 確認 audit/usage 模組回傳穩定 schema

Exit code 0 → LLM_AUDIT_GUARD_RUNTIME_VERIFIED
Exit code 1 → one or more checks failed
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Any
from unittest.mock import MagicMock, patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── ANSI colours ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

_results: list[dict] = []


def _pass(name: str, detail: str = "") -> None:
    tag = f"{GREEN}PASS{RESET}"
    print(f"  [{tag}] {name}" + (f" — {detail}" if detail else ""))
    _results.append({"check": name, "status": "PASS", "detail": detail})


def _fail(name: str, detail: str = "") -> None:
    tag = f"{RED}FAIL{RESET}"
    print(f"  [{tag}] {name}" + (f" — {detail}" if detail else ""))
    _results.append({"check": name, "status": "FAIL", "detail": detail})


def _section(title: str) -> None:
    bar = "─" * 60
    print(f"\n{BOLD}{bar}{RESET}")
    print(f"{BOLD}{title}{RESET}")
    print(f"{BOLD}{bar}{RESET}")


# ── Check 1: Coverage ─────────────────────────────────────────────────────────

def check_coverage() -> None:
    _section("CHECK 1 — Audit Coverage Checker")
    try:
        from orchestrator.llm_audit_coverage import check_coverage as _cov
        result = _cov()
        status = result["coverage_status"]
        covered = result.get("covered_paths", [])
        uncovered = result.get("uncovered_paths", [])
        excluded = result.get("excluded_paths", [])

        print(f"  coverage_status : {status}")
        for p in covered:
            print(f"    ✅ {p}")
        for p in excluded:
            print(f"    ℹ️  {p} (excluded)")
        for p in uncovered:
            print(f"    ❌ {p}")

        if status == "FULL":
            _pass("coverage_status=FULL", f"{len(covered)} covered, {len(excluded)} excluded")
        elif status == "PARTIAL" and not uncovered:
            _pass("coverage_status=PARTIAL (no unguarded paths)", f"{len(excluded)} excluded")
        else:
            _fail("coverage_checker", f"status={status}, uncovered={uncovered}")
    except Exception as exc:
        _fail("coverage_checker", f"exception: {exc}")


# ── Check 2: Blocked-Call Smoke ───────────────────────────────────────────────

def check_blocked_smoke() -> None:
    _section("CHECK 2 — Blocked-Call Smoke (Planner → Claude)")
    import orchestrator.llm_audit as audit_mod

    tmp = tempfile.mkdtemp()
    original_path = audit_mod._AUDIT_PATH
    audit_path = os.path.join(tmp, "smoke_blocked.jsonl")
    audit_mod._AUDIT_PATH = audit_path

    try:
        from orchestrator.provider_factory import ProviderFactory, ProviderRoleViolationError

        # 1. ProviderFactory blocks planner→claude
        planner_blocked = False
        try:
            ProviderFactory.assert_role_allowed("planner", "claude")
        except ProviderRoleViolationError:
            planner_blocked = True

        if planner_blocked:
            _pass("provider_factory_blocks_planner_claude")
        else:
            _fail("provider_factory_blocks_planner_claude", "no exception raised")

        # 2. Write BLOCKED event
        from orchestrator.llm_audit import write_blocked
        write_blocked(
            runner="planner",
            provider="claude",
            block_reason="PLANNER_EXTERNAL_BLOCKED",
            trigger_source="validation_smoke",
        )

        # 3. Read and verify
        records = _read_jsonl(audit_path)
        blocked_ev = [r for r in records if r.get("event_type") == "LLM_CALL_BLOCKED"]
        attempt_ev = [r for r in records if r.get("event_type") == "LLM_CALL_ATTEMPT"]

        print(f"  audit records  : {len(records)}")
        print(f"  BLOCKED events : {len(blocked_ev)}")
        print(f"  ATTEMPT events : {len(attempt_ev)}")

        if len(blocked_ev) == 1:
            _pass("blocked_event_written", f"reason={blocked_ev[0].get('block_reason')}")
        else:
            _fail("blocked_event_written", f"expected 1, got {len(blocked_ev)}")

        if len(attempt_ev) == 0:
            _pass("no_attempt_after_block")
        else:
            _fail("no_attempt_after_block", f"found {len(attempt_ev)} ATTEMPT events")

    finally:
        audit_mod._AUDIT_PATH = original_path


# ── Check 3: Allowed Mocked-Call Smoke ───────────────────────────────────────

def check_allowed_smoke() -> None:
    _section("CHECK 3 — Allowed Mocked-Call Smoke (Worker → Claude mock)")
    import orchestrator.llm_audit as audit_mod
    import orchestrator.llm_usage_logger as usage_mod

    tmp = tempfile.mkdtemp()
    orig_audit = audit_mod._AUDIT_PATH
    orig_usage = usage_mod._LOG_PATH
    audit_path = os.path.join(tmp, "smoke_allowed_audit.jsonl")
    usage_path = os.path.join(tmp, "smoke_allowed_usage.jsonl")
    audit_mod._AUDIT_PATH = audit_path
    usage_mod._LOG_PATH = usage_path

    subprocess_called: list = []

    def mock_run(*args, **kwargs):
        cmd = args[0] if args else []
        if isinstance(cmd, list) and cmd and cmd[0] == "git":
            m = MagicMock(); m.returncode = 0; m.stdout = ""; m.stderr = ""
            return m
        subprocess_called.append(cmd)
        m = MagicMock()
        m.returncode = 0
        m.stdout = "# Mock output"
        m.stderr = ""
        return m

    try:
        with patch("subprocess.run", side_effect=mock_run), \
             patch("shutil.which", return_value="/usr/bin/claude"), \
             patch("os.path.isfile", return_value=True), \
             patch("orchestrator.execution_policy.evaluate_execution",
                   return_value={"allowed": True, "mode": "safe-run", "reason": None}), \
             patch("orchestrator.execution_policy.record_llm_call"), \
             patch("orchestrator.provider_factory.ProviderFactory.assert_role_allowed",
                   staticmethod(lambda r, p: None)):

            import orchestrator.worker_tick as wt
            with tempfile.TemporaryDirectory() as td:
                prompt_path = os.path.join(td, "task.md")
                with open(prompt_path, "w") as fh:
                    fh.write("# Mock task")
                task = {
                    "id": 1001,
                    "slot_key": "smoke-allowed",
                    "prompt_file_path": prompt_path,
                    "expected_duration_hours": 0.01,
                }
                result = wt.execute_task_with_claude(task)

        audit_records = _read_jsonl(audit_path)
        usage_records = _read_jsonl(usage_path)
        ev_types = [r.get("event_type") for r in audit_records]

        print(f"  subprocess calls  : {len(subprocess_called)}")
        print(f"  audit events      : {ev_types}")
        print(f"  usage records     : {len(usage_records)}")
        print(f"  worker success    : {result.get('success')}")

        if len(subprocess_called) == 1:
            _pass("subprocess_called_once")
        else:
            _fail("subprocess_called_once", f"got {len(subprocess_called)}")

        if "LLM_CALL_ATTEMPT" in ev_types:
            _pass("audit_attempt_event_written")
        else:
            _fail("audit_attempt_event_written", f"events={ev_types}")

        if "LLM_CALL_RESULT" in ev_types:
            _pass("audit_result_event_written")
        else:
            _fail("audit_result_event_written", f"events={ev_types}")

        if len(usage_records) == 1:
            _pass("usage_record_written")
        else:
            _fail("usage_record_written", f"got {len(usage_records)}")

        if result.get("success") is True:
            _pass("worker_task_succeeded")
        else:
            _fail("worker_task_succeeded", f"result={result}")

        # Verify correlation IDs match
        attempt = next((r for r in audit_records if r.get("event_type") == "LLM_CALL_ATTEMPT"), None)
        res_rec = next((r for r in audit_records if r.get("event_type") == "LLM_CALL_RESULT"), None)
        if attempt and res_rec and attempt.get("correlation_id") == res_rec.get("correlation_id"):
            _pass("correlation_id_matched_attempt_result")
        else:
            _fail("correlation_id_matched_attempt_result")

    finally:
        audit_mod._AUDIT_PATH = orig_audit
        usage_mod._LOG_PATH = orig_usage


# ── Check 4: API Schema ───────────────────────────────────────────────────────

def check_api_schema() -> None:
    _section("CHECK 4 — API Schema Validation")
    try:
        from orchestrator.llm_audit import read_audit_records, build_audit_today_summary
        today = build_audit_today_summary()
        required_today_keys = {"date", "total_events", "attempts", "results", "blocked", "by_role", "by_provider"}
        missing = required_today_keys - set(today.keys())
        if not missing:
            _pass("llm_audit_today_schema", f"keys={list(today.keys())}")
        else:
            _fail("llm_audit_today_schema", f"missing keys: {missing}")

        recent = read_audit_records(hours=24, tail=5)
        _pass("llm_audit_recent_returns_list", f"count={len(recent)}")
    except Exception as exc:
        _fail("llm_audit_schema", f"exception: {exc}")

    try:
        from orchestrator.llm_usage_summary import get_usage_summary
        usage = get_usage_summary(window="today", limit=5)
        required_usage_keys = {"window", "total", "roles", "warnings", "recent"}
        missing = required_usage_keys - set(usage.keys())
        if not missing:
            _pass("llm_usage_today_schema", f"keys={list(usage.keys())}")
        else:
            _fail("llm_usage_today_schema", f"missing keys: {missing}")
    except Exception as exc:
        _fail("llm_usage_schema", f"exception: {exc}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _read_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    records = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                records.append(json.loads(line))
    return records


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}LLM Audit Guard Runtime Validation — Phase A2{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    check_coverage()
    check_blocked_smoke()
    check_allowed_smoke()
    check_api_schema()

    # Summary
    _section("SUMMARY")
    passed = [r for r in _results if r["status"] == "PASS"]
    failed = [r for r in _results if r["status"] == "FAIL"]

    for r in _results:
        icon = f"{GREEN}✅{RESET}" if r["status"] == "PASS" else f"{RED}❌{RESET}"
        print(f"  {icon} {r['check']}")
        if r["detail"] and r["status"] == "FAIL":
            print(f"       {YELLOW}→ {r['detail']}{RESET}")

    print(f"\n  Total: {len(_results)}  Passed: {len(passed)}  Failed: {len(failed)}")

    if not failed:
        print(f"\n{BOLD}{GREEN}✅ LLM_AUDIT_GUARD_RUNTIME_VERIFIED{RESET}\n")
        return 0
    else:
        print(f"\n{BOLD}{RED}❌ VALIDATION FAILED — {len(failed)} check(s) failed{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
