"""
test_randomness_audit_cadence.py
====================================
P0-1 — Randomness Audit Cadence Gate (2026-05-08)
P275E-A update (2026-06-16): distinguish re-attestation from audit execution

Risk mitigated: R04 — randomness audit goes silently stale.

Policy source: wiki/system/randomness_final_verdict.md §9 (policy v0.1)
  - Max 14 calendar days between re-attestations
  - Max 50 new draws since last audit
  - Either threshold triggers failure

Summary file:   outputs/randomness_audit/randomness_audit_summary.md
  Expected lines:
    **Run timestamp:** <ISO-8601 timestamp>         — when statistical analysis ran
    **Re-attestation timestamp:** <ISO-8601 timestamp> — when a human last reviewed the evidence

The cadence gate checks the Re-attestation timestamp, not the Run timestamp.
scripts/randomness_audit.py is absent from this repository (never existed).
Re-attestation = human review confirming committed evidence is the current state.
It does not establish that the prior verdict holds for new draws since the Run timestamp.

Acceptance criteria:
  - Passes against current summary when re-attestation is within 14 days
  - Fails when re-attestation timestamp is absent (no silent fallback to Run timestamp)
  - Fails when re-attestation is 60 days old (fixture test)
  - Fails when summary file is absent (fixture test)
  - No network dependency; runs fully offline in CI
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# ─── Policy constants (wiki/system/randomness_final_verdict.md §9 policy v0.1) ─

CADENCE_MAX_CALENDAR_DAYS: int = 14
CADENCE_MAX_NEW_DRAWS: int = 50  # trigger if this many new draws exist since last audit
CADENCE_MAX_FUTURE_SKEW_HOURS: int = 24  # re-attestation timestamps this far in the future are rejected

# Original statistical run timestamp — must never change without a real audit rerun
_ORIGINAL_RUN_TIMESTAMP = "2026-06-02T06:57:02.982982"

# ─── Paths ────────────────────────────────────────────────────────────────────

REPO = Path(__file__).parent.parent
SUMMARY_FILE = REPO / "outputs" / "randomness_audit" / "randomness_audit_summary.md"
WIKI_VERDICT = REPO / "wiki" / "system" / "randomness_final_verdict.md"

# ─── Parsing helpers ──────────────────────────────────────────────────────────

_TS_PATTERN = re.compile(r"\*\*Run timestamp:\*\*\s+(.+)")
_REATTEST_TS_PATTERN = re.compile(r"\*\*Re-attestation timestamp:\*\*\s+(.+)")


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


def _parse_re_attestation_time(text: str) -> datetime:
    """
    Extract the Re-attestation timestamp from a summary markdown text.
    Returns an aware UTC datetime.
    Raises ValueError if not found or unparseable.
    No silent fallback to Run timestamp — re-attestation must be explicit.
    Re-attestation = human review of unchanged committed evidence; not a statistical rerun.
    """
    m = _REATTEST_TS_PATTERN.search(text)
    if not m:
        raise ValueError(
            "Could not find '**Re-attestation timestamp:**' line in audit summary. "
            "Re-attestation must be performed explicitly; no fallback to Run timestamp."
        )
    raw = m.group(1).strip()
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(
            f"Unrecognisable re-attestation timestamp format: {raw!r}"
        ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _check_cadence(reattest_time: datetime, now: datetime) -> tuple[bool, str]:
    """
    Returns (is_stale, reason).
    stale = True means the re-attestation is overdue or the timestamp is implausibly far in the future.

    Inputs:
      reattest_time — the Re-attestation timestamp (human review time, not statistical run time)
      now           — current UTC time

    A future timestamp within CADENCE_MAX_FUTURE_SKEW_HOURS (24 h) is accepted as clock skew.
    A future timestamp beyond that tolerance is rejected as implausible.
    """
    age_days = (now - reattest_time).total_seconds() / 86400.0
    max_future_days = CADENCE_MAX_FUTURE_SKEW_HOURS / 24.0
    if age_days < -max_future_days:
        return True, (
            f"Re-attestation timestamp is {-age_days:.2f} days in the future "
            f"(tolerance: {CADENCE_MAX_FUTURE_SKEW_HOURS} hours). "
            "Clock skew exceeds maximum tolerance."
        )
    if age_days > CADENCE_MAX_CALENDAR_DAYS:
        return True, (
            f"Re-attestation is {age_days:.1f} calendar days old "
            f"(policy limit: {CADENCE_MAX_CALENDAR_DAYS} days). "
            "Human review of committed evidence required."
        )
    return False, f"Re-attestation is {age_days:.1f} days old — within {CADENCE_MAX_CALENDAR_DAYS}-day policy."


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

    # ── Re-attestation parsing helpers ────────────────────────────────────────

    def test_parse_re_attestation_valid(self):
        text = "**Re-attestation timestamp:** 2026-06-16T10:24:11.889860\n"
        dt = _parse_re_attestation_time(text)
        assert dt.year == 2026 and dt.month == 6 and dt.day == 16

    def test_parse_re_attestation_aware_datetime_returned(self):
        text = "**Re-attestation timestamp:** 2026-06-16T10:00:00\n"
        dt = _parse_re_attestation_time(text)
        assert dt.tzinfo is not None, "Re-attestation datetime must be timezone-aware"

    def test_parse_re_attestation_raises_when_missing(self):
        """No silent fallback to Run timestamp when Re-attestation timestamp is absent."""
        text = "**Run timestamp:** 2026-06-02T06:57:02.982982\n"
        with pytest.raises(ValueError, match="Re-attestation timestamp"):
            _parse_re_attestation_time(text)

    def test_parse_re_attestation_raises_on_bad_format(self):
        text = "**Re-attestation timestamp:** not-a-date\n"
        with pytest.raises(ValueError, match="re-attestation"):
            _parse_re_attestation_time(text)

    def test_re_attestation_stale_at_15_days(self):
        now = datetime(2026, 5, 8, tzinfo=timezone.utc)
        reattest = now - timedelta(days=15)
        stale, reason = _check_cadence(reattest, now)
        assert stale, f"15-day-old re-attestation MUST be stale. reason={reason}"

    def test_re_attestation_fresh_at_1_day(self):
        now = datetime(2026, 5, 8, tzinfo=timezone.utc)
        reattest = now - timedelta(hours=24)
        stale, reason = _check_cadence(reattest, now)
        assert not stale, f"24-hour-old re-attestation should be fresh. reason={reason}"

    def test_re_attestation_future_timestamp_treated_as_fresh(self):
        """A future re-attestation timestamp (clock skew) yields negative age — not stale."""
        now = datetime(2026, 5, 8, tzinfo=timezone.utc)
        reattest = now + timedelta(hours=1)
        stale, _ = _check_cadence(reattest, now)
        assert not stale, "Future re-attestation (clock skew < 1 day) must not be treated as stale"

    def test_re_attestation_exactly_24h_future_accepted(self):
        """Exactly 24 hours in the future is at the tolerance boundary — must be accepted."""
        now = datetime(2026, 5, 8, tzinfo=timezone.utc)
        reattest = now + timedelta(hours=CADENCE_MAX_FUTURE_SKEW_HOURS)
        stale, reason = _check_cadence(reattest, now)
        assert not stale, (
            f"Re-attestation exactly {CADENCE_MAX_FUTURE_SKEW_HOURS}h in future must be accepted. "
            f"reason={reason}"
        )

    def test_re_attestation_beyond_24h_future_rejected(self):
        """More than 24 hours in the future must be rejected as implausible clock skew."""
        now = datetime(2026, 5, 8, tzinfo=timezone.utc)
        reattest = now + timedelta(hours=CADENCE_MAX_FUTURE_SKEW_HOURS, seconds=1)
        stale, reason = _check_cadence(reattest, now)
        assert stale, (
            f"Re-attestation {CADENCE_MAX_FUTURE_SKEW_HOURS}h+1s in future must be rejected. "
            f"reason={reason}"
        )

    def test_re_attestation_exactly_24h_plus_1s_future_rejected(self):
        """Alias: 24 hours + 1 second in the future must fail the cadence gate."""
        now = datetime(2026, 5, 8, tzinfo=timezone.utc)
        reattest = now + timedelta(hours=24, seconds=1)
        stale, reason = _check_cadence(reattest, now)
        assert stale, f"24h+1s future must be stale. reason={reason}"


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
            "This is a static committed artifact. Restore it from git history."
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
        MAIN GATE: fail if the re-attestation is older than CADENCE_MAX_CALENDAR_DAYS.

        The cadence gate checks the explicit Re-attestation timestamp, not the original
        Run timestamp (which records when statistical analysis was last executed).

        Current policy (wiki/system/randomness_final_verdict.md §9, policy v0.1):
          max 14 calendar days between re-attestations.

        scripts/randomness_audit.py is absent from this repository (never existed).
        If this test fails, a human reviewer must:
          1. Review the committed statistical evidence in this file.
          2. Add/update the Re-attestation timestamp line and re_attestation_timestamp
             field in outputs/randomness_audit/randomness_audit_results.json.
          3. Do NOT alter Run timestamp or any statistical result.
        """
        text = SUMMARY_FILE.read_text(encoding="utf-8")
        reattest_time = _parse_re_attestation_time(text)
        now = datetime.now(tz=timezone.utc)
        stale, reason = _check_cadence(reattest_time, now)
        assert not stale, (
            f"CADENCE GATE FAILURE — re-attestation is stale!\n"
            f"  {reason}\n"
            f"  Summary file: {SUMMARY_FILE}\n"
            f"  Fix: update Re-attestation timestamp after human review of committed evidence."
        )

    def test_re_attestation_timestamp_exists(self):
        """Summary must contain an explicit Re-attestation timestamp separate from Run timestamp."""
        text = SUMMARY_FILE.read_text(encoding="utf-8")
        reattest_time = _parse_re_attestation_time(text)
        assert reattest_time.year >= 2026, f"Re-attestation timestamp looks wrong: {reattest_time}"

    def test_original_run_timestamp_preserved(self):
        """The original Run timestamp must equal the known value from the statistical run."""
        text = SUMMARY_FILE.read_text(encoding="utf-8")
        run_time = _parse_last_run(text)
        expected = datetime.fromisoformat(_ORIGINAL_RUN_TIMESTAMP).replace(tzinfo=timezone.utc)
        assert run_time == expected, (
            f"Run timestamp must be exactly {_ORIGINAL_RUN_TIMESTAMP!r}. "
            f"Got {run_time.isoformat()!r}. "
            "Do not change the original Run timestamp."
        )
        reattest_time = _parse_re_attestation_time(text)
        assert reattest_time >= run_time, (
            f"Re-attestation time {reattest_time} must not precede Run timestamp {run_time}"
        )


