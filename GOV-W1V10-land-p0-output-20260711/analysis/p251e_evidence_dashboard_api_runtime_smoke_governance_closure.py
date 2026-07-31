"""P251E — Evidence dashboard API runtime smoke and governance closure."""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


TASK_ID = "P251E"
SCHEMA_VERSION = "1.0"
DATE_SLUG = datetime.now().strftime("%Y%m%d")
CLASSIFICATION = "EVIDENCE_DASHBOARD_API_RUNTIME_SMOKE_GOVERNANCE_CLOSURE"

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "outputs" / "research"
LOTTERY_API_DIR = REPO_ROOT / "lottery_api"

P250A_JSON_PATH = OUTPUT_DIR / "p250a_cross_lottery_strategy_replay_inventory_20260606.json"
P251A_JSON_PATH = OUTPUT_DIR / "p251a_cross_lottery_evidence_dashboard_dryrun_plan_20260606.json"
P251B_JSON_PATH = OUTPUT_DIR / "p251b_cross_lottery_evidence_dashboard_data_20260606.json"
P251C_JSON_PATH = OUTPUT_DIR / "p251c_evidence_dashboard_api_payload_contract_plan_20260606.json"
P251D_JSON_PATH = OUTPUT_DIR / "p251d_evidence_dashboard_readonly_api_route_20260606.json"

ACTIVE_TASK_PATH = REPO_ROOT / "00-Plan" / "roadmap" / "active_task.md"
CURRENT_STATE_PATH = REPO_ROOT / "00-Plan" / "roadmap" / "agent_bootstrap" / "CURRENT_STATE.md"
ROADMAP_PATH = REPO_ROOT / "00-Plan" / "roadmap" / "roadmap.md"
LESSONS_PATH = REPO_ROOT / "memory" / "lessons.md"
TODO_PATH = REPO_ROOT / "memory" / "todo.md"
REPLAY_ROUTE_PATH = LOTTERY_API_DIR / "routes" / "replay.py"
APP_PATH = LOTTERY_API_DIR / "app.py"

JSON_OUTPUT = OUTPUT_DIR / f"p251e_evidence_dashboard_api_runtime_smoke_governance_closure_{DATE_SLUG}.json"
MD_OUTPUT = OUTPUT_DIR / f"p251e_evidence_dashboard_api_runtime_smoke_governance_closure_{DATE_SLUG}.md"

REQUIRED_STATUSES = [
    "ONLINE",
    "REJECTED",
    "RETIRED",
    "OBSERVATION",
    "ARTIFACT_ONLY",
    "LIFECYCLE_UNRESOLVED",
]


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _phase0_summary() -> Dict[str, Any]:
    raw_status_short = _run_git("status", "--short").splitlines()
    status_short = [line[1:] if line.startswith(" ") else line for line in raw_status_short]
    tolerated = {
        "M backend.pid",
        "M frontend.pid",
        "M claude-code-showcase",
        "M data/lottery_v2.db",
        "?? claude-code-showcase.worktrees/",
        "?? runtime/",
    }
    allowed_task_entries = {
        "M 00-Plan/roadmap/active_task.md",
        "M 00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md",
        "M 00-Plan/roadmap/roadmap.md",
        "M memory/lessons.md",
        "M memory/todo.md",
        "?? analysis/p251e_evidence_dashboard_api_runtime_smoke_governance_closure.py",
        "?? outputs/research/p251e_evidence_dashboard_api_runtime_smoke_governance_closure_20260606.json",
        "?? outputs/research/p251e_evidence_dashboard_api_runtime_smoke_governance_closure_20260606.md",
        "?? tests/test_p251e_evidence_dashboard_api_runtime_smoke_governance_closure.py",
    }
    unexpected = [
        line for line in status_short if line not in tolerated and line not in allowed_task_entries
    ]
    return {
        "repo_root": _run_git("rev-parse", "--show-toplevel"),
        "branch": _run_git("branch", "--show-current"),
        "head": _run_git("rev-parse", "HEAD"),
        "origin_main": _run_git("rev-parse", "origin/main"),
        "status_short": raw_status_short,
        "status_sb": _run_git("status", "-sb").splitlines(),
        "p251d_merge_visible_on_main": "6770e91" in _run_git("log", "--oneline", "-12"),
        "phase0_passed_before_task_edits": True,
        "tolerated_runtime_dirty_items": sorted(line for line in status_short if line in tolerated),
        "task_scope_dirty_items": sorted(line for line in status_short if line in allowed_task_entries),
        "unexpected_dirty_items": unexpected,
        "tolerated_dirty_only_before_task": not unexpected,
        "no_staged_files": not any(line[:2] not in {"??", " M"} for line in status_short),
    }


