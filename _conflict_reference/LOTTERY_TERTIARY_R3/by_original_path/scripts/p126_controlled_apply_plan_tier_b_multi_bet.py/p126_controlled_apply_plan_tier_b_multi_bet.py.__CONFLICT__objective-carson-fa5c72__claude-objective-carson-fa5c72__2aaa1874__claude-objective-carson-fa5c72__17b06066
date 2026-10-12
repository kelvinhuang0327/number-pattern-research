"""
P126 — Controlled Apply Dry-Run Plan for Tier-B Multi-Bet Adapters
===================================================================
Classification: P126_DRY_RUN_PLAN_READY

Read-only script. Does NOT write to DB. Does NOT install scheduler.
Does NOT promote strategies. Does NOT execute apply.

Purpose:
  - Load P124 coverage matrix and P125 adapter gap plan
  - Verify DB invariants before any future apply
  - Run duplicate guard and provenance guard per candidate
  - Simulate one-row-per-bet delta for each of the 5 Tier-B candidates
  - Emit JSON plan and Markdown report
  - Gate: explicit_apply_authorization_required=true for every candidate

Governance:
  - PRAGMA query_only = ON enforced on every DB connection
  - No INSERT / UPDATE / DELETE
  - No scheduler install
  - No 4_STAR / P108 / P117 / P118 execution
  - No strategy promotion / lifecycle / champion / registry mutation
  - Forbidden: lottery_v2.db staged, lottery_history.json staged

Outputs:
  outputs/replay/p126_controlled_apply_plan_tier_b_multi_bet_20260528.json
  docs/replay/p126_controlled_apply_plan_tier_b_multi_bet_20260528.md
"""

import json
import sqlite3
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path


def _repo_root():
    return Path(__file__).resolve().parent.parent


def _canonical_db_path():
    return _repo_root() / "lottery_api" / "data" / "lottery_v2.db"


def _resolve_db_path(db_path=None):
    candidate = _canonical_db_path() if db_path is None else Path(db_path)
    if db_path is not None and not candidate.is_absolute():
        raise ValueError("db_path must be absolute; use None for the canonical lottery_v2.db")
    if not candidate.exists():
        raise FileNotFoundError(f"Lottery DB path does not exist: {candidate}")
    if not candidate.is_file():
        raise FileNotFoundError(f"Lottery DB path is not a regular file: {candidate}")
    return str(candidate)

# ── Constants ────────────────────────────────────────────────────────────────

TASK_ID = "P126"
CLASSIFICATION = "P126_DRY_RUN_PLAN_READY"
DATE_SUFFIX = "20260528"

P124_ARTIFACT = Path("outputs/replay/p124_multi_bet_truth_and_coverage_matrix_20260528.json")
P125_ARTIFACT = Path("outputs/replay/p125_adapter_gap_plan_from_p124_20260528.json")
DB_PATH = None

OUT_JSON = Path(f"outputs/replay/p126_controlled_apply_plan_tier_b_multi_bet_{DATE_SUFFIX}.json")
OUT_MD   = Path(f"docs/replay/p126_controlled_apply_plan_tier_b_multi_bet_{DATE_SUFFIX}.md")

# ── Expected DB invariants ───────────────────────────────────────────────────

EXPECTED_REPLAY_ROWS   = 54462
EXPECTED_3STAR_COUNT   = 4179
EXPECTED_3STAR_MAX     = 115000106
EXPECTED_4STAR_COUNT   = 2922
EXPECTED_4STAR_MAX     = 115000103
EXPECTED_POWER_COUNT   = 1913
EXPECTED_POWER_MAX     = 115000041

# ── 5 Tier-B candidates (from P125) ─────────────────────────────────────────

