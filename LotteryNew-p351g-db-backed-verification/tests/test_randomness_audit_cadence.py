"""
test_randomness_audit_cadence.py
====================================
P0-1 — Randomness Audit Cadence Gate (2026-05-08)

Risk mitigated: R04 — randomness audit goes silently stale.

Policy source: wiki/system/randomness_final_verdict.md §9 (policy v0.1)
  - Max 14 calendar days between audits
  - Max 50 new draws since last audit
  - Either threshold triggers failure

Summary file:   outputs/randomness_audit/randomness_audit_summary.md
  Expected line: **Run timestamp:** <ISO-8601 timestamp>

Acceptance criteria:
  - Passes against current summary (last run 2026-05-01, today 2026-05-08 → 7 days < 14 day limit)
  - Fails when last_run is 60 days old (fixture test)
  - Fails when summary file is absent (fixture test)
  - No network dependency; runs fully offline in CI
"""
from __future__ import annotations

import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# ─── Policy constants (wiki/system/randomness_final_verdict.md §9 policy v0.1) ─

CADENCE_MAX_CALENDAR_DAYS: int = 14
CADENCE_MAX_NEW_DRAWS: int = 50  # trigger if this many new draws exist since last audit

# ─── Paths ────────────────────────────────────────────────────────────────────

REPO = Path(__file__).parent.parent
SUMMARY_FILE = REPO / "outputs" / "randomness_audit" / "randomness_audit_summary.md"
WIKI_VERDICT = REPO / "wiki" / "system" / "randomness_final_verdict.md"

# ─── Parsing helpers ──────────────────────────────────────────────────────────

_TS_PATTERN = re.compile(r"\*\*Run timestamp:\*\*\s+(.+)")


def _parse_last_run(text: str) -> datetime:
    """
    Extract the Run timestamp from a summary markdown text.
    Returns an aware UTC datetime.
    Raises ValueError if not found or unparseable.
    """
    m = _TS_PATTERN.search(text)
    if not m:
        raise ValueError(
            "Could not find '**Run timestamp:**' line in audit summary"
        )
    raw = m.group(1).strip()
    # Try ISO format; handle optional timezone info
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"Unrecognisable timestamp format: {raw!r}") from exc
    # Normalise to UTC-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _check_cadence(last_run: datetime, now: datetime) -> tuple[bool, str]:
    """
    Returns (is_stale, reason).
    stale = True means the audit should be re-run.
    """
    age_days = (now - last_run).total_seconds() / 86400.0
    if age_days > CADENCE_MAX_CALENDAR_DAYS:
        return True, (
            f"Audit is {age_days:.1f} calendar days old "
            f"(policy limit: {CADENCE_MAX_CALENDAR_DAYS} days). "
            "Re-run scripts/randomness_audit.py."
        )
    return False, f"Audit is {age_days:.1f} days old — within {CADENCE_MAX_CALENDAR_DAYS}-day policy."


# ─── Tests ────────────────────────────────────────────────────────────────────


class TestCadencePolicyDefinition:
    """Policy must be formally defined in the wiki before the gate is meaningful."""

    def test_wiki_verdict_exists(self):
        assert WIKI_VERDICT.exists(), \
            f"wiki/system/randomness_final_verdict.md not found: {WIKI_VERDICT}"

    def test_wiki_contains_cadence_section(self):
        text = WIKI_VERDICT.read_text(encoding="utf-8")
        assert "policy v0.1" in text, \
            "randomness_final_verdict.md must contain 'policy v0.1' cadence section (§9)"

    def test_wiki_cadence_max_days_consistent(self):
        """The policy number in the wiki must match the constant in this test file."""
        text = WIKI_VERDICT.read_text(encoding="utf-8")
        assert str(CADENCE_MAX_CALENDAR_DAYS) in text, \
            (
                f"Wiki must mention the {CADENCE_MAX_CALENDAR_DAYS}-day cadence limit "
                "to stay in sync with this test."
            )

    def test_wiki_cadence_max_draws_consistent(self):
        text = WIKI_VERDICT.read_text(encoding="utf-8")
        assert str(CADENCE_MAX_NEW_DRAWS) in text, \
            (
                f"Wiki must mention the {CADENCE_MAX_NEW_DRAWS}-draw cadence limit "
                "to stay in sync with this test."
            )


