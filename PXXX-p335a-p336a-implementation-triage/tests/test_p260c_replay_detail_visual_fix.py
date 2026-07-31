"""P260C — Tests for Replay Detail Visual Fix (legacy white/green token style).

Validates that the CSS values in index.html match the legacy style spec:
- .replay-number-token: white background (#ffffff), dark text (#1f2328), circular (50%)
- .replay-number-token--hit: green solid (#28a745), white text (#ffffff)
- .replay-number-token--special: purple solid (#6e40c9), white text (#ffffff), pill (1000px)
- .replay-number-token--special-hit: lighter purple (#9b6dff), white text
- .replay-row--hit: subtle green background rgba(40,167,69,...)
- .replay-result-badge--hit: green (#28a745), white text
- .replay-result-badge--miss: light gray background, no dark colors
- P260A quick range 100/300/500/1500 still present; 1000 absent (regression)
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = REPO_ROOT / "index.html"


def _html() -> str:
    return HTML_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Group 1: Base token — white background, dark text
# ---------------------------------------------------------------------------

class TestBaseTokenWhiteStyle:
    def test_base_token_white_background(self):
        """.replay-number-token must use #ffffff background."""
        html = _html()
        # Find the .replay-number-token rule block (before the --hit modifier)
        m = re.search(
            r'\.replay-number-token\s*\{[^}]*background\s*:\s*([^;]+)',
            html
        )
        assert m, ".replay-number-token background not found"
        val = m.group(1).strip()
        assert '#ffffff' in val.lower() or 'rgb(255' in val.lower(), \
            f"Expected white background, got: {val}"

    def test_base_token_dark_text(self):
        """.replay-number-token must use dark text color."""
        html = _html()
        m = re.search(
            r'\.replay-number-token\s*\{[^}]*color\s*:\s*([^;]+)',
            html
        )
        assert m, ".replay-number-token color not found"
        val = m.group(1).strip()
        assert '#1f2328' in val.lower(), \
            f"Expected dark text #1f2328, got: {val}"

    def test_base_token_circular_border_radius(self):
        """.replay-number-token must use border-radius:50% for circular shape."""
        assert 'border-radius:50%' in _html()

    def test_base_token_no_dark_background(self):
        """Confirm dark GitHub theme background #161b22 is removed from base token."""
        html = _html()
        m = re.search(r'\.replay-number-token\s*\{([^}]+)\}', html)
        assert m, ".replay-number-token rule not found"
        rule_body = m.group(1)
        assert '#161b22' not in rule_body, \
            "Dark background #161b22 still present in base token — P260C fix not applied"


# ---------------------------------------------------------------------------
# Group 2: Hit token — green solid, white text
# ---------------------------------------------------------------------------

class TestHitTokenGreenStyle:
    def _hit_rule(self) -> str:
        html = _html()
        m = re.search(
            r'\.replay-number-token--hit\s*\{([^}]+)\}',
            html
        )
        assert m, ".replay-number-token--hit rule not found"
        return m.group(1)

    def test_hit_token_green_background(self):
        """.replay-number-token--hit must use green #28a745 background."""
        rule = self._hit_rule()
        assert '#28a745' in rule, \
            f"Expected green #28a745 in hit token, got rule: {rule}"

    def test_hit_token_white_text(self):
        """.replay-number-token--hit must use white text."""
        rule = self._hit_rule()
        # Use negative lookbehind to avoid matching border-color
        m = re.search(r'(?<!border-)(?<!border-)color\s*:\s*([^;]+)', rule)
        assert m, "color not found in hit token rule"
        val = m.group(1).strip()
        assert '#ffffff' in val.lower(), \
            f"Expected white text in hit token, got: {val}"

    def test_hit_token_no_dark_green_background(self):
        """Old dark green #1a3c2a must be removed from hit token."""
        rule = self._hit_rule()
        assert '#1a3c2a' not in rule, \
            "Old dark green background #1a3c2a still present — P260C fix not applied"

    def test_hit_token_no_dim_text(self):
        """Old dim green text #3fb950 must be removed from hit token."""
        rule = self._hit_rule()
        assert '#3fb950' not in rule, \
            "Old dim green text #3fb950 still present — P260C fix not applied"


# ---------------------------------------------------------------------------
# Group 3: Special token — purple solid, white text, pill shape
# ---------------------------------------------------------------------------

class TestSpecialTokenPurpleStyle:
    def _special_rule(self) -> str:
        html = _html()
        # Match .replay-number-token--special { ... } but not --special-hit
        m = re.search(
            r'\.replay-number-token--special\s*\{([^}]+)\}',
            html
        )
        assert m, ".replay-number-token--special rule not found"
        return m.group(1)

    def test_special_token_purple_background(self):
        """.replay-number-token--special must use purple #6e40c9 background."""
        rule = self._special_rule()
        assert '#6e40c9' in rule, \
            f"Expected purple #6e40c9 in special token, got: {rule}"

    def test_special_token_white_text(self):
        """.replay-number-token--special must use white text."""
        rule = self._special_rule()
        m = re.search(r'(?:^|;)\s*color\s*:\s*([^;]+)', rule)
        assert m, "color not found in special token rule"
        val = m.group(1).strip()
        assert '#ffffff' in val.lower(), \
            f"Expected white text in special token, got: {val}"

    def test_special_token_pill_border_radius(self):
        """.replay-number-token--special must use pill border-radius:1000px."""
        assert 'border-radius:1000px' in _html()

    def test_special_token_no_dark_purple_background(self):
        """Old dark purple #2d1f6e must be removed from special token."""
        rule = self._special_rule()
        assert '#2d1f6e' not in rule, \
            "Old dark purple #2d1f6e still present — P260C fix not applied"

    def test_special_token_no_dim_text(self):
        """Old dim purple text #b392f0 must be removed from special token."""
        rule = self._special_rule()
        assert '#b392f0' not in rule, \
            "Old dim text #b392f0 still present in special token — P260C fix not applied"


