#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Targeted tests for BIG649_MEASUREMENT_EXPORT_API_UI_IMPLEMENTATION.

Covers:
  A. The deterministic, read-only measurement-export generator
     (analysis/big649_measurement_export.py).
  B. The artifact-backed read-only API route
     (GET /api/replay/big649-measurement-export in lottery_api/routes/replay.py).
  C. The static BIG649 measurement section in index.html.

Read-only: no DB writes; the generator opens the canonical DB strictly read-only.
Run with:
  PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_big649_measurement_export.py -q
"""
import asyncio
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import pytest

# --------------------------------------------------------------------------
# Paths / constants
# --------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_DIR = REPO_ROOT / "analysis"
LOTTERY_API_DIR = REPO_ROOT / "lottery_api"
ARTIFACT_PATH = REPO_ROOT / "outputs" / "research" / "big649_measurement_export_20260621.json"
INDEX_HTML = REPO_ROOT / "index.html"

EXPECTED_DIGEST = "0f4c417902dedb8882d23edad1ca16152c660656e08bc64ee22f7832c472ba2a"
EXPECTED_DB_SHA256 = "539efda5874b08f7b7e25b36cd0c70e4d4d582c8df9541eec73eaa0e373650d2"
CANONICAL_DB_PATH = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db"

OUTPUT_FILES = [
    "frozen_strategy_family",
    "canonical_target_windows",
    "per_strategy_ticket_level_distribution",
    "per_strategy_target_level_distribution",
    "per_strategy_prize_aware_distribution",
    "per_strategy_redundancy_diagnostics",
    "pairwise_ticket_overlap_diagnostics",
    "frozen_measurement_contract",
    "big649_measurement_export_schema",
]
STRATEGIES = [
    "bet2_fourier_expansion_biglotto",
    "biglotto_deviation_2bet",
    "biglotto_echo_aware_3bet",
    "biglotto_triple_strike",
    "biglotto_ts3_markov_4bet_w30",
    "cold_complement_biglotto",
    "coldpool15_biglotto",
    "fourier30_markov30_biglotto",
    "markov_2bet_biglotto",
    "markov_single_biglotto",
    "ts3_regime_3bet",
]
API_WINDOWS = ["all_reference", "recent_750", "recent_300", "recent_50"]
WINDOW_MAP = {
    "all_reference": "REFERENCE_ALL_ELIGIBLE",
    "recent_750": "RECENT_750",
    "recent_300": "RECENT_300",
    "recent_50": "RECENT_50",
}
SCOPES = ["ticket_slot", "target_level", "prize_aware", "redundancy", "pairwise_overlap"]

# --------------------------------------------------------------------------
# Module imports (generator + route), with graceful guards
# --------------------------------------------------------------------------
for _p in (str(REPO_ROOT), str(ANALYSIS_DIR), str(LOTTERY_API_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import big649_measurement_export as gen  # noqa: E402  (analysis dir on sys.path)

try:
    from routes import replay as replay_mod  # noqa: E402
    _HAVE_REPLAY = True
except Exception:  # pragma: no cover - depends on fastapi availability
    replay_mod = None
    _HAVE_REPLAY = False

_DB_AVAILABLE = os.path.exists(CANONICAL_DB_PATH)
requires_db = pytest.mark.skipif(
    not _DB_AVAILABLE, reason=f"canonical DB not present at {CANONICAL_DB_PATH}"
)
requires_replay = pytest.mark.skipif(not _HAVE_REPLAY, reason="fastapi/replay route unavailable")


def _canon(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT_PATH.exists(), f"artifact missing: {ARTIFACT_PATH}"
    with ARTIFACT_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def html_text():
    assert INDEX_HTML.exists(), f"index.html missing: {INDEX_HTML}"
    return INDEX_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def section(html_text):
    m = re.search(
        r"<!-- ===== BIG649 MEASUREMENT.*?<!-- ===== END BIG649 MEASUREMENT =====",
        html_text, re.DOTALL,
    )
    assert m, "BIG649 measurement section not found in index.html"
    return m.group(0)


# ==========================================================================
# A. Generator
# ==========================================================================
def test_artifact_is_valid_json_object(artifact):
    assert isinstance(artifact, dict)
    assert isinstance(artifact.get("payload"), dict)


def test_artifact_has_nine_subpayloads(artifact):
    assert sorted(artifact["payload"].keys()) == sorted(OUTPUT_FILES)


def test_artifact_canonical_digest_matches_frozen_contract(artifact):
    assert artifact["canonical_payload_digest"] == EXPECTED_DIGEST
    recomputed = hashlib.sha256(
        _canon({k: artifact["payload"][k] for k in OUTPUT_FILES}).encode("utf-8")
    ).hexdigest()
    assert recomputed == EXPECTED_DIGEST


def test_artifact_lexical_strategy_family(artifact):
    fam = artifact["payload"]["frozen_strategy_family"]
    assert fam["strategy_family_size"] == 11
    assert fam["strategy_order_lexical"] == STRATEGIES


def test_artifact_endpoint_support_semantics(artifact):
    s = artifact["endpoint_support_status"]
    assert s["EXACT_PRIZE_TIER"] == "PARTIALLY_SUPPORTED"
    assert s["PAYOUT_EV_ROI"] == "UNSUPPORTED"
    for k in ("MAIN_HIT_DISTRIBUTION_M0_M6", "CUMULATIVE_M1_PLUS_TO_M6_PLUS",
              "SPECIAL_HIT", "M2_AND_SPECIAL", "LOCAL_PRIZE_AWARE_V1_ANY_WIN"):
        assert s[k] == "SUPPORTED"
    # schema sub-payload carries the same semantics
    assert artifact["payload"]["big649_measurement_export_schema"][
        "endpoint_support_status"]["EXACT_PRIZE_TIER"] == "PARTIALLY_SUPPORTED"


def test_artifact_db_anchor(artifact):
    a = artifact["source_anchor"]
    assert a["db_sha256"] == EXPECTED_DB_SHA256
    assert a["wal_size_bytes"] == 0
    assert a["quick_check"] == "ok"
    assert isinstance(a["size_bytes"], int) and a["size_bytes"] > 0
    assert "mode=ro" in a["access_mode"]


def test_artifact_has_no_nondeterministic_or_promotional_top_level_fields(artifact):
    # Determinism: no timestamp / seed / randomness baked into the committed artifact.
    forbidden = ("generated_at", "timestamp", "created_at", "seed", "random_seed", "nonce")
    for k in artifact.keys():
        assert k.lower() not in forbidden, f"unexpected non-deterministic field: {k}"
    # No ranking / recommendation / payout / ROI VALUE field at the top level
    # (PAYOUT_EV_ROI=UNSUPPORTED is a safety label inside endpoint_support_status, allowed).
    assert "ranking" not in artifact and "recommendation" not in artifact
    assert "payout" not in artifact and "roi" not in artifact and "p_value" not in artifact


def test_artifact_window_definitions(artifact):
    wd = artifact["window_definitions"]
    assert set(wd.keys()) == set(WINDOW_MAP.values())
    assert wd["REFERENCE_ALL_ELIGIBLE"]["is_reference_only"] is True
    assert wd["REFERENCE_ALL_ELIGIBLE"]["target_count"] == 1531
    for internal in ("RECENT_750", "RECENT_300", "RECENT_50"):
        assert wd[internal]["is_reference_only"] is False
    assert wd["RECENT_750"]["target_count"] == 750
    assert wd["RECENT_300"]["target_count"] == 300
    assert wd["RECENT_50"]["target_count"] == 50


def test_artifact_missing_coverage_preserved_not_imputed(artifact):
    # At least one window must have PARTIAL coverage with a positive missing count,
    # and rates must be null (not 0) only when the denominator is 0 — never imputed.
    tgt = artifact["payload"]["per_strategy_target_level_distribution"]["by_strategy"]
    saw_partial = False
    for sid, by_win in tgt.items():
        for win, cell in by_win.items():
            assert cell["window_target_count"] - cell["covered_target_count"] == cell["missing_target_count"]
            if cell["coverage_status"] == "PARTIAL":
                saw_partial = True
                assert cell["missing_target_count"] > 0
    assert saw_partial, "expected at least one PARTIAL coverage cell"


@requires_db
def test_generator_uses_readonly_connection():
    import sqlite3
    con = gen.connect_ro(gen.DB_PATH)
    try:
        assert int(con.execute("PRAGMA query_only").fetchone()[0]) == 1
        with pytest.raises(sqlite3.OperationalError):
            con.execute("CREATE TABLE _big649_probe_should_fail (x INTEGER)")
    finally:
        con.close()


@requires_db
def test_generator_validates_db_anchor():
    stat = gen._db_stat(gen.DB_PATH)
    assert stat["sha256"] == EXPECTED_DB_SHA256
    assert stat["wal_size_bytes"] == 0


@requires_db
def test_generator_deterministic_and_reproduces_committed(tmp_path):
    out1 = tmp_path / "run1.json"
    out2 = tmp_path / "run2.json"
    export1, dig1 = gen.build_export()
    gen.write_export(export1, str(out1))
    export2, dig2 = gen.build_export()
    gen.write_export(export2, str(out2))
    b1 = out1.read_bytes()
    b2 = out2.read_bytes()
    assert b1 == b2, "two unchanged runs are not byte-identical"
    assert dig1 == dig2 == EXPECTED_DIGEST
    # the generator reproduces the committed artifact byte-for-byte
    assert b1 == ARTIFACT_PATH.read_bytes()


@requires_db
def test_generator_does_not_modify_db():
    before = gen._db_stat(gen.DB_PATH)
    gen.build_export()
    after = gen._db_stat(gen.DB_PATH)
    assert after == before, "DB stat changed across a generator run"


def test_generator_canonical_digest_helper_matches(artifact):
    # gen.canonical_digest over the artifact payload reproduces the frozen digest
    assert gen.canonical_digest(artifact["payload"]) == EXPECTED_DIGEST


def test_neumaier_sum_is_interpreter_portable():
    # Compensated sum used for jaccard means; exercise the helper directly.
    vals = [0.1, 0.2, 0.3, 1e16, 1.0, -1e16]
    assert abs(gen._neumaier_sum(vals) - 1.6) < 1e-6


# ==========================================================================
# B. API route (artifact-backed, read-only)
# ==========================================================================
def _call(window, metric_scope):
    """Invoke the async route directly (interpreter-independent; explicit args)."""
    return asyncio.run(
        replay_mod.get_big649_measurement_export(window=window, metric_scope=metric_scope)
    )


@requires_replay
def test_route_is_registered():
    paths = {getattr(r, "path", None) for r in replay_mod.router.routes}
    assert "/api/replay/big649-measurement-export" in paths


@requires_replay
def test_route_default_query_values():
    import inspect
    sig = inspect.signature(replay_mod.get_big649_measurement_export)
    assert sig.parameters["window"].default.default == "all_reference"
    assert sig.parameters["metric_scope"].default.default == "ticket_slot"


@requires_replay
@pytest.mark.parametrize("window", API_WINDOWS)
@pytest.mark.parametrize("scope", SCOPES)
def test_route_valid_window_scope(window, scope):
    d = _call(window, scope)
    assert d["route_path"] == "/api/replay/big649-measurement-export"
    assert d["lottery_type"] == "BIG_LOTTO"
    assert d["window"] == window
    assert d["window_internal"] == WINDOW_MAP[window]
    assert d["metric_scope"] == scope
    assert d["endpoint_support_status"]["EXACT_PRIZE_TIER"] == "PARTIALLY_SUPPORTED"
    assert d["endpoint_support_status"]["PAYOUT_EV_ROI"] == "UNSUPPORTED"
    assert d["window_definition"]["target_count"] == {
        "REFERENCE_ALL_ELIGIBLE": 1531, "RECENT_750": 750,
        "RECENT_300": 300, "RECENT_50": 50,
    }[WINDOW_MAP[window]]
    assert d["source_artifact"] == "big649_measurement_export_20260621.json"
    if scope == "pairwise_overlap":
        assert d["pair_count"] == 55
        assert len(d["pairs"]) == 55
        assert len(d["pairs_lexical"]) == 55
        assert d["pairs"][0]["pair_key"].startswith(STRATEGIES[0] + "|")
    else:
        # per-strategy scopes: lexical order, exactly 11 strategies
        assert d["strategy_order_lexical"] == STRATEGIES
        assert list(d["by_strategy"].keys()) == STRATEGIES


@requires_replay
def test_route_ticket_slot_fields_map_to_artifact(artifact):
    d = _call("recent_300", "ticket_slot")
    sid = STRATEGIES[0]
    cell = d["by_strategy"][sid]
    ref = artifact["payload"]["per_strategy_ticket_level_distribution"]["by_strategy"][sid]["RECENT_300"]
    assert cell == ref
    assert d["denominator_kind"] == "VALID_SUBMITTED_TICKET_SLOTS"


@requires_replay
def test_route_target_level_exposes_coverage(artifact):
    d = _call("recent_300", "target_level")
    sid = STRATEGIES[0]
    cell = d["by_strategy"][sid]
    assert cell["coverage_status"] in ("COMPLETE", "PARTIAL")
    assert cell["window_target_count"] - cell["covered_target_count"] == cell["missing_target_count"]
    assert d["denominator_kind"] == "COVERED_TARGETS_ONLY"


@requires_replay
def test_route_prize_aware_has_both_levels():
    d = _call("recent_50", "prize_aware")
    assert "endpoint_definitions" in d
    cell = d["by_strategy"][STRATEGIES[0]]
    assert "ticket_slot_level" in cell and "target_any_ticket_level" in cell


@requires_replay
def test_route_response_has_no_score_rank_or_payout_value(artifact):
    d = _call("all_reference", "ticket_slot")
    # No promotional value field at the response top level.
    for bad in ("rank", "ranking", "score", "recommendation", "candidate",
                "p_value", "payout", "roi", "best_strategy"):
        assert bad not in d
    # endpoint_support_status carries only labels, never the literal "SUPPORTED" for payout
    assert d["endpoint_support_status"]["PAYOUT_EV_ROI"] == "UNSUPPORTED"


@requires_replay
def test_route_invalid_window_rejected():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as ei:
        _call("not_a_window", "ticket_slot")
    assert ei.value.status_code == 400


@requires_replay
def test_route_invalid_scope_rejected():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as ei:
        _call("all_reference", "not_a_scope")
    assert ei.value.status_code == 400


@requires_replay
def test_loader_missing_artifact_500(monkeypatch, tmp_path):
    from fastapi import HTTPException
    monkeypatch.setattr(replay_mod, "_BIG649_MEASUREMENT_EXPORT_PATH", tmp_path / "nope.json")
    with pytest.raises(HTTPException) as ei:
        replay_mod._load_big649_measurement_export_payload()
    assert ei.value.status_code == 500


@requires_replay
def test_loader_malformed_json_500(monkeypatch, tmp_path):
    from fastapi import HTTPException
    bad = tmp_path / "bad.json"
    bad.write_text("{ this is not json", encoding="utf-8")
    monkeypatch.setattr(replay_mod, "_BIG649_MEASUREMENT_EXPORT_PATH", bad)
    with pytest.raises(HTTPException) as ei:
        replay_mod._load_big649_measurement_export_payload()
    assert ei.value.status_code == 500


@requires_replay
def test_loader_non_dict_500(monkeypatch, tmp_path):
    from fastapi import HTTPException
    arr = tmp_path / "arr.json"
    arr.write_text("[1, 2, 3]", encoding="utf-8")
    monkeypatch.setattr(replay_mod, "_BIG649_MEASUREMENT_EXPORT_PATH", arr)
    with pytest.raises(HTTPException) as ei:
        replay_mod._load_big649_measurement_export_payload()
    assert ei.value.status_code == 500


@requires_replay
def test_loader_missing_payload_object_500(monkeypatch, tmp_path):
    from fastapi import HTTPException
    nopay = tmp_path / "nopay.json"
    nopay.write_text('{"schema_version": "x"}', encoding="utf-8")
    monkeypatch.setattr(replay_mod, "_BIG649_MEASUREMENT_EXPORT_PATH", nopay)
    with pytest.raises(HTTPException) as ei:
        replay_mod._load_big649_measurement_export_payload()
    assert ei.value.status_code == 500


@requires_replay
def test_route_does_not_query_db_at_runtime(monkeypatch):
    import sqlite3

    def _boom(*a, **k):
        raise AssertionError("DB connection opened at request time")

    monkeypatch.setattr(sqlite3, "connect", _boom)
    d = _call("all_reference", "ticket_slot")  # must succeed purely from the artifact
    assert d["lottery_type"] == "BIG_LOTTO"


@requires_replay
def test_route_does_not_read_tmp(monkeypatch):
    # The route's artifact path must point into the repo, never /tmp.
    p = str(replay_mod._BIG649_MEASUREMENT_EXPORT_PATH)
    assert not p.startswith("/tmp")
    assert p.endswith("outputs/research/big649_measurement_export_20260621.json")


@requires_replay
def test_route_e2e_via_testclient_if_available():
    """End-to-end HTTP check; skips if the environment's TestClient is incompatible
    (mirrors the existing P258 route tests' skip behaviour)."""
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"fastapi/httpx unavailable: {exc}")
    app = FastAPI()
    app.include_router(replay_mod.router)
    try:
        client = TestClient(app)
    except TypeError:  # pragma: no cover - known starlette/httpx env mismatch
        pytest.skip("TestClient version incompatibility (pre-existing env issue)")
    r = client.get("/api/replay/big649-measurement-export")
    assert r.status_code == 200
    body = r.json()
    assert body["lottery_type"] == "BIG_LOTTO"
    assert len(body["strategy_order_lexical"]) == 11
    assert client.get("/api/replay/big649-measurement-export",
                      params={"window": "bogus"}).status_code == 400
    assert client.get("/api/replay/big649-measurement-export",
                      params={"metric_scope": "bogus"}).status_code == 400


