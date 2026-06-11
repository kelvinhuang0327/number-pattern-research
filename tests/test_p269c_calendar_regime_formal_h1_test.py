"""
Tests for P269C: Calendar Regime Formal H1 Test.

Validates the artifacts and the Hypothesis Registry entry — no live-DB
dependency (artifact/registry files only), per the RO-DB WAL guidance.
"""
import json
import pathlib

REPO_ROOT = pathlib.Path(__file__).parent.parent
ARTIFACT_JSON = REPO_ROOT / "outputs" / "research" / "p269c_calendar_regime_formal_h1_test_20260611.json"
ARTIFACT_MD = REPO_ROOT / "outputs" / "research" / "p269c_calendar_regime_formal_h1_test_20260611.md"
REGISTRY = REPO_ROOT / "lottery_api" / "data" / "hypothesis_registry.jsonl"

HYPOTHESIS_ID = "HR-P269C-H1-DAILY539-SATURDAY-M3PLUS-001"


def _load_json():
    with open(ARTIFACT_JSON, encoding="utf-8") as f:
        return json.load(f)


def _registry_entries():
    with open(REGISTRY, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


# ---------------------------------------------------------------------------
# Artifact existence
# ---------------------------------------------------------------------------

def test_json_artifact_exists():
    assert ARTIFACT_JSON.exists(), f"JSON artifact missing: {ARTIFACT_JSON}"


def test_json_artifact_valid():
    data = _load_json()
    assert isinstance(data, dict)
    assert len(data) > 5


def test_markdown_artifact_exists():
    assert ARTIFACT_MD.exists(), f"Markdown artifact missing: {ARTIFACT_MD}"
    assert len(ARTIFACT_MD.read_text(encoding="utf-8")) > 500


# ---------------------------------------------------------------------------
# Hypothesis Registry
# ---------------------------------------------------------------------------

def test_registry_contains_entry_exactly_once():
    entries = [e for e in _registry_entries()
               if e.get("hypothesis_id") == HYPOTHESIS_ID]
    assert len(entries) == 1, (
        f"registry must contain {HYPOTHESIS_ID} exactly once, found {len(entries)}"
    )


def test_registry_status_pre_registered():
    entry = next(e for e in _registry_entries()
                 if e.get("hypothesis_id") == HYPOTHESIS_ID)
    assert entry["status"] == "PRE_REGISTERED_BEFORE_TEST"


def test_registry_entry_locked_parameters():
    entry = next(e for e in _registry_entries()
                 if e.get("hypothesis_id") == HYPOTHESIS_ID)
    assert entry["task_id"] == "P269C"
    assert entry["lottery"] == "DAILY_539"
    assert entry["primary_game"] == "DAILY_539"
    assert entry["candidate"] == "C05 draw weekday / schedule regime"
    assert entry["permutations"] == 10000
    assert entry["seed"] == 42
    assert entry["alpha"] == 0.01
    assert entry["statistical_test"] == "two-tailed permutation test"
    assert entry["c06_secondary"] == "NOT_RUN"
    assert entry["no_db_write"] is True
    assert entry["no_strategy"] is True
    assert entry["no_hit_rate_improvement_claim"] is True
    assert "P269B" in entry["source_design_artifact"].upper() or \
           "p269b" in entry["source_design_artifact"]


def test_registry_append_before_computation():
    entry = next(e for e in _registry_entries()
                 if e.get("hypothesis_id") == HYPOTHESIS_ID)
    data = _load_json()
    registered_at = entry["registered_at"]
    generated_at = data["generated_at"]
    assert registered_at < generated_at, (
        f"registry append ({registered_at}) must precede artifact "
        f"generation ({generated_at})"
    )
    assert data["registry_append"]["registered_before_computation"] is True


# ---------------------------------------------------------------------------
# Scope: DAILY_539, C05 only, no scans
# ---------------------------------------------------------------------------

def test_daily539_only():
    data = _load_json()
    method = data["h1_method"]
    assert method["primary_game"] == "DAILY_539"
    raw = json.dumps(data)
    # No other lottery may appear as a tested target
    assert "POWER_LOTTO" not in raw
    assert "BIG_LOTTO" not in raw


def test_c05_saturday_vs_weekday_only():
    data = _load_json()
    method = data["h1_method"]
    assert "C05" in method["candidate"]
    assert "Saturday" in method["hypothesis"]
    assert "Mon-Fri" in method["hypothesis"]


def test_c06_not_run():
    data = _load_json()
    assert data["c06_secondary"] == "NOT_RUN"


def test_no_scans_performed():
    data = _load_json()
    assert "NONE" in data["scans_performed"]


# ---------------------------------------------------------------------------
# Test parameters
# ---------------------------------------------------------------------------

def test_permutations_and_seed():
    data = _load_json()
    assert data["h1_method"]["permutations"] == 10000
    assert data["h1_method"]["seed"] == 42
    assert data["result"]["permutations"] == 10000
    assert data["result"]["seed"] == 42


def test_alpha():
    data = _load_json()
    assert data["h1_method"]["alpha"] == 0.01


def test_p_value_present_and_valid():
    data = _load_json()
    p = data["result"]["p_value"]
    assert isinstance(p, (int, float))
    assert 0.0 <= p <= 1.0


def test_result_completeness():
    data = _load_json()
    r = data["result"]
    for field in ("n_saturday", "n_weekday", "m3plus_events_saturday",
                  "m3plus_events_weekday", "saturday_rate", "weekday_rate",
                  "rate_diff_sat_minus_weekday", "abs_statistic", "p_value"):
        assert field in r, f"result missing field '{field}'"
    assert r["n_saturday"] > 0
    assert r["n_weekday"] > 0


def test_classification_consistent_with_gate():
    data = _load_json()
    r = data["result"]
    h1 = data["h1_classification"]
    if r["p_value"] < 0.01 and r["saturday_rate"] > r["weekday_rate"]:
        assert h1 == "H1_PRIMARY_PASS_POSITIVE"
    elif r["p_value"] < 0.01:
        assert h1 == "H1_PRIMARY_SIGNIFICANT_NEGATIVE"
    else:
        assert h1 == "H1_PRIMARY_FAIL"


# ---------------------------------------------------------------------------
# Non-claims
# ---------------------------------------------------------------------------

def test_no_db_write():
    data = _load_json()
    assert data["explicit_non_claims"]["no_db_write"] is True


def test_no_strategy_no_picks():
    data = _load_json()
    claims = data["explicit_non_claims"]
    assert claims["no_strategy"] is True
    assert claims["no_picks"] is True
    assert claims["no_numbers_generated"] is True


def test_no_hit_rate_improvement_claim():
    data = _load_json()
    assert data["explicit_non_claims"]["no_hit_rate_improvement_claim"] is True


def test_no_claim_markers_in_markdown():
    content = ARTIFACT_MD.read_text(encoding="utf-8")
    forbidden = ["recommended numbers", "betting strategy", "place a bet",
                 "strategy is authorized", "win rate improvement"]
    lower = content.lower()
    for phrase in forbidden:
        assert phrase not in lower, f"forbidden phrase: '{phrase}'"
    assert "does not constitute" in lower or "not betting advice" in lower


# ---------------------------------------------------------------------------
# Boundaries
# ---------------------------------------------------------------------------

def test_inherited_boundaries_present():
    data = _load_json()
    b = data["inherited_boundaries"]
    assert b["p269a_lite_no_go"]["status"] == "NO_GO"
    assert "ALREADY_NULL" in b["p268_draw_order"]
    assert "p269b" in b["p269b_ready_for_registry"]["design_artifact"]


def test_low_plausibility_warning_present():
    data = _load_json()
    assert "LOW" in data["low_plausibility_warning"]


# ---------------------------------------------------------------------------
# Final classification
# ---------------------------------------------------------------------------

def test_final_classification_allowed():
    allowed = {
        "P269C_CALENDAR_REGIME_FORMAL_H1_COMPLETE_PRIMARY_PASS_POSITIVE",
        "P269C_CALENDAR_REGIME_FORMAL_H1_COMPLETE_PRIMARY_FAIL",
        "P269C_CALENDAR_REGIME_FORMAL_H1_COMPLETE_SIGNIFICANT_NEGATIVE",
        "P269C_CALENDAR_REGIME_FORMAL_H1_BLOCKED_METRIC_UNAVAILABLE",
        "P269C_CALENDAR_REGIME_FORMAL_H1_BLOCKED_STATE_MISMATCH",
        "P269C_CALENDAR_REGIME_FORMAL_H1_BLOCKED_SCOPE_CONFLICT",
    }
    data = _load_json()
    assert data["final_classification"] in allowed


def test_final_classification_matches_h1():
    data = _load_json()
    h1 = data["h1_classification"]
    fc = data["final_classification"]
    mapping = {
        "H1_PRIMARY_PASS_POSITIVE": "PRIMARY_PASS_POSITIVE",
        "H1_PRIMARY_FAIL": "PRIMARY_FAIL",
        "H1_PRIMARY_SIGNIFICANT_NEGATIVE": "SIGNIFICANT_NEGATIVE",
    }
    assert fc.endswith(mapping[h1])
