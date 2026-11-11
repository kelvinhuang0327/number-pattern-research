"""
tests/test_p70_path_a_the_odds_api_historical_pull.py
=======================================================
P70 — PATH_A: The Odds API Historical Pull Test Suite
All tests run in dry-run mode (no API key required).
≥20 tests required.
"""

from __future__ import annotations

import csv
import io
import json
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "_p70_path_a_the_odds_api_historical_pull.py"
SUMMARY_PATH = (
    REPO_ROOT
    / "data"
    / "mlb_2025"
    / "derived"
    / "p70_path_a_the_odds_api_historical_pull_summary.json"
)
P69_SUMMARY_PATH = (
    REPO_ROOT
    / "data"
    / "mlb_2025"
    / "derived"
    / "p69_ceo_decision_memo_path_a_authorization_summary.json"
)
OUTPUT_CSV_PATH = REPO_ROOT / "data" / "mlb_2025" / "mlb_odds_2024_real.csv"
ACTIVE_TASK_PATH = REPO_ROOT / "00-Plan" / "roadmap" / "active_task.md"

# ---------------------------------------------------------------------------
# Module import
# ---------------------------------------------------------------------------
spec = importlib.util.spec_from_file_location(
    "_p70_path_a_the_odds_api_historical_pull", SCRIPT_PATH
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_summary() -> dict:
    with open(SUMMARY_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_p69() -> dict:
    with open(P69_SUMMARY_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# §1 — CEO Authorization
# ---------------------------------------------------------------------------

def test_ceo_authorization_confirmed_in_module():
    """CEO_AUTHORIZATION_CONFIRMED must be True."""
    assert mod.CEO_AUTHORIZATION_CONFIRMED is True


def test_ceo_authorization_phrase_exact():
    """CEO authorization phrase must match exactly."""
    expected = (
        "YES authorize P61 PATH_A The Odds API historical 2024 MLB moneyline pull "
        "for paper-only validation"
    )
    assert mod.CEO_AUTHORIZATION_PHRASE == expected


def test_ceo_authorization_in_summary():
    """Summary must confirm CEO authorization."""
    summary = load_summary()
    assert summary["ceo_authorization_confirmed"] is True
    phrase = summary.get("ceo_authorization_phrase", "")
    assert "YES" in phrase and "PATH_A" in phrase


def test_p69_approval_phrase_matches_p70():
    """P70 CEO phrase must match P69 approval phrase exactly."""
    p69 = load_p69()
    assert p69["ceo_approval_phrase"] == mod.CEO_AUTHORIZATION_PHRASE


# ---------------------------------------------------------------------------
# §2 — Governance Constants
# ---------------------------------------------------------------------------

def test_paper_only_flag():
    assert mod.PAPER_ONLY is True


def test_diagnostic_only_flag():
    assert mod.DIAGNOSTIC_ONLY is True


def test_kelly_deploy_not_allowed():
    assert mod.KELLY_DEPLOY_ALLOWED is False


def test_real_bet_not_allowed():
    assert mod.REAL_BET_ALLOWED is False


def test_production_not_ready():
    assert mod.PRODUCTION_READY is False


def test_runtime_logic_not_changed():
    assert mod.RUNTIME_RECOMMENDATION_LOGIC_CHANGED is False


def test_tsl_crawler_not_called():
    assert mod.TSL_CRAWLER_CALLED is False


def test_bulk_scraping_not_performed():
    assert mod.BULK_SCRAPING_PERFORMED is False


def test_anti_bot_bypass_not_attempted():
    assert mod.ANTI_BOT_BYPASS_ATTEMPTED is False


def test_platt_constants_unchanged():
    assert mod.PLATT_A == pytest.approx(0.435432, rel=1e-6)
    assert mod.PLATT_B == pytest.approx(0.245464, rel=1e-6)


# ---------------------------------------------------------------------------
# §3 — Pull Configuration
# ---------------------------------------------------------------------------

def test_pull_config_sport():
    """Pull config must target baseball_mlb."""
    assert mod.PULL_CONFIG["sport"] == "baseball_mlb"


def test_pull_config_season_dates():
    """Pull config must target 2024 MLB regular season."""
    assert mod.PULL_CONFIG["season_start"] == "2024-03-20"
    assert mod.PULL_CONFIG["season_end"] == "2024-09-29"


def test_pull_config_market():
    """Pull config must target moneyline (h2h) market only."""
    assert mod.PULL_CONFIG["market"] == "h2h"


def test_pull_config_target_rows():
    """Estimated target rows must be in expected range for 2024 MLB season."""
    rows = mod.PULL_CONFIG["target_rows_estimate"]
    assert 1500 <= rows <= 5000, f"Unexpected target rows estimate: {rows}"


def test_required_output_fields():
    """All 9 required fields must be declared."""
    required = set(mod.REQUIRED_OUTPUT_FIELDS)
    expected = {
        "game_date", "home_team", "away_team", "home_ml", "away_ml",
        "bookmaker", "odds_timestamp", "closing_indicator", "source_trace",
    }
    assert expected <= required, f"Missing required fields: {expected - required}"


# ---------------------------------------------------------------------------
# §4 — Dry-Run Mode
# ---------------------------------------------------------------------------

def test_dry_run_mode_no_api_key():
    """When no API key is set, run_dry_run() must return DRY_RUN classification."""
    summary = mod.run_dry_run()
    assert summary["p70_classification"] == "P70_PATH_A_AUTHORIZED_AWAITING_API_KEY"
    assert summary["dry_run"] is True
    assert summary["api_key_configured"] is False
    assert summary["paid_api_called"] is False


def test_dry_run_rows_zero():
    """Dry-run must write 0 rows (no API call)."""
    summary = mod.run_dry_run()
    assert summary["rows_written"] == 0


def test_dry_run_includes_api_key_instructions():
    """Dry-run summary must include API key acquisition instructions."""
    summary = mod.run_dry_run()
    instructions = summary.get("api_key_acquisition_instructions", {})
    assert len(instructions) >= 4, "Insufficient API key instructions"
    # Must mention the-odds-api.com somewhere
    all_text = " ".join(str(v) for v in instructions.values()).lower()
    assert "the-odds-api" in all_text or "odds-api" in all_text


def test_load_api_key_returns_none_without_key(tmp_path):
    """load_api_key must return None when env var and .env are absent."""
    import os
    orig = os.environ.pop("THE_ODDS_API_KEY", None)
    try:
        # Use a non-existent env file
        orig_env = mod.ENV_PATH
        mod.ENV_PATH = tmp_path / ".env_nonexistent"
        key = mod.load_api_key()
        assert key is None
    finally:
        if orig is not None:
            os.environ["THE_ODDS_API_KEY"] = orig
        mod.ENV_PATH = orig_env


def test_load_api_key_from_env_file(tmp_path):
    """load_api_key must read key from .env file when env var is absent."""
    import os
    env_file = tmp_path / ".env"
    env_file.write_text("THE_ODDS_API_KEY=test_key_12345\n")
    orig = os.environ.pop("THE_ODDS_API_KEY", None)
    orig_env = mod.ENV_PATH
    try:
        mod.ENV_PATH = env_file
        key = mod.load_api_key()
        assert key == "test_key_12345"
    finally:
        if orig is not None:
            os.environ["THE_ODDS_API_KEY"] = orig
        mod.ENV_PATH = orig_env


# ---------------------------------------------------------------------------
# §5 — Decimal → American Odds Conversion
# ---------------------------------------------------------------------------

def test_american_odds_favourite():
    """Decimal < 2.0 → negative American odds."""
    result = mod._american_odds(1.50)
    assert result == -200, f"Expected -200, got {result}"


def test_american_odds_underdog():
    """Decimal ≥ 2.0 → positive American odds."""
    result = mod._american_odds(2.50)
    assert result == 150, f"Expected +150, got {result}"


def test_american_odds_even():
    """Decimal 2.0 → +100 American odds."""
    result = mod._american_odds(2.0)
    assert result == 100, f"Expected +100, got {result}"


def test_american_odds_heavy_favourite():
    """Heavy favourite decimal → large negative American."""
    result = mod._american_odds(1.20)
    assert result == -500, f"Expected -500, got {result}"


# ---------------------------------------------------------------------------
# §6 — Row Extraction
# ---------------------------------------------------------------------------

SAMPLE_EVENT = {
    "home_team": "New York Yankees",
    "away_team": "Boston Red Sox",
    "commence_time": "2024-07-04T20:00:00Z",
    "bookmakers": [
        {
            "key": "pinnacle",
            "title": "Pinnacle",
            "markets": [
                {
                    "key": "h2h",
                    "last_update": "2024-07-04T19:50:00Z",
                    "outcomes": [
                        {"name": "New York Yankees", "price": 1.75},
                        {"name": "Boston Red Sox", "price": 2.15},
                    ],
                }
            ],
        }
    ],
}


def test_extract_row_from_event_basic():
    """Row extraction must return all required fields."""
    row = mod._extract_row_from_event(SAMPLE_EVENT, "source=test")
    assert row is not None
    for field in mod.REQUIRED_OUTPUT_FIELDS:
        assert field in row, f"Missing field: {field}"


def test_extract_row_home_team():
    row = mod._extract_row_from_event(SAMPLE_EVENT, "source=test")
    assert row["home_team"] == "New York Yankees"


def test_extract_row_away_team():
    row = mod._extract_row_from_event(SAMPLE_EVENT, "source=test")
    assert row["away_team"] == "Boston Red Sox"


def test_extract_row_home_ml_is_int():
    row = mod._extract_row_from_event(SAMPLE_EVENT, "source=test")
    assert isinstance(row["home_ml"], int)


def test_extract_row_away_ml_is_int():
    row = mod._extract_row_from_event(SAMPLE_EVENT, "source=test")
    assert isinstance(row["away_ml"], int)


def test_extract_row_game_date():
    row = mod._extract_row_from_event(SAMPLE_EVENT, "source=test")
    assert row["game_date"] == "2024-07-04"


def test_extract_row_bookmaker():
    row = mod._extract_row_from_event(SAMPLE_EVENT, "source=test")
    assert row["bookmaker"] == "pinnacle"


def test_extract_row_closing_indicator():
    row = mod._extract_row_from_event(SAMPLE_EVENT, "source=test")
    assert "CLOSING" in row["closing_indicator"] or "PROXY" in row["closing_indicator"]


def test_extract_row_source_trace():
    row = mod._extract_row_from_event(SAMPLE_EVENT, "source=p70_test")
    assert "p70_test" in row["source_trace"]


def test_extract_row_no_h2h_market_returns_none():
    """Event with no h2h market must return None."""
    event = {
        "home_team": "Yankees",
        "away_team": "Red Sox",
        "commence_time": "2024-07-04T20:00:00Z",
        "bookmakers": [
            {
                "key": "pinnacle",
                "markets": [
                    {"key": "spreads", "outcomes": []}  # no h2h
                ],
            }
        ],
    }
    row = mod._extract_row_from_event(event, "source=test")
    assert row is None


# ---------------------------------------------------------------------------
# §7 — CSV Writer
# ---------------------------------------------------------------------------

def test_write_csv_creates_file(tmp_path):
    """write_csv must create file with correct headers."""
    rows = [
        {
            "game_date": "2024-04-01",
            "home_team": "Yankees",
            "away_team": "Red Sox",
            "home_ml": -150,
            "away_ml": 130,
            "bookmaker": "pinnacle",
            "odds_timestamp": "2024-04-01T19:50:00Z",
            "closing_indicator": "CLOSING_PROXY_COMMENCE_TIME",
            "source_trace": "source=test",
        }
    ]
    out = tmp_path / "test_output.csv"
    mod.write_csv(rows, out)
    assert out.exists()
    content = out.read_text()
    assert "game_date" in content
    assert "home_ml" in content


def test_write_csv_row_count(tmp_path):
    """write_csv must write correct number of rows."""
    rows = [
        {
            "game_date": f"2024-04-{i:02d}",
            "home_team": "Team A",
            "away_team": "Team B",
            "home_ml": -120,
            "away_ml": 105,
            "bookmaker": "pinnacle",
            "odds_timestamp": "2024-04-01T19:50:00Z",
            "closing_indicator": "CLOSING_PROXY_COMMENCE_TIME",
            "source_trace": "source=test",
        }
        for i in range(1, 6)
    ]
    out = tmp_path / "test_output.csv"
    mod.write_csv(rows, out)
    with open(out, newline="") as f:
        reader = csv.reader(f)
        all_rows = list(reader)
    # header + 5 data rows
    assert len(all_rows) == 6


# ---------------------------------------------------------------------------
# §8 — Classification Validity
# ---------------------------------------------------------------------------

def test_p70_classification_is_allowed():
    """P70 classification must be from VALID_P70_CLASSIFICATIONS."""
    summary = load_summary()
    cls = summary["p70_classification"]
    assert cls in mod.VALID_P70_CLASSIFICATIONS, (
        f"P70 classification {cls!r} not in VALID_P70_CLASSIFICATIONS"
    )


def test_p70_classification_dry_run():
    """Dry-run classification must be P70_PATH_A_AUTHORIZED_AWAITING_API_KEY."""
    summary = load_summary()
    assert summary["p70_classification"] == "P70_PATH_A_AUTHORIZED_AWAITING_API_KEY"


# ---------------------------------------------------------------------------
# §9 — Summary Structure
# ---------------------------------------------------------------------------

def test_summary_has_required_keys():
    summary = load_summary()
    required = {
        "p70_version", "p70_classification", "pull_date", "mode",
        "api_key_configured", "paid_api_called", "governance",
    }
    missing = required - set(summary.keys())
    assert not missing, f"Missing summary keys: {missing}"


def test_summary_governance_flags_correct():
    summary = load_summary()
    gov = summary["governance"]
    assert gov["paper_only"] is True
    assert gov["real_bet_allowed"] is False
    assert gov["kelly_deploy_allowed"] is False
    assert gov["production_ready"] is False
    assert gov["paid_api_called"] is False  # dry-run
    assert gov["platt_a"] == pytest.approx(0.435432, rel=1e-6)
    assert gov["platt_b"] == pytest.approx(0.245464, rel=1e-6)


# ---------------------------------------------------------------------------
# §10 — Forbidden Affirmative Scan
# ---------------------------------------------------------------------------

FORBIDDEN_PATTERNS = [
    "REAL_BET_ALLOWED: bool = True",
    "KELLY_DEPLOY_ALLOWED: bool = True",
    "PRODUCTION_READY: bool = True",
    "BULK_SCRAPING_PERFORMED: bool = True",
    "ANTI_BOT_BYPASS_ATTEMPTED: bool = True",
    "TSL_CRAWLER_CALLED: bool = True",
    "RUNTIME_RECOMMENDATION_LOGIC_CHANGED: bool = True",
    "CEO_AUTHORIZATION_CONFIRMED: bool = False",
    "PROMOTION_FREEZE: bool = False",
    "PAPER_ONLY: bool = False",
    "DIAGNOSTIC_ONLY: bool = False",
]


def test_forbidden_affirmative_scan_in_script():
    """P70 script must not contain any forbidden affirmative patterns."""
    text = SCRIPT_PATH.read_text(encoding="utf-8")
    violations = [p for p in FORBIDDEN_PATTERNS if p in text]
    assert not violations, f"Forbidden patterns in P70 script: {violations}"


# ---------------------------------------------------------------------------
# §11 — Active Task Updated
# ---------------------------------------------------------------------------

def test_active_task_contains_p70():
    content = ACTIVE_TASK_PATH.read_text(encoding="utf-8")
    assert "P70" in content


def test_active_task_contains_p70_completed():
    content = ACTIVE_TASK_PATH.read_text(encoding="utf-8")
    assert "P70" in content and "COMPLETED" in content


# ---------------------------------------------------------------------------
# §12 — Governance Build Helper
# ---------------------------------------------------------------------------

def test_build_governance_dry_run_paid_false():
    gov = mod._build_governance(paid_api_called=False)
    assert gov["paid_api_called"] is False
    assert gov["paper_only"] is True


def test_build_governance_live_paid_true():
    gov = mod._build_governance(paid_api_called=True)
    assert gov["paid_api_called"] is True
    assert gov["paper_only"] is True
    assert gov["real_bet_allowed"] is False


# ---------------------------------------------------------------------------
# §13 — run_p70 Integration (dry-run)
# ---------------------------------------------------------------------------

def test_run_p70_dry_run_writes_summary(tmp_path):
    """run_p70 in dry-run mode must write a valid summary JSON."""
    out = tmp_path / "p70_test_summary.json"
    summary = mod.run_p70(output_path=out)
    assert out.exists()
    assert summary["p70_classification"] == "P70_PATH_A_AUTHORIZED_AWAITING_API_KEY"
    loaded = json.loads(out.read_text())
    assert loaded["p70_classification"] == "P70_PATH_A_AUTHORIZED_AWAITING_API_KEY"


def test_run_p70_governance_assertions_block_bad_state():
    """run_p70 must fail if governance invariant is violated (assert guard)."""
    orig = mod.PAPER_ONLY
    try:
        mod.PAPER_ONLY = False
        with pytest.raises(AssertionError):
            mod.run_p70(output_path=Path("/tmp/p70_should_fail.json"))
    finally:
        mod.PAPER_ONLY = orig
