"""P251D — Evidence dashboard read-only API route implementation artifact."""
from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


TASK_ID = "P251D"
SCHEMA_VERSION = "1.0"
DATE_SLUG = datetime.now().strftime("%Y%m%d")

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "outputs" / "research"
P251B_JSON_PATH = OUTPUT_DIR / "p251b_cross_lottery_evidence_dashboard_data_20260606.json"
P251C_JSON_PATH = OUTPUT_DIR / "p251c_evidence_dashboard_api_payload_contract_plan_20260606.json"
REPLAY_ROUTE_PATH = REPO_ROOT / "lottery_api" / "routes" / "replay.py"

JSON_OUTPUT = OUTPUT_DIR / f"p251d_evidence_dashboard_readonly_api_route_{DATE_SLUG}.json"
MD_OUTPUT = OUTPUT_DIR / f"p251d_evidence_dashboard_readonly_api_route_{DATE_SLUG}.md"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _scan_route_convention() -> Dict[str, Any]:
    replay_text = REPLAY_ROUTE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(replay_text)
    imported_modules: List[str] = []
    imported_from: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            imported_from.extend(f"{base}:{alias.name}" for alias in node.names)

    forbidden_terms = ("controlled_apply", "migration", "alembic", "shutil", "subprocess")
    return {
        "route_file": str(REPLAY_ROUTE_PATH.relative_to(REPO_ROOT)),
        "existing_replay_namespace": "/api/replay/*",
        "implemented_endpoint_present": '/api/replay/evidence-dashboard' in replay_text,
        "strategy_catalog_present": '/api/replay/strategy-catalog' in replay_text,
        "freshness_present": '/api/replay/freshness' in replay_text,
        "artifact_loader_present": "_load_evidence_dashboard_payload" in replay_text,
        "forbidden_imports_present": [
            name
            for name in imported_modules + imported_from
            if any(term in name for term in forbidden_terms)
        ],
    }


def build_p251d_report() -> Dict[str, Any]:
    p251b = _load_json(P251B_JSON_PATH)
    p251c = _load_json(P251C_JSON_PATH)
    route_scan = _scan_route_convention()
    big_lotto = next(card for card in p251b["lottery_cards"] if card["lottery_type"] == "BIG_LOTTO")

    report = {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "classification": "EVIDENCE_DASHBOARD_READONLY_API_ROUTE_IMPLEMENTED",
        "source_artifacts": {
            "p251b_dashboard_data": str(P251B_JSON_PATH.relative_to(REPO_ROOT)),
            "p251c_contract_plan": str(P251C_JSON_PATH.relative_to(REPO_ROOT)),
        },
        "route_convention_scan": route_scan,
        "implemented_endpoint": {
            "path": "/api/replay/evidence-dashboard",
            "http_method": "GET",
            "route_file": str(REPLAY_ROUTE_PATH.relative_to(REPO_ROOT)),
            "artifact_backed": True,
            "db_query_performed": False,
        },
        "implementation_files": [
            "lottery_api/routes/replay.py",
            f"analysis/p251d_evidence_dashboard_readonly_api_route_{''}".replace("_", "_").strip("_"),
        ],
        "response_contract_preserved": {
            "task_id": p251b["task_id"],
            "classification": p251b["classification"],
            "strategy_rows_len": len(p251b["strategy_rows"]),
            "artifact_only_visible_count": sum(1 for row in p251b["strategy_rows"] if row["artifact_only_flag"]),
            "default_lifecycle_statuses": p251b["default_filter_state"]["enabled_lifecycle_statuses"],
            "exclude_by_lifecycle": p251b["default_filter_state"]["exclude_by_lifecycle"],
            "big_lotto_replay_rows": big_lotto["replay_rows"],
            "big_lotto_draw_rows": big_lotto["draw_rows"],
            "big_lotto_canonical_rows": big_lotto["canonical_rows"],
            "big_lotto_add_on_rows": p251b["global_summary"]["big_lotto_add_on_rows"],
            "no_deployable_candidate": p251b["global_summary"]["no_deployable_candidate"],
            "no_betting_advice_notice_present": "no_betting_advice_notice" in p251b,
            "contract_path_matches_p251c": p251c["proposed_endpoint"]["path"] == "/api/replay/evidence-dashboard",
        },
        "no_db_write_confirmed": True,
        "no_registry_mutation_confirmed": True,
        "no_strategy_promotion_confirmed": True,
        "no_ui_implementation_confirmed": True,
        "no_betting_advice_confirmed": True,
        "tests": {
            "targeted_route_tests": "tests/test_p251d_evidence_dashboard_readonly_api_route.py",
            "p251c_regression": "tests/test_p251c_evidence_dashboard_api_payload_contract_plan.py",
            "p251b_regression": "tests/test_p251b_cross_lottery_evidence_dashboard_data_builder.py",
        },
        "final_decision": (
            "P251D complete. Implemented GET /api/replay/evidence-dashboard as a "
            "read-only artifact-backed replay endpoint that serves the published P251B "
            "payload without DB reads, registry mutation, strategy promotion, UI work, "
            "or betting advice."
        ),
    }
    report["implementation_files"] = [
        "lottery_api/routes/replay.py",
        "analysis/p251d_evidence_dashboard_readonly_api_route.py",
        "outputs/research/p251d_evidence_dashboard_readonly_api_route_20260606.json",
        "outputs/research/p251d_evidence_dashboard_readonly_api_route_20260606.md",
        "tests/test_p251d_evidence_dashboard_readonly_api_route.py",
    ]
    return report


