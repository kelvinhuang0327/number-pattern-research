"""
Tests for P275B — Unified Prize-Aware Success Matrix.

Coverage maps 1:1 to the task's Required Tests:
  * supported-lottery matrix construction
  * strategy and lifecycle preservation
  * 50 / 300 / 750 window handling
  * bet_index / bet_count / ticket_count separation
  * DAILY_539 M2+ scoring
  * BIG_LOTTO special-number scoring
  * POWER_LOTTO second-zone scoring
  * POWER missing predicted second-zone exclusion
  * missing rows never counted as losses
  * baseline calculation
  * confidence intervals (Wilson + Clopper-Pearson, independently re-derived)
  * Bonferroni family size and corrected values
  * deterministic ordering
  * canonical digest reproducibility
  * JSON and Markdown consistency
  * no write-path invocation
"""

from __future__ import annotations

import builtins
import importlib.util
import json
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "analysis" / "p275b_unified_prize_aware_success_matrix.py"

spec = importlib.util.spec_from_file_location("p275b_matrix", _MODULE_PATH)
p275b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p275b)

PINNED_AT = "2026-06-16T00:00:00+00:00"


@pytest.fixture(scope="module")
def artifact():
    return p275b.build_artifact(generated_at=PINNED_AT)


@pytest.fixture(scope="module")
def rows(artifact):
    return artifact["matrix_rows"]


def _row(rows, lottery, strategy, window_type):
    for r in rows:
        if (r["lottery_type"] == lottery and r["strategy_id"] == strategy
                and r["window_type"] == window_type):
            return r
    raise AssertionError(f"row not found: {lottery}/{strategy}/{window_type}")


# --------------------------------------------------------------------------- #
# Supported-lottery matrix construction                                       #
# --------------------------------------------------------------------------- #

def test_supported_lottery_matrix_construction(artifact, rows):
    s = artifact["matrix_summary"]
    assert s["supported_lotteries"] == ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO"]
    assert s["frozen_cells"] == 36
    assert s["total_rows"] == 108
    assert len(rows) == 108
    assert s["cells_by_lottery"] == {"BIG_LOTTO": 11, "DAILY_539": 15, "POWER_LOTTO": 10}
    # each cell appears for exactly the three primary windows
    cells = {(r["lottery_type"], r["strategy_id"]) for r in rows}
    assert len(cells) == 36
    for lottery, strategy in cells:
        wins = sorted(r["window_draw_count"] for r in rows
                      if r["lottery_type"] == lottery and r["strategy_id"] == strategy)
        assert wins == [50, 300, 750]


def test_retrospective_and_no_future_claim(artifact):
    assert artifact["retrospective_research_only"] is True
    assert artifact["prediction_success_claim"] is False
    assert artifact["performs_strategy_combination_search"] is False
    assert all(r["evaluation_mode"] == "RETROSPECTIVE" for r in artifact["matrix_rows"])


# --------------------------------------------------------------------------- #
# Strategy and lifecycle preservation                                         #
# --------------------------------------------------------------------------- #

def test_strategy_and_lifecycle_preservation(artifact, rows):
    s = artifact["matrix_summary"]
    # All registered lifecycle states are preserved and visible — nothing dropped.
    counts = s["lifecycle_status_counts"]
    assert counts.get("ONLINE") == 8
    assert counts.get("REJECTED") == 12
    assert counts.get("RETIRED") == 13
    # Cells absent from the canonical lifecycle registry are kept with an
    # explicit non-fabricated sentinel (never silently removed).
    assert counts.get(p275b.LIFECYCLE_SENTINEL) == 3
    assert sum(counts.values()) == 36

    # Spot-check authoritative, lottery-scoped lifecycle/version values.
    assert _row(rows, "DAILY_539", "acb_1bet", "MID")["lifecycle_status"] == "RETIRED"
    assert _row(rows, "DAILY_539", "539_3bet_orthogonal", "MID")["lifecycle_status"] == "REJECTED"
    assert _row(rows, "DAILY_539", "daily539_f4cold", "MID")["lifecycle_status"] == "ONLINE"
    assert _row(rows, "BIG_LOTTO", "ts3_regime_3bet", "MID")["lifecycle_status"] == "ONLINE"
    online = _row(rows, "DAILY_539", "daily539_f4cold", "MID")
    assert online["strategy_version"] == "v0.1"
    assert online["lifecycle_source"] == "canonical_replay_strategy_registry"

    # Rejected / retired / observation strategies retain their evidence rows.
    rejected_rows = [r for r in rows if r["lifecycle_status"] == "REJECTED"]
    assert rejected_rows  # present, not removed
    assert all(r["ticket_identity_available"] is True for r in rows)


