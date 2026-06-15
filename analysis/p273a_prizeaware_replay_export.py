"""
P273A — Prize-Aware Observed-Counts Export (read-only data prerequisite)

Produces an immutable, traceable observed-counts artifact containing the
draw-level prize-aware support / observed-success counts required by a later,
separately authorized P273A inferential validation.

THIS MODULE IS A READ-ONLY DATA EXPORT PREREQUISITE. It is NOT P273A inference
and NOT P273B feature mining. It does NOT compute random baselines, p-values,
corrected significance, confidence intervals, strategy edge, or any verdict.

Key invariants (governance):
  - Import-safe: no DB open, no file write, no network/subprocess at import time.
  - Reuses committed P271C scorer + P271E adapter logic (eligibility, mapping,
    scoring) rather than redefining endpoints.
  - Opens the canonical DB strictly read-only (URI mode=ro) on ONE connection,
    sets PRAGMA query_only=ON, and reads all three lotteries inside ONE explicit
    read transaction / ONE consistent snapshot.
  - Performs SELECT / PRAGMA reads only. No write statements of any kind.
  - POWER_LOTTO rows with a missing stored second-zone prediction are excluded
    (reason MISSING_PREDICTED_SECOND_ZONE) and are NEVER filled, defaulted,
    inferred, or replaced by the actual second-zone value.
  - Emits no inference, baseline, probability, p-value, correction, or edge claim.

Frozen scope:
  - Lotteries: DAILY_539, BIG_LOTTO, POWER_LOTTO.
  - Strategy x lottery cells: derived from the P267C revalidation artifact
    (exactly 36 cells; asserted).
  - Windows: most-recent 100 / 500 / 1500 distinct target_draw values
    (ordered by CAST(target_draw AS INTEGER) DESC).

Governed prize-aware endpoint (traced from P271A, scored by P271C):
  draw-level success = 1 if any eligible/scoreable bet for that target draw is an
  any_prize_aware_win. Per lottery the minimum qualifying tier is:
    DAILY_539  : hit_count >= 2                              (lowest prize 肆獎)
    BIG_LOTTO  : hit_count >= 3 OR (hit_count = 2 AND special)  ("M2+special")
    POWER_LOTTO: hit_count >= 3 OR (hit_count >= 1 AND special) ("M1+second-zone")

artifact_version = "p273a_observed_counts_v1"
scoring_version  = delegated to lottery_api.prize_aware_scorer.SCORING_VERSION
source_verification_status = "MANUAL_VERIFICATION_REQUIRED"
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone

from lottery_api.prize_aware_replay_adapter import (
    ADAPTER_VERSION,
    EXCLUSION_MISSING_PREDICTED_SECOND_ZONE,
    SUPPORTED_LOTTERY_TYPES,
    _check_eligibility,
    map_replay_row_to_scorer_input,
)
from lottery_api.prize_aware_scorer import (
    SCORING_VERSION,
    SOURCE_VERIFICATION_STATUS,
    score_prize_aware_ticket,
)

# ---------------------------------------------------------------------------
# Frozen constants
# ---------------------------------------------------------------------------

TASK_ID = "P273A_OBSERVED_COUNTS_EXPORT"
ARTIFACT_VERSION = "p273a_observed_counts_v1"

WINDOWS = (100, 500, 1500)
# Canonical reporting order for the three frozen lotteries.
LOTTERY_TYPES = ("DAILY_539", "BIG_LOTTO", "POWER_LOTTO")
EXPECTED_FROZEN_CELL_COUNT = 36

CANONICAL_DB_PATH = "lottery_api/data/lottery_v2.db"
DB_OPEN_MODE = "sqlite3 URI mode=ro + PRAGMA query_only=ON"

P271A_JSON_PATH = (
    "outputs/research/p271a_prize_aware_endpoint_scoring_spec_20260611.json"
)
P267C_JSON_PATH = (
    "outputs/research/p267c_m3plus_strategy_revalidation_20260610.json"
)
P271C_SOURCE_PATH = "lottery_api/prize_aware_scorer.py"
P271E_SOURCE_PATH = "lottery_api/prize_aware_replay_adapter.py"

DEFAULT_OUT_JSON = (
    "outputs/research/p273a_prizeaware_observed_counts_20260614.json"
)
DEFAULT_OUT_MD = "outputs/research/p273a_prizeaware_observed_counts_20260614.md"

# Governed "any prize" endpoint per lottery. The expected_condition_sql values
# are verified against the committed P271A spec at run time (verify, not assume).
GOVERNED_ENDPOINT = {
    "DAILY_539": {
        "endpoint_id": "D539_ANY_PRIZE_AWARE_WIN",
        "expected_condition_sql": "hit_count >= 2",
        "task_shorthand": "governed prize-aware endpoint",
        "min_qualifying_tier": "肆獎 (2-match)",
    },
    "BIG_LOTTO": {
        "endpoint_id": "BIG_ANY_PRIZE_AWARE_WIN",
        "expected_condition_sql": (
            "hit_count >= 3 OR (hit_count = 2 AND special_hit = 1)"
        ),
        "task_shorthand": "M2-plus-special",
        "min_qualifying_tier": "普獎 (2-match + special)",
    },
    "POWER_LOTTO": {
        "endpoint_id": "POWER_ANY_PRIZE_AWARE_WIN",
        "expected_condition_sql": (
            "hit_count >= 3 OR (hit_count >= 1 AND special_hit = 1)"
        ),
        "task_shorthand": "M1-plus-second-zone",
        "min_qualifying_tier": "普獎 (1-match + second-zone)",
    },
}

# Required tables/columns; a missing table or column is schema drift -> STOP.
REQUIRED_COLUMNS = {
    "strategy_prediction_replays": (
        "lottery_type", "target_draw", "strategy_id", "bet_index",
        "history_cutoff_draw", "predicted_numbers", "predicted_special",
        "actual_numbers", "actual_special", "replay_status", "dry_run",
    ),
    "draws": ("lottery_type", "draw"),
}

# The single normalized per-cell read query (parameterized, read-only).
CELL_QUERY = (
    "SELECT "
    "r.lottery_type, r.target_draw, r.strategy_id, r.bet_index, "
    "r.history_cutoff_draw, r.predicted_numbers, r.predicted_special, "
    "r.actual_numbers, r.actual_special, "
    "(SELECT COUNT(*) FROM draws d "
    "WHERE d.lottery_type = r.lottery_type AND d.draw = r.target_draw) "
    "AS join_count "
    "FROM strategy_prediction_replays r "
    "WHERE r.lottery_type = ? AND r.strategy_id = ? "
    "AND r.replay_status = 'PREDICTED' AND r.dry_run = 0 "
    "ORDER BY CAST(r.target_draw AS INTEGER) DESC, r.bet_index ASC"
)

# Fields excluded from the deterministic payload digest: wall-clock timestamps,
# environment-specific paths (so the digest reflects substantive content, not
# where the DB file lives), and the self-hash field itself.
_VOLATILE_KEYS = frozenset({
    "generated_at",
    "transaction_start_at",
    "transaction_end_at",
    "canonical_payload_digest",
    "source_db_path",
    "connection_uri",
})


class P273AExportError(RuntimeError):
    """Base error for the export; raising one STOPs the export with no write."""


class SchemaDriftError(P273AExportError):
    """A required table or column is missing from the opened database."""


class FrozenCellError(P273AExportError):
    """The frozen strategy x lottery cell set is not exactly 36."""


class EndpointDriftError(P273AExportError):
    """A committed P271A endpoint condition differs from the expected value."""


class QueryOnlyError(P273AExportError):
    """PRAGMA query_only could not be confirmed enabled on the connection."""


# ---------------------------------------------------------------------------
# Provenance helpers (pure)
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: str) -> str:
    """Return the SHA-256 hex digest of a file's bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalize_sql(text: str) -> str:
    """Collapse whitespace so a stored table-definition string fingerprints stably."""
    return " ".join((text or "").split())