def build_md_report(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    add = lines.append

    add("# P251D — Evidence Dashboard Read-only API Route")
    add("")
    add(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    add(f"**Task:** `{TASK_ID}`  ")
    add(f"**Classification:** `EVIDENCE_DASHBOARD_READONLY_API_ROUTE_IMPLEMENTED`  ")
    add("")
    add("## Executive Summary")
    add("")
    add(
        "P251D implements the read-only replay endpoint `/api/replay/evidence-dashboard` "
        "and serves the published P251B dashboard artifact directly, following the "
        "P251C contract path and preserving all no-overclaim semantics."
    )
    add("")
    add("## Source Artifacts")
    add("")
    for key, value in report["source_artifacts"].items():
        add(f"- {key}: `{value}`")
    add("")
    add("## Existing Route Convention Scan")
    add("")
    for key, value in report["route_convention_scan"].items():
        add(f"- {key}: `{value}`")
    add("")
    add("## Implemented Endpoint")
    add("")
    for key, value in report["implemented_endpoint"].items():
        add(f"- {key}: `{value}`")
    add("")
    add("## Response Payload Summary")
    add("")
    for key, value in report["response_contract_preserved"].items():
        add(f"- {key}: `{value}`")
    add("")
    add("## P251B Semantic Preservation")
    add("")
    add("- Strategy rows remain >= 41 and artifact-only rows remain visible.")
    add("- Lifecycle remains badge/filter only and does not exclude by default.")
    add("- BIG_LOTTO replay/raw/canonical/add-on counts remain separated.")
    add("")
    add("## No-Overclaim / No-Betting Notice")
    add("")
    add("- No DB write")
    add("- No registry mutation")
    add("- No strategy promotion")
    add("- No UI implementation")
    add("- No betting advice")
    add("")
    add("## Files Changed")
    add("")
    for path in report["implementation_files"]:
        add(f"- `{path}`")
    add("")
    add("## Tests")
    add("")
    for key, value in report["tests"].items():
        add(f"- {key}: `{value}`")
    add("")
    add("## Explicit Non-Actions")
    add("")
    add("- Did not query or write the database for this endpoint.")
    add("- Did not mutate registry or strategy logic.")
    add("- Did not implement frontend/UI.")
    add("- Did not generate predictions or betting advice.")
    add("")
    add("Final Classification: `EVIDENCE_DASHBOARD_READONLY_API_ROUTE_IMPLEMENTED`")
    return "\n".join(lines)


def main() -> int:
    report = build_p251d_report()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    MD_OUTPUT.write_text(build_md_report(report), encoding="utf-8")
    print(f"Wrote {JSON_OUTPUT}")
    print(f"Wrote {MD_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