def test_unresolved_lifecycle_uses_sentinel_not_fabrication(rows):
    sentinel_rows = [r for r in rows if r["lifecycle_status"] == p275b.LIFECYCLE_SENTINEL]
    assert len(sentinel_rows) == 9  # 3 cells x 3 windows
    for r in sentinel_rows:
        assert r["strategy_version"] == p275b.VERSION_SENTINEL
        assert r["lifecycle_source"] == "unresolved"
        assert any("not fabricated" in lim.lower() or "sentinel" in lim.lower()
                   for lim in r["limitations"])


# --------------------------------------------------------------------------- #
# Window handling                                                             #
# --------------------------------------------------------------------------- #

def test_50_300_750_window_handling(rows):
    r = _row(rows, "DAILY_539", "acb_markov_midfreq_3bet", "SHORT")
    assert r["window_draw_count"] == 50 and r["window_type"] == "SHORT"
    assert r["promotion_eligible_window"] is False  # 50 cannot promote
    for wt, n in (("MID", 300), ("LONG", 750)):
        rr = _row(rows, "DAILY_539", "acb_markov_midfreq_3bet", wt)
        assert rr["window_draw_count"] == n
        assert rr["promotion_eligible_window"] is True
    # 1500 / all-history are reference-only and excluded from the matrix.
    assert all(r["window_draw_count"] in (50, 300, 750) for r in rows)
    assert artifact_all_history_excluded(rows)


def artifact_all_history_excluded(rows):
    return not any(r["window_draw_count"] in (1500,) for r in rows)


def test_short_50_cannot_promote(rows):
    # daily539_f4cold_5bet @ 50 survives Bonferroni but is NOT counted as a
    # correction-surviving EDGE (it is DESCRIPTIVE_ONLY) — the guardrail.
    r = _row(rows, "DAILY_539", "daily539_f4cold_5bet", "SHORT")
    assert r["corrected_p_value"] is not None and r["corrected_p_value"] < 0.05
    assert r["evidence_status"] == "PRIZE_AWARE_DESCRIPTIVE_ONLY"
    assert r["promotion_eligible_window"] is False


# --------------------------------------------------------------------------- #
# bet_index / bet_count / ticket_count separation                             #
# --------------------------------------------------------------------------- #

def test_bet_index_bet_count_ticket_count_separation(rows):
    three = _row(rows, "DAILY_539", "acb_markov_midfreq_3bet", "LONG")
    assert three["bet_indices"]["derived_bet_count_per_draw"] == 3
    assert three["ticket_count"]["per_draw_distinct_ticket_count"] == 3
    assert three["ticket_count"]["window_total_distinct_tickets"] == 3 * 750
    assert three["ticket_budget"] == 3
    assert isinstance(three["bet_indices"]["distinct_bet_index_values"], list)
    assert three["bet_indices"]["distinct_bet_index_values"]  # non-empty

    one = _row(rows, "DAILY_539", "acb_1bet", "LONG")
    assert one["bet_indices"]["derived_bet_count_per_draw"] == 1
    assert one["ticket_count"]["per_draw_distinct_ticket_count"] == 1
    assert one["ticket_budget"] == 1

    five = _row(rows, "DAILY_539", "daily539_f4cold_5bet", "LONG")
    assert five["bet_indices"]["derived_bet_count_per_draw"] == 5
    assert five["ticket_count"]["per_draw_distinct_ticket_count"] == 5

    # bet_index (raw indices), bet_count (derived), ticket_count (distinct) and
    # prediction number count are four distinct, separately reported concepts.
    assert set(three.keys()) >= {"bet_indices", "ticket_count",
                                 "ticket_budget", "prediction_number_count"}


def test_prediction_number_count(rows):
    assert _row(rows, "DAILY_539", "acb_1bet", "MID")["prediction_number_count"] == {
        "main_number_count": 5, "has_second_zone": False, "second_zone_number_count": 0}
    assert _row(rows, "BIG_LOTTO", "ts3_regime_3bet", "MID")["prediction_number_count"] == {
        "main_number_count": 6, "has_second_zone": False, "second_zone_number_count": 0}
    assert _row(rows, "POWER_LOTTO", "power_precision_3bet", "MID")["prediction_number_count"] == {
        "main_number_count": 6, "has_second_zone": True, "second_zone_number_count": 1}


# --------------------------------------------------------------------------- #
# Per-lottery prize-aware endpoints                                           #
# --------------------------------------------------------------------------- #

