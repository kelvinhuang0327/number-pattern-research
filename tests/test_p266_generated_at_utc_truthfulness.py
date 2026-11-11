"""P266 truthful generated_at_utc contract tests."""
from __future__ import annotations

import importlib
import inspect
from datetime import datetime, timezone
from pathlib import Path

from wbc_backend.recommendation import paper_strategy_learning as learning
from wbc_backend.recommendation import paper_strategy_workflow as workflow


ROOT = Path(__file__).resolve().parents[1]
FIXED_FIRST = "2026-07-10T01:02:03Z"
FIXED_SECOND = "2026-07-10T04:05:06Z"

GENERATOR_FUNCTIONS = {
    "paper_artifact_catalog": ("build_paper_artifact_catalog",),
    "paper_artifact_catalog_diff": ("diff_paper_artifact_catalogs",),
    "paper_artifact_catalog_query": ("query_paper_artifact_catalog",),
    "paper_artifact_diff_gate": ("gate_paper_artifact_diff",),
    "paper_strategy_workflow": ("run_paper_strategy_workflow",),
    "paper_strategy_workflow_bundle": (
        "run_paper_strategy_workflow_bundle",
        "run_bundle_or_raise",
    ),
    "paper_strategy_workflow_inspector": ("inspect_paper_strategy_workflow",),
    "paper_strategy_workflow_review_pack": ("build_paper_strategy_workflow_review_pack",),
    "paper_toolchain_cli_help": ("build_paper_toolchain_cli_help",),
    "paper_toolchain_dashboard": ("build_paper_toolchain_dashboard",),
    "paper_toolchain_index": ("build_paper_toolchain_index",),
    "paper_toolchain_operator_pack": ("build_paper_toolchain_operator_pack",),
    "paper_toolchain_pack_integrity": ("build_paper_toolchain_pack_integrity",),
    "paper_toolchain_quickstart": ("build_paper_toolchain_quickstart",),
    "paper_toolchain_status": ("build_paper_toolchain_status",),
}


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo == timezone.utc
    return parsed


def _fixture_source(path: Path) -> None:
    path.write_text(
        "game_id,game_date,home_team,away_team,line_value,model_name,"
        "predicted_home_probability,predicted_side,predicted_side_probability,actual_side,correct\n"
        "g1,2025-07-01,Home,Away,-1.5,fixture,0.7,HOME,0.7,HOME,1\n",
        encoding="utf-8",
    )


def test_default_timestamp_is_current_timezone_aware_utc():
    before = datetime.now(timezone.utc).replace(microsecond=0)
    generated = learning.resolve_generated_at_utc()
    after = datetime.now(timezone.utc).replace(microsecond=0)

    parsed = _utc(generated)
    assert generated.endswith("Z")
    assert before <= parsed <= after
    assert generated not in {"2026-07-08T00:00:00Z", "2026-07-09T00:00:00Z"}


def test_explicit_timestamp_is_preserved_and_two_payloads_only_differ_in_time():
    decision = learning.PaperDecision(
        game_id="g1",
        game_date="2025-07-01",
        predicted_side="HOME",
        confidence=0.7,
        correct=1,
        stake_units=1.0,
    )
    dataset = learning.PaperLearningDataset(
        decisions=(decision,),
        source_csv="fixture.csv",
        source_sha256="fixture-sha",
    )

    first, first_segments = learning.build_output_payload(
        dataset, generated_at_utc=FIXED_FIRST
    )
    second, second_segments = learning.build_output_payload(
        dataset, generated_at_utc=FIXED_SECOND
    )

    assert first["generated_at_utc"] == FIXED_FIRST
    assert second["generated_at_utc"] == FIXED_SECOND
    first_without_time = {key: value for key, value in first.items() if key != "generated_at_utc"}
    second_without_time = {key: value for key, value in second.items() if key != "generated_at_utc"}
    assert first_without_time == second_without_time
    assert first_segments == second_segments


def test_production_defaults_are_runtime_resolved_not_import_time_constants():
    for module_name, function_names in GENERATOR_FUNCTIONS.items():
        module = importlib.import_module(f"wbc_backend.recommendation.{module_name}")
        assert module.DEFAULT_GENERATED_AT_UTC is None
        source = inspect.getsource(module)
        assert "resolve_generated_at_utc" in source
        for function_name in function_names:
            parameter = inspect.signature(getattr(module, function_name)).parameters[
                "generated_at_utc"
            ]
            assert parameter.default is None


def test_workflow_default_emits_generation_time_without_changing_schema(tmp_path):
    source = tmp_path / "source.csv"
    _fixture_source(source)
    result = workflow.run_paper_strategy_workflow(
        source_csv=source,
        output_dir=tmp_path / "workflow",
        thresholds=(0.5, 0.7),
    )

    generated = result.summary["generated_at_utc"]
    parsed = _utc(generated)
    assert generated.endswith("Z")
    assert parsed <= datetime.now(timezone.utc)
    assert result.manifest["generated_at_utc"] == generated
    assert result.summary["workflow_status"] == "RESULT_ONLY_PAPER_WORKFLOW"
    assert set(result.summary) >= {"source_csv", "generated_at_utc", "workflow_status"}
