"""
Targeted tests for P230B1 DAILY_539 backward-OOS code-only dry-run generator.

Covers: causal slicing / no future leakage, ordinal-predecessor cutoff,
min_history warmup, bet semantics, P224-replicating statistics, classification
mapping, determinism, and a read-only DB guarantee (skipped if the DB is absent).

numpy is required by the reused adapter module; importorskip keeps this test
CI-safe in lanes that do not install numpy.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("numpy")  # adapter module imports numpy at top-level

from scripts import p230b1_daily539_backward_oos_dryrun as gen  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
BASELINE = gen.P224_BASELINE


# ─── Synthetic helpers ────────────────────────────────────────────────────────

def _synthetic_draws(n: int) -> list:
    """Deterministic synthetic DAILY_539 draws, chronologically ascending."""
    draws = []
    for k in range(n):
        base = (k % 35) + 1
        nums = sorted({((base + j * 7 - 1) % 39) + 1 for j in range(5)})
        while len(nums) < 5:  # guarantee exactly 5 distinct
            nums = sorted(set(nums) | {(nums[-1] % 39) + 1})
        draws.append({"draw": str(100000001 + k), "date": f"2010/{(k % 12) + 1:02d}/01",
                      "numbers": nums[:5]})
    return draws


class _StubAdapter:
    """Deterministic stub: bet depends ONLY on the last history draw (causal)."""
    class _Meta:
        min_history = 5
        supported_lottery_types = ["DAILY_539"]
        strategy_id = "midfreq_fourier_2bet"
        strategy_version = "stub"
    meta = _Meta()

    def get_one_bet(self, history, lottery_type):
        if len(history) < self.meta.min_history:
            raise ValueError("insufficient history")
        return sorted(history[-1]["numbers"])[:5], None


# ─── Causal slicing / leakage ─────────────────────────────────────────────────

def test_no_future_leakage():
    """Mutating draws AFTER a target must not change that target's prediction."""
    draws = _synthetic_draws(60)
    window_min = int(draws[40]["draw"])  # first 40 are backward
    rows_a, _ = gen.generate_backward_rows(draws, window_min, _StubAdapter(), min_history=5)

    mutated = [dict(d) for d in draws]
    for j in range(45, 60):  # corrupt the future
        mutated[j] = {**mutated[j], "numbers": [1, 2, 3, 4, 5]}
    rows_b, _ = gen.generate_backward_rows(mutated, window_min, _StubAdapter(), min_history=5)

    pa = {r["target_draw"]: r["provenance_hash"] for r in rows_a if r["replay_status"] == "PREDICTED"}
    pb = {r["target_draw"]: r["provenance_hash"] for r in rows_b if r["replay_status"] == "PREDICTED"}
    assert pa and pa == pb  # identical predictions despite future mutation


def test_history_cutoff_is_ordinal_predecessor():
    draws = _synthetic_draws(60)
    window_min = int(draws[40]["draw"])
    draw_to_idx = {d["draw"]: i for i, d in enumerate(draws)}
    rows, _ = gen.generate_backward_rows(draws, window_min, _StubAdapter(), min_history=5)
    assert rows
    for r in rows:
        t_idx = draw_to_idx[r["target_draw"]]
        # cutoff is the immediately preceding draw in chronological order
        assert r["history_cutoff_draw"] == draws[t_idx - 1]["draw"]
        assert draw_to_idx[r["history_cutoff_draw"]] == t_idx - 1  # strictly earlier


def test_warmup_skip_and_backward_boundary():
    draws = _synthetic_draws(60)
    window_min = int(draws[40]["draw"])  # backward = indices 0..39 (40 draws)
    rows, inv = gen.generate_backward_rows(draws, window_min, _StubAdapter(), min_history=5)
    assert inv["backward_total_draws"] == 40
    assert inv["warmup_skipped"] == 5            # indices 0..4 skipped
    assert inv["replayable_backward_targets"] == 35
    assert len(rows) == 35
    # all generated targets are strictly earlier than the window boundary
    assert all(int(r["target_draw"]) < window_min for r in rows)


def test_limit_reports_true_replayable_count():
    draws = _synthetic_draws(60)
    window_min = int(draws[40]["draw"])
    rows, inv = gen.generate_backward_rows(draws, window_min, _StubAdapter(), min_history=5, limit=10)
    assert inv["replayable_backward_targets"] == 35  # true count
    assert inv["targets_generated"] == 10            # capped
    assert len(rows) == 10


# ─── Bet semantics with the REAL adapter ──────────────────────────────────────