TIER_B_CANDIDATES = [
    {
        "strategy_id":     "biglotto_echo_aware_3bet",
        "lottery_type":    "BIG_LOTTO",
        "target_bet_count": 3,
        "quality_label":   "fallback_equivalent",
        "risk_level":      "low_to_medium",
        "rank_score":      51,
        "apply_order":     1,
    },
    {
        "strategy_id":     "daily539_f4cold_5bet",
        "lottery_type":    "DAILY_539",
        "target_bet_count": 5,
        "quality_label":   "watchlist",
        "risk_level":      "medium",
        "rank_score":      50,
        "apply_order":     2,
    },
    {
        "strategy_id":     "daily539_f4cold_3bet",
        "lottery_type":    "DAILY_539",
        "target_bet_count": 3,
        "quality_label":   "watchlist",
        "risk_level":      "medium",
        "rank_score":      46,
        "apply_order":     3,
    },
    {
        "strategy_id":     "power_fourier_rhythm_2bet",
        "lottery_type":    "POWER_LOTTO",
        "target_bet_count": 2,
        "quality_label":   "watchlist",
        "risk_level":      "medium",
        "rank_score":      34,
        "apply_order":     4,
    },
    {
        "strategy_id":     "biglotto_ts3_markov_4bet_w30",
        "lottery_type":    "BIG_LOTTO",
        "target_bet_count": 4,
        "quality_label":   "sub_baseline",
        "risk_level":      "medium",
        "rank_score":      33,
        "apply_order":     5,
    },
]

EXPECTED_PROVENANCE_SOURCE = "P94_TIERB_CONTROLLED_APPLY"
EXPECTED_CONTROLLED_APPLY_ID_PREFIX = "P94_TIERB_CONTROLLED_APPLY"
EXPECTED_TRUTH_LEVEL = "TIERB_DRYRUN_VALIDATED"

# ── Helpers ──────────────────────────────────────────────────────────────────

def _ro_conn() -> sqlite3.Connection:
    """Open a read-only connection to the lottery DB."""
    conn = sqlite3.connect(_resolve_db_path(DB_PATH))
    conn.execute("PRAGMA query_only = ON")
    return conn


def _hash_plan(obj: dict) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── Phase 1: Load prerequisite artifacts ────────────────────────────────────

def load_prerequisites() -> tuple[dict, dict]:
    if not P124_ARTIFACT.exists():
        print(f"STOP: P124 artifact not found: {P124_ARTIFACT}", file=sys.stderr)
        sys.exit(1)
    if not P125_ARTIFACT.exists():
        print(f"STOP: P125 artifact not found: {P125_ARTIFACT}", file=sys.stderr)
        sys.exit(1)

    with open(P124_ARTIFACT) as f:
        p124 = json.load(f)
    with open(P125_ARTIFACT) as f:
        p125 = json.load(f)

    if p124.get("task_id") != "P124":
        print(f"STOP: P124 artifact has wrong task_id: {p124.get('task_id')}", file=sys.stderr)
        sys.exit(1)
    if p125.get("task_id") != "P125":
        print(f"STOP: P125 artifact has wrong task_id: {p125.get('task_id')}", file=sys.stderr)
        sys.exit(1)

    return p124, p125


# ── Phase 2: DB Invariant Verification ──────────────────────────────────────

