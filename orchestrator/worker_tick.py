#!/usr/bin/env python3
"""
Codex Worker tick — triggered every 10 min by launchd.
Heartbeats active tasks, finalizes completed ones, claims and starts new QUEUED tasks.
"""

import sys
import os
import time
import logging
import subprocess
import json
import re
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator import db, common, execution_policy, health, planner_guard, failure_taxonomy, repair_task_generator, outcome_extractor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [worker] %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

RUNNER = "worker"
FINALIZED = False  # track if we finalized this tick (to decide whether to try claiming)
COPILOT_STALE_LOG_TIMEOUT_SECONDS = 600
DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS = 1800


def _build_strategy_table_from_rows(rows: list) -> str:
    header = [
        "strategy_name",
        "family",
        "edge_150",
        "edge_500",
        "edge_1000",
        "mc_status",
        "vs_incumbent",
        "incumbent_name",
        "validation_tier",
        "promotion_blocker",
        "next_action",
    ]
    table_lines = [
        "## Strategy Output Table",
        "",
        "| " + " | ".join(header) + " |",
        "|" + "|".join(["---"] * len(header)) + "|",
    ]
    for row in rows:
        if not isinstance(row, dict):
            continue
        values = []
        for key in header:
            value = row.get(key, "")
            if key == "family" and value in (None, ""):
                value = row.get("game", "")
            if value is None:
                value = ""
            elif isinstance(value, (int, float)):
                value = f"{value:+.6f}" if "edge" in key or key == "vs_incumbent" else str(value)
            else:
                value = str(value)
            values.append(value.replace("\n", " ").strip())
        table_lines.append("| " + " | ".join(values) + " |")
    return "\n".join(table_lines) if len(table_lines) > 4 else ""


def _load_strategy_table_fallback_text(task: Optional[dict] = None) -> str:
    """Return a synthetic Strategy Output Table section from sidecar artifacts.

    Some worker runs write `outputs/strategy_output_table.md` or
    `outputs/strategy_output_table.json` but fail to echo the final table back to
    stdout. To avoid discarding otherwise-usable work, the deep-research gate can
    fall back to these artifacts.
    """
    outputs_dir = os.path.join(common.ROOT, "outputs")
    candidate_paths: list[str] = []
    if isinstance(task, dict):
        changed_files_raw = task.get("changed_files_json")
        try:
            changed_files = json.loads(changed_files_raw) if isinstance(changed_files_raw, str) else changed_files_raw
        except json.JSONDecodeError:
            changed_files = None
        if isinstance(changed_files, list):
            for rel_path in changed_files:
                if not isinstance(rel_path, str) or not rel_path:
                    continue
                candidate_paths.append(
                    rel_path if os.path.isabs(rel_path) else os.path.join(common.ROOT, rel_path)
                )

    candidate_paths.extend([
        os.path.join(outputs_dir, "strategy_output_table.md"),
        os.path.join(outputs_dir, "strategy_table.md"),
        os.path.join(outputs_dir, "strategy_output_table.json"),
        os.path.join(outputs_dir, "strategy_table.json"),
    ])

    seen_paths: set[str] = set()
    for path in candidate_paths:
        if not path or path in seen_paths or not os.path.exists(path):
            continue
        seen_paths.add(path)
        if path.lower().endswith(".md"):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                    body = handle.read().strip()
            except OSError:
                continue
            if not body or "|" not in body:
                continue
            if re.search(r"strategy\s+output\s+table", body, re.IGNORECASE):
                return body
            if re.search(r"^\|\s*strategy_name\s*\|", body, re.IGNORECASE | re.MULTILINE):
                return f"## Strategy Output Table\n\n{body}"

    for path in candidate_paths:
        if not path or path in seen_paths or not os.path.exists(path):
            continue
        seen_paths.add(path)
        if not path.lower().endswith(".json"):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue

        if isinstance(payload, list) and payload:
            table_text = _build_strategy_table_from_rows(payload)
            if table_text:
                return table_text
        if isinstance(payload, dict):
            rows = payload.get("strategies")
            if isinstance(rows, list) and rows:
                table_text = _build_strategy_table_from_rows(rows)
                if table_text:
                    return table_text

    return ""


def _worker_runtime_error_markers_to_check() -> list[str]:
    """Return list of markers to check for in worker output."""
    return [
        # Runtime/execution errors — use specific Python exception names to avoid
        # false positives from tool CLI messages that contain "error:" as inline text
        # (e.g., SQLite "Error: 4 values for 3 columns" from a Codex tool call).
        # "traceback" already catches Python exception stack headers.
        "traceback",
        "syntaxerror:",
        "nameerror:",
        "typeerror:",
        "importerror:",
        "runtimeerror:",
        "attributeerror:",
        "modulenotfounderror:",
        "command not found",
        "panicked",
        "failed to connect",
        "stream disconnected before completion",
        "could not create otel exporter",
        
        # Quota/rate-limit errors (critical for governance)
        "you have no quota",
        "no quota",
        "you've hit your rate limit",
        "you've reached your weekly rate limit",
        "reached your weekly rate limit",
        "weekly rate limit",
        "rate limit",
        "limit to reset",
        "please wait for your limit to reset",
        "switch to auto model to continue",
        "github.com/en/copilot/concepts/rate-limits",
        "docs.github.com/en/copilot/concepts/rate-limits",
        "premium request limit",
        "premium requests exhausted",
        "out of premium",
        
        # Environment/permission errors
        "third-party mcp servers are disabled",
        "auth failed",
        "not logged in",
        "permission denied",
        "unable to complete this task due to environment execution restrictions",
        
        # Additional environment blocking messages — must use HTTP context prefixes to
        # avoid matching bare numbers in normal log output (e.g., "403 lines..." from
        # Codex tool truncation notices).
        "http 403",
        "http/1.1 403",
        "status: 403",
        "status code 403",
        "403 forbidden",
        "http 429",
        "http/1.1 429",
        "status: 429",
        "status code 429",
        "429 too many",
    ]


def _check_worker_runtime_errors(output_lower: str) -> list[str]:
    """Check output against error markers and return matched markers."""
    markers_to_check = _worker_runtime_error_markers_to_check()
    found_markers = []
    for marker in markers_to_check:
        if marker in output_lower:
            found_markers.append(marker)
    return found_markers


def _as_list(value):
    if isinstance(value, list):
        return value
    if value:
        return [value]
    return []


def _load_task_commit_context(task: dict, meta: dict, task_result: dict, changed_files: list[str]) -> dict:
    contract = {}
    contract_path = meta.get("task_contract_path") or common.contract_path(task["slot_key"], task.get("slug") or "task", task["date_folder"])
    if os.path.exists(contract_path):
        try:
            with open(contract_path, "r", encoding="utf-8") as handle:
                contract = json.load(handle)
        except Exception:
            contract = {}

    integration_group = (
        meta.get("integration_group")
        or contract.get("integration_group")
        or contract.get("group")
        or task.get("slug")
        or task.get("title")
        or ""
    )
    depends_on_tasks = (
        meta.get("depends_on_tasks")
        or contract.get("depends_on_tasks")
        or contract.get("depends_on_task_ids")
        or []
    )
    depends_on_commits = (
        meta.get("depends_on_commits")
        or contract.get("depends_on_commits")
        or []
    )
    committable_paths = common.filter_committable_paths(changed_files)
    high_conflict_paths = [path for path in committable_paths if common.is_high_conflict_path(path)]
    review_priority = "high" if high_conflict_paths else "normal"
    safe_to_autocommit = bool(
        task.get("status") == "COMPLETED"
        and task_result.get("gate_verdict") == "PASS"
        and committable_paths
    )
    return {
        "contract": contract,
        "integration_group": str(integration_group or "").strip(),
        "depends_on_tasks": _as_list(depends_on_tasks),
        "depends_on_commits": _as_list(depends_on_commits),
        "committable_paths": committable_paths,
        "high_conflict_paths": high_conflict_paths,
        "review_priority": review_priority,
        "safe_to_autocommit": safe_to_autocommit,
    }


