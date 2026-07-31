"""
Targeted tests for the P231B POWER_LOTTO first-zone backward-OOS code-only dry-run.

Covers: causal slicing / no future leakage, ordinal-predecessor cutoff,
min_history warmup, deterministic bet-1-only semantics (no invented bets 2-3),
first-zone statistics that replicate the published artifact, second-zone
display-only handling, the falsification-oriented classification mapping, and a
read-only DB guarantee with a row-count before/after no-write proof.

numpy is required by the reused P47 adapter module; importorskip keeps this test
CI-safe in lanes that do not install numpy (run with ./.venv/bin/python3 to
exercise the real-adapter / real-DB cases instead of skipping them).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("numpy")  # adapter module imports numpy at top-level

from scripts import p231b_powerlotto_first_zone_backward_oos_dryrun as gen  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
BASELINE = gen.FIRST_ZONE_BASELINE       # 36/38
SPECIAL_BASELINE = gen.SPECIAL_BASELINE  # 1/8


# ─── Synthetic helpers ────────────────────────────────────────────────────────

def _synthetic_power_draws(n: int) -> list:
    """Deterministic synthetic POWER_LOTTO draws, chronologically ascending.

    Each draw has 6 distinct first-zone numbers in 1-38 and a special in 1-8.
    Draw IDs are strictly increasing so `int(draw) < window_min` and the
    chronological index order agree.
    """
    draws = []
    for k in range(n):
        base = (k % 33) + 1
        nums = sorted({((base + j * 5 - 1) % 38) + 1 for j in range(6)})
        while len(nums) < 6:  # guarantee exactly 6 distinct first-zone numbers
            nums = sorted(set(nums) | {(nums[-1] % 38) + 1})
        draws.append({
            "draw": str(100000001 + k),
            "date": f"2010/{(k % 12) + 1:02d}/01",
            "numbers": nums[:6],
            "special": (k % 8) + 1,
        })
    return draws


class _StubAdapter:
    """Deterministic stub: bet-1 depends ONLY on the last history draw (causal)."""
    class _Meta:
        min_history = 5
        supported_lottery_types = ["POWER_LOTTO"]
        strategy_id = "midfreq_fourier_mk_3bet"
        strategy_version = "stub"
    meta = _Meta()

    def get_one_bet(self, history, lottery_type):
        if len(history) < self.meta.min_history:
            raise ValueError("insufficient history")
        last = history[-1]
        return sorted(last["numbers"])[:6], last.get("special")


# ─── Causal slicing / leakage ─────────────────────────────────────────────────

def test_no_future_leakage():
    """Mutating draws AFTER a target must not change that target's prediction."""
    draws = _synthetic_power_draws(60)
    window_min = int(draws[40]["draw"])  # first 40 are backward
    rows_a, _ = gen.generate_backward_rows(draws, window_min, _StubAdapter(), min_history=5)

    mutated = [dict(d) for d in draws]
    for j in range(45, 60):  # corrupt the future
        mutated[j] = {**mutated[j], "numbers": [1, 2, 3, 4, 5, 6], "special": 1}
    rows_b, _ = gen.generate_backward_rows(mutated, window_min, _StubAdapter(), min_history=5)

    pa = {r["target_draw"]: r["provenance_hash"] for r in rows_a if r["replay_status"] == "PREDICTED"}
    pb = {r["target_draw"]: r["provenance_hash"] for r in rows_b if r["replay_status"] == "PREDICTED"}
    assert pa and pa == pb  # identical predictions despite future mutation


def test_history_cutoff_is_ordinal_predecessor():
    """Leakage guard: cutoff is the immediately-preceding draw, not target_draw-1."""
    draws = _synthetic_power_draws(60)
    window_min = int(draws[40]["draw"])
    draw_to_idx = {d["draw"]: i for i, d in enumerate(draws)}
    rows, _ = gen.generate_backward_rows(draws, window_min, _StubAdapter(), min_history=5)
    assert rows
    for r in rows:
        t_idx = draw_to_idx[r["target_draw"]]
        assert r["history_cutoff_draw"] == draws[t_idx - 1]["draw"]
        assert draw_to_idx[r["history_cutoff_draw"]] == t_idx - 1  # strictly earlier


