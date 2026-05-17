#!/usr/bin/env python3
"""Dry-run policy matrix for replay source promotion."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lottery_api.models.replay_source_promotion_contract import (
    PROMOTION_METHODS,
    can_execute_in_p5a,
    get_promotion_method_metadata,
)


DEFAULT_AUDIT = REPO_ROOT / "outputs" / "replay" / "p5_replay_source_of_truth_audit_20260517.json"
DEFAULT_PIPELINE = REPO_ROOT / "outputs" / "replay" / "p3_replay_pipeline_split_20260517.json"
DEFAULT_JSON = REPO_ROOT / "outputs" / "replay" / "p5a_replay_source_promotion_policy_20260517.json"
DEFAULT_MD = REPO_ROOT / "docs" / "replay" / "p5a_replay_source_promotion_policy_20260517.md"

P5_AUDIT_GIT_REF = "235b271"
P3_PIPELINE_GIT_REF = "480c554"


def _load_json_or_git(path: Path, git_ref: str) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    rel = str(path.relative_to(REPO_ROOT))
    completed = subprocess.run(
        ["git", "show", f"{git_ref}:{rel}"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _string_guard(payload: Any) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, str):
                assert value not in {"TBD", "TODO", "null"}, f"placeholder found in {key}"
            _string_guard(value)
    elif isinstance(payload, list):
        for item in payload:
            _string_guard(item)


def _method_risk(method: dict[str, Any]) -> str:
    if not method["deployment_safe"]:
        return "HIGH"
    if method["requires_db_write"]:
        return "MEDIUM"
    return "LOW"


def collect_policy(audit_path: Path | None = None, pipeline_path: Path | None = None) -> dict[str, Any]:
    audit = _load_json_or_git(audit_path or DEFAULT_AUDIT, P5_AUDIT_GIT_REF)
    pipeline = _load_json_or_git(pipeline_path or DEFAULT_PIPELINE, P3_PIPELINE_GIT_REF)

    input_summary = {
        "canonical_runtime_source": audit["source_of_truth_assessment"]["canonical_runtime_source"],
        "deployment_safe": audit["source_of_truth_assessment"]["deployment_safe"],
        "local_only_risk": audit["source_of_truth_assessment"]["local_only_risk"],
        "historical_reconstruction_candidates": len(pipeline["historical_reconstruction_candidates"]),
        "future_waiting_candidates": len(pipeline["future_waiting_candidates"]),
        "display_only_candidates": len(pipeline["display_only_candidates"]),
    }

    promotion_methods = []
    for method in PROMOTION_METHODS:
        meta = get_promotion_method_metadata(method)
        promotion_methods.append(
            {
                "method": meta["method"],
                "deployment_safe": meta["deployment_safe"],
                "reproducible": meta["reproducible"],
                "auditable": meta["auditable"],
                "requires_db_write": meta["requires_db_write"],
                "requires_human_approval": meta["requires_human_approval"],
                "supports_rollback": meta["supports_rollback"],
                "recommended_for_historical_reconstruction": meta["recommended_for_historical_reconstruction"],
                "risk": _method_risk(meta),
                "notes": meta["notes"],
                "can_execute_in_p5a": can_execute_in_p5a(method),
            }
        )

    recommended_policy = {
        "primary_method": "ARTIFACT_PROMOTION",
        "secondary_method": "CONTROLLED_DB_APPLY",
        "rationale": (
            "P0/P3 already produce auditable JSON artifacts; artifact promotion keeps reviewable diffs "
            "before a controlled DB apply, while the ignored local DB cannot be treated as source of truth."
        ),
        "preconditions": [
            "schema validation passes",
            "dry-run diff artifact is generated",
            "human approval is recorded",
            "rollback plan is available",
            "post-apply verification is defined",
        ],
        "explicit_non_goals": [
            "No DB write in P5A",
            "No replay row generation in P5A",
            "No promotion execution in P5A",
        ],
    }

    required_gates = [
        "explicit CEO/CTO approval",
        "dry-run diff artifact",
        "rollback plan",
        "post-apply verification",
        "drift guard pass",
    ]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_audit": _display_path(audit_path or DEFAULT_AUDIT),
        "pipeline_split": _display_path(pipeline_path or DEFAULT_PIPELINE),
        "input_summary": input_summary,
        "promotion_methods": promotion_methods,
        "recommended_policy": recommended_policy,
        "required_gates_before_execution": required_gates,
        "p4_acceptance_dependency": {
            "can_run_p4_before_policy": False,
            "reason": "Replay page acceptance must verify deployable source, not local ignored DB.",
        },
        "safety": {
            "db_write": False,
            "draw_import": False,
            "replay_row_generation": False,
            "prediction_update": False,
            "strategy_execution": False,
            "promotion_executed": False,
        },
    }

    _string_guard(payload)
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    lines = [
        "# P5A Replay Source Promotion Policy - 20260517",
        "",
        "## Final Classification",
        "P5A_REPLAY_SOURCE_PROMOTION_POLICY_COMPLETED",
        "",
        "## P5 Input Summary",
        f"- Canonical runtime source: {payload['input_summary']['canonical_runtime_source']}",
        f"- Deployment safe: {payload['input_summary']['deployment_safe']}",
        f"- Local-only risk: {payload['input_summary']['local_only_risk']}",
        "- Required policy gaps: no deployable promotion policy, DB copies ambiguity, local ignored DB risk, fixture/runtime mismatch.",
        "",
        "## Promotion Methods Compared",
    ]
    for row in payload["promotion_methods"]:
        lines.append(
            f"- {row['method']}: safe={row['deployment_safe']} reproducible={row['reproducible']} "
            f"auditable={row['auditable']} requires_db_write={row['requires_db_write']} "
            f"human_approval={row['requires_human_approval']} rollback={row['supports_rollback']} "
            f"recommended_for_historical_reconstruction={row['recommended_for_historical_reconstruction']} "
            f"risk={row['risk']}"
        )
    lines.extend([
        "",
        "## Recommended Policy",
        f"- Primary method: {payload['recommended_policy']['primary_method']}",
        f"- Secondary method: {payload['recommended_policy']['secondary_method']}",
        "- Long-term method: MIGRATION or SEED depending deployment model",
        f"- Rationale: {payload['recommended_policy']['rationale']}",
        "",
        "## P4 Acceptance Dependency",
        f"- Can P4 run now: {payload['p4_acceptance_dependency']['can_run_p4_before_policy']}",
        f"- Reason: {payload['p4_acceptance_dependency']['reason']}",
        "",
        "## Required Gates Before Actual DB Apply",
        *[f"- {gate}" for gate in payload["required_gates_before_execution"]],
        "",
        "## Safety Confirmation",
        "- No DB write",
        "- No draw import",
        "- No replay row generation",
        "- No prediction update",
        "- No strategy execution",
        "- No promotion executed",
        "",
        "## Current Conclusion",
        "The deployable path must be artifact-led first, then controlled DB apply. The ignored local DB remains non-canonical.",
    ])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-audit", default=str(DEFAULT_AUDIT))
    parser.add_argument("--pipeline-split", default=str(DEFAULT_PIPELINE))
    parser.add_argument("--output-json", default=str(DEFAULT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_MD))
    args = parser.parse_args(argv)

    payload = collect_policy(Path(args.source_audit), Path(args.pipeline_split))
    json_path = Path(args.output_json)
    md_path = Path(args.output_md)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_build_report(payload), encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "primary_method": payload["recommended_policy"]["primary_method"],
        "output_json": _display_path(json_path),
        "output_md": _display_path(md_path),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