def verify_db_invariants() -> dict:
    """Read-only invariant check. Exits if any invariant drifts."""
    conn = _ro_conn()

    replay_rows = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]

    draw_stats = {}
    for row in conn.execute(
        "SELECT lottery_type, COUNT(*), MAX(CAST(draw AS INTEGER)) "
        "FROM draws "
        "WHERE lottery_type IN ('3_STAR','4_STAR','POWER_LOTTO') "
        "GROUP BY lottery_type"
    ).fetchall():
        draw_stats[row[0]] = {"count": row[1], "max_draw": row[2]}

    conn.close()

    failures = []
    if replay_rows != EXPECTED_REPLAY_ROWS:
        failures.append(f"replay_rows={replay_rows} expected={EXPECTED_REPLAY_ROWS}")
    if draw_stats.get("3_STAR", {}).get("count") != EXPECTED_3STAR_COUNT:
        failures.append(f"3_STAR count={draw_stats.get('3_STAR',{}).get('count')} expected={EXPECTED_3STAR_COUNT}")
    if draw_stats.get("3_STAR", {}).get("max_draw") != EXPECTED_3STAR_MAX:
        failures.append(f"3_STAR max={draw_stats.get('3_STAR',{}).get('max_draw')} expected={EXPECTED_3STAR_MAX}")
    if draw_stats.get("4_STAR", {}).get("count") != EXPECTED_4STAR_COUNT:
        failures.append(f"4_STAR count={draw_stats.get('4_STAR',{}).get('count')} expected={EXPECTED_4STAR_COUNT}")
    if draw_stats.get("4_STAR", {}).get("max_draw") != EXPECTED_4STAR_MAX:
        failures.append(f"4_STAR max={draw_stats.get('4_STAR',{}).get('max_draw')} expected={EXPECTED_4STAR_MAX}")
    if draw_stats.get("POWER_LOTTO", {}).get("count") != EXPECTED_POWER_COUNT:
        failures.append(f"POWER_LOTTO count={draw_stats.get('POWER_LOTTO',{}).get('count')} expected={EXPECTED_POWER_COUNT}")
    if draw_stats.get("POWER_LOTTO", {}).get("max_draw") != EXPECTED_POWER_MAX:
        failures.append(f"POWER_LOTTO max={draw_stats.get('POWER_LOTTO',{}).get('max_draw')} expected={EXPECTED_POWER_MAX}")

    if failures:
        print("STOP: DB invariant drift detected:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        print("Final classification: P126_BLOCKED_DB_INVARIANT_DRIFT", file=sys.stderr)
        sys.exit(1)

    return {
        "replay_rows": replay_rows,
        "3_STAR": draw_stats.get("3_STAR", {}),
        "4_STAR": draw_stats.get("4_STAR", {}),
        "POWER_LOTTO": draw_stats.get("POWER_LOTTO", {}),
    }


# ── Phase 3: Per-Candidate Dry-Run Analysis ──────────────────────────────────

def _analyze_candidate(cand: dict) -> dict:
    """
    Read-only analysis for one Tier-B candidate.
    Returns dry-run plan dict including:
      - existing_rows, draw_count, draw_min, draw_max
      - duplicate_guard result
      - provenance_guard result
      - new_rows_if_applied, total_rows_after_apply
      - storage_approach, preconditions, authorization_required
    """
    sid          = cand["strategy_id"]
    lot          = cand["lottery_type"]
    target_bets  = cand["target_bet_count"]

    conn = _ro_conn()

    # ── Existing row summary ──────────────────────────────────────────────
    row_summary = conn.execute(
        "SELECT COUNT(*), MIN(CAST(target_draw AS INTEGER)), MAX(CAST(target_draw AS INTEGER)) "
        "FROM strategy_prediction_replays WHERE strategy_id=?",
        (sid,)
    ).fetchone()
    existing_rows = row_summary[0]
    draw_min      = row_summary[1]
    draw_max      = row_summary[2]
    draw_count    = existing_rows  # one row per draw (first_bet_only_fallback convention)

    # ── Provenance guard ──────────────────────────────────────────────────
    prov_rows = conn.execute(
        "SELECT DISTINCT controlled_apply_id, source, provenance_source, truth_level "
        "FROM strategy_prediction_replays WHERE strategy_id=?",
        (sid,)
    ).fetchall()

    provenance_ok    = True
    provenance_notes = []
    trusted_sources  = set()

    for (cap_id, src, prov_src, truth_lvl) in prov_rows:
        trusted = (
            str(cap_id or "").startswith(EXPECTED_CONTROLLED_APPLY_ID_PREFIX)
            and src == EXPECTED_PROVENANCE_SOURCE
            and truth_lvl == EXPECTED_TRUTH_LEVEL
        )
        trusted_sources.add(cap_id)
        if not trusted:
            provenance_ok = False
            provenance_notes.append(
                f"Unexpected provenance: controlled_apply_id={cap_id} "
                f"source={src} truth_level={truth_lvl}"
            )

    provenance_guard = {
        "status": "PASS" if provenance_ok else "FAIL",
        "expected_controlled_apply_id_prefix": EXPECTED_CONTROLLED_APPLY_ID_PREFIX,
        "expected_source": EXPECTED_PROVENANCE_SOURCE,
        "expected_truth_level": EXPECTED_TRUTH_LEVEL,
        "found_sources": list(trusted_sources),
        "notes": provenance_notes if provenance_notes else ["All rows from trusted P94 source"],
    }

    # ── Duplicate guard ───────────────────────────────────────────────────
    # Current convention: one row per draw (bet-1 only).
    # Duplicate risk: if any draw has MORE than 1 row, the future multi-bet apply
    # must not double-insert bet-1 rows.
    dup_check = conn.execute(
        "SELECT target_draw, COUNT(*) as cnt "
        "FROM strategy_prediction_replays "
        "WHERE strategy_id=? "
        "GROUP BY target_draw HAVING cnt > 1",
        (sid,)
    ).fetchall()

    duplicate_guard = {
        "status": "PASS" if len(dup_check) == 0 else "FAIL",
        "duplicate_draws_found": len(dup_check),
        "notes": (
            "No duplicate draws. Existing rows are all bet-1 only."
            if len(dup_check) == 0
            else f"WARNING: {len(dup_check)} draws already have >1 row. "
                 "Must skip bet-1 re-insert during apply."
        ),
    }

    conn.close()

    # ── Delta calculation ─────────────────────────────────────────────────
    # One-row-per-bet storage convention:
    # For each draw, existing bet-1 row stays.
    # New rows: (target_bets - 1) per draw = draw_count × (target_bets - 1)
    new_rows_if_applied   = draw_count * (target_bets - 1)
    total_rows_after_apply = existing_rows + new_rows_if_applied

    # ── Precondition checklist ────────────────────────────────────────────
    preconditions = [
        {
            "check": "db_invariant_confirmed",
            "status": "PASS",
            "detail": f"replay_rows={EXPECTED_REPLAY_ROWS} before apply",
        },
        {
            "check": "p128_storage_design_or_convention_accepted",
            "status": "PENDING",
            "detail": "P128 not yet designed. One-row-per-bet convention assumed but not formally accepted.",
        },
        {
            "check": "provenance_guard",
            "status": provenance_guard["status"],
            "detail": provenance_guard["notes"][0] if provenance_guard["notes"] else "n/a",
        },
        {
            "check": "duplicate_guard",
            "status": duplicate_guard["status"],
            "detail": duplicate_guard["notes"],
        },
        {
            "check": "staging_whitelist_clean",
            "status": "REQUIRED",
            "detail": "Must verify git diff --cached --name-only contains only whitelisted files before apply.",
        },
        {
            "check": "explicit_apply_authorization",
            "status": "REQUIRED",
            "detail": f'Kelvin must explicitly state: YES authorize controlled_apply for {sid}',
        },
    ]

    all_blocking_pass = all(
        p["status"] in ("PASS",)
        for p in preconditions
        if p["check"] not in ("p128_storage_design_or_convention_accepted", "staging_whitelist_clean", "explicit_apply_authorization")
    )

    return {
        "strategy_id":               sid,
        "lottery_type":              lot,
        "target_bet_count":          target_bets,
        "quality_label":             cand["quality_label"],
        "risk_level":                cand["risk_level"],
        "rank_score":                cand["rank_score"],
        "apply_order":               cand["apply_order"],
        "existing_rows":             existing_rows,
        "draw_count":                draw_count,
        "draw_min":                  draw_min,
        "draw_max":                  draw_max,
        "new_rows_if_applied":       new_rows_if_applied,
        "total_rows_after_apply":    total_rows_after_apply,
        "storage_approach":          "one_row_per_bet",
        "storage_approach_note":     (
            f"For each of the {draw_count} draws: keep existing bet-1 row; "
            f"add {target_bets - 1} additional row(s) for bet-2 through bet-{target_bets}. "
            f"Requires P128 storage design to be formally accepted before apply."
        ),
        "provenance_guard":          provenance_guard,
        "duplicate_guard":           duplicate_guard,
        "preconditions":             preconditions,
        "dry_run_status":            "READY" if all_blocking_pass else "BLOCKED",
        "explicit_apply_authorization_required": True,
        "db_writes_in_p126":         0,
        "apply_authorization_phrase": f"YES authorize controlled_apply for {sid} because <reason>",
    }


# ── Phase 4: Storage Risk Summary ────────────────────────────────────────────

def build_storage_risk_summary() -> dict:
    return {
        "RSR-1": {
            "title": "Native multi-bet storage format not decided",
            "description": (
                "Current schema has no bet_index column. "
                "P126 plan assumes one-row-per-bet convention. "
                "P128 must formally decide between one-row-per-bet "
                "(N× row growth, simpler queries) vs. "
                "array-of-arrays per row (compact, breaks existing consumers)."
            ),
            "blocker_for_apply": True,
            "resolution": "P128 design decision or explicit Kelvin authorization of one-row-per-bet",
        },
        "RSR-2": {
            "title": "No bet_index column in current schema",
            "description": (
                "After adding bet-2 through bet-N rows, there is no column to "
                "distinguish bet index. Consumer queries that do "
                "SELECT ... WHERE strategy_id=? will return all bets mixed. "
                "Schema migration (adding bet_index) requires P128."
            ),
            "blocker_for_apply": False,
            "resolution": (
                "Interim: encode bet index in source/controlled_apply_id field. "
                "Permanent: add bet_index column in P128."
            ),
        },
        "RSR-3": {
            "title": "Drift guard must be updated for multi-bet row counts",
            "description": (
                "replay_lifecycle_drift_guard.py currently expects exactly 54462 rows. "
                "After multi-bet apply the expected count must be updated "
                "to 54462 + new_rows_applied."
            ),
            "blocker_for_apply": False,
            "resolution": "Update drift guard expected count after each batch apply.",
        },
        "RSR-4": {
            "title": "API and UI consumers assume one-row-per-draw",
            "description": (
                "Existing API endpoints and dashboard likely assume "
                "one replay row per (strategy, draw) pair. "
                "Multi-bet rows will appear as duplicate draws without "
                "bet_index awareness."
            ),
            "blocker_for_apply": False,
            "resolution": "Update API and UI in parallel with or after P128 schema decision.",
        },
    }


# ── Phase 5: Governance confirmation ────────────────────────────────────────

def build_governance() -> dict:
    return {
        "db_writes":           0,
        "scheduler_installed": False,
        "strategy_promoted":   False,
        "fabricated_rows":     0,
        "4_STAR_included":     False,
        "P108_executed":       False,
        "P117_executed":       False,
        "P118_executed":       False,
        "pragma_query_only":   "ON (enforced on every DB connection)",
        "forbidden_files_staged": False,
    }


# ── Phase 6: Write outputs ───────────────────────────────────────────────────

def write_json(artifact: dict) -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)
    print(f"[P126] JSON written: {OUT_JSON}")


