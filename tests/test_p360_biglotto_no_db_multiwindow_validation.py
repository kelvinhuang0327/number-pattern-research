import csv
import sqlite3

import pytest

from recovered_strategies.biglotto import historical_adapters
from recovered_strategies.biglotto import no_db_multiwindow_validation as validation


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P360 validation")


@pytest.fixture(scope="session")
def double_run():
    """Run the full validation twice in this test process with DB opens blocked."""
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = validation.run_validation()
        second = validation.run_validation()
    finally:
        patcher.undo()
    return first, second


def synthetic_draws(count):
    draws = []
    for idx in range(count):
        pool = sorted({((idx * 7 + offset * 11) % 49) + 1 for offset in range(9)})
        mains = tuple(sorted(pool[:6]))
        draws.append(
            validation.Draw(period=100000000 + idx, mains=mains, special=((idx * 5) % 49) + 1)
        )
    return draws


def test_fixture_load_sha256_and_row_count():
    draws, sha256 = validation.load_big_lotto_draws()
    assert sha256 == validation.EXPECTED_FIXTURE_SHA256
    assert len(draws) == validation.EXPECTED_BIG_LOTTO_ROWS == 2139
    periods = [d.period for d in draws]
    assert periods == sorted(periods)
    assert len(set(periods)) == len(periods)
    for draw in draws:
        assert len(draw.mains) == 6
        assert len(set(draw.mains)) == 6
        assert all(1 <= n <= 49 for n in draw.mains)
        assert list(draw.mains) == sorted(draw.mains)
        assert 1 <= draw.special <= 49


def test_adapter_allowlist_is_exactly_five_and_parity_only():
    assert len(validation.ALLOWLISTED_ADAPTERS) == 5
    specs = validation.resolve_scoring_adapters()
    assert tuple(spec.name for spec in specs) == validation.ALLOWLISTED_ADAPTERS
    for spec in specs:
        assert spec.parity_status == validation.REQUIRED_PARITY_STATUS
        assert callable(spec.fn)
        assert spec.bet_count in (2, 3)
    non_parity = {
        name
        for name, meta in historical_adapters.ADAPTER_METADATA.items()
        if meta.get("parity_status") != validation.REQUIRED_PARITY_STATUS
    }
    assert non_parity
    assert not non_parity & set(validation.ALLOWLISTED_ADAPTERS)


def test_shape_only_and_blocked_adapters_fail_closed():
    shape_only = [
        name
        for name, meta in historical_adapters.ADAPTER_METADATA.items()
        if meta.get("parity_status") != validation.REQUIRED_PARITY_STATUS
    ]
    assert shape_only
    for name in shape_only:
        with pytest.raises(validation.AdapterSelectionError):
            validation.resolve_scoring_adapters(validation.ALLOWLISTED_ADAPTERS + (name,))
        with pytest.raises(validation.AdapterSelectionError):
            validation.resolve_scoring_adapters((name,))
    with pytest.raises(validation.AdapterSelectionError):
        validation.resolve_scoring_adapters(validation.ALLOWLISTED_ADAPTERS[:4])
    with pytest.raises(validation.AdapterSelectionError):
        validation.resolve_scoring_adapters(("adapter_that_does_not_exist",))


def test_scored_cohort_contains_only_allowlisted_adapters(double_run):
    first, _ = double_run
    scored = {row["adapter_function"] for row in first.results_rows}
    assert scored == set(validation.ALLOWLISTED_ADAPTERS)
    assert all(row["tier"] == validation.TIER for row in first.results_rows)
    assert all(
        row["parity_status"] == validation.REQUIRED_PARITY_STATUS for row in first.results_rows
    )