def _record_git_commit_state(task: dict, task_result: dict, changed_files: list[str], commit_info: dict):
    db.upsert_task_git_commit(
        task_id=task["id"],
        slot_key=task["slot_key"],
        task_title=task.get("title"),
        source_branch=commit_info.get("source_branch"),
        commit_sha=commit_info.get("commit_sha"),
        commit_message=commit_info.get("commit_message"),
        integration_group=commit_info.get("integration_group"),
        review_priority=commit_info.get("review_priority", "normal"),
        safe_to_autocommit=commit_info.get("safe_to_autocommit", False),
        status=commit_info.get("status", "SKIPPED_GIT_COMMIT"),
        reviewer_role=commit_info.get("reviewer_role"),
        reviewed_at=commit_info.get("reviewed_at"),
        merge_branch=commit_info.get("merge_branch"),
        merge_commit_sha=commit_info.get("merge_commit_sha"),
        reject_reason=commit_info.get("reject_reason"),
        superseded_by_task_id=commit_info.get("superseded_by_task_id"),
        superseded_by_commit_sha=commit_info.get("superseded_by_commit_sha"),
        changed_files=changed_files,
        depends_on_tasks=commit_info.get("depends_on_tasks"),
        depends_on_commits=commit_info.get("depends_on_commits"),
        high_conflict_paths=commit_info.get("high_conflict_paths"),
        task_status=task.get("status"),
        gate_verdict=task_result.get("gate_verdict"),
        gate_reason=task_result.get("gate_reason"),
    )


def _attempt_auto_commit(task: dict, meta: dict, task_result: dict, changed_files: list[str]) -> dict:
    context = _load_task_commit_context(task, meta, task_result, changed_files)
    current_branch = common.git_current_branch()
    commit_paths = context["committable_paths"]
    inbox_branch = common.git_branch_name_for_inbox(task["date_folder"], scope=common.derive_scope_from_paths(commit_paths))

    commit_info = {
        "status": "SKIPPED_GIT_COMMIT",
        "source_branch": current_branch,
        "merge_branch": None,
        "merge_commit_sha": None,
        "commit_sha": None,
        "commit_message": None,
        "reject_reason": "",
        "safe_to_autocommit": context["safe_to_autocommit"],
        "integration_group": context["integration_group"],
        "review_priority": context["review_priority"],
        "depends_on_tasks": context["depends_on_tasks"],
        "depends_on_commits": context["depends_on_commits"],
        "high_conflict_paths": context["high_conflict_paths"],
        "reviewer_role": "worker-auto",
    }

    if task.get("status") != "COMPLETED":
        commit_info["reject_reason"] = f"task status {task.get('status')} is not COMPLETED"
        return commit_info
    if task_result.get("gate_verdict") != "PASS":
        commit_info["reject_reason"] = f"gate verdict {task_result.get('gate_verdict')} is not PASS"
        return commit_info
    if not commit_paths:
        commit_info["reject_reason"] = "no committable files after filtering runtime artifacts"
        return commit_info

    title = str(task.get("title") or "Task").strip()
    subject = f"auto(task-{task['id']}): {title[:80]}"
    body_lines = [
        f"Task-ID: {task['id']}",
        f"Slot-Key: {task['slot_key']}",
        f"Planner-Provider: {meta.get('planner_provider') or meta.get('planner_requested_provider') or meta.get('planner_source') or 'unknown'}",
        f"Worker-Provider: {meta.get('worker_provider') or meta.get('worker_requested_provider') or meta.get('worker_runtime') or 'unknown'}",
        f"Gate-Verdict: {task_result.get('gate_verdict')}",
        f"Review-Priority: {context['review_priority']}",
    ]
    if context["integration_group"]:
        body_lines.append(f"Integration-Group: {context['integration_group']}")
    if context["depends_on_tasks"]:
        body_lines.append(f"Depends-On-Tasks: {json.dumps(context['depends_on_tasks'], ensure_ascii=False)}")
    if context["depends_on_commits"]:
        body_lines.append(f"Depends-On-Commits: {json.dumps(context['depends_on_commits'], ensure_ascii=False)}")
    if context["high_conflict_paths"]:
        body_lines.append(f"High-Conflict-Paths: {json.dumps(context['high_conflict_paths'], ensure_ascii=False)}")
    commit_body = "\n".join(body_lines)

    with common.git_ops_lock():
        if current_branch != inbox_branch:
            ok, output = common.git_checkout_branch(inbox_branch)
            if not ok:
                commit_info["reject_reason"] = f"failed to checkout inbox branch {inbox_branch}: {output}"
                return commit_info

        ok, commit_sha, output = common.git_commit_selected_files(
            commit_paths,
            subject=subject,
            body=commit_body,
        )
        if not ok:
            commit_info["reject_reason"] = output
            return commit_info

    commit_info.update({
        "status": "PENDING_REVIEW",
        "commit_sha": commit_sha,
        "commit_message": f"{subject}\n\n{commit_body}",
        "merge_branch": inbox_branch,
        "reject_reason": "",
        "safe_to_autocommit": True,
        "reviewer_role": "worker-auto",
    })
    return commit_info


def _violates_forbidden_changes(changed_files: list[str], forbidden_rules: list[str]) -> list[str]:
    violations = []
    for path in changed_files:
        for rule in forbidden_rules:
            r = str(rule or "").strip()
            if not r:
                continue
            # Prefix-like rule for strategy state files.
            if r.endswith("_"):
                if path.startswith(r):
                    violations.append(path)
            elif path == r or path.startswith(r.rstrip("/") + "/"):
                violations.append(path)
    return sorted(set(violations))


def _is_environment_blocking_error(error_markers_hit: list[str]) -> bool:
    """Check if error markers indicate environment/quota blocking (not worker code failure)."""
    blocking_markers = (
        "no quota",
        "you have no quota",
        "rate limit",
        "weekly rate limit",
        "reached your weekly rate limit",
        "you've reached your weekly rate limit",
        "you've hit your rate limit",
        "limit to reset",
        "please wait for your limit to reset",
        "switch to auto model to continue",
        "third-party mcp servers are disabled",
        "429",
        "403",
    )
    return any(any(blocker in marker for blocker in blocking_markers) for marker in error_markers_hit)


