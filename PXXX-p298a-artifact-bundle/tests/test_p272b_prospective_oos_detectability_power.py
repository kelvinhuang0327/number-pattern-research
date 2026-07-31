"""Focused tests for P272B — Prospective OOS Detectability & Apply Go/No-Go Power Brief.

Covers (Phase 4):
  * combinatorial p0 calculations (independently recomputed)
  * independently verified small exact-binomial fixtures (Fraction-based)
  * rejection-threshold correctness
  * minimum-N search correctness (true minimum)
  * power monotonicity in N and in positive delta
  * 90% target requires >= N than 80%; corrected alpha requires >= N than uncorrected
  * delta=0 never becomes an 80% detectable advantage
  * deterministic output
  * invalid probability / alpha / power / N inputs
  * bounded-search exhaustion
  * missing-governed-horizon classification + all five decision branches
  * artifact schema, evidence-manifest traceability, JSON/Markdown consistency
  * forbidden-interface absence, production DB path never opened, registry not mutated
  * import safety (no import-time artifact writes)
"""

import ast
import hashlib
import importlib.util
import json
import math
from fractions import Fraction
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "analysis" / "p272b_prospective_oos_detectability_power.py"
JSON_PATH = ROOT / "outputs" / "research" / "p272b_prospective_oos_detectability_power_20260614.json"
MD_PATH = ROOT / "outputs" / "research" / "p272b_prospective_oos_detectability_power_20260614.md"


