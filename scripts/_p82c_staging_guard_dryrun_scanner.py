"""
P82C — Staging Guard Enforcement Dry-Run + Policy Drift Scanner
Date: 2026-05-26
Mode: paper_only=True | diagnostic_only=True | NO_REAL_BET=True

Goals:
  1. Verify P82B contract state and extract guard rules.
  2. Implement dry-run scanner that checks staged/working-tree/allowlisted files.
  3. Execute all 6 P82B guard rules against current repo state.
  4. Test mock violation fixtures — in-memory only, no real odds files created.
  5. Run current repo dry-run and report guard state.
  6. Confirm P82 remains BLOCKED_NO_REAL_DATASET.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Governance — MUST stay paper_only=True / diagnostic_only=True
# ---------------------------------------------------------------------------
GOVERNANCE: dict[str, Any] = {
    "paper_only": True,
    "diagnostic_only": True,
    "uses_historical_odds": False,
    "live_api_calls": 0,
    "the_odds_api_key_required": False,
    "ev_calculated": False,
    "clv_calculated": False,
    "market_edge_calculated": False,
    "kelly_deploy_allowed": False,
    "production_ready": False,
    "real_bet_allowed": False,
    "champion_replacement_allowed": False,
    "profitability_claim": False,
    "p82_unlocked": False,
}

ALLOWED_CLASSIFICATIONS = [
    "P82C_STAGING_GUARD_DRYRUN_READY",
    "P82C_STAGING_GUARD_DRYRUN_READY_WITH_WARNINGS",
    "P82C_BLOCKED_BY_MISSING_P82B_ARTIFACT",
    "P82C_FAILED_VALIDATION",
]

PREDICTION_BOUNDARY = (
    "P82C is a diagnostic dry-run scanner only. Scanner output is a policy-compliance report — "
    "NOT a production deployment, NOT a betting recommendation, NOT a market-edge claim. "
    "paper_only=True, diagnostic_only=True."
)

# Guard states (from P82B contract)
GUARD_STATES = [
    "STAGE_CLEAN",
    "BLOCK_RAW_PAID_DATA",
    "BLOCK_SECRET",
    "BLOCK_UNPOLICIED_ODDS",
    "BLOCK_ROW_LEVEL_LEAKAGE",
    "REVIEW_REQUIRED",
]

# Priority order for guard state resolution (highest priority first)
GUARD_STATE_PRIORITY = {
    "BLOCK_SECRET": 5,
    "BLOCK_RAW_PAID_DATA": 4,
    "BLOCK_ROW_LEVEL_LEAKAGE": 3,
    "BLOCK_UNPOLICIED_ODDS": 2,
    "REVIEW_REQUIRED": 1,
    "STAGE_CLEAN": 0,
}

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PATHS = {
    "p82b_json": ROOT / "data/mlb_2025/derived/p82b_raw_paid_odds_data_policy_contract_summary.json",
    "p82a_json": ROOT / "data/mlb_2025/derived/p82a_real_legal_odds_intake_gate_summary.json",
    "p81_json":  ROOT / "data/mlb_2025/derived/p81_legal_odds_dataset_validator_contract_summary.json",
    "p80_json":  ROOT / "data/mlb_2025/derived/p80_market_edge_reentry_readiness_contract_summary.json",
    "p79b_json": ROOT / "data/mlb_2025/derived/p79b_tier_b_vs_tier_c_comparison_harness_summary.json",
    "p79a_json": ROOT / "data/mlb_2025/derived/p79a_tier_b_trigger_readiness_contract_summary.json",
    "p78_json":  ROOT / "data/mlb_2025/derived/p78_monthly_shadow_tracker_report_template_summary.json",
    "p77_json":  ROOT / "data/mlb_2025/derived/p77_prediction_only_shadow_tracker_contract_summary.json",
    "p76_json":  ROOT / "data/mlb_2025/derived/p76_corrected_tier_c_final_rule_selection_summary.json",
    "p75b_json": ROOT / "data/mlb_2025/derived/p75b_calibration_diagnostics_corrected_tier_c_summary.json",
    "p75a_json": ROOT / "data/mlb_2025/derived/p75a_tier_c_corrected_rule_validator_summary.json",
    "p74_json":  ROOT / "data/mlb_2025/derived/p74_tier_c_home_away_bias_correction_summary.json",
    "p73_json":  ROOT / "data/mlb_2025/derived/p73_tier_stability_and_sample_expansion_summary.json",
    "p72b_json": ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json",
    "p72a_json": ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json",
}

OUTPUT_JSON   = ROOT / "data/mlb_2025/derived/p82c_staging_guard_dryrun_scanner_summary.json"
OUTPUT_REPORT = ROOT / "report/p82c_staging_guard_dryrun_scanner_20260526.md"
PLAN_REPORT   = ROOT / "00-BettingPlan/20260526/p82c_staging_guard_dryrun_scanner_20260526.md"


# ---------------------------------------------------------------------------
# Allowlist: files that pass automatically (P-series contracts / reports)
# ---------------------------------------------------------------------------
ALLOWLIST_PATTERNS = [
    "data/mlb_2025/derived/p*.json",
    "report/p*_20260526.md",
    "report/p*_20260*.md",
    "00-BettingPlan/20260526/p*.md",
    "scripts/_p*.py",
    "tests/test_p*.py",
    "00-Plan/roadmap/active_task.md",
    "00-Plan/roadmap/roadmap.md",
]

# Out-of-scope runtime/data paths that generate REVIEW_REQUIRED (not hard block)
RUNTIME_PATTERNS = [
    "runtime/**",
    "logs/**",
    "data/.live_cache/**",
    "data/derived/**",
    "data/mlb_context/**",
    "data/tsl_*.json",
    "data/tsl_*.jsonl",
    "data/learning_state.json",
    "data/wbc_backend/**",
    "outputs/**",
    "00-BettingPlan/20260510/**",
    "00-Plan/roadmap/CEO-Decision.md",
    "00-Plan/roadmap/CTO-Analysis.md",
]

# ---------------------------------------------------------------------------
# Suppression markers — content containing these is suppressed from false-positives
# ---------------------------------------------------------------------------
SUPPRESSION_MARKERS = [
    "NO_REAL_BET",
    "paper_only",
    "diagnostic_only",
    "BLOCK_RAW_PAID_CSV",       # policy/contract text
    "BLOCK_REAL_ODDS_FILENAME",  # policy/contract text
    "guard_state",               # contract structure
    "P82B_RAW_PAID_DATA_POLICY_READY",
    "MOCK_ONLY",
    "MOCK_FIXTURE",
    "governance_snapshot",
]

# ---------------------------------------------------------------------------
# Guard rule implementations
# ---------------------------------------------------------------------------


@dataclass
class Violation:
    rule_id: str
    filepath: str
    guard_state: str
    evidence_redacted: str
    suppressed: bool = False
    suppression_reason: str = ""


@dataclass
class ScanResult:
    scan_mode: str
    files_scanned: list[str] = field(default_factory=list)
    violations: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    false_positive_suppression_notes: list[str] = field(default_factory=list)
    guard_state: str = "STAGE_CLEAN"
    summary: str = ""


def _is_allowlisted(rel_path: str) -> bool:
    """True if file matches P-series allowlist patterns."""
    for pat in ALLOWLIST_PATTERNS:
        if fnmatch.fnmatch(rel_path, pat):
            return True
    return False


def _is_pseries_contract(rel_path: str) -> bool:
    """True if file is a known P-series contract file (immune to filename-based block rules).
    P-series contracts may have descriptive names that incidentally contain blocked keywords,
    but they are governance/research artifacts, not real odds data files.
    """
    filename = Path(rel_path).name.lower()
    # P-series derived summaries: p<nn>_..._summary.json
    if re.match(r'^p\d+[a-z]?_.*_summary\.json$', filename):
        return True
    # P-series reports: p<nn>_..._<date>.md
    if re.match(r'^p\d+[a-z]?_.*_\d{8}\.md$', filename):
        return True
    return False


def _is_runtime_file(rel_path: str) -> bool:
    """True if file is a known runtime/state file (out-of-scope, not forbidden)."""
    for pat in RUNTIME_PATTERNS:
        if fnmatch.fnmatch(rel_path, pat):
            return True
    return False


def _has_suppression_marker(content: str) -> tuple[bool, str]:
    """Check if content has any suppression marker. Returns (suppressed, reason)."""
    for marker in SUPPRESSION_MARKERS:
        if marker in content:
            return True, f"suppression_marker={marker}"
    return False, ""


def _redact_secret(s: str, keep: int = 4) -> str:
    """Redact a secret string, keeping only first/last N chars."""
    if len(s) <= keep * 2:
        return "***REDACTED***"
    return f"{s[:keep]}...REDACTED...{s[-keep:]}"


# ---- Rule 1: BLOCK_ENV_FILE ------------------------------------------------
ENV_FILE_PATTERNS = [".env", ".env.local", ".env.production", ".env.test", ".env.staging"]
ENV_FILE_REGEX = re.compile(r"^\.env(\.[a-z]+)?$", re.IGNORECASE)


def rule_block_env_file(rel_path: str, _content: str | None = None) -> Violation | None:
    filename = Path(rel_path).name
    if ENV_FILE_REGEX.match(filename):
        return Violation(
            rule_id="BLOCK_ENV_FILE",
            filepath=rel_path,
            guard_state="BLOCK_SECRET",
            evidence_redacted=f"filename={filename}",
        )
    return None


# ---- Rule 2: BLOCK_API_KEY_PATTERN -----------------------------------------
# Detect long alphanumeric strings in context of KEY/TOKEN/SECRET/API
API_KEY_CONTEXT_RE = re.compile(
    r'(?:api_?key|token|secret|credential)["\s:=]+([A-Za-z0-9_\-]{32,})',
    re.IGNORECASE,
)
# Also detect bare long alphanumeric strings (must be > 40 chars to reduce false positives)
LONG_ALPHANUM_RE = re.compile(r'\b([A-Za-z0-9]{48,})\b')


def rule_block_api_key_pattern(rel_path: str, content: str | None = None) -> Violation | None:
    if content is None:
        return None
    # Context-aware search first (more confident)
    m = API_KEY_CONTEXT_RE.search(content)
    if m:
        suppressed, reason = _has_suppression_marker(content)
        key_value = m.group(1)
        # Further suppress if it's a git commit hash (40 hex chars only)
        if re.match(r'^[0-9a-f]{40}$', key_value, re.IGNORECASE):
            suppressed = True
            reason = "git_commit_hash"
        return Violation(
            rule_id="BLOCK_API_KEY_PATTERN",
            filepath=rel_path,
            guard_state="BLOCK_SECRET" if not suppressed else "STAGE_CLEAN",
            evidence_redacted=_redact_secret(key_value),
            suppressed=suppressed,
            suppression_reason=reason,
        )
    # Bare long alphanumeric (lower confidence, require no suppression marker)
    m2 = LONG_ALPHANUM_RE.search(content)
    if m2:
        suppressed, reason = _has_suppression_marker(content)
        if suppressed:
            return Violation(
                rule_id="BLOCK_API_KEY_PATTERN",
                filepath=rel_path,
                guard_state="STAGE_CLEAN",
                evidence_redacted="[suppressed-governance-content]",
                suppressed=True,
                suppression_reason=reason,
            )
    return None


# ---- Rule 3: BLOCK_RAW_PAID_CSV --------------------------------------------
RAW_PAID_CSV_FILENAME_PATTERNS = [
    "*paid*odds*.csv",
    "*raw*odds*.json",
    "*paid*odds*.json",
    "*paid*odds*.jsonl",
]


def rule_block_raw_paid_csv(rel_path: str, _content: str | None = None) -> Violation | None:
    """Block raw paid odds CSV/JSON under data/ paths (fnmatch-compatible, no **). """
    rel_lower = rel_path.lower()
    # Must be under data/ directory
    if not (rel_lower.startswith("data/") or rel_lower.startswith("data\\")):
        return None
    # P-series contract files are immune — their descriptive names may contain keywords
    if _is_pseries_contract(rel_path):
        return None
    filename = Path(rel_path).name.lower()
    for pat in RAW_PAID_CSV_FILENAME_PATTERNS:
        if fnmatch.fnmatch(filename, pat.lower()):
            return Violation(
                rule_id="BLOCK_RAW_PAID_CSV",
                filepath=rel_path,
                guard_state="BLOCK_RAW_PAID_DATA",
                evidence_redacted=f"filename_pattern=data/**/{pat}",
            )
    return None


# ---- Rule 4: BLOCK_REAL_ODDS_FILENAME --------------------------------------
REAL_ODDS_FILENAME_PATTERNS = [
    "*odds_2024_real.csv",
    "*odds_2025_real.csv",
    "*paid*odds*.csv",
    "*raw*odds*.json",
    "*raw*odds*.csv",
    "*the_odds_api*raw*",
    "*mlb_odds_real*",
    "*real_odds*",
]


def rule_block_real_odds_filename(rel_path: str, _content: str | None = None) -> Violation | None:
    # P-series contract files are immune from filename-based rules
    if _is_pseries_contract(rel_path):
        return None
    filename = Path(rel_path).name.lower()
    for pat in REAL_ODDS_FILENAME_PATTERNS:
        if fnmatch.fnmatch(filename, pat.lower()):
            return Violation(
                rule_id="BLOCK_REAL_ODDS_FILENAME",
                filepath=rel_path,
                guard_state="BLOCK_RAW_PAID_DATA",
                evidence_redacted=f"filename_match={pat}",
            )
    return None


# ---- Rule 5: BLOCK_CONTAINS_API_KEY_FLAG -----------------------------------
CONTAINS_API_KEY_FLAG_RE = re.compile(
    r'"contains_api_key"\s*:\s*true', re.IGNORECASE
)


def rule_block_contains_api_key_flag(rel_path: str, content: str | None = None) -> Violation | None:
    if content is None:
        return None
    if CONTAINS_API_KEY_FLAG_RE.search(content):
        suppressed, reason = _has_suppression_marker(content)
        return Violation(
            rule_id="BLOCK_CONTAINS_API_KEY_FLAG",
            filepath=rel_path,
            guard_state="BLOCK_SECRET" if not suppressed else "STAGE_CLEAN",
            evidence_redacted='contains_api_key=true detected',
            suppressed=suppressed,
            suppression_reason=reason,
        )
    return None


# ---- Rule 6: BLOCK_ROW_LEVEL_ODDS ------------------------------------------
# Detect row-level real odds patterns.
# Indicators: combination of game_id + numeric odds values (-110, +120, etc.)
# Must be in non-suppressed context.
ROW_LEVEL_INDICATORS = [
    re.compile(r'"raw_odds_row"', re.IGNORECASE),
    re.compile(r'"row_level_odds"', re.IGNORECASE),
    # CSV header with both home_ml and away_ml as column names
    re.compile(r'home_ml\s*,\s*away_ml', re.IGNORECASE),
    # JSON with numeric odds values in array (row-level pattern)
    re.compile(r'"home_ml"\s*:\s*-?\d{3,4}', re.IGNORECASE),
]

# These patterns indicate the content is describing odds in a safe aggregate context
ROW_LEVEL_FALSE_POSITIVE_PATTERNS = [
    re.compile(r'home_moneyline_avg', re.IGNORECASE),  # aggregate field name
    re.compile(r'avg_home_ml', re.IGNORECASE),          # aggregate
    re.compile(r'auc|cal_brier|cal_ece|hit_rate', re.IGNORECASE),  # calibration metrics
]


def rule_block_row_level_odds(rel_path: str, content: str | None = None) -> Violation | None:
    if content is None:
        return None
    # Check suppression first
    suppressed, reason = _has_suppression_marker(content)
    # Score indicators
    indicator_hits = sum(1 for r in ROW_LEVEL_INDICATORS if r.search(content))
    if indicator_hits == 0:
        return None
    # Check false-positive patterns (any present reduces confidence)
    fp_hits = sum(1 for r in ROW_LEVEL_FALSE_POSITIVE_PATTERNS if r.search(content))
    if fp_hits > 0 or suppressed:
        return Violation(
            rule_id="BLOCK_ROW_LEVEL_ODDS",
            filepath=rel_path,
            guard_state="STAGE_CLEAN",
            evidence_redacted=f"row_level_indicators={indicator_hits} suppressed by fp_context or governance",
            suppressed=True,
            suppression_reason=reason if suppressed else f"false_positive_indicators={fp_hits}",
        )
    return Violation(
        rule_id="BLOCK_ROW_LEVEL_ODDS",
        filepath=rel_path,
        guard_state="BLOCK_ROW_LEVEL_LEAKAGE",
        evidence_redacted=f"row_level_indicators={indicator_hits}",
    )


# All guard rules in order
ALL_RULES = [
    rule_block_env_file,
    rule_block_api_key_pattern,
    rule_block_raw_paid_csv,
    rule_block_real_odds_filename,
    rule_block_contains_api_key_flag,
    rule_block_row_level_odds,
]


# ---------------------------------------------------------------------------
# Mock violation fixtures (in-memory only — never written to disk)
# ---------------------------------------------------------------------------
@dataclass
class MockFixture:
    name: str
    filepath: str
    content: str
    expected_guard_state: str
    expected_rule_id: str | None
    is_risky: bool


MOCK_FIXTURES: list[MockFixture] = [
    MockFixture(
        name="env_file",
        filepath=".env",
        content="THE_ODDS_API_KEY=FAKEKEYNOTREAL\nDB_PASSWORD=secret123",
        expected_guard_state="BLOCK_SECRET",
        expected_rule_id="BLOCK_ENV_FILE",
        is_risky=True,
    ),
    MockFixture(
        name="api_key_content",
        filepath="data/config_backup.json",
        content='{"api_key": "ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890ABCDEF"}',
        expected_guard_state="BLOCK_SECRET",
        expected_rule_id="BLOCK_API_KEY_PATTERN",
        is_risky=True,
    ),
    MockFixture(
        name="raw_paid_csv_filename",
        filepath="data/paid_odds_mlb_2025.csv",
        content="game_id,home_team,away_team,home_ml,away_ml\nMLB001,NYY,BOS,-130,+110",
        expected_guard_state="BLOCK_RAW_PAID_DATA",
        expected_rule_id="BLOCK_RAW_PAID_CSV",
        is_risky=True,
    ),
    MockFixture(
        name="real_odds_filename",
        filepath="data/mlb_odds_2024_real.csv",
        content="game_id,date,home_ml,away_ml\nMLB001,2024-04-01,-115,+105",
        expected_guard_state="BLOCK_RAW_PAID_DATA",
        expected_rule_id="BLOCK_REAL_ODDS_FILENAME",
        is_risky=True,
    ),
    MockFixture(
        name="contains_api_key_flag",
        filepath="data/mlb_2025/odds_intake_test.json",
        content='{"contains_api_key": true, "provider": "the_odds_api", "batch_id": "X001"}',
        expected_guard_state="BLOCK_SECRET",
        expected_rule_id="BLOCK_CONTAINS_API_KEY_FLAG",
        is_risky=True,
    ),
    MockFixture(
        name="row_level_odds_leakage",
        # filepath deliberately does NOT match BLOCK_REAL_ODDS_FILENAME patterns
        filepath="data/mlb_2025/game_analysis_export.json",
        content=(
            '{"game_id": "MLB_001", "home_ml": -130, "away_ml": 110, '
            '"raw_odds_row": true, "source": "paid_provider"}'
        ),
        expected_guard_state="BLOCK_ROW_LEVEL_LEAKAGE",
        expected_rule_id="BLOCK_ROW_LEVEL_ODDS",
        is_risky=True,
    ),
    MockFixture(
        name="safe_derived_summary",
        filepath="data/mlb_2025/derived/p82c_staging_guard_dryrun_scanner_summary.json",
        content=(
            '{"p82c_classification": "P82C_STAGING_GUARD_DRYRUN_READY", '
            '"governance": {"paper_only": true, "NO_REAL_BET": true, '
            '"kelly_deploy_allowed": false}, '
            '"hit_rate": 0.639, "auc": 0.579}'
        ),
        expected_guard_state="STAGE_CLEAN",
        expected_rule_id=None,
        is_risky=False,
    ),
    MockFixture(
        name="safe_policy_report",
        filepath="report/p82b_raw_paid_odds_data_policy_contract_20260526.md",
        content=(
            "# P82B Policy Contract\n"
            "Guard rule BLOCK_RAW_PAID_CSV blocks files matching `*paid*odds*.csv`.\n"
            "BLOCK_REAL_ODDS_FILENAME blocks `*odds_2024_real.csv`.\n"
            "paper_only=True | diagnostic_only=True | NO_REAL_BET=True"
        ),
        expected_guard_state="STAGE_CLEAN",
        expected_rule_id=None,
        is_risky=False,
    ),
]


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------
def _resolve_guard_state(violations: list[dict]) -> str:
    """Pick highest-priority guard state from violations."""
    if not violations:
        return "STAGE_CLEAN"
    states = [v["guard_state"] for v in violations if not v.get("suppressed", False)]
    if not states:
        return "STAGE_CLEAN"
    return max(states, key=lambda s: GUARD_STATE_PRIORITY.get(s, 0))


def _scan_single_file(
    rel_path: str,
    content: str | None,
    suppression_notes: list[str],
) -> tuple[list[dict], list[dict]]:
    """Scan one file against all guard rules. Returns (violations, warnings)."""
    violations = []
    warnings = []

    for rule_fn in ALL_RULES:
        v = rule_fn(rel_path, content)
        if v is None:
            continue
        v_dict = {
            "rule_id": v.rule_id,
            "filepath": v.filepath,
            "guard_state": v.guard_state,
            "evidence_redacted": v.evidence_redacted,
            "suppressed": v.suppressed,
            "suppression_reason": v.suppression_reason,
        }
        if v.suppressed:
            note = f"[{v.rule_id}] {v.filepath}: suppressed — {v.suppression_reason}"
            suppression_notes.append(note)
            warnings.append({**v_dict, "category": "SUPPRESSED_FALSE_POSITIVE"})
        else:
            violations.append(v_dict)

    return violations, warnings


def scan_inmemory(fixtures: list[MockFixture]) -> ScanResult:
    """Scan in-memory mock fixtures."""
    result = ScanResult(scan_mode="INMEMORY_MOCK")
    suppression_notes: list[str] = []

    for fx in fixtures:
        result.files_scanned.append(f"[MOCK] {fx.filepath}")
        viols, warns = _scan_single_file(fx.filepath, fx.content, suppression_notes)
        result.violations.extend(viols)
        result.warnings.extend(warns)

    result.false_positive_suppression_notes = suppression_notes
    result.guard_state = _resolve_guard_state(result.violations)
    return result


def scan_staged_files() -> ScanResult:
    """Scan currently staged files (git diff --cached --name-only)."""
    result = ScanResult(scan_mode="STAGED_FILES")
    suppression_notes: list[str] = []

    try:
        out = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(ROOT), text=True
        ).strip()
        staged = [f for f in out.splitlines() if f] if out else []
    except subprocess.CalledProcessError:
        staged = []

    for rel_path in staged:
        result.files_scanned.append(rel_path)
        if _is_allowlisted(rel_path):
            result.warnings.append({
                "filepath": rel_path, "category": "ALLOWLISTED", "note": "P-series artifact"
            })
            continue
        # Read content for content-based rules
        abs_path = ROOT / rel_path
        content = None
        if abs_path.exists() and abs_path.stat().st_size < 500_000:
            try:
                content = abs_path.read_text(errors="replace")
            except Exception:
                pass
        viols, warns = _scan_single_file(rel_path, content, suppression_notes)
        result.violations.extend(viols)
        result.warnings.extend(warns)

    result.false_positive_suppression_notes = suppression_notes
    result.guard_state = _resolve_guard_state(result.violations)
    return result


def scan_working_tree() -> ScanResult:
    """Scan working-tree changed files (git status --short)."""
    result = ScanResult(scan_mode="WORKING_TREE")
    suppression_notes: list[str] = []

    try:
        out = subprocess.check_output(
            ["git", "status", "--short", "--porcelain"],
            cwd=str(ROOT), text=True
        ).strip()
        changed = []
        for line in out.splitlines():
            if len(line) > 3:
                rel_path = line[3:].strip().strip('"')
                changed.append(rel_path)
    except subprocess.CalledProcessError:
        changed = []

    for rel_path in changed:
        result.files_scanned.append(rel_path)
        # Runtime files: mark as out-of-scope warning, not hard-check (unless forbidden filename)
        if _is_runtime_file(rel_path):
            # Still check filename-only rules for forbidden patterns
            v_env   = rule_block_env_file(rel_path)
            v_paid  = rule_block_raw_paid_csv(rel_path)
            v_real  = rule_block_real_odds_filename(rel_path)
            for v in [v_env, v_paid, v_real]:
                if v:
                    result.violations.append({
                        "rule_id": v.rule_id, "filepath": v.filepath,
                        "guard_state": v.guard_state,
                        "evidence_redacted": v.evidence_redacted,
                        "suppressed": False, "suppression_reason": "",
                    })
            if not any([v_env, v_paid, v_real]):
                result.warnings.append({
                    "filepath": rel_path,
                    "category": "RUNTIME_OUT_OF_SCOPE",
                    "note": "Runtime/state file not in commit scope"
                })
            continue
        if _is_allowlisted(rel_path):
            result.warnings.append({
                "filepath": rel_path, "category": "ALLOWLISTED", "note": "P-series artifact"
            })
            continue
        abs_path = ROOT / rel_path
        content = None
        if abs_path.exists() and abs_path.stat().st_size < 500_000:
            try:
                content = abs_path.read_text(errors="replace")
            except Exception:
                pass
        viols, warns = _scan_single_file(rel_path, content, suppression_notes)
        result.violations.extend(viols)
        result.warnings.extend(warns)

    result.false_positive_suppression_notes = suppression_notes
    result.guard_state = _resolve_guard_state(result.violations)
    # If only runtime-out-of-scope warnings remain with no violations, mark clean
    non_runtime_violations = [
        v for v in result.violations if not v.get("suppressed", False)
    ]
    if not non_runtime_violations and result.warnings:
        result.guard_state = "STAGE_CLEAN"
    return result


def scan_allowlisted_paths() -> ScanResult:
    """Scan only the P-series allowlisted derived JSON + report files."""
    result = ScanResult(scan_mode="ALLOWLISTED_PATHS")
    suppression_notes: list[str] = []

    # Collect all P-series derived JSONs
    derived_dir = ROOT / "data/mlb_2025/derived"
    report_dir = ROOT / "report"

    candidate_paths = []
    if derived_dir.exists():
        candidate_paths.extend(derived_dir.glob("p*.json"))
    if report_dir.exists():
        candidate_paths.extend(report_dir.glob("p*_20260526.md"))

    for abs_path in sorted(candidate_paths):
        rel_path = str(abs_path.relative_to(ROOT))
        result.files_scanned.append(rel_path)
        content = None
        if abs_path.stat().st_size < 500_000:
            try:
                content = abs_path.read_text(errors="replace")
            except Exception:
                pass
        viols, warns = _scan_single_file(rel_path, content, suppression_notes)
        result.violations.extend(viols)
        result.warnings.extend(warns)

    result.false_positive_suppression_notes = suppression_notes
    result.guard_state = _resolve_guard_state(result.violations)
    return result


# ---------------------------------------------------------------------------
# Step 1 — Verify P82B state
# ---------------------------------------------------------------------------
def step1_verify_p82b(p82b: dict) -> dict:
    classification = p82b.get("p82b_classification", "")
    artifact_classes = p82b.get("step2_artifact_classes", {})
    class_ids = artifact_classes.get("class_ids", [])
    staging_guard = p82b.get("step4_staging_guard", {})
    blocks = staging_guard.get("blocks", [])
    policy_matrix = p82b.get("step3_commit_policy_matrix", {})
    p82_unlock_status = p82b.get("p82_unlock_status", "")
    live_api = p82b.get("live_api_calls", -1)
    ev_clv = p82b.get("ev_clv_kelly_computed", True)
    gov = p82b.get("governance_snapshot", {})

    expected_artifact_classes = [
        "RAW_PAID_ODDS_DATA", "RAW_FREE_LEGAL_ODDS_DATA", "VALIDATION_MANIFEST",
        "CHECKSUM_ONLY_RECORD", "DERIVED_VALIDATION_SUMMARY", "DERIVED_MARKET_EDGE_SUMMARY",
        "LOCAL_REPRODUCIBILITY_NOTE", "SECRET_OR_API_KEY", "MOCK_FIXTURE",
    ]
    expected_guard_rules = [
        "BLOCK_ENV_FILE", "BLOCK_API_KEY_PATTERN", "BLOCK_RAW_PAID_CSV",
        "BLOCK_REAL_ODDS_FILENAME", "BLOCK_CONTAINS_API_KEY_FLAG", "BLOCK_ROW_LEVEL_ODDS",
    ]

    block_rule_ids = [b.get("rule_id") for b in blocks]
    missing_artifact_classes = [c for c in expected_artifact_classes if c not in class_ids]
    missing_guard_rules = [r for r in expected_guard_rules if r not in block_rule_ids]

    verification_ok = (
        classification == "P82B_RAW_PAID_DATA_POLICY_READY"
        and p82_unlock_status == "BLOCKED_NO_REAL_DATASET"
        and live_api == 0
        and ev_clv is False
        and not missing_artifact_classes
        and not missing_guard_rules
        and gov.get("paper_only") is True
        and gov.get("kelly_deploy_allowed") is False
    )

    return {
        "classification": classification,
        "classification_ok": classification == "P82B_RAW_PAID_DATA_POLICY_READY",
        "artifact_classes_count": len(class_ids),
        "artifact_classes_ok": not missing_artifact_classes,
        "missing_artifact_classes": missing_artifact_classes,
        "guard_rules_count": len(block_rule_ids),
        "guard_rules_ok": not missing_guard_rules,
        "missing_guard_rules": missing_guard_rules,
        "guard_rule_ids": block_rule_ids,
        "policy_matrix_classes": list(policy_matrix.keys()) if isinstance(policy_matrix, dict) else [],
        "p82_unlock_status": p82_unlock_status,
        "p82_blocked": p82_unlock_status == "BLOCKED_NO_REAL_DATASET",
        "live_api_calls": live_api,
        "ev_clv_kelly_computed": ev_clv,
        "governance_paper_only": gov.get("paper_only"),
        "governance_kelly_allowed": gov.get("kelly_deploy_allowed"),
        "verification_ok": verification_ok,
    }


# ---------------------------------------------------------------------------
# Step 2 — Scanner contract
# ---------------------------------------------------------------------------
def step2_scanner_contract() -> dict:
    return {
        "scanner_id": "P82C_STAGING_GUARD_DRYRUN_SCANNER",
        "version": "1.0.0",
        "scan_modes": ["STAGED_FILES", "WORKING_TREE", "ALLOWLISTED_PATHS", "INMEMORY_MOCK"],
        "guard_rules": [
            {"rule_id": "BLOCK_ENV_FILE", "type": "filename_pattern", "guard_state": "BLOCK_SECRET"},
            {"rule_id": "BLOCK_API_KEY_PATTERN", "type": "content_regex", "guard_state": "BLOCK_SECRET"},
            {"rule_id": "BLOCK_RAW_PAID_CSV", "type": "filename_pattern", "guard_state": "BLOCK_RAW_PAID_DATA"},
            {"rule_id": "BLOCK_REAL_ODDS_FILENAME", "type": "filename_pattern", "guard_state": "BLOCK_RAW_PAID_DATA"},
            {"rule_id": "BLOCK_CONTAINS_API_KEY_FLAG", "type": "content_match", "guard_state": "BLOCK_SECRET"},
            {"rule_id": "BLOCK_ROW_LEVEL_ODDS", "type": "content_indicator", "guard_state": "BLOCK_ROW_LEVEL_LEAKAGE"},
        ],
        "output_fields": [
            "scan_mode", "files_scanned", "violations", "warnings",
            "false_positive_suppression_notes", "guard_state",
        ],
        "allowlist_patterns": ALLOWLIST_PATTERNS,
        "runtime_patterns": RUNTIME_PATTERNS,
        "suppression_markers": SUPPRESSION_MARKERS,
        "redaction_policy": "API keys and secrets are redacted — only first 4 / last 4 chars reported",
        "no_real_odds_created": True,
        "no_api_calls": True,
    }


# ---------------------------------------------------------------------------
# Step 3 — Mock fixture scan
# ---------------------------------------------------------------------------
def step3_mock_fixture_scan() -> dict:
    results = []
    all_pass = True

    for fx in MOCK_FIXTURES:
        # Run single fixture
        suppression_notes: list[str] = []
        viols, warns = _scan_single_file(fx.filepath, fx.content, suppression_notes)

        # Determine effective guard state for this fixture
        active_viols = [v for v in viols if not v.get("suppressed", False)]
        guard_state = _resolve_guard_state(active_viols) if active_viols else "STAGE_CLEAN"

        # Check expectation
        state_ok = guard_state == fx.expected_guard_state
        rule_ok = (
            fx.expected_rule_id is None
            or any(v["rule_id"] == fx.expected_rule_id for v in viols)
        )
        passed = state_ok and rule_ok
        if not passed:
            all_pass = False

        results.append({
            "fixture_name": fx.name,
            "filepath": fx.filepath,
            "is_risky": fx.is_risky,
            "expected_guard_state": fx.expected_guard_state,
            "actual_guard_state": guard_state,
            "expected_rule_id": fx.expected_rule_id,
            "triggered_rules": [v["rule_id"] for v in viols],
            "state_ok": state_ok,
            "rule_ok": rule_ok,
            "passed": passed,
            "is_inmemory_only": True,  # never written to disk
        })

    return {
        "mock_fixture_count": len(MOCK_FIXTURES),
        "risky_fixtures": sum(1 for fx in MOCK_FIXTURES if fx.is_risky),
        "safe_fixtures": sum(1 for fx in MOCK_FIXTURES if not fx.is_risky),
        "all_passed": all_pass,
        "results": results,
        "no_files_created": True,
    }


# ---------------------------------------------------------------------------
# Step 4 — Current repo dry-run
# ---------------------------------------------------------------------------
def step4_current_repo_dryrun() -> dict:
    staged = scan_staged_files()
    working = scan_working_tree()
    allowlisted = scan_allowlisted_paths()

    # Combine for overall assessment
    all_violations = (
        [v for v in staged.violations if not v.get("suppressed", False)]
        + [v for v in allowlisted.violations if not v.get("suppressed", False)]
    )

    overall_guard_state = _resolve_guard_state(all_violations) if all_violations else "STAGE_CLEAN"

    return {
        "staged_files_result": {
            "scan_mode": staged.scan_mode,
            "files_scanned_count": len(staged.files_scanned),
            "violations_count": len([v for v in staged.violations if not v.get("suppressed")]),
            "warnings_count": len(staged.warnings),
            "guard_state": staged.guard_state,
            "files_scanned": staged.files_scanned,
        },
        "working_tree_result": {
            "scan_mode": working.scan_mode,
            "files_scanned_count": len(working.files_scanned),
            "violations_count": len([v for v in working.violations if not v.get("suppressed")]),
            "runtime_out_of_scope_count": sum(
                1 for w in working.warnings if w.get("category") == "RUNTIME_OUT_OF_SCOPE"
            ),
            "warnings_count": len(working.warnings),
            "guard_state": working.guard_state,
        },
        "allowlisted_paths_result": {
            "scan_mode": allowlisted.scan_mode,
            "files_scanned_count": len(allowlisted.files_scanned),
            "violations_count": len([v for v in allowlisted.violations if not v.get("suppressed")]),
            "warnings_count": len(allowlisted.warnings),
            "guard_state": allowlisted.guard_state,
        },
        "overall_guard_state": overall_guard_state,
        "overall_clean": overall_guard_state == "STAGE_CLEAN",
        "runtime_dirty_files_note": (
            "Runtime/state files in working tree are marked RUNTIME_OUT_OF_SCOPE and do not "
            "trigger hard blocks unless they match forbidden patterns."
        ),
    }


# ---------------------------------------------------------------------------
# Forbidden phrase scan
# ---------------------------------------------------------------------------
FORBIDDEN_PHRASES = [
    "expected_value",
    "closing_line_value",
    '"clv_calculated": true',
    "kelly fraction",
    '"kelly_deploy_allowed": true',
    '"production_ready": true',
    "profitability confirmed",
    '"real_bet_allowed": true',
    '"p82_unlocked": true',
]


def _scan_forbidden(text: str) -> dict:
    violations = [p for p in FORBIDDEN_PHRASES if p.lower() in text.lower()]
    return {"violations": violations, "result": "CLEAN" if not violations else "VIOLATION_FOUND"}


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def _generate_report(result: dict) -> str:
    lines: list[str] = []
    a = lines.append

    cls = result.get("p82c_classification", "—")
    mock_res = result["step3_mock_fixture_scan"]
    repo_res = result["step4_current_repo_dryrun"]

    a("# P82C — Staging Guard Enforcement Dry-Run + Policy Drift Scanner")
    a("**Date:** 2026-05-26  ")
    a(f"**Phase:** P82C  ")
    a(f"**Classification:** `{cls}`  ")
    a("**Mode:** paper_only=True | diagnostic_only=True | NO_REAL_BET=True")
    a("")
    a("---")
    a("")
    a("## P82B State Verification")
    a("")
    p82b_v = result["step1_p82b_verification"]
    a(f"- Classification: `{p82b_v['classification']}` {'✅' if p82b_v['classification_ok'] else '❌'}")
    a(f"- Artifact classes: {p82b_v['artifact_classes_count']} {'✅' if p82b_v['artifact_classes_ok'] else '❌'}")
    a(f"- Guard rules: {p82b_v['guard_rules_count']} {'✅' if p82b_v['guard_rules_ok'] else '❌'}")
    a(f"- P82 unlock status: `{p82b_v['p82_unlock_status']}` {'✅' if p82b_v['p82_blocked'] else '❌'}")
    a(f"- Verification: {'✅ PASS' if p82b_v['verification_ok'] else '❌ FAIL'}")
    a("")
    a("---")
    a("")
    a("## Guard Rules Implemented")
    a("")
    a("| Rule | Type | Guard State |")
    a("|---|---|---|")
    for gr in result["step2_scanner_contract"]["guard_rules"]:
        a(f"| `{gr['rule_id']}` | {gr['type']} | `{gr['guard_state']}` |")
    a("")
    a("---")
    a("")
    a("## Mock Fixture Results")
    a("")
    a(f"All fixtures in-memory only (no files created). Total: {mock_res['mock_fixture_count']} "
      f"({mock_res['risky_fixtures']} risky, {mock_res['safe_fixtures']} safe).")
    a("")
    a("| Fixture | Expected State | Actual State | Pass |")
    a("|---|---|---|---|")
    for r in mock_res["results"]:
        icon = "✅" if r["passed"] else "❌"
        a(f"| `{r['fixture_name']}` | `{r['expected_guard_state']}` | "
          f"`{r['actual_guard_state']}` | {icon} |")
    a("")
    a(f"**All mock cases pass:** {'✅ YES' if mock_res['all_passed'] else '❌ NO'}")
    a("")
    a("---")
    a("")
    a("## Current Repo Dry-Run")
    a("")
    a(f"**Overall guard state: `{repo_res['overall_guard_state']}`**")
    a("")
    a("| Scope | Files Scanned | Violations | Guard State |")
    a("|---|---:|---:|---|")
    a(f"| Staged files | {repo_res['staged_files_result']['files_scanned_count']} | "
      f"{repo_res['staged_files_result']['violations_count']} | "
      f"`{repo_res['staged_files_result']['guard_state']}` |")
    a(f"| Working tree | {repo_res['working_tree_result']['files_scanned_count']} | "
      f"{repo_res['working_tree_result']['violations_count']} | "
      f"`{repo_res['working_tree_result']['guard_state']}` |")
    a(f"| Allowlisted paths | {repo_res['allowlisted_paths_result']['files_scanned_count']} | "
      f"{repo_res['allowlisted_paths_result']['violations_count']} | "
      f"`{repo_res['allowlisted_paths_result']['guard_state']}` |")
    a("")
    a(f"> {repo_res['runtime_dirty_files_note']}")
    a("")
    a("---")
    a("")
    a("## P82 Status")
    a("")
    a(f"P82 remains **BLOCKED_NO_REAL_DATASET**. No real legal odds dataset acquired.")
    a("P82 dry-run phase (P82C) complete. Unlocking requires external legal dataset + P81 validator pass.")
    a("")
    a("---")
    a("")
    a("*paper_only=True | diagnostic_only=True | NO_REAL_BET=True*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run_p82c() -> dict:
    # Check required P82B artifact
    p82b_path = PATHS["p82b_json"]
    if not p82b_path.exists():
        return {
            "phase": "P82C",
            "date": "2026-05-26",
            "p82c_classification": "P82C_BLOCKED_BY_MISSING_P82B_ARTIFACT",
            "governance": GOVERNANCE,
        }

    p82b = json.loads(p82b_path.read_text())

    # Step 1 — verify P82B
    p82b_verification = step1_verify_p82b(p82b)
    if not p82b_verification["verification_ok"]:
        return {
            "phase": "P82C",
            "date": "2026-05-26",
            "p82c_classification": "P82C_FAILED_VALIDATION",
            "step1_p82b_verification": p82b_verification,
            "governance": GOVERNANCE,
        }

    # Step 2 — scanner contract
    scanner_contract = step2_scanner_contract()

    # Step 3 — mock fixture scan
    mock_scan = step3_mock_fixture_scan()

    # Step 4 — current repo dry-run
    repo_dryrun = step4_current_repo_dryrun()

    # Determine classification
    if not mock_scan["all_passed"]:
        classification = "P82C_FAILED_VALIDATION"
    elif repo_dryrun["overall_guard_state"] in ("BLOCK_SECRET", "BLOCK_RAW_PAID_DATA",
                                                  "BLOCK_ROW_LEVEL_LEAKAGE", "BLOCK_UNPOLICIED_ODDS"):
        classification = "P82C_STAGING_GUARD_DRYRUN_READY_WITH_WARNINGS"
    else:
        classification = "P82C_STAGING_GUARD_DRYRUN_READY"

    result: dict[str, Any] = {
        "phase": "P82C",
        "date": "2026-05-26",
        "p82c_classification": classification,
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "governance": GOVERNANCE,
        "prediction_boundary": PREDICTION_BOUNDARY,
        "source_artifacts": {k: str(p) for k, p in PATHS.items()},
        "step1_p82b_verification": p82b_verification,
        "step2_scanner_contract": scanner_contract,
        "step3_mock_fixture_scan": mock_scan,
        "step4_current_repo_dryrun": repo_dryrun,
        "p82_status": "BLOCKED_NO_REAL_DATASET",
        "p82_unlock_condition": "Requires external legal odds dataset + P81 validator pass",
    }

    result_text = json.dumps(result, indent=2)
    scan = _scan_forbidden(result_text)
    result["forbidden_scan"] = scan

    return result


def main() -> None:
    result = run_p82c()
    cls = result.get("p82c_classification", "UNKNOWN")
    print(f"[P82C] Classification: {cls}")

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(result, f, indent=2)
    print(f"[P82C] JSON → {OUTPUT_JSON}")

    if cls not in ("P82C_BLOCKED_BY_MISSING_P82B_ARTIFACT", "P82C_FAILED_VALIDATION"):
        report_text = _generate_report(result)
        OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_REPORT.write_text(report_text)
        print(f"[P82C] Report → {OUTPUT_REPORT}")
        PLAN_REPORT.parent.mkdir(parents=True, exist_ok=True)
        PLAN_REPORT.write_text(report_text)
        print(f"[P82C] Plan report → {PLAN_REPORT}")

    scan = result.get("forbidden_scan", {})
    if scan.get("result") != "CLEAN":
        print(f"[P82C] FORBIDDEN PHRASE VIOLATION: {scan.get('violations')}")
        sys.exit(1)
    print("[P82C] Forbidden scan: CLEAN")
    print("[P82C] Done.")


if __name__ == "__main__":
    main()