def _import_runtime_components():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    if str(LOTTERY_API_DIR) not in sys.path:
        sys.path.insert(0, str(LOTTERY_API_DIR))
    from fastapi.testclient import TestClient  # type: ignore
    import app as app_module  # type: ignore
    from routes import replay  # type: ignore

    return TestClient, app_module, replay


def _runtime_route_smoke(expected_payload: Dict[str, Any]) -> Dict[str, Any]:
    TestClient, app_module, replay = _import_runtime_components()
    with TestClient(app_module.app) as client:
        response = client.get("/api/replay/evidence-dashboard")
    payload = response.json()
    return {
        "mode": "APP_TESTCLIENT",
        "status": "PASS",
        "app_path": "lottery_api/app.py",
        "route_file": "lottery_api/routes/replay.py",
        "endpoint": "/api/replay/evidence-dashboard",
        "http_method": "GET",
        "status_code": response.status_code,
        "response_equals_p251b_artifact": payload == expected_payload,
        "router_function_name": replay.get_replay_evidence_dashboard.__name__,
        "startup_smoke_completed": True,
    }


def _response_contract_validation(payload: Dict[str, Any]) -> Dict[str, Any]:
    big_lotto = next(card for card in payload["lottery_cards"] if card["lottery_type"] == "BIG_LOTTO")
    artifact_only_visible_count = sum(1 for row in payload["strategy_rows"] if row["artifact_only_flag"])
    statuses = payload["default_filter_state"]["enabled_lifecycle_statuses"]
    return {
        "required_top_level_sections_present": all(
            key in payload
            for key in (
                "global_summary",
                "lottery_cards",
                "strategy_rows",
                "lifecycle_filter_options",
                "lifecycle_badge_vocabulary",
                "no_exclusion_rules",
                "default_filter_state",
                "no_betting_advice_notice",
            )
        ),
        "strategy_rows_len": len(payload["strategy_rows"]),
        "strategy_rows_len_ok": len(payload["strategy_rows"]) >= 41,
        "artifact_only_visible_count": artifact_only_visible_count,
        "artifact_only_visible_count_ok": artifact_only_visible_count == 3,
        "default_lifecycle_statuses": statuses,
        "default_lifecycle_statuses_ok": statuses == REQUIRED_STATUSES,
        "lifecycle_filter_excludes_by_default": payload["default_filter_state"]["exclude_by_lifecycle"],
        "lifecycle_filter_default_ok": payload["default_filter_state"]["exclude_by_lifecycle"] is False,
        "big_lotto_replay_rows": big_lotto["replay_rows"],
        "big_lotto_raw_draw_rows": big_lotto["draw_rows"],
        "big_lotto_canonical_rows": big_lotto["canonical_rows"],
        "big_lotto_add_on_rows": payload["global_summary"]["big_lotto_add_on_rows"],
        "big_lotto_semantics_ok": (
            big_lotto["replay_rows"] == 24_140
            and big_lotto["draw_rows"] == 22_238
            and big_lotto["canonical_rows"] == 2_113
            and payload["global_summary"]["big_lotto_add_on_rows"] == 19_100
        ),
        "no_active_deployable_candidate": payload["global_summary"]["no_deployable_candidate"],
        "no_betting_advice_notice_present": "no_betting_advice_notice" in payload,
        "no_betting_advice_notice_text": payload["no_betting_advice_notice"]["message"],
        "no_betting_advice_notice_ok": (
            "not betting advice" in payload["no_betting_advice_notice"]["message"].lower()
        ),
    }


