#!/usr/bin/env python3
"""P545D — read-only static validator for the no-force launchd quiescence playbook.

Safe by construction:

* The core (`validate_text`) is a **pure function of the playbook text**. It performs no
  file, network, database, process, or signal I/O.
* `validate_file` only *reads* a text file and delegates to `validate_text`.
* The module imports no SQLite/network client and contains no process-signal, file-delete,
  or file-write call. See ``tests/test_p545d_launchd_quiescence_playbook_validator.py`` which
  statically asserts this.
* An **optional, opt-in** live preflight (`--preflight`) runs only commands drawn from the
  hardcoded read-only allowlist ``READONLY_PREFLIGHT_COMMANDS`` and emits terminal output.
  It never changes launchd/service/process/PID/DB/sidecar state.

This validator statically enforces the playbook's own safety contract: every executable
(```` ```bash ````) block must be free of dangerous or ambiguous commands, and every required
section / marker / STOP classification must be present. Non-executable content (STOP rules,
the always-forbidden list, unresolved-mapping templates) lives in ```` ```text ```` blocks or
prose and is intentionally exempt from the executable-command scan.

Usage::

    python analysis/p545d_launchd_quiescence_playbook_validator.py            # validate default playbook
    python analysis/p545d_launchd_quiescence_playbook_validator.py --playbook PATH
    python analysis/p545d_launchd_quiescence_playbook_validator.py --preflight # + read-only live inspection

Exit code 0 == all checks passed; 1 == at least one check failed.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAYBOOK = REPO_ROOT / "docs" / "operations" / "p545d_launchd_quiescence_playbook.md"

# --------------------------------------------------------------------------------------
# Contract tokens (kept in sync with docs/operations/p545d_launchd_quiescence_playbook.md)
# --------------------------------------------------------------------------------------

REQUIRED_SECTIONS: Tuple[Tuple[str, str], ...] = (
    ("## A.", "Purpose and Scope"),
    ("## B.", "Preconditions"),
    ("## C.", "Service Discovery"),
    ("## D.", "Pre-Stop Evidence Capture"),
    ("## E.", "Safe Respawn Control"),
    ("## F.", "Graceful Stop Order"),
    ("## G.", "Quiescence Verification"),
    ("## H.", "Probe Handoff"),
    ("## I.", "Restore Procedure"),
    ("## J.", "Rollback and STOP Classifications"),
    ("## K.", "Always-Forbidden Actions"),
    ("## L.", "Evidence Retention"),
)

REQUIRED_STOP_TOKENS: Tuple[str, ...] = (
    "STOP_UNIDENTIFIED_DB_HOLDER",
    "STOP_PERSISTENT_SIDECAR",
    "STOP_DB_DRIFT",
    "STOP_GRACEFUL_STOP_FAILED",
    "STOP_RESTORE_FAILED",
)

# (token that must appear anywhere in the playbook, human description)
REQUIRED_MARKERS: Tuple[Tuple[str, str], ...] = (
    ("gui/$(id -u)", "explicit reproducible launchd domain"),
    ("com.kelvin.lottery.dev", "managed launchd label"),
    ("com.kelvin.lottery.dev.plist", "committed plist evidence path"),
    ("ZERO_OPEN_HANDLES", "zero-handle verification token"),
    ("KeepAlive", "respawn-control basis (plist KeepAlive)"),
    ("bootout", "launchd-native stop mechanism"),
    ("Stop order", "explicit stop order definition"),
    ("Restore order", "explicit restore order definition"),
    ("reverse", "restore is the reverse dependency order"),
    ("sha256", "DB content-hash stability check"),
    ("inode", "DB inode stability check"),
    ("T0", "quiescence sample T0"),
    ("T1", "quiescence sample T1"),
    ("max_attempts", "bounded confirmation loop"),
    ("PROVEN", "service confidence classification"),
    ("NOT_INSTALLED", "not-installed classification"),
    ("HISTORICAL_ONLY", "historical-only classification"),
)

# Must be *documented as forbidden* (these live in prose / ```text```, not in executable blocks).
REQUIRED_FORBIDDEN_DOC_TOKENS: Tuple[Tuple[str, str], ...] = (
    ("kill -9", "kill -9 documented forbidden"),
    ("--force", "force flag documented forbidden"),
    ("PID file", "PID-file deletion documented forbidden"),
    ("-wal", "WAL sidecar documented (do-not-delete)"),
    ("-shm", "SHM sidecar documented (do-not-delete)"),
    ("sqlite3", "sqlite open documented forbidden"),
    ("wal_checkpoint", "checkpoint documented forbidden"),
    ("VACUUM", "VACUUM documented forbidden"),
    ("ATTACH", "ATTACH documented forbidden"),
    ("DETACH", "DETACH documented forbidden"),
    ("stop_all.sh", "stop_all.sh referenced"),
)

# Dangerous patterns that must NEVER appear inside an executable (```bash```) block.
FORBIDDEN_BASH_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("kill/pkill signal", r"\b(kill|pkill)\b"),
    ("-9 / -KILL signal", r"(?<!\w)-9\b|-KILL\b"),
    ("force flag", r"--force\b|\brm\s+-[a-zA-Z]*f\b|\bpush\b[^\n]*--force|kickstart[^\n]*\s-k\b"),
    ("rm/cp/mv/dd/truncate of pid|db|wal|shm|journal",
     r"\b(rm|cp|mv|dd|truncate|tee)\b[^\n]*(\.pid|\.db\b|\.db-|-wal|-shm|-journal)"),
    ("sqlite client", r"\bsqlite3?\b"),
    ("db maintenance (checkpoint/vacuum/attach/detach/pragma)",
     r"wal_checkpoint|\bVACUUM\b|\bATTACH\b|\bDETACH\b|\bPRAGMA\b"),
    ("network command", r"(?:^|[|;&]\s*|\s)(curl|wget|telnet|ssh|scp|ncat)\b|(?:^|[|;&]\s*)nc\s"),
    ("ambiguous launchctl load/unload", r"launchctl\s+(load|unload)\b"),
)

# launchctl subcommands that change state and therefore require an explicit domain + label.
_STATE_CHANGING_LAUNCHCTL = re.compile(
    r"launchctl\s+(bootout|bootstrap|enable|disable|kickstart|load|unload)\b"
)
_DOMAIN_RE = re.compile(r"\b(gui|user|system|pid)/")
_LABEL_RE = re.compile(r"com\.kelvin\.lottery")

# Read-only commands the optional live preflight is permitted to run. Every entry is a fixed
# argv list; nothing here changes launchd/service/process/PID/DB/sidecar state.
READONLY_PREFLIGHT_COMMANDS: Tuple[Tuple[str, ...], ...] = (
    ("launchctl", "list"),
    ("bash", "-c", "launchctl print-disabled gui/$(id -u) | grep -i com.kelvin.lottery || true"),
    ("bash", "-c",
     "for p in 8002 8081 8080; do lsof -nP -iTCP:$p -sTCP:LISTEN 2>/dev/null || echo \"port $p idle\"; done"),
    ("bash", "-c",
     "ps -Ao pid,args | grep -iE 'lottery_api/app\\.py|http\\.server 808|uvicorn app:app|start_all\\.sh' "
     "| grep -viE 'grep|validator' || echo NO_LOTTERY_SERVICE_PROCESSES"),
    ("bash", "-c",
     "DB=" + str(REPO_ROOT / "lottery_api/data/lottery_v2.db") + "; "
     "lsof -nP -- \"$DB\" \"$DB-wal\" \"$DB-shm\" \"$DB-journal\" 2>/dev/null || echo ZERO_OPEN_HANDLES"),
    ("bash", "-c",
     "DB=" + str(REPO_ROOT / "lottery_api/data/lottery_v2.db") + "; "
     "for f in \"$DB\" \"$DB-wal\" \"$DB-shm\" \"$DB-journal\"; do "
     "test -e \"$f\" && stat -f '%N size=%z inode=%i mode=%Sp mtime=%Sm' \"$f\" || echo \"$f ABSENT\"; done"),
)



# --------------------------------------------------------------------------------------
# Result types
# --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class ValidationReport:
    results: Tuple[CheckResult, ...]

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)

    def to_lines(self) -> List[str]:
        lines = ["P545D playbook validator — static checks"]
        for r in self.results:
            lines.append(f"[{'PASS' if r.ok else 'FAIL'}] {r.name}: {r.detail}")
        lines.append(f"RESULT: {'PASS' if self.ok else 'FAIL'} "
                     f"({sum(1 for r in self.results if r.ok)}/{len(self.results)} checks passed)")
        return lines


# --------------------------------------------------------------------------------------
# Markdown fenced-block extraction (pure)
# --------------------------------------------------------------------------------------

def iter_code_blocks(text: str) -> List[Tuple[str, str]]:
    """Return ``[(lang, body), ...]`` for each fenced block.

    A fence is a line whose first non-empty characters are three backticks. The language is the
    first token after the backticks (e.g. ``bash`` / ``text``). Inline back-tick spans do not
    start a line and are therefore ignored.
    """
    blocks: List[Tuple[str, str]] = []
    lang: str | None = None
    body: List[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```"):
            if lang is None:
                info = stripped[3:].strip()
                lang = (info.split() or [""])[0].lower()
                body = []
            else:
                blocks.append((lang, "\n".join(body)))
                lang = None
                body = []
        elif lang is not None:
            body.append(line)
    # An unterminated fence is treated as a (best-effort) block so its content is still scanned.
    if lang is not None:
        blocks.append((lang, "\n".join(body)))
    return blocks


def bash_blocks(text: str) -> List[str]:
    return [body for lang, body in iter_code_blocks(text) if lang == "bash"]


# --------------------------------------------------------------------------------------
# Individual checks (each pure: str -> CheckResult)
# --------------------------------------------------------------------------------------

def _check_required_sections(text: str) -> CheckResult:
    # Match the anchor only at the start of a line so a `### C.1` subheader cannot masquerade as
    # the `## C.` H2 section header.
    missing = [
        f"{anchor} {name}"
        for anchor, name in REQUIRED_SECTIONS
        if not re.search(r"(?m)^" + re.escape(anchor), text)
    ]
    return CheckResult("required_sections", not missing,
                       "all A-L present" if not missing else f"missing: {missing}")


def _check_required_markers(text: str) -> CheckResult:
    missing = [f"{tok} ({desc})" for tok, desc in REQUIRED_MARKERS if tok not in text]
    return CheckResult("required_markers", not missing,
                       "all present" if not missing else f"missing: {missing}")


def _check_stop_conditions(text: str) -> CheckResult:
    missing = [t for t in REQUIRED_STOP_TOKENS if t not in text]
    return CheckResult("stop_classifications", not missing,
                       "all STOP tokens present" if not missing else f"missing: {missing}")


def _check_forbidden_documented(text: str) -> CheckResult:
    missing = [f"{tok} ({desc})" for tok, desc in REQUIRED_FORBIDDEN_DOC_TOKENS if tok not in text]
    return CheckResult("forbidden_actions_documented", not missing,
                       "documented" if not missing else f"missing: {missing}")


def _check_forbidden_bash_patterns(text: str) -> CheckResult:
    hits: List[str] = []
    for body in bash_blocks(text):
        for name, pattern in FORBIDDEN_BASH_PATTERNS:
            m = re.search(pattern, body)
            if m:
                hits.append(f"{name!r} matched {m.group(0)!r}")
    return CheckResult("no_dangerous_executable_commands", not hits,
                       "clean" if not hits else f"violations: {hits}")


def _check_launchctl_explicit(text: str) -> CheckResult:
    """Every state-changing launchctl command in a bash block must carry a domain + label."""
    ambiguous: List[str] = []
    for body in bash_blocks(text):
        for line in body.splitlines():
            if _STATE_CHANGING_LAUNCHCTL.search(line):
                has_domain = bool(_DOMAIN_RE.search(line))
                has_label = bool(_LABEL_RE.search(line))
                if not (has_domain and has_label):
                    ambiguous.append(line.strip())
    return CheckResult("launchctl_explicit_domain_label", not ambiguous,
                       "all state-changing launchctl commands carry gui/… domain + label"
                       if not ambiguous else f"ambiguous: {ambiguous}")


def _check_stop_all_noncompliant(text: str) -> CheckResult:
    ok = any(
        "stop_all.sh" in line and re.search(r"NONCOMPLIANT|noncompliant|MUST NOT|Do not|forbidden", line)
        for line in text.splitlines()
    )
    return CheckResult("stop_all_marked_noncompliant", ok,
                       "stop_all.sh explicitly marked noncompliant"
                       if ok else "stop_all.sh not marked noncompliant on any line")


def _check_orders_defined(text: str) -> CheckResult:
    ok = ("Stop order" in text) and ("Restore order" in text) and ("reverse" in text)
    return CheckResult("stop_and_restore_orders", ok,
                       "stop order + reverse restore order defined"
                       if ok else "missing stop/restore order or reverse justification")


def _check_bounded_and_zero_handle(text: str) -> CheckResult:
    bounded = ("max_attempts" in text) and ("T0" in text) and ("T1" in text)
    zero_handle = ("ZERO_OPEN_HANDLES" in text) and ("lsof" in text)
    ok = bounded and zero_handle
    detail = f"bounded_confirmation={bounded}, zero_handle_check={zero_handle}"
    return CheckResult("bounded_confirmation_and_zero_handle", ok, detail)


def _check_managed_service_evidence(text: str) -> CheckResult:
    """The one managed label must appear with its committed plist evidence and a confidence class."""
    ok = ("com.kelvin.lottery.dev" in text
          and "com.kelvin.lottery.dev.plist" in text
          and "Evidence" in text
          and ("PROVEN" in text and "NOT_INSTALLED" in text))
    return CheckResult("managed_service_has_evidence", ok,
                       "managed service carries plist evidence + confidence class"
                       if ok else "managed service evidence/confidence incomplete")


def validate_text(text: str) -> ValidationReport:
    """Pure static validation of playbook *text*. No I/O of any kind."""
    checks = (
        _check_required_sections(text),
        _check_required_markers(text),
        _check_stop_conditions(text),
        _check_forbidden_documented(text),
        _check_forbidden_bash_patterns(text),
        _check_launchctl_explicit(text),
        _check_stop_all_noncompliant(text),
        _check_orders_defined(text),
        _check_bounded_and_zero_handle(text),
        _check_managed_service_evidence(text),
    )
    return ValidationReport(results=checks)


def validate_file(path: str | Path) -> ValidationReport:
    """Read a playbook file (read-only) and validate its text."""
    return validate_text(Path(path).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------------------
# Optional read-only live preflight (opt-in; never mutates)
# --------------------------------------------------------------------------------------

def _command_is_readonly_safe(command: str) -> bool:
    """A preflight command is safe iff it contains no state-changing launchctl subcommand and no
    dangerous executable pattern. This reuses the exact regexes the static playbook scan uses, so
    the allowlist can never drift into a mutating command without failing this gate."""
    if _STATE_CHANGING_LAUNCHCTL.search(command):
        return False
    return not any(re.search(pattern, command) for _name, pattern in FORBIDDEN_BASH_PATTERNS)


def _assert_preflight_allowlist_safe() -> None:
    for cmd in READONLY_PREFLIGHT_COMMANDS:
        joined = " ".join(cmd)
        if not _command_is_readonly_safe(joined):
            raise AssertionError(f"preflight allowlist entry is not read-only safe: {joined!r}")


def run_readonly_preflight(printer=print) -> int:
    """Run only the read-only allowlist commands and print their output. Mutates nothing."""
    import subprocess  # local import: never used by the pure static path

    _assert_preflight_allowlist_safe()
    printer("P545D read-only live preflight (inspection only; no state change)")
    for cmd in READONLY_PREFLIGHT_COMMANDS:
        printer(f"$ {' '.join(cmd)}")
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
            out = (proc.stdout or "").rstrip()
            err = (proc.stderr or "").rstrip()
            if out:
                printer(out)
            if err:
                printer(f"[stderr] {err}")
        except Exception as exc:  # pragma: no cover - environment dependent
            printer(f"[preflight-skip] {cmd[0]}: {exc}")
    return 0


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Static validator for the P545D launchd quiescence playbook.")
    parser.add_argument("--playbook", default=str(DEFAULT_PLAYBOOK), help="path to the playbook markdown")
    parser.add_argument("--preflight", action="store_true",
                        help="ALSO run the read-only live preflight (inspection only)")
    args = parser.parse_args(argv)

    report = validate_file(args.playbook)
    for line in report.to_lines():
        print(line)

    if args.preflight:
        run_readonly_preflight()

    return 0 if report.ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