def test_daily539_m2_plus_scoring(rows):
    r = _row(rows, "DAILY_539", "acb_markov_midfreq_3bet", "MID")
    assert r["outcome_endpoint"]["endpoint_id"] == "D539_ANY_PRIZE_AWARE_WIN"
    assert r["outcome_endpoint"]["condition"] == "hit_count >= 2"
    assert "2-match" in r["prize_tier"]


def test_biglotto_special_number_scoring(rows):
    r = _row(rows, "BIG_LOTTO", "ts3_regime_3bet", "MID")
    assert r["outcome_endpoint"]["endpoint_id"] == "BIG_ANY_PRIZE_AWARE_WIN"
    assert r["outcome_endpoint"]["condition"] == "hit_count >= 3 OR (hit_count = 2 AND special_hit = 1)"
    assert "special" in r["prize_tier"]


def test_powerlotto_second_zone_scoring(rows):
    r = _row(rows, "POWER_LOTTO", "power_precision_3bet", "MID")
    assert r["outcome_endpoint"]["endpoint_id"] == "POWER_ANY_PRIZE_AWARE_WIN"
    assert r["outcome_endpoint"]["condition"] == "hit_count >= 3 OR (hit_count >= 1 AND special_hit = 1)"
    assert "second-zone" in r["prize_tier"]
    assert r["prediction_number_count"]["has_second_zone"] is True


# --------------------------------------------------------------------------- #
# POWER missing-second-zone exclusion + missing-never-a-loss                  #
# --------------------------------------------------------------------------- #

def test_power_missing_second_zone_exclusion(rows):
    # fourier_rhythm_3bet has no eligible second-zone bets in any primary window.
    for wt in ("SHORT", "MID", "LONG"):
        r = _row(rows, "POWER_LOTTO", "fourier_rhythm_3bet", wt)
        assert r["eligible_draws"] == 0
        assert r["evaluable"] is False
        assert r["evidence_status"] == "PRIZE_AWARE_INSUFFICIENT_SUPPORT"
        assert r["missing_draws"]["second_zone_excluded_bet_rows"] > 0
        # excluded, never imputed
        assert r["missing_draws"]["imputed"] is False
        assert r["confidence_interval"] is None
        assert r["p_value"] is None and r["corrected_p_value"] is None


def test_partial_power_exclusion_keeps_eligible_draws(rows):
    # midfreq_fourier_mk_3bet keeps 1 eligible bet/draw while excluding others.
    r = _row(rows, "POWER_LOTTO", "midfreq_fourier_mk_3bet", "LONG")
    assert r["eligible_draws"] == 750
    assert r["missing_draws"]["second_zone_excluded_bet_rows"] > 0
    assert r["evaluable"] is True


def test_missing_rows_never_counted_as_losses(rows):
    for r in rows:
        md = r["missing_draws"]
        assert md["treated_as_loss"] is False
        assert md["imputed"] is False
    # A fully-excluded window has zero successes but is NOT a NULL/loss verdict.
    r = _row(rows, "POWER_LOTTO", "power_orthogonal_5bet", "LONG")
    assert r["success_draws"] == 0
    assert r["evidence_status"] == "PRIZE_AWARE_INSUFFICIENT_SUPPORT"
    assert r["evidence_status"] != "PRIZE_AWARE_NULL"


# --------------------------------------------------------------------------- #
# Baseline calculation                                                        #
# --------------------------------------------------------------------------- #

def test_baseline_calculation(rows):
    for r in rows:
        assert r["baseline_type"] == "GOVERNED_EXACT_DISTINCT_TICKET_RANDOM_NULL"
    r = _row(rows, "DAILY_539", "539_3bet_orthogonal", "MID")
    assert r["baseline_success_rate"] == pytest.approx(0.113973429763, abs=1e-9)
    assert r["absolute_lift"] == pytest.approx(r["success_rate"] - r["baseline_success_rate"], abs=1e-9)
    # non-evaluable windows carry no baseline (excluded, not zeroed)
    ne = _row(rows, "POWER_LOTTO", "fourier_rhythm_3bet", "MID")
    assert ne["baseline_success_rate"] is None


def test_diversified_random_baseline_absent(artifact):
    assert artifact["baseline_contract"]["diversified_random_baseline"] == "ABSENT_NOT_IMPLEMENTED"


# --------------------------------------------------------------------------- #
# Confidence intervals (independently re-derived)                             #
# --------------------------------------------------------------------------- #