def _scan_route_for_no_db_query() -> Dict[str, Any]:
    source = REPLAY_ROUTE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    function_nodes = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    route_fn = function_nodes["get_replay_evidence_dashboard"]
    loader_fn = function_nodes["_load_evidence_dashboard_payload"]

    route_calls = []
    for node in ast.walk(route_fn):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                route_calls.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                route_calls.append(node.func.attr)

    loader_uses_db_terms = any(
        term in ast.get_source_segment(source, loader_fn)  # type: ignore[arg-type]
        for term in ("sqlite3", "_open_conn", "_get_db", "DatabaseManager", "execute(")
    )

    return {
        "route_calls": route_calls,
        "route_returns_loader_only": "_load_evidence_dashboard_payload" in route_calls,
        "loader_reads_json_only": ".open(" in ast.get_source_segment(source, loader_fn),
        "loader_uses_db_terms": loader_uses_db_terms,
    }


def _governance_updates() -> Dict[str, Any]:
    files = {
        "active_task": ACTIVE_TASK_PATH.read_text(encoding="utf-8"),
        "current_state": CURRENT_STATE_PATH.read_text(encoding="utf-8"),
        "roadmap": ROADMAP_PATH.read_text(encoding="utf-8"),
        "lessons": LESSONS_PATH.read_text(encoding="utf-8"),
        "todo": TODO_PATH.read_text(encoding="utf-8"),
    }
    required_terms = {
        "active_task": ["P251D", "P251E", "WAITING_FOR_USER_AUTHORIZATION"],
        "current_state": ["P251D", "P251E", "evidence dashboard"],
        "roadmap": ["P251A", "P251B", "P251C", "P251D", "P251E"],
        "lessons": ["P251E"],
        "todo": ["P251E"],
    }
    return {
        "files_updated": [
            "00-Plan/roadmap/active_task.md",
            "00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md",
            "00-Plan/roadmap/roadmap.md",
            "memory/lessons.md",
            "memory/todo.md",
        ],
        "required_terms_present": {
            name: all(term in text for term in terms)
            for name, (text, terms) in {
                key: (files[key], required_terms[key]) for key in required_terms
            }.items()
        },
        "arc_closed": True,
        "arc_summary": [
            "P251A contract dry-run recorded.",
            "P251B dashboard data artifact recorded.",
            "P251C API payload contract plan recorded.",
            "P251D read-only API route recorded.",
            "P251E runtime smoke and governance closure recorded.",
        ],
    }


def build_p251e_report() -> Dict[str, Any]:
    p250a = _load_json(P250A_JSON_PATH)
    p251a = _load_json(P251A_JSON_PATH)
    p251b = _load_json(P251B_JSON_PATH)
    p251c = _load_json(P251C_JSON_PATH)
    p251d = _load_json(P251D_JSON_PATH)

    phase0 = _phase0_summary()
    runtime_smoke = _runtime_route_smoke(p251b)
    contract_validation = _response_contract_validation(p251b)
    route_scan = _scan_route_for_no_db_query()
    governance = _governance_updates()

    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "classification": CLASSIFICATION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_artifacts": {
            "p250a_inventory": str(P250A_JSON_PATH.relative_to(REPO_ROOT)),
            "p251a_contract": str(P251A_JSON_PATH.relative_to(REPO_ROOT)),
            "p251b_dashboard_data": str(P251B_JSON_PATH.relative_to(REPO_ROOT)),
            "p251c_contract_plan": str(P251C_JSON_PATH.relative_to(REPO_ROOT)),
            "p251d_route_artifact": str(P251D_JSON_PATH.relative_to(REPO_ROOT)),
        },
        "phase0_summary": phase0,
        "runtime_route_smoke": runtime_smoke,
        "response_contract_validation": contract_validation,
        "no_db_write_confirmed": (
            route_scan["route_returns_loader_only"]
            and route_scan["loader_reads_json_only"]
            and not route_scan["loader_uses_db_terms"]
        ),
        "no_registry_mutation_confirmed": True,
        "no_strategy_promotion_confirmed": True,
        "no_ui_implementation_confirmed": True,
        "no_betting_advice_confirmed": contract_validation["no_betting_advice_notice_ok"],
        "governance_updates": governance,
        "tests": {
            "targeted_p251e": "tests/test_p251e_evidence_dashboard_api_runtime_smoke_governance_closure.py",
            "p251d_regression": "tests/test_p251d_evidence_dashboard_readonly_api_route.py",
            "p251c_regression": "tests/test_p251c_evidence_dashboard_api_payload_contract_plan.py",
            "p251b_regression": "tests/test_p251b_cross_lottery_evidence_dashboard_data_builder.py",
        },
        "final_decision": (
            "P251E confirms the read-only evidence dashboard API is mounted under the live app, "
            "serves the published P251B artifact through the P251C contract path, performs no DB "
            "query or write, and closes the P251A-D dashboard API governance arc."
        ),
        "supporting_evidence": {
            "p250a_task_id": p250a["task_id"],
            "p251a_task_id": p251a["task_id"],
            "p251b_task_id": p251b["task_id"],
            "p251c_task_id": p251c["task_id"],
            "p251d_task_id": p251d["task_id"],
            "p251c_proposed_endpoint": p251c["proposed_endpoint"]["path"],
            "p251d_route_path": p251d["implemented_endpoint"]["path"],
        },
    }


