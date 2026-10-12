"""Synthetic contract tests for the P543B feasibility packet."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from analysis import p543b_scoreboard_validation_feasibility_pilot as packet_module


GENERATED_AT = "2026-07-10T00:00:00+08:00"


def _candidate(candidate_id: str, *, lottery: str = "BIG_LOTTO", section: str = "combination") -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "lottery": lottery,
        "section": section,
        "bucket": 1,
        "observed_windows": [50, 300],
    }


def _p543a() -> dict[str, object]:
    return {
        "candidate_packet": {
            "multi_window_stable": [_candidate("alpha")],
            "single_window_spike": [_candidate("spike")],
            "prize_or_zone2_signal": [_candidate("zone", lottery="POWER_LOTTO", section="power_lotto_zone2_metrics")],
            "unknown_or_incomplete": [{"source_key": "unknown-row"}],
            "not_comparable": [{"lottery": "BIG_LOTTO", "section": "combination"}],
        }
    }


def _p542a(rows: list[dict[str, object]] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "strategy_pick_matrix": [],
        "combination_leaderboard": [],
        "power_lotto_zone2_metrics": [],
        "window_policy": {"draw_windows": [50, 300, 750]},
    }
    if rows is not None:
        payload["per_draw_validation_rows"] = rows
    return payload


def _build(p542a: dict[str, object], seed: int = 17) -> tuple[dict[str, object], str]:
    p543_raw = json.dumps(_p543a(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    p542_raw = json.dumps(p542a, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return packet_module.build_packet_from_bytes(
        p543_raw,
        "synthetic-p543a.json",
        p542_raw,
        "synthetic-p542a.json",
        GENERATED_AT,
        top_n=10,
        seed=seed,
    )


def _result(packet: dict[str, object], candidate_id: str) -> dict[str, object]:
    return next(row for row in packet["candidate_feasibility"] if row["candidate_id"] == candidate_id)


def test_source_hash_and_byte_metadata_are_recorded() -> None:
    packet, _ = _build(_p542a())
    sources = packet["source_artifacts"]
    expected = json.dumps(_p543a(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    assert sources[0]["sha256"] == hashlib.sha256(expected).hexdigest()
    assert sources[0]["bytes"] == len(expected)
    assert sources[1]["path"] == "synthetic-p542a.json"


def test_aggregate_only_input_is_blocked_without_fabricated_pilot() -> None:
    packet, _ = _build(_p542a())
    alpha = _result(packet, "alpha")
    assert alpha["overall_status"] == "aggregate_only_not_validatable"
    assert "blocked_missing_per_draw_predictions" in alpha["blockers"]
    assert "blocked_missing_actual_draw_outcomes" in alpha["blockers"]
    assert packet["pilot"]["computed"] is False


def test_missing_per_draw_predictions_are_explicit() -> None:
    packet, _ = _build(
        _p542a([{"candidate_id": "alpha", "draw_id": 1, "window": 50, "actual_numbers": [1, 2]}])
    )
    alpha = _result(packet, "alpha")
    assert alpha["walk_forward_status"] == "blocked_missing_per_draw_predictions"
    assert "blocked_missing_per_draw_predictions" in alpha["blockers"]


def test_missing_actual_outcomes_are_explicit() -> None:
    packet, _ = _build(
        _p542a([{"candidate_id": "alpha", "draw_id": 1, "window": 50, "predicted_numbers": [1, 2]}])
    )
    alpha = _result(packet, "alpha")
    assert alpha["permutation_status"] == "blocked_missing_actual_draw_outcomes"
    assert "blocked_missing_actual_draw_outcomes" in alpha["blockers"]


def test_fixed_seed_pilot_is_deterministic_when_explicit_rows_exist() -> None:
    rows = [
        {"candidate_id": "alpha", "draw_id": draw_id, "window": 50, "predicted_numbers": [draw_id], "actual_numbers": [draw_id, 9]}
        for draw_id in range(1, 5)
    ]
    first, _ = _build(_p542a(rows), seed=17)
    second, _ = _build(_p542a(rows), seed=17)
    assert first["pilot"]["computed"] is True
    assert first["pilot"]["seed"] == 17
    assert first["pilot"] == second["pilot"]


def test_generated_files_are_byte_deterministic(tmp_path: Path) -> None:
    p543_path = tmp_path / "p543a.json"
    p542_path = tmp_path / "p542a.json"
    output_json = tmp_path / "packet.json"
    output_md = tmp_path / "packet.md"
    p543_path.write_text(json.dumps(_p543a(), ensure_ascii=False, sort_keys=True), encoding="utf-8")
    p542_path.write_text(json.dumps(_p542a(), ensure_ascii=False, sort_keys=True), encoding="utf-8")
    packet_module.generate(p543_path, p542_path, output_json, output_md, GENERATED_AT, seed=17)
    first = (output_json.read_bytes(), output_md.read_bytes())
    packet_module.generate(p543_path, p542_path, output_json, output_md, GENERATED_AT, seed=17)
    assert (output_json.read_bytes(), output_md.read_bytes()) == first


def test_unknown_rows_fail_closed() -> None:
    packet, _ = _build(_p542a())
    unknown = next(row for row in packet["candidate_feasibility"] if row["candidate_class"] == "unknown_or_incomplete")
    assert unknown["overall_status"] == "unsupported"
    assert unknown["blockers"] == ["unknown_or_incomplete"]


def test_markdown_has_disclaimers_without_forbidden_claims() -> None:
    _, markdown = _build(_p542a())
    for phrase in ("不預測未來", "不構成投注建議", "P543B 僅為 feasibility / pilot"):
        assert phrase in markdown
    for forbidden in ("guaranteed", "future win-rate", "go-live ready", "production ready"):
        assert forbidden not in markdown.lower()


def test_new_files_do_not_reference_forbidden_runtime_symbols() -> None:
    source = Path(packet_module.__file__).read_text(encoding="utf-8").lower()
    test_source = Path(__file__).read_text(encoding="utf-8").lower()
    forbidden = ("sql" + "ite", "data" + "base" + "manager", "con" + "nect(")
    for token in forbidden:
        assert token not in source
        assert token not in test_source
