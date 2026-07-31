"""Synthetic JSON-only tests for the P543D descriptive pilot."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from analysis import p543d_contract_validation_pilot as pilot


GENERATED_AT = "2026-07-10T00:00:00+08:00"


def _row(candidate_id: str, strategy_id: str, order: int, selected: list[int], actual: list[int]) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "candidate_label": candidate_id,
        "lottery": "SYNTHETIC",
        "strategy_ids": [strategy_id],
        "draw_order": order,
        "draw_id": f"D{order:03d}",
        "draw_date": f"2026/01/{order:02d}",
        "selected_numbers": selected,
        "actual_numbers": actual,
        "hit_count": len(set(selected) & set(actual)),
        "special_selected": None,
        "special_actual": None,
        "zone2_selected": None,
        "zone2_actual": None,
    }


def _contract() -> dict[str, object]:
    rows = [
        _row("alpha:1", "alpha", 1, [1, 2], [1, 7]),
        _row("alpha:1", "alpha", 2, [1, 2], [2, 8]),
        _row("alpha:1", "alpha", 3, [1, 2], [7, 8]),
        _row("alpha:1", "alpha", 4, [1, 2], [7, 8]),
        _row("beta:1", "beta", 1, [3, 4], [3, 8]),
        _row("beta:1", "beta", 2, [3, 4], [7, 8]),
        _row("beta:1", "beta", 3, [3, 4], [4, 9]),
        _row("beta:1", "beta", 4, [3, 4], [7, 9]),
    ]
    return {
        "candidate_subset": [
            {"candidate_id": "alpha:1", "strategy_id": "alpha", "bet_index": 1, "lottery": "SYNTHETIC"},
            {"candidate_id": "beta:1", "strategy_id": "beta", "bet_index": 1, "lottery": "SYNTHETIC"},
        ],
        "contract": {"contract_status": "generated", "rows": rows},
    }


def _raw(value: dict[str, object]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")


def _build(*, seed: int = 31, permutations: int = 40) -> tuple[dict[str, object], str]:
    return pilot.build_pilot_from_bytes(_raw(_contract()), "synthetic-p543c.json", GENERATED_AT, seed=seed, permutations=permutations)


def test_schema_metrics_and_chronological_split() -> None:
    packet, _ = _build()
    assert packet["contract_shape"]["candidate_count"] == 2
    assert packet["contract_shape"]["row_count"] == 8
    alpha = next(item for item in packet["candidate_results"] if item["candidate_id"] == "alpha:1")
    assert alpha["metrics"]["hit_count_distribution"] == {"0": 2, "1": 2}
    assert alpha["metrics"]["at_least_one_hit_rate"] == 0.5
    assert alpha["metrics"]["average_hit_count"] == 0.5
    assert alpha["chronological_split"]["first_half_at_least_one_hit_rate"] == 1.0
    assert alpha["chronological_split"]["second_half_at_least_one_hit_rate"] == 0.0
    assert alpha["chronological_split"]["stability_label"] == "late_drop"


def test_fixed_seed_permutations_are_deterministic() -> None:
    first, _ = _build(seed=17, permutations=60)
    second, _ = _build(seed=17, permutations=60)
    assert first == second
    assert first["candidate_results"][0]["permutation_baseline"]["permutations"] == 60


def test_candidate_classification_labels_are_evidence_based() -> None:
    metric = {"row_count": 50, "at_least_one_hit_rate": 0.5}
    split = {"stability_label": "stable_descriptive", "absolute_delta": 0.02}
    baseline = {"at_least_one_hit_rate": {"empirical_percentile": 0.95, "distribution": {"mean": 0.3}}}
    assert pilot.classify_candidate(metric, split, baseline)["label"] == "pilot_above_permutation_baseline"
    assert pilot.classify_candidate(metric, {"stability_label": "late_drop", "absolute_delta": 0.3}, baseline)["label"] == "chronologically_unstable"
    assert pilot.classify_candidate({"row_count": 3, "at_least_one_hit_rate": 0.5}, split, baseline)["label"] == "insufficient_or_unsupported"


def test_ambiguous_contract_fails_closed() -> None:
    broken = _contract()
    del broken["contract"]["rows"][0]["actual_numbers"]
    with pytest.raises(pilot.ContractSchemaError, match="missing required fields"):
        pilot.build_pilot_from_bytes(_raw(broken), "broken.json", GENERATED_AT)


def test_generate_is_byte_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "contract.json"
    first_json = tmp_path / "first.json"
    first_md = tmp_path / "first.md"
    second_json = tmp_path / "second.json"
    second_md = tmp_path / "second.md"
    source.write_bytes(_raw(_contract()))
    pilot.generate(source, first_json, first_md, GENERATED_AT, seed=7, permutations=30)
    pilot.generate(source, second_json, second_md, GENERATED_AT, seed=7, permutations=30)
    assert first_json.read_bytes() == second_json.read_bytes()
    assert first_md.read_bytes() == second_md.read_bytes()


def test_markdown_contains_pilot_only_disclaimers_without_positive_claims() -> None:
    _, markdown = _build()
    for phrase in ("Descriptive-only and pilot-only", "not betting advice", "no future prediction", "No true OOS", "production or go-live readiness", "selection bias remains"):
        assert phrase in markdown
    for forbidden in ("future win-rate", "betting usefulness", "production-ready", "go-live-ready", "validation success"):
        assert forbidden not in markdown.lower()


def test_new_sources_have_no_data_engine_import_or_connection_symbols() -> None:
    source = Path(pilot.__file__).read_text(encoding="utf-8").lower()
    test_source = Path(__file__).read_text(encoding="utf-8").lower()
    for text in (source, test_source):
        assert "sql" + "ite" not in text
        assert re.search(r"import\\s+sql" + "ite", text) is None
        assert re.search(r"\\.con" + "nect\\s*\\(", text) is None
