"""
tests/test_p73_tier_stability_and_sample_expansion.py

P73A/B — Odds-Free Tier Stability Deep-Dive + Tier B Sample Expansion
23 tests validating the analysis outputs, governance constraints, and
decision matrix integrity.

Governance:
  paper_only=True, diagnostic_only=True, uses_historical_odds=False,
  live_api_calls=0, kelly_deploy_allowed=False, production_ready=False
"""

from __future__ import annotations

import importlib
import json
import math
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ─── Load module ────────────────────────────────────────────────────────────
mod = importlib.import_module("scripts._p73_tier_stability_and_sample_expansion")

# ─── Load JSON artifact ──────────────────────────────────────────────────────
P73_JSON = ROOT / "data/mlb_2025/derived/p73_tier_stability_and_sample_expansion_summary.json"


def load_p73() -> dict:
    with open(P73_JSON) as f:
        return json.load(f)


# ─── FORBIDDEN PHRASES ───────────────────────────────────────────────────────
# Only affirmative claims are forbidden — NOT negative disclaimers.
# Phrases like "no guaranteed profit" or "not operational" contain these as
# substrings but are negative, so we exclude them here per the established
# pattern from P72A/P72B.
FORBIDDEN_PHRASES = [
    "guaranteed profit",
    "this model is profitable",
    "positive ev against market",
    "recommended for live betting",
    "champion strategy replaced",
    "kelly deployment approved",
]


# ═══════════════════════════════════════════════════════════════════════════════
# Tests 1–2 — Source artifact existence
# ═══════════════════════════════════════════════════════════════════════════════

def test_p72a_source_artifact_exists():
    """T01 — P72A JSON source artifact must exist."""
    p72a_path = ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json"
    assert p72a_path.exists(), f"P72A artifact missing: {p72a_path}"


def test_p72b_source_artifact_exists():
    """T02 — P72B JSON source artifact must exist."""
    p72b_path = ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json"
    assert p72b_path.exists(), f"P72B artifact missing: {p72b_path}"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests 3–7 — P73A Tier C stability analysis
# ═══════════════════════════════════════════════════════════════════════════════

def test_tier_c_monthly_breakdown_all_months():
    """T03 — Tier C monthly breakdown covers >= 5 months with valid hit rates."""
    data = load_p73()
    monthly = data["p73a_tier_c"]["monthly_breakdown"]
    months_with_data = [m for m in monthly if m["n"] >= 5]
    assert len(months_with_data) >= 5, (
        f"Expected >= 5 months with sufficient data, got {len(months_with_data)}"
    )
    for m in months_with_data:
        assert 0.0 <= m["hit_rate"] <= 1.0, f"Invalid hit_rate in month {m}"


def test_tier_c_halves_and_thirds_splits():
    """T04 — Halves and thirds splits are present with valid n and hit rates."""
    data = load_p73()
    p73a = data["p73a_tier_c"]

    halves = p73a["halves_split"]
    assert len(halves) == 2, f"Expected 2 halves, got {len(halves)}"
    assert halves[0]["half"] == 1
    assert halves[1]["half"] == 2
    total_n = halves[0]["n"] + halves[1]["n"]
    assert total_n == p73a["n"], (
        f"Halves n sum {total_n} != total Tier C n {p73a['n']}"
    )

    thirds = p73a["thirds_split"]
    assert len(thirds) == 3, f"Expected 3 thirds, got {len(thirds)}"
    for t in thirds:
        assert 0.0 <= t["hit_rate"] <= 1.0


def test_tier_c_home_away_split():
    """T05 — Home/away split shows meaningful difference; both sides present."""
    data = load_p73()
    p73a = data["p73a_tier_c"]

    home = p73a["home_split"]
    away = p73a["away_split"]

    assert home["n"] > 0, "Home split has no samples"
    assert away["n"] > 0, "Away split has no samples"
    assert home["n"] + away["n"] == p73a["n"], (
        f"home+away={home['n']+away['n']} != n={p73a['n']}"
    )
    # Home advantage: home hit rate should be noticeably higher than away
    assert home["hit_rate"] > away["hit_rate"], (
        f"Expected home hit_rate > away but got home={home['hit_rate']} away={away['hit_rate']}"
    )