def test_confidence_intervals(rows):
    evaluable = [r for r in rows if r["evaluable"]]
    assert len(evaluable) == 86
    for r in evaluable:
        ci = r["confidence_interval"]
        assert ci is not None
        assert len(ci["wilson_95"]) == 2 and len(ci["clopper_pearson_95"]) == 2
        # Valid probability intervals that bracket the observed rate.
        for lo, hi in (ci["wilson_95"], ci["clopper_pearson_95"]):
            assert 0.0 <= lo <= r["success_rate"] <= hi <= 1.0
        # Independent re-derivation reproduces the committed P273A intervals.
        assert ci["rederivation_matches_committed"] is True
        assert r["reproducibility_status"] == "REPRODUCED"


def test_all_rows_reproduced(artifact):
    assert artifact["matrix_summary"]["all_rows_reproduced"] is True
    assert artifact["matrix_summary"]["rows_reproduced"] == 108


# --------------------------------------------------------------------------- #
# Bonferroni family size and corrected values                                 #
# --------------------------------------------------------------------------- #

def test_bonferroni_family_size_and_corrected_values(artifact, rows):
    for r in rows:
        cf = r["correction_family"]
        assert cf["family_m"] == 108
        assert cf["per_test_alpha"] == pytest.approx(0.05 / 108, abs=1e-15)
        assert cf["no_post_outcome_family_shrinkage"] is True
        assert r["correction_method"] == "BONFERRONI"
    for r in rows:
        if r["evaluable"]:
            assert r["corrected_p_value"] == pytest.approx(
                min(1.0, r["p_value"] * 108), abs=1e-9)
    # The four correction-surviving EDGE windows are exactly the DAILY_539 set.
    surviving = {(e["lottery_type"], e["strategy_id"], e["window_type"])
                 for e in artifact["matrix_summary"]["correction_surviving_edge_windows"]}
    assert surviving == {
        ("DAILY_539", "acb_markov_midfreq_3bet", "MID"),
        ("DAILY_539", "daily539_f4cold_3bet", "LONG"),
        ("DAILY_539", "daily539_f4cold_5bet", "MID"),
        ("DAILY_539", "daily539_f4cold_5bet", "LONG"),
    }


# --------------------------------------------------------------------------- #
# Deterministic ordering + canonical digest reproducibility                   #
# --------------------------------------------------------------------------- #

def test_deterministic_ordering(rows):
    order = [(r["lottery_type"], r["strategy_id"], r["window_draw_count"]) for r in rows]
    assert order == sorted(order)


def test_canonical_digest_reproducibility():
    a1 = p275b.build_artifact(generated_at=PINNED_AT)
    a2 = p275b.build_artifact(generated_at="2099-12-31T23:59:59+00:00")
    # generated_at is excluded from the digest; everything else is deterministic.
    assert a1["canonical_payload_digest"] == a2["canonical_payload_digest"]
    recomputed = p275b.canonical_digest(a1, p275b.SELF_DIGEST_EXCLUDE)
    assert recomputed == a1["canonical_payload_digest"]


def test_committed_artifact_digest_matches_fresh_build():
    committed_path = (_MODULE_PATH.parents[1] / "outputs" / "research"
                      / "p275b_unified_prize_aware_success_matrix_20260616.json")
    if not committed_path.exists():
        pytest.skip("committed artifact not present in this tree")
    committed = json.loads(committed_path.read_text(encoding="utf-8"))
    # Reproduce the committed artifact from its *pinned* source snapshot, not
    # the live HEAD: a branch update advances HEAD without changing the source
    # snapshot the committed artifact records, so source_commit must be replayed
    # explicitly rather than re-derived from the current working tree.
    fresh = p275b.build_artifact(
        generated_at=committed["generated_at"],
        source_commit=committed["source_commit"])
    assert committed["canonical_payload_digest"] == fresh["canonical_payload_digest"]
    assert committed["canonical_payload_digest"] == p275b.canonical_digest(
        committed, p275b.SELF_DIGEST_EXCLUDE)


# --------------------------------------------------------------------------- #
# Source-snapshot provenance (source_commit) semantics                        #
#                                                                             #
# source_commit is the immutable source snapshot a build is derived from —    #
# not the artifact-carrying commit and not necessarily the live HEAD. It must #
# stay digest-covered and be replayable for historical reproduction.          #
# --------------------------------------------------------------------------- #

# A second well-formed (but distinct) snapshot id, used to prove the digest is
# sensitive to source_commit. Value is synthetic; the builder only embeds it as
# provenance and never resolves it against git.
_PINNED_SOURCE_A = "77994824d1c1e5e4d4db14f0c7d5cb64bf933ead"
_PINNED_SOURCE_B = "0123456789abcdef0123456789abcdef01234567"


