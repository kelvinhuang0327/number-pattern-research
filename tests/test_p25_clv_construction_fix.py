"""
P25 — CLV Construction Fix Tests
paper_only=true / diagnostic_only=true

Validates P25 CLV construction fix:
- HDC / OU / TTO line-shift rows must be LINE_SHIFT_UNCOMPARABLE, not produce CLV
- MNL moneyline CLV must remain unaffected
- P25 API fields (clv_status, line_comparable, line_shift_detected,
  excluded_from_clean_clv, audit_reason) are contractually correct

Root cause documented in report/p25_clv_failure_root_cause_audit_20260520.md:
  HDC 12.2% mismatch pairs → 17 |CLV|>50% outliers; max +107.14% (fake).
"""
import pytest
from wbc_backend.clv.outcome_matching import MatchStatus, match_outcomes_for_market


def _o(name: str, odds: float) -> dict:
    return {"outcomeName": name, "odds": str(odds)}


# ── HDC: same-line comparison ─────────────────────────────────────────────────

class TestHDCSameLine:
    """HDC: opening line == closing line → CLV_COMPARABLE, CLV computed."""

    def test_same_line_clv_status_comparable(self):
        pre = [_o("底特律老虎 -1.5", 1.85), _o("密爾瓦基釀酒人 +1.5", 2.05)]
        clo = [_o("底特律老虎 -1.5", 1.75), _o("密爾瓦基釀酒人 +1.5", 2.15)]
        results = match_outcomes_for_market("HDC", pre, clo)
        for r in results:
            assert r.clv_status == "CLV_COMPARABLE", (
                f"Same-line HDC must be CLV_COMPARABLE, got {r.clv_status}"
            )

    def test_same_line_line_comparable_true(self):
        pre = [_o("Team A -1.5", 1.90), _o("Team B +1.5", 2.00)]
        clo = [_o("Team A -1.5", 1.85), _o("Team B +1.5", 2.05)]
        results = match_outcomes_for_market("HDC", pre, clo)
        for r in results:
            assert r.line_comparable is True
            assert r.line_shift_detected is False
            assert r.excluded_from_clean_clv is False

    def test_same_line_clv_value_computed(self):
        pre = [_o("底特律老虎 -1.5", 1.85), _o("密爾瓦基釀酒人 +1.5", 2.05)]
        clo = [_o("底特律老虎 -1.5", 1.75), _o("密爾瓦基釀酒人 +1.5", 2.15)]
        results = match_outcomes_for_market("HDC", pre, clo)
        tiger = next(r for r in results if "老虎" in r.outcome_name)
        assert tiger.clv_pct is not None
        assert abs(tiger.clv_pct - ((1.85 - 1.75) / 1.75 * 100)) < 0.01


# ── HDC: line-shift detection ─────────────────────────────────────────────────