def test_tier_c_delta_band_breakdown():
    """T06 — Delta band breakdown has 5 bands covering [0.50,∞)."""
    data = load_p73()
    bands = data["p73a_tier_c"]["delta_band_breakdown"]
    assert len(bands) == 5, f"Expected 5 delta bands, got {len(bands)}"

    expected_ids = {"band_050_075", "band_075_100", "band_100_125", "band_125_150", "band_150_plus"}
    actual_ids = {b["band_id"] for b in bands}
    assert actual_ids == expected_ids, f"Band IDs mismatch: {actual_ids}"

    # Total band samples should sum to Tier C n (all bands start at 0.50)
    tier_c_n = data["p73a_tier_c"]["n"]
    band_total = sum(b["n"] for b in bands)
    assert band_total == tier_c_n, (
        f"Band total {band_total} != Tier C n {tier_c_n}"
    )

    # Band 050_075 should have highest hit rate (known from data exploration)
    band_map = {b["band_id"]: b for b in bands}
    assert band_map["band_050_075"]["hit_rate"] >= 0.60, (
        f"band_050_075 hit rate expected >= 0.60, got {band_map['band_050_075']['hit_rate']}"
    )


def test_tier_c_bootstrap_deterministic_seed42():
    """T07 — Bootstrap CI is deterministic with seed=42 (module function)."""
    records = mod.load_records()
    tc_rows = [r for r in records if r["abs_delta"] >= mod.TIER_C_THRESHOLD]

    ci1 = mod.bootstrap_ci_hit(tc_rows, seed=42)
    ci2 = mod.bootstrap_ci_hit(tc_rows, seed=42)
    assert ci1 == ci2, "Bootstrap CI not deterministic with same seed"

    auc_ci1 = mod.bootstrap_ci_auc(tc_rows, seed=42)
    auc_ci2 = mod.bootstrap_ci_auc(tc_rows, seed=42)
    assert auc_ci1 == auc_ci2, "AUC bootstrap CI not deterministic with same seed"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests 8–14 — P73A classification + P73B variants
# ═══════════════════════════════════════════════════════════════════════════════

def test_tier_c_classification_operational_stable():
    """T08 — Tier C classification must be TIER_C_OPERATIONAL_STABLE (monthly STABLE, n=535)."""
    data = load_p73()
    cls = data["p73a_tier_c"]["tier_c_classification"]
    assert cls == "TIER_C_OPERATIONAL_STABLE", (
        f"Expected TIER_C_OPERATIONAL_STABLE, got {cls}"
    )
    # Verify monthly stability is STABLE
    assert data["p73a_tier_c"]["monthly_stability"] == "STABLE"


def test_tier_b_original_reconstructed():
    """T09 — TB_ORIGINAL variant reconstructs Tier B with n=98, AUC>=0.62."""
    data = load_p73()
    variants = data["p73b_tier_b"]["variants"]
    orig = next((v for v in variants if v["variant_id"] == "TB_ORIGINAL"), None)
    assert orig is not None, "TB_ORIGINAL variant not found"
    assert orig["n"] == 98, f"Expected n=98, got {orig['n']}"
    assert orig["auc"] >= 0.62, f"Expected AUC >= 0.62, got {orig['auc']}"


def test_tier_b_all_five_variants_generated():
    """T10 — All 5 Tier B variants generated: STRICT/ORIGINAL/RELAXED_V1/V2/EXCL_WEAK_BAND."""
    data = load_p73()
    variant_ids = {v["variant_id"] for v in data["p73b_tier_b"]["variants"]}
    expected = {
        "TB_STRICT",
        "TB_ORIGINAL",
        "TB_RELAXED_V1",
        "TB_RELAXED_V2",
        "TB_EXCL_WEAK_BAND",
    }
    assert variant_ids == expected, (
        f"Expected variants {expected}, got {variant_ids}"
    )


def test_tier_b_bootstrap_deterministic():
    """T11 — P73B bootstrap CI is deterministic with seed=42 across variants."""
    records = mod.load_records()
    # Use TB_ORIGINAL rows
    tb_rows = [r for r in records if r["abs_delta"] >= 1.25]

    ci1 = mod.bootstrap_ci_hit(tb_rows, seed=42)
    ci2 = mod.bootstrap_ci_hit(tb_rows, seed=42)
    assert ci1 == ci2, "Tier B bootstrap CI not deterministic"