def test_walk_forward_does_not_leak_future_draws():
    draws = synthetic_draws(count=validation.LOOKBACK + 10)
    seen_histories = []

    def spy_adapter(history):
        seen_histories.append([entry["period"] for entry in history])
        return [[1, 2, 3, 4, 5, 6]]

    records = validation.run_walk_forward(draws, {"spy_adapter": spy_adapter})
    assert len(records) == 10
    assert len(seen_histories) == 10
    all_periods = [d.period for d in draws]
    for call_index, (target_period, name, bet_count, hit) in enumerate(records):
        history_periods = seen_histories[call_index]
        assert name == "spy_adapter"
        assert bet_count == 1
        assert isinstance(hit, bool)
        assert len(history_periods) == validation.LOOKBACK
        assert max(history_periods) < target_period
        expected = all_periods[call_index : call_index + validation.LOOKBACK]
        assert history_periods == expected


def test_baseline_formula_for_two_and_three_bets():
    p = validation.BASELINE_SINGLE_TICKET_P
    assert p == 0.0186375
    assert validation.compute_baseline(2) == 1 - (1 - p) ** 2
    assert validation.compute_baseline(3) == 1 - (1 - p) ** 3
    assert validation.compute_baseline(3) > validation.compute_baseline(2) > p


def test_results_schema_has_required_columns(double_run):
    first, _ = double_run
    expected_columns = (
        "adapter_function",
        "strategy_id",
        "tier",
        "parity_status",
        "bet_count",
        "window_size",
        "period_count",
        "hit_count",
        "hit_rate",
        "same_bet_count_baseline",
        "edge_vs_same_bet_count_baseline",
        "positive_edge",
        "first_period",
        "last_period",
        "fixture_sha256",
    )
    assert validation.RESULTS_COLUMNS == expected_columns
    assert len(first.results_rows) == len(validation.ALLOWLISTED_ADAPTERS) * len(validation.WINDOWS)
    for row in first.results_rows:
        assert set(row.keys()) == set(expected_columns)
        assert int(row["period_count"]) == int(row["window_size"])
        assert 0 <= int(row["hit_count"]) <= int(row["period_count"])
        assert row["fixture_sha256"] == validation.EXPECTED_FIXTURE_SHA256


def test_deterministic_double_run_equality(double_run):
    first, second = double_run
    assert first.results_rows == second.results_rows
    assert first.coverage_rows == second.coverage_rows
    assert first.manifest_rows == second.manifest_rows
    assert first.fixture_sha256 == second.fixture_sha256
    assert first.scoreable_period_count == second.scoreable_period_count == 1619


def test_csv_artifacts_are_written_and_parseable(tmp_path, double_run):
    first, _ = double_run
    paths = validation.write_artifacts(first, tmp_path)
    with open(paths["results"], newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == len(first.results_rows)
    assert set(rows[0].keys()) == set(validation.RESULTS_COLUMNS)
    with open(paths["coverage"], newline="", encoding="utf-8") as handle:
        coverage = list(csv.DictReader(handle))
    assert len(coverage) == len(first.coverage_rows)
    assert set(coverage[0].keys()) == set(validation.COVERAGE_COLUMNS)
    pairwise = [row for row in coverage if row["row_type"] == "pairwise"]
    assert len(pairwise) == 10
    unique = [row for row in coverage if row["row_type"] == "unique_contribution"]
    assert len(unique) == 5
    with open(paths["manifest"], newline="", encoding="utf-8") as handle:
        manifest = {row["key"]: row["value"] for row in csv.DictReader(handle)}
    assert manifest["fixture_sha256"] == validation.EXPECTED_FIXTURE_SHA256
    assert manifest["big_lotto_row_count"] == "2139"
    assert manifest["scoreable_period_count"] == "1619"
    assert manifest["db_opened"] == "NO"
    assert paths["report"].is_file()
    assert paths["report"].stat().st_size > 0


def test_report_contains_required_statements(double_run):
    first, _ = double_run
    report = validation.render_report(first)
    assert "historical descriptive validation only" in report
    assert "No future prediction guarantee" in report
    assert "No betting advice" in report
    assert "No DB was opened or written" in report
    assert "No blended leaderboard" in report
    assert "Shape/safety-only adapters and blocked targets were excluded from scoring" in report
    assert validation.EXPECTED_FIXTURE_SHA256 in report
    assert "2139" in report
    assert validation.BASELINE_FORMULA in report
    for window in validation.WINDOWS:
        assert f"### Trailing {window} periods" in report
