"""Synthetic temporary-SQLite tests for the P543C contract generator."""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import pytest

from analysis import p543c_candidate_per_draw_validation_contract as contract_module


GENERATED_AT = "2026-07-10T00:00:00+08:00"


def _p543b() -> dict[str, object]:
    return {
        "summary": {
            "walk_forward_possible_from_committed_artifacts": 0,
            "permutation_possible_from_committed_artifacts": 0,
            "aggregate_only_not_validatable": 402,
            "unsupported": 6,
        },
        "pilot": {"computed": False},
    }


def _p543a(candidate_id: str = "alpha:1") -> dict[str, object]:
    return {
        "candidate_packet": {
            "multi_window_stable": [
                {
                    "candidate_id": candidate_id,
                    "lottery": "BIG_LOTTO",
                    "section": "combination",
                    "bucket": 1,
                    "observed_windows": [50, 300],
                }
            ]
        }
    }


def _raw(value: dict[str, object]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")


def _temporary_store(tmp_path: Path, *, predicted: str | None = "[1, 2, 3]", actual: str | None = "[1, 8, 9]") -> Path:
    path = tmp_path / "synthetic.db"
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CRE" + "ATE TABLE strategy_prediction_replays ("
            "id INTEGER PRIMARY KEY, lottery_type TEXT, target_draw TEXT, target_date TEXT, "
            "strategy_id TEXT, strategy_name TEXT, bet_index INTEGER, predicted_numbers TEXT, "
            "predicted_special INTEGER, actual_numbers TEXT, actual_special INTEGER, hit_count INTEGER, "
            "special_hit INTEGER, replay_status TEXT)"
        )
        for index, date in enumerate(("2024/01/01", "2024/01/05"), start=1):
            connection.execute(
                "INS" + "ERT INTO strategy_prediction_replays "
                "(id, lottery_type, target_draw, target_date, strategy_id, strategy_name, bet_index, "
                "predicted_numbers, predicted_special, actual_numbers, actual_special, hit_count, special_hit, replay_status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (index, "BIG_LOTTO", f"11300000{index}", date, "alpha", "Alpha strategy", 1, predicted, None, actual, 7, 1, 0, "PREDICTED"),
            )
        connection.commit()
    finally:
        connection.close()
    return path


def _build(db_path: Path, candidate_id: str = "alpha:1") -> tuple[dict[str, object], str]:
    return contract_module.build_packet_from_bytes(
        _raw(_p543b()),
        "synthetic-p543b.json",
        _raw(_p543a(candidate_id)),
        "synthetic-p543a.json",
        _raw({"schema_version": "synthetic"}),
        "synthetic-p542a.json",
        str(db_path),
        GENERATED_AT,
    )


def test_read_only_uri_is_enforced(tmp_path: Path) -> None:
    path = tmp_path / "sample.db"
    uri = contract_module.read_only_uri(str(path))
    assert uri.startswith("file:")
    assert uri.endswith("?mode=ro")
    for invalid in ("file:/tmp/sample.db?mode=rw", "relative.db", "/tmp/sample.txt"):
        with pytest.raises(ValueError):
            contract_module.read_only_uri(invalid)


def test_schema_discovery_and_successful_contract_rows(tmp_path: Path) -> None:
    packet, _ = _build(_temporary_store(tmp_path))
    assert packet["db_access"]["opened_read_only"] is True
    assert packet["contract"]["contract_status"] == "generated"
    rows = packet["contract"]["rows"]
    assert len(rows) == 2
    assert [row["draw_order"] for row in rows] == [1, 2]
    assert rows[0]["candidate_id"] == "alpha:1"
    assert rows[0]["selected_numbers"] == [1, 2, 3]
    assert "strategy_prediction_replays" in packet["schema_inventory"]


def test_blocked_report_when_predictions_are_missing(tmp_path: Path) -> None:
    packet, _ = _build(_temporary_store(tmp_path, predicted=None))
    assert packet["contract"]["contract_status"] == "blocked"
    assert any("predicted numbers missing" in blocker for blocker in packet["contract"]["blockers"])


def test_blocked_report_when_actual_outcomes_are_missing(tmp_path: Path) -> None:
    packet, _ = _build(_temporary_store(tmp_path, actual=None))
    assert packet["contract"]["contract_status"] == "blocked"
    assert any("actual outcomes missing" in blocker for blocker in packet["contract"]["blockers"])


def test_candidate_linkage_blocker_is_precise(tmp_path: Path) -> None:
    packet, _ = _build(_temporary_store(tmp_path), candidate_id="unlinked:1")
    assert packet["contract"]["contract_status"] == "blocked"
    assert packet["contract"]["blockers"] == ["candidate linkage missing: unlinked:1"]


def test_output_is_byte_deterministic(tmp_path: Path) -> None:
    db_path = _temporary_store(tmp_path)
    p543b = tmp_path / "p543b.json"
    p543a = tmp_path / "p543a.json"
    p542a = tmp_path / "p542a.json"
    output_json = tmp_path / "contract.json"
    output_md = tmp_path / "contract.md"
    p543b.write_bytes(_raw(_p543b()))
    p543a.write_bytes(_raw(_p543a()))
    p542a.write_bytes(_raw({"schema_version": "synthetic"}))
    contract_module.generate(p543b, p543a, p542a, str(db_path), output_json, output_md, GENERATED_AT)
    first = (output_json.read_bytes(), output_md.read_bytes())
    contract_module.generate(p543b, p543a, p542a, str(db_path), output_json, output_md, GENERATED_AT)
    assert (output_json.read_bytes(), output_md.read_bytes()) == first


def test_markdown_contains_contract_only_disclaimers(tmp_path: Path) -> None:
    _, markdown = _build(_temporary_store(tmp_path))
    for phrase in ("不執行 walk-forward 或 permutation 驗證", "不預測未來", "不構成投注建議"):
        assert phrase in markdown
    for forbidden in ("guaranteed", "future win-rate", "go-live ready", "production ready"):
        assert forbidden not in markdown.lower()


def test_production_module_has_no_mutating_sql_tokens() -> None:
    source = Path(contract_module.__file__).read_text(encoding="utf-8").lower()
    mutating_statement = r"\\b(in" + "sert|up" + "date|del" + "ete|rep" + "lace|cre" + "ate|dr" + "op|al" + "ter|vac" + "uum)\\s+(table|index|into|from|database)\\b"
    assert re.search(mutating_statement, source) is None