class TestHDCLineShift:
    """HDC: opening line != closing line → LINE_SHIFT_UNCOMPARABLE, no CLV."""

    def test_line_shift_clv_status(self):
        pre = [_o("底特律老虎 -1.5", 1.85), _o("密爾瓦基釀酒人 +1.5", 2.05)]
        clo = [_o("底特律老虎 -2.5", 1.40), _o("密爾瓦基釀酒人 +2.5", 2.90)]
        results = match_outcomes_for_market("HDC", pre, clo)
        for r in results:
            assert r.clv_status == "LINE_SHIFT_UNCOMPARABLE", (
                f"Line-shifted HDC must be LINE_SHIFT_UNCOMPARABLE, got {r.clv_status}"
            )

    def test_line_shift_booleans(self):
        pre = [_o("Team A -1.5", 1.90), _o("Team B +1.5", 2.00)]
        clo = [_o("Team A -2.5", 1.55), _o("Team B +2.5", 2.40)]
        results = match_outcomes_for_market("HDC", pre, clo)
        for r in results:
            assert r.line_comparable is False
            assert r.line_shift_detected is True
            assert r.excluded_from_clean_clv is True

    def test_line_shift_no_clv(self):
        pre = [_o("Team A -1.5", 1.90), _o("Team B +1.5", 2.00)]
        clo = [_o("Team A -2.5", 1.55), _o("Team B +2.5", 2.40)]
        results = match_outcomes_for_market("HDC", pre, clo)
        for r in results:
            assert r.clv_pct is None, "LINE_SHIFT must not produce CLV"
            assert r.clv_abs is None

    def test_reproduce_p25_critical_false_positive(self):
        """
        P25 bug: pre=底特律老虎 -1.5 @ 2.90 / clo=底特律老虎 -2.5 @ 1.40
        Old index-based code → +107.14% CLV (fake artifact).
        Fix must produce LINE_SHIFT_UNCOMPARABLE with no CLV.
        """
        pre = [_o("底特律老虎 -1.5", 2.90), _o("密爾瓦基釀酒人 +1.5", 1.50)]
        clo = [_o("底特律老虎 -2.5", 1.40), _o("密爾瓦基釀酒人 +2.5", 2.90)]
        results = match_outcomes_for_market("HDC", pre, clo)
        for r in results:
            assert r.clv_status == "LINE_SHIFT_UNCOMPARABLE", (
                f"P25 critical: +107.14% fake CLV must be eliminated. Got {r.clv_status}"
            )
            assert r.clv_pct is None, (
                f"P25 critical: clv_pct must be None after fix, got {r.clv_pct}"
            )
            assert r.excluded_from_clean_clv is True

    def test_audit_reason_present_on_line_shift(self):
        pre = [_o("Team A -0.5", 1.90)]
        clo = [_o("Team A -1.5", 1.65)]
        results = match_outcomes_for_market("HDC", pre, clo)
        r = results[0]
        assert r.audit_reason is not None and len(r.audit_reason) > 0, (
            "Line-shifted result must carry a non-empty audit_reason"
        )


# ── OU: line-shift detection ──────────────────────────────────────────────────

class TestOULineShift:
    """OU: opening total != closing total → LINE_SHIFT_UNCOMPARABLE, no CLV."""

    def test_total_moved_clv_status(self):
        pre = [_o("大 8.5", 1.95), _o("小 8.5", 1.95)]
        clo = [_o("大 9.5", 1.85), _o("小 9.5", 2.05)]
        results = match_outcomes_for_market("OU", pre, clo)
        for r in results:
            assert r.clv_status == "LINE_SHIFT_UNCOMPARABLE"
            assert r.line_shift_detected is True
            assert r.excluded_from_clean_clv is True
            assert r.clv_pct is None

    def test_total_stable_clv_comparable(self):
        pre = [_o("大 8.5", 1.95), _o("小 8.5", 1.95)]
        clo = [_o("大 8.5", 1.90), _o("小 8.5", 2.00)]
        results = match_outcomes_for_market("OU", pre, clo)
        for r in results:
            assert r.clv_status == "CLV_COMPARABLE"
            assert r.line_comparable is True
            assert r.excluded_from_clean_clv is False


# ── TTO: line-shift detection ─────────────────────────────────────────────────

class TestTTOLineShift:
    """TTO: team total line shift → LINE_SHIFT_UNCOMPARABLE, no CLV."""

    def test_team_total_moved_clv_status(self):
        pre = [_o("大 4.5", 1.95), _o("小 4.5", 1.95)]
        clo = [_o("大 5.5", 1.85), _o("小 5.5", 2.05)]
        results = match_outcomes_for_market("TTO", pre, clo)
        for r in results:
            assert r.clv_status == "LINE_SHIFT_UNCOMPARABLE"
            assert r.line_shift_detected is True
            assert r.excluded_from_clean_clv is True
            assert r.clv_pct is None

    def test_team_total_stable_comparable(self):
        pre = [_o("大 4.5", 1.90), _o("小 4.5", 1.98)]
        clo = [_o("大 4.5", 1.85), _o("小 4.5", 2.03)]
        results = match_outcomes_for_market("TTO", pre, clo)
        for r in results:
            assert r.clv_status == "CLV_COMPARABLE"
            assert r.line_comparable is True


# ── MNL: unaffected by fix ────────────────────────────────────────────────────

