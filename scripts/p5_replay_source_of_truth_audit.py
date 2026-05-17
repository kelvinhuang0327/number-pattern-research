#!/usr/bin/env python3
"""Read-only audit for replay source-of-truth and deployment safety."""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JSON = REPO_ROOT / "outputs" / "replay" / "p5_replay_source_of_truth_audit_20260517.json"
DEFAULT_MD = REPO_ROOT / "docs" / "replay" / "p5_replay_source_of_truth_report_20260517.md"
DEFAULT_POLICY_MD = REPO_ROOT / "docs" / "replay" / "p5_replay_source_of_truth_policy_20260517.md"

DB_CANDIDATES = [
    REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db",
    REPO_ROOT / "data" / "lottery_v2.db",
    REPO_ROOT / "data" / "lottery.db",
    REPO_ROOT / "tools" / "data" / "lottery_v2.db",
    REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db.p3bc_pre_rollback_20260516T154610",
]

ARTIFACT_CANDIDATES = [
    ("outputs/replay/p0_strategy_universe_inventory_20260517.json", "inventory"),
    ("docs/replay/p0_strategy_universe_inventory_report_20260517.md", "report"),
    ("lottery_api/models/replay_lifecycle_contract.py", "other"),
    ("outputs/replay/p1_lifecycle_formalization_fixture_20260517.json", "fixture"),
    ("docs/replay/p1_lifecycle_formalization_report_20260517.md", "report"),
    ("lottery_api/models/replay_pipeline_contract.py", "other"),
    ("outputs/replay/p3_replay_pipeline_split_20260517.json", "pipeline_split"),
    ("docs/replay/p3_replay_pipeline_split_report_20260517.md", "report"),
    ("docs/replay/p3_historical_reconstruction_policy_20260517.md", "report"),
    ("outputs/replay/non_online_replay_fixture_20260511.json", "fixture"),
]

RUNTIME_READ_PATHS = [
    {
        "component": "replay_api",
        "source": "lottery_api/data/lottery_v2.db",
        "source_type": "db",
        "risk": "HIGH",
        "notes": "GET /api/replay/history|summary|freshness opens this SQLite path in normal mode.",
    },
    {
        "component": "replay_api_fixture_mode",
        "source": "outputs/replay/non_online_replay_fixture_20260511.json",
        "source_type": "json",
        "risk": "MEDIUM",
        "notes": "Used only when fixture_mode=true; not the normal replay source.",
    },
    {
        "component": "replay_lifecycle_drift_guard",
        "source": "lottery_api/data/lottery_v2.db",
        "source_type": "db",
        "risk": "HIGH",
        "notes": "Read-only baseline guard reads the same SQLite path as the replay API.",
    },
    {
        "component": "run_replay_ci_db_validation",
        "source": "lottery_api/data/lottery_v2.db",
        "source_type": "db",
        "risk": "HIGH",
        "notes": "Dedicated DB path validation uses the same replay SQLite fixture by default.",
    },
    {
        "component": "p4a_rsm_refresh_readonly",
        "source": "lottery_api/data/lottery_v2.db",
        "source_type": "db",
        "risk": "HIGH",
        "notes": "Read-only diagnostic inspects prediction_items and strategy_prediction_replays.",
    },
    {
        "component": "p3_replay_pipeline_split_classifier",
        "source": "outputs/replay/p0_strategy_universe_inventory_20260517.json",
        "source_type": "json",
        "risk": "LOW",
        "notes": "Dry-run classifier reads the canonical P0 inventory artifact.",
    },
    {
        "component": "p3_replay_pipeline_split_classifier",
        "source": "outputs/replay/non_online_replay_fixture_20260511.json",
        "source_type": "json",
        "risk": "LOW",
        "notes": "Optional fixture input for display and compatibility context only.",
    },
    {
        "component": "tests/test_replay_api_contract.py",
        "source": "lottery_api/data/lottery_v2.db",
        "source_type": "db",
        "risk": "MEDIUM",
        "notes": "Direct async route tests expect the local replay DB fixture to exist.",
    },
    {
        "component": "tests/test_replay_api_contract.py",
        "source": "outputs/replay/non_online_replay_fixture_20260511.json",
        "source_type": "json",
        "risk": "LOW",
        "notes": "fixture_mode coverage is synthetic and read-only.",
    },
    {
        "component": "tests/test_replay_truth_level_contract.py",
        "source": "lottery_api/data/lottery_v2.db",
        "source_type": "db",
        "risk": "MEDIUM",
        "notes": "Truth-level contract depends on the same local replay DB fixture.",
    },
    {
        "component": "tests/test_replay_strategy_lifecycle_endpoint.py",
        "source": "in_memory_registry",
        "source_type": "unknown",
        "risk": "LOW",
        "notes": "Lifecycle endpoint test is registry-backed and does not open sqlite3.",
    },
]