# ---------------------------------------------------------------------------
# Frozen scope + endpoint verification (pure, no DB)
# ---------------------------------------------------------------------------

def load_frozen_cells(p267c_path: str) -> list:
    """Derive the frozen strategy x lottery cells from the P267C artifact.

    Returns a list of {"lottery_type", "strategy_id"} dicts in canonical order
    (lottery order = LOTTERY_TYPES, then strategy_id ascending).

    No filtering, ranking, replacement, or outcome-based reselection is done.
    Raises FrozenCellError unless exactly EXPECTED_FROZEN_CELL_COUNT cells exist.
    """
    with open(p267c_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    results = data.get("results")
    if not isinstance(results, list):
        raise FrozenCellError("P267C artifact has no 'results' list")

    seen = []
    seen_keys = set()
    for entry in results:
        lt = entry.get("lottery_type")
        sid = entry.get("strategy_id")
        if lt not in LOTTERY_TYPES:
            raise FrozenCellError(f"Unexpected lottery_type in P267C: {lt!r}")
        if not isinstance(sid, str) or not sid:
            raise FrozenCellError(f"Invalid strategy_id in P267C: {sid!r}")
        key = (lt, sid)
        if key in seen_keys:
            raise FrozenCellError(f"Duplicate frozen cell in P267C: {key!r}")
        seen_keys.add(key)
        seen.append({"lottery_type": lt, "strategy_id": sid})

    if len(seen) != EXPECTED_FROZEN_CELL_COUNT:
        raise FrozenCellError(
            f"Expected {EXPECTED_FROZEN_CELL_COUNT} frozen cells, "
            f"found {len(seen)}"
        )

    lot_rank = {lt: i for i, lt in enumerate(LOTTERY_TYPES)}
    seen.sort(key=lambda c: (lot_rank[c["lottery_type"]], c["strategy_id"]))
    return seen


def verify_endpoints_against_p271a(p271a_path: str) -> dict:
    """Verify each governed endpoint condition matches the committed P271A spec.

    Returns {lottery_type: actual_condition_sql}. Raises EndpointDriftError if a
    committed condition differs from GOVERNED_ENDPOINT[lt]["expected_condition_sql"].
    Endpoint definitions are never redefined here — only verified.
    """
    with open(p271a_path, "r", encoding="utf-8") as fh:
        spec = json.load(fh)
    defs = spec.get("endpoint_definitions", {})
    actual = {}
    for lt in LOTTERY_TYPES:
        endpoint_id = GOVERNED_ENDPOINT[lt]["endpoint_id"]
        expected = _normalize_sql(GOVERNED_ENDPOINT[lt]["expected_condition_sql"])
        try:
            committed = defs[lt][endpoint_id]["condition_sql"]
        except (KeyError, TypeError):
            raise EndpointDriftError(
                f"P271A is missing endpoint {lt}/{endpoint_id}"
            )
        if _normalize_sql(committed) != expected:
            raise EndpointDriftError(
                f"P271A endpoint {lt}/{endpoint_id} condition differs: "
                f"committed={committed!r} expected={expected!r}"
            )
        actual[lt] = committed
    return actual


# ---------------------------------------------------------------------------
# Read-only connection management (single connection, single snapshot)
# ---------------------------------------------------------------------------

def open_readonly_connection(db_path: str) -> tuple:
    """Open the DB strictly read-only and enforce PRAGMA query_only=ON.

    Returns (connection, query_only_evidence_dict). Raises QueryOnlyError if
    query_only cannot be confirmed enabled.
    """
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    # Manual transaction control so all reads share one snapshot.
    conn.isolation_level = None
    conn.execute("PRAGMA query_only=ON")
    row = conn.execute("PRAGMA query_only").fetchone()
    enabled = bool(row and row[0] == 1)
    if not enabled:
        conn.close()
        raise QueryOnlyError("PRAGMA query_only did not report enabled")
    evidence = {
        "connection_uri": uri,
        "mode_ro": True,
        "query_only_pragma_value": (row[0] if row else None),
        "query_only_enabled": enabled,
    }
    return conn, evidence


def verify_schema(conn: sqlite3.Connection) -> dict:
    """Verify required tables/columns exist; capture schema identity.

    Raises SchemaDriftError on any missing required table or column.
    """
    table_def = {}
    for table in REQUIRED_COLUMNS:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if row is None or row[0] is None:
            raise SchemaDriftError(f"Required table missing: {table}")
        table_def[table] = _normalize_sql(row[0])

    column_inventory = {}
    for table, required in REQUIRED_COLUMNS.items():
        present = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        column_inventory[table] = present
        missing = [c for c in required if c not in present]
        if missing:
            raise SchemaDriftError(
                f"Table {table} missing required columns: {missing}"
            )

    user_version = conn.execute("PRAGMA user_version").fetchone()[0]
    schema_cookie = conn.execute("PRAGMA schema_version").fetchone()[0]
    fingerprint_src = "\n".join(
        f"{t}::{table_def[t]}" for t in sorted(table_def)
    )
    fingerprint = hashlib.sha256(fingerprint_src.encode("utf-8")).hexdigest()
    return {
        "user_version": user_version,
        "schema_version_cookie": schema_cookie,
        "schema_fingerprint_sha256": fingerprint,
        "table_definition_sql": table_def,
        "column_inventory": column_inventory,
    }


# ---------------------------------------------------------------------------
# Per-row processing + per-cell aggregation (reuses P271C/P271E logic)
# ---------------------------------------------------------------------------

def _row_dict(raw) -> dict:
    """Map a CELL_QUERY result tuple to the adapter row-dict contract."""
    return {
        "lottery_type": raw[0],
        "target_draw": raw[1],
        "strategy_id": raw[2],
        "bet_index": raw[3],
        "history_cutoff_draw": raw[4],
        "predicted_numbers": raw[5],
        "predicted_special": raw[6],
        "actual_numbers": raw[7],
        "actual_special": raw[8],
        "_join_count": raw[9],
    }


def _process_rows(rows: list) -> tuple:
    """Deduplicate by (target_draw, bet_index), then classify each row.

    Returns (processed, distinct_draws_desc):
      processed = list of {target_draw, bet_index, eligible, reason, win}
                  in the original CAST-DESC order (no pseudo-replication).
      distinct_draws_desc = distinct target_draw values, most-recent first.
    """
    processed = []
    distinct_draws_desc = []
    seen_draw = set()
    seen_bet = set()
    for raw in rows:
        row = _row_dict(raw)
        td = row["target_draw"]
        bi = row["bet_index"]
        dedupe_key = (td, bi)
        if dedupe_key in seen_bet:
            continue  # duplicate replay row -> count once
        seen_bet.add(dedupe_key)

        eligible, reason = _check_eligibility(row)
        win = False
        if eligible:
            result = score_prize_aware_ticket(**map_replay_row_to_scorer_input(row))
            win = bool(result["any_prize_aware_win"])
        processed.append({
            "target_draw": td,
            "bet_index": bi,
            "eligible": eligible,
            "reason": reason,
            "win": win,
        })
        if td not in seen_draw:
            seen_draw.add(td)
            distinct_draws_desc.append(td)
    return processed, distinct_draws_desc


def aggregate_window(processed: list, distinct_draws_desc: list, window: int,
                     lottery_type: str, strategy_id: str) -> dict:
    """Compute the observed-counts record for one strategy x lottery x window.

    Window = most-recent `window` distinct target_draw values. A draw enters
    support only if it has at least one eligible/scoreable bet. Draw-level
    success = any eligible bet is an any_prize_aware_win. No baseline / p-value.
    """
    window_draws = distinct_draws_desc[:window]
    window_set = set(window_draws)

    # Group window rows by target_draw.
    by_draw = {}
    for pr in processed:
        if pr["target_draw"] not in window_set:
            continue
        d = by_draw.setdefault(
            pr["target_draw"],
            {"scoreable_bets": set(), "any_win": False, "excluded": []},
        )
        if pr["eligible"]:
            d["scoreable_bets"].add(pr["bet_index"])
            if pr["win"]:
                d["any_win"] = True
        else:
            d["excluded"].append(pr["reason"])

    support_draws = 0
    observed_successes = 0
    scoreable_rows = 0
    excluded_rows = 0
    exclusion_by_reason = Counter()
    bet_counts = []  # distinct scoreable bet_index per supported draw

    for td in window_draws:
        d = by_draw.get(td)
        if d is None:
            continue
        n_score = len(d["scoreable_bets"])
        scoreable_rows += n_score
        excluded_rows += len(d["excluded"])
        exclusion_by_reason.update(d["excluded"])
        if n_score >= 1:
            support_draws += 1
            bet_counts.append(n_score)
            if d["any_win"]:
                observed_successes += 1

    excluded_missing_special_rows = exclusion_by_reason.get(
        EXCLUSION_MISSING_PREDICTED_SECOND_ZONE, 0
    )
    bet_count_distribution = {
        str(k): v for k, v in sorted(Counter(bet_counts).items())
    }
    bet_count_min = min(bet_counts) if bet_counts else None
    bet_count_max = max(bet_counts) if bet_counts else None
    bet_count_constant = (
        len(set(bet_counts)) <= 1 if bet_counts else None
    )
    success_rate = (
        observed_successes / support_draws if support_draws else None
    )
    draw_ints = [int(d) for d in window_draws]
    latest_target_draw = str(max(draw_ints)) if draw_ints else None
    earliest_target_draw = str(min(draw_ints)) if draw_ints else None

    endpoint = GOVERNED_ENDPOINT[lottery_type]
    return {
        "lottery_type": lottery_type,
        "strategy_id": strategy_id,
        "window": window,
        "requested_window": window,
        "support_draws": support_draws,
        "observed_successes": observed_successes,
        "observed_success_rate": success_rate,
        "scoreable_rows": scoreable_rows,
        "excluded_rows": excluded_rows,
        "excluded_missing_special_rows": excluded_missing_special_rows,
        "exclusion_by_reason": dict(sorted(exclusion_by_reason.items())),
        "bet_count_min": bet_count_min,
        "bet_count_max": bet_count_max,
        "bet_count_constant": bet_count_constant,
        "bet_count_distribution": bet_count_distribution,
        "distinct_draws_in_window": len(window_draws),
        "latest_target_draw": latest_target_draw,
        "earliest_target_draw": earliest_target_draw,
        "endpoint_id": endpoint["endpoint_id"],
        "endpoint_source_ref": "P271A",
        "strategy_source_ref": "P267C",
    }


def compute_cell(conn: sqlite3.Connection, lottery_type: str,
                 strategy_id: str) -> dict:
    """Read one cell's rows and aggregate all windows. Returns a cell block."""
    cur = conn.execute(CELL_QUERY, (lottery_type, strategy_id))
    rows = cur.fetchall()
    processed, distinct_draws_desc = _process_rows(rows)
    windows = [
        aggregate_window(processed, distinct_draws_desc, w,
                         lottery_type, strategy_id)
        for w in WINDOWS
    ]
    return {
        "lottery_type": lottery_type,
        "strategy_id": strategy_id,
        "distinct_draws_available": len(distinct_draws_desc),
        "windows": windows,
    }


# ---------------------------------------------------------------------------
# Canonical payload digest + Markdown rendering
# ---------------------------------------------------------------------------

def _strip_volatile(obj):
    """Deep-copy `obj` removing volatile keys (recursively) for hashing."""
    if isinstance(obj, dict):
        return {
            k: _strip_volatile(v)
            for k, v in obj.items()
            if k not in _VOLATILE_KEYS
        }
    if isinstance(obj, list):
        return [_strip_volatile(v) for v in obj]
    return obj


def compute_payload_digest(result: dict) -> str:
    """Deterministic SHA-256 over the result with volatile fields removed.

    Documented canonical payload hash: excludes wall-clock timestamps,
    environment-specific paths (source_db_path, connection_uri), and the
    self-hash field; serializes with sorted keys and compact separators. This is
    NOT a recursive full-file self-hash (see _VOLATILE_KEYS for the exact set).
    """
    payload = _strip_volatile(copy.deepcopy(result))
    canonical = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def render_markdown(result: dict) -> str:
    """Render the human-readable Markdown view from the one canonical result."""
    meta = result["meta"]
    prov = result["provenance"]
    lines = []
    lines.append("# P273A — Prize-Aware Observed-Counts Export")
    lines.append("")
    lines.append(
        "> **Read-only observed-counts artifact.** No random baseline, "
        "probability, p-value, correction, confidence interval, edge "
        "classification, or prediction-success claim is computed here. "
        "P273A inferential validation is a separate, future, separately "
        "authorized task."
    )
    lines.append("")
    lines.append("## Run metadata")
    lines.append("")
    lines.append(f"- task_id: `{meta['task_id']}`")
    lines.append(f"- artifact_version: `{meta['artifact_version']}`")
    lines.append(f"- scoring_version: `{meta['scoring_version']}`")
    lines.append(f"- adapter_version: `{meta['adapter_version']}`")
    lines.append(f"- generated_at: `{meta['generated_at']}`")
    lines.append(f"- frozen_strategy_cell_count: **{meta['frozen_strategy_cell_count']}**")
    lines.append(f"- lotteries: {', '.join(meta['lotteries'])}")
    lines.append(f"- windows: {', '.join(str(w) for w in meta['windows'])}")
    lines.append(
        f"- source_verification_status: `{meta['source_verification_status']}`"
    )
    lines.append("")
    lines.append("## Safety flags")
    lines.append("")
    for key in (
        "production_write", "services_controlled", "inference_performed",
        "edge_claim_made", "registry_mutation", "db_read_only",
    ):
        lines.append(f"- {key}: `{str(result['safety_flags'][key]).lower()}`")
    lines.append("")
    lines.append("## Provenance")
    lines.append("")
    lines.append(f"- source_db_path: `{prov['source_db_path']}`")
    lines.append(f"- db_open_mode: `{prov['db_open_mode']}`")
    lines.append(
        f"- query_only_enabled: "
        f"`{str(prov['query_only_evidence']['query_only_enabled']).lower()}`"
    )
    lines.append(
        f"- single_snapshot: `{str(prov['single_snapshot']).lower()}` "
        f"(one connection, one read transaction)"
    )
    lines.append(f"- schema user_version: `{prov['schema']['user_version']}`")
    lines.append(
        f"- schema_fingerprint_sha256: `{prov['schema']['schema_fingerprint_sha256']}`"
    )
    for label, key in (
        ("P271A spec", "p271a_json_sha256"),
        ("P267C artifact", "p267c_json_sha256"),
        ("P271C scorer src", "p271c_source_sha256"),
        ("P271E adapter src", "p271e_source_sha256"),
    ):
        lines.append(f"- {label} SHA-256: `{prov['source_hashes'][key]}`")
    lines.append(
        f"- canonical_payload_digest: `{result['canonical_payload_digest']}`"
    )
    lines.append("")
    lines.append("## Governed endpoint (verified against P271A)")
    lines.append("")
    lines.append("| lottery | endpoint_id | condition (committed) | min tier |")
    lines.append("|---|---|---|---|")
    for lt in LOTTERY_TYPES:
        ep = result["endpoint_definitions"][lt]
        lines.append(
            f"| {lt} | `{ep['endpoint_id']}` | "
            f"`{ep['committed_condition_sql']}` | {ep['min_qualifying_tier']} |"
        )
    lines.append("")
    lines.append("## Per-cell observed counts")
    lines.append("")
    lines.append(
        "| lottery | strategy_id | window | support_draws | "
        "observed_successes | success_rate | scoreable_rows | excluded_rows | "
        "excl_missing_special | bet_count(min..max) | latest..earliest |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|")
    for cell in result["cells"]:
        for w in cell["windows"]:
            rate = (
                f"{w['observed_success_rate']:.6f}"
                if w["observed_success_rate"] is not None else "—"
            )
            bc = (
                f"{w['bet_count_min']}..{w['bet_count_max']}"
                if w["bet_count_min"] is not None else "—"
            )
            span = (
                f"{w['latest_target_draw']}..{w['earliest_target_draw']}"
                if w["latest_target_draw"] is not None else "—"
            )
            lines.append(
                f"| {w['lottery_type']} | {w['strategy_id']} | {w['window']} | "
                f"{w['support_draws']} | {w['observed_successes']} | {rate} | "
                f"{w['scoreable_rows']} | {w['excluded_rows']} | "
                f"{w['excluded_missing_special_rows']} | {bc} | {span} |"
            )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_export(db_path: str = CANONICAL_DB_PATH,
               p267c_path: str = P267C_JSON_PATH,
               p271a_path: str = P271A_JSON_PATH,
               scorer_path: str = P271C_SOURCE_PATH,
               adapter_path: str = P271E_SOURCE_PATH) -> dict:
    """Run the full read-only export and return one canonical result dict.

    Owns exactly one mode=ro connection and one read transaction (one snapshot).
    Performs no inference and no write of any kind to the database.
    """
    frozen_cells = load_frozen_cells(p267c_path)
    committed_conditions = verify_endpoints_against_p271a(p271a_path)
    source_hashes = {
        "p271a_json_sha256": sha256_file(p271a_path),
        "p267c_json_sha256": sha256_file(p267c_path),
        "p271c_source_sha256": sha256_file(scorer_path),
        "p271e_source_sha256": sha256_file(adapter_path),
    }

    conn, query_only_evidence = open_readonly_connection(db_path)
    transaction_start_at = _now_iso()
    try:
        conn.execute("BEGIN")  # explicit read transaction -> one snapshot
        schema = verify_schema(conn)
        cells = [
            compute_cell(conn, c["lottery_type"], c["strategy_id"])
            for c in frozen_cells
        ]
        conn.execute("ROLLBACK")  # end read transaction; no write performed
    finally:
        conn.close()
    transaction_end_at = _now_iso()

    # Roll up exclusion totals (per lottery + grand total) for transparency.
    exclusion_totals = {lt: Counter() for lt in LOTTERY_TYPES}
    for cell in cells:
        lt = cell["lottery_type"]
        for w in cell["windows"]:
            exclusion_totals[lt].update(w["exclusion_by_reason"])
    exclusion_summary = {
        lt: dict(sorted(counter.items()))
        for lt, counter in exclusion_totals.items()
    }

    endpoint_definitions = {
        lt: {
            "endpoint_id": GOVERNED_ENDPOINT[lt]["endpoint_id"],
            "committed_condition_sql": committed_conditions[lt],
            "task_shorthand": GOVERNED_ENDPOINT[lt]["task_shorthand"],
            "min_qualifying_tier": GOVERNED_ENDPOINT[lt]["min_qualifying_tier"],
            "scored_by": "lottery_api.prize_aware_scorer.any_prize_aware_win",
        }
        for lt in LOTTERY_TYPES
    }

    result = {
        "meta": {
            "task_id": TASK_ID,
            "artifact_version": ARTIFACT_VERSION,
            "scoring_version": SCORING_VERSION,
            "adapter_version": ADAPTER_VERSION,
            "source_verification_status": SOURCE_VERIFICATION_STATUS,
            "generated_at": _now_iso(),
            "frozen_strategy_cell_count": len(frozen_cells),
            "lotteries": list(LOTTERY_TYPES),
            "windows": list(WINDOWS),
            "analysis_unit": "distinct target_draw (draw-level any-bet)",
        },
        "safety_flags": {
            "db_read_only": True,
            "production_write": False,
            "services_controlled": False,
            "inference_performed": False,
            "edge_claim_made": False,
            "registry_mutation": False,
            "baseline_computed": False,
            "p_value_computed": False,
            "second_zone_manufactured": False,
        },
        "provenance": {
            "source_db_path": db_path,
            "db_open_mode": DB_OPEN_MODE,
            "query_only_evidence": query_only_evidence,
            "single_snapshot": True,
            "single_connection": True,
            "transaction_start_at": transaction_start_at,
            "transaction_end_at": transaction_end_at,
            "permitted_tables": sorted(REQUIRED_COLUMNS.keys()),
            "normalized_cell_query": CELL_QUERY,
            "schema": schema,
            "source_hashes": source_hashes,
            "canonical_payload_digest_excludes": sorted(_VOLATILE_KEYS),
            "frozen_cells": frozen_cells,
        },
        "endpoint_definitions": endpoint_definitions,
        "windowing_semantics": {
            "selection": "most-recent N distinct target_draw, CAST(target_draw AS INTEGER) DESC",
            "support_rule": "a draw counts toward support only if >= 1 eligible scoreable bet remains",
            "success_rule": "draw success = any eligible bet is an any_prize_aware_win",
            "bet_count_scope": "distinct scoreable bet_index per supported draw",
            "power_exclusion": "POWER_LOTTO rows with NULL predicted_special excluded (never filled)",
            "dedupe_rule": "rows deduplicated by (target_draw, bet_index) to avoid pseudo-replication",
        },
        "exclusion_summary_by_lottery": exclusion_summary,
        "cells": cells,
    }
    result["canonical_payload_digest"] = compute_payload_digest(result)
    return result


def write_artifacts(result: dict, out_json: str, out_md: str) -> None:
    """Write the JSON and Markdown artifacts from the one canonical result."""
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(out_md, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(result))
        fh.write("\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="P273A read-only prize-aware observed-counts export"
    )
    parser.add_argument("--db", default=CANONICAL_DB_PATH,
                        help="path to the canonical SQLite DB (opened mode=ro)")
    parser.add_argument("--p267c", default=P267C_JSON_PATH)
    parser.add_argument("--p271a", default=P271A_JSON_PATH)
    parser.add_argument("--scorer-src", default=P271C_SOURCE_PATH)
    parser.add_argument("--adapter-src", default=P271E_SOURCE_PATH)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)

    result = run_export(
        db_path=args.db,
        p267c_path=args.p267c,
        p271a_path=args.p271a,
        scorer_path=args.scorer_src,
        adapter_path=args.adapter_src,
    )
    write_artifacts(result, args.out_json, args.out_md)
    print(json.dumps({
        "task_id": TASK_ID,
        "frozen_strategy_cell_count": result["meta"]["frozen_strategy_cell_count"],
        "canonical_payload_digest": result["canonical_payload_digest"],
        "out_json": args.out_json,
        "out_md": args.out_md,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