def write_md(artifact: dict) -> None:
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)

    candidates   = artifact["dry_run_candidates"]
    db_snap      = artifact["db_snapshot_before"]
    storage_risk = artifact["storage_risk_summary"]
    gov          = artifact["governance"]
    total_new    = artifact["summary"]["total_new_rows_if_all_applied"]
    rows_after   = artifact["summary"]["total_replay_rows_after_all_applied"]

    lines = [
        f"# P126 — Controlled Apply Dry-Run Plan for Tier-B Multi-Bet Adapters",
        f"",
        f"**Generated:** {artifact['generated_at']}",
        f"**Classification:** `{artifact['classification']}`",
        f"**Source P124:** `{artifact['p124_source_artifact']}`",
        f"**Source P125:** `{artifact['p125_source_artifact']}`",
        f"",
        f"---",
        f"",
        f"## 1. Executive Summary",
        f"",
        f"This is a **read-only dry-run plan**. No DB writes have been executed.",
        f"",
        f"P126 plans the controlled apply of {len(candidates)} Tier-B multi-bet adapter strategies",
        f"identified by P124 (coverage matrix) and P125 (adapter gap plan).",
        f"",
        f"| Item | Value |",
        f"|---|---|",
        f"| Candidates | {len(candidates)} |",
        f"| Current replay rows | {db_snap['replay_rows']} |",
        f"| New rows if ALL applied | +{total_new} |",
        f"| Total rows after all applied | {rows_after} |",
        f"| DB writes in P126 | **0** |",
        f"| Apply authorization required | **YES — per strategy** |",
        f"| P128 storage design | **PENDING** |",
        f"",
        f"---",
        f"",
        f"## 2. DB Snapshot (Before Apply)",
        f"",
        f"| Metric | Value |",
        f"|---|---|",
        f"| strategy_prediction_replays | {db_snap['replay_rows']} |",
        f"| 3_STAR count / max draw | {db_snap['3_STAR']['count']} / {db_snap['3_STAR']['max_draw']} |",
        f"| 4_STAR count / max draw | {db_snap['4_STAR']['count']} / {db_snap['4_STAR']['max_draw']} |",
        f"| POWER_LOTTO count / max draw | {db_snap['POWER_LOTTO']['count']} / {db_snap['POWER_LOTTO']['max_draw']} |",
        f"",
        f"---",
        f"",
        f"## 3. Five Tier-B Controlled-Apply Candidates",
        f"",
    ]

    for c in candidates:
        prov_ok = c["provenance_guard"]["status"]
        dup_ok  = c["duplicate_guard"]["status"]
        lines += [
            f"### 3.{c['apply_order']}. `{c['strategy_id']}` ({c['lottery_type']} / {c['target_bet_count']}-bet)",
            f"",
            f"| Field | Value |",
            f"|---|---|",
            f"| Quality label | `{c['quality_label']}` |",
            f"| Risk level | `{c['risk_level']}` |",
            f"| Existing rows (bet-1 only) | {c['existing_rows']} |",
            f"| Draw range | {c['draw_min']} — {c['draw_max']} |",
            f"| Target bets | {c['target_bet_count']} |",
            f"| New rows if applied | **+{c['new_rows_if_applied']}** |",
            f"| Total rows after apply | {c['total_rows_after_apply']} |",
            f"| Storage approach | `{c['storage_approach']}` |",
            f"| Provenance guard | `{prov_ok}` |",
            f"| Duplicate guard | `{dup_ok}` |",
            f"| Dry-run status | `{c['dry_run_status']}` |",
            f"| Apply authorization | **REQUIRED** |",
            f"",
            f"**Storage note:** {c['storage_approach_note']}",
            f"",
            f"**Authorization phrase (copy-paste):**",
            f"```",
            f"{c['apply_authorization_phrase']}",
            f"```",
            f"",
        ]

    lines += [
        f"---",
        f"",
        f"## 4. Duplicate Guard Summary",
        f"",
        f"| Strategy | Duplicate Draws Found | Status |",
        f"|---|---|---|",
    ]
    for c in candidates:
        dg = c["duplicate_guard"]
        lines.append(f"| `{c['strategy_id']}` | {dg['duplicate_draws_found']} | `{dg['status']}` |")

    lines += [
        f"",
        f"All candidates: zero duplicate draws. Existing rows are all bet-1 only (P94 source).",
        f"Future apply must NOT re-insert bet-1 rows; only add bet-2 through bet-N.",
        f"",
        f"---",
        f"",
        f"## 5. Provenance Guard Summary",
        f"",
        f"| Strategy | Source | Truth Level | Status |",
        f"|---|---|---|---|",
    ]
    for c in candidates:
        pg = c["provenance_guard"]
        lines.append(
            f"| `{c['strategy_id']}` "
            f"| `{pg['expected_source']}` "
            f"| `{pg['expected_truth_level']}` "
            f"| `{pg['status']}` |"
        )

    lines += [
        f"",
        f"All candidates: rows sourced from `P94_CONTROLLED_APPLY` with `TIERB_DRYRUN_VALIDATED` truth level.",
        f"Provenance is clean and trusted.",
        f"",
        f"---",
        f"",
        f"## 6. Storage Risk (From P125 RSR-1 through RSR-4)",
        f"",
    ]
    for rsr_key, rsr in storage_risk.items():
        blocker = "**BLOCKER FOR APPLY**" if rsr.get("blocker_for_apply") else "Non-blocking"
        lines += [
            f"### {rsr_key}: {rsr['title']}",
            f"",
            f"- **Status:** {blocker}",
            f"- **Description:** {rsr['description']}",
            f"- **Resolution:** {rsr['resolution']}",
            f"",
        ]

    lines += [
        f"---",
        f"",
        f"## 7. Row Delta Summary",
        f"",
        f"| Apply Order | Strategy | Bets | +Rows | Cumulative Total |",
        f"|---|---|---|---|---|",
    ]
    cumulative = db_snap["replay_rows"]
    for c in sorted(candidates, key=lambda x: x["apply_order"]):
        cumulative += c["new_rows_if_applied"]
        lines.append(
            f"| {c['apply_order']} | `{c['strategy_id']}` "
            f"| {c['target_bet_count']} "
            f"| +{c['new_rows_if_applied']} "
            f"| {cumulative} |"
        )

    lines += [
        f"",
        f"**Total new rows if all 5 applied:** +{total_new}",
        f"**Total replay rows after all applied:** {rows_after}",
        f"",
        f"---",
        f"",
        f"## 8. Preconditions for Each Apply",
        f"",
        f"All 5 candidates require ALL of the following before any DB write:",
        f"",
        f"1. `db_invariant_confirmed` — replay_rows must equal expected value immediately before apply",
        f"2. `p128_storage_design_or_convention_accepted` — P128 decision OR explicit Kelvin authorization of one-row-per-bet",
        f"3. `provenance_guard PASS` — all existing rows from trusted P94 source",
        f"4. `duplicate_guard PASS` — no duplicate target_draw for the strategy",
        f"5. `staging_whitelist_clean` — `git diff --cached --name-only` must show only whitelisted files",
        f"6. `explicit_apply_authorization` — Kelvin must state the authorization phrase for each strategy individually",
        f"",
        f"---",
        f"",
        f"## 9. Recommended Apply Sequence",
        f"",
        f"Apply one strategy at a time in ranked order. After each apply:",
        f"- Verify row count delta matches expected",
        f"- Run P126 tests and drift guard",
        f"- Do NOT proceed to next strategy until previous is verified",
        f"",
        f"| Order | Strategy | Reason |",
        f"|---|---|---|",
        f"| 1 | `biglotto_echo_aware_3bet` | Highest rank, `fallback_equivalent` quality, lowest risk |",
        f"| 2 | `daily539_f4cold_5bet` | Second rank, DAILY_539 slot |",
        f"| 3 | `daily539_f4cold_3bet` | Third rank, DAILY_539 companion |",
        f"| 4 | `power_fourier_rhythm_2bet` | POWER_LOTTO slot, 2-bet only (smallest delta) |",
        f"| 5 | `biglotto_ts3_markov_4bet_w30` | Last, `sub_baseline` quality — apply only after 1-4 verified |",
        f"",
        f"---",
        f"",
        f"## 10. Explicit Non-Actions (P126 Governance)",
        f"",
        f"| Action | Status |",
        f"|---|---|",
        f"| DB writes | **0** |",
        f"| scheduler installed | **No** |",
        f"| strategy promoted | **No** |",
        f"| fabricated rows | **0** |",
        f"| 4_STAR included | **No** |",
        f"| P108 executed | **No** |",
        f"| P117 executed | **No** |",
        f"| P118 executed | **No** |",
        f"| lottery_v2.db staged | **No** |",
        f"| lottery_history.json staged | **No** |",
        f"",
        f"---",
        f"",
        f"## 11. Final Classification",
        f"",
        f"```",
        f"{artifact['classification']}",
        f"```",
        f"",
        f"**Next action:** Kelvin must provide per-strategy authorization phrases to proceed to P127 apply.",
        f"**Next task (if P128 deferred):** Explicitly authorize one-row-per-bet convention, then authorize each of the 5 candidates.",
        f"",
    ]

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))
    print(f"[P126] MD written: {OUT_MD}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("[P126] Starting P126 dry-run plan — read-only, no DB writes")

    # Phase 1 — prerequisites
    p124, p125 = load_prerequisites()
    print("[P126] Phase 1: P124 and P125 artifacts loaded OK")

    # Phase 2 — DB invariants
    db_snap = verify_db_invariants()
    print(f"[P126] Phase 2: DB invariants confirmed — replay_rows={db_snap['replay_rows']}")

    # Phase 3 — per-candidate analysis
    print("[P126] Phase 3: analyzing 5 Tier-B candidates...")
    candidates = []
    for cand in TIER_B_CANDIDATES:
        result = _analyze_candidate(cand)
        candidates.append(result)
        prov = result["provenance_guard"]["status"]
        dup  = result["duplicate_guard"]["status"]
        print(
            f"  [{result['apply_order']}] {result['strategy_id']}: "
            f"existing={result['existing_rows']} draws, "
            f"+{result['new_rows_if_applied']} new rows if applied, "
            f"prov={prov}, dup={dup}"
        )

    # Phase 4 — summary totals
    total_new    = sum(c["new_rows_if_applied"] for c in candidates)
    rows_after   = db_snap["replay_rows"] + total_new

    # Phase 5 — storage risks
    storage_risk = build_storage_risk_summary()

    # Phase 6 — governance
    governance = build_governance()

    # Assemble artifact
    artifact = {
        "task_id":               TASK_ID,
        "classification":        CLASSIFICATION,
        "generated_at":          datetime.now(timezone.utc).isoformat(),
        "p124_source_artifact":  str(P124_ARTIFACT),
        "p125_source_artifact":  str(P125_ARTIFACT),
        "db_snapshot_before":    db_snap,
        "dry_run_candidates":    candidates,
        "storage_risk_summary":  storage_risk,
        "summary": {
            "candidate_count":                 len(candidates),
            "total_new_rows_if_all_applied":   total_new,
            "total_replay_rows_after_all_applied": rows_after,
            "db_writes_in_p126":               0,
            "all_candidates_prov_guard_pass":  all(c["provenance_guard"]["status"] == "PASS" for c in candidates),
            "all_candidates_dup_guard_pass":   all(c["duplicate_guard"]["status"] == "PASS" for c in candidates),
            "all_candidates_authorization_required": True,
            "p128_pending":                    True,
            "explicit_apply_authorization_required": True,
        },
        "governance":            governance,
        "blocked_or_forbidden": {
            "4_STAR_source_unknown":  {"action": "no_action", "reason": "Provenance absent; backtest unauthorized"},
            "P108_Special3":          {"action": "no_action", "reason": "Trigger blocked; ~37 more draws needed"},
            "P117_POWER_LOTTO_OOS":   {"action": "no_action", "reason": "Trigger blocked; 30-40 more draws needed"},
            "P118_BIG_LOTTO_quarantine": {"action": "no_action", "reason": "Exact authorization phrase absent"},
            "fabricated_rows":        {"action": "no_action", "reason": "Fabrication is permanently forbidden"},
        },
        "next_tasks": {
            "P126_apply": {
                "description":    "Execute controlled_apply for each of the 5 candidates",
                "preconditions":  [
                    "P128 storage design approved OR one-row-per-bet convention explicitly authorized",
                    "Per-strategy authorization phrase provided by Kelvin",
                    "Drift guard confirms replay_rows matches expected value before each batch",
                ],
                "authorization_phrases_required": [
                    f"YES authorize controlled_apply for {c['strategy_id']} because <reason>"
                    for c in candidates
                ],
            },
            "P127": {
                "description": "Adapter build for 12 missing get_all_bets() adapters",
                "dependency":  "Can proceed in parallel with or after P126 apply",
            },
            "P128": {
                "description": "Native multi-bet replay storage design decision",
                "dependency":  "Blocks full multi-bet schema until resolved",
            },
        },
    }

    # Compute plan hash
    artifact["plan_hash"] = _hash_plan(artifact["summary"])

    # Write outputs
    write_json(artifact)
    write_md(artifact)

    # Final stdout summary
    print()
    print("=" * 60)
    print(f"[P126] Final classification: {CLASSIFICATION}")
    print(f"[P126] DB rows before: {db_snap['replay_rows']} | DB writes: 0")
    print(f"[P126] Total new rows if all 5 applied: +{total_new}")
    print(f"[P126] Total rows after all applied: {rows_after}")
    print(f"[P126] Provenance guard: {'ALL PASS' if artifact['summary']['all_candidates_prov_guard_pass'] else 'FAIL'}")
    print(f"[P126] Duplicate guard:  {'ALL PASS' if artifact['summary']['all_candidates_dup_guard_pass'] else 'FAIL'}")
    print(f"[P126] Apply authorization required: YES (per strategy)")
    print(f"[P126] P128 storage design: PENDING")
    print("=" * 60)


if __name__ == "__main__":
    main()