def test_explicit_pinned_source_commit_is_preserved():
    art = p275b.build_artifact(generated_at=PINNED_AT, source_commit=_PINNED_SOURCE_A)
    assert art["source_commit"] == _PINNED_SOURCE_A
    # Every row carries the same pinned snapshot, and it is never excluded from
    # the canonical digest.
    assert all(r["source_commit"] == _PINNED_SOURCE_A for r in art["matrix_rows"])
    assert "source_commit" not in p275b.SELF_DIGEST_EXCLUDE


def test_pinned_reproduction_matches_committed_digest():
    committed_path = (_MODULE_PATH.parents[1] / "outputs" / "research"
                      / "p275b_unified_prize_aware_success_matrix_20260616.json")
    if not committed_path.exists():
        pytest.skip("committed artifact not present in this tree")
    committed = json.loads(committed_path.read_text(encoding="utf-8"))
    fresh = p275b.build_artifact(
        generated_at=committed["generated_at"],
        source_commit=committed["source_commit"])
    assert fresh["source_commit"] == committed["source_commit"]
    assert fresh["canonical_payload_digest"] == committed["canonical_payload_digest"]


def test_changing_pinned_source_commit_changes_digest():
    a = p275b.build_artifact(generated_at=PINNED_AT, source_commit=_PINNED_SOURCE_A)
    b = p275b.build_artifact(generated_at=PINNED_AT, source_commit=_PINNED_SOURCE_B)
    assert _PINNED_SOURCE_A != _PINNED_SOURCE_B
    assert a["source_commit"] != b["source_commit"]
    # source_commit is inside the canonical payload, so a different snapshot
    # must yield a different canonical digest.
    assert a["canonical_payload_digest"] != b["canonical_payload_digest"]


def test_default_source_commit_uses_live_head():
    # The None default documents new-build behaviour: the live execution HEAD.
    # This path stays separately testable from the pinned-replay path above.
    art = p275b.build_artifact(generated_at=PINNED_AT)
    assert art["source_commit"] == p275b._git_head()


@pytest.mark.parametrize("bad", ["", "   ", "\t\n"])
def test_empty_source_commit_rejected(bad):
    # Explicit but empty/whitespace provenance is malformed — it must be
    # rejected rather than silently falling back to the live HEAD (which is
    # expressed only by None).
    with pytest.raises(ValueError):
        p275b.build_artifact(generated_at=PINNED_AT, source_commit=bad)


# --------------------------------------------------------------------------- #
# JSON and Markdown consistency                                               #
# --------------------------------------------------------------------------- #

def test_json_serialisable_and_roundtrips(artifact):
    blob = json.dumps(artifact, ensure_ascii=False, sort_keys=True)
    reloaded = json.loads(blob)
    assert reloaded["matrix_summary"]["total_rows"] == 108
    assert reloaded["final_classification"] == "P275B_UNIFIED_PRIZE_AWARE_SUCCESS_MATRIX_COMPLETE"


def test_json_and_markdown_consistency(artifact):
    md = p275b.render_markdown(artifact)
    s = artifact["matrix_summary"]
    assert artifact["canonical_payload_digest"] in md
    assert str(s["total_rows"]) in md
    assert str(s["frozen_cells"]) in md
    # lifecycle + evidence counts surfaced in the Markdown
    for status, count in s["lifecycle_status_counts"].items():
        assert status in md
    assert "PRIZE_AWARE_EDGE_CORRECTION_SURVIVING" in md
    # no betting recommendation / no future-success claim language present
    low = md.lower()
    assert "no betting recommendation" in low
    assert "no future-success claim" in low
    assert "retrospective" in low


# --------------------------------------------------------------------------- #
# No write-path invocation / no DB access                                     #
# --------------------------------------------------------------------------- #

def test_no_write_path_invocation(monkeypatch):
    """Building the artifact must perform no file writes and no DB access."""
    writes = []
    real_open = builtins.open

    def spy_open(file, mode="r", *a, **k):
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            writes.append((str(file), mode))
        return real_open(file, mode, *a, **k)

    monkeypatch.setattr(builtins, "open", spy_open)
    art = p275b.build_artifact(generated_at=PINNED_AT)
    assert writes == []
    assert art["production_db_opened"] is False
    assert art["db_guard_hits"] == []


def test_write_outputs_not_called_during_build(monkeypatch):
    called = {"n": 0}

    def boom(*a, **k):
        called["n"] += 1
        raise AssertionError("write_outputs must not run during build")

    monkeypatch.setattr(p275b, "write_outputs", boom)
    p275b.build_artifact(generated_at=PINNED_AT)
    assert called["n"] == 0