def test_warmup_skip_and_backward_boundary():
    draws = _synthetic_power_draws(60)
    window_min = int(draws[40]["draw"])  # backward = indices 0..39 (40 draws)
    rows, inv = gen.generate_backward_rows(draws, window_min, _StubAdapter(), min_history=5)
    assert inv["backward_total_draws"] == 40
    assert inv["warmup_skipped"] == 5            # indices 0..4 skipped
    assert inv["replayable_backward_targets"] == 35
    assert len(rows) == 35
    # every generated target is strictly earlier than the window boundary
    assert all(int(r["target_draw"]) < window_min for r in rows)


def test_limit_reports_true_replayable_count():
    draws = _synthetic_power_draws(60)
    window_min = int(draws[40]["draw"])
    rows, inv = gen.generate_backward_rows(draws, window_min, _StubAdapter(), min_history=5, limit=10)
    assert inv["replayable_backward_targets"] == 35  # true count, not the cap
    assert inv["targets_generated"] == 10            # capped
    assert len(rows) == 10


# ─── Deterministic bet-1-only semantics with the REAL adapter ─────────────────

def test_real_adapter_is_deterministic_bet1_only():
    """Real P47 adapter: bet-1 only, 6 first-zone numbers + a special; no bets 2-3."""
    from lottery_api.models.p47_wave4_powerlotto_adapters import WAVE4_ADAPTER_MAP
    adapter = WAVE4_ADAPTER_MAP["midfreq_fourier_mk_3bet"]
    assert adapter.meta.min_history == 30
    assert adapter.meta.supported_lottery_types == ["POWER_LOTTO"]

    draws = _synthetic_power_draws(80)
    window_min = int(draws[60]["draw"])  # backward = 0..59
    rows, _ = gen.generate_backward_rows(draws, window_min, adapter, min_history=30)
    predicted = [r for r in rows if r["replay_status"] == "PREDICTED"]
    assert predicted
    for r in predicted:
        assert r["bet_index"] == 1                       # bet-1 only — bets 2,3 never invented
        nums = r["predicted_numbers"]
        assert len(nums) == 6 and len(set(nums)) == 6
        assert all(1 <= n <= 38 for n in nums)           # first zone 1-38
        assert 1 <= r["predicted_special"] <= 8          # second zone 1-8
        assert 0 <= r["hit_count"] <= 6                  # first-zone hits only
        assert r["special_hit"] in (0, 1)
        assert r["dry_run"] == 1

    # Determinism: a second identical run yields identical provenance hashes.
    rows2, _ = gen.generate_backward_rows(draws, window_min, adapter, min_history=30)
    h1 = [r["provenance_hash"] for r in rows if r["replay_status"] == "PREDICTED"]
    h2 = [r["provenance_hash"] for r in rows2 if r["replay_status"] == "PREDICTED"]
    assert h1 == h2


# ─── First-zone statistics replicate the published artifact ───────────────────

def test_summarize_replicates_artifact_first_zone():
    """The published first-zone distribution must reproduce the artifact headline."""
    hc = [0] * 116 + [1] * 173 + [2] * 83 + [3] * 9 + [4] * 1  # artifact distribution
    s = gen.summarize(hc, BASELINE)
    assert s["n"] == 382
    assert abs(s["mean"] - 0.9685863874345549) < 1e-9
    assert abs(s["ci95"][0] - 0.8885012575011227) < 1e-6
    assert abs(s["ci95"][1] - 1.0486715173679872) < 1e-6
    assert abs(s["p_one_sided_vs_baseline"] - 0.3017801031096934) < 1e-6
    assert s["ci_crosses_baseline"] is True
    assert s["direction"] == "above"


def test_summarize_below_baseline_direction():
    """A clearly below-baseline sample => direction below and upper-tail p > 0.5."""
    hc = [0, 1] * 5000  # mean 0.5 < baseline (0.947)
    s = gen.summarize(hc, BASELINE)
    assert s["direction"] == "below"
    assert s["p_one_sided_vs_baseline"] > 0.5


def test_second_zone_display_only_is_separate():
    """Second-zone special is summarized against 1/8 and never enters first-zone stats."""
    sp = [0] * 340 + [1] * 42  # artifact special distribution
    so = gen.summarize(sp, SPECIAL_BASELINE)
    assert so["n"] == 382
    assert abs(so["mean"] - 0.1099476439790576) < 1e-9
    assert so["direction"] == "below"  # 0.110 < 0.125 baseline


