"""
P264B — Hide Empty Legacy D3 Tab From Default Navigation
Read-only index.html tests: verify legacy D3 nav tab is hidden (display:none),
SSOT nav remains visible, all P258 locked strings and both endpoints preserved.
No API calls, no DB access.
"""
import re
import pathlib
import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


@pytest.fixture(scope="module")
def html() -> str:
    assert INDEX_HTML.exists(), f"index.html not found: {INDEX_HTML}"
    return INDEX_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def p258_section(html) -> str:
    m = re.search(
        r"<!-- ===== P258O D3 Strategy Status.*?<!-- ===== END P258O =====",
        html, re.DOTALL,
    )
    assert m, "P258O section not found in index.html"
    return m.group(0)


@pytest.fixture(scope="module")
def p263b_section(html) -> str:
    m = re.search(
        r"<!-- ===== P263B D3 Strategy Status.*?<!-- ===== END P263B =====",
        html, re.DOTALL,
    )
    assert m, "P263B section not found in index.html"
    return m.group(0)


# ---------------------------------------------------------------------------
# 1. Legacy D3 nav tab is hidden from default navigation
# ---------------------------------------------------------------------------

def test_legacy_nav_button_present_in_dom(html):
    """data-section attribute must remain in DOM for contract compliance."""
    assert 'data-section="p258-d3-audit"' in html


def test_legacy_nav_button_hidden_display_none(html):
    """Legacy D3 nav button must have display:none so it is not visible by default."""
    legacy_pos = html.find('data-section="p258-d3-audit"')
    assert legacy_pos != -1
    btn_snippet = html[legacy_pos - 200:legacy_pos + 200]
    assert "display:none" in btn_snippet, (
        "Legacy D3 nav button must have display:none — it should not appear in default navigation"
    )


def test_legacy_nav_button_not_visible_default(html):
    """Legacy nav button must not lack display:none — opacity-only is not sufficient."""
    legacy_pos = html.find('data-section="p258-d3-audit"')
    btn_snippet = html[legacy_pos - 200:legacy_pos + 200]
    # Extract the style attribute value
    style_m = re.search(r'style="([^"]*)"', btn_snippet)
    assert style_m, "Legacy nav button must have a style attribute"
    style = style_m.group(1)
    assert "display:none" in style, (
        f"Legacy nav button style must contain display:none, got: {style!r}"
    )


# ---------------------------------------------------------------------------
# 2. SSOT D3 nav tab is visible (no display:none)
# ---------------------------------------------------------------------------

def test_ssot_nav_button_exists(html):
    assert 'data-section="p263b-d3-ssot"' in html


def test_ssot_nav_button_not_hidden(html):
    """SSOT D3 nav button must NOT have display:none."""
    ssot_pos = html.find('data-section="p263b-d3-ssot"')
    assert ssot_pos != -1
    btn_snippet = html[ssot_pos - 200:ssot_pos + 200]
    assert "display:none" not in btn_snippet, (
        "SSOT D3 nav button must not be hidden with display:none"
    )


def test_ssot_nav_before_legacy_in_dom(html):
    """SSOT nav button must appear before legacy nav button."""
    ssot_pos = html.find('data-section="p263b-d3-ssot"')
    legacy_pos = html.find('data-section="p258-d3-audit"')
    assert ssot_pos != -1 and legacy_pos != -1
    assert ssot_pos < legacy_pos


# ---------------------------------------------------------------------------
# 3. SSOT section intact with all fields
# ---------------------------------------------------------------------------

def test_ssot_section_exists(html):
    assert 'id="p263b-d3-ssot-section"' in html


def test_ssot_success_rate_columns(p263b_section):
    for col in ["30期", "100期", "500期", "1500期"]:
        assert col in p263b_section, f"SSOT section missing column: {col}"


def test_ssot_lifecycle_field(p263b_section):
    assert "lifecycle" in p263b_section or "生命週期" in p263b_section


def test_ssot_registry_status_field(p263b_section):
    assert "registry_status" in p263b_section or "註冊狀態" in p263b_section


def test_ssot_can_open_detail_field(p263b_section):
    assert "can_open_detail" in p263b_section or "可開明細" in p263b_section


def test_ssot_missing_reason_field(p263b_section):
    assert "missing_reason" in p263b_section or "缺漏" in p263b_section


def test_ssot_fetches_coverage_endpoint(html):
    assert "/api/replay/d3-strategy-status-coverage" in html


# ---------------------------------------------------------------------------
# 4. Legacy warning copy preserved in P258O section
# ---------------------------------------------------------------------------

def test_legacy_warning_banner_preserved(p258_section):
    assert "p258-legacy-warning-p264a" in p258_section


def test_legacy_warning_not_current_strategy(p258_section):
    assert "不代表目前策略總數" in p258_section


def test_legacy_warning_refers_to_ssot(p258_section):
    assert "SSOT" in p258_section or "D3 策略狀態 (SSOT)" in p258_section


def test_legacy_warning_mentions_ssot_count(p258_section):
    assert "40 strategies" in p258_section


# ---------------------------------------------------------------------------
# 5. P258N/O/P locked contract strings intact
# ---------------------------------------------------------------------------

def test_p258_locked_section_id(html):
    assert 'id="p258-d3-audit-section"' in html


def test_p258_locked_disclaimer_banner(p258_section):
    assert "p258-disclaimer-banner" in p258_section


def test_p258_locked_not_yet_rejected(p258_section):
    assert "NOT_YET_REJECTED" in p258_section


def test_p258_locked_prediction_model(p258_section):
    assert "預測模型" in p258_section or "prediction model" in p258_section.lower()


def test_p258_locked_d3_title(p258_section):
    assert "D3" in p258_section
    assert "合約稽核" in p258_section or "Strategy Status" in p258_section


def test_p258_details_collapse_preserved(p258_section):
    assert "<details>" in p258_section


# ---------------------------------------------------------------------------
# 6. Both endpoints preserved
# ---------------------------------------------------------------------------

def test_old_endpoint_preserved(html):
    assert "/api/replay/d3-strategy-status-audit" in html


def test_new_endpoint_preserved(html):
    assert "/api/replay/d3-strategy-status-coverage" in html


# ---------------------------------------------------------------------------
# 7. No misleading "14 strategies" wording in primary nav or section title
# ---------------------------------------------------------------------------

def test_ssot_section_not_contaminated_by_legacy_warning(p263b_section):
    assert "p258-legacy-warning-p264a" not in p263b_section


def test_ssot_section_not_contaminated_by_14_rows(p263b_section):
    """SSOT section must not contain '14 rows' wording that misleads on strategy count."""
    assert "14 rows" not in p263b_section