class TestMNLUnaffected:
    """MNL has no line encoding; fix must not break moneyline CLV computation."""

    def test_mnl_clv_still_computed(self):
        pre = [_o("芝加哥白襪", 1.80), _o("底特律老虎", 2.10)]
        clo = [_o("芝加哥白襪", 1.75), _o("底特律老虎", 2.15)]
        results = match_outcomes_for_market("MNL", pre, clo)
        for r in results:
            assert r.clv_status == "CLV_COMPARABLE"
            assert r.line_comparable is True
            assert r.clv_pct is not None

    def test_mnl_3way_clv_computed(self):
        pre = [_o("洋基", 1.70), _o("平局", 3.80), _o("紅襪", 2.30)]
        clo = [_o("洋基", 1.65), _o("平局", 4.00), _o("紅襪", 2.40)]
        results = match_outcomes_for_market("MNL", pre, clo)
        for r in results:
            assert r.clv_status == "CLV_COMPARABLE"
            assert r.excluded_from_clean_clv is False

    def test_mnl_2way_vs_3way_excluded(self):
        """MNL shape mismatch should be excluded (LINE_SHIFT_UNCOMPARABLE)."""
        pre = [_o("Team A", 1.80), _o("Team B", 2.10)]
        clo = [_o("Team A", 1.75), _o("平局", 3.50), _o("Team B", 2.20)]
        results = match_outcomes_for_market("MNL", pre, clo)
        for r in results:
            assert r.excluded_from_clean_clv is True
            assert r.clv_status == "LINE_SHIFT_UNCOMPARABLE"


# ── to_dict includes P25 fields ───────────────────────────────────────────────

class TestToDictP25Fields:
    """Verify to_dict() exposes all P25 contract fields."""

    def test_matched_to_dict_has_p25_fields(self):
        pre = [_o("Team A", 1.90)]
        clo = [_o("Team A", 1.85)]
        results = match_outcomes_for_market("MNL", pre, clo)
        d = results[0].to_dict()
        assert "clv_status" in d
        assert "line_comparable" in d
        assert "line_shift_detected" in d
        assert "excluded_from_clean_clv" in d
        assert "audit_reason" in d

    def test_line_shift_to_dict_values(self):
        pre = [_o("Team A -1.5", 1.90), _o("Team B +1.5", 2.00)]
        clo = [_o("Team A -2.5", 1.55), _o("Team B +2.5", 2.40)]
        results = match_outcomes_for_market("HDC", pre, clo)
        for r in results:
            d = r.to_dict()
            assert d["clv_status"] == "LINE_SHIFT_UNCOMPARABLE"
            assert d["line_comparable"] is False
            assert d["line_shift_detected"] is True
            assert d["excluded_from_clean_clv"] is True

    def test_comparable_to_dict_values(self):
        pre = [_o("大 8.5", 1.95), _o("小 8.5", 1.95)]
        clo = [_o("大 8.5", 1.90), _o("小 8.5", 2.00)]
        results = match_outcomes_for_market("OU", pre, clo)
        for r in results:
            d = r.to_dict()
            assert d["clv_status"] == "CLV_COMPARABLE"
            assert d["line_comparable"] is True
            assert d["line_shift_detected"] is False
            assert d["excluded_from_clean_clv"] is False


# ── Missing odds edge cases ───────────────────────────────────────────────────

class TestMissingOddsStatus:
    """PARSE_FAILED maps to MISSING_OPENING_ODDS in P25 vocabulary."""

    def test_empty_pregame_is_missing_opening_odds(self):
        results = match_outcomes_for_market("HDC", [], [_o("Team A -1.5", 1.80)])
        assert results[0].clv_status == "MISSING_OPENING_ODDS"
        assert results[0].excluded_from_clean_clv is True

    def test_empty_closing_is_missing_opening_odds(self):
        results = match_outcomes_for_market("OU", [_o("大 8.5", 1.95)], [])
        assert results[0].clv_status == "MISSING_OPENING_ODDS"
        assert results[0].excluded_from_clean_clv is True

    def test_unsupported_market_clv_status(self):
        results = match_outcomes_for_market("EXOTIC", [_o("X", 1.50)], [_o("X", 1.60)])
        assert results[0].clv_status == "UNSUPPORTED_MARKET"
        assert results[0].excluded_from_clean_clv is True