class TestSummaryFileParsing:
    """Unit tests for the parsing helper — no filesystem dependency."""

    def test_parse_valid_timestamp(self):
        text = "**Run timestamp:** 2026-05-01T23:39:17.808663\n"
        dt = _parse_last_run(text)
        assert dt.year == 2026
        assert dt.month == 5
        assert dt.day == 1
        assert dt.hour == 23

    def test_parse_raises_when_no_timestamp(self):
        text = "# Some other markdown without timestamp"
        with pytest.raises(ValueError, match="Run timestamp"):
            _parse_last_run(text)

    def test_parse_aware_datetime_returned(self):
        text = "**Run timestamp:** 2026-05-01T00:00:00\n"
        dt = _parse_last_run(text)
        assert dt.tzinfo is not None, "Returned datetime must be timezone-aware"

    def test_check_cadence_fresh(self):
        now = datetime(2026, 5, 8, tzinfo=timezone.utc)
        last_run = datetime(2026, 5, 1, tzinfo=timezone.utc)  # 7 days ago
        stale, reason = _check_cadence(last_run, now)
        assert not stale, f"7-day-old audit should NOT be stale (limit={CADENCE_MAX_CALENDAR_DAYS}d). reason={reason}"

    def test_check_cadence_stale_at_15_days(self):
        now = datetime(2026, 5, 8, tzinfo=timezone.utc)
        last_run = now - timedelta(days=15)
        stale, reason = _check_cadence(last_run, now)
        assert stale, f"15-day-old audit MUST be stale (limit={CADENCE_MAX_CALENDAR_DAYS}d). reason={reason}"

    def test_check_cadence_stale_at_60_days(self):
        now = datetime(2026, 5, 8, tzinfo=timezone.utc)
        last_run = now - timedelta(days=60)
        stale, reason = _check_cadence(last_run, now)
        assert stale, f"60-day-old audit MUST be stale. reason={reason}"

    def test_check_cadence_exactly_at_limit_is_fresh(self):
        """Exactly at limit (14 days) should not be stale (> not >=)."""
        now = datetime(2026, 5, 8, tzinfo=timezone.utc)
        last_run = now - timedelta(days=CADENCE_MAX_CALENDAR_DAYS)
        stale, _ = _check_cadence(last_run, now)
        assert not stale, f"Exactly {CADENCE_MAX_CALENDAR_DAYS} days old should NOT be stale"

    def test_check_cadence_one_second_over_limit_is_stale(self):
        now = datetime(2026, 5, 8, tzinfo=timezone.utc)
        last_run = now - timedelta(days=CADENCE_MAX_CALENDAR_DAYS, seconds=1)
        stale, _ = _check_cadence(last_run, now)
        assert stale, f"One second over {CADENCE_MAX_CALENDAR_DAYS} days must be stale"


