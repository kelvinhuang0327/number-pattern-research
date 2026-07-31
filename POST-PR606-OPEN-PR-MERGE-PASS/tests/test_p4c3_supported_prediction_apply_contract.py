from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
APPLY_SCRIPT = REPO_ROOT / "scripts" / "p4c3_supported_prediction_apply.py"
QUICK_PREDICT = REPO_ROOT / "tools" / "quick_predict.py"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _db_counts() -> tuple[int, int, int]:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        cur = conn.cursor()
        return (
            cur.execute("SELECT COUNT(*) FROM prediction_items").fetchone()[0],
            cur.execute("SELECT COUNT(*) FROM prediction_runs").fetchone()[0],
            cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0],
        )
    finally:
        conn.close()


def _run_quick_predict_dry_run(tmp_path: Path, lottery: str, bets: int = 3) -> Path:
    json_out = tmp_path / f"{lottery.lower()}_quick_predict.json"
    subprocess.run(
        [
            sys.executable,
            str(QUICK_PREDICT),
            "--dry-run",
            "--json-out",
            str(json_out),
            "--lottery",
            lottery,
            "--bets",
            str(bets),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json_out


def _run_apply_script(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(APPLY_SCRIPT), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=check,
    )


def test_help_exposes_controlled_apply_and_scope_flags():
    proc = subprocess.run(
        [sys.executable, str(APPLY_SCRIPT), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--sources" in proc.stdout
    assert "--lotteries" in proc.stdout
    assert "--controlled-apply-id" in proc.stdout
    assert "--apply" in proc.stdout


def test_dry_run_receipt_is_read_only(tmp_path):
    big_source = _run_quick_predict_dry_run(tmp_path, "BIG_LOTTO", bets=3)
    power_source = _run_quick_predict_dry_run(tmp_path, "POWER_LOTTO", bets=3)
    json_out = tmp_path / "p4c3_apply_dryrun.json"

    before_sha = _sha256(DB_PATH)
    before_counts = _db_counts()

    proc = _run_apply_script(
        [
            "--db",
            str(DB_PATH),
            "--sources",
            f"{big_source},{power_source}",
            "--lotteries",
            "BIG_LOTTO,POWER_LOTTO",
            "--controlled-apply-id",
            "P4C3_20260516",
            "--json-out",
            str(json_out),
        ]
    )

    after_sha = _sha256(DB_PATH)
    after_counts = _db_counts()

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(json_out.read_text())

    assert payload["final_classification"] == "P4C3_SUPPORTED_PREDICTION_APPLY_PATH_READY"
    assert payload["mode"] == "dry-run"
    assert payload["db_written"] is False
    assert payload["prediction_runs_inserted"] is False
    assert payload["prediction_items_inserted"] is False
    assert payload["replay_rows_inserted"] is False
    assert payload["supported_lotteries"] == ["BIG_LOTTO", "POWER_LOTTO"]
    assert "DAILY_539" in payload["excluded_lotteries"]
    assert payload["planned_prediction_runs_count"] == 2
    assert payload["planned_prediction_items_count"] == 6
    assert len(payload["planned_prediction_runs"]) == 2
    assert payload["planned_prediction_runs"][0]["bets"], "expected planned items in receipt"

    assert before_sha == after_sha, "dry-run must not change DB hash"
    assert before_counts == after_counts, "dry-run must not change DB row counts"


def test_daily_539_is_rejected_even_with_valid_dry_run_source(tmp_path):
    daily_source = _run_quick_predict_dry_run(tmp_path, "DAILY_539", bets=3)
    json_out = tmp_path / "daily_rejected.json"

    proc = _run_apply_script(
        [
            "--db",
            str(DB_PATH),
            "--sources",
            str(daily_source),
            "--lotteries",
            "DAILY_539",
            "--controlled-apply-id",
            "P4C3_20260516",
            "--json-out",
            str(json_out),
        ],
        check=False,
    )

    assert proc.returncode != 0
    assert "unsupported scope" in (proc.stderr + proc.stdout)


def test_unsupported_lottery_is_rejected(tmp_path):
    big_source = _run_quick_predict_dry_run(tmp_path, "BIG_LOTTO", bets=3)
    json_out = tmp_path / "unsupported_rejected.json"

    proc = _run_apply_script(
        [
            "--db",
            str(DB_PATH),
            "--sources",
            str(big_source),
            "--lotteries",
            "LUCKY_7",
            "--controlled-apply-id",
            "P4C3_20260516",
            "--json-out",
            str(json_out),
        ],
        check=False,
    )

    assert proc.returncode != 0
    assert "supported" in (proc.stderr + proc.stdout)


def test_missing_source_json_is_rejected(tmp_path):
    missing_source = tmp_path / "missing.json"
    json_out = tmp_path / "missing_rejected.json"

    proc = _run_apply_script(
        [
            "--db",
            str(DB_PATH),
            "--sources",
            str(missing_source),
            "--lotteries",
            "BIG_LOTTO",
            "--controlled-apply-id",
            "P4C3_20260516",
            "--json-out",
            str(json_out),
        ],
        check=False,
    )

    assert proc.returncode != 0
    assert "source JSON not found" in (proc.stderr + proc.stdout)


def test_apply_requires_controlled_apply_id(tmp_path):
    big_source = _run_quick_predict_dry_run(tmp_path, "BIG_LOTTO", bets=3)
    json_out = tmp_path / "apply_requires_id.json"

    proc = _run_apply_script(
        [
            "--db",
            str(DB_PATH),
            "--sources",
            str(big_source),
            "--lotteries",
            "BIG_LOTTO",
            "--json-out",
            str(json_out),
            "--apply",
        ],
        check=False,
    )

    assert proc.returncode != 0
    assert "controlled-apply-id" in (proc.stderr + proc.stdout)
