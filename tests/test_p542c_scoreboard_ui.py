"""Static contract tests for the P542C read-only scoreboard panel."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX = REPO_ROOT / "index.html"


def _p542c_block() -> str:
    source = INDEX.read_text(encoding="utf-8")
    start = source.index("// ===== P542C STRATEGY PICK / COMBINATION SCOREBOARD")
    end = source.index("// ===== P536E STRATEGY LIFT EXTENSION", start)
    return source[start:end]


def test_panel_has_scoreboard_label_and_p542b_endpoint() -> None:
    source = INDEX.read_text(encoding="utf-8")
    block = _p542c_block()

    assert "Strategy Pick / Combination Scoreboard" in source
    assert "p542c-refresh-btn" in source
    assert "fetch(base + '/api/research/p542a/scoreboard')" in block
    assert "/api/replay/strategy-pick-scoreboard" not in block


def test_panel_renders_artifact_metadata_and_descriptive_metrics() -> None:
    source = INDEX.read_text(encoding="utf-8")
    block = _p542c_block()

    for marker in (
        "p542c-artifact-metadata",
        "artifact_sha256",
        "artifact_bytes",
        "random_zone2_hit_rate",
        "baseline_prize_signal_rate",
        "power_lotto_zone2_metrics",
    ):
        assert marker in source or marker in block


def test_panel_fails_closed_with_loading_error_and_unknown_states() -> None:
    source = INDEX.read_text(encoding="utf-8")
    block = _p542c_block()

    assert 'id="p542c-loading"' in source
    assert 'id="p542c-error"' in source
    assert "payload.ok !== true" in block
    assert "payload.descriptive_only !== true" in block
    assert "setFallback()" in block
    assert "UNKNOWN" in block


def test_p542c_block_has_no_positive_future_or_action_claims() -> None:
    block = _p542c_block().lower()
    for phrase in ("guaranteed", "winning odds", "go-live ready", "production ready"):
        assert phrase not in block
    assert "not represent" not in block


def test_p542c_changes_have_no_data_store_dependency() -> None:
    block = _p542c_block().lower()
    test_source = Path(__file__).read_text(encoding="utf-8").lower()
    forbidden = ("sql" + "ite3", "database" + "manager", "con" + "nect(")
    for token in forbidden:
        assert token not in block
        assert token not in test_source
