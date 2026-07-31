"""Synthetic contract tests for the P543A stability packet."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis import p543a_scoreboard_stability_packet as packet_module


GENERATED_AT = "2026-07-10T00:00:00+08:00"


def _ranking_row(window: int, candidate: str, *, section: str) -> dict[str, object]:
    row: dict[str, object] = {
        "lottery_type": "BIG_LOTTO",
        "window": window,
        "support_draws": window,
        "any_main_hit_rate": 0.2,
        "baseline_any_main_rate": 0.15,
        "any_main_hit_edge_pp": 5.0,
        "prize_signal_rate": 0.04,
        "baseline_prize_signal_rate": 0.02,
        "prize_signal_edge_pp": 2.0,
    }
    if section == "strategy":
        row.update({"strategy_id": candidate, "pick_k": 1})
    else:
        row.update({"combo_id": candidate, "requested_budget": 1, "rank_in_bucket": 1})
    return row


def _artifact() -> dict[str, object]:
    strategy = {
        "BIG_LOTTO|50|1": _ranking_row(50, "strategy-alpha", section="strategy"),
        "BIG_LOTTO|300|1": _ranking_row(300, "strategy-alpha", section="strategy"),
        "BIG_LOTTO|750|1": _ranking_row(750, "strategy-beta", section="strategy"),
    }
    combinations = {
        "BIG_LOTTO|50|1": _ranking_row(50, "combo-alpha", section="combination"),
        "BIG_LOTTO|300|1": _ranking_row(300, "combo-alpha", section="combination"),
        "BIG_LOTTO|750|1": _ranking_row(750, "combo-beta", section="combination"),
    }
    zone2 = [
        {
            "scope": "combination",
            "identifier": "zone-alpha",
            "window": window,
            "support_draws": window,
            "zone2_hit_rate": 0.2,
            "random_zone2_hit_rate": 0.125,
            "zone2_hit_edge_pp": 7.5,
            "prize_aware_hit_rate": 0.05,
            "random_prize_aware_hit_rate": 0.02,
            "prize_aware_edge_pp": 3.0,
        }
        for window in (50, 300, 750)
    ]
    return {
        "schema_version": "synthetic-v1",
        "window_policy": {"draw_windows": [50, 300, 750]},
        "descriptive_rankings": {
            "top_strategy_pick_by_lottery_window_pick": strategy,
            "best_combination_by_lottery_window_budget": combinations,
        },
        "combination_leaderboard": list(combinations.values()),
        "power_lotto_zone2_metrics": zone2,
    }


def _packet(artifact: dict[str, object] | None = None) -> tuple[dict[str, object], str]:
    raw = json.dumps(artifact or _artifact(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    return packet_module.build_packet_from_bytes(raw, "synthetic.json", GENERATED_AT, top_n=2)


def test_schema_inspection_and_available_metric_ranking() -> None:
    packet, _ = _packet()
    summary = packet["schema_summary"]
    assert summary["top_level_keys"] == sorted(_artifact())
    assert summary["usable_ranking_sections"][0]["identity_field"] == "strategy_id"
    rows = packet["top_historical_candidates"]
    strategy = next(row for row in rows if row["candidate_id"] == "strategy-alpha")
    assert strategy["evidence"]["prize_signal_edge_pp"] == 2.0
    assert strategy["evidence"]["baseline_any_main_rate"] == 0.15


def test_cross_window_stability_and_single_window_spike_classification() -> None:
    packet, _ = _packet()
    stable = packet["candidate_packet"]["multi_window_stable"]
    spike = packet["candidate_packet"]["single_window_spike"]
    stable_strategy = next(row for row in stable if row["candidate_id"] == "strategy-alpha")
    assert stable_strategy["observed_windows"] == [50, 300]
    assert stable_strategy["window_count"] == 2
    assert any(row["candidate_id"] == "strategy-beta" for row in spike)


def test_unknown_row_is_preserved_without_inference() -> None:
    artifact = _artifact()
    rankings = artifact["descriptive_rankings"]
    rankings["top_strategy_pick_by_lottery_window_pick"]["UNKNOWN|50|1"] = {
        "lottery_type": "UNKNOWN",
        "window": 50,
    }
    packet, _ = _packet(artifact)
    unknown_rows = packet["candidate_packet"]["unknown_or_incomplete"]
    unknown = next(row for row in unknown_rows if row["source_key"] == "UNKNOWN|50|1")
    assert unknown["status"] == "UNKNOWN"
    assert "strategy_id" in unknown["missing_fields"]


def test_output_is_byte_deterministic_for_fixed_inputs(tmp_path: Path) -> None:
    input_path = tmp_path / "synthetic.json"
    output_json = tmp_path / "packet.json"
    output_md = tmp_path / "packet.md"
    input_path.write_text(json.dumps(_artifact(), ensure_ascii=False, sort_keys=True), encoding="utf-8")

    packet_module.generate(input_path, output_json, output_md, GENERATED_AT, top_n=2)
    first = (output_json.read_bytes(), output_md.read_bytes())
    packet_module.generate(input_path, output_json, output_md, GENERATED_AT, top_n=2)
    assert (output_json.read_bytes(), output_md.read_bytes()) == first


def test_markdown_has_safety_and_selection_bias_language() -> None:
    _, markdown = _packet()
    assert "不預測未來" in markdown
    assert "不構成投注建議" in markdown
    assert "選擇偏差" in markdown
    for forbidden in ("guaranteed", "future win-rate", "go-live ready", "production ready"):
        assert forbidden not in markdown.lower()


def test_unsupported_schema_fails_closed() -> None:
    with pytest.raises(packet_module.SchemaError):
        packet_module.build_packet_from_bytes(b'{"unsupported": true}', "synthetic.json", GENERATED_AT)


def test_new_files_do_not_reference_forbidden_runtime_symbols() -> None:
    source = Path(packet_module.__file__).read_text(encoding="utf-8").lower()
    test_source = Path(__file__).read_text(encoding="utf-8").lower()
    forbidden = ("sql" + "ite", "data" + "base" + "manager", "con" + "nect(")
    for token in forbidden:
        assert token not in source
        assert token not in test_source