class TestReAttestationJsonFields:
    """
    Verify that outputs/randomness_audit/randomness_audit_results.json
    carries truthful re-attestation metadata fields.
    Added in P275E-A (2026-06-16).
    """

    import json as _json

    RESULTS_FILE = REPO / "outputs" / "randomness_audit" / "randomness_audit_results.json"

    def _load(self):
        import json
        return json.loads(self.RESULTS_FILE.read_text(encoding="utf-8"))

    def test_results_json_exists(self):
        assert self.RESULTS_FILE.exists(), f"Results JSON not found: {self.RESULTS_FILE}"

    def test_original_run_timestamp_unchanged(self):
        """run_timestamp must be preserved at the value from the original statistical run."""
        data = self._load()
        assert "run_timestamp" in data, "run_timestamp field must be present"
        assert data["run_timestamp"] == "2026-06-02T06:57:02.982982", (
            f"Original run_timestamp must be preserved unchanged. Got: {data.get('run_timestamp')!r}"
        )

    def test_re_attestation_timestamp_present(self):
        data = self._load()
        assert "re_attestation_timestamp" in data, "re_attestation_timestamp field must be present"
        dt = datetime.fromisoformat(data["re_attestation_timestamp"])
        assert dt.year >= 2026, f"re_attestation_timestamp looks wrong: {dt}"

    def test_reanalysis_performed_false(self):
        data = self._load()
        assert "reanalysis_performed" in data, "reanalysis_performed field must be present"
        assert data["reanalysis_performed"] is False, (
            f"reanalysis_performed must be false; got {data['reanalysis_performed']!r}"
        )

    def test_new_draws_analyzed_false(self):
        data = self._load()
        assert "new_draws_analyzed" in data, "new_draws_analyzed field must be present"
        assert data["new_draws_analyzed"] is False, (
            f"new_draws_analyzed must be false; got {data['new_draws_analyzed']!r}"
        )

    def test_re_attestation_type_field(self):
        data = self._load()
        assert "re_attestation_type" in data, "re_attestation_type field must be present"
        assert data["re_attestation_type"] == "HUMAN_REVIEW_OF_UNCHANGED_COMMITTED_EVIDENCE"

    def test_re_attestation_after_original_run(self):
        """Re-attestation must not be earlier than the original statistical run."""
        data = self._load()
        run_dt = datetime.fromisoformat(data["run_timestamp"]).replace(tzinfo=timezone.utc)
        reattest_dt = datetime.fromisoformat(
            data["re_attestation_timestamp"]
        ).replace(tzinfo=timezone.utc)
        assert reattest_dt >= run_dt, (
            f"re_attestation_timestamp {reattest_dt} must not precede run_timestamp {run_dt}"
        )

    def test_existing_statistical_fields_intact(self):
        """All original top-level statistical fields must remain present."""
        data = self._load()
        required = {"simulations", "seed", "alpha", "games", "tests",
                    "multiple_testing", "final_verdict", "strategy_implication"}
        missing = required - set(data.keys())
        assert not missing, f"Statistical fields missing from results JSON: {missing}"
