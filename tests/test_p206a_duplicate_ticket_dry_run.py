from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_mlb_duplicate_ticket_dry_run import run_dry_run


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_dry_run_writes_json_csv_and_markdown_reports(tmp_path):
    input_path = tmp_path / "replay" / "recommendations.jsonl"
    rows = [
        {
            "game_id": "2026-05-11-LAA-CLE-824441",
            "tsl_side": "home",
            "tsl_market": "moneyline",
            "strategy_id": "strategy-a",
            "source_trace": {"learning_eligible": True},
        },
        {
            "game_id": "mlb_2026_824441",
            "tsl_side": "home",
            "tsl_market": "moneyline",
            "strategy_id": "strategy-a",
            "source_trace": {"learning_eligible": True},
        },
    ]
    _write_jsonl(input_path, rows)

    json_report = tmp_path / "report.json"
    csv_report = tmp_path / "report.csv"
    md_report = tmp_path / "report.md"
    payload = run_dry_run(
        [str(input_path)],
        json_report=json_report,
        md_report=md_report,
        csv_report=csv_report,
    )

    assert payload["total_input_rows"] == 2
    assert payload["kept_rows"] == 1
    assert payload["suppressed_rows"] == 1
    assert payload["input_sources"] == [str(input_path)]

    written = json.loads(json_report.read_text(encoding="utf-8"))
    assert written["suppression_rate"] == 0.5
    assert written["non_claims"]["future_prediction"] is False
    assert written["non_claims"]["production_or_db_mutation"] is False

    csv_rows = list(csv.DictReader(csv_report.open(encoding="utf-8")))
    assert csv_rows[0]["group_key"] == "game=824441|side=home|market=moneyline"
    assert csv_rows[1]["suppress_reason"]
    assert csv_rows[0]["learning_guard_status"] == "legacy_contract"

    md_text = md_report.read_text(encoding="utf-8")
    assert "local historical/replay dry run only" in md_text
    assert "not a future prediction" in md_text
    assert "DB mutation" in md_text
    assert "future-ticket mutation" in md_text


def test_dry_run_default_discovery_uses_local_jsonl_glob(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    input_path = tmp_path / "outputs" / "recommendations" / "PAPER" / "2026-05-11" / "one.jsonl"
    _write_jsonl(
        input_path,
        [
            {
                "game_id": "mlb_2026_824441",
                "tsl_side": "home",
                "tsl_market": "moneyline",
            }
        ],
    )

    payload = run_dry_run(
        ["outputs/recommendations/PAPER/**/*.jsonl"],
        json_report=tmp_path / "report" / "out.json",
        md_report=tmp_path / "report" / "out.md",
        csv_report=tmp_path / "report" / "out.csv",
    )

    assert payload["total_input_rows"] == 1
    assert payload["input_sources"] == [str(input_path.relative_to(tmp_path))]