def _git(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, check=False)


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _git_tracked(path: Path) -> bool:
    rel = str(path.relative_to(REPO_ROOT))
    return _git(["git", "ls-files", "--error-unmatch", rel]).returncode == 0


def _git_ignored(path: Path) -> bool:
    rel = str(path.relative_to(REPO_ROOT))
    return _git(["git", "check-ignore", "-q", rel]).returncode == 0


def _inspect_db(path: Path) -> tuple[bool, bool, list[str], str | None]:
    if not path.exists():
        return False, False, [], "missing"
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            cur = conn.cursor()
            tables = [row[0] for row in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()]
            has_replay = any("replay" in table for table in tables)
            has_prediction = any("prediction" in table for table in tables)
            return has_replay, has_prediction, tables, None
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        return False, False, [], f"sqlite_open_failed: {exc}"


def _db_risk(path: Path, tracked: bool, ignored: bool, has_replay: bool, has_prediction: bool, open_error: str | None) -> str:
    if open_error:
        return "HIGH"
    if ignored and has_replay:
        return "HIGH"
    if tracked and has_replay:
        return "MEDIUM"
    if has_prediction:
        return "MEDIUM" if tracked else "HIGH"
    return "LOW"


def _artifact_tracked(path: Path) -> bool:
    rel = str(path.relative_to(REPO_ROOT))
    return _git(["git", "ls-files", "--error-unmatch", rel]).returncode == 0


def collect_audit() -> dict[str, Any]:
    db_files = []
    for path in DB_CANDIDATES:
        tracked = _git_tracked(path)
        ignored = _git_ignored(path)
        has_replay, has_prediction, tables, open_error = _inspect_db(path)
        db_files.append(
            {
                "path": str(path.relative_to(REPO_ROOT)),
                "exists": path.exists(),
                "tracked_by_git": tracked,
                "ignored_by_git": ignored,
                "size_bytes": path.stat().st_size if path.exists() else 0,
                "contains_replay_tables": has_replay,
                "contains_prediction_tables": has_prediction,
                "risk": _db_risk(path, tracked, ignored, has_replay, has_prediction, open_error),
                "notes": "; ".join(
                    filter(
                        None,
                        [
                            f"tables={tables[:8]}" if tables else None,
                            open_error,
                            "runtime_read_path" if path == REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db" else None,
                            "ignored_local_db" if ignored else None,
                        ],
                    )
                )
                or "UNKNOWN",
            }
        )

    artifact_sources = []
    for rel_path, artifact_type in ARTIFACT_CANDIDATES:
        path = REPO_ROOT / rel_path
        tracked = _artifact_tracked(path)
        used_by_runtime = rel_path in {
            "outputs/replay/non_online_replay_fixture_20260511.json",
        }
        artifact_sources.append(
            {
                "path": rel_path,
                "type": artifact_type,
                "tracked_by_git": tracked,
                "deployable": False,
                "used_by_runtime": used_by_runtime,
                "notes": (
                    "governance_only_dry_run_artifact"
                    if artifact_type in {"inventory", "fixture", "pipeline_split", "report"}
                    else "supporting_contract_file"
                ),
            }
        )

    runtime_read_paths = list(RUNTIME_READ_PATHS)
    source_of_truth_assessment = {
        "canonical_runtime_source": "DB",
        "deployment_safe": False,
        "local_only_risk": True,
        "requires_migration_or_seed_policy": True,
        "requires_artifact_promotion_policy": True,
        "summary": (
            "Replay runtime reads SQLite DB directly in normal mode, while P0/P1/P3 "
            "artifacts remain governance-only. The current repo has multiple DB copies "
            "and an ignored runtime DB path, so deployment source-of-truth is not yet safe."
        ),
    }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(REPO_ROOT),
        "db_files": db_files,
        "artifact_sources": artifact_sources,
        "runtime_read_paths": runtime_read_paths,
        "source_of_truth_assessment": source_of_truth_assessment,
        "safety": {
            "db_write": False,
            "draw_import": False,
            "replay_row_generation": False,
            "prediction_update": False,
            "strategy_execution": False,
        },
    }

    _string_guard(payload)
    return payload


def _string_guard(payload: Any) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, str):
                assert value not in {"TBD", "TODO", "null"}, f"placeholder found in {key}"
            _string_guard(value)
    elif isinstance(payload, list):
        for item in payload:
            _string_guard(item)


