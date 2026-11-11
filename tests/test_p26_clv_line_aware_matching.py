"""
P26 — Deterministic tests for line-aware CLV outcome matching
paper_only=true / diagnostic_only=true

Requirements:
- HDC line moved case: -1.5 vs -2.5 must skip (LINE_MOVED)
- HDC exact line match: -1.5 vs -1.5 must compute CLV (MATCHED)
- OU total moved: 8.5 vs 9.5 must skip (LINE_MOVED)
- OU exact total match: 8.5 vs 8.5 must compute CLV (MATCHED)
- OE odd/even side match: 單/雙 must compute CLV (MATCHED)
- TTO team total moved: 大 4.5 vs 大 5.5 must skip (LINE_MOVED)
- MNL 2-way vs 3-way shape mismatch must skip (MARKET_SHAPE_MISMATCH)
- PARSE_FAILED must skip
- No index fallback allowed
"""
import pytest
from wbc_backend.clv.outcome_matching import (
    MatchStatus,
    match_outcomes_for_market,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _o(name: str, odds: float) -> dict:
    return {"outcomeName": name, "odds": str(odds)}


def _matched_names(results) -> list[str]:
    return [r.outcome_name for r in results if r.status == MatchStatus.MATCHED]


def _skip_names(results) -> list[str]:
    return [r.outcome_name for r in results if r.status != MatchStatus.MATCHED]


def _statuses(results) -> list[str]:
    return [r.status.value for r in results]


# ── HDC tests ─────────────────────────────────────────────────────────────────

class TestHDCMatching:
    def test_line_moved_must_skip(self):
        """HDC: pregame -1.5 vs closing -2.5 must produce LINE_MOVED, not CLV."""
        pre = [_o("底特律老虎 -1.5", 1.85), _o("密爾瓦基釀酒人 +1.5", 2.05)]
        clo = [_o("底特律老虎 -2.5", 1.40), _o("密爾瓦基釀酒人 +2.5", 2.90)]
        results = match_outcomes_for_market("HDC", pre, clo)
        assert all(r.status == MatchStatus.LINE_MOVED for r in results), (
            f"Expected all LINE_MOVED, got {_statuses(results)}"
        )
        assert not any(r.is_valid_clv for r in results), "No result should be valid CLV when line moved"

    def test_exact_line_match_computes_clv(self):
        """HDC: pregame -1.5 vs closing -1.5 must compute CLV (MATCHED)."""
        pre = [_o("底特律老虎 -1.5", 1.85), _o("密爾瓦基釀酒人 +1.5", 2.05)]
        clo = [_o("底特律老虎 -1.5", 1.75), _o("密爾瓦基釀酒人 +1.5", 2.15)]
        results = match_outcomes_for_market("HDC", pre, clo)
        assert all(r.status == MatchStatus.MATCHED for r in results), (
            f"Expected all MATCHED, got {_statuses(results)}"
        )
        tiger = next(r for r in results if "老虎" in r.outcome_name)
        assert tiger.clv_pct is not None
        assert abs(tiger.clv_pct - ((1.85 - 1.75) / 1.75 * 100)) < 0.01

    def test_partial_line_move_skips_moved_keeps_stable(self):
        """HDC: one outcome line moved, other stayed — moved skips, stayed computes."""
        pre = [_o("KT巫師 -1.5", 1.90), _o("LG雙子 +1.5", 2.00)]
        clo = [_o("KT巫師 -2.5", 1.50), _o("LG雙子 +1.5", 2.05)]
        results = match_outcomes_for_market("HDC", pre, clo)
        statuses = {r.outcome_name: r.status for r in results}
        assert statuses["KT巫師 -1.5"] == MatchStatus.LINE_MOVED
        assert statuses["LG雙子 +1.5"] == MatchStatus.MATCHED

    def test_no_index_fallback(self):
        """HDC: name mismatch must NOT silently produce CLV via index fallback."""
        pre = [_o("Team A -0.5", 1.90), _o("Team B +0.5", 2.00)]
        clo = [_o("Team A -1.5", 1.55), _o("Team B +1.5", 2.40)]
        results = match_outcomes_for_market("HDC", pre, clo)
        for r in results:
            assert r.status == MatchStatus.LINE_MOVED, f"Expected LINE_MOVED, got {r.status}"
            assert r.clv_pct is None, "CLV must be None when line moved — no index fallback allowed"


# ── OU tests ──────────────────────────────────────────────────────────────────

class TestOUMatching:
    def test_total_moved_must_skip(self):
        """OU: total 8.5 vs 9.5 must produce LINE_MOVED."""
        pre = [_o("大 8.5", 1.95), _o("小 8.5", 1.95)]
        clo = [_o("大 9.5", 1.85), _o("小 9.5", 2.05)]
        results = match_outcomes_for_market("OU", pre, clo)
        assert all(r.status == MatchStatus.LINE_MOVED for r in results)
        assert not any(r.is_valid_clv for r in results)

    def test_exact_total_match_computes_clv(self):
        """OU: total 8.5 vs 8.5 must compute CLV (MATCHED)."""
        pre = [_o("大 8.5", 1.95), _o("小 8.5", 1.95)]
        clo = [_o("大 8.5", 1.90), _o("小 8.5", 2.00)]
        results = match_outcomes_for_market("OU", pre, clo)
        assert all(r.status == MatchStatus.MATCHED for r in results)
        over = next(r for r in results if r.outcome_name == "大 8.5")
        expected_clv = (1.95 - 1.90) / 1.90 * 100
        assert abs(over.clv_pct - expected_clv) < 0.01

    def test_total_line_moved_from_85_to_95(self):
        """OU: TSL example — 大 8.5 pre vs 大 9.5 closing must skip."""
        pre = [_o("大 8.5", 1.95), _o("小 8.5", 1.95)]
        clo = [_o("大 9.5", 1.85), _o("小 9.5", 2.05)]
        results = match_outcomes_for_market("OU", pre, clo)
        for r in results:
            assert r.status == MatchStatus.LINE_MOVED


# ── OE tests ──────────────────────────────────────────────────────────────────

class TestOEMatching:
    def test_odd_even_side_match(self):
        """OE: 單/雙 names are fixed — should always MATCH."""
        pre = [_o("單", 1.85), _o("雙", 2.05)]
        clo = [_o("單", 1.80), _o("雙", 2.10)]
        results = match_outcomes_for_market("OE", pre, clo)
        assert all(r.status == MatchStatus.MATCHED for r in results)
        odd = next(r for r in results if r.outcome_name == "單")
        expected_clv = (1.85 - 1.80) / 1.80 * 100
        assert abs(odd.clv_pct - expected_clv) < 0.01

    def test_oe_no_line_to_move(self):
        """OE: no line in outcome name, same odds → CLV=0."""
        pre = [_o("單", 2.00), _o("雙", 2.00)]
        clo = [_o("單", 2.00), _o("雙", 2.00)]
        results = match_outcomes_for_market("OE", pre, clo)
        assert all(r.status == MatchStatus.MATCHED for r in results)
        assert all(abs(r.clv_pct) < 0.001 for r in results)


# ── TTO tests ─────────────────────────────────────────────────────────────────

class TestTTOMatching:
    def test_team_total_moved_must_skip(self):
        """TTO: 大 4.5 vs 大 5.5 must skip (LINE_MOVED)."""
        pre = [_o("大 4.5", 1.95), _o("小 4.5", 1.95)]
        clo = [_o("大 5.5", 1.85), _o("小 5.5", 2.05)]
        results = match_outcomes_for_market("TTO", pre, clo)
        assert all(r.status == MatchStatus.LINE_MOVED for r in results)
        assert not any(r.is_valid_clv for r in results)

    def test_team_total_exact_match_computes_clv(self):
        """TTO: same total line must compute CLV."""
        pre = [_o("大 4.5", 1.90), _o("小 4.5", 1.98)]
        clo = [_o("大 4.5", 1.85), _o("小 4.5", 2.03)]
        results = match_outcomes_for_market("TTO", pre, clo)
        assert all(r.status == MatchStatus.MATCHED for r in results)


# ── MNL tests ─────────────────────────────────────────────────────────────────

class TestMNLMatching:
    def test_2way_vs_3way_shape_mismatch_must_skip(self):
        """MNL: 2-way pregame vs 3-way closing must skip all (MARKET_SHAPE_MISMATCH)."""
        pre_2way = [_o("芝加哥白襪", 1.80), _o("底特律老虎", 2.10)]
        clo_3way = [_o("芝加哥白襪", 1.90), _o("平局", 3.50), _o("底特律老虎", 2.20)]
        results = match_outcomes_for_market("MNL", pre_2way, clo_3way)
        assert all(r.status == MatchStatus.MARKET_SHAPE_MISMATCH for r in results), (
            f"Expected all MARKET_SHAPE_MISMATCH, got {_statuses(results)}"
        )

    def test_3way_vs_2way_shape_mismatch_must_skip(self):
        """MNL: 3-way pregame vs 2-way closing must skip all (MARKET_SHAPE_MISMATCH)."""
        pre_3way = [_o("Team A", 2.10), _o("平局", 3.20), _o("Team B", 2.30)]
        clo_2way = [_o("Team A", 2.00), _o("Team B", 2.40)]
        results = match_outcomes_for_market("MNL", pre_3way, clo_2way)
        assert all(r.status == MatchStatus.MARKET_SHAPE_MISMATCH for r in results)

    def test_2way_same_shape_matches_by_name(self):
        """MNL: 2-way same shape — match by team name."""
        pre = [_o("芝加哥白襪", 1.80), _o("底特律老虎", 2.10)]
        clo = [_o("芝加哥白襪", 1.75), _o("底特律老虎", 2.15)]
        results = match_outcomes_for_market("MNL", pre, clo)
        assert all(r.status == MatchStatus.MATCHED for r in results)

    def test_3way_same_shape_matches_by_name(self):
        """MNL: 3-way same shape — match by team name (draw matched too)."""
        pre = [_o("洋基", 1.70), _o("平局", 3.80), _o("紅襪", 2.30)]
        clo = [_o("洋基", 1.65), _o("平局", 4.00), _o("紅襪", 2.40)]
        results = match_outcomes_for_market("MNL", pre, clo)
        assert all(r.status == MatchStatus.MATCHED for r in results)
        yankees = next(r for r in results if r.outcome_name == "洋基")
        assert abs(yankees.clv_pct - ((1.70 - 1.65) / 1.65 * 100)) < 0.01

    def test_mnl_missing_outcome_in_closing(self):
        """MNL: team name in pregame but missing in closing → MISSING_OUTCOME."""
        pre = [_o("Team A", 1.80), _o("Team B", 2.10)]
        clo = [_o("Team A", 1.75), _o("Team C", 2.15)]  # Team B replaced by Team C
        results = match_outcomes_for_market("MNL", pre, clo)
        statuses = {r.outcome_name: r.status for r in results}
        assert statuses["Team B"] == MatchStatus.MISSING_OUTCOME
        assert statuses["Team A"] == MatchStatus.MATCHED


# ── Parse failure / unsupported ───────────────────────────────────────────────

class TestParseFailures:
    def test_empty_pregame_outcomes_parse_failed(self):
        """Empty pregame outcomes → PARSE_FAILED."""
        results = match_outcomes_for_market("HDC", [], [_o("Team A", 1.80)])
        assert results[0].status == MatchStatus.PARSE_FAILED

    def test_empty_closing_outcomes_parse_failed(self):
        """Empty closing outcomes → PARSE_FAILED."""
        results = match_outcomes_for_market("OU", [_o("大 8.5", 1.95)], [])
        assert results[0].status == MatchStatus.PARSE_FAILED

    def test_unsupported_market_code(self):
        """Unknown market code → UNSUPPORTED_MARKET."""
        results = match_outcomes_for_market("UNKNOWN_MKT", [_o("X", 1.50)], [_o("X", 1.60)])
        assert results[0].status == MatchStatus.UNSUPPORTED_MARKET

    def test_unsupported_market_no_clv(self):
        """Unsupported market must not produce CLV."""
        results = match_outcomes_for_market("EXOTIC", [_o("A", 2.0)], [_o("A", 1.9)])
        assert not any(r.is_valid_clv for r in results)


# ── No index fallback contract ────────────────────────────────────────────────

class TestNoIndexFallback:
    def test_hdc_different_names_no_clv(self):
        """Verifies no index fallback: pre has 'A -1.5', clo has 'A -2.5' → no CLV."""
        pre = [_o("A -1.5", 1.90)]
        clo = [_o("A -2.5", 1.50)]
        results = match_outcomes_for_market("HDC", pre, clo)
        assert results[0].status == MatchStatus.LINE_MOVED
        assert results[0].clv_pct is None
        assert results[0].clv_abs is None

    def test_ou_different_totals_no_clv(self):
        """OU: 大 7.5 pre vs 大 8.5 clo — no CLV, must be LINE_MOVED."""
        pre = [_o("大 7.5", 1.95), _o("小 7.5", 1.95)]
        clo = [_o("大 8.5", 1.90), _o("小 8.5", 2.00)]
        results = match_outcomes_for_market("OU", pre, clo)
        for r in results:
            assert r.clv_pct is None, (
                f"Outcome '{r.outcome_name}': clv_pct should be None (index fallback forbidden), "
                f"got {r.clv_pct}"
            )

    def test_artificial_clv_cannot_arise_from_line_shift(self):
        """
        Reproduce P25 critical finding: pregame 老虎 -1.5 @ 2.90
        closing 老虎 -2.5 @ 1.40 → old code produced +107.14% CLV.
        New code must NOT produce any CLV.
        """
        pre = [_o("底特律老虎 -1.5", 2.90), _o("密爾瓦基釀酒人 +1.5", 1.50)]
        clo = [_o("底特律老虎 -2.5", 1.40), _o("密爾瓦基釀酒人 +2.5", 2.90)]
        results = match_outcomes_for_market("HDC", pre, clo)
        for r in results:
            assert r.status == MatchStatus.LINE_MOVED
            assert r.clv_pct is None, (
                f"Artificial +107.14% CLV must be eliminated. Got clv_pct={r.clv_pct}"
            )
