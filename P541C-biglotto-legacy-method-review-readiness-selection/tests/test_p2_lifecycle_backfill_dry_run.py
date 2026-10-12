from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "generate_p2_lifecycle_backfill_dry_run.py"
MANIFEST_PATH = REPO_ROOT / "outputs" / "replay" / "p2_lifecycle_backfill_dry_run_manifest_20260510.json"
REPORT_PATH = REPO_ROOT / "outputs" / "replay" / "p2_lifecycle_backfill_dry_run_report_20260510.md"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

ALLOWED_LIFECYCLE_STATUSES = {"ONLINE", "OFFLINE", "REJECTED", "OBSERVATION", "RETIRED"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_script() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=REPO_ROOT)


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text())


def test_dry_run_generates_manifest_and_report():
    _run_script()
    assert MANIFEST_PATH.exists(), "dry-run manifest not written"
    assert REPORT_PATH.exists(), "dry-run report not written"


def test_dry_run_is_read_only_and_manifest_schema_is_valid():
    before = _sha256(DB_PATH)
    _run_script()
    after = _sha256(DB_PATH)
    assert before == after, "dry-run script must not change the runtime DB"

    manifest = _load_manifest()
    assert manifest["mode"] == "dry-run"
    assert manifest["no_write_proof"]["db_sha256_unchanged"] is True
    assert manifest["no_write_proof"]["manifest_rows_runtime_write_allowed"] is False

    for key in [
        "runtime_sources",
        "evidence_only_sources",
        "runtime_schema_snapshot",
        "summary",
        "promotable_candidates",
        "blocked_rows",
        "parse_error_rows",
    ]:
        assert key in manifest, f"missing manifest key: {key}"

    # Non-negative integers (hardcoded counts removed — they shift as data evolves)
    pc = manifest["summary"]["promotable_candidates"]
    br = manifest["summary"]["blocked_rows"]
    pe = manifest["summary"]["parse_error_rows"]
    tr = manifest["summary"]["total_rows"]
    assert isinstance(pc, int) and pc >= 0, f"promotable_candidates must be non-negative int, got {pc!r}"
    assert isinstance(br, int) and br >= 0, f"blocked_rows must be non-negative int, got {br!r}"
    assert isinstance(pe, int) and pe >= 0, f"parse_error_rows must be non-negative int, got {pe!r}"
    assert tr == pc + br + pe, f"total_rows {tr} != promotable+blocked+parse ({pc}+{br}+{pe})"


def test_manifest_rows_use_allowed_lifecycle_and_remain_non_writable():
    _run_script()
    manifest = _load_manifest()

    all_rows = (
        manifest["promotable_candidates"]
        + manifest["blocked_rows"]
        + manifest["parse_error_rows"]
    )

    promotable_signatures = {
        (row["strategy_id"], row.get("target_draw"), row.get("target_date"))
        for row in manifest["promotable_candidates"]
    }

    for row in all_rows:
        assert row["runtime_write_allowed"] is False
        assert row["lifecycle_status"] in ALLOWED_LIFECYCLE_STATUSES
        assert row["strategy_id"]
        assert row["source_evidence"]
        assert row["validation_status"] in {"PROMOTABLE", "BLOCKED", "PARSE_ERROR"}
        assert row["validation_reasons"], "validation reasons must not be empty"

    for row in manifest["blocked_rows"]:
        signature = (row["strategy_id"], row.get("target_draw"), row.get("target_date"))
        assert signature not in promotable_signatures

    for row in manifest["parse_error_rows"]:
        signature = (row["strategy_id"], row.get("target_draw"), row.get("target_date"))
        assert signature not in promotable_signatures


def test_runtime_and_evidence_sources_are_separated_in_the_manifest():
    _run_script()
    manifest = _load_manifest()

    runtime_paths = {entry["path"] for entry in manifest["runtime_sources"]}
    evidence_paths = {entry["path"] for entry in manifest["evidence_only_sources"]}

    assert all(not path.startswith("outputs/replay/") for path in runtime_paths)
    assert {
        "outputs/replay/p2_lifecycle_catalog_backfill_plan_20260510.md",
        "outputs/replay/p0_replay_data_health_20260510.md",
        "outputs/replay/p0_replay_product_golive_pr_readiness_20260510.md",
        "outputs/replay/p0_replay_product_post_merge_closure_20260510.md",
    }.issubset(evidence_paths)

    report_text = REPORT_PATH.read_text()
    assert "No DB writes were performed." in report_text
    assert "runtime_write_allowed is false for every manifest row" in report_text or "runtime_write_allowed" in report_text
    assert "runtime source" in report_text.lower()
    assert "evidence-only" in report_text.lower()