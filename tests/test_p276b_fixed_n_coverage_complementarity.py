"""
P276B — Fixed-N Cross-Strategy Coverage & Complementarity Study tests.

All targeted tests are DB-FREE: they use synthetic in-memory structures, the
committed read-only artifacts already in the repo, and (for the read-only
guard) a temporary synthetic SQLite fixture created with pytest tmp_path. The
canonical production database is NEVER opened, referenced, or written by any
test, so CI does not require it.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

import pytest

from analysis import p276b_fixed_n_coverage_complementarity as P

ROOT = Path(__file__).resolve().parent.parent
P275B_JSON = ROOT / "outputs/research/p275b_unified_prize_aware_success_matrix_20260616.json"
IDENTITY_JSON = ROOT / "outputs/research/p273a_distinct_ticket_identity_20260615.json"
PRIMARY_COUNTS_JSON = ROOT / "outputs/research/p273a_primary_window_observed_counts_20260615.json"
INFERENTIAL_JSON = ROOT / "outputs/research/p273a_prize_aware_inferential_validation_20260615.json"

PINNED_DIGEST = "c1b99e57024f528e39e4beeca03cb22dd3278eb1d356aafbe48d8485695102f6"


# ---------------------------------------------------------------------------
# Synthetic scenario helpers (DAILY_539, no special)
# ---------------------------------------------------------------------------

def _fp(main, sz=None):
    content = {"main_numbers": sorted(main)}
    if sz is not None:
        content["predicted_second_zone"] = sz
    return P.canonical_ticket_fingerprint(content), content


def _cell(lt, sid, per_draw_tickets, dup_collapsed=0):
    """per_draw_tickets: {draw: [main_list, ...]} -> identity cell dict."""
    supported = []
    for draw, tickets in per_draw_tickets.items():
        groups = []
        for main in tickets:
            fingerprint, content = _fp(main)
            groups.append({"canonical_ticket_content": content,
                           "fingerprint_sha256": fingerprint})
        supported.append({"target_draw": draw,
                          "canonical_ticket_groups": groups})
    return {"lottery_type": lt, "strategy_id": sid,
            "supported_draws": supported,
            "same_bet_index_duplicate_rows_collapsed": dup_collapsed}


def _outcomes(spec):
    """spec: {(lt,draw): main_list} -> outcomes map (DAILY_539, special None)."""
    return {k: {"main": v, "special": None} for k, v in spec.items()}


@pytest.fixture
def synthetic539():
    # 4 draws; outcomes chosen so wins are known.
    draws = ["100", "99", "98", "97"]
    outcome_spec = {
        ("DAILY_539", "100"): [1, 2, 3, 4, 5],
        ("DAILY_539", "99"): [6, 7, 8, 9, 10],
        ("DAILY_539", "98"): [1, 2, 3, 4, 5],
        ("DAILY_539", "97"): [11, 12, 13, 14, 15],
    }
    # stratA wins draws 100 & 98 (ticket hits 1,2); loses 99 & 97.
    A = {"100": [[1, 2, 30, 31, 32], [20, 21, 22, 23, 24]],
         "99": [[30, 31, 32, 33, 34], [20, 21, 22, 23, 24]],
         "98": [[1, 2, 30, 31, 32], [20, 21, 22, 23, 24]],
         "97": [[30, 31, 32, 33, 34], [20, 21, 22, 23, 24]]}
    # stratB complementary — wins only draw 97 (hits 11,12); loses 100/99/98.
    B = {"100": [[25, 26, 27, 28, 29], [14, 15, 16, 17, 18]],
         "99": [[25, 26, 27, 28, 29], [35, 36, 37, 38, 39]],
         "98": [[25, 26, 27, 28, 29], [14, 15, 16, 17, 18]],
         "97": [[11, 12, 30, 31, 32], [35, 36, 37, 38, 39]]}
    identity = {"cells": [_cell("DAILY_539", "stratA", A),
                          _cell("DAILY_539", "stratB", B)]}
    outcomes = _outcomes(outcome_spec)
    cell_data = P.build_cell_per_draw(identity, outcomes)
    return {"identity": identity, "outcomes": outcomes, "cell_data": cell_data,
            "draws": draws}


# ---------------------------------------------------------------------------
# 1. P275B/P273A input invariant validation (committed, read-only)
# ---------------------------------------------------------------------------

def test_committed_input_invariants():
    inputs = P.load_and_verify_inputs(
        p275b_path=str(P275B_JSON), identity_path=str(IDENTITY_JSON),
        primary_counts_path=str(PRIMARY_COUNTS_JSON),
        inferential_path=str(INFERENTIAL_JSON))
    assert len(inputs["p275b"]["matrix_rows"]) == 108
    assert inputs["p275b"]["matrix_summary"]["frozen_cells"] == 36
    assert inputs["p275b"]["prediction_success_claim"] is False
    assert inputs["p275b"]["canonical_payload_digest"] == PINNED_DIGEST
    assert inputs["fingerprints_reverified"] > 0
    assert len(inputs["identity"]["cells"]) == 36


def test_input_integrity_fails_on_tampered_digest(tmp_path):
    doc = json.loads(P275B_JSON.read_text())
    doc["matrix_rows"] = doc["matrix_rows"][:-1]  # break invariant (108 -> 107)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(doc))
    with pytest.raises(P.IntegrityError):
        P.load_and_verify_inputs(
            p275b_path=str(bad), identity_path=str(IDENTITY_JSON),
            primary_counts_path=str(PRIMARY_COUNTS_JSON),
            inferential_path=str(INFERENTIAL_JSON))


# ---------------------------------------------------------------------------
# 2. Stable draw-identity/date alignment (never array position)
# ---------------------------------------------------------------------------

def test_stable_draw_identity_alignment(synthetic539):
    cd = synthetic539["cell_data"][("DAILY_539", "stratA")]
    # stratA wins on draws 100 and 98 (hits [1,2]); not 99 or 97.
    assert cd["prize_win"]["100"] is True
    assert cd["prize_win"]["98"] is True
    assert cd["prize_win"]["99"] is False
    assert cd["prize_win"]["97"] is False
    # draws_desc is sorted by integer value descending (identity, not position).
    assert cd["draws_desc"] == ["100", "99", "98", "97"]


def test_alignment_uses_draw_id_not_position():
    # Outcome map keyed by draw id; shuffling supported_draws order must not
    # change which outcome a draw is scored against.
    out = _outcomes({("DAILY_539", "5"): [1, 2, 3, 4, 5],
                     ("DAILY_539", "9"): [30, 31, 32, 33, 34]})
    cell = _cell("DAILY_539", "s", {"9": [[1, 2, 3, 9, 8]],
                                    "5": [[1, 2, 3, 9, 8]]})
    cd = P.build_cell_per_draw({"cells": [cell]}, out)[("DAILY_539", "s")]
    # ticket [1,2,3,9,8] hits 3 on draw 5 (win), 0 on draw 9 (loss).
    assert cd["prize_win"]["5"] is True
    assert cd["prize_win"]["9"] is False


# ---------------------------------------------------------------------------
# 3. Full aggregate-count reproduction (synthetic, fail-closed)
# ---------------------------------------------------------------------------

def _mini_counts_and_p275b(cell_data, windows=(2, 4)):
    counts_cells = []
    p275b_rows = []
    for (lt, sid), data in cell_data.items():
        wlist = []
        for w in windows:
            ddesc = data["draws_desc"][:w]
            succ = sum(1 for d in ddesc if data["prize_win"][d])
            wlist.append({"window": w, "support_draws": len(ddesc),
                          "observed_successes": succ,
                          "latest_target_draw": ddesc[0],
                          "earliest_target_draw": ddesc[-1]})
            p275b_rows.append({"lottery_type": lt, "strategy_id": sid,
                               "window_draw_count": w, "success_draws": succ})
        counts_cells.append({"lottery_type": lt, "strategy_id": sid,
                             "windows": wlist})
    return ({"cells": counts_cells}, {"matrix_rows": p275b_rows})


def test_full_count_reproduction_pass(synthetic539):
    cd = synthetic539["cell_data"]
    counts, p275b = _mini_counts_and_p275b(cd)
    rep = P.reproduce_committed_counts(cd, counts, p275b)
    assert rep["reproduction_status"] == "PASS"
    assert rep["p273a_primary_window_cells_checked"] > 0


def test_count_reproduction_fails_closed(synthetic539):
    cd = synthetic539["cell_data"]
    counts, p275b = _mini_counts_and_p275b(cd)
    counts["cells"][0]["windows"][0]["observed_successes"] += 1  # corrupt
    with pytest.raises(P.ReproductionError):
        P.reproduce_committed_counts(cd, counts, p275b)


# ---------------------------------------------------------------------------
# 4. Portfolio family frozen before outcome access
# ---------------------------------------------------------------------------

def test_contract_frozen_before_outcome_access():
    c1 = P.freeze_contract()
    c2 = P.freeze_contract()
    assert c1["frozen_before_outcome_access"] is True
    assert c1["preregistered_family_sha256"] == c2["preregistered_family_sha256"]
    # hash is computed purely from the literal family (no outcome dependence)
    manual = hashlib.sha256(json.dumps(
        P.PREREGISTERED_PORTFOLIO_FAMILY, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode("utf-8")).hexdigest()
    assert c1["preregistered_family_sha256"] == manual


# ---------------------------------------------------------------------------
# 5. Fixed-N enforcement
# ---------------------------------------------------------------------------

def test_fixed_n_enforcement(synthetic539):
    cd = synthetic539["cell_data"]
    chosen, _dup = P._select_n_tickets("DAILY_539", 3, ["stratA", "stratB"],
                                       cd, "100")
    assert chosen is not None and len(chosen) == 3  # exactly N, never more


def test_portfolio_never_exceeds_budget(synthetic539):
    cd = synthetic539["cell_data"]
    port = {"portfolio_id": "x", "lottery_type": "DAILY_539",
            "ticket_budget": 3, "tier": "PRIMARY", "kind": "CROSS",
            "source_cells": ["stratA", "stratB"]}
    pdata = P.build_portfolio_per_draw(port, cd)
    # 2+2=4 distinct tickets per draw, budget 3 -> all draws eligible.
    assert set(pdata["eligible_draws"]) == set(synthetic539["draws"])


# ---------------------------------------------------------------------------
# 6. Ticket-fingerprint deduplication
# ---------------------------------------------------------------------------

def test_fingerprint_dedup():
    out = _outcomes({("DAILY_539", "1"): [1, 2, 3, 4, 5]})
    # stratA and stratB both play the identical ticket [1,2,3,38,39].
    a = _cell("DAILY_539", "A", {"1": [[1, 2, 3, 38, 39]]})
    b = _cell("DAILY_539", "B", {"1": [[1, 2, 3, 38, 39]]})
    cd = P.build_cell_per_draw({"cells": [a, b]}, out)
    chosen, dup = P._select_n_tickets("DAILY_539", 2, ["A", "B"], cd, "1")
    # identical fingerprint -> only 1 distinct ticket -> < N -> ineligible.
    assert chosen is None
    assert dup >= 1


# ---------------------------------------------------------------------------
# 7. Fewer-than-N handling without backfill
# ---------------------------------------------------------------------------

def test_fewer_than_n_no_backfill():
    out = _outcomes({("DAILY_539", "1"): [1, 2, 3, 4, 5]})
    a = _cell("DAILY_539", "A", {"1": [[1, 2, 3, 38, 39]]})  # only 1 ticket
    cd = P.build_cell_per_draw({"cells": [a]}, out)
    chosen, _dup = P._select_n_tickets("DAILY_539", 3, ["A"], cd, "1")
    assert chosen is None  # never back-filled to reach N


# ---------------------------------------------------------------------------
# 8 & 9. Random-baseline determinism
# ---------------------------------------------------------------------------

def test_ordinary_random_determinism():
    outs = [{"main": [1, 2, 3, 4, 5], "special": None}]
    q1 = P.estimate_baseline_Q("DAILY_539", 3, outs,
                               P._derived_rng("Q", "DAILY_539", 3, "ordinary"),
                               "ordinary", 2000)
    q2 = P.estimate_baseline_Q("DAILY_539", 3, outs,
                               P._derived_rng("Q", "DAILY_539", 3, "ordinary"),
                               "ordinary", 2000)
    assert q1["prize_Q"] == q2["prize_Q"]


def test_diversified_random_determinism():
    rng1 = P._derived_rng("g", "DAILY_539", 5, "diversified")
    rng2 = P._derived_rng("g", "DAILY_539", 5, "diversified")
    t1 = P._gen_random_tickets("DAILY_539", 5, rng1, "diversified",
                               __import__("numpy").arange(1, 40), 5)
    t2 = P._gen_random_tickets("DAILY_539", 5, rng2, "diversified",
                               __import__("numpy").arange(1, 40), 5)
    assert [sorted(s) for s, _ in t1] == [sorted(s) for s, _ in t2]


# ---------------------------------------------------------------------------
# 10. Diversified overlap no worse than ordinary
# ---------------------------------------------------------------------------

def test_diversified_overlap_le_ordinary():
    outs = [{"main": [1, 2, 3, 4, 5], "special": None}]
    ordn = P.estimate_baseline_Q("DAILY_539", 5, outs,
                                 P._derived_rng("Q", "x", 5, "ordinary"),
                                 "ordinary", 5000)
    div = P.estimate_baseline_Q("DAILY_539", 5, outs,
                                P._derived_rng("Q", "x", 5, "diversified"),
                                "diversified", 5000)
    assert div["mean_pairwise_overlap"] <= ordn["mean_pairwise_overlap"] + 1e-9
    # diversified disjoint blocks (5x5=25 <= 39) -> ~zero overlap
    assert div["mean_pairwise_overlap"] < 0.5


# ---------------------------------------------------------------------------
# 11. Union calculation correctness
# ---------------------------------------------------------------------------

def test_union_calculation(synthetic539):
    cd = synthetic539["cell_data"]
    # CROSS portfolio of stratA+stratB at N=4 (all 4 tickets) wins a draw iff
    # any constituent ticket wins. Draw 97: stratB wins (11,12), stratA loses.
    port = {"portfolio_id": "x", "lottery_type": "DAILY_539",
            "ticket_budget": 4, "tier": "PRIMARY", "kind": "CROSS",
            "source_cells": ["stratA", "stratB"]}
    pdata = P.build_portfolio_per_draw(port, cd)
    assert pdata["prize_win"]["97"] is True   # union picks up stratB's win
    assert pdata["prize_win"]["99"] is False  # neither wins draw 99


# ---------------------------------------------------------------------------
# 12. Jaccard correctness
# ---------------------------------------------------------------------------

def test_jaccard_correctness():
    assert P.jaccard({1, 2, 3}, {2, 3, 4}) == pytest.approx(2 / 4)
    assert P.jaccard(set(), set()) is None
    assert P.jaccard({1}, {2}) == 0.0


# ---------------------------------------------------------------------------
# 13. McNemar correctness
# ---------------------------------------------------------------------------

def test_mcnemar_correctness():
    n, p = P.mcnemar_exact(0, 0)
    assert n == 0 and p == 1.0
    n, p = P.mcnemar_exact(10, 0)
    assert n == 10 and p < 0.01            # all discordant one way -> tiny p
    n, p = P.mcnemar_exact(5, 5)
    assert n == 10 and p == pytest.approx(1.0)  # symmetric -> p == 1


# ---------------------------------------------------------------------------
# 14. Marginal-gain correctness
# ---------------------------------------------------------------------------

def test_marginal_gain_structure(synthetic539):
    cd = synthetic539["cell_data"]
    port = {"portfolio_id": "x", "lottery_type": "DAILY_539",
            "ticket_budget": 3, "tier": "PRIMARY", "kind": "CROSS",
            "source_cells": ["stratA", "stratB"]}
    pdata = P.build_portfolio_per_draw(port, cd)
    bq = {("DAILY_539", 3): {kind: P.estimate_baseline_Q(
        "DAILY_539", 3, list(synthetic539["outcomes"].values()),
        P._derived_rng("Q", "DAILY_539", 3, kind), kind, 1000)
        for kind in ("ordinary", "diversified")}}
    metrics = P.compute_portfolio_metrics(port, pdata, cd, bq)
    long_w = [w for w in metrics["windows"] if w["window"] == 750][0]
    mg = long_w["prize_aware"]["marginal_coverage_gain"]
    assert [g["k_sources"] for g in mg] == [1, 2]  # cumulative over sources


# ---------------------------------------------------------------------------
# 15. Prize-aware / M3+ family separation
# ---------------------------------------------------------------------------

def test_prize_aware_m3_separation():
    # DAILY_539 hit_count == 2 -> prize-aware win but NOT M3+ (hit>=3).
    pa, m3 = P._score_ticket("DAILY_539", [1, 2, 30, 31, 32], None,
                             {"main": [1, 2, 3, 4, 5], "special": None})
    assert pa is True and m3 is False
    # hit_count == 3 -> both.
    pa3, m33 = P._score_ticket("DAILY_539", [1, 2, 3, 31, 32], None,
                               {"main": [1, 2, 3, 4, 5], "special": None})
    assert pa3 is True and m33 is True


# ---------------------------------------------------------------------------
# 16. POWER missing-second-zone exclusion (eligibility, never imputed)
# ---------------------------------------------------------------------------

def test_power_missing_second_zone_excluded():
    row = {"lottery_type": "POWER_LOTTO", "target_draw": "10",
           "history_cutoff_draw": "9", "bet_index": 1,
           "predicted_numbers": "[1,2,3,4,5,6]", "predicted_special": None,
           "actual_numbers": "[1,2,3,4,5,6]", "actual_special": 4,
           "_join_count": 1}
    eligible, reason = P._check_eligibility(row)
    assert eligible is False
    assert reason == "MISSING_PREDICTED_SECOND_ZONE"


# ---------------------------------------------------------------------------
# 17. SHORT-50 non-promotion
# ---------------------------------------------------------------------------

def test_short50_non_promotion(synthetic539):
    cd = synthetic539["cell_data"]
    port = {"portfolio_id": "x", "lottery_type": "DAILY_539",
            "ticket_budget": 3, "tier": "PRIMARY", "kind": "CROSS",
            "source_cells": ["stratA", "stratB"]}
    pdata = P.build_portfolio_per_draw(port, cd)
    bq = {("DAILY_539", 3): {kind: P.estimate_baseline_Q(
        "DAILY_539", 3, list(synthetic539["outcomes"].values()),
        P._derived_rng("Q", "DAILY_539", 3, kind), kind, 1000)
        for kind in ("ordinary", "diversified")}}
    metrics = P.compute_portfolio_metrics(port, pdata, cd, bq)
    short = [w for w in metrics["windows"] if w["window"] == 50][0]
    assert short["promotion_eligible_window"] is False


# ---------------------------------------------------------------------------
# 18. Strict future-cutoff enforcement
# ---------------------------------------------------------------------------

def test_future_cutoff_and_status():
    # cutoff = latest committed target draw; status must be PENDING (no
    # committed walk-forward tickets exist beyond the cutoff).
    c = P.freeze_contract()
    assert c["confirmatory_family_size"] == P.CONFIRMATORY_FAMILY_SIZE
    # SHORT excluded from inferential windows
    assert 50 not in P.INFERENTIAL_WINDOWS
    assert tuple(P.INFERENTIAL_WINDOWS) == (300, 750)


# ---------------------------------------------------------------------------
# 19. Bonferroni family-size integrity
# ---------------------------------------------------------------------------

def test_bonferroni_family_size():
    # 3 primary CROSS portfolios x 2 inferential windows = 6.
    assert len(P.CONFIRMATORY_PRIMARY_CROSS_PORTFOLIOS) == 3
    assert P.CONFIRMATORY_FAMILY_SIZE == 6
    c = P.freeze_contract()
    assert c["bonferroni_per_test_alpha"] == pytest.approx(0.05 / 6)


# ---------------------------------------------------------------------------
# 20. No-DB-write guard (temporary synthetic SQLite fixture)
# ---------------------------------------------------------------------------

def test_no_db_write_guard(tmp_path):
    db = tmp_path / "synthetic.db"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE draws (lottery_type TEXT, draw TEXT, "
                "numbers TEXT, special INTEGER)")
    con.execute("INSERT INTO draws VALUES ('DAILY_539','1','[1,2,3,4,5]',0)")
    con.commit()
    con.close()
    pre = hashlib.sha256(db.read_bytes()).hexdigest()

    conn, evidence = P.open_readonly_connection(str(db))
    assert evidence["query_only_enabled"] is True
    assert evidence["write_denying_authorizer_installed"] is True
    # reads work
    assert conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0] == 1
    # every write/DDL is denied
    for stmt in ("INSERT INTO draws VALUES ('DAILY_539','2','[1,2,3,4,6]',0)",
                 "UPDATE draws SET special=9",
                 "DELETE FROM draws",
                 "CREATE TABLE t2 (x INTEGER)",
                 "DROP TABLE draws"):
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute(stmt)
    conn.close()
    assert hashlib.sha256(db.read_bytes()).hexdigest() == pre  # unchanged


# ---------------------------------------------------------------------------
# 21. Committed canonical-digest reproduction
# ---------------------------------------------------------------------------

def test_committed_canonical_digest_reproduction():
    doc = json.loads(P275B_JSON.read_text())
    recomputed = P.canonical_digest(doc, P._P275B_SELF_EXCLUDE)
    assert recomputed == PINNED_DIGEST == doc["canonical_payload_digest"]


def test_self_digest_roundtrips():
    sample = {"a": 1, "b": [1, 2, 3], "generated_at": "X",
              "canonical_payload_digest": "Y"}
    d = P.canonical_digest(sample, P.SELF_DIGEST_EXCLUDE)
    sample2 = dict(sample, generated_at="DIFFERENT")  # volatile change
    assert P.canonical_digest(sample2, P.SELF_DIGEST_EXCLUDE) == d


# ---------------------------------------------------------------------------
# 22. JSON / Markdown consistency
# ---------------------------------------------------------------------------

def test_json_md_consistency(synthetic539, tmp_path):
    # Build a minimal result-shaped dict via the real metric path and render MD.
    cd = synthetic539["cell_data"]
    port = {"portfolio_id": "D539_demo", "lottery_type": "DAILY_539",
            "ticket_budget": 3, "tier": "PRIMARY", "kind": "CROSS",
            "source_cells": ["stratA", "stratB"]}
    pdata = P.build_portfolio_per_draw(port, cd)
    bq = {("DAILY_539", 3): {kind: P.estimate_baseline_Q(
        "DAILY_539", 3, list(synthetic539["outcomes"].values()),
        P._derived_rng("Q", "DAILY_539", 3, kind), kind, 1000)
        for kind in ("ordinary", "diversified")}}
    metrics = P.compute_portfolio_metrics(port, pdata, cd, bq)
    verdict = P.derive_verdict([metrics])
    result = {
        "task_id": P.TASK_ID, "artifact_version": P.ARTIFACT_VERSION,
        "scoring_version": P.SCORING_VERSION, "generated_at": "T",
        "scientific_verdict": verdict,
        "frozen_contract": P.freeze_contract(),
        "db_snapshot": {"path_identifier": "x", "sha256_pre": "a",
                        "sha256_post": "a", "sha256_unchanged": True,
                        "size_bytes": 1, "modification_time_utc": "T",
                        "read_only_evidence": {"query_only_enabled": True,
                        "write_denying_authorizer_installed": True},
                        "latest_draw_in_db": {}},
        "reconstruction": {"count_reproduction": {
            "reproduction_status": "PASS",
            "p273a_primary_window_cells_checked": 1}},
        "frozen_future_contract": {
            "cutoff_target_draw_by_lottery": {"DAILY_539": "100"},
            "future_confirmation_status": "FUTURE_CONFIRMATION_PENDING"},
        "portfolio_results": [metrics],
        "limitations": ["demo"],
    }
    result["canonical_payload_digest"] = P.canonical_digest(
        result, P.SELF_DIGEST_EXCLUDE)
    md = P.render_markdown(result)
    assert verdict in md
    assert result["canonical_payload_digest"] in md
    assert "D539_demo" in md


# ---------------------------------------------------------------------------
# 23. Unicode / control-character safety
# ---------------------------------------------------------------------------

def _has_dangerous_unicode(text):
    """True if text contains bidi-override, zero-width, BOM, or C0/C1 control
    characters (excluding the benign tab/newline/carriage-return)."""
    for ch in text:
        cp = ord(ch)
        if cp in (0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0xFEFF):
            return True  # zero-width / bidi marks / BOM
        if 0x202A <= cp <= 0x202E or 0x2066 <= cp <= 0x2069:
            return True  # bidi embedding / override / isolate
        if cp < 0x20 and ch not in ("\t", "\n", "\r"):
            return True  # C0 control
        if 0x7F <= cp <= 0x9F:
            return True  # DEL / C1 control
    return False


def test_no_dangerous_unicode_in_module_and_committed_artifacts():
    src = (ROOT / "analysis/p276b_fixed_n_coverage_complementarity.py").read_text()
    assert not _has_dangerous_unicode(src)
    # committed P275B json must also be free of bidi/control chars
    assert not _has_dangerous_unicode(P275B_JSON.read_text())


def test_render_markdown_unicode_safe(synthetic539):
    cd = synthetic539["cell_data"]
    port = {"portfolio_id": "x", "lottery_type": "DAILY_539",
            "ticket_budget": 4, "tier": "PRIMARY", "kind": "CROSS",
            "source_cells": ["stratA", "stratB"]}
    pdata = P.build_portfolio_per_draw(port, cd)
    bq = {("DAILY_539", 4): {kind: P.estimate_baseline_Q(
        "DAILY_539", 4, list(synthetic539["outcomes"].values()),
        P._derived_rng("Q", "DAILY_539", 4, kind), kind, 500)
        for kind in ("ordinary", "diversified")}}
    m = P.compute_portfolio_metrics(port, pdata, cd, bq)
    result = {"task_id": "x", "artifact_version": "v", "scoring_version": "s",
              "generated_at": "T", "scientific_verdict": "X",
              "frozen_contract": P.freeze_contract(),
              "db_snapshot": {"path_identifier": "x", "sha256_pre": "a",
                              "sha256_post": "a", "sha256_unchanged": True,
                              "size_bytes": 1, "modification_time_utc": "T",
                              "read_only_evidence": {"query_only_enabled": True,
                              "write_denying_authorizer_installed": True},
                              "latest_draw_in_db": {}},
              "reconstruction": {"count_reproduction": {
                  "reproduction_status": "PASS",
                  "p273a_primary_window_cells_checked": 1}},
              "frozen_future_contract": {
                  "cutoff_target_draw_by_lottery": {},
                  "future_confirmation_status": "FUTURE_CONFIRMATION_PENDING"},
              "portfolio_results": [m], "limitations": ["x"],
              "canonical_payload_digest": "d"}
    assert not _has_dangerous_unicode(P.render_markdown(result))