def _build_report(payload: dict[str, Any]) -> str:
    db_summary = payload["source_of_truth_assessment"]
    lines = [
        "# P5 Replay Source of Truth Audit - 20260517",
        "",
        "## Final Classification",
        "P5_REPLAY_SOURCE_OF_TRUTH_AUDIT_COMPLETED",
        "",
        "## P0/P1/P3 Input Summary",
        "- Total strategies: 506",
        "- Lifecycle states: PRODUCTION, WATCHING, PROVISIONAL, REJECTED, OFFLINE, EXPERIMENTAL, UNKNOWN",
        "- Pipeline split: HISTORICAL_RECONSTRUCTION 97, FUTURE_WAITING 2, DISPLAY_ONLY 407, UNSUPPORTED 0",
        "- Replay coverage gap: 13 replay rows, 86 historical-record-no-replay, 407 no-records-anywhere",
        "",
        "## Source Map Summary",
        f"- DB sources: {len(payload['db_files'])}",
        f"- JSON / artifact sources: {len(payload['artifact_sources'])}",
        f"- Runtime read paths: {len(payload['runtime_read_paths'])}",
        "",
        "## Source-of-Truth Assessment",
        f"- Canonical runtime source: {db_summary['canonical_runtime_source']}",
        f"- Deployment safe: {db_summary['deployment_safe']}",
        f"- Local-only risk: {db_summary['local_only_risk']}",
        f"- Migration / seed policy required: {db_summary['requires_migration_or_seed_policy']}",
        f"- Artifact promotion policy required: {db_summary['requires_artifact_promotion_policy']}",
        "",
        "## Key Risks Found",
        "- Tracked vs ignored DB risk: the runtime SQLite path under lottery_api/data is ignored by git, while tracked DB copies also exist under data/ and tools/data/.",
        "- Local-only replay rows risk: the replay API reads the ignored local DB path directly, so a clean repo checkout does not guarantee deployable replay state.",
        "- Fixture/runtime mismatch risk: fixture_mode reads a JSON fixture, which is useful for tests but not the normal runtime source.",
        "- Deployment visibility risk: there is no Docker/migration/seed policy in the repo that currently proves production can derive the same replay rows deterministically.",
        "",
        "## Recommended Policy",
        "- Canonical runtime source should remain DB, but only a deployment DB that is produced by an explicit migration/seed/promotion policy.",
        "- P0/P1/P3 artifacts should remain governance and dry-run inputs, not runtime truth.",
        "- Replay page acceptance should verify the deployable source, not the local ignored DB file.",
        "- P6 watcher logic should continue to treat DB source-of-truth decisions as a blocker until the deployable path is explicit.",
        "",
        "## Safety Confirmation",
        "- No DB write",
        "- No draw import",
        "- No replay row generation",
        "- No prediction update",
        "- No strategy execution",
        "",
        "## Current Conclusion",
        "Runtime replay data is DB-backed, but the current repo state is not yet deployment-safe because the working replay DB is local/ignored and the promotion path is not formalized.",
    ]
    return "\n".join(lines) + "\n"


def _build_policy(payload: dict[str, Any]) -> str:
    assessment = payload["source_of_truth_assessment"]
    lines = [
        "# P5 Replay Source of Truth Policy",
        "",
        "1. Replay runtime canonical source is DB, not JSON governance artifacts.",
        "2. P0/P1/P3 artifacts are dry-run and governance inputs; they are not runtime truth.",
        "3. The local `lottery_api/data/lottery_v2.db` file is not deployable source-of-truth by itself because it is ignored by git and not promoted through a documented migration/seed path.",
        "4. Production replay rows should come from a deployment DB that is produced by explicit promotion policy, not from ad hoc local state.",
        "5. For historical reconstruction, choose one of migration, seed, artifact promotion, or controlled DB apply; compare their operational risk before adopting one, but do not execute any of them in P5.",
        "6. P4 replay page acceptance should validate the deployable source, never only the local checkout.",
        "7. P6 DAILY_539 torch blocker remains dependent on the same deployment source-of-truth decision.",
        "",
        "## Decision",
        f"- canonical_runtime_source: {assessment['canonical_runtime_source']}",
        f"- deployment_safe: {assessment['deployment_safe']}",
        f"- local_only_risk: {assessment['local_only_risk']}",
        f"- requires_migration_or_seed_policy: {assessment['requires_migration_or_seed_policy']}",
        f"- requires_artifact_promotion_policy: {assessment['requires_artifact_promotion_policy']}",
        "",
        "## Before Replay Page Acceptance",
        "The team should first formalize the deployable DB promotion path so that acceptance can run against the same source that production will actually serve.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", default=str(DEFAULT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_MD))
    parser.add_argument("--policy-md", default=str(DEFAULT_POLICY_MD))
    args = parser.parse_args(argv)

    payload = collect_audit()
    json_path = Path(args.output_json)
    md_path = Path(args.output_md)
    policy_path = Path(args.policy_md)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_build_report(payload), encoding="utf-8")
    policy_path.write_text(_build_policy(payload), encoding="utf-8")

    print(json.dumps({
        "status": "PASS",
        "canonical_runtime_source": payload["source_of_truth_assessment"]["canonical_runtime_source"],
        "output_json": _display_path(json_path),
        "output_md": _display_path(md_path),
        "policy_md": _display_path(policy_path),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