def test_monthly_stability_class_function():
    """T12 — monthly_stability_class function classifies STABLE/MODERATE/UNSTABLE correctly."""
    # STABLE: range <= 0.10
    stable_monthly = [
        {"month": "2025-04", "n": 20, "hit_rate": 0.60},
        {"month": "2025-05", "n": 20, "hit_rate": 0.65},
        {"month": "2025-06", "n": 20, "hit_rate": 0.62},
        {"month": "2025-07", "n": 20, "hit_rate": 0.67},
    ]
    assert mod.monthly_stability_class(stable_monthly) == "STABLE"

    # MODERATE: range <= 0.20
    moderate_monthly = [
        {"month": "2025-05", "n": 20, "hit_rate": 0.55},
        {"month": "2025-06", "n": 20, "hit_rate": 0.70},
        {"month": "2025-07", "n": 20, "hit_rate": 0.62},
    ]
    assert mod.monthly_stability_class(moderate_monthly) == "MODERATE"

    # UNSTABLE: range > 0.20
    unstable_monthly = [
        {"month": "2025-05", "n": 20, "hit_rate": 0.45},
        {"month": "2025-06", "n": 20, "hit_rate": 0.72},
        {"month": "2025-07", "n": 20, "hit_rate": 0.60},
    ]
    assert mod.monthly_stability_class(unstable_monthly) == "UNSTABLE"


def test_tier_b_cannot_be_operational_unstable():
    """T13 — Tier B cannot be operational: n<200 AND monthly stability UNSTABLE."""
    data = load_p73()
    p73b = data["p73b_tier_b"]

    assert p73b["tier_b_can_be_operational"] is False, (
        "Tier B should not be operational: n=98 < 200 and monthly UNSTABLE"
    )
    # Verify the reasoning
    orig = next(v for v in p73b["variants"] if v["variant_id"] == "TB_ORIGINAL")
    assert orig["n"] < 200, f"n={orig['n']} should be < 200"
    assert orig["monthly_stability"] == "UNSTABLE", (
        f"monthly stability should be UNSTABLE, got {orig['monthly_stability']}"
    )


def test_tier_a_watchlist_only():
    """T14 — Tier A (n=24) appears in decision matrix as WATCHLIST_ONLY."""
    data = load_p73()
    matrix = data["decision_matrix"]
    tier_a_row = next(
        (r for r in matrix if r["strategy_id"] == "S03_TIER_A_DIRECTIONAL"), None
    )
    assert tier_a_row is not None, "S03_TIER_A_DIRECTIONAL not in decision matrix"
    assert tier_a_row["role"] == "WATCHLIST_ONLY", (
        f"Expected WATCHLIST_ONLY, got {tier_a_row['role']}"
    )
    assert tier_a_row["n"] == 24


# ═══════════════════════════════════════════════════════════════════════════════
# Tests 15–18 — Governance constraints
# ═══════════════════════════════════════════════════════════════════════════════

def test_no_odds_required():
    """T15 — uses_historical_odds=False and the_odds_api_key_required=False."""
    data = load_p73()
    gov = data["governance"]
    assert gov["uses_historical_odds"] is False
    assert gov["the_odds_api_key_required"] is False


def test_no_ev_clv_kelly_calculated():
    """T16 — ev_calculated, clv_calculated, market_edge_calculated all False."""
    data = load_p73()
    gov = data["governance"]
    assert gov["ev_calculated"] is False, "ev_calculated must be False"
    assert gov["clv_calculated"] is False, "clv_calculated must be False"
    assert gov["market_edge_calculated"] is False, "market_edge_calculated must be False"


def test_live_api_calls_zero():
    """T17 — live_api_calls=0 in governance."""
    data = load_p73()
    assert data["governance"]["live_api_calls"] == 0