# ==========================================================================
# C. Static UI (index.html)
# ==========================================================================
def test_ui_nav_button_present(html_text):
    assert 'data-section="big649-measurement"' in html_text


def test_ui_section_present(html_text):
    assert 'id="big649-measurement-section"' in html_text


def test_ui_section_markers_present(html_text):
    assert "<!-- ===== BIG649 MEASUREMENT" in html_text
    assert "<!-- ===== END BIG649 MEASUREMENT =====" in html_text


def test_ui_window_labels_present(section):
    for label in ("全部歷史（僅參考）", "最近 750 期", "最近 300 期", "最近 50 期"):
        assert label in section
    # window query values present in the data attributes
    for w in API_WINDOWS:
        assert f'data-window="{w}"' in section


def test_ui_metric_scope_controls_present(section):
    for s in SCOPES:
        assert f'data-scope="{s}"' in section
    for label in ("每票命中分布", "每期任一票命中", "LOCAL_PRIZE_AWARE_V1",
                  "重複票", "兩策略交疊度"):
        assert label in section


def test_ui_safety_disclaimer_present(section):
    assert "本地歷史" in section
    assert "非預測" in section and "非推薦" in section
    assert "僅供參考" in section


def test_ui_denominator_distinction_present(section):
    assert "VALID_SUBMITTED_TICKET_SLOTS" in section
    assert "COVERED_TARGETS_ONLY" in section
    assert "票數分母" in section and "期數分母" in section


def test_ui_status_and_na_labels_present(section):
    assert "PARTIALLY_SUPPORTED" in section
    assert "UNSUPPORTED" in section
    assert "PARTIAL" in section
    assert "N/A" in section


def test_ui_uses_artifact_api_route(section):
    assert "/api/replay/big649-measurement-export" in section


def test_ui_no_promotional_or_ranking_language(section):
    # The section must not present rankings, recommendations, or betting advice.
    for banned in ("最佳策略", "推薦下注", "建議下注", "保證中獎", "勝率排名",
                   "recommendation", "official prize"):
        assert banned not in section, f"promotional/ranking language present: {banned}"