def _parse_rate_limit_reset_hint(output_text: str) -> tuple[str, Optional[str]]:
    text = str(output_text or "")
    match = re.search(
        r"(?:limit to reset|reset)\s+on\s+(.+?)(?:\s+or\s+switch|\s+learn more|\.|\n|$)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return "", None

    reset_hint = match.group(1).strip(" .")
    parsed_iso = None
    for fmt in (
        "%B %d, %Y at %I:%M %p",
        "%b %d, %Y at %I:%M %p",
    ):
        try:
            parsed = datetime.strptime(reset_hint, fmt).replace(tzinfo=timezone.utc)
            parsed_iso = parsed.isoformat()
            break
        except ValueError:
            continue
    return reset_hint, parsed_iso


def _detect_rate_limit_failure(output_text: str, error_markers_hit: list[str], provider: str = "") -> Optional[dict]:
    lowered = str(output_text or "").lower()
    patterns = [
        "you've hit your rate limit",
        "rate limit",
        "limit to reset",
        "github.com/en/copilot/concepts/rate-limits",
        "docs.github.com/en/copilot/concepts/rate-limits",
        "premium request limit",
        "premium requests exhausted",
        "out of premium",
        "429",
    ]
    matched_patterns = [pattern for pattern in patterns if pattern in lowered]
    if not matched_patterns and not any("rate limit" in marker or "429" in marker for marker in error_markers_hit):
        return None

    reset_hint, blocked_until = _parse_rate_limit_reset_hint(output_text)
    provider_name = "copilot" if str(provider or "").startswith("copilot") else str(provider or "unknown")
    final_message = f"provider = {provider_name}; reason = rate_limit"
    if reset_hint:
        final_message += f"; reset_hint = {reset_hint}"
    return {
        "provider": provider_name,
        "reason": "rate_limit",
        "failure_reason": f"{provider_name}_rate_limit",
        "reset_hint": reset_hint,
        "blocked_until": blocked_until,
        "matched_patterns": matched_patterns or error_markers_hit,
        "final_message": final_message,
    }


# ── Deep Research Strategy Gate ───────────────────────────────────────────────

_STRATEGY_TABLE_HEADER = "## Strategy Output Table"
# Also accept without the markdown ## heading prefix, or with extra trailing text
_STRATEGY_TABLE_HEADER_BARE = "strategy output table"


def _is_deep_research_task(task: dict, contract: dict) -> bool:
    """Return True if this is a Deep Research task that requires strategy output gate."""
    title = str(task.get("title") or "").lower()
    if "deep research" in title or "deep-research" in title:
        return True
    return str(contract.get("task_type") or "").lower() == "deep_research"


def _check_strategy_gate(
    task: dict,
    codex_output: str,
    contract: dict,
) -> tuple[Optional[str], Optional[str]]:
    """
    Validate Deep Research strategy output.
    Returns (gate_verdict, gate_reason) if the gate fails, else (None, None).
    Only runs when _is_deep_research_task() is True.
    """
    if not _is_deep_research_task(task, contract):
        return None, None

    text = codex_output or ""
    text_lower = text.lower()

    # 1. Require the Strategy Output Table section.
    # Accept with or without the markdown "##" heading prefix so that
    # workers that write "Strategy Output Table (...)" instead of
    # "## Strategy Output Table" are not falsely rejected.
    section_marker = _STRATEGY_TABLE_HEADER.lower()
    bare_marker = _STRATEGY_TABLE_HEADER_BARE
    if section_marker not in text_lower and bare_marker not in text_lower:
        fallback_table = _load_strategy_table_fallback_text()
        if fallback_table:
            text = f"{text.rstrip()}\n\n{fallback_table}\n"
            text_lower = text.lower()
    if section_marker not in text_lower and bare_marker not in text_lower:
        return (
            "FAILED_ACCEPTANCE",
            (
                "Deep Research task missing required '## Strategy Output Table' section. "
                "Worker must produce a strategy table with ≥3 strategies including "
                "edge/sharpe/MC columns. Pure analysis/description output is not accepted."
            ),
        )

    # Extract section content starting at the marker (prefer ## heading if present)
    if section_marker in text_lower:
        idx = text_lower.find(section_marker)
    else:
        idx = text_lower.find(bare_marker)
    section = text[idx:]

    # 2. Collect edge values via format-agnostic scan.
    #    Strategy name counting is NOT done here — it is delegated to step 6's robust
    #    table parser so that format changes (new columns, no window column, etc.) never
    #    break the count.  We only need edge values here for step 4 (FAILED_NO_EDGE).
    edge_values: list = []
    for e in re.findall(r'[|\s,]([+-]?\d+\.\d+)[|\s,]', section):
        try:
            edge_values.append(float(e))
        except ValueError:
            pass
    # Also catch "edge = X.XXX" style inline
    for e in re.findall(r'edge\s*[=:]\s*([+-]?\d+\.\d+)', section, re.IGNORECASE):
        try:
            edge_values.append(float(e))
        except ValueError:
            pass

    min_strategies = int(contract.get("strategy_min_count") or 3)

    # 3. (Removed — strategy count is now enforced inside step 6 using the robust parser.
    #     This eliminates format-specific regex fragility.)

    # 4. FAILED_NO_EDGE — all edges are ≤ 0
    if edge_values and all(v <= 0 for v in edge_values):
        max_edge = max(edge_values)
        return (
            "FAILED_NO_EDGE",
            (
                f"All {len(edge_values)} strategy edge value(s) in Strategy Output Table are "
                f"≤ 0 (max={max_edge:+.4f}). Task requires at least one strategy with "
                "positive edge. Mark as FAILED_NO_EDGE in the table and propose alternative "
                "research direction in the next planning cycle."
            ),
        )

    # 5. Require at least one MC reference (seed=42 / n≥1000)
    has_mc = bool(
        re.search(r'seed\s*=\s*42', text, re.IGNORECASE)
        or re.search(r'monte\s*carlo[^,;\n]{0,60}n\s*[=≥>]\s*\d{3,}', text, re.IGNORECASE)
        or re.search(r'\bn\s*[=≥>]\s*1\d{3,}', text)
    )
    if not has_mc:
        return (
            "FAILED_ACCEPTANCE",
            (
                "Deep Research task missing Monte Carlo validation in output. "
                "Require at least one MC run with seed=42, n≥1000."
            ),
        )

    # 6. ── Required-field enforcement ────────────────────────────────────────
    # Only run when the contract explicitly lists required_strategy_fields.
    # Also performs the minimum strategy count check (moved from step 3).
    required_fields = contract.get("required_strategy_fields") if isinstance(contract, dict) else None
    if required_fields:
        verdict, reason = _check_strategy_output_fields(
            section, required_fields, edge_values, min_strategies
        )
        if verdict:
            return verdict, reason
    else:
        # No required_strategy_fields in contract — fall back to a simple row-count check
        # by scanning for pipe-table data rows with a strategy-name-like first cell.
        simple_names = set(
            m.group(1).strip().lower()
            for m in re.finditer(
                r'^\s*\|\s*([A-Za-z][\w_.:\-]{2,})\s*\|', section, re.MULTILINE
            )
            if not re.match(r'^[-=]+$', m.group(1).strip())
            and m.group(1).strip().lower() not in ("strategy_name", "strategy name")
        )
        if len(simple_names) < min_strategies:
            return (
                "FAILED_ACCEPTANCE",
                (
                    f"Deep Research task produced {len(simple_names)} distinct strategy name(s) "
                    f"in '## Strategy Output Table', required \u2265 {min_strategies}. "
                    "Each row must have a unique strategy name, not just analysis text."
                ),
            )

    return None, None


# ── Required-field checker (called from _check_strategy_gate) ─────────────────

_PROMOTION_KEYWORDS = re.compile(
    r'\b(?:promotion_candidate|promoted|promote|升格|晉升|production_ready)\b',
    re.IGNORECASE,
)
_VALID_TIERS = {
    "t0_idea", "t1_mc_pass", "t2_three_window_pass",
    "t3_incumbent_pass", "t4_deployable",
}

# Chinese→English column header aliases.
# Workers trained on Chinese-header prompt templates produce these; map them to
# the canonical English field names used by required_strategy_fields.
_CHINESE_COL_ALIASES: dict[str, str] = {
    "策略名称":        "strategy_name",
    "策略名稱":        "strategy_name",
    "彩种":            "family",
    "彩種":            "family",
    "彩种/game":       "family",
    "彩種/game":       "family",
    "game":            "family",
    "回测视窗":        "window",
    "回測視窗":        "window",
    "视窗":            "window",
    "視窗":            "window",
    "edge":            "edge_150",   # generic "Edge" column → treat as edge_150
    "sharpe":          "sharpe",
    "mc(n≥1000)":      "mc_status",
    "mc（n≥1000）":    "mc_status",
    "mc status":       "mc_status",
    "vs.现有最佳":     "vs_incumbent",
    "vs.現有最佳":     "vs_incumbent",
    "vs incumbent":    "vs_incumbent",
    "vs_incumbent":    "vs_incumbent",
}


def _check_strategy_output_fields(
    section_text: str,
    required_fields: list,
    edge_values: list,
    min_strategies: int = 3,
) -> tuple[Optional[str], Optional[str]]:
    """
    Validate each data row in the ## Strategy Output Table section against
    required_strategy_fields.  Returns (verdict, reason) or (None, None).

    Checks (in order):
    6a. Parse header row for required columns (case-insensitive, with Chinese aliases).
         Missing columns are SKIPPED (not rejected) — prompt format and contract fields
         have historically been inconsistent.  Only columns present in the header are
         validated further.
    6b'. Minimum strategy count — enforced here using the robust parser (moved from step 3).
    6b. Check every data row has non-empty cells for each column that IS in the header.
    6c. vs_incumbent: if all positive-edge rows have vs_incumbent <= 0 → FAILED_WEAK_EDGE.
    6d. validation_tier T1 + promotion signal → FAILED_ACCEPTANCE.
    6e. non-T4 row with blank/NONE promotion_blocker → REPLAN_REQUIRED.
    6f. mc_status=PASS + vs_incumbent <= 0 + promotion_blocker=NONE → FAILED_ACCEPTANCE.
    """
    lines = section_text.splitlines()

    # Find header row (first pipe-separated row with ≥3 columns after the header marker)
    header_cols: list[str] = []
    header_line_idx = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("|") and stripped.count("|") >= 3:
            cols = [c.strip().lower() for c in stripped.strip("|").split("|")]
            # Skip separator rows (all dashes)
            if all(re.match(r'^[-:]+$', c) for c in cols if c):
                continue
            if len(cols) >= 3:
                header_cols = cols
                header_line_idx = i
                break

    if not header_cols:
        # No parseable header found — cannot verify fields
        return None, None

    # Build column index map with Chinese→English alias support
    col_idx: dict[str, int] = {}
    for j, h in enumerate(header_cols):
        # Direct mapping
        col_idx[h] = j
        # Also map via alias (h is already lower-cased)
        alias = _CHINESE_COL_ALIASES.get(h)
        if alias:
            col_idx[alias.lower()] = j

    # Now resolve required_fields against col_idx
    resolved_col_idx: dict[str, int] = {}
    for req in required_fields:
        key = req.lower()
        if key in col_idx:
            resolved_col_idx[key] = col_idx[key]
            continue
        # underscore ↔ space normalisation
        key_space = key.replace("_", " ")
        for h, j in col_idx.items():
            if key_space == h.replace("_", " "):
                resolved_col_idx[key] = j
                break
        # edge_1000 / edge_1500 interchangeable
        if key == "edge_1000" and key not in resolved_col_idx:
            for h, j in col_idx.items():
                if "edge_1500" in h or "edge 1500" in h:
                    resolved_col_idx["edge_1000"] = j
                    break

    _STRICTLY_REQUIRED = frozenset({"vs_incumbent", "validation_tier", "promotion_blocker", "mc_status"})

    # 6a. Missing-column check.
    # Formatting tolerance is allowed for informational columns, but governance
    # and promotion-control fields must still exist in the table header.
    missing_strict_fields = [
        field for field in required_fields
        if field.lower() in _STRICTLY_REQUIRED and field.lower() not in resolved_col_idx
    ]
    if missing_strict_fields:
        return (
            "REPLAN_REQUIRED",
            (
                "## Strategy Output Table is missing required column(s): "
                f"{', '.join(missing_strict_fields)}. "
                "Do not omit vs_incumbent, validation_tier, promotion_blocker, or mc_status."
            ),
        )

    # Columns not found in the header (even with aliases) are skipped.
    # We only validate the subset of required_fields that actually appear in the header.
    validated_fields = [f for f in required_fields if f.lower() in resolved_col_idx]
    if not validated_fields:
        # No required fields found in header at all — cannot validate further
        return None, None

    # Parse data rows (after header + separator)
    data_rows: list[dict] = []
    past_header = False
    past_separator = False
    for line in lines[header_line_idx + 1:]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cols_raw = [c.strip() for c in stripped.strip("|").split("|")]
        # Skip separator
        if all(re.match(r'^[-:]+$', c) for c in cols_raw if c):
            past_separator = True
            continue
        if not past_separator:
            continue
        if len(cols_raw) < len(header_cols):
            # Pad with empty
            cols_raw += [""] * (len(header_cols) - len(cols_raw))
        row = {h: cols_raw[j] if j < len(cols_raw) else "" for j, h in enumerate(header_cols)}
        # Also inject aliased English keys so downstream checks can use English field names
        for alias_zh, alias_en in _CHINESE_COL_ALIASES.items():
            if alias_zh in row:
                row.setdefault(alias_en.lower(), row[alias_zh])
        # Skip rows that look like the strategy_name header (e.g. example row)
        sname = (row.get("strategy_name") or row.get("策略名稱") or row.get("策略名称") or "").lower()
        if re.match(r'^[-=]+$', sname) or sname in ("strategy_name", "strategy name", ""):
            continue
        data_rows.append(row)

    if not data_rows:
        return (
            "FAILED_ACCEPTANCE",
            (
                f"## Strategy Output Table header found but 0 data rows parsed "
                f"(required \u2265 {min_strategies}). "
                "Table must contain actual strategy result rows, not just headers or analysis text."
            ),
        )

    # 6b'. Minimum strategy count check (format-agnostic, uses robust parser)
    unique_strat_names = {
        (r.get("strategy_name") or r.get("\u7b56\u7565\u540d\u7a31") or r.get("\u7b56\u7565\u540d\u79f0") or "").strip().lower()
        for r in data_rows
    } - {"", "strategy_name", "strategy name"}
    if len(unique_strat_names) < min_strategies:
        return (
            "FAILED_ACCEPTANCE",
            (
                f"Deep Research task produced {len(unique_strat_names)} distinct strategy name(s) "
                f"in '## Strategy Output Table', required \u2265 {min_strategies}. "
                "Each row must have a unique strategy name, not just analysis text."
            ),
        )

    # 6b. Check each row for empty required cells — only for fields found in the header
    # Per-window format detection: if the header has a "window" / "回測視窗" column, the
    # table uses one row per (strategy × window) instead of one row per strategy.
    # In that case, edge_150/mc_status/vs_incumbent may be "—" on non-base-window rows.
    # We allow a blank in field F for a row if ANY sibling row with the same strategy_name
    # provides a non-blank value for F.
    is_per_window = "window" in col_idx
    _BLANK_VALUES: frozenset = frozenset({"", "-", "—", "n/a", "na"})
    # Only these fields have downstream business-logic gates (6c–6f) that require
    # non-blank values.  Everything else (next_action, family, incumbent_name, etc.)
    # is informational and we tolerate blank / missing cells to avoid spurious
    # REPLAN_REQUIRED when the worker has a minor formatting inconsistency.
    # Per-window: these fields may be blank on non-base-window rows if a sibling row
    # for the same strategy provides a non-blank value.
    _PER_WINDOW_EXEMPT = frozenset({"edge_150", "edge_500", "mc_status", "vs_incumbent", "incumbent_name"})
    blank_row_fields: list[str] = []
    for row in data_rows:
        for req in validated_fields:
            key = req.lower()
            # Skip fields that are not strictly required (informational only)
            if key not in _STRICTLY_REQUIRED:
                continue
            val = row.get(key, "").strip()
            if not val or val in _BLANK_VALUES:
                # Per-window format: blank is OK if any sibling row for the same
                # strategy provides a non-blank value for this field.
                if is_per_window and key in _PER_WINDOW_EXEMPT:
                    sname = (row.get("strategy_name") or "?").strip()
                    has_any = any(
                        (r.get(key) or "").strip() and (r.get(key) or "").strip().lower() not in _BLANK_VALUES
                        for r in data_rows
                        if (r.get("strategy_name") or "?").strip() == sname
                    )
                    if has_any:
                        continue
                blank_row_fields.append(f"row[{row.get('strategy_name') or row.get('策略名稱','?')}].{key}")
    if blank_row_fields:
        return (
            "REPLAN_REQUIRED",
            (
                f"## Strategy Output Table has blank required fields: "
                f"{', '.join(blank_row_fields[:10])}. "
                "Do not leave vs_incumbent, validation_tier, promotion_blocker, or mc_status blank."
            ),
        )

    # 6c. vs_incumbent check → FAILED_WEAK_EDGE
    # For rows with positive edge, check if ALL vs_incumbent <= 0
    def _parse_float(s: str) -> Optional[float]:
        try:
            return float(re.sub(r'[^0-9+\-.]', '', s))
        except (ValueError, TypeError):
            return None

    positive_edge_rows = []
    for row in data_rows:
        e150 = _parse_float(row.get("edge_150", ""))
        e500 = _parse_float(row.get("edge_500", ""))
        e1000 = _parse_float(row.get("edge_1000", "") or row.get("edge_1500", ""))
        any_positive = any(v is not None and v > 0 for v in [e150, e500, e1000])
        if any_positive:
            positive_edge_rows.append(row)

    if positive_edge_rows:
        all_vs_incumbent_nonpositive = all(
            (_parse_float(r.get("vs_incumbent", "")) or 0.0) <= 0
            for r in positive_edge_rows
        )
        if all_vs_incumbent_nonpositive:
            return (
                "FAILED_WEAK_EDGE",
                (
                    f"{len(positive_edge_rows)} strategy row(s) have positive edge but "
                    "all vs_incumbent values are ≤ 0. "
                    "No promotion is warranted. "
                    "Mark FAILED_WEAK_EDGE and propose signal fusion or new family in next cycle."
                ),
            )

    # 6d. T1_MC_PASS + promotion signal → FAILED_ACCEPTANCE
    for row in data_rows:
        tier = row.get("validation_tier", "").strip().lower()
        if tier == "t1_mc_pass":
            blocker = row.get("promotion_blocker", "").strip().lower()
            next_act = row.get("next_action", "").strip().lower()
            # Any promotion keyword in blocker=NONE / next_action is suspicious
            if blocker in ("none", "") or _PROMOTION_KEYWORDS.search(
                row.get("promotion_blocker", "") + " " + row.get("next_action", "")
            ):
                return (
                    "FAILED_ACCEPTANCE",
                    (
                        f"Strategy '{row.get('strategy_name','?')}' has validation_tier=T1_MC_PASS "
                        "but promotion_blocker is NONE or next_action implies promotion. "
                        "T1_MC_PASS strategies cannot be promotion candidates. "
                        "Set promotion_blocker='MC_ONLY_NO_THREE_WINDOW' and next_action='shadow_watch'."
                    ),
                )

    # 6e. Non-T4 row with blank/NONE promotion_blocker → REPLAN_REQUIRED
    for row in data_rows:
        tier = row.get("validation_tier", "").strip().lower()
        if tier in ("t4_deployable", ""):
            continue
        blocker = row.get("promotion_blocker", "").strip()
        if not blocker or blocker.lower() == "none":
            return (
                "REPLAN_REQUIRED",
                (
                    f"Strategy '{row.get('strategy_name','?')}' has validation_tier={tier!r} "
                    "but promotion_blocker is blank or 'NONE'. "
                    "Every non-T4 strategy must have a non-NONE promotion_blocker explaining "
                    "why it has not been promoted (e.g. 'MC_ONLY_NO_THREE_WINDOW', "
                    "'VS_INCUMBENT_NEGATIVE', 'MCNEMAR_NOT_RUN')."
                ),
            )

    # 6f. mc_status=PASS + vs_incumbent<=0 + promotion_blocker=NONE → FAILED_ACCEPTANCE
    for row in data_rows:
        mc_status = row.get("mc_status", "").strip().upper()
        blocker = row.get("promotion_blocker", "").strip().lower()
        vs_inc = _parse_float(row.get("vs_incumbent", ""))
        if mc_status == "PASS" and (vs_inc is not None and vs_inc <= 0) and blocker == "none":
            return (
                "FAILED_ACCEPTANCE",
                (
                    f"Strategy '{row.get('strategy_name','?')}' has mc_status=PASS but "
                    "vs_incumbent ≤ 0 and promotion_blocker=NONE. "
                    "MC PASS alone is not sufficient for promotion when vs_incumbent ≤ 0. "
                    "Set promotion_blocker='VS_INCUMBENT_NEGATIVE'."
                ),
            )

    return None, None


def _build_and_gate_task_result(
    task: dict,
    status: str,
    duration: int,
    changed_files: list[str],
    codex_output: str,
    error_markers_hit: list[str],
    contract: dict,
    contract_valid: bool,
    contract_reason: str,
    completed_file_path: str,
    provider: str = "",
) -> tuple[dict, str, str]:
    """
    Returns: (task_result_json, final_status, gate_verdict)
    """
    acceptance_tests = contract.get("acceptance_tests", []) if isinstance(contract, dict) else []
    required_outputs = contract.get("required_outputs", []) if isinstance(contract, dict) else []
    forbidden_changes = contract.get("forbidden_changes", []) if isinstance(contract, dict) else []

    output_present = bool(codex_output.strip())
    required_output_map = {
        "completed_markdown": bool(completed_file_path),
        "task_result_json": True,  # will be written right after build
        "changed_files_list": True,
    }
    missing_required = [name for name in required_outputs if not required_output_map.get(name, False)]
    violations = _violates_forbidden_changes(changed_files, forbidden_changes if isinstance(forbidden_changes, list) else [])
    no_effective_delivery = (not changed_files) and (bool(error_markers_hit) or not output_present)
    is_env_blocked = _is_environment_blocking_error(error_markers_hit)
    rate_limit_info = _detect_rate_limit_failure(codex_output, error_markers_hit, provider=provider)

    acceptance_results = []
    for item in acceptance_tests:
        acceptance_results.append({
            "name": str(item),
            "passed": output_present and not bool(error_markers_hit) and not no_effective_delivery,
            "evidence": (
                "worker_stdout_tail_present"
                if output_present and not no_effective_delivery
                else "no_effective_delivery"
            ),
        })

    gate_verdict = "PASS"
    final_status = status
    gate_reason = ""
    if not contract_valid:
        gate_verdict = "INVALID_DELIVERY"
        final_status = "REPLAN_REQUIRED"
        gate_reason = contract_reason
    elif missing_required:
        gate_verdict = "FAILED_ACCEPTANCE"
        final_status = "FAILED_ACCEPTANCE"
        gate_reason = f"missing required outputs: {', '.join(missing_required)}"
    elif no_effective_delivery:
        gate_verdict = "FAILED_ACCEPTANCE"
        final_status = "FAILED_ACCEPTANCE"
        gate_reason = "no effective delivery: no changed files and no valid runtime output"
    elif violations:
        gate_verdict = "POLICY_VIOLATION"
        final_status = "REPLAN_REQUIRED"
        gate_reason = f"forbidden changes detected: {', '.join(violations[:5])}"
    elif status == "FAILED":
        if rate_limit_info:
            gate_verdict = "FAILED_RATE_LIMIT"
            final_status = "FAILED_RATE_LIMIT"
            gate_reason = rate_limit_info["final_message"]
        elif is_env_blocked:
            gate_verdict = "BLOCKED_ENV"
            final_status = "BLOCKED_ENV"
            gate_reason = f"environment execution blocked: {error_markers_hit[0] if error_markers_hit else 'unknown'}"
        else:
            gate_verdict = "WORKER_RUNTIME_FAILED"
            final_status = "FAILED"
            gate_reason = "worker runtime failure markers detected"

    # ── Deep Research strategy output gate (runs only when existing gates pass) ─
    if gate_verdict == "PASS":
        strat_gate_verdict, strat_gate_reason = _check_strategy_gate(task, codex_output, contract)
        if strat_gate_verdict:
            gate_verdict = strat_gate_verdict
            if strat_gate_verdict in ("FAILED_NO_EDGE", "FAILED_WEAK_EDGE"):
                final_status = strat_gate_verdict
            elif strat_gate_verdict == "FAILED_ACCEPTANCE":
                final_status = "FAILED_ACCEPTANCE"
            else:
                final_status = "REPLAN_REQUIRED"
            gate_reason = strat_gate_reason or gate_verdict

    task_result = {
        "version": "1.0",
        "task_id": task.get("id"),
        "slot_key": task.get("slot_key"),
        "title": task.get("title"),
        "status": final_status,
        "gate_verdict": gate_verdict,
        "gate_reason": gate_reason,
        "duration_seconds": duration,
        "changed_files": changed_files,
        "error_markers_hit": error_markers_hit,
        "required_outputs": required_outputs,
        "missing_required_outputs": missing_required,
        "forbidden_change_violations": violations,
        "acceptance_results": acceptance_results,
        "next_action": (
            "Planner must replan from task_result gate_reason and handoff_questions."
            if final_status == "REPLAN_REQUIRED"
            else "Fix the delivery contract failure from gate_reason and rerun the same research focus."
            if final_status == "FAILED_ACCEPTANCE"
            else "Wait for provider reset or switch provider before retrying."
            if final_status == "FAILED_RATE_LIMIT"
            else "Record the negative research result and use gate_reason to steer the next candidate family."
            if final_status in ("FAILED_NO_EDGE", "FAILED_WEAK_EDGE")
            else "Continue to next planned task."
        ),
        "provider": rate_limit_info.get("provider") if rate_limit_info else provider,
        "failure_reason": rate_limit_info.get("failure_reason") if rate_limit_info else "",
        "reason": rate_limit_info.get("reason") if rate_limit_info else "",
        "reset_hint": rate_limit_info.get("reset_hint") if rate_limit_info else "",
        "blocked_until": rate_limit_info.get("blocked_until") if rate_limit_info else "",
        "final_message": rate_limit_info.get("final_message") if rate_limit_info else gate_reason,
        "matched_rate_limit_patterns": rate_limit_info.get("matched_patterns") if rate_limit_info else [],
    }
    return task_result, final_status, gate_verdict


def _finalize(lock: dict):
    """Codex process is dead — write completed file, update DB."""
    task_id = lock["task_id"]
    task = db.get_task(task_id)
    if not task:
        db.clear_worker_lock()
        return

    slot_key = task["slot_key"]
    slug = task["slug"] or "task"
    date_folder = task["date_folder"]

    log_path = common.find_stdout_log_path(slot_key, date_folder)
    codex_output = ""
    if os.path.exists(log_path):
        with open(log_path) as f:
            codex_output = f.read()

    changed_files_now = common.git_changed_files()
    meta = common.read_meta(slot_key, date_folder)
    worker_runtime = meta.get("worker_runtime", "codex")
    requested_provider = meta.get("worker_requested_provider", meta.get("worker_provider", worker_runtime))
    fallback_reason = meta.get("worker_fallback_reason")
    execution_mode = meta.get("worker_execution_mode", "direct")
    baseline_changed_files = set(meta.get("baseline_changed_files") or [])
    changed_files = sorted(set(changed_files_now) - baseline_changed_files)

    # Determine runtime status heuristically from worker output because we do not
    # retain the original process handle / exit code across launchd ticks.
    output_lower = codex_output.lower()
    error_markers_hit = _check_worker_runtime_errors(output_lower)
    # 若輸出包含明確失敗訊號（例如 quota/policy/auth），必定標 FAILED。
    # 否則再看是否有產出與異動。
    has_output = bool(codex_output.strip())
    has_changes = bool(changed_files)
    fatal_error = bool(error_markers_hit)
    if fatal_error:
        status = "FAILED"
    elif not has_output and not has_changes:
        status = "FAILED"
    elif has_output and not has_changes and len(codex_output.strip()) < 120:
        # Avoid treating a tiny one-line runtime message as a successful delivery.
        status = "FAILED"
    else:
        status = "COMPLETED"

    started_at = task.get("started_at") or lock.get("started_at") or datetime.now(timezone.utc).isoformat()
    try:
        started_dt = datetime.fromisoformat(started_at)
        if started_dt.tzinfo is None:
            started_dt = started_dt.replace(tzinfo=timezone.utc)
        else:
            started_dt = started_dt.astimezone(timezone.utc)
        duration = int((datetime.now(timezone.utc) - started_dt).total_seconds())
    except Exception:
        duration = 0

    completed_text_parts = [
        f"## 執行摘要\n\n狀態：{status}，耗時：{duration}s\n",
        (
            "執行器資訊：\n"
            f"- 請求：{requested_provider}\n"
            f"- 實際：{worker_runtime}\n"
            f"- 模式：{execution_mode}\n"
            + (f"- Fallback：{fallback_reason}\n" if fallback_reason else "")
        ),
        "## 異動檔案清單\n\n" + ("\n".join(f"- {f}" for f in changed_files) if changed_files else "（無異動）"),
        f"## Worker 輸出（後 200 行）\n\n```\n{codex_output[-4000:]}\n```",
        "## 驗證結果\n\n（請人工確認）",
        "## 阻塞 / 風險\n\n（請人工填寫）",
    ]
    completed_text = "\n\n".join(completed_text_parts)

    c_path = common.completed_path(slot_key, slug, date_folder)
    with open(c_path, "w") as f:
        f.write(f"# Completed: {task['title']}\n\n")
        f.write(completed_text)

    contract_path = common.contract_path(slot_key, slug, date_folder)
    contract = {}
    contract_valid = False
    contract_reason = "task contract missing"
    if os.path.exists(contract_path):
        try:
            with open(contract_path, "r", encoding="utf-8") as f:
                contract = json.load(f)
            contract_valid, contract_reason = common.validate_task_contract(contract)
        except Exception as exc:
            contract_valid = False
            contract_reason = f"failed to parse contract: {exc}"

    task_result, final_status, gate_verdict = _build_and_gate_task_result(
        task=task,
        status=status,
        duration=duration,
        changed_files=changed_files,
        codex_output=codex_output,
        error_markers_hit=error_markers_hit,
        contract=contract,
        contract_valid=contract_valid,
        contract_reason=contract_reason,
        completed_file_path=c_path,
        provider=meta.get("worker_provider") or meta.get("worker_requested_provider") or meta.get("worker_runtime") or "",
    )
    result_path = common.result_path(slot_key, slug, date_folder)
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(task_result, f, ensure_ascii=False, indent=2)

    error_message = ""
    if final_status in ("FAILED", "FAILED_RATE_LIMIT", "REPLAN_REQUIRED", "BLOCKED_ENV", "FAILED_NO_EDGE", "FAILED_WEAK_EDGE"):
        error_message = task_result.get("gate_reason", "") or (", ".join(error_markers_hit[:3]) if error_markers_hit else "")

    if final_status == "FAILED_RATE_LIMIT":
        blocked_provider = meta.get("worker_provider") or meta.get("worker_requested_provider") or meta.get("worker_runtime") or "copilot"
        common.set_provider_rate_limit_block(
            blocked_provider,
            reason=task_result.get("failure_reason") or "copilot_rate_limit",
            task_id=task_id,
            requested_provider=meta.get("worker_requested_provider"),
            runtime=meta.get("worker_runtime"),
            reset_hint=task_result.get("reset_hint"),
            blocked_until=task_result.get("blocked_until"),
            cooldown_seconds=DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS,
        )

    db.update_task(
        task_id,
        status=final_status,
        completed_file_path=c_path,
        completed_text=completed_text,
        changed_files_json=json.dumps(changed_files, ensure_ascii=False),
        completed_at=datetime.now(timezone.utc).isoformat(),
        duration_seconds=duration,
        error_message=error_message,
    )

    # Classify failure into taxonomy category and persist to DB.
    fc = failure_taxonomy.classify(
        final_status=final_status,
        gate_verdict=task_result.get("gate_verdict", ""),
        gate_reason=task_result.get("gate_reason", ""),
        error_markers=error_markers_hit,
    )
    if final_status not in ("COMPLETED", "REPLAN_REQUIRED"):
        db.update_task(
            task_id,
            failure_category=fc.category,
            failure_weight=fc.weight,
        )

    # Record quality failures to Negative Space Memory so the planner
    # can apply progressive suppression on repeat failures.
    # Pass the taxonomy weight so the guard can apply category-differentiated suppression.
    if final_status in planner_guard.QUALITY_FAILURE_STATUSES:
        dedupe_key = task.get("dedupe_key")
        if dedupe_key:
            planner_guard.record_outcome(
                dedupe_key,
                final_status,
                gate_reason=task_result.get("gate_reason", ""),
                failure_category=fc.category,
                failure_weight=fc.weight,
            )
            common.log_jsonl(
                RUNNER, "WORKER_PLANNER_GUARD_RECORDED",
                task_id=task_id,
                dedupe_key=dedupe_key,
                final_status=final_status,
                failure_category=fc.category,
                failure_weight=fc.weight,
            )

    # Auto-repair loop: generate a targeted repair task when FORMAT_CONTRACT or
    # VALIDATION_CONTRACT failures accumulate beyond the threshold.
    repair_task_generator.maybe_generate_repair_task(
        task_id=task_id,
        task=task,
        fc=fc,
        gate_reason=task_result.get("gate_reason", ""),
    )

    # Repair outcome tracking: if this task IS a repair task, evaluate and
    # persist its success/effectiveness, and escalate suppression when all
    # attempts are exhausted without success.
    repair_task_generator.record_repair_outcome(
        task_id=task_id,
        task=task,
        fc=fc,
        final_status=final_status,
    )

    # read_meta includes slot_key/date_folder keys; avoid passing them twice.
    safe_meta = {
        k: v for k, v in (meta or {}).items()
        if k not in ("slot_key", "date_folder")
    }

    # Sync the in-memory task snapshot with the final status that was just written to
    # the DB so _attempt_auto_commit sees "COMPLETED" instead of the stale "RUNNING".
    task["status"] = final_status
    git_commit_info = _attempt_auto_commit(task, safe_meta, task_result, changed_files)
    _record_git_commit_state(task, task_result, changed_files, git_commit_info)
    common.write_meta(
        slot_key,
        date_folder,
        **{
            **safe_meta,
            "task_id": task_id,
            "title": task["title"],
            "slug": slug,
            "status": final_status,
            "duration_seconds": duration,
            "changed_files": changed_files,
            "task_contract_path": contract_path,
            "task_result_path": result_path,
            "gate_verdict": gate_verdict,
            "gate_reason": task_result.get("gate_reason", ""),
            "failure_reason": task_result.get("failure_reason", ""),
            "failure_provider": task_result.get("provider", ""),
            "reset_hint": task_result.get("reset_hint", ""),
            "final_message": task_result.get("final_message", ""),
            "git_commit_status": git_commit_info.get("status"),
            "git_commit_sha": git_commit_info.get("commit_sha"),
            "git_source_branch": git_commit_info.get("source_branch"),
            "git_inbox_branch": git_commit_info.get("merge_branch"),
            "git_commit_reason": git_commit_info.get("reject_reason"),
        },
    )

    # \u2500\u2500 Outcome pipeline write (real extraction) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    try:
        from orchestrator.light_worker_tick import _extract_task_type as _ett
        _task_type = _ett(task.get("dedupe_key") or "")
        _success   = final_status == "COMPLETED"
        _res = outcome_extractor.extract(
            task_id            = task_id,
            task_type          = _task_type,
            completed_file_path= c_path,
            completed_text     = completed_text,
        )
        db.record_task_outcome(
            task_id           = task_id,
            task_type         = _task_type,
            success           = _success,
            quality_score     = _res.quality_score,
            roi_score         = _res.roi_score,
            edge_score        = _res.edge_score,
            extraction_method = _res.extraction_method,
            best_edge         = _res.best_edge,
            strategies_found  = _res.strategies_found,
            mc_pass_count     = _res.mc_pass_count,
            confidence_score  = _res.confidence_score,
        )
        db.update_task_type_roi(
            task_type     = _task_type,
            quality_score = _res.quality_score,
            roi_score     = _res.roi_score,
            success       = _success,
        )
        logger.debug(
            "Outcome recorded: task=%d type=%s method=%s q=%.2f roi=%.2f edge=%.3f conf=%.2f",
            task_id, _task_type, _res.extraction_method,
            _res.quality_score, _res.roi_score, _res.edge_score, _res.confidence_score,
        )
    except Exception as _oe:
        logger.debug("Outcome write error (non-fatal): %s", _oe)
    # \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

    db.clear_worker_lock()

    msg = (
        f"Task {task_id} finalized as {final_status} "
        f"({duration}s, {len(changed_files)} files changed, gate={gate_verdict})"
    )
    logger.info(msg)
    db.log_tick(RUNNER, "WORKER_FINALIZED", task_id=task_id, message=msg)
    common.log_jsonl(
        RUNNER,
        "WORKER_FINALIZED",
        task_id=task_id,
        status=final_status,
        gate_verdict=gate_verdict,
    )
    # Keep backlog status snapshot in sync after every finalized task.
    common.refresh_backlog_auto_status()


def _log_idle_seconds(path: str):
    try:
        mtime = os.path.getmtime(path)
        return max(0, int(time.time() - mtime))
    except OSError:
        return None


def _read_log_tail(path: str, max_chars: int = 6000) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()[-max_chars:]
    except OSError:
        return ""


def _copilot_permission_blocked(log_tail: str) -> bool:
    s = (log_tail or "").lower()
    markers = [
        "permission denied and could not request permission from user",
        "could not request permission from user",
        "cannot request permission from user",
        "tool permission",
    ]
    return any(marker in s for marker in markers)


def _claim(task: dict):
    """Claim a QUEUED task and launch the resolved worker runtime."""
    task_id = task.get("id")
    worker_provider = db.get_worker_provider()
    decision = execution_policy.evaluate("worker.claim", scope="main", provider=worker_provider, task_id=task_id)
    if not decision.allowed:
        msg = f"{decision.skip_reason} — skip execution"
        logger.info(msg)
        db.log_tick(RUNNER, "WORKER_SKIP_GLOBAL_GUARD", task_id=task_id, message=msg)
        common.log_jsonl(RUNNER, "WORKER_SKIP_GLOBAL_GUARD", task_id=task_id, reason=decision.skip_reason)
        execution_policy.record_skip(decision)
        return False

    task_id = task["id"]
    slot_key = task["slot_key"]
    slug = task["slug"] or "task"
    date_folder = task["date_folder"]
    prompt_path = task.get("prompt_file_path", "")
    if not prompt_path or not os.path.exists(prompt_path):
        msg = f"Task {task_id} prompt file missing: {prompt_path}"
        logger.error(msg)
        db.update_task(task_id, status="FAILED", error_message=msg)
        db.log_tick(RUNNER, "WORKER_FAILED", task_id=task_id, message=msg)
        return

    log_path = common.worker_stdout_log_path(slot_key, date_folder)

    with open(prompt_path) as f:
        prompt_content = f.read()

    log_file = open(log_path, "w")
    try:
        resolution = common.worker_command(prompt_content, worker_provider)
    except FileNotFoundError as e:
        log_file.write(f"{e}\n")
        log_file.close()
        msg = f"Task {task_id} worker provider '{worker_provider}' unavailable: {e}"
        logger.error(msg)
        db.update_task(task_id, status="FAILED", error_message=msg)
        common.write_meta(
            slot_key,
            date_folder,
            task_id=task_id,
            title=task["title"],
            slug=slug,
            status="FAILED",
            error_message=msg,
            worker_provider=worker_provider,
        )
        db.log_tick(RUNNER, "WORKER_FAILED", task_id=task_id, message=msg)
        common.log_jsonl(RUNNER, "WORKER_FAILED", task_id=task_id, error=msg)
        return

    worker_runtime = resolution["runtime"]
    dispatch_provider = resolution.get("dispatch_provider", worker_runtime)
    requested_provider = resolution["requested_provider"]
    fallback_reason = resolution.get("fallback_reason")
    worker_model = resolution.get("model") or ""
    command = resolution["command"]
    execution_mode = "daemon" if requested_provider == "copilot-daemon" else "direct"
    baseline_changed_files = common.git_changed_files()

    launch_decision = execution_policy.evaluate(
        "worker.launch",
        scope="main",
        provider=dispatch_provider,
        model=worker_model,
        task_id=task_id,
    )
    if not launch_decision.allowed:
        msg = f"{launch_decision.skip_reason} — worker launch blocked"
        db.log_tick(RUNNER, "WORKER_SKIP_GLOBAL_GUARD", task_id=task_id, message=msg)
        common.log_jsonl(RUNNER, "WORKER_SKIP_GLOBAL_GUARD", task_id=task_id, reason=launch_decision.skip_reason)
        execution_policy.record_skip(launch_decision, requested_provider=requested_provider)
        return False
    execution_policy.record_pre_call(
        launch_decision,
        requested_provider=requested_provider,
        worker_runtime=worker_runtime,
        execution_mode=execution_mode,
    )

    proc = subprocess.Popen(
        command,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        cwd=common.ROOT,
        start_new_session=True,
    )
    log_file.close()

    db.update_task(task_id, status="RUNNING", worker_pid=proc.pid,
                   started_at=datetime.now(timezone.utc).isoformat())
    db.set_worker_lock(pid=proc.pid, task_id=task_id)
    common.write_meta(slot_key, date_folder,
                      task_id=task_id, title=task["title"], slug=slug,
                      status="RUNNING", worker_pid=proc.pid,
                      worker_runtime=worker_runtime,
                      worker_dispatch_provider=dispatch_provider,
                      worker_provider=worker_provider,
                      worker_requested_provider=requested_provider,
                      worker_model=worker_model,
                      worker_execution_mode=execution_mode,
                      worker_fallback_reason=fallback_reason,
                      baseline_changed_files=baseline_changed_files)

    msg = f"Task {task_id} claimed, {worker_runtime} PID={proc.pid}"
    logger.info(msg)
    db.log_tick(RUNNER, "WORKER_CLAIMED", task_id=task_id, message=msg)
    common.log_jsonl(RUNNER, "WORKER_CLAIMED", task_id=task_id, pid=proc.pid, worker_runtime=worker_runtime)

    # ── Resource isolation guard ───────────────────────────────────────────────
    # Log a warning (non-blocking) when CPU is high and light workers are active,
    # so operators can tune MAX_LIGHT_WORKERS or LONG_RUNNER thresholds.
    try:
        _cpu = common.get_system_cpu_pct(interval=0.5)
        _light_active = db.count_active_light_workers()
        if _cpu > 80.0 and _light_active > 0:
            _iso_msg = (
                f"Resource isolation: CPU={_cpu:.0f}% with {_light_active} light worker(s) active "
                f"while research task {task_id} starting — consider lowering MAX_LIGHT_WORKERS"
            )
            logger.warning(_iso_msg)
            db.log_tick(RUNNER, "WORKER_HIGH_CPU_LOAD", task_id=task_id, message=_iso_msg)
        # Emit research worker metrics
        _depth = db.get_queue_depth_by_type()
        db.log_worker_metrics(
            worker_type="research",
            active_count=1,
            queued_count=_depth.get("research", 0),
            completed_count=0,
            failed_count=0,
            avg_latency_s=db.get_avg_task_latency("research", window_hours=6),
            throughput_ph=db.get_throughput_per_hour("research", window_hours=1),
            cpu_pct=_cpu if _cpu > 0 else common.get_system_cpu_pct(interval=0.1),
            slot_limit=1,
            backpressure=0,
        )
    except Exception as _iso_err:
        logger.debug("Isolation guard error (non-fatal): %s", _iso_err)


        fallback_msg = (
            f"Task {task_id} requested {requested_provider} but launched {worker_runtime}: "
            f"{fallback_reason}"
        )
        logger.warning(fallback_msg)
        db.log_tick(RUNNER, "WORKER_RUNTIME_FALLBACK", task_id=task_id, message=fallback_msg)
        common.log_jsonl(
            RUNNER,
            "WORKER_RUNTIME_FALLBACK",
            task_id=task_id,
            requested_provider=requested_provider,
            worker_runtime=worker_runtime,
            reason=fallback_reason,
        )

    return True


def run(force: bool = False):
    common.ensure_dirs()

    # Health gate — block if system is marked BROKEN
    _gate_ok, _gate_reason = health.check_and_gate("worker")
    if not _gate_ok:
        logger.error("[health] Worker blocked: %s", _gate_reason)
        db.log_tick(RUNNER, "WORKER_BLOCKED_HEALTH", message=_gate_reason)
        return

    lock = db.get_worker_lock()
    policy_state = execution_policy.current_state()
    worker_provider = db.get_worker_provider()

    if lock and lock["pid"]:
        pid = lock["pid"]
        task_id = lock["task_id"]
        task = db.get_task(task_id) if task_id else None
        meta = common.read_meta(task["slot_key"], task["date_folder"]) if task else {}
        worker_runtime = meta.get("worker_runtime", "codex")

        # Check 8-hour timeout
        if task and task.get("started_at"):
            try:
                started = datetime.fromisoformat(task["started_at"])
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                else:
                    started = started.astimezone(timezone.utc)
                elapsed = (datetime.now(timezone.utc) - started).total_seconds()
                if elapsed > common.WORKER_MAX_SECONDS and common.is_process_alive(pid):
                    logger.warning(f"Task {task_id} exceeded {common.WORKER_MAX_SECONDS}s — killing")
                    common.kill_process_tree(pid)
            except Exception:
                pass

        if common.is_process_alive(pid):
            # Copilot special guard: process alive but log stalled for too long => likely hung.
            if task and worker_runtime == "copilot":
                log_path = common.find_stdout_log_path(task["slot_key"], task["date_folder"])
                tail = _read_log_tail(log_path)
                if _copilot_permission_blocked(tail):
                    msg = f"Task {task_id} blocked by Copilot permission gate; force finalize"
                    logger.warning(msg)
                    db.log_tick(RUNNER, "WORKER_PERMISSION_BLOCKED", task_id=task_id, message=msg)
                    common.log_jsonl(RUNNER, "WORKER_PERMISSION_BLOCKED", task_id=task_id, pid=pid)
                    common.kill_process_tree(pid)
                    _finalize(lock)
                    return
                idle_seconds = _log_idle_seconds(log_path)
                if idle_seconds is not None and idle_seconds > COPILOT_STALE_LOG_TIMEOUT_SECONDS:
                    msg = (
                        f"Task {task_id} appears stuck: copilot process alive but log idle "
                        f"{idle_seconds}s (> {COPILOT_STALE_LOG_TIMEOUT_SECONDS}s)"
                    )
                    logger.warning(msg)
                    db.log_tick(RUNNER, "WORKER_STUCK_TIMEOUT", task_id=task_id, message=msg)
                    common.log_jsonl(RUNNER, "WORKER_STUCK_TIMEOUT", task_id=task_id, pid=pid, idle_seconds=idle_seconds)
                    common.kill_process_tree(pid)
                    _finalize(lock)
                    return

            if not policy_state.get("scheduler_enabled"):
                msg = f"Scheduler disabled; task {task_id} still running (PID={pid}), no new claim"
                logger.info(msg)
                db.log_tick(RUNNER, "WORKER_SKIP_DISABLED_RUNNING", task_id=task_id, message=msg)
                common.log_jsonl(RUNNER, "WORKER_SKIP_DISABLED_RUNNING", task_id=task_id, pid=pid)
                return
            db.update_worker_heartbeat()
            msg = f"Task {task_id} still running (PID={pid})"
            logger.info(msg)
            db.log_tick(RUNNER, "WORKER_HEARTBEAT", task_id=task_id, message=msg)
            common.log_jsonl(RUNNER, "WORKER_HEARTBEAT", task_id=task_id, pid=pid)
            return
        else:
            logger.info(f"Task {task_id} PID={pid} is dead — finalizing")
            _finalize(lock)

    decision = execution_policy.evaluate("worker.run", scope="main", provider=worker_provider)
    if not decision.allowed:
        msg = f"{decision.skip_reason} — skip execution"
        logger.info(msg)
        db.log_tick(RUNNER, "WORKER_SKIP_GLOBAL_GUARD", message=msg)
        common.log_jsonl(RUNNER, "WORKER_SKIP_GLOBAL_GUARD", reason=decision.skip_reason)
        execution_policy.record_skip(decision)
        return

    provider_block = common.get_provider_rate_limit_block(worker_provider)
    if provider_block:
        blocked_until = provider_block.get("blocked_until") or "unknown"
        reset_hint = provider_block.get("reset_hint") or blocked_until
        msg = (
            f"Worker provider {worker_provider} is rate-limited; waiting until {blocked_until}. "
            f"reset_hint={reset_hint}"
        )
        logger.warning(msg)
        db.log_tick(RUNNER, "WORKER_SKIP_PROVIDER_RATE_LIMIT", task_id=provider_block.get("task_id"), message=msg)
        common.log_jsonl(
            RUNNER,
            "WORKER_SKIP_PROVIDER_RATE_LIMIT",
            provider=worker_provider,
            blocked_until=blocked_until,
            reset_hint=reset_hint,
            task_id=provider_block.get("task_id"),
        )
        return

    if worker_provider == "copilot-daemon":
        msg = "Worker provider is copilot-daemon — resident daemon will claim queued tasks"
        logger.info(msg)
        db.log_tick(RUNNER, "WORKER_SKIP_DAEMON_PROVIDER", message=msg)
        common.log_jsonl(RUNNER, "WORKER_SKIP_DAEMON_PROVIDER")
        return

    # Apply aging bonus before selection so long-waiting items bubble up
    try:
        aged = db.apply_aging_bonus()
        if aged:
            logger.info(f"[worker] Aging applied to {aged} backlog items")
    except Exception as _age_err:
        logger.warning(f"[worker] Aging bonus error (non-fatal): {_age_err}")

    # Try to claim the highest-priority QUEUED task using execution policy
    queued_task = None
    try:
        queued_task = db.get_next_task_by_policy()
        # Filter: research worker should only claim research (or untyped) tasks
        if queued_task and queued_task.get("worker_type") == "light":
            queued_task = None
    except Exception as _pol_err:
        logger.warning(f"[worker] Policy selection error, falling back: {_pol_err}")

    if not queued_task:
        # Fallback: direct priority query (research-typed only)
        try:
            queued_task = db.get_next_research_task_by_priority()
        except Exception:
            pass

    if not queued_task:
        # Last resort: FIFO for research tasks
        fallback = [
            t for t in (db.list_tasks(status="QUEUED", limit=10) or [])
            if t.get("worker_type") in ("research", None)
        ]
        queued_task = fallback[0] if fallback else None

    if not queued_task:
        msg = "No QUEUED tasks available"
        logger.info(msg)
        db.log_tick(RUNNER, "WORKER_SKIP_IDLE_NO_TASK", message=msg)
        common.log_jsonl(RUNNER, "WORKER_SKIP_IDLE_NO_TASK")
        return

    _claim(queued_task)


if __name__ == "__main__":
    db.init_db()
    force_run = str(os.environ.get("ORCHESTRATOR_FORCE_RUN", "")).strip().lower() in ("1", "true", "yes", "on")
    run(force=force_run)