class TestFixtureStaleness:
    """
    Fixture-based tests that verify the gate FAILS for stale/missing data.
    These use tmp_path and do NOT modify the real summary file.
    """

    def test_fail_when_summary_file_absent(self, tmp_path):
        """Gate must fail (raise) when summary file is missing."""
        missing = tmp_path / "nonexistent_summary.md"
        assert not missing.exists()
        with pytest.raises((FileNotFoundError, OSError)):
            text = missing.read_text(encoding="utf-8")
            _parse_last_run(text)

    def test_fail_when_last_run_60_days_ago_fixture(self, tmp_path):
        """
        Simulate a stale audit: last_run = 60 days before today.
        The cadence gate MUST report stale.
        """
        now = datetime.now(tz=timezone.utc)
        stale_dt = now - timedelta(days=60)
        stale_ts = stale_dt.strftime("%Y-%m-%dT%H:%M:%S")

        summary_content = f"""\
# Lottery Randomness Audit Report

**Run timestamp:** {stale_ts}
**Simulations:** 2,000 (seed=42)
## FINAL VERDICT
**🔶 WEAK_DEVIATIONS_NOT_SIGNIFICANT_AFTER_CORRECTION**
"""
        fixture_file = tmp_path / "randomness_audit_summary.md"
        fixture_file.write_text(summary_content, encoding="utf-8")

        text = fixture_file.read_text(encoding="utf-8")
        last_run = _parse_last_run(text)
        stale, reason = _check_cadence(last_run, now)

        assert stale, (
            f"60-day-old fixture MUST trigger stale. "
            f"last_run={stale_dt.date()} now={now.date()} reason={reason}"
        )

    def test_pass_after_restore_with_recent_fixture(self, tmp_path):
        """
        After 'fixing' the stale timestamp to today, the gate must pass.
        Simulates the '修復後恢復通過' requirement.
        """
        now = datetime.now(tz=timezone.utc)
        recent_ts = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")

        summary_content = f"""\
# Lottery Randomness Audit Report

**Run timestamp:** {recent_ts}
**Simulations:** 2,000 (seed=42)
## FINAL VERDICT
**🔶 WEAK_DEVIATIONS_NOT_SIGNIFICANT_AFTER_CORRECTION**
"""
        fixture_file = tmp_path / "randomness_audit_summary.md"
        fixture_file.write_text(summary_content, encoding="utf-8")

        text = fixture_file.read_text(encoding="utf-8")
        last_run = _parse_last_run(text)
        stale, reason = _check_cadence(last_run, now)

        assert not stale, (
            f"2-hour-old fixture MUST pass (not stale). reason={reason}"
        )

    def test_fail_stale_gate_function_returns_true(self, tmp_path):
        """Direct stale check: 30 days → must be stale."""
        now = datetime(2026, 5, 8, tzinfo=timezone.utc)
        last_run = now - timedelta(days=30)
        stale, reason = _check_cadence(last_run, now)
        assert stale, f"30-day-old audit must be stale. reason={reason}"

    def test_fail_when_summary_has_bad_timestamp(self, tmp_path):
        """Gate must fail when timestamp format is unrecognisable."""
        bad_content = "**Run timestamp:** not-a-date-at-all\n"
        fixture_file = tmp_path / "bad_summary.md"
        fixture_file.write_text(bad_content, encoding="utf-8")
        with pytest.raises(ValueError):
            _parse_last_run(fixture_file.read_text(encoding="utf-8"))


class TestRealSummaryFile:
    """
    Live test against the real outputs/randomness_audit/randomness_audit_summary.md.
    Fails if the file is missing or the audit is stale per policy.
    """

    def test_summary_file_exists(self):
        assert SUMMARY_FILE.exists(), (
            f"Randomness audit summary not found: {SUMMARY_FILE}\n"
            "Fix: run scripts/randomness_audit.py to generate it."
        )

    def test_summary_is_readable(self):
        text = SUMMARY_FILE.read_text(encoding="utf-8")
        assert len(text) > 50, "Summary file appears empty or too short"

    def test_summary_contains_run_timestamp(self):
        text = SUMMARY_FILE.read_text(encoding="utf-8")
        assert "Run timestamp:" in text, (
            "Summary file must contain 'Run timestamp:' line.\n"
            f"File: {SUMMARY_FILE}"
        )

    def test_last_run_parseable(self):
        text = SUMMARY_FILE.read_text(encoding="utf-8")
        dt = _parse_last_run(text)
        assert dt.year >= 2026, f"Parsed timestamp looks wrong: {dt}"

    def test_summary_contains_verdict(self):
        """Audit summary must include a FINAL VERDICT section."""
        text = SUMMARY_FILE.read_text(encoding="utf-8")
        assert "FINAL VERDICT" in text, (
            "Audit summary must contain 'FINAL VERDICT' section — "
            "summary may be from a failed/incomplete audit run."
        )

    def test_audit_not_stale_by_calendar(self):
        """
        MAIN GATE: fail if the randomness audit is older than CADENCE_MAX_CALENDAR_DAYS.

        Current policy (wiki/system/randomness_final_verdict.md §9, policy v0.1):
          max 14 calendar days between audits.

        If this test fails, run:
          /Library/Developer/CommandLineTools/usr/bin/python3 scripts/randomness_audit.py
        then re-run this test.
        """
        text = SUMMARY_FILE.read_text(encoding="utf-8")
        last_run = _parse_last_run(text)
        now = datetime.now(tz=timezone.utc)
        stale, reason = _check_cadence(last_run, now)
        assert not stale, (
            f"CADENCE GATE FAILURE — randomness audit is stale!\n"
            f"  {reason}\n"
            f"  Summary file: {SUMMARY_FILE}\n"
            f"  Fix: re-run scripts/randomness_audit.py"
        )
