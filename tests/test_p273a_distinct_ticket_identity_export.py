"""Focused synthetic tests for the P273A distinct-ticket identity export."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

import pytest

import analysis.p273a_distinct_ticket_identity_export as P
import analysis.p273a_prizeaware_replay_export as B

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "analysis" / "p273a_distinct_ticket_identity_export.py"
SCORER = ROOT / B.P271C_SOURCE_PATH
ADAPTER = ROOT / B.P271E_SOURCE_PATH


def row(
    lottery,
    draw,
    strategy,
    bet_index,
    predicted,
    *,
    predicted_special=None,
    actual=None,
    actual_special=None,
    cutoff=None,
    join_count=1,
):
    if actual is None:
        actual = {
            "DAILY_539": [1, 2, 3, 4, 5],
            "BIG_LOTTO": [1, 2, 3, 4, 5, 6],
            "POWER_LOTTO": [1, 2, 3, 4, 5, 6],
        }[lottery]
    if lottery == "BIG_LOTTO" and actual_special is None:
        actual_special = 49
    if lottery == "POWER_LOTTO" and actual_special is None:
        actual_special = 8
    cutoff = cutoff or str(int(draw) - 1)
    return (
        lottery,
        str(draw),
        strategy,
        bet_index,
        cutoff,
        json.dumps(predicted),
        predicted_special,
        json.dumps(actual),
        actual_special,
        join_count,
    )


def create_db(path: Path, rows):
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE strategy_prediction_replays ("
        "lottery_type TEXT, target_draw TEXT, strategy_id TEXT, "
        "bet_index INTEGER, history_cutoff_draw TEXT, predicted_numbers TEXT, "
        "predicted_special INTEGER, actual_numbers TEXT, actual_special INTEGER, "
        "replay_status TEXT, dry_run INTEGER)"
    )
    conn.execute("CREATE TABLE draws (lottery_type TEXT, draw TEXT)")
    for raw in rows:
        conn.execute(
            "INSERT INTO strategy_prediction_replays "
            "(lottery_type,target_draw,strategy_id,bet_index,history_cutoff_draw,"
            "predicted_numbers,predicted_special,actual_numbers,actual_special,"
            "replay_status,dry_run) VALUES (?,?,?,?,?,?,?,?,?,'PREDICTED',0)",
            raw[:9],
        )
    for lottery, draw in sorted({(raw[0], raw[1]) for raw in rows}):
        conn.execute(
            "INSERT INTO draws (lottery_type,draw) VALUES (?,?)",
            (lottery, draw),
        )
    conn.commit()
    conn.close()


def p267c():
    results = []
    for prefix, lottery, count in (
        ("d", "DAILY_539", 15),
        ("b", "BIG_LOTTO", 11),
        ("p", "POWER_LOTTO", 10),
    ):
        for i in range(count):
            results.append(
                {"lottery_type": lottery, "strategy_id": f"{prefix}{i:02d}"}
            )
    return {"results": results}


def p271a():
    return {
        "endpoint_definitions": {
            lottery: {
                B.GOVERNED_ENDPOINT[lottery]["endpoint_id"]: {
                    "condition_sql": B.GOVERNED_ENDPOINT[lottery][
                        "expected_condition_sql"
                    ]
                }
            }
            for lottery in B.LOTTERY_TYPES
        }
    }


def write_json(path: Path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return str(path)


def build_primary(db_path: str, cells):
    conn, _ = B.open_readonly_connection(db_path)
    try:
        conn.execute("BEGIN")
        output = []
        for cell in cells:
            rows = conn.execute(
                B.CELL_QUERY,
                (cell["lottery_type"], cell["strategy_id"]),
            ).fetchall()
            processed, draws = B._process_rows(rows)
            windows = []
            for window in P.PRIMARY_WINDOWS:
                rec = B.aggregate_window(
                    processed,
                    draws,
                    window,
                    cell["lottery_type"],
                    cell["strategy_id"],
                )
                rec["window_label"] = P.PRIMARY_WINDOW_LABELS[window]
                windows.append(rec)
            output.append(
                {
                    "lottery_type": cell["lottery_type"],
                    "strategy_id": cell["strategy_id"],
                    "distinct_draws_available": len(draws),
                    "windows": windows,
                }
            )
        conn.execute("ROLLBACK")
    finally:
        conn.close()
    result = {"cells": output}
    result["canonical_payload_digest"] = B.compute_payload_digest(result)
    return result


def fixture_bundle(tmp_path, extra_rows=None):
    rows = [
        row("DAILY_539", 1000, "d00", 1, [5, 4, 3, 2, 1]),
        row("DAILY_539", 999, "d00", 1, [6, 7, 8, 9, 10]),
        row("BIG_LOTTO", 800, "b00", 1, [1, 2, 3, 4, 5, 10]),
        row(
            "POWER_LOTTO",
            700,
            "p00",
            1,
            [1, 2, 3, 4, 5, 10],
            predicted_special=3,
        ),
        row(
            "POWER_LOTTO",
            699,
            "p00",
            1,
            [1, 2, 3, 4, 5, 11],
            predicted_special=None,
        ),
    ]
    rows.extend(extra_rows or [])
    db = tmp_path / "synthetic.db"
    create_db(db, rows)
    p267 = p267c()
    cells = B.load_frozen_cells(write_json(tmp_path / "p267c.json", p267))
    primary = build_primary(str(db), cells)
    primary_path = tmp_path / "primary.json"
    write_json(primary_path, primary)
    reference = {"reference_only": True}
    reference["canonical_payload_digest"] = B.compute_payload_digest(reference)
    reference_path = tmp_path / "reference.json"
    write_json(reference_path, reference)
    p271_path = tmp_path / "p271a.json"
    write_json(p271_path, p271a())
    return {
        "db": str(db),
        "p267c": str(tmp_path / "p267c.json"),
        "p271a": str(p271_path),
        "primary": str(primary_path),
        "primary_raw": hashlib.sha256(primary_path.read_bytes()).hexdigest(),
        "primary_canonical": primary["canonical_payload_digest"],
        "reference": str(reference_path),
        "reference_raw": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
        "reference_canonical": reference["canonical_payload_digest"],
    }


def run_bundle(bundle):
    return P.run_export(
        db_path=bundle["db"],
        primary_path=bundle["primary"],
        reference_path=bundle["reference"],
        p267c_path=bundle["p267c"],
        p271a_path=bundle["p271a"],
        scorer_path=str(SCORER),
        adapter_path=str(ADAPTER),
        primary_expected_raw=bundle["primary_raw"],
        primary_expected_canonical=bundle["primary_canonical"],
        reference_expected_raw=bundle["reference_raw"],
        reference_expected_canonical=bundle["reference_canonical"],
    )


def eligible_dict(raw):
    return B._row_dict(raw)


def test_frozen_scope():
    assert P.PRIMARY_WINDOWS == (50, 300, 750)
    assert P.CORRECTION_FAMILY_PLANNED == 108
    cells = B.load_frozen_cells(
        str(ROOT / B.P267C_JSON_PATH)
    )
    assert len(cells) == 36
    assert Counter(c["lottery_type"] for c in cells) == {
        "DAILY_539": 15,
        "BIG_LOTTO": 11,
        "POWER_LOTTO": 10,
    }


def test_daily539_normalization_and_sorting():
    ident = P.normalize_ticket_identity(
        eligible_dict(
            row("DAILY_539", 1000, "d", 1, [9, 1, 8, 2, 7])
        )
    )
    assert ident["canonical_ticket_content"] == {
        "main_numbers": [1, 2, 7, 8, 9]
    }


def test_big_identity_excludes_drawn_special():
    first = eligible_dict(
        row(
            "BIG_LOTTO",
            1000,
            "b",
            1,
            [9, 1, 8, 2, 7, 3],
            actual_special=49,
        )
    )
    second = dict(first, actual_special=48)
    assert P.normalize_ticket_identity(first) == P.normalize_ticket_identity(
        second
    )


def test_power_identity_includes_predicted_second_zone():
    raw = row(
        "POWER_LOTTO",
        1000,
        "p",
        1,
        [9, 1, 8, 2, 7, 3],
        predicted_special=4,
    )
    ident = P.normalize_ticket_identity(eligible_dict(raw))
    assert ident["canonical_ticket_content"] == {
        "main_numbers": [1, 2, 3, 7, 8, 9],
        "predicted_second_zone": 4,
    }


@pytest.mark.parametrize(
    "predicted",
    ([1, 1, 2, 3, 4], [0, 1, 2, 3, 4], [1, 2, 3, 4, 40]),
)
def test_duplicate_or_range_invalid_numbers_rejected(predicted):
    raw = eligible_dict(row("DAILY_539", 1000, "d", 1, predicted))
    with pytest.raises(P.TicketContentError):
        P.normalize_ticket_identity(raw)


def test_power_missing_special_excluded():
    raw = eligible_dict(
        row(
            "POWER_LOTTO",
            1000,
            "p",
            1,
            [1, 2, 3, 4, 5, 6],
            predicted_special=None,
        )
    )
    with pytest.raises(P.TicketContentError, match="MISSING"):
        P.normalize_ticket_identity(raw)


def test_same_bet_index_identical_rows_collapse():
    raw = row("DAILY_539", 1000, "d", 1, [1, 2, 3, 4, 5])
    processed = P.process_cell_rows([raw, raw], "DAILY_539", "d")
    draw = processed["draw_summaries"]["1000"]
    assert draw["eligible_bet_index_count"] == 1
    assert draw["distinct_ticket_count"] == 1
    assert processed["same_bet_index_duplicate_rows_collapsed"] == 1


def test_same_bet_index_conflicting_contents_stop():
    rows = [
        row("DAILY_539", 1000, "d", 1, [1, 2, 3, 4, 5]),
        row("DAILY_539", 1000, "d", 1, [1, 2, 3, 4, 6]),
    ]
    with pytest.raises(P.BetIndexContentConflict):
        P.process_cell_rows(rows, "DAILY_539", "d")


def test_cross_bet_index_identical_contents_deduplicate():
    rows = [
        row("DAILY_539", 1000, "d", 1, [1, 2, 3, 4, 5]),
        row("DAILY_539", 1000, "d", 2, [5, 4, 3, 2, 1]),
    ]
    draw = P.process_cell_rows(rows, "DAILY_539", "d")[
        "draw_summaries"
    ]["1000"]
    assert draw["eligible_bet_index_count"] == 2
    assert draw["distinct_ticket_count"] == 1
    assert draw["duplicate_ticket_count"] == 1
    assert draw["canonical_ticket_groups"][0]["bet_index_values"] == [1, 2]
    assert draw["canonical_ticket_groups"][0]["group_multiplicity"] == 2


def test_different_contents_remain_distinct():
    rows = [
        row("DAILY_539", 1000, "d", 1, [1, 2, 3, 4, 5]),
        row("DAILY_539", 1000, "d", 2, [1, 2, 3, 4, 6]),
    ]
    draw = P.process_cell_rows(rows, "DAILY_539", "d")[
        "draw_summaries"
    ]["1000"]
    assert draw["eligible_bet_index_count"] == 2
    assert draw["distinct_ticket_count"] == 2
    assert draw["duplicate_ticket_count"] == 0


def test_fingerprint_deterministic():
    a = {"main_numbers": [1, 2, 3, 4, 5]}
    b = {"main_numbers": [1, 2, 3, 4, 5]}
    assert P.canonical_ticket_fingerprint(a) == P.canonical_ticket_fingerprint(
        b
    )
    assert len(P.canonical_ticket_fingerprint(a)) == 64


def test_integer_draw_order_and_primary_selection():
    rows = [
        row("DAILY_539", draw, "d", 1, [1, 2, 3, 4, 5])
        for draw in ("9", "10", "200", "1000")
    ]
    rows.sort(key=lambda raw: int(raw[1]), reverse=True)
    processed = P.process_cell_rows(rows, "DAILY_539", "d")
    assert processed["distinct_draws_desc"] == ["1000", "200", "10", "9"]
    win = P.aggregate_identity_window(
        processed, 50, "DAILY_539", "d"
    )
    assert win["latest_target_draw"] == "1000"
    assert win["earliest_target_draw"] == "9"


def test_window_duplicate_arithmetic():
    rows = [
        row("DAILY_539", 1000, "d", 1, [1, 2, 3, 4, 5]),
        row("DAILY_539", 1000, "d", 2, [5, 4, 3, 2, 1]),
        row("DAILY_539", 999, "d", 1, [1, 2, 3, 4, 6]),
    ]
    processed = P.process_cell_rows(rows, "DAILY_539", "d")
    win = P.aggregate_identity_window(
        processed, 50, "DAILY_539", "d"
    )
    assert win["eligible_bet_index_count_distribution"] == {"1": 1, "2": 1}
    assert win["distinct_ticket_count_distribution"] == {"1": 2}
    assert win["duplicate_content_draw_count"] == 1
    assert win["total_duplicate_ticket_content_count"] == 1


def test_source_artifact_raw_and_canonical_checks(tmp_path):
    artifact = {"value": 1}
    artifact["canonical_payload_digest"] = B.compute_payload_digest(artifact)
    path = tmp_path / "artifact.json"
    write_json(path, artifact)
    raw = hashlib.sha256(path.read_bytes()).hexdigest()
    verified = P.verify_source_artifact(
        str(path), raw, artifact["canonical_payload_digest"]
    )
    assert verified["raw_sha256"] == raw
    with pytest.raises(P.IdentityExportError):
        P.verify_source_artifact(
            str(path), "0" * 64, artifact["canonical_payload_digest"]
        )


def test_e2e_alignment_and_safety(tmp_path):
    result = run_bundle(fixture_bundle(tmp_path))
    assert len(result["cells"]) == 36
    assert result["summary"]["artifact_alignment_status"] == "PASS"
    assert result["summary"]["artifact_alignment_windows_checked"] == 108
    assert set(result["provenance"]["source_paths"]) == {
        "identity_export_source",
        "primary_export_source",
        "replay_export_source",
        "p267c_json",
        "p271a_json",
        "p271c_scorer",
        "p271e_adapter",
    }
    assert set(result["summary"]["distinct_ticket_count_distribution_by_window"]) == {
        "50",
        "300",
        "750",
    }
    assert result["safety_flags"]["production_write"] is False
    assert result["safety_flags"]["inference_performed"] is False
    assert result["safety_flags"]["baseline_computed"] is False
    assert result["safety_flags"]["p_value_computed"] is False


def test_e2e_cross_index_duplicates_recorded(tmp_path):
    extras = [
        row("DAILY_539", 1000, "d00", 2, [1, 2, 3, 4, 5])
    ]
    bundle = fixture_bundle(tmp_path, extras)
    # Build the immutable synthetic observed source with the extra bet index,
    # then the identity export must align while recording one content duplicate.
    result = run_bundle(bundle)
    cell = next(
        c
        for c in result["cells"]
        if c["lottery_type"] == "DAILY_539"
        and c["strategy_id"] == "d00"
    )
    draw = next(d for d in cell["supported_draws"] if d["target_draw"] == "1000")
    assert draw["eligible_bet_index_count"] == 2
    assert draw["distinct_ticket_count"] == 1
    assert draw["duplicate_ticket_count"] == 1


def test_alignment_failure_stops(tmp_path):
    bundle = fixture_bundle(tmp_path)
    artifact = json.loads(Path(bundle["primary"]).read_text(encoding="utf-8"))
    artifact["cells"][0]["windows"][0]["support_draws"] += 1
    artifact["canonical_payload_digest"] = B.compute_payload_digest(artifact)
    write_json(Path(bundle["primary"]), artifact)
    bundle["primary_raw"] = hashlib.sha256(
        Path(bundle["primary"]).read_bytes()
    ).hexdigest()
    bundle["primary_canonical"] = artifact["canonical_payload_digest"]
    with pytest.raises(P.IdentityArtifactAlignmentError):
        run_bundle(bundle)


def test_one_connection_one_snapshot(tmp_path, monkeypatch):
    bundle = fixture_bundle(tmp_path)
    calls = []
    real = P.open_readonly_connection

    def spy(path):
        calls.append(path)
        return real(path)

    monkeypatch.setattr(P, "open_readonly_connection", spy)
    result = run_bundle(bundle)
    assert calls == [bundle["db"]]
    assert result["provenance"]["single_connection"] is True
    assert result["provenance"]["single_snapshot"] is True
    assert result["provenance"]["query_only_evidence"][
        "query_only_pragma_value"
    ] == 1


def test_mode_ro_rejects_write(tmp_path):
    bundle = fixture_bundle(tmp_path)
    conn, evidence = P.open_readonly_connection(bundle["db"])
    try:
        assert evidence["mode_ro"] is True
        assert evidence["query_only_enabled"] is True
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM draws")
    finally:
        conn.close()


def test_deterministic_payload_and_markdown(tmp_path):
    bundle = fixture_bundle(tmp_path)
    first = run_bundle(bundle)
    second = run_bundle(bundle)
    assert first["canonical_payload_digest"] == second[
        "canonical_payload_digest"
    ]
    assert P.render_markdown(first) == P.render_markdown(second)


def test_json_markdown_consistency(tmp_path):
    result = run_bundle(fixture_bundle(tmp_path))
    md = P.render_markdown(result)
    assert result["canonical_payload_digest"] in md
    assert result["final_classification"] in md
    assert "108" in md
    assert "50" in md and "300" in md and "750" in md


def collect_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from collect_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from collect_keys(child)


def test_no_inference_result_fields(tmp_path):
    result = run_bundle(fixture_bundle(tmp_path))
    keys = set(collect_keys(result["cells"]))
    forbidden = {
        "expected_successes",
        "confidence_interval",
        "raw_p_value",
        "bonferroni_p_value",
        "bh_fdr",
        "stability_decision",
        "edge_decision",
        "go_recommendation",
    }
    assert keys.isdisjoint(forbidden)


def test_static_forbidden_sql_and_interfaces():
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    literals = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    forbidden_sql = re.compile(
        r"\b(INSERT|UPDATE|DELETE|REPLACE|CREATE|ALTER|DROP|VACUUM|"
        r"REINDEX|ATTACH|DETACH)\b",
        re.IGNORECASE,
    )
    for literal in literals:
        if re.search(r"\b(SELECT|PRAGMA|BEGIN|ROLLBACK|FROM)\b", literal):
            assert not forbidden_sql.search(literal)
    for banned in (
        "import subprocess",
        "import socket",
        "import requests",
        "launchctl",
        "Popen(",
        ".commit(",
        ".executemany(",
        "hypothesis_registry",
        "os.remove(",
    ):
        assert banned not in source


def test_query_names_only_permitted_tables():
    assert "SELECT *" not in P.CELL_QUERY.upper()
    assert "strategy_prediction_replays" in P.CELL_QUERY
    assert "draws" in P.CELL_QUERY
    assert P.PRODUCTION_DB_PATH not in Path(__file__).read_text(encoding="utf-8")