def test_real_adapter_bet_semantics():
    from lottery_api.models.p31a_wave1_retired_adapters import WAVE1_ADAPTER_MAP
    adapter = WAVE1_ADAPTER_MAP["midfreq_fourier_2bet"]
    assert adapter.meta.min_history == 100
    draws = _synthetic_draws(150)
    window_min = int(draws[130]["draw"])  # backward = 0..129
    rows, _ = gen.generate_backward_rows(draws, window_min, adapter, min_history=100)
    predicted = [r for r in rows if r["replay_status"] == "PREDICTED"]
    assert predicted
    for r in predicted:
        assert r["bet_index"] == 1
        assert r["predicted_special"] is None
        nums = r["predicted_numbers"]
        assert len(nums) == 5 and len(set(nums)) == 5
        assert all(1 <= n <= 39 for n in nums)
        assert 0 <= r["hit_count"] <= 5
        assert r["dry_run"] == 1


# ─── Statistics replicate P224 ────────────────────────────────────────────────

def test_summarize_replicates_p224():
    hc = [0] * 714 + [1] * 587 + [2] * 180 + [3] * 19  # P224 in-window distribution
    s = gen.summarize(hc, BASELINE)
    assert s["n"] == 1500
    assert abs(s["mean_hit_count"] - 0.6693333333333333) < 1e-9
    assert abs(s["ci95"][0] - 0.6322371303354622) < 1e-3
    assert abs(s["ci95"][1] - 0.7064295363312044) < 1e-3
    assert abs(s["p_one_sided_vs_baseline"] - 0.0673719479414372) < 5e-3
    assert s["direction"] == "above"


def test_summarize_baseline_p_is_half():
    """A sample whose mean equals baseline yields one-sided p ~ 0.5."""
    # construct hit_counts with mean exactly baseline-ish using many draws
    hc = [0, 1] * 5000  # mean 0.5 < baseline -> below; check direction only
    s = gen.summarize(hc, BASELINE)
    assert s["direction"] == "below"
    assert s["p_one_sided_vs_baseline"] > 0.5  # below baseline => upper-tail p > 0.5


# ─── Classification mapping ───────────────────────────────────────────────────

def _mk(mean, ci_cross, maj, eh_ok, es_ok):
    overall = {"mean_hit_count": mean, "ci_crosses_baseline": ci_cross}
    blocks150 = {"majority_above_baseline": maj}
    robust = {"exclude_hit_ge3": {"at_or_above_baseline": eh_ok},
              "exclude_strongest_150block": {"at_or_above_baseline": es_ok}}
    return overall, blocks150, robust


def test_classify_below_baseline():
    cls, _ = gen.classify(*_mk(BASELINE - 0.01, True, False, False, False), BASELINE)
    assert cls == "P230B1_BACKWARD_OOS_DRYRUN_BELOW_BASELINE"


def test_classify_mixed():
    cls, _ = gen.classify(*_mk(BASELINE + 0.02, True, True, False, True), BASELINE)
    assert cls == "P230B1_BACKWARD_OOS_DRYRUN_MIXED"


def test_classify_complete():
    cls, _ = gen.classify(*_mk(BASELINE + 0.05, False, True, True, True), BASELINE)
    assert cls == "P230B1_BACKWARD_OOS_DRYRUN_COMPLETE"


# ─── Read-only DB guarantees (skipped if DB absent) ───────────────────────────

@pytest.mark.skipif(not DB_PATH.exists(), reason="production DB fixture absent")
def test_readonly_connection_blocks_writes():
    conn = gen._connect_ro(DB_PATH)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute(
                "INSERT INTO strategy_prediction_replays "
                "(lottery_type, target_draw, strategy_id, replay_status) "
                "VALUES ('DAILY_539','0','x','PREDICTED')"
            )
    finally:
        conn.close()


@pytest.mark.skipif(not DB_PATH.exists(), reason="production DB fixture absent")
def test_real_db_inventory_and_no_write():
    before = gen.total_replay_rows(DB_PATH)
    result = gen.run(DB_PATH, limit=50)  # small cap for speed
    after = gen.total_replay_rows(DB_PATH)
    assert before == after                      # no DB write
    assert result["db_write_performed"] is False
    inv = result["inventory"]
    assert inv["daily539_total_draws"] == 5876
    assert inv["window_min_draw"] == 110000190
    assert inv["backward_total_draws"] == 4365
    assert inv["warmup_skipped"] == 100
    assert inv["replayable_backward_targets"] == 4265
    assert inv["first_backward_replayable"] == "96000101"