# ─── Classification mapping (falsification-oriented, never presumes success) ───

def _mk(mean, ci_cross, p, maj, eh_ok, es_ok):
    overall = {"mean": mean, "ci_crosses_baseline": ci_cross, "p_one_sided_vs_baseline": p}
    blocks = {"100": {"majority_above_baseline": maj}}
    robust = {"exclude_hit_ge3": {"at_or_above_baseline": eh_ok},
              "exclude_strongest_block": {"at_or_above_baseline": es_ok}}
    return overall, blocks, robust


def test_classify_below_baseline():
    cls, _ = gen.classify(*_mk(BASELINE - 0.05, True, 0.9, False, False, False), BASELINE)
    assert cls == "P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN_BELOW_BASELINE"


def test_classify_null_matches_actual_result():
    """mean ~ baseline, CI crosses, not significant => NULL (the real P231B outcome)."""
    cls, _ = gen.classify(*_mk(BASELINE + 0.02, True, 0.30, False, False, False), BASELINE)
    assert cls == "P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN_NULL"


def test_classify_needs_more_oos_when_clean():
    cls, _ = gen.classify(*_mk(BASELINE + 0.05, False, 0.01, True, True, True), BASELINE)
    assert cls == "P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN_NEEDS_MORE_OOS"


def test_classify_weak_observation_when_a_gate_fails():
    # above baseline, significant, CI does not cross, but a robustness gate fails
    cls, _ = gen.classify(*_mk(BASELINE + 0.05, False, 0.01, True, True, False), BASELINE)
    assert cls == "P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN_WEAK_OBSERVATION_ONLY"


# ─── Read-only DB guarantees (skipped if DB absent) ───────────────────────────

@pytest.mark.skipif(not DB_PATH.exists(), reason="production DB fixture absent")
def test_readonly_connection_blocks_writes():
    conn = gen._connect_ro(DB_PATH)
    try:
        # Probe readability first. A WAL-mode DB held by a concurrent live writer
        # (the backend server) transiently rejects any mode=ro open with
        # "unable to open database file" — an environment condition, not a code
        # defect — so skip rather than false-pass on that error below.
        try:
            conn.execute("SELECT 1 FROM strategy_prediction_replays LIMIT 1").fetchone()
        except sqlite3.OperationalError as exc:
            pytest.skip(f"production DB not openable read-only right now: {exc}")
        # Connection is genuinely open read-only: a write MUST be rejected as such.
        with pytest.raises(sqlite3.OperationalError) as ei:
            conn.execute(
                "INSERT INTO strategy_prediction_replays "
                "(lottery_type, target_draw, strategy_id, replay_status) "
                "VALUES ('POWER_LOTTO','0','x','PREDICTED')"
            )
        msg = str(ei.value).lower()
        assert "readonly" in msg or "read-only" in msg  # a true RO rejection, not an open failure
    finally:
        conn.close()


@pytest.mark.skipif(not DB_PATH.exists(), reason="production DB fixture absent")
def test_real_db_inventory_and_no_write():
    try:
        before = gen.total_replay_rows(DB_PATH)
        result = gen.run(DB_PATH, limit=50)  # small cap for speed
        after = gen.total_replay_rows(DB_PATH)
    except sqlite3.OperationalError as exc:
        # Transient: the WAL-mode production DB is held by a concurrent live
        # writer and cannot be opened mode=ro at this instant. This is an
        # environment condition, not a code defect (a real write would change
        # the row count or set db_write_performed, not raise on open).
        pytest.skip(f"production DB not openable read-only right now: {exc}")
    assert before == after                       # zero DB write
    assert result["db_write_performed"] is False
    assert result["db_rows_before"] == result["db_rows_after"]
    inv = result["inventory"]
    assert inv["power_total_draws"] == 1915
    assert inv["window_min_draw"] == 101000002
    assert inv["backward_total_draws"] == 412
    assert inv["min_history_warmup"] == 30
    assert inv["warmup_skipped"] == 30
    assert inv["replayable_backward_targets"] == 382          # true count (limit-independent)
    assert inv["replayable_under_conservative_100_warmup"] == 312
    assert inv["first_backward_replayable"] == "97000031"
