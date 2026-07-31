from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "tools" / "quick_predict.py"
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
        prediction_items = cur.execute("SELECT COUNT(*) FROM prediction_items").fetchone()[0]
        prediction_runs = cur.execute("SELECT COUNT(*) FROM prediction_runs").fetchone()[0]
        replay_rows = cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
        return prediction_items, prediction_runs, replay_rows
    finally:
        conn.close()


def test_help_exposes_dry_run_and_json_out():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=True,
    )
    assert "--dry-run" in proc.stdout
    assert "--json-out" in proc.stdout


def test_dry_run_generates_json_without_touching_db(tmp_path):
    json_out = tmp_path / "quick_predict_dryrun.json"

    before_sha = _sha256(DB_PATH)
    before_counts = _db_counts()

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--dry-run",
            "--json-out",
            str(json_out),
            "--lottery",
            "BIG_LOTTO",
            "--bets",
            "2",
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=True,
    )

    after_sha = _sha256(DB_PATH)
    after_counts = _db_counts()

    assert json_out.exists(), f"missing JSON output: {json_out}"
    payload = json.loads(json_out.read_text())

    assert payload["dry_run"] is True
    assert payload["db_written"] is False
    assert payload["prediction_items_inserted"] is False
    assert payload["prediction_runs_inserted"] is False
    assert payload["replay_rows_inserted"] is False
    assert payload["final_classification"] == "P4B_QUICK_PREDICT_DRYRUN_READY"
    assert isinstance(payload["predictions"], list)
    assert payload["predictions"], "expected at least one prediction payload"
    assert payload["predictions"][0]["lottery_type"] == "BIG_LOTTO"
    assert payload["predictions"][0]["num_bets"] == 2
    assert payload["predictions"][0]["bets"], "dry-run predictions should include bets"

    assert before_sha == after_sha, "dry-run must not change the DB file"
    assert before_counts == after_counts, "dry-run must not change DB row counts"
    assert "Dry-run completed" in proc.stdout