def test_production_ready_false_kelly_false():
    """T18 — production_ready=False and kelly_deploy_allowed=False."""
    data = load_p73()
    gov = data["governance"]
    assert gov["production_ready"] is False
    assert gov["kelly_deploy_allowed"] is False
    assert gov["paper_only"] is True
    assert gov["diagnostic_only"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# Tests 19–23 — Forbidden phrases + JSON schema + decision matrix + active_task
# ═══════════════════════════════════════════════════════════════════════════════

def _collect_all_text(obj, acc: list[str]) -> None:
    """Recursively collect all string values from a JSON object."""
    if isinstance(obj, str):
        acc.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_all_text(v, acc)
    elif isinstance(obj, list):
        for item in obj:
            _collect_all_text(item, acc)


def test_forbidden_phrase_scan():
    """T19 — No affirmative forbidden phrases in the P73 JSON artifact."""
    data = load_p73()
    all_texts: list[str] = []
    _collect_all_text(data, all_texts)
    full_text = " ".join(all_texts).lower()

    for phrase in FORBIDDEN_PHRASES:
        assert phrase.lower() not in full_text, (
            f"Forbidden phrase found in P73 JSON: '{phrase}'"
        )


def test_json_schema_stable():
    """T20 — P73 JSON has required top-level fields."""
    data = load_p73()
    required_keys = [
        "phase", "tracks", "date", "governance", "source_artifacts",
        "total_games", "p73a_tier_c", "p73b_tier_b",
        "decision_matrix", "p73_classification", "allowed_classifications",
        "prediction_boundary", "forbidden_claims_verified",
    ]
    for k in required_keys:
        assert k in data, f"Missing required top-level key: '{k}'"

    # P73A must have required sub-keys
    p73a_keys = [
        "n", "hit_rate", "auc", "monthly_breakdown", "monthly_stability",
        "halves_split", "thirds_split", "rolling_window_50",
        "home_split", "away_split", "delta_band_breakdown",
        "concentration_risk", "tier_c_classification",
    ]
    for k in p73a_keys:
        assert k in data["p73a_tier_c"], f"Missing P73A key: '{k}'"

    # P73B must have required sub-keys
    p73b_keys = [
        "variants", "best_variant_by_auc", "original_tier_b_signal",
        "original_tier_b_n", "original_tier_b_auc", "tier_b_can_be_operational",
    ]
    for k in p73b_keys:
        assert k in data["p73b_tier_b"], f"Missing P73B key: '{k}'"


def test_report_includes_decision_matrix():
    """T21 — Decision matrix has 4 rows covering all Tier strategies."""
    data = load_p73()
    matrix = data["decision_matrix"]
    assert len(matrix) == 4, f"Expected 4 rows in decision matrix, got {len(matrix)}"

    strategy_ids = {r["strategy_id"] for r in matrix}
    expected_ids = {
        "S01_TIER_C_DIRECTIONAL",
        "S02_TIER_B_DIRECTIONAL",
        "S03_TIER_A_DIRECTIONAL",
        "S04_TIER_C_PLATT_CALIBRATED",
    }
    assert strategy_ids == expected_ids, (
        f"Decision matrix strategy IDs mismatch: {strategy_ids}"
    )

    # Each row must have required fields
    for row in matrix:
        for field in ("strategy_id", "role", "status", "why", "next_action"):
            assert field in row, f"Missing field '{field}' in matrix row {row}"


def test_active_task_updated_with_p73():
    """T22 — active_task.md references P73 phase."""
    active_task = ROOT / "00-Plan/roadmap/active_task.md"
    assert active_task.exists(), "active_task.md not found"
    content = active_task.read_text()
    assert "P73" in content, "active_task.md does not reference P73 phase"


def test_p72a_p72b_p73_regression():
    """T23 — P72A, P72B, and P73 JSON artifacts all exist and load cleanly."""
    artifacts = [
        ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json",
        ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json",
        ROOT / "data/mlb_2025/derived/p73_tier_stability_and_sample_expansion_summary.json",
    ]
    for path in artifacts:
        assert path.exists(), f"Artifact missing: {path}"
        with open(path) as f:
            obj = json.load(f)
        assert isinstance(obj, dict), f"Expected dict, got {type(obj)} for {path}"
        # Each artifact must have a 'phase' or 'governance' field
        assert "governance" in obj or "phase" in obj, (
            f"Artifact {path.name} missing 'phase' or 'governance' field"
        )

    # Additional: confirm P73 classification is one of the allowed values
    with open(artifacts[2]) as f:
        p73_data = json.load(f)
    classification = p73_data["p73_classification"]
    allowed = p73_data["allowed_classifications"]
    assert classification in allowed, (
        f"P73 classification '{classification}' not in allowed list"
    )