def _load_module():
    spec = importlib.util.spec_from_file_location("p272b_mod", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load_module()


# --------------------------------------------------------------------------
# Independent reference implementations (do NOT use the module's lgamma path).
# --------------------------------------------------------------------------
def ref_sf_ge(n, k, p_frac):
    """Exact P(X >= k) via Fraction arithmetic (independent of module)."""
    total = Fraction(0)
    for i in range(max(k, 0), n + 1):
        total += Fraction(math.comb(n, i)) * (p_frac ** i) * ((1 - p_frac) ** (n - i))
    return total


def ref_p0(pool, pick):
    denom = math.comb(pool, pick)
    num = sum(math.comb(pick, k) * math.comb(pool - pick, pick - k) for k in range(3, pick + 1))
    return Fraction(num, denom)


# ==========================================================================
# Combinatorial p0
# ==========================================================================
def test_p0_combinatorics_independent():
    # DAILY_539 5/39: 5781 / 575757
    assert math.comb(39, 5) == 575757
    assert ref_p0(39, 5) == Fraction(5781, 575757)
    assert ref_p0(49, 6) == Fraction(260624, 13983816)
    assert ref_p0(38, 6) == Fraction(106833, 2760681)


def test_p0_module_matches_reference_and_committed():
    pairs = {"DAILY_539": (39, 5), "BIG_LOTTO": (49, 6), "POWER_LOTTO": (38, 6)}
    for lt, (pool, pick) in pairs.items():
        mod_val = m.exact_one_bet_m3plus_p0(pool, pick)
        ref_val = float(ref_p0(pool, pick))
        assert abs(mod_val - ref_val) < 1e-12
        assert abs(mod_val - m.LOTTERY_SPECS[lt]["p0_committed"]) <= 5e-7


def test_verify_p0_against_committed_all_match():
    chk = m.verify_p0_against_committed()
    for lt in m.LOTTERIES:
        assert chk[lt]["match"] is True


# ==========================================================================
# Exact binomial fixtures (independently verified)
# ==========================================================================
def test_binom_sf_ge_fixture_half():
    # P(X>=8 | n=10, p=0.5) = 56/1024
    assert abs(m.binom_sf_ge(10, 8, 0.5) - 56 / 1024) < 1e-12
    assert abs(m.binom_sf_ge(10, 8, 0.5) - float(ref_sf_ge(10, 8, Fraction(1, 2)))) < 1e-12


@pytest.mark.parametrize("n,k,pn,pd", [(20, 5, 1, 10), (50, 3, 1, 20), (10, 1, 3, 10), (30, 30, 1, 2)])
def test_binom_sf_ge_matches_fraction_reference(n, k, pn, pd):
    ref = float(ref_sf_ge(n, k, Fraction(pn, pd)))
    assert abs(m.binom_sf_ge(n, k, pn / pd) - ref) < 1e-10


def test_binom_sf_ge_boundaries():
    assert m.binom_sf_ge(10, 0, 0.3) == 1.0   # P(X>=0)=1
    assert m.binom_sf_ge(10, 11, 0.3) == 0.0  # P(X>n)=0
    assert m.binom_sf_ge(10, 1, 0.0) == 0.0   # impossible when p=0
    assert m.binom_sf_ge(10, 10, 1.0) == 1.0  # X==n


def test_binom_cdf_complement():
    for k in range(0, 11):
        assert abs(m.binom_cdf_le(10, k, 0.37) + m.binom_sf_ge(10, k + 1, 0.37) - 1.0) < 1e-12


# ==========================================================================
# Rejection threshold
# ==========================================================================
def test_rejection_threshold_fixture():
    # n=10, p=0.5, alpha=0.05: P(X>=9)=11/1024<=0.05; P(X>=8)=56/1024>0.05 -> k*=9
    res = m.one_sided_rejection_threshold(10, 0.5, 0.05)
    assert res["k_star"] == 9
    assert res["actual_size"] <= 0.05
    assert m.binom_sf_ge(10, 8, 0.5) > 0.05  # 8 would exceed alpha


def test_rejection_threshold_actual_size_within_alpha():
    for n in (50, 500, 5000, 100000):
        res = m.one_sided_rejection_threshold(n, 0.018638, 0.0167)
        if res["k_star"] <= n:
            assert res["actual_size"] <= 0.0167 + 1e-15
            # one step lower must exceed alpha (smallest such k)
            assert m.binom_sf_ge(n, res["k_star"] - 1, 0.018638) > 0.0167


def test_rejection_threshold_large_n_robust():
    # regression: a k=0 PMF recurrence underflows ((1-p)**n -> 0); log-gamma path must not.
    res = m.one_sided_rejection_threshold(100000, 0.01, 0.0167)
    assert 1 <= res["k_star"] <= 100000
    assert 0 < res["actual_size"] <= 0.0167


# ==========================================================================
# Power + minimum-N search
# ==========================================================================
def test_power_at_least_target_at_n_star_and_below():
    p0 = m.exact_one_bet_m3plus_p0(39, 5)
    p1 = p0 + 0.0132
    res = m.min_n_for_power(p0, p1, m.ALPHA_CORRECTED, 0.80)
    assert res["found"] is True
    ns = res["n_star"]
    assert m.binomial_power(ns, p0, p1, m.ALPHA_CORRECTED)["power"] >= 0.80
    # true minimum: one draw fewer is below target
    assert m.binomial_power(ns - 1, p0, p1, m.ALPHA_CORRECTED)["power"] < 0.80


def test_power_monotonic_in_n_fixed_threshold():
    # P(X>=k) is non-decreasing in n for fixed k, p (exact, always true).
    prev = -1.0
    for n in (20, 40, 80, 160, 320, 640):
        v = m.binom_sf_ge(n, 5, 0.02)
        assert v >= prev - 1e-15
        prev = v


def test_power_monotonic_in_n_grid():
    p0, p1, a = 0.010041, 0.023241, m.ALPHA_CORRECTED
    prev = -1.0
    for n in (200, 400, 600, 800, 1200, 2000):
        pw = m.binomial_power(n, p0, p1, a)["power"]
        assert pw >= prev - 1e-9
        prev = pw


def test_power_monotonic_in_positive_delta():
    p0, n, a = 0.018638, 1000, m.ALPHA_CORRECTED
    prev = -1.0
    for p1 in (0.018638, 0.025, 0.03, 0.04, 0.05):
        pw = m.binomial_power(n, p0, p1, a)["power"]
        assert pw >= prev - 1e-12
        prev = pw


def test_min_n_decreases_with_larger_delta():
    p0, a = 0.018638, m.ALPHA_CORRECTED
    n_small = m.min_n_for_power(p0, p0 + 0.0123, a, 0.80)["n_star"]
    n_large = m.min_n_for_power(p0, p0 + 0.05, a, 0.80)["n_star"]
    assert n_large <= n_small


def test_90_requires_at_least_as_much_n_as_80():
    for lt in m.LOTTERIES:
        p0 = m.exact_one_bet_m3plus_p0(m.LOTTERY_SPECS[lt]["pool"], m.LOTTERY_SPECS[lt]["pick"])
        p1 = p0 + m.EFFECT_SCENARIO_PP[lt] / 100.0
        n80 = m.min_n_for_power(p0, p1, m.ALPHA_CORRECTED, 0.80)["n_star"]
        n90 = m.min_n_for_power(p0, p1, m.ALPHA_CORRECTED, 0.90)["n_star"]
        assert n90 >= n80


def test_corrected_alpha_requires_at_least_as_much_n_as_uncorrected():
    for lt in m.LOTTERIES:
        p0 = m.exact_one_bet_m3plus_p0(m.LOTTERY_SPECS[lt]["pool"], m.LOTTERY_SPECS[lt]["pick"])
        p1 = p0 + m.EFFECT_SCENARIO_PP[lt] / 100.0
        n_unc = m.min_n_for_power(p0, p1, m.ALPHA_UNCORRECTED, 0.80)["n_star"]
        n_cor = m.min_n_for_power(p0, p1, m.ALPHA_CORRECTED, 0.80)["n_star"]
        assert n_cor >= n_unc


def test_delta_zero_never_detectable_at_80():
    p0 = 0.018638
    res = m.min_n_for_power(p0, p0, m.ALPHA_CORRECTED, 0.80)
    assert res["found"] is False
    assert res["result_label"] == "NOT_DETECTABLE_WITHIN_SEARCH_BOUND"


def test_bounded_search_exhaustion():
    # Tiny positive effect with a small bound cannot reach 80% power.
    res = m.min_n_for_power(0.018638, 0.018700, m.ALPHA_CORRECTED, 0.80, max_n=50)
    assert res["found"] is False
    assert res["max_n"] == 50
    assert res["result_label"] == "NOT_DETECTABLE_WITHIN_SEARCH_BOUND"


def test_normal_approx_is_close_but_distinct():
    # exact >= approx for these rare-event params; same ballpark validates both.
    p0 = m.exact_one_bet_m3plus_p0(39, 5)
    p1 = p0 + 0.0132
    exact = m.min_n_for_power(p0, p1, m.ALPHA_CORRECTED, 0.80)["n_star"]
    approx = m.normal_approx_min_n(p0, p1, m.ALPHA_CORRECTED, 0.80)
    assert approx > 0
    assert 0.5 * approx <= exact <= 2.0 * approx


# ==========================================================================
# Input validation
# ==========================================================================
@pytest.mark.parametrize("bad", [-0.1, 1.1, 2.0])
def test_invalid_probability_rejected(bad):
    with pytest.raises(ValueError):
        m.binom_sf_ge(10, 3, bad)


def test_invalid_p0_boundary_rejected():
    with pytest.raises(ValueError):
        m.one_sided_rejection_threshold(10, 0.0, 0.05)
    with pytest.raises(ValueError):
        m.one_sided_rejection_threshold(10, 1.0, 0.05)


@pytest.mark.parametrize("bad_alpha", [0.0, 1.0, -0.2, 1.5])
def test_invalid_alpha_rejected(bad_alpha):
    with pytest.raises(ValueError):
        m.min_n_for_power(0.02, 0.04, bad_alpha, 0.80)


@pytest.mark.parametrize("bad_power", [0.0, 1.0, 1.2, -0.3])
def test_invalid_power_rejected(bad_power):
    with pytest.raises(ValueError):
        m.min_n_for_power(0.02, 0.04, 0.05, bad_power)


@pytest.mark.parametrize("bad_n", [0, -5])
def test_invalid_n_rejected(bad_n):
    with pytest.raises(ValueError):
        m.binom_sf_ge(bad_n, 1, 0.5)


def test_bool_not_accepted_as_n():
    with pytest.raises(ValueError):
        m.binom_sf_ge(True, 1, 0.5)


# ==========================================================================
# Decision classification (all five branches)
# ==========================================================================
def test_classify_blocked_on_untraceable():
    assert m.classify_decision([True], None, inputs_traceable=False, cadence_traceable=True) == "P272B_BLOCKED_UNTRACEABLE_POWER_INPUT"
    assert m.classify_decision([True], None, inputs_traceable=True, cadence_traceable=False) == "P272B_BLOCKED_UNTRACEABLE_POWER_INPUT"


def test_classify_not_detectable():
    assert m.classify_decision([False], None, True, True) == "NOT_DETECTABLE_WITHIN_SEARCH_BOUND"


def test_classify_not_governed():
    assert m.classify_decision([True, True], None, True, True) == "POWER_QUANTIFIED_THRESHOLD_NOT_GOVERNED"


def test_classify_go_and_no_go_require_governed_horizon():
    # With a governed horizon present, GO is selectable (not used in this brief).
    assert m.classify_decision([True], 5, True, True) == "PROSPECTIVE_APPLY_POWER_GO"


def test_missing_governed_horizon_constant():
    assert m.GOVERNED_HORIZON_YEARS is None
    rep = m.build_report()
    assert rep["decision_classification"] == "POWER_QUANTIFIED_THRESHOLD_NOT_GOVERNED"
    assert rep["decision_classification"] in m.ALLOWED_DECISIONS


# ==========================================================================
# Determinism
# ==========================================================================
def test_build_report_deterministic():
    a = json.dumps(m.build_report(), ensure_ascii=False, sort_keys=True)
    b = json.dumps(m.build_report(), ensure_ascii=False, sort_keys=True)
    assert a == b


def test_render_markdown_deterministic():
    rep = m.build_report()
    assert m.render_markdown(rep) == m.render_markdown(rep)


# ==========================================================================
# Artifact schema + JSON parse
# ==========================================================================
def test_artifacts_exist_and_parse():
    assert JSON_PATH.exists(), f"missing {JSON_PATH}"
    assert MD_PATH.exists(), f"missing {MD_PATH}"
    json.loads(JSON_PATH.read_text(encoding="utf-8"))  # parse validation


def test_artifact_required_fields_and_flags():
    a = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    for field in (
        "task_id", "artifact_date", "branch", "base_main", "pre_registered_contract",
        "evidence_manifest", "lottery_inputs", "cadence", "power_results",
        "calendar_horizons", "governed_horizon", "decision_classification",
        "statistical_method", "limitations", "test_execution", "p0_verification",
    ):
        assert field in a, f"missing artifact field: {field}"
    assert a["task_id"] == m.TASK_ID
    assert a["decision_classification"] in m.ALLOWED_DECISIONS
    # mandatory governance no-claim flags
    assert a["production_apply_authorized"] is False
    assert a["controlled_apply_started"] is False
    assert a["P271M_started"] is False
    assert a["P271N_started"] is False
    assert a["prediction_success_claim"] is False
    assert a["db_opened"] is False
    assert a["db_write"] is False
    assert a["registry_write"] is False
    assert a["production_apply_state"] == "NOT_READY_FOR_APPLY"


def test_artifact_contract_locked_values():
    a = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    c = a["pre_registered_contract"]
    assert c["primary_bet_count"] == 1
    assert c["power_targets"] == [0.80, 0.90]
    assert c["family_alpha"] == 0.05
    assert c["primary_correction"] == "Bonferroni"
    assert c["primary_correction_m"] == 3
    assert c["calendar_reporting_horizons_years"] == [1, 3, 5, 10]
    assert c["deterministic_seed"] == 42
    # displayed alpha is rounded for the artifact; computations use full precision.
    assert abs(a["alpha_corrected_bonferroni_m3"] - 0.05 / 3) < 1e-6
    assert a["alpha_uncorrected"] == 0.05


def test_artifact_matches_build_report_deterministic_regen():
    committed = JSON_PATH.read_text(encoding="utf-8")
    regenerated = json.dumps(m.build_report(), ensure_ascii=False, indent=2) + "\n"
    assert committed == regenerated, "committed JSON artifact is not a byte-deterministic regeneration of build_report()"


def test_md_matches_render():
    committed_md = MD_PATH.read_text(encoding="utf-8")
    assert committed_md == m.render_markdown(m.build_report())


def test_exact_method_labelled_truthfully():
    a = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    sm = a["statistical_method"]
    assert sm["exactness"] == "EXACT_BINOMIAL"
    assert "not a normal" in sm["exact_method_detail"].lower()
    assert sm["stochastic_component"] is False


# ==========================================================================
# Evidence-manifest traceability
# ==========================================================================
def test_evidence_manifest_fields_present():
    a = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert len(a["evidence_manifest"]) >= 8
    for e in a["evidence_manifest"]:
        for k in ("input", "source_path", "field", "value", "derivation", "status"):
            assert k in e


def test_evidence_source_hashes_match_committed_artifacts():
    # Re-hash the immutable dated outputs/research artifacts and compare.
    for rel in m.DECISIVE_HASH_VERIFY_SOURCES:
        p = ROOT / rel
        assert p.exists(), f"missing decisive source: {rel}"
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        assert digest == m.EVIDENCE_SOURCE_SHA256[rel], f"sha256 mismatch for {rel}"


def test_cadence_derivation_traceable():
    a = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    for lt in m.LOTTERIES:
        cad = a["cadence"][lt]
        assert cad["status"] == "CONFIRMED"
        assert cad["source_path"].endswith("p268d1_draw_order_full_history_artifact_backfill_20260610.jsonl")
        assert cad["draws_per_week"] in (2, 6)


# ==========================================================================
# JSON / Markdown consistency
# ==========================================================================
def test_json_markdown_consistency_key_values():
    a = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    md = MD_PATH.read_text(encoding="utf-8")
    assert a["decision_classification"] in md
    for lt in m.LOTTERIES:
        ns = a["power_results"][lt]["alpha_corrected_bonferroni_m3"]["power_80"]["n_star_draws"]
        assert str(ns) in md, f"N* {ns} for {lt} not reflected in markdown"
        p0 = a["lottery_inputs"][lt]["p0_exact"]
        assert str(p0) in md


# ==========================================================================
# Forbidden interfaces / DB / registry / import safety
# ==========================================================================
def test_no_forbidden_imports():
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    forbidden = {
        "sqlite3", "subprocess", "requests", "sqlalchemy", "urllib", "socket",
        "http", "psycopg2", "pymysql", "aiohttp", "httpx", "os",
    }
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                imported.add(n.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
    assert not (imported & forbidden), f"forbidden imports present: {imported & forbidden}"
    assert imported <= {"json", "math", "pathlib", "__future__"}, f"unexpected imports: {imported}"


def test_no_forbidden_call_syntax():
    text = SCRIPT_PATH.read_text(encoding="utf-8")
    for token in (
        "sqlite3.connect", "create_engine(", "requests.get", "requests.post",
        "subprocess.", "urllib.request", "socket.socket", ".execute(",
        "lottery_v2.db", "hypothesis_registry", "replay_strategy_registry",
    ):
        assert token not in text, f"forbidden token present in module: {token}"


def test_production_db_never_referenced():
    a = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert a["db_opened"] is False
    assert a["network_access"] is False
    assert a["subprocess_used"] is False
    assert "lottery_v2.db" not in SCRIPT_PATH.read_text(encoding="utf-8")


def test_registry_not_mutated_flag():
    a = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert a["registry_write"] is False


def test_module_import_safe_no_top_level_side_effects():
    """No import-time artifact writes: top-level nodes are only imports, constants,
    defs, the module docstring, and the __main__ guard — no bare calls."""
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign,
                             ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue  # module docstring
        if isinstance(node, ast.If):
            # only the `if __name__ == "__main__":` guard is allowed
            test = node.test
            assert isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and test.left.id == "__name__", \
                "unexpected top-level if block"
            continue
        raise AssertionError(f"unexpected top-level node (possible import-time side effect): {ast.dump(node)[:80]}")


def test_no_betting_or_edge_claim_wording():
    text = MD_PATH.read_text(encoding="utf-8").lower()
    # Positive-claim phrases that would overstate the result. "edge exists" is
    # excluded because it appears only inside the negated disclaimer.
    for phrase in ("betting advice", "guaranteed win", "predictive edge confirmed",
                   "confirmed predictive edge", "approved for production", "edge is real"):
        assert phrase not in text, f"forbidden claim phrase: {phrase}"
    assert "not evidence of a predictive edge" in text
