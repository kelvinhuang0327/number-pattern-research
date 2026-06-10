"""
P264A — Hide Legacy D3 Artifact From Default UI
Read-only index.html tests: verify SSOT is primary, legacy is demoted/collapsed.
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
# 1. Nav order — SSOT appears before Legacy in nav
# ---------------------------------------------------------------------------

def test_ssot_nav_button_exists(html):
    assert 'data-section="p263b-d3-ssot"' in html


def test_legacy_nav_button_exists(html):
    assert 'data-section="p258-d3-audit"' in html


def test_ssot_nav_before_legacy_nav(html):
    """SSOT nav button must appear before Legacy nav button in the HTML."""
    ssot_pos = html.find('data-section="p263b-d3-ssot"')
    legacy_pos = html.find('data-section="p258-d3-audit"')
    assert ssot_pos != -1 and legacy_pos != -1
    assert ssot_pos < legacy_pos, (
        f"SSOT nav pos {ssot_pos} should be before legacy nav pos {legacy_pos}"
    )


def test_legacy_nav_button_visually_demoted(html):
    """Legacy nav button must carry opacity or similar dimming style."""
    legacy_pos = html.find('data-section="p258-d3-audit"')
    # Extract the button tag (up to closing >)
    btn_snippet = html[legacy_pos - 150:legacy_pos + 200]
    assert "opacity" in btn_snippet, (
        "Legacy nav button should have opacity styling to visually demote it"
    )


def test_legacy_nav_label_indicates_legacy(html):
    """Legacy nav button label must contain 'Legacy' indicator."""
    legacy_pos = html.find('data-section="p258-d3-audit"')
    btn_snippet = html[legacy_pos - 10:legacy_pos + 250]
    assert "Legacy" in btn_snippet, (
        "Legacy nav button label should contain 'Legacy'"
    )


# ---------------------------------------------------------------------------
# 2. SSOT section — primary / intact
# ---------------------------------------------------------------------------

def test_ssot_section_exists(html):
    assert 'id="p263b-d3-ssot-section"' in html


def test_ssot_fetches_coverage_endpoint(html):
    assert "/api/replay/d3-strategy-status-coverage" in html


def test_ssot_has_success_rate_columns(p263b_section):
    for col in ["30期", "100期", "500期", "1500期"]:
        assert col in p263b_section, f"SSOT section missing column: {col}"


def test_ssot_has_lifecycle_field(p263b_section):
    assert "lifecycle" in p263b_section or "生命週期" in p263b_section


def test_ssot_has_registry_status_field(p263b_section):
    assert "registry_status" in p263b_section or "註冊狀態" in p263b_section


def test_ssot_has_can_open_detail_field(p263b_section):
    assert "can_open_detail" in p263b_section or "可開明細" in p263b_section


def test_ssot_has_missing_reason_field(p263b_section):
    assert "missing_reason" in p263b_section or "缺漏" in p263b_section


def test_ssot_not_contaminated_by_legacy_warning(p263b_section):
    """Legacy warning div must NOT appear inside the SSOT section."""
    assert "p258-legacy-warning-p264a" not in p263b_section


# ---------------------------------------------------------------------------
# 3. Legacy section — demoted, not primary
# ---------------------------------------------------------------------------

def test_legacy_section_exists(p258_section):
    assert len(p258_section) > 100


def test_legacy_section_id_preserved(html):
    assert 'id="p258-d3-audit-section"' in html


def test_legacy_section_has_legacy_badge(p258_section):
    """P258O section heading must carry a 'Legacy' label."""
    assert "Legacy" in p258_section


def test_legacy_section_has_warning_banner(p258_section):
    assert "p258-legacy-warning-p264a" in p258_section


def test_legacy_warning_not_current_strategy(p258_section):
    assert "不代表目前策略總數" in p258_section


def test_legacy_warning_refers_to_ssot(p258_section):
    assert "SSOT" in p258_section or "D3 策略狀態 (SSOT)" in p258_section


def test_legacy_warning_mentions_correct_ssot_count(p258_section):
    """Warning must state 40 strategies / 41 cells to direct users correctly."""
    assert "40 strategies" in p258_section


def test_legacy_section_content_collapsed_by_default(p258_section):
    """section-content must be wrapped in <details> (collapsed by default)."""
    assert "<details>" in p258_section


def test_legacy_section_details_closed(p258_section):
    assert "</details>" in p258_section


def test_legacy_section_has_expand_summary(p258_section):
    assert "<summary" in p258_section


# ---------------------------------------------------------------------------
# 4. P258N/O/P locked contract strings — must remain intact
# ---------------------------------------------------------------------------

def test_p258_locked_nav_button(html):
    assert 'data-section="p258-d3-audit"' in html


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


# ---------------------------------------------------------------------------
# 5. Both endpoints preserved
# ---------------------------------------------------------------------------

def test_old_endpoint_string_preserved(html):
    assert "/api/replay/d3-strategy-status-audit" in html


def test_new_endpoint_string_preserved(html):
    assert "/api/replay/d3-strategy-status-coverage" in html
