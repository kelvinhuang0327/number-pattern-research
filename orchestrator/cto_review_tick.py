#!/usr/bin/env python3
"""
CTO review tick — batches pending git commits, classifies them, reviews them,
optionally cherry-picks approved commits into a CTO merge branch, and writes
Markdown / JSON reports for the UI.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator import common, db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [cto-review] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

RUNNER = "cto-review"
DECISION_PENDING = "PENDING_REVIEW"
DECISION_SKIPPED = "SKIPPED_GIT_COMMIT"
DECISION_APPROVED = "APPROVED_FOR_MERGE"
DECISION_MERGED = "MERGED"
DECISION_REPLAN = "REJECTED_NEEDS_REPLAN"
DECISION_CLOSED = "REJECTED_CLOSED"
DECISION_DEPENDENCY = "REJECTED_DEPENDENCY"
DECISION_CONFLICT = "DEFERRED_CONFLICT"
DECISION_INVALID = "REJECTED_INVALID_COMMIT"
DECISION_SUPERSEDED = "SUPERSEDED"
DECISION_DUPLICATE = "DUPLICATE"
DECISION_MERGE_FAIL = "MERGE_VALIDATION_FAILED"

# ─── Decision Intelligence Schema ─────────────────────────────────────────────

SEVERITY_RANK: dict[str, int] = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}

_DECISION_SEVERITY: dict[str, str] = {
    DECISION_SKIPPED:      "LOW",
    DECISION_DUPLICATE:    "LOW",
    DECISION_SUPERSEDED:   "LOW",
    DECISION_CLOSED:       "LOW",
    DECISION_MERGED:       "LOW",
    DECISION_APPROVED:     "LOW",
    DECISION_DEPENDENCY:   "MEDIUM",
    DECISION_REPLAN:       "HIGH",
    DECISION_INVALID:      "HIGH",
    DECISION_CONFLICT:     "HIGH",
    DECISION_MERGE_FAIL:   "CRITICAL",
}

_DECISION_URGENCY: dict[str, str] = {
    DECISION_SKIPPED:      "LONG",
    DECISION_DUPLICATE:    "LONG",
    DECISION_SUPERSEDED:   "LONG",
    DECISION_CLOSED:       "LONG",
    DECISION_MERGED:       "LONG",
    DECISION_APPROVED:     "LONG",
    DECISION_DEPENDENCY:   "SHORT",
    DECISION_REPLAN:       "SHORT",
    DECISION_INVALID:      "SHORT",
    DECISION_CONFLICT:     "IMMEDIATE",
    DECISION_MERGE_FAIL:   "IMMEDIATE",
}

_DECISION_BASE_IMPACT: dict[str, int] = {
    DECISION_SKIPPED:      5,
    DECISION_DUPLICATE:    5,
    DECISION_SUPERSEDED:   5,
    DECISION_CLOSED:       10,
    DECISION_MERGED:       10,
    DECISION_APPROVED:     15,
    DECISION_DEPENDENCY:   40,
    DECISION_REPLAN:       55,
    DECISION_INVALID:      65,
    DECISION_CONFLICT:     75,
    DECISION_MERGE_FAIL:   90,
}

_DECISION_ACTION_MAP: dict[str, dict] = {
    DECISION_MERGED: {
        "action": "已合併，無需操作",
        "priority": "LOW",
        "expected_benefit": "功能已整合至主線",
        "risk_note": "低風險；cherry-pick 成功",
        "create_task": False,
    },
    DECISION_APPROVED: {
        "action": "等待合併確認",
        "priority": "MEDIUM",
        "expected_benefit": "通過審查，等待部署整合",
        "risk_note": "已審核通過；等待 merge 完成",
        "create_task": False,
    },
    DECISION_REPLAN: {
        "action": "重新規劃任務：Gate 驗收未通過，需修正後重新提交",
        "priority": "HIGH",
        "expected_benefit": "修正 gate 問題，確保品質後再整合",
        "risk_note": "若直接合併可能引入缺陷，需強制 replan",
        "create_task": True,
    },
    DECISION_CONFLICT: {
        "action": "立即解決 cherry-pick 衝突，恢復合併流程",
        "priority": "IMMEDIATE",
        "expected_benefit": "解除衝突後可恢復正常流水線",
        "risk_note": "衝突若未解決將阻塞後續所有提交",
        "create_task": True,
    },
    DECISION_INVALID: {
        "action": "檢查 commit scope 設定，移除範圍外檔案後重新提交",
        "priority": "HIGH",
        "expected_benefit": "確保 commit 範圍符合任務定義，避免越界副作用",
        "risk_note": "Commit 包含範圍外檔案，可能造成意外副作用",
        "create_task": True,
    },
    DECISION_MERGE_FAIL: {
        "action": "立即排查合併失敗原因，修復 git 狀態，確認 pipeline 健康",
        "priority": "IMMEDIATE",
        "expected_benefit": "恢復合併流水線正常運作",
        "risk_note": "CRITICAL：合併失敗可能代表系統性問題，需立即處理",
        "create_task": True,
    },
    DECISION_DEPENDENCY: {
        "action": "先完成上游依賴任務，再重新排入審核隊列",
        "priority": "SHORT",
        "expected_benefit": "確保依賴鏈完整後合併，避免功能缺失",
        "risk_note": "依賴未就緒若強制合併會導致功能缺失",
        "create_task": False,
    },
    DECISION_SUPERSEDED: {
        "action": "確認已被較新版本取代，無需額外操作",
        "priority": "LOW",
        "expected_benefit": "自動清理舊版本，避免重複合併",
        "risk_note": "低風險；系統自動檢測並跳過",
        "create_task": False,
    },
    DECISION_DUPLICATE: {
        "action": "無需操作，已去重",
        "priority": "LOW",
        "expected_benefit": "避免重複審核浪費資源",
        "risk_note": "無風險",
        "create_task": False,
    },
    DECISION_CLOSED: {
        "action": "任務已取消，commit 關閉；確認取消決策是否正確",
        "priority": "LOW",
        "expected_benefit": "清理無效提交，保持 queue 整潔",
        "risk_note": "低風險；確認取消決策是否有意為之",
        "create_task": False,
    },
}

_CATEGORY_FILE_PATTERNS: list[tuple[str, list[str]]] = [
    ("validation",       ["test", "spec", "__test", "_test.", "pytest", "conftest"]),
    ("knowledge_system", ["wiki/", "memory/", "docs/", ".md", "lessons"]),
    ("architecture",     ["orchestrator/", "api.py", "api/", "config/", "schema", "db.py", "db/"]),
    ("uiux",             [".html", ".css", "frontend/", "src/ui", "styles", "index.html"]),
    ("tech_debt",        ["legacy/", "archive/", "deprecated", "refactor", "cleanup"]),
]


def _classify_files(files: list[str]) -> str:
    files_lower = [str(f).lower() for f in (files or [])]
    for category, patterns in _CATEGORY_FILE_PATTERNS:
        if any(p in f for f in files_lower for p in patterns):
            return category
    return "functionality"


def _extract_from_steps(steps: list[dict]) -> dict:
    """Extract key facts from decision steps evidence for scoring/classification."""
    result: dict[str, Any] = {
        "actual_files": [],
        "high_conflict_paths": [],
        "has_scope_violation": False,
        "has_git_conflict": False,
    }
    for step in (steps or []):
        evidence = step.get("evidence") or {}
        name = step.get("step", "")
        status = step.get("status", "")
        if name == "check_changed_files_scope":
            if status == "FAIL":
                result["has_scope_violation"] = True
            result["actual_files"] = evidence.get("actual_files") or evidence.get("extra_files") or []
        if name == "check_protected_paths":
            result["high_conflict_paths"] = evidence.get("high_conflict_paths") or []
        if name == "merge_validation" and status == "FAIL":
            output = str(evidence.get("output") or "").lower()
            if "conflict" in output:
                result["has_git_conflict"] = True
    return result


def _score_decision(decision: str, steps: list[dict], extra_conflict_paths: list[str]) -> dict:
    severity = _DECISION_SEVERITY.get(decision, "MEDIUM")
    urgency = _DECISION_URGENCY.get(decision, "SHORT")
    base_impact = _DECISION_BASE_IMPACT.get(decision, 50)
    extracted = _extract_from_steps(steps)
    high_conflict = extracted["high_conflict_paths"] or extra_conflict_paths or []
    impact_boost = min(20, len(high_conflict) * 5)
    if extracted["has_scope_violation"]:
        impact_boost += 15
    impact_score = min(100, base_impact + impact_boost)
    confidence: float = 0.9 if decision in (DECISION_MERGED, DECISION_DUPLICATE, DECISION_SUPERSEDED) else 0.75
    if decision in (DECISION_CONFLICT, DECISION_MERGE_FAIL):
        confidence = 1.0
    return {
        "severity": severity,
        "impact_score": impact_score,
        "confidence": round(confidence, 2),
        "urgency": urgency,
        "high_conflict_paths": high_conflict[:10],
    }


def _build_action(task_id: Any, commit_sha: str, decision: str, reason: str) -> dict:
    base = dict(_DECISION_ACTION_MAP.get(decision, {
        "action": f"手動確認決策狀態：{decision}",
        "priority": "MEDIUM",
        "expected_benefit": "確保系統正常運作",
        "risk_note": "未知狀態，需手動確認",
        "create_task": False,
    }))
    if decision == DECISION_REPLAN and reason:
        base["action"] = f"重新規劃任務 #{task_id}：{reason[:120]}"
    if decision == DECISION_CONFLICT:
        base["action"] = f"立即解決 cherry-pick 衝突 ({str(commit_sha)[:12]})，恢復合併流程"
    base["task_id"] = task_id
    base["commit_sha"] = str(commit_sha or "")[:12]
    return base


def _compute_health_score(run_record: dict, enriched_decisions: list[dict]) -> int:
    candidates = run_record.get("candidate_count") or 0
    if candidates == 0:
        return 100
    merged = run_record.get("merged_count") or 0
    approved = run_record.get("approved_count") or 0
    rejected = run_record.get("rejected_count") or 0
    deferred = run_record.get("deferred_count") or 0
    processed = merged + rejected + deferred
    success_rate = (merged / processed) if processed > 0 else (0.8 if approved > 0 else 0.5)
    base = int(success_rate * 70)
    critical_count = sum(1 for d in enriched_decisions if (d.get("scoring") or {}).get("severity") == "CRITICAL")
    high_count = sum(1 for d in enriched_decisions if (d.get("scoring") or {}).get("severity") == "HIGH")
    if critical_count == 0:
        base += 20
    else:
        base = max(0, base - critical_count * 20)
    if high_count == 0:
        base += 10
    else:
        base = max(0, base - high_count * 5)
    return max(0, min(100, base))


def _cto_verdict(health_score: int, enriched_decisions: list[dict]) -> str:
    has_critical = any((d.get("scoring") or {}).get("severity") == "CRITICAL" for d in enriched_decisions)
    has_immediate = any((d.get("scoring") or {}).get("urgency") == "IMMEDIATE" for d in enriched_decisions)
    if has_critical or health_score < 40:
        return "STOP"
    if has_immediate or health_score < 70:
        return "CAUTION"
    return "GO"


def _build_executive_summary(run_record: dict, enriched_decisions: list[dict], health_score: int, verdict: str) -> dict:
    sorted_d = sorted(
        enriched_decisions,
        key=lambda d: (
            -SEVERITY_RANK.get((d.get("scoring") or {}).get("severity", "LOW"), 1),
            -(d.get("scoring") or {}).get("impact_score", 0),
        ),
    )
    top_risks = []
    for d in sorted_d:
        s = d.get("scoring") or {}
        if s.get("severity") in ("HIGH", "CRITICAL") or s.get("impact_score", 0) >= 60:
            top_risks.append({
                "task_id": d.get("task_id"),
                "commit_sha": str(d.get("commit_sha") or "")[:12],
                "severity": s.get("severity"),
                "impact_score": s.get("impact_score"),
                "urgency": s.get("urgency"),
                "decision": d.get("decision"),
                "description": d.get("reason") or d.get("decision"),
            })
        if len(top_risks) >= 3:
            break
    top_actions = []
    for d in sorted_d:
        a = d.get("action") or {}
        if a.get("priority") in ("IMMEDIATE", "HIGH") or a.get("create_task"):
            top_actions.append({
                "task_id": d.get("task_id"),
                "action": a.get("action"),
                "priority": a.get("priority"),
                "create_task": a.get("create_task", False),
                "expected_benefit": a.get("expected_benefit"),
            })
        if len(top_actions) >= 3:
            break
    return {
        "health_score": health_score,
        "verdict": verdict,
        "top_risks": top_risks,
        "top_actions": top_actions,
        "candidate_count": run_record.get("candidate_count", 0),
        "merged_count": run_record.get("merged_count", 0),
        "approved_count": run_record.get("approved_count", 0),
        "rejected_count": run_record.get("rejected_count", 0),
        "deferred_count": run_record.get("deferred_count", 0),
        "superseded_count": run_record.get("superseded_count", 0),
        "duplicate_count": run_record.get("duplicate_count", 0),
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _json_loads(raw: Any, default: Any):
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        value = raw.strip()
        if not value:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return default


def _read_text(path: Optional[str]) -> str:
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            return handle.read()
    except OSError:
        return ""


def _load_task_context(commit_row: dict) -> dict:
    task = db.get_task(int(commit_row["task_id"]))
    if not task:
        return {
            "task": None,
            "meta": {},
            "task_result": {},
            "contract": {},
            "changed_files": _json_loads(commit_row.get("changed_files_json"), []),
            "task_contract_path": None,
            "task_result_path": None,
        }

    meta = common.read_meta(task["slot_key"], task["date_folder"])
    if not isinstance(meta, dict):
        meta = {}

    contract_path = meta.get("task_contract_path") or common.contract_path(task["slot_key"], task.get("slug") or "task", task["date_folder"])
    result_path = meta.get("task_result_path") or common.result_path(task["slot_key"], task.get("slug") or "task", task["date_folder"])
    contract = _json_loads(_read_text(contract_path), {})
    task_result = _json_loads(_read_text(result_path), {})
    if not isinstance(task_result, dict):
        task_result = {}

    changed_files = _json_loads(commit_row.get("changed_files_json"), [])
    if not changed_files:
        changed_files = _json_loads(task.get("changed_files_json"), [])
    if not changed_files:
        changed_files = _json_loads(task_result.get("changed_files"), [])

    return {
        "task": task,
        "meta": meta,
        "task_result": task_result if isinstance(task_result, dict) else {},
        "contract": contract if isinstance(contract, dict) else {},
        "changed_files": changed_files if isinstance(changed_files, list) else [],
        "task_contract_path": contract_path,
        "task_result_path": result_path,
    }


def _decision_step(step: str, status: str, summary: str, evidence: Any = None) -> dict:
    return {
        "step": step,
        "status": status,
        "summary": summary,
        "evidence": evidence,
    }


def _commit_changed_files(commit_sha: str) -> list[str]:
    if not commit_sha:
        return []
    try:
        result = subprocess.run(
            ["git", "-C", common.ROOT, "show", "--pretty=", "--name-only", commit_sha],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        return [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    except Exception as exc:
        logger.warning("failed to inspect commit diff for %s: %s", commit_sha, exc)
        return []


def _find_latest_run_time() -> Optional[datetime]:
    latest = db.get_latest_cto_review_run()
    if not latest:
        return None
    return _parse_iso(latest.get("completed_at") or latest.get("started_at"))


def _should_skip_for_frequency(frequency_mode: str) -> bool:
    latest = _find_latest_run_time()
    if not latest:
        return False
    now = datetime.now(timezone.utc)
    elapsed = now - latest
    if frequency_mode == "once_daily":
        return elapsed < timedelta(hours=20)
    if frequency_mode == "twice_daily":
        return elapsed < timedelta(hours=10)
    return False


def _build_run_id(started_at: datetime) -> str:
    local = started_at.astimezone(timezone(timedelta(hours=8)))
    return f"cto-{local.strftime('%Y%m%d-%H%M%S')}"


def _build_report_paths(run_id: str, started_at: datetime) -> tuple[str, str]:
    date_folder = started_at.astimezone(timezone(timedelta(hours=8))).strftime("%Y%m%d")
    report_dir = os.path.join(common.ORCH_ROOT, "cto_reviews", date_folder)
    os.makedirs(report_dir, exist_ok=True)
    return (
        os.path.join(report_dir, f"{run_id}-report.md"),
        os.path.join(report_dir, f"{run_id}-report.json"),
    )


def _build_review_summary(context: dict, decision: str, reason: str) -> str:
    task = context.get("task") or {}
    return (
        f"Task #{task.get('id')} / {task.get('title') or '—'} — {decision}"
        + (f" | {reason}" if reason else "")
    )


def _record_review(
    commit_row: dict,
    review_run_id: str,
    decision: str,
    reason: str,
    checked_from: str,
    checked_until: str,
    steps: list[dict],
    reviewer_role: str = "cto-reviewer",
):
    context = _load_task_context(commit_row)
    summary = _build_review_summary(context, decision, reason)
    db.insert_task_git_review(
        commit_sha=commit_row.get("commit_sha"),
        task_id=commit_row.get("task_id"),
        review_run_id=review_run_id,
        decision=decision,
        reason=reason,
        checked_from=checked_from,
        checked_until=checked_until,
        review_summary=summary,
        decision_steps=steps,
        reviewer_role=reviewer_role,
    )
    db.upsert_task_git_commit(
        task_id=commit_row.get("task_id"),
        slot_key=commit_row.get("slot_key"),
        task_title=commit_row.get("task_title"),
        source_branch=commit_row.get("source_branch"),
        commit_sha=commit_row.get("commit_sha"),
        commit_message=commit_row.get("commit_message"),
        integration_group=commit_row.get("integration_group"),
        review_priority=commit_row.get("review_priority"),
        safe_to_autocommit=commit_row.get("safe_to_autocommit"),
        status=decision,
        reviewer_role=reviewer_role,
        reviewed_at=_now_iso(),
        merge_branch=commit_row.get("merge_branch"),
        merge_commit_sha=commit_row.get("merge_commit_sha"),
        reject_reason=reason,
        superseded_by_task_id=commit_row.get("superseded_by_task_id"),
        superseded_by_commit_sha=commit_row.get("superseded_by_commit_sha"),
        changed_files=_json_loads(commit_row.get("changed_files_json"), []),
        depends_on_tasks=_json_loads(commit_row.get("depends_on_tasks_json"), []),
        depends_on_commits=_json_loads(commit_row.get("depends_on_commits_json"), []),
        high_conflict_paths=_json_loads(commit_row.get("high_conflict_paths_json"), []),
        task_status=commit_row.get("task_status"),
        gate_verdict=commit_row.get("gate_verdict"),
        gate_reason=commit_row.get("gate_reason"),
    )


def _load_dependency_record(task_id: int = None, commit_sha: str = None) -> Optional[dict]:
    if task_id is not None:
        return db.get_task_git_commit_for_task(int(task_id))
    if commit_sha:
        return db.get_task_git_commit_by_sha(commit_sha)
    return None


def _evaluate_commit(commit_row: dict, pending_group_latest: dict) -> dict:
    context = _load_task_context(commit_row)
    task = context.get("task") or {}
    task_result = context.get("task_result") or {}
    changed_files = context.get("changed_files") or []
    declared_changed_files = _json_loads(commit_row.get("changed_files_json"), [])
    if not declared_changed_files:
        declared_changed_files = changed_files
    decision_steps: list[dict] = []

    decision_steps.append(_decision_step(
        "load_task_context",
        "PASS" if task else "FAIL",
        "Loaded task, contract, and task result context" if task else "Task context missing",
        {
            "task_id": commit_row.get("task_id"),
            "slot_key": commit_row.get("slot_key"),
            "task_status": commit_row.get("task_status"),
            "gate_verdict": commit_row.get("gate_verdict"),
            "commit_sha": commit_row.get("commit_sha"),
        },
    ))
    if not task:
        return {"decision": DECISION_INVALID, "reason": "task context missing", "steps": decision_steps, "context": context}

    if commit_row.get("status") == DECISION_DUPLICATE or db.get_task_git_review_for_commit(commit_row.get("commit_sha") or ""):
        decision_steps.append(_decision_step(
            "final_decision",
            "PASS",
            "Commit already reviewed; skipping as duplicate",
            {"commit_sha": commit_row.get("commit_sha")},
        ))
        return {"decision": DECISION_DUPLICATE, "reason": "commit already reviewed", "steps": decision_steps, "context": context}

    task_status = str(commit_row.get("task_status") or task.get("status") or "").upper()
    gate_verdict = str(commit_row.get("gate_verdict") or task_result.get("gate_verdict") or "").upper()
    if task_status == "CANCELLED":
        decision_steps.append(_decision_step("validate_gate_verdict", "FAIL", "Task was cancelled", {"task_status": task_status}))
        return {"decision": DECISION_CLOSED, "reason": "task cancelled", "steps": decision_steps, "context": context}
    if task_status != "COMPLETED" or gate_verdict != "PASS":
        decision_steps.append(_decision_step(
            "validate_gate_verdict",
            "FAIL",
            f"Task status {task_status} / gate verdict {gate_verdict} is not merge-ready",
            {"task_status": task_status, "gate_verdict": gate_verdict, "gate_reason": task_result.get("gate_reason")},
        ))
        return {"decision": DECISION_REPLAN, "reason": task_result.get("gate_reason") or "gate verdict not PASS", "steps": decision_steps, "context": context}
    decision_steps.append(_decision_step(
        "validate_gate_verdict",
        "PASS",
        "Task completed with PASS gate verdict",
        {"task_status": task_status, "gate_verdict": gate_verdict},
    ))

    actual_changed_files = _commit_changed_files(commit_row.get("commit_sha") or "")
    expected_set = {str(path) for path in declared_changed_files if str(path).strip()}
    actual_set = set(actual_changed_files)
    if not actual_set:
        decision_steps.append(_decision_step(
            "check_changed_files_scope",
            "FAIL",
            "Could not inspect commit file list",
            {"commit_sha": commit_row.get("commit_sha")},
        ))
        return {"decision": DECISION_INVALID, "reason": "unable to inspect commit diff", "steps": decision_steps, "context": context}

    extra_files = sorted(actual_set - expected_set)
    if extra_files:
        decision_steps.append(_decision_step(
            "check_changed_files_scope",
            "FAIL",
            "Commit changes files outside the task scope",
            {"extra_files": extra_files[:20], "expected_count": len(expected_set), "actual_count": len(actual_set)},
        ))
        return {"decision": DECISION_INVALID, "reason": f"commit includes out-of-scope files: {', '.join(extra_files[:5])}", "steps": decision_steps, "context": context}
    decision_steps.append(_decision_step(
        "check_changed_files_scope",
        "PASS",
        "Commit files are within the task scope",
        {"actual_files": actual_changed_files[:20], "declared_files": declared_changed_files[:20]},
    ))

    high_conflict_paths = [path for path in actual_changed_files if common.is_high_conflict_path(path)]
    decision_steps.append(_decision_step(
        "check_protected_paths",
        "PASS" if not high_conflict_paths else "WARN",
        "Protected path review completed",
        {"high_conflict_paths": high_conflict_paths},
    ))

    depends_on_tasks = _json_loads(commit_row.get("depends_on_tasks_json"), [])
    depends_on_commits = _json_loads(commit_row.get("depends_on_commits_json"), [])
    dependency_evidence = []
    dependency_blockers = []
    for dep_task_id in depends_on_tasks if isinstance(depends_on_tasks, list) else []:
        dep_row = _load_dependency_record(task_id=dep_task_id)
        dependency_evidence.append({"task_id": dep_task_id, "record": dep_row.get("status") if dep_row else None})
        if not dep_row or dep_row.get("status") not in (DECISION_APPROVED, DECISION_MERGED):
            dependency_blockers.append({"task_id": dep_task_id, "status": dep_row.get("status") if dep_row else None})
    for dep_commit_sha in depends_on_commits if isinstance(depends_on_commits, list) else []:
        dep_row = _load_dependency_record(commit_sha=dep_commit_sha)
        dependency_evidence.append({"commit_sha": dep_commit_sha, "record": dep_row.get("status") if dep_row else None})
        if not dep_row or dep_row.get("status") not in (DECISION_APPROVED, DECISION_MERGED):
            dependency_blockers.append({"commit_sha": dep_commit_sha, "status": dep_row.get("status") if dep_row else None})
    if dependency_blockers:
        decision_steps.append(_decision_step(
            "check_dependency",
            "FAIL",
            "Dependencies are not ready",
            {"dependency_blockers": dependency_blockers, "dependency_evidence": dependency_evidence},
        ))
        return {"decision": DECISION_DEPENDENCY, "reason": "dependency not ready", "steps": decision_steps, "context": context}
    decision_steps.append(_decision_step(
        "check_dependency",
        "PASS",
        "Dependencies are satisfied",
        {"dependency_evidence": dependency_evidence},
    ))

    if pending_group_latest and commit_row.get("commit_sha") != pending_group_latest.get("commit_sha"):
        decision_steps.append(_decision_step(
            "check_conflict_risk",
            "FAIL",
            "A newer commit in the same integration group superseded this commit",
            {"superseded_by_commit_sha": pending_group_latest.get("commit_sha"), "integration_group": commit_row.get("integration_group")},
        ))
        return {
            "decision": DECISION_SUPERSEDED,
            "reason": f"superseded by {pending_group_latest.get('commit_sha')}",
            "steps": decision_steps,
            "context": context,
            "superseded_by_task_id": pending_group_latest.get("task_id"),
            "superseded_by_commit_sha": pending_group_latest.get("commit_sha"),
        }
    decision_steps.append(_decision_step(
        "check_conflict_risk",
        "PASS",
        "No superseding commit detected in the integration group",
        {"integration_group": commit_row.get("integration_group")},
    ))

    if not commit_row.get("commit_sha"):
        decision_steps.append(_decision_step(
            "check_merge_readiness",
            "FAIL",
            "Commit SHA missing",
            {},
        ))
        return {"decision": DECISION_INVALID, "reason": "missing commit sha", "steps": decision_steps, "context": context}

    decision_steps.append(_decision_step(
        "check_merge_readiness",
        "PASS",
        "Commit is ready for merge processing",
        {"commit_sha": commit_row.get("commit_sha"), "high_conflict_paths": high_conflict_paths},
    ))

    return {
        "decision": DECISION_APPROVED,
        "reason": "approved for merge",
        "steps": decision_steps,
        "context": context,
        "high_conflict_paths": high_conflict_paths,
    }


def _detect_base_branch() -> str:
    for candidate in ("master", "main"):
        if common.git_branch_exists(candidate):
            return candidate
    return common.git_current_branch()


def _ensure_merge_branch(merge_branch: str, base_branch: str) -> tuple[bool, str]:
    if common.git_branch_exists(merge_branch):
        return common.git_checkout_branch(merge_branch)
    ok, output = common.git_checkout_branch(base_branch)
    if not ok:
        return False, output
    return common.git_checkout_branch(merge_branch)


def _merge_approved_commits(run_id: str, merge_branch: str, base_branch: str, approved_commits: list[dict], checked_from: str, checked_until: str) -> tuple[list[dict], int, int, int, str]:
    merged_records = []
    merged_count = 0
    deferred_count = 0
    validation_failures = 0
    current_merge_branch = merge_branch

    if not approved_commits:
        return merged_records, merged_count, deferred_count, validation_failures, current_merge_branch

    with common.git_ops_lock():
        ok, output = _ensure_merge_branch(merge_branch, base_branch)
        if not ok:
            raise RuntimeError(f"failed to prepare merge branch {merge_branch}: {output}")
        current_merge_branch = merge_branch

        for commit_row in approved_commits:
            commit_sha = commit_row.get("commit_sha")
            task_id = commit_row.get("task_id")
            steps = commit_row.get("steps") or []
            reason = commit_row.get("reason") or "approved for merge"
            try:
                result = subprocess.run(
                    ["git", "-C", common.ROOT, "cherry-pick", commit_sha],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode != 0:
                    output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip().lower()
                    subprocess.run(["git", "-C", common.ROOT, "cherry-pick", "--abort"], capture_output=True, text=True, timeout=60)
                    if "conflict" in output or "merge conflict" in output:
                        decision = DECISION_CONFLICT
                        reason = f"cherry-pick conflict on {commit_sha}"
                        deferred_count += 1
                    else:
                        decision = DECISION_MERGE_FAIL
                        reason = f"merge validation failed for {commit_sha}: {output[:300]}"
                        validation_failures += 1
                    _record_review(
                        commit_row,
                        run_id,
                        decision,
                        reason,
                        checked_from,
                        checked_until,
                        steps + [_decision_step("merge_validation", "FAIL", reason, {"output": output[:1200]})],
                    )
                    merged_records.append({
                        "task_id": task_id,
                        "commit_sha": commit_sha,
                        "decision": decision,
                        "reason": reason,
                        "steps": steps,
                    })
                    continue

                merge_commit_sha = common.git_head_sha()
                decision = DECISION_MERGED
                _record_review(
                    commit_row,
                    run_id,
                    decision,
                    "merged to CTO branch",
                    checked_from,
                    checked_until,
                    steps + [_decision_step("merge_validation", "PASS", "Cherry-pick applied cleanly", {"merge_commit_sha": merge_commit_sha})],
                )
                db.upsert_task_git_commit(
                    task_id=task_id,
                    slot_key=commit_row.get("slot_key"),
                    task_title=commit_row.get("task_title"),
                    source_branch=commit_row.get("source_branch"),
                    commit_sha=commit_sha,
                    commit_message=commit_row.get("commit_message"),
                    integration_group=commit_row.get("integration_group"),
                    review_priority=commit_row.get("review_priority"),
                    safe_to_autocommit=commit_row.get("safe_to_autocommit"),
                    status=DECISION_MERGED,
                    reviewer_role="cto-reviewer",
                    reviewed_at=_now_iso(),
                    merge_branch=current_merge_branch,
                    merge_commit_sha=merge_commit_sha,
                    reject_reason=None,
                    superseded_by_task_id=commit_row.get("superseded_by_task_id"),
                    superseded_by_commit_sha=commit_row.get("superseded_by_commit_sha"),
                    changed_files=_json_loads(commit_row.get("changed_files_json"), []),
                    depends_on_tasks=_json_loads(commit_row.get("depends_on_tasks_json"), []),
                    depends_on_commits=_json_loads(commit_row.get("depends_on_commits_json"), []),
                    high_conflict_paths=_json_loads(commit_row.get("high_conflict_paths_json"), []),
                    task_status=commit_row.get("task_status"),
                    gate_verdict=commit_row.get("gate_verdict"),
                    gate_reason=commit_row.get("gate_reason"),
                )
                merged_count += 1
                merged_records.append({
                    "task_id": task_id,
                    "commit_sha": commit_sha,
                    "decision": decision,
                    "reason": "merged to CTO branch",
                    "merge_commit_sha": merge_commit_sha,
                    "steps": steps,
                })
            except Exception as exc:
                subprocess.run(["git", "-C", common.ROOT, "cherry-pick", "--abort"], capture_output=True, text=True, timeout=60)
                decision = DECISION_MERGE_FAIL
                reason = f"merge validation failed for {commit_sha}: {exc}"
                validation_failures += 1
                _record_review(
                    commit_row,
                    run_id,
                    decision,
                    reason,
                    checked_from,
                    checked_until,
                    steps + [_decision_step("merge_validation", "FAIL", reason, {"error": str(exc)})],
                )
                merged_records.append({
                    "task_id": task_id,
                    "commit_sha": commit_sha,
                    "decision": decision,
                    "reason": reason,
                    "steps": steps,
                })

        # Merge back to master only if there was at least one successful merge.
        if merged_count > 0:
            ok, output = common.git_checkout_branch(base_branch)
            if not ok:
                raise RuntimeError(f"failed to checkout base branch {base_branch}: {output}")
            merge_result = subprocess.run(
                ["git", "-C", common.ROOT, "merge", "--ff-only", current_merge_branch],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if merge_result.returncode != 0:
                raise RuntimeError(((merge_result.stdout or "") + "\n" + (merge_result.stderr or "")).strip())

    return merged_records, merged_count, deferred_count, validation_failures, current_merge_branch


def _write_reports(
    run_record: dict,
    decisions: list[dict],
    report_md_path: str,
    report_json_path: str,
):
    # ── Enrich each decision with scoring / category / action ─────────────────
    enriched: list[dict] = []
    for item in decisions:
        decision = item.get("decision") or ""
        steps = item.get("steps") or []
        extra_conflict = item.get("high_conflict_paths") or []
        extracted = _extract_from_steps(steps)
        scoring = _score_decision(decision, steps, extra_conflict)
        category = _classify_files(extracted["actual_files"] or extra_conflict)
        action = _build_action(item.get("task_id"), item.get("commit_sha") or "", decision, item.get("reason") or "")
        enriched.append({
            "task_id": item.get("task_id"),
            "commit_sha": item.get("commit_sha"),
            "decision": decision,
            "reason": item.get("reason"),
            "category": category,
            "scoring": scoring,
            "action": action,
            "steps": steps,
        })

    # Sort by severity desc, impact_score desc
    enriched.sort(key=lambda d: (
        -SEVERITY_RANK.get((d.get("scoring") or {}).get("severity", "LOW"), 1),
        -(d.get("scoring") or {}).get("impact_score", 0),
    ))

    health_score = _compute_health_score(run_record, enriched)
    verdict = _cto_verdict(health_score, enriched)
    exec_summary = _build_executive_summary(run_record, enriched, health_score, verdict)

    # Roadmap: tasks needing follow-up
    roadmap = [
        {
            "task_id": d.get("task_id"),
            "title": (d.get("action") or {}).get("action"),
            "priority": (d.get("action") or {}).get("priority"),
            "category": d.get("category"),
            "urgency": (d.get("scoring") or {}).get("urgency"),
        }
        for d in enriched
        if (d.get("action") or {}).get("create_task")
    ]

    report_json = {
        **run_record,
        "decisions": enriched,
        "intelligence": {
            "schema_version": "2.0",
            "executive_summary": exec_summary,
            "health_score": health_score,
            "verdict": verdict,
            "roadmap": roadmap,
        },
    }

    # ── Markdown ───────────────────────────────────────────────────────────────
    _V = {"GO": "✅", "CAUTION": "⚠️", "STOP": "🛑"}
    _S = {"CRITICAL": "🔴 CRITICAL", "HIGH": "🟠 HIGH", "MEDIUM": "🟡 MEDIUM", "LOW": "🟢 LOW"}
    _P = {"IMMEDIATE": "🚨", "HIGH": "🟠", "SHORT": "⏰", "MEDIUM": "—", "LOW": "🟢"}
    verdict_icon = _V.get(verdict, "—")
    health_bar = "█" * (health_score // 10) + "░" * (10 - health_score // 10)

    lines: list[str] = [
        f"# CTO Review Report — {run_record['run_id']}",
        "",
        f"> {verdict_icon} **CTO Verdict: {verdict}** | System Health: **{health_score}/100**",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Health Score | **{health_score}/100** |",
        f"| CTO Verdict | **{verdict_icon} {verdict}** |",
        f"| Candidates | {exec_summary['candidate_count']} |",
        f"| Merged | {exec_summary['merged_count']} |",
        f"| Approved (pending merge) | {exec_summary['approved_count']} |",
        f"| Rejected | {exec_summary['rejected_count']} |",
        f"| Deferred | {exec_summary['deferred_count']} |",
        f"| Superseded | {exec_summary['superseded_count']} |",
        f"| Duplicate | {exec_summary['duplicate_count']} |",
        "",
        "---",
        "",
        "## 2. System Health Score",
        "",
        f"```",
        f"Health: {health_score:>3}/100  [{health_bar}]",
        f"```",
        "",
        "---",
        "",
        "## 3. Top Risks",
        "",
    ]

    if exec_summary["top_risks"]:
        for i, risk in enumerate(exec_summary["top_risks"], 1):
            sev = _S.get(risk.get("severity", "LOW"), risk.get("severity", "—"))
            lines += [
                f"### Risk #{i} — {sev}",
                f"- **Task**: #{risk.get('task_id')} | Commit: `{risk.get('commit_sha') or '—'}`",
                f"- **Impact Score**: {risk.get('impact_score', 0)}/100",
                f"- **Urgency**: {risk.get('urgency', '—')}",
                f"- **Decision**: {risk.get('decision', '—')}",
                f"- **Description**: {risk.get('description', '—')}",
                "",
            ]
    else:
        lines += ["_無高風險項目_", ""]

    lines += ["---", "", "## 4. Top Actions", ""]

    if exec_summary["top_actions"]:
        for i, act in enumerate(exec_summary["top_actions"], 1):
            icon = _P.get(act.get("priority", "MEDIUM"), "—")
            lines += [
                f"### Action #{i} — {icon} [{act.get('priority')}] {act.get('action', '—')}",
                f"- **Task**: #{act.get('task_id')}",
                f"- **Expected Benefit**: {act.get('expected_benefit', '—')}",
                f"- **建立任務**: {'是 ⬡' if act.get('create_task') else '否'}",
                "",
            ]
    else:
        lines += ["_無高優先行動項目_", ""]

    lines += ["---", "", "## 5. Detailed Findings", ""]

    for item in enriched:
        scoring = item.get("scoring") or {}
        action = item.get("action") or {}
        sev = _S.get(scoring.get("severity", "LOW"), scoring.get("severity", "—"))
        icon = _P.get(action.get("priority", "MEDIUM"), "—")
        lines += [
            f"### Task #{item.get('task_id')} — {sev} | {item.get('decision', '—')}",
            f"- **Commit**: `{str(item.get('commit_sha') or '—')[:12]}`",
            f"- **Category**: `{item.get('category', '—')}`",
            f"- **Severity**: {scoring.get('severity', '—')} | Impact: {scoring.get('impact_score', 0)}/100 | Confidence: {scoring.get('confidence', 0):.0%}",
            f"- **Urgency**: {scoring.get('urgency', '—')}",
            f"- **Reason**: {item.get('reason') or '—'}",
            f"- **Action** {icon}: {action.get('action', '—')} `[{action.get('priority', '—')}]`",
            f"- **Expected Benefit**: {action.get('expected_benefit', '—')}",
            f"- **Risk Note**: {action.get('risk_note', '—')}",
            f"- **建立任務**: {'是 ⬡' if action.get('create_task') else '否'}",
        ]
        hcp = scoring.get("high_conflict_paths") or []
        if hcp:
            lines.append(f"- **High-conflict Paths**: {', '.join(str(p) for p in hcp[:5])}")
        lines.append("- **Decision Steps**:")
        for step in item.get("steps") or []:
            lines.append(f"  - `{step.get('step')}` | {step.get('status')} | {step.get('summary')}")
        lines.append("")

    lines += ["---", "", "## 6. Recommended Roadmap", ""]

    if roadmap:
        for i, item in enumerate(roadmap, 1):
            icon = _P.get(item.get("priority", "MEDIUM"), "—")
            lines.append(
                f"{i}. {icon} **[{item.get('priority')}]** {item.get('title', '—')} "
                f"(Task #{item.get('task_id')}, Category: `{item.get('category', '—')}`, Urgency: {item.get('urgency', '—')})"
            )
    else:
        lines.append("_無需要建立任務的項目_")

    lines += [
        "",
        "---",
        "",
        "## 7. CTO Final Verdict",
        "",
        f"> {verdict_icon} **{verdict}**",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| Health Score | {health_score}/100 |",
        f"| Run ID | {run_record['run_id']} |",
        f"| Started | {run_record['started_at']} |",
        f"| Completed | {run_record.get('completed_at') or '—'} |",
        f"| Duration | {run_record.get('duration_seconds') or '—'}s |",
        f"| Frequency Mode | {run_record['frequency_mode']} |",
        f"| Merge Branch | {run_record.get('merge_branch') or '—'} |",
        f"| Summary | {run_record.get('summary') or '—'} |",
    ]

    with open(report_md_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines).strip() + "\n")
    with open(report_json_path, "w", encoding="utf-8") as handle:
        json.dump(report_json, handle, ensure_ascii=False, indent=2)


def run(force: bool = False):
    common.ensure_dirs()
    db.init_db()
    started_at = datetime.now(timezone.utc)
    frequency_mode = db.get_cto_review_frequency_mode()
    run_id = _build_run_id(started_at)
    checked_until = _now_iso()
    request_id = os.environ.get("ORCHESTRATOR_REQUEST_ID") or None
    latest_run = db.get_latest_cto_review_run()
    checked_from = latest_run.get("completed_at") if latest_run and latest_run.get("completed_at") else None
    if not checked_from:
        if frequency_mode == "twice_daily":
            checked_from = (started_at - timedelta(hours=12)).isoformat()
        else:
            checked_from = (started_at - timedelta(days=1)).isoformat()

    report_md_path, report_json_path = _build_report_paths(run_id, started_at)
    run_branch = common.git_branch_name_for_cto_merge(started_at.astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d"), frequency_mode=frequency_mode, started_at=started_at.isoformat())
    base_branch = _detect_base_branch()

    run_record = {
        "run_id": run_id,
        "frequency_mode": frequency_mode,
        "started_at": started_at.isoformat(),
        "completed_at": None,
        "duration_seconds": None,
        "checked_from": checked_from,
        "checked_until": checked_until,
        "candidate_count": 0,
        "approved_count": 0,
        "merged_count": 0,
        "rejected_count": 0,
        "deferred_count": 0,
        "superseded_count": 0,
        "duplicate_count": 0,
        "merge_branch": None,
        "report_md_path": report_md_path,
        "report_json_path": report_json_path,
        "summary": "",
        "created_at": started_at.isoformat(),
        "updated_at": started_at.isoformat(),
    }
    db.create_cto_review_run(**run_record)

    if not db.is_cto_scheduler_enabled() and not force:
        run_record["summary"] = "CTO Scheduler disabled; CTO review skipped"
        run_record["completed_at"] = _now_iso()
        run_record["duration_seconds"] = int((datetime.now(timezone.utc) - started_at).total_seconds())
        db.update_cto_review_run(run_id, completed_at=run_record["completed_at"], duration_seconds=run_record["duration_seconds"], summary=run_record["summary"], merge_branch=None)
        _write_reports(run_record, [], report_md_path, report_json_path)
        db.update_cto_review_run(run_id, report_md_path=report_md_path, report_json_path=report_json_path)
        db.log_tick("cto-review", "CTO_REVIEW_SKIP_DISABLED", message="CTO Scheduler disabled", request_id=request_id)
        logger.info("CTO review skipped because CTO scheduler is disabled")
        return run_record

    if _should_skip_for_frequency(frequency_mode) and not force:
        run_record["summary"] = "Frequency gate: too recent to run"
        run_record["completed_at"] = _now_iso()
        run_record["duration_seconds"] = int((datetime.now(timezone.utc) - started_at).total_seconds())
        db.update_cto_review_run(run_id, completed_at=run_record["completed_at"], duration_seconds=run_record["duration_seconds"], summary=run_record["summary"], merge_branch=None)
        _write_reports(run_record, [], report_md_path, report_json_path)
        db.update_cto_review_run(run_id, report_md_path=report_md_path, report_json_path=report_json_path)
        db.log_tick("cto-review", "CTO_REVIEW_SKIP_FREQUENCY", message=f"Frequency gate: {frequency_mode}", request_id=request_id)
        logger.info("CTO review skipped due to frequency gate")
        return run_record

    pending = db.list_task_git_commits(status=DECISION_PENDING, limit=1000, offset=0)
    run_record["candidate_count"] = len(pending)

    decisions: list[dict] = []
    if not pending:
        run_record["summary"] = "No pending review candidates"
        run_record["completed_at"] = _now_iso()
        run_record["duration_seconds"] = int((datetime.now(timezone.utc) - started_at).total_seconds())
        db.update_cto_review_run(run_id, candidate_count=0, completed_at=run_record["completed_at"], duration_seconds=run_record["duration_seconds"], summary=run_record["summary"], merge_branch=None)
        _write_reports(run_record, [], report_md_path, report_json_path)
        db.update_cto_review_run(run_id, report_md_path=report_md_path, report_json_path=report_json_path)
        db.log_tick("cto-review", "CTO_REVIEW_NO_CANDIDATES", message="No pending review candidates", request_id=request_id)
        logger.info("No pending CTO review candidates")
        return run_record

    latest_by_group: dict[str, dict] = {}
    for row in sorted(pending, key=lambda item: (_parse_iso(item.get("created_at")) or started_at, item.get("id") or 0)):
        group = str(row.get("integration_group") or "").strip() or f"task-{row.get('task_id')}"
        latest = latest_by_group.get(group)
        if latest is None:
            latest_by_group[group] = row
            continue
        latest_ts = _parse_iso(latest.get("created_at")) or started_at
        row_ts = _parse_iso(row.get("created_at")) or started_at
        if row_ts >= latest_ts:
            latest_by_group[group] = row

    approved_candidates: list[dict] = []
    for row in pending:
        group = str(row.get("integration_group") or "").strip() or f"task-{row.get('task_id')}"
        newest_in_group = latest_by_group.get(group)
        if newest_in_group and newest_in_group.get("commit_sha") != row.get("commit_sha"):
            decision = DECISION_SUPERSEDED
            reason = f"superseded by {newest_in_group.get('commit_sha')}"
            steps = [
                _decision_step("load_task_context", "PASS", "Loaded task context", {"task_id": row.get("task_id"), "commit_sha": row.get("commit_sha")}),
                _decision_step("check_conflict_risk", "FAIL", "A newer commit in the same integration group exists", {"superseded_by_commit_sha": newest_in_group.get("commit_sha"), "integration_group": group}),
                _decision_step("final_decision", "PASS", "Marked as superseded", {}),
            ]
            _record_review(row, run_id, decision, reason, checked_from, checked_until, steps)
            decisions.append({
                "task_id": row.get("task_id"),
                "commit_sha": row.get("commit_sha"),
                "decision": decision,
                "reason": reason,
                "steps": steps,
                "status": decision,
            })
            run_record["superseded_count"] += 1
            continue

        evaluated = _evaluate_commit(row, newest_in_group)
        decision = evaluated["decision"]
        reason = evaluated["reason"]
        steps = evaluated["steps"]
        commit_record = dict(row)
        commit_record["steps"] = steps
        commit_record["reason"] = reason

        if decision == DECISION_APPROVED:
            run_record["approved_count"] += 1
            approved_candidates.append(commit_record)
            _record_review(row, run_id, decision, reason, checked_from, checked_until, steps)
            decisions.append({
                "task_id": row.get("task_id"),
                "commit_sha": row.get("commit_sha"),
                "decision": decision,
                "reason": reason,
                "steps": steps,
                "status": decision,
                "high_conflict_paths": evaluated.get("high_conflict_paths", []),
            })
            # Preserve pending state until merge succeeds.
            db.upsert_task_git_commit(
                task_id=row.get("task_id"),
                slot_key=row.get("slot_key"),
                task_title=row.get("task_title"),
                source_branch=row.get("source_branch"),
                commit_sha=row.get("commit_sha"),
                commit_message=row.get("commit_message"),
                integration_group=row.get("integration_group"),
                review_priority=row.get("review_priority"),
                safe_to_autocommit=row.get("safe_to_autocommit"),
                status=DECISION_APPROVED,
                reviewer_role="cto-reviewer",
                reviewed_at=_now_iso(),
                merge_branch=run_branch,
                merge_commit_sha=None,
                reject_reason=reason,
                superseded_by_task_id=row.get("superseded_by_task_id"),
                superseded_by_commit_sha=row.get("superseded_by_commit_sha"),
                changed_files=_json_loads(row.get("changed_files_json"), []),
                depends_on_tasks=_json_loads(row.get("depends_on_tasks_json"), []),
                depends_on_commits=_json_loads(row.get("depends_on_commits_json"), []),
                high_conflict_paths=_json_loads(row.get("high_conflict_paths_json"), []),
                task_status=row.get("task_status"),
                gate_verdict=row.get("gate_verdict"),
                gate_reason=row.get("gate_reason"),
            )
            continue

        if decision in (DECISION_REPLAN, DECISION_CLOSED, DECISION_DEPENDENCY, DECISION_INVALID, DECISION_DUPLICATE):
            if decision.startswith("REJECTED"):
                run_record["rejected_count"] += 1
            elif decision == DECISION_DUPLICATE:
                run_record["duplicate_count"] += 1
            elif decision == DECISION_CLOSED:
                run_record["rejected_count"] += 1
            _record_review(row, run_id, decision, reason, checked_from, checked_until, steps)
            decisions.append({
                "task_id": row.get("task_id"),
                "commit_sha": row.get("commit_sha"),
                "decision": decision,
                "reason": reason,
                "steps": steps,
                "status": decision,
            })
            db.upsert_task_git_commit(
                task_id=row.get("task_id"),
                slot_key=row.get("slot_key"),
                task_title=row.get("task_title"),
                source_branch=row.get("source_branch"),
                commit_sha=row.get("commit_sha"),
                commit_message=row.get("commit_message"),
                integration_group=row.get("integration_group"),
                review_priority=row.get("review_priority"),
                safe_to_autocommit=row.get("safe_to_autocommit"),
                status=decision,
                reviewer_role="cto-reviewer",
                reviewed_at=_now_iso(),
                merge_branch=row.get("merge_branch"),
                merge_commit_sha=row.get("merge_commit_sha"),
                reject_reason=reason,
                superseded_by_task_id=row.get("superseded_by_task_id"),
                superseded_by_commit_sha=row.get("superseded_by_commit_sha"),
                changed_files=_json_loads(row.get("changed_files_json"), []),
                depends_on_tasks=_json_loads(row.get("depends_on_tasks_json"), []),
                depends_on_commits=_json_loads(row.get("depends_on_commits_json"), []),
                high_conflict_paths=_json_loads(row.get("high_conflict_paths_json"), []),
                task_status=row.get("task_status"),
                gate_verdict=row.get("gate_verdict"),
                gate_reason=row.get("gate_reason"),
            )
            continue

        if decision in (DECISION_CONFLICT, DECISION_MERGE_FAIL):
            run_record["deferred_count"] += 1
        _record_review(row, run_id, decision, reason, checked_from, checked_until, steps)
        decisions.append({
            "task_id": row.get("task_id"),
            "commit_sha": row.get("commit_sha"),
            "decision": decision,
            "reason": reason,
            "steps": steps,
            "status": decision,
        })
        db.upsert_task_git_commit(
            task_id=row.get("task_id"),
            slot_key=row.get("slot_key"),
            task_title=row.get("task_title"),
            source_branch=row.get("source_branch"),
            commit_sha=row.get("commit_sha"),
            commit_message=row.get("commit_message"),
            integration_group=row.get("integration_group"),
            review_priority=row.get("review_priority"),
            safe_to_autocommit=row.get("safe_to_autocommit"),
            status=decision,
            reviewer_role="cto-reviewer",
            reviewed_at=_now_iso(),
            merge_branch=row.get("merge_branch"),
            merge_commit_sha=row.get("merge_commit_sha"),
            reject_reason=reason,
            superseded_by_task_id=row.get("superseded_by_task_id"),
            superseded_by_commit_sha=row.get("superseded_by_commit_sha"),
            changed_files=_json_loads(row.get("changed_files_json"), []),
            depends_on_tasks=_json_loads(row.get("depends_on_tasks_json"), []),
            depends_on_commits=_json_loads(row.get("depends_on_commits_json"), []),
            high_conflict_paths=_json_loads(row.get("high_conflict_paths_json"), []),
            task_status=row.get("task_status"),
            gate_verdict=row.get("gate_verdict"),
            gate_reason=row.get("gate_reason"),
        )

    merged_records = []
    merge_branch = None
    if approved_candidates:
        merge_branch = common.git_branch_name_for_cto_merge(
            started_at.astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d"),
            frequency_mode=frequency_mode,
            started_at=started_at.isoformat(),
        )
        try:
            merged_records, merged_count, deferred_count, validation_failures, merge_branch = _merge_approved_commits(
                run_id,
                merge_branch,
                base_branch,
                approved_candidates,
                checked_from,
                checked_until,
            )
            run_record["merged_count"] = merged_count
            run_record["deferred_count"] += deferred_count + validation_failures
            run_record["merge_branch"] = merge_branch if merged_count > 0 else None
            for item in merged_records:
                decisions.append(item)
        except Exception as exc:
            logger.exception("CTO merge step failed: %s", exc)
            run_record["summary"] = f"Merge validation failed: {exc}"
            run_record["completed_at"] = _now_iso()
            run_record["duration_seconds"] = int((datetime.now(timezone.utc) - started_at).total_seconds())
            db.update_cto_review_run(
                run_id,
                completed_at=run_record["completed_at"],
                duration_seconds=run_record["duration_seconds"],
                summary=run_record["summary"],
                merge_branch=run_record.get("merge_branch"),
                candidate_count=run_record["candidate_count"],
                approved_count=run_record["approved_count"],
                merged_count=run_record["merged_count"],
                rejected_count=run_record["rejected_count"],
                deferred_count=run_record["deferred_count"],
                superseded_count=run_record["superseded_count"],
                duplicate_count=run_record["duplicate_count"],
            )
            _write_reports(run_record, decisions, report_md_path, report_json_path)
            db.update_cto_review_run(run_id, report_md_path=report_md_path, report_json_path=report_json_path)
            db.log_tick("cto-review", "CTO_REVIEW_ERROR", message=f"Merge failed: {exc}", request_id=request_id)
            raise

    run_record["completed_at"] = _now_iso()
    run_record["duration_seconds"] = int((datetime.now(timezone.utc) - started_at).total_seconds())
    if not run_record.get("summary"):
        run_record["summary"] = (
            f"Processed {run_record['candidate_count']} candidate(s): "
            f"{run_record['approved_count']} approved, {run_record['merged_count']} merged, "
            f"{run_record['rejected_count']} rejected, {run_record['deferred_count']} deferred, "
            f"{run_record['superseded_count']} superseded, {run_record['duplicate_count']} duplicate"
        )
    db.update_cto_review_run(
        run_id,
        completed_at=run_record["completed_at"],
        duration_seconds=run_record["duration_seconds"],
        checked_from=run_record["checked_from"],
        checked_until=run_record["checked_until"],
        candidate_count=run_record["candidate_count"],
        approved_count=run_record["approved_count"],
        merged_count=run_record["merged_count"],
        rejected_count=run_record["rejected_count"],
        deferred_count=run_record["deferred_count"],
        superseded_count=run_record["superseded_count"],
        duplicate_count=run_record["duplicate_count"],
        merge_branch=run_record.get("merge_branch"),
        summary=run_record["summary"],
    )
    _write_reports(run_record, decisions, report_md_path, report_json_path)
    db.update_cto_review_run(run_id, report_md_path=report_md_path, report_json_path=report_json_path)
    db.log_tick("cto-review", "CTO_REVIEW_COMPLETED", message=run_record["summary"], request_id=request_id)
    logger.info("CTO review %s completed: %s", run_id, run_record["summary"])
    return run_record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(force=args.dry_run)