# ---------------------------------------------------------------------------
# Group 4: Special-hit token — lighter purple, white text
# ---------------------------------------------------------------------------

class TestSpecialHitTokenStyle:
    def _special_hit_rule(self) -> str:
        html = _html()
        m = re.search(
            r'\.replay-number-token--special-hit\s*\{([^}]+)\}',
            html
        )
        assert m, ".replay-number-token--special-hit rule not found"
        return m.group(1)

    def test_special_hit_background_lighter_purple(self):
        """.replay-number-token--special-hit must use #9b6dff."""
        rule = self._special_hit_rule()
        assert '#9b6dff' in rule, \
            f"Expected #9b6dff in special-hit token, got: {rule}"

    def test_special_hit_white_text(self):
        """.replay-number-token--special-hit must use white text."""
        rule = self._special_hit_rule()
        assert '#ffffff' in rule, \
            f"Expected white text in special-hit token, got: {rule}"


# ---------------------------------------------------------------------------
# Group 5: Row and badge styles
# ---------------------------------------------------------------------------

class TestRowAndBadgeStyles:
    def test_row_hit_uses_green_rgba(self):
        """.replay-row--hit must use green rgba (40,167,69 family)."""
        html = _html()
        m = re.search(r'\.replay-row--hit\s*\{([^}]+)\}', html)
        assert m, ".replay-row--hit rule not found"
        rule = m.group(1)
        assert 'rgba(40,167,69' in rule or 'rgba(40, 167, 69' in rule, \
            f"Expected green rgba in row hit, got: {rule}"

    def test_row_hit_opacity_gt_05(self):
        """.replay-row--hit opacity must be > 0.05 (at least 0.10) for visibility."""
        html = _html()
        m = re.search(r'\.replay-row--hit\s*\{[^}]*rgba\([^)]+,\s*([\d.]+)\)', html)
        assert m, "rgba opacity not found in .replay-row--hit"
        opacity = float(m.group(1))
        assert opacity >= 0.10, \
            f"Row hit opacity {opacity} too low — must be >= 0.10 for visibility"

    def test_result_badge_hit_green(self):
        """.replay-result-badge--hit must use green #28a745."""
        html = _html()
        m = re.search(r'\.replay-result-badge--hit\s*\{([^}]+)\}', html)
        assert m, ".replay-result-badge--hit rule not found"
        assert '#28a745' in m.group(1), \
            f"Expected #28a745 in result badge hit, got: {m.group(1)}"

    def test_result_badge_hit_white_text(self):
        """.replay-result-badge--hit must use white text."""
        html = _html()
        m = re.search(r'\.replay-result-badge--hit\s*\{([^}]+)\}', html)
        assert m, ".replay-result-badge--hit rule not found"
        rule = m.group(1)
        color_m = re.search(r'color\s*:\s*([^;]+)', rule)
        assert color_m, "color not found in badge hit rule"
        assert '#ffffff' in color_m.group(1).lower(), \
            f"Expected white text in badge hit, got: {color_m.group(1)}"

    def test_result_badge_miss_light_bg(self):
        """.replay-result-badge--miss must use light gray background #f6f8fa."""
        html = _html()
        m = re.search(r'\.replay-result-badge--miss\s*\{([^}]+)\}', html)
        assert m, ".replay-result-badge--miss rule not found"
        assert '#f6f8fa' in m.group(1), \
            f"Expected #f6f8fa in miss badge, got: {m.group(1)}"

    def test_result_badge_miss_no_pure_dark(self):
        """Miss badge must not use pure dark background #161b22."""
        html = _html()
        m = re.search(r'\.replay-result-badge--miss\s*\{([^}]+)\}', html)
        assert m, ".replay-result-badge--miss rule not found"
        assert '#161b22' not in m.group(1), \
            "Old dark background #161b22 still in miss badge — P260C fix not applied"


# ---------------------------------------------------------------------------
# Group 6: P260A regression — quick range buttons still correct
# ---------------------------------------------------------------------------

class TestP260ARegressionGuard:
    def test_range_100_still_present(self):
        assert 'data-testid="p260a-range-100"' in _html()

    def test_range_300_still_present(self):
        assert 'data-testid="p260a-range-300"' in _html()

    def test_range_500_still_present(self):
        assert 'data-testid="p260a-range-500"' in _html()

    def test_range_1500_still_present(self):
        assert 'data-testid="p260a-range-1500"' in _html()

    def test_range_1000_still_absent(self):
        assert 'data-testid="p260a-range-1000"' not in _html()

    def test_circular_border_radius_still_present(self):
        assert 'border-radius:50%' in _html()

    def test_pill_border_radius_still_present(self):
        assert 'border-radius:1000px' in _html()

    def test_token_classes_all_present(self):
        html = _html()
        for cls in [
            '.replay-number-token',
            '.replay-number-token--hit',
            '.replay-number-token--special',
            '.replay-number-token--special-hit',
            '.replay-row--hit',
            '.replay-result-badge--hit',
            '.replay-result-badge--miss',
        ]:
            assert cls in html, f"CSS class missing: {cls}"
