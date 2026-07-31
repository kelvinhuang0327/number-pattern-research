"""Tests for the P545D no-force launchd quiescence playbook validator.

All fixtures are textual/synthetic or mutations of the committed playbook. No test starts,
stops, or signals a service, and no test opens a database. Coverage maps to the 30 required
cases in the P545D task specification (see the numbered comments below).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from analysis import p545d_launchd_quiescence_playbook_validator as validator

REPO_ROOT = Path(validator.__file__).resolve().parents[1]
PLAYBOOK_PATH = REPO_ROOT / "docs" / "operations" / "p545d_launchd_quiescence_playbook.md"


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------

def good_text() -> str:
    return PLAYBOOK_PATH.read_text(encoding="utf-8")


def result_by_name(report: validator.ValidationReport, name: str) -> validator.CheckResult:
    for r in report.results:
        if r.name == name:
            return r
    raise AssertionError(f"no check named {name!r}; have {[r.name for r in report.results]}")


def check_ok(text: str, name: str) -> bool:
    return result_by_name(validator.validate_text(text), name).ok


def with_bash(text: str, cmd: str) -> str:
    return text + "\n\n```bash\n" + cmd + "\n```\n"


# --------------------------------------------------------------------------------------
# foundational: the committed playbook passes
# --------------------------------------------------------------------------------------

def test_committed_playbook_passes_all_checks():
    report = validator.validate_file(PLAYBOOK_PATH)
    assert report.ok, [(r.name, r.detail) for r in report.results if not r.ok]


def test_good_text_is_valid_baseline():
    assert validator.validate_text(good_text()).ok


# --------------------------------------------------------------------------------------
# 1. Required playbook sections
# --------------------------------------------------------------------------------------

def test_required_sections_present():
    assert check_ok(good_text(), "required_sections")


def test_missing_section_fails():
    mutated = good_text().replace("## C. Service Discovery", "## Z. Service Discovery")
    assert not check_ok(mutated, "required_sections")


def test_subheader_does_not_satisfy_section_anchor():
    # `### C.1` must not count as the `## C.` H2 section header.
    only_subheader = good_text().replace("## C. Service Discovery", "## Z. Service Discovery")
    assert "### C.1" in only_subheader
    assert not check_ok(only_subheader, "required_sections")


# --------------------------------------------------------------------------------------
# 2. Proven-service evidence requirement
# --------------------------------------------------------------------------------------

def test_proven_service_evidence_required():
    assert check_ok(good_text(), "managed_service_has_evidence")
    mutated = good_text().replace("PROVEN", "guessed")
    assert not check_ok(mutated, "managed_service_has_evidence")


# --------------------------------------------------------------------------------------
# 3. Explicit launchd domain requirement
# --------------------------------------------------------------------------------------

def test_state_changing_launchctl_requires_domain():
    # label present, no gui/system domain -> ambiguous
    mutated = with_bash(good_text(), "launchctl bootout com.kelvin.lottery.dev")
    assert not check_ok(mutated, "launchctl_explicit_domain_label")


# --------------------------------------------------------------------------------------
# 4. Explicit label/path requirement
# --------------------------------------------------------------------------------------

def test_state_changing_launchctl_requires_label():
    # domain present, wrong/missing lottery label -> ambiguous
    mutated = with_bash(good_text(), "launchctl bootout gui/$(id -u)/com.example.other")
    assert not check_ok(mutated, "launchctl_explicit_domain_label")


# --------------------------------------------------------------------------------------
# 5. Dependency-aware stop order  &  6. Reverse restore order
# --------------------------------------------------------------------------------------

def test_stop_order_defined():
    assert check_ok(good_text(), "stop_and_restore_orders")
    assert not check_ok(good_text().replace("Stop order", "sequence"), "stop_and_restore_orders")


def test_restore_order_is_reverse():
    # remove the reverse justification -> restore order not proven reverse
    assert not check_ok(good_text().replace("reverse", "some"), "stop_and_restore_orders")
    assert not check_ok(good_text().replace("Restore order", "startup"), "stop_and_restore_orders")


# --------------------------------------------------------------------------------------
# 7. Bounded stop confirmation  &  8. Bounded restore confirmation
# --------------------------------------------------------------------------------------

def test_bounded_confirmation_present():
    assert check_ok(good_text(), "bounded_confirmation_and_zero_handle")
    assert not check_ok(good_text().replace("max_attempts", "loop"), "bounded_confirmation_and_zero_handle")


def test_bounded_confirmation_in_both_stop_and_restore_sections():
    text = good_text()
    stop_section = text.split("## F.", 1)[1].split("## G.", 1)[0]
    restore_section = text.split("## I.", 1)[1].split("## J.", 1)[0]
    assert "max_attempts" in stop_section, "stop section lacks a bounded confirmation loop"
    assert "max_attempts" in restore_section, "restore section lacks a bounded confirmation loop"


# --------------------------------------------------------------------------------------
# 9. Respawn-control verification
# --------------------------------------------------------------------------------------

def test_respawn_control_markers_present():
    assert "KeepAlive" in good_text() and "bootout" in good_text()
    assert not check_ok(good_text().replace("KeepAlive", "AutoStart"), "required_markers")


# --------------------------------------------------------------------------------------
# 10-14. STOP classifications
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize("token", [
    "STOP_UNIDENTIFIED_DB_HOLDER",   # 10 unidentified-holder STOP
    "STOP_PERSISTENT_SIDECAR",       # 11 persistent-sidecar STOP
    "STOP_DB_DRIFT",                 # 12 DB-drift STOP
    "STOP_GRACEFUL_STOP_FAILED",     # 13 graceful-stop failure STOP
    "STOP_RESTORE_FAILED",           # 14 restore failure STOP
])
def test_stop_classifications_required(token):
    assert token in good_text()
    assert not check_ok(good_text().replace(token, "STOP_X"), "stop_classifications")


# --------------------------------------------------------------------------------------
# 15-22. dangerous / ambiguous executable-command rejection
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize("dangerous", [
    "kill -9 $BACKEND_PID",                              # 15 kill -9
    "launchctl bootout gui/$(id -u)/com.kelvin.lottery.dev --force",  # 16 force flag
    "rm backend.pid",                                    # 17 PID-file deletion
    'rm "$DB-wal"',                                      # 18 WAL deletion
    'rm "$DB-shm"',                                      # 18 SHM deletion
    'cp "$DB" /tmp/lottery_backup.db',                   # 19 DB copy/dump
    'sqlite3 "$DB" "SELECT count(*) FROM draws"',        # 20 sqlite open
    'sqlite3 "$DB" "PRAGMA wal_checkpoint(TRUNCATE)"',   # 21 checkpoint
    'sqlite3 "$DB" "VACUUM"',                            # 21 VACUUM
    "launchctl unload ~/Library/LaunchAgents/x.plist",   # 22 ambiguous load/unload
    "launchctl load ~/Library/LaunchAgents/x.plist",     # 22 ambiguous load/unload
    "curl http://localhost:8002/health",                 # network
    "pkill -9 -f app.py",                                # force kill
])
def test_dangerous_commands_rejected(dangerous):
    assert not check_ok(with_bash(good_text(), dangerous), "no_dangerous_executable_commands")


def test_forbidden_tokens_in_text_are_allowed():
    # The always-forbidden list documents kill -9 / sqlite3 / VACUUM in prose; that must NOT trip
    # the executable-command scan (only ```bash``` blocks are scanned).
    assert check_ok(good_text(), "no_dangerous_executable_commands")


# --------------------------------------------------------------------------------------
# 23. existing stop_all.sh explicitly noncompliant
# --------------------------------------------------------------------------------------

def test_stop_all_marked_noncompliant():
    assert check_ok(good_text(), "stop_all_marked_noncompliant")
    # strip every noncompliance annotation the check recognises; stop_all.sh is still mentioned but
    # is now never flagged as noncompliant -> must fail.
    neutral = good_text()
    for marker in ("NONCOMPLIANT", "noncompliant", "MUST NOT", "forbidden", "Do not"):
        neutral = neutral.replace(marker, "ok")
    assert "stop_all.sh" in neutral
    assert not check_ok(neutral, "stop_all_marked_noncompliant")


# --------------------------------------------------------------------------------------
# 24-27. validator is safe by construction (source guards + behaviour)
# --------------------------------------------------------------------------------------

def validator_source() -> str:
    return Path(validator.__file__).read_text(encoding="utf-8")


def test_validator_performs_no_write():
    src = validator_source()
    for bad in ("os.remove(", "os.unlink(", "shutil.rmtree(", ".unlink(", ".write_text(",
                ".write_bytes(", "os.rmdir(", "open("):
        # allow read-only open via Path.read_text only; raw open() is disallowed entirely
        assert bad not in src, f"validator must not contain {bad!r}"


def test_validator_write_free_behaviour(tmp_path):
    before = set(os.listdir(tmp_path))
    validator.validate_text(good_text())
    (tmp_path / "probe.md").write_text(good_text(), encoding="utf-8")
    validator.validate_file(tmp_path / "probe.md")
    after = set(os.listdir(tmp_path))
    assert after == before | {"probe.md"}, "validate_* created unexpected files"


def test_validator_performs_no_signal():
    src = validator_source()
    for bad in ("os.kill(", "signal.SIG", ".terminate(", ".send_signal(", "os.system("):
        assert bad not in src, f"validator must not contain {bad!r}"
    # the read-only preflight allowlist must be free of signalling / force tokens
    validator._assert_preflight_allowlist_safe()


def test_validator_performs_no_db_open():
    src = validator_source()
    for bad in ("import sqlite3", "sqlite3.", "sqlalchemy", "import pandas"):
        assert bad not in src, f"validator must not reference {bad!r}"


def test_validator_performs_no_network():
    src = validator_source()
    for bad in ("import socket", "import urllib", "urllib.request", "import http.client",
                "http.client", "import requests", "import telnetlib", "socket."):
        assert bad not in src, f"validator must not reference {bad!r}"


def test_preflight_allowlist_only_readonly_commands():
    for cmd in validator.READONLY_PREFLIGHT_COMMANDS:
        joined = " ".join(cmd)
        assert cmd[0] in {"launchctl", "ps", "lsof", "stat", "shasum", "sha256sum", "bash", "git"}
        assert validator._command_is_readonly_safe(joined), f"preflight cmd not read-only safe: {joined!r}"
    # sanity: a mutating command is rejected by the same gate
    assert not validator._command_is_readonly_safe("launchctl bootout gui/$(id -u)/com.kelvin.lottery.dev")
    assert not validator._command_is_readonly_safe("kill -9 123")


# --------------------------------------------------------------------------------------
# 28. deterministic static-validation output
# --------------------------------------------------------------------------------------

def test_deterministic_output():
    a = validator.validate_text(good_text())
    b = validator.validate_text(good_text())
    assert a.results == b.results
    assert a.to_lines() == b.to_lines()
    assert a.ok == b.ok is True


# --------------------------------------------------------------------------------------
# 29. fail-closed when no installed plist exists
# --------------------------------------------------------------------------------------

def test_fail_closed_no_installed_plist():
    text = good_text()
    # the playbook must classify the one label as NOT_INSTALLED and carry the runtime-dependency verdict
    assert "NOT_INSTALLED" in text
    assert "PLAYBOOK_READY_WITH_RUNTIME_MAPPING_DEPENDENCIES" in text
    # fail-closed proof: `launchctl bootstrap` must NOT appear as an executable (```bash```) instruction
    for body in validator.bash_blocks(text):
        assert "launchctl bootstrap" not in body, "bootstrap must not be an executable command"


# --------------------------------------------------------------------------------------
# 30. fail-closed when service attribution is incomplete
# --------------------------------------------------------------------------------------

def test_fail_closed_incomplete_attribution():
    text = good_text()
    assert "STOP_UNIDENTIFIED_DB_HOLDER" in text
    assert "Attribution rule" in text
    assert "fail-closed" in text
    # historical labels must not be promoted to a manageable service without evidence
    assert "HISTORICAL_ONLY" in text


# --------------------------------------------------------------------------------------
# CLI exit codes (deterministic, read-only)
# --------------------------------------------------------------------------------------

def test_main_returns_zero_on_valid_playbook(capsys):
    rc = validator.main(["--playbook", str(PLAYBOOK_PATH)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "RESULT: PASS" in out


def test_main_returns_one_on_invalid_playbook(tmp_path, capsys):
    bad = tmp_path / "bad.md"
    bad.write_text("# not a playbook\n", encoding="utf-8")
    rc = validator.main(["--playbook", str(bad)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "RESULT: FAIL" in out


def test_code_block_extraction_distinguishes_bash_and_text():
    sample = "```bash\nls -la\n```\n\n```text\nkill -9 everything\n```\n"
    blocks = dict((lang, body) for lang, body in validator.iter_code_blocks(sample))
    assert "ls -la" in blocks["bash"]
    assert "kill -9 everything" in blocks["text"]
    # a dangerous token in a ```text``` block is not an executable violation
    assert result_by_name(validator.validate_text(good_text() + sample),
                          "no_dangerous_executable_commands").ok