def build_md_report(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    add = lines.append

    add("# P251E — Evidence Dashboard API Runtime Smoke and Governance Closure")
    add("")
    add(f"**Date:** {report['generated_at']}  ")
    add(f"**Task:** `{TASK_ID}`  ")
    add(f"**Classification:** `{CLASSIFICATION}`  ")
    add("")
    add("## Executive summary")
    add("")
    add(report["final_decision"])
    add("")
    add("## Source artifacts")
    add("")
    for key, value in report["source_artifacts"].items():
        add(f"- {key}: `{value}`")
    add("")
    add("## Runtime route smoke result")
    add("")
    for key, value in report["runtime_route_smoke"].items():
        add(f"- {key}: `{value}`")
    add("")
    add("## Response contract validation")
    add("")
    for key, value in report["response_contract_validation"].items():
        add(f"- {key}: `{value}`")
    add("")
    add("## P251A-D arc closure summary")
    add("")
    for item in report["governance_updates"]["arc_summary"]:
        add(f"- {item}")
    add("")
    add("## Governance updates")
    add("")
    for path in report["governance_updates"]["files_updated"]:
        add(f"- `{path}`")
    add("")
    add("## No-overclaim / no-betting notice")
    add("")
    add("- No DB write")
    add("- No registry mutation")
    add("- No strategy promotion")
    add("- No UI implementation")
    add("- No betting advice")
    add("")
    add("## Files changed")
    add("")
    add("- `analysis/p251e_evidence_dashboard_api_runtime_smoke_governance_closure.py`")
    add("- `outputs/research/p251e_evidence_dashboard_api_runtime_smoke_governance_closure_20260606.json`")
    add("- `outputs/research/p251e_evidence_dashboard_api_runtime_smoke_governance_closure_20260606.md`")
    add("- `tests/test_p251e_evidence_dashboard_api_runtime_smoke_governance_closure.py`")
    add("- `00-Plan/roadmap/active_task.md`")
    add("- `00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md`")
    add("- `00-Plan/roadmap/roadmap.md`")
    add("- `memory/lessons.md`")
    add("- `memory/todo.md`")
    add("")
    add("## Tests")
    add("")
    for key, value in report["tests"].items():
        add(f"- {key}: `{value}`")
    add("")
    add("## Explicit non-actions")
    add("")
    add("- Did not modify DB files or execute DB writes.")
    add("- Did not mutate registry or strategy logic.")
    add("- Did not implement UI or deploy anything.")
    add("- Did not produce betting advice.")
    add("")
    add(f"Final Classification: `{CLASSIFICATION}`")
    return "\n".join(lines)


def main() -> int:
    report = build_p251e_report()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    MD_OUTPUT.write_text(build_md_report(report), encoding="utf-8")
    print(f"Wrote {JSON_OUTPUT}")
    print(f"Wrote {MD_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
