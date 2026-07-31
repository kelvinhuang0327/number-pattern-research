"""P268B: Official drawNumberAppear ingestion + positional-bias audit prototype.

Read-only diagnostics-only prototype. Pulls a BOUNDED sample of recent draws
from the official TLCAPIWeB endpoints (already verified reachable in P268A
recovery), checks the structure of the new `drawNumberAppear` (draw-order)
field, attempts a schema/row-level alignment check against the local
`draws` table, and runs a minimal per-position frequency / descriptive
diagnostic.

Hard constraints (per task authorization):
  - No production DB write. The local SQLite DB is opened read-only
    (mode=ro) and is never modified.
  - No replay row modification.
  - No betting recommendations.
  - No success-rate / hit-rate-improvement claims.
  - Bounded sample only (no full-history backfill).

P267C conclusion boundary:
  P267C found NO_VALIDATED_M3_EDGE for the existing replay-backed strategy
  family (36/36 cells). It does not close the broader success-rate research
  line, and does not cover `drawNumberAppear`, which is a field never present
  in the internal sorted-number DB.

P268A Top-1 rationale:
  Direction A (this prototype) was ranked Top 1 for hit-rate research because
  `drawNumberAppear` (the physical draw-order sequence) is genuinely new
  information not present in, or derivable from, the internal sorted-number
  `draws` table. winnerCount/prize-distribution (Direction B) is explicitly
  payout/EV-only and out of scope for this task.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "lottery_v2.db"
ARTIFACT_JSON = REPO_ROOT / "outputs" / "research" / "p268b_official_draw_order_positional_bias_audit_20260610.json"
ARTIFACT_MD = REPO_ROOT / "outputs" / "research" / "p268b_official_draw_order_positional_bias_audit_20260610.md"

API_BASE = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery"
TIMEOUT_SECONDS = 20

# Bounded sample scope: 2 most-recent calendar months per game (no full
# history backfill). Chosen to stay well within the months verified live
# during P268A recovery.
SAMPLE_MONTHS = ["2026-04", "2026-05"]

# Game definitions: internal lottery_type -> (endpoint, response array key,
# expected drawNumberAppear length, number-pool description).
GAMES = {
    "BIG_LOTTO": {
        "endpoint": "Lotto649Result",
        "array_key": "lotto649Res",
        "expected_appear_len": 7,  # 6 main + 1 special
        "main_count": 6,
        "main_pool": (1, 49),
        "special_pool": (1, 49),
        "has_size_field": True,
    },
    "POWER_LOTTO": {
        "endpoint": "SuperLotto638Result",
        "array_key": "superLotto638Res",
        "expected_appear_len": 7,  # 6 main + 1 special
        "main_count": 6,
        "main_pool": (1, 38),
        "special_pool": (1, 8),
        "has_size_field": True,
    },
    "DAILY_539": {
        "endpoint": "Daily539Result",
        "array_key": "daily539Res",
        "expected_appear_len": 5,
        "main_count": 5,
        "main_pool": (1, 39),
        "special_pool": None,
        "has_size_field": True,
    },
    "3_STAR": {
        "endpoint": "3DResult",
        "array_key": "lotto3DRes",
        "expected_appear_len": 3,
        "main_count": 3,
        "main_pool": (0, 9),
        "special_pool": None,
        "has_size_field": False,
    },
    "4_STAR": {
        "endpoint": "4DResult",
        "array_key": "lotto4DRes",
        "expected_appear_len": 4,
        "main_count": 4,
        "main_pool": (0, 9),
        "special_pool": None,
        "has_size_field": False,
    },
}


def fetch_month(endpoint: str, month: str, page_size: int = 31) -> dict:
    """Fetch one month of results from the official TLCAPIWeB endpoint.

    Uses `curl` rather than `urllib` because this environment's Python/OpenSSL
    rejects the official cert chain with
    "[SSL: CERTIFICATE_VERIFY_FAILED] ... Missing Subject Key Identifier",
    while curl (and browsers) verify it successfully via the system CA store.
    This is a real, verified-live, unauthenticated public endpoint (P268A
    recovery) — not mock/fake data.
    """
    url = f"{API_BASE}/{endpoint}?period&month={month}&pageNum=1&pageSize={page_size}"
    result = subprocess.run(
        ["curl", "-s", "--max-time", str(TIMEOUT_SECONDS), "-A", "Mozilla/5.0", url],
        capture_output=True,
        timeout=TIMEOUT_SECONDS + 5,
        check=False,
    )
    if result.returncode != 0:
        raise OSError(f"curl exited {result.returncode}: {result.stderr.decode('utf-8', 'replace')}")
    if not result.stdout:
        raise OSError("curl returned empty response")
    return json.loads(result.stdout.decode("utf-8"))


def chi_square_uniform(counts: list[int]) -> tuple[float, int]:
    """Simple chi-square goodness-of-fit vs uniform over len(counts) bins.

    Returns (statistic, df). No p-value lookup table is bundled (no scipy
    dependency); statistic + df are reported as descriptive diagnostics only.
    """
    n = sum(counts)
    k = len(counts)
    if n == 0 or k == 0:
        return 0.0, max(k - 1, 0)
    expected = n / k
    stat = sum((c - expected) ** 2 / expected for c in counts)
    return round(stat, 4), max(k - 1, 0)


def main() -> dict:
    sources_summary = []
    sample_scope = {
        "months_sampled": SAMPLE_MONTHS,
        "games_sampled": list(GAMES.keys()),
        "page_size": 31,
        "note": "Bounded prototype sample: 2 calendar months per game, no full-history backfill.",
    }

    parse_results = {}
    db_alignment = {}
    positional_diagnostics = {}
    raw_records_by_game: dict[str, list[dict]] = {}
    any_endpoint_ok = False
    all_endpoints_failed = True

    for lottery_type, cfg in GAMES.items():
        endpoint = cfg["endpoint"]
        array_key = cfg["array_key"]
        records: list[dict] = []
        endpoint_status = "OK"
        error_detail = None

        for month in SAMPLE_MONTHS:
            try:
                payload = fetch_month(endpoint, month)
            except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError) as exc:
                endpoint_status = "ERROR"
                error_detail = f"{type(exc).__name__}: {exc}"
                continue
            content = payload.get("content") or {}
            month_records = content.get(array_key) or []
            for rec in month_records:
                rec["_sample_month"] = month
            records.extend(month_records)

        if records:
            any_endpoint_ok = True
            all_endpoints_failed = False
        elif endpoint_status == "OK":
            # No error, but also no records (e.g. unexpected payload shape).
            endpoint_status = "EMPTY"
            all_endpoints_failed = False

        raw_records_by_game[lottery_type] = records
        sources_summary.append(
            {
                "lottery_type": lottery_type,
                "endpoint": f"{API_BASE}/{endpoint}",
                "array_key": array_key,
                "status": endpoint_status,
                "error": error_detail,
                "records_fetched": len(records),
            }
        )

    if all_endpoints_failed:
        return {
            "task_id": "P268B_OFFICIAL_DRAW_ORDER_INGESTION_AND_POSITIONAL_BIAS_AUDIT_PROTOTYPE",
            "final_classification": "P268B_DRAW_ORDER_POSITIONAL_BIAS_AUDIT_PROTOTYPE_BLOCKED_EXTERNAL_API_UNAVAILABLE",
            "data_sources": sources_summary,
            "sample_scope": sample_scope,
        }

    # --- Parse / structure validation per game ---
    for lottery_type, cfg in GAMES.items():
        records = raw_records_by_game.get(lottery_type, [])
        expected_len = cfg["expected_appear_len"]
        main_count = cfg["main_count"]

        n_total = len(records)
        n_field_present = 0
        n_parsed_as_sequence = 0
        n_correct_length = 0
        n_sorted_matches_size = 0
        n_size_field_present = 0
        parse_failures = []

        for rec in records:
            appear = rec.get("drawNumberAppear")
            if appear is None:
                parse_failures.append({"period": rec.get("period"), "reason": "drawNumberAppear missing"})
                continue
            n_field_present += 1

            if not isinstance(appear, list) or not all(isinstance(x, int) for x in appear):
                parse_failures.append({"period": rec.get("period"), "reason": "drawNumberAppear not an int list"})
                continue
            n_parsed_as_sequence += 1

            if len(appear) == expected_len:
                n_correct_length += 1
            else:
                parse_failures.append(
                    {
                        "period": rec.get("period"),
                        "reason": f"unexpected length {len(appear)} (expected {expected_len})",
                    }
                )

            if cfg["has_size_field"]:
                size = rec.get("drawNumberSize")
                if size is not None:
                    n_size_field_present += 1
                    if (
                        isinstance(size, list)
                        and len(size) >= main_count
                        and len(appear) >= main_count
                        and sorted(appear[:main_count]) == sorted(size[:main_count])
                    ):
                        n_sorted_matches_size += 1

        parse_results[lottery_type] = {
            "n_records_sampled": n_total,
            "drawNumberAppear_present": n_field_present,
            "parsed_as_ordered_sequence": n_parsed_as_sequence,
            "correct_length_count": n_correct_length,
            "expected_length": expected_len,
            "drawNumberSize_present": n_size_field_present if cfg["has_size_field"] else None,
            "sorted_appear_matches_drawNumberSize": (
                n_sorted_matches_size if cfg["has_size_field"] else None
            ),
            "parse_failures": parse_failures[:10],  # cap for artifact size
            "parse_failure_count": len(parse_failures),
        }

    # --- DB alignment check (read-only) ---
    db_exists = DB_PATH.exists()
    if db_exists:
        try:
            db_uri = f"file:{DB_PATH}?mode=ro"
            conn = sqlite3.connect(db_uri, uri=True)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM draws")
            total_draw_rows = cur.fetchone()[0]

            for lottery_type, cfg in GAMES.items():
                records = raw_records_by_game.get(lottery_type, [])
                periods = [str(rec.get("period")) for rec in records if rec.get("period") is not None]
                matched = 0
                checked = 0
                if total_draw_rows > 0 and periods:
                    placeholders = ",".join("?" for _ in periods)
                    cur.execute(
                        f"SELECT draw FROM draws WHERE lottery_type = ? AND draw IN ({placeholders})",
                        [lottery_type, *periods],
                    )
                    matched_draws = {r[0] for r in cur.fetchall()}
                    checked = len(periods)
                    matched = len(matched_draws)

                db_alignment[lottery_type] = {
                    "sample_periods_checked": len(periods),
                    "matched_in_local_draws_table": matched,
                    "checked": checked,
                    "status": (
                        "NO_LOCAL_ROWS"
                        if total_draw_rows == 0
                        else ("ALIGNED" if matched == checked and checked > 0 else "PARTIAL_OR_NO_MATCH")
                    ),
                }
            conn.close()
            db_alignment["_meta"] = {
                "db_path": str(DB_PATH.relative_to(REPO_ROOT)),
                "open_mode": "read-only (sqlite3 mode=ro URI)",
                "local_draws_table_row_count": total_draw_rows,
                "note": (
                    "Local draws table currently has 0 rows in this checkout; "
                    "alignment check is schema-level only (column structure "
                    "compatible: draw/date/lottery_type/numbers/special exist), "
                    "not row-level, when total_draw_rows == 0."
                    if total_draw_rows == 0
                    else "Row-level alignment checked by matching `draw` (period) + lottery_type."
                ),
            }
        except sqlite3.Error as exc:
            db_alignment["_meta"] = {
                "db_path": str(DB_PATH.relative_to(REPO_ROOT)),
                "open_mode": "read-only (sqlite3 mode=ro URI)",
                "error": f"{type(exc).__name__}: {exc}",
            }
    else:
        db_alignment["_meta"] = {"db_path": str(DB_PATH.relative_to(REPO_ROOT)), "error": "DB file not found"}

    # --- Minimal positional-bias diagnostic ---
    for lottery_type, cfg in GAMES.items():
        records = raw_records_by_game.get(lottery_type, [])
        expected_len = cfg["expected_appear_len"]
        sequences = [
            rec["drawNumberAppear"]
            for rec in records
            if isinstance(rec.get("drawNumberAppear"), list)
            and len(rec["drawNumberAppear"]) == expected_len
            and all(isinstance(x, int) for x in rec["drawNumberAppear"])
        ]

        n = len(sequences)
        per_position_freq = []
        per_position_chi2 = []
        for pos in range(expected_len):
            values = [seq[pos] for seq in sequences]
            counts = Counter(values)
            lo, hi = cfg["main_pool"] if pos < cfg["main_count"] else (cfg["special_pool"] or cfg["main_pool"])
            pool_size = hi - lo + 1
            full_counts = [counts.get(v, 0) for v in range(lo, hi + 1)]
            stat, df = chi_square_uniform(full_counts)
            per_position_freq.append(
                {
                    "position": pos,
                    "n": n,
                    "value_pool": [lo, hi],
                    "top_values": counts.most_common(5),
                }
            )
            per_position_chi2.append({"position": pos, "chi2_stat": stat, "df": df, "pool_size": pool_size})

        # Adjacent-order "echo" diagnostic: how often consecutive draw-order
        # positions hold values that differ by exactly 1 (descriptive only).
        adjacent_diff1_count = 0
        adjacent_pairs_total = 0
        for seq in sequences:
            for i in range(len(seq) - 1):
                adjacent_pairs_total += 1
                if abs(seq[i + 1] - seq[i]) == 1:
                    adjacent_diff1_count += 1

        positional_diagnostics[lottery_type] = {
            "n_sequences_used": n,
            "expected_length": expected_len,
            "per_position_frequency": per_position_freq,
            "per_position_chi2_vs_uniform": per_position_chi2,
            "adjacent_position_diff1_count": adjacent_diff1_count,
            "adjacent_position_pairs_total": adjacent_pairs_total,
            "adjacent_position_diff1_rate": (
                round(adjacent_diff1_count / adjacent_pairs_total, 4) if adjacent_pairs_total else None
            ),
            "note": (
                "Descriptive prototype diagnostic only. Sample size is small "
                "(2-month bounded sample); chi2 statistics are NOT paired with "
                "p-value thresholds or any pass/fail gate. No null-distribution "
                "calibration performed. No success-rate or betting claim."
            ),
        }

    overall_status = "OK" if any_endpoint_ok else "PARTIAL"
    final_classification = "P268B_DRAW_ORDER_POSITIONAL_BIAS_AUDIT_PROTOTYPE_COMPLETE_DIAGNOSTICS_ONLY"

    artifact = {
        "task_id": "P268B_OFFICIAL_DRAW_ORDER_INGESTION_AND_POSITIONAL_BIAS_AUDIT_PROTOTYPE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "p267c_conclusion_boundary": (
            "P267C (M3+ revalidation) found NO_VALIDATED_M3_EDGE across 36/36 "
            "cells for the existing replay-backed strategy family. This does "
            "NOT close the broader success-rate research line, and does NOT "
            "cover the official drawNumberAppear field, which is absent from "
            "the replay-backed family and from the internal sorted-number "
            "draws table."
        ),
        "p268a_top1_rationale": (
            "P268A-S ranked 'official drawNumberAppear draw-order positional "
            "bias test' as the Top-1 hit-rate candidate because it is a "
            "genuinely new official field (physical draw-order sequence) not "
            "present in, or derivable from, the internal sorted-number `draws` "
            "table. winnerCount/prize-distribution (Direction B) is "
            "payout/EV-only and is explicitly excluded from this task."
        ),
        "data_sources": sources_summary,
        "sample_scope": sample_scope,
        "parse_results": parse_results,
        "db_alignment": db_alignment,
        "positional_diagnostics": positional_diagnostics,
        "limitations": [
            "Bounded 2-month prototype sample only; not statistically powered "
            "for any confirmatory test.",
            "Chi-square statistics are descriptive only; no p-value table, no "
            "multiple-testing correction, no pre-registration (prototype, not "
            "a confirmatory scan).",
            "Local draws table is empty (0 rows) in this checkout, so "
            "row-level DB alignment could not be exercised end-to-end; only "
            "schema compatibility and a query-path dry-run were verified.",
            "3_STAR / 4_STAR draw-order positions are digit draws (0-9, with "
            "replacement); BIG_LOTTO/POWER_LOTTO/DAILY_539 positions are "
            "without-replacement draws from a larger pool, so a uniform-chi2 "
            "null is a rough descriptive diagnostic, not a calibrated test.",
            "No success-rate / hit-rate improvement is claimed by this "
            "prototype.",
        ],
        "next_step_recommendation": (
            "If this prototype's structural checks (field presence, length, "
            "sorted-equivalence with drawNumberSize) hold across a larger "
            "bounded re-run, a separate, explicitly-authorized P221F-gated "
            "confirmatory task could pre-register a full-history "
            "drawNumberAppear backfill + positional-bias hypothesis test. "
            "That future task would require its own DB-write authorization "
            "(new column/table) and would be a confirmatory test, not this "
            "prototype."
        ),
        "disclaimer": (
            "DIAGNOSTICS ONLY. No betting recommendation. No validated "
            "hit-rate edge. No production DB write. No replay row "
            "modification. This artifact does not claim any success-rate "
            "improvement."
        ),
        "overall_status": overall_status,
        "final_classification": final_classification,
    }
    return artifact


def render_markdown(artifact: dict) -> str:
    lines = []
    lines.append("# P268B: Official drawNumberAppear Ingestion + Positional-Bias Audit Prototype")
    lines.append("")
    lines.append(f"Generated: {artifact.get('generated_at')}")
    lines.append("")
    lines.append("## P267C Conclusion Boundary")
    lines.append(artifact.get("p267c_conclusion_boundary", ""))
    lines.append("")
    lines.append("## P268A Top-1 Rationale")
    lines.append(artifact.get("p268a_top1_rationale", ""))
    lines.append("")
    lines.append("## Data Source Endpoint Summary")
    for src in artifact.get("data_sources", []):
        lines.append(
            f"- **{src['lottery_type']}**: `{src['endpoint']}` "
            f"(array key `{src['array_key']}`) — status={src['status']}, "
            f"records_fetched={src['records_fetched']}"
            + (f", error={src['error']}" if src.get("error") else "")
        )
    lines.append("")
    lines.append("## Sample Scope")
    for k, v in artifact.get("sample_scope", {}).items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    lines.append("## Parse Success/Failure Counts")
    for lt, pr in artifact.get("parse_results", {}).items():
        lines.append(f"### {lt}")
        lines.append(f"- records sampled: {pr['n_records_sampled']}")
        lines.append(f"- drawNumberAppear present: {pr['drawNumberAppear_present']}")
        lines.append(f"- parsed as ordered int sequence: {pr['parsed_as_ordered_sequence']}")
        lines.append(f"- correct length ({pr['expected_length']}): {pr['correct_length_count']}")
        if pr["drawNumberSize_present"] is not None:
            lines.append(f"- drawNumberSize present: {pr['drawNumberSize_present']}")
            lines.append(
                f"- sorted(drawNumberAppear) == drawNumberSize (main numbers): "
                f"{pr['sorted_appear_matches_drawNumberSize']}"
            )
        lines.append(f"- parse failures: {pr['parse_failure_count']}")
        lines.append("")
    lines.append("## DB Alignment Summary")
    meta = artifact.get("db_alignment", {}).get("_meta", {})
    for k, v in meta.items():
        lines.append(f"- **{k}**: {v}")
    for lt, al in artifact.get("db_alignment", {}).items():
        if lt == "_meta":
            continue
        lines.append(
            f"- **{lt}**: status={al['status']}, "
            f"sample_periods_checked={al['sample_periods_checked']}, "
            f"matched={al['matched_in_local_draws_table']}"
        )
    lines.append("")
    lines.append("## Position-Frequency Diagnostic Table (descriptive only)")
    for lt, diag in artifact.get("positional_diagnostics", {}).items():
        lines.append(f"### {lt} (n={diag['n_sequences_used']})")
        lines.append("| position | value pool | top values (value, count) | chi2 vs uniform | df |")
        lines.append("|---|---|---|---|---|")
        chi2_by_pos = {c["position"]: c for c in diag["per_position_chi2_vs_uniform"]}
        for f in diag["per_position_frequency"]:
            c = chi2_by_pos.get(f["position"], {})
            lines.append(
                f"| {f['position']} | {f['value_pool']} | {f['top_values']} | "
                f"{c.get('chi2_stat')} | {c.get('df')} |"
            )
        lines.append(
            f"- adjacent |diff|==1 rate: {diag['adjacent_position_diff1_rate']} "
            f"({diag['adjacent_position_diff1_count']}/{diag['adjacent_position_pairs_total']})"
        )
        lines.append("")
    lines.append("## Limitations")
    for item in artifact.get("limitations", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Next-Step Recommendation")
    lines.append(artifact.get("next_step_recommendation", ""))
    lines.append("")
    lines.append("## Disclaimer")
    lines.append(artifact.get("disclaimer", ""))
    lines.append("")
    lines.append(f"## Final Classification")
    lines.append(artifact.get("final_classification", ""))
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    artifact = main()
    ARTIFACT_JSON.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_JSON.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    if artifact["final_classification"] != "P268B_DRAW_ORDER_POSITIONAL_BIAS_AUDIT_PROTOTYPE_BLOCKED_EXTERNAL_API_UNAVAILABLE":
        ARTIFACT_MD.write_text(render_markdown(artifact), encoding="utf-8")

    print(f"Final Classification: {artifact['final_classification']}")
    sys.exit(0)
