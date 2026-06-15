"""P273A distinct-ticket identity export.

This additive, import-safe module produces identity evidence for the frozen
50/300/750 prize-aware analysis. It opens the production database only through
SQLite URI ``mode=ro``, verifies ``PRAGMA query_only=ON``, uses one connection
and one explicit read transaction, and reads only
``strategy_prediction_replays`` and ``draws``.

The export contains canonical ticket contents and their fingerprints. It does
not compute a random baseline, expected successes, confidence intervals,
p-values, corrections, stability, EDGE/NULL decisions, GO recommendations, or
production decisions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Tuple

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from analysis.p273a_primary_window_observed_counts_export import (  # noqa: E402
    CORRECTION_FAMILY_PLANNED,
    PRIMARY_WINDOW_LABELS,
    PRIMARY_WINDOWS,
)
from analysis.p273a_prizeaware_replay_export import (  # noqa: E402
    ADAPTER_VERSION,
    CELL_QUERY,
    DB_OPEN_MODE,
    EXPECTED_FROZEN_CELL_COUNT,
    GOVERNED_ENDPOINT,
    LOTTERY_TYPES,
    P267C_JSON_PATH,
    P271A_JSON_PATH,
    P271C_SOURCE_PATH,
    P271E_SOURCE_PATH,
    SCORING_VERSION,
    SOURCE_VERIFICATION_STATUS,
    _VOLATILE_KEYS,
    _now_iso,
    _row_dict,
    compute_payload_digest,
    load_frozen_cells,
    open_readonly_connection,
    sha256_file,
    verify_endpoints_against_p271a,
    verify_schema,
)
from lottery_api.prize_aware_replay_adapter import (  # noqa: E402
    EXCLUSION_MISSING_PREDICTED_SECOND_ZONE,
    _check_eligibility,
    _parse_number_list,
)

TASK_ID = "P273A_DISTINCT_TICKET_IDENTITY_READONLY_EXPORT"
ARTIFACT_VERSION = "p273a_distinct_ticket_identity_v1"
SOURCE_MAIN_COMMIT = "6b264e7054a2ae793b12a7279cb0a9706c41f174"
PRIMARY_EXPORT_COMMIT = "a144bb0ed5a42e985b5acb84e53471ecb725e47e"
REFERENCE_EXPORT_COMMIT = "445587e0147cab8af54594aa0cfa5fe83f0353fa"
TASK_BRANCH = "task/p273a-distinct-ticket-identity-export"

PRODUCTION_DB_PATH = (
    "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db"
)
PRIMARY_ARTIFACT_PATH = (
    "outputs/research/p273a_primary_window_observed_counts_20260615.json"
)
PRIMARY_RAW_SHA256 = (
    "14b2ed29628111f32925909ba07e9be0b3de48a04ee4b0877e39c1dfa4e51b73"
)
PRIMARY_CANONICAL_DIGEST = (
    "65a4cc59f5ab64d685890566e38493b0295e622f351e0527782f1dce2f38645f"
)
REFERENCE_ARTIFACT_PATH = (
    "outputs/research/p273a_prizeaware_observed_counts_20260614.json"
)
REFERENCE_RAW_SHA256 = (
    "ee5cc98a4c0b673e1172d4478e72bced50167e7f206acf25fe170eee0ece7bd9"
)
REFERENCE_CANONICAL_DIGEST = (
    "859c3889f2c698a27d16caf4195bbd0fd032cad80d8c44e990958658624b3103"
)

DEFAULT_OUT_JSON = (
    "outputs/research/p273a_distinct_ticket_identity_20260615.json"
)
DEFAULT_OUT_MD = (
    "outputs/research/p273a_distinct_ticket_identity_20260615.md"
)
IDENTITY_EXPORT_SOURCE_PATH = (
    "analysis/p273a_distinct_ticket_identity_export.py"
)
PRIMARY_EXPORT_SOURCE_PATH = (
    "analysis/p273a_primary_window_observed_counts_export.py"
)
REPLAY_EXPORT_SOURCE_PATH = "analysis/p273a_prizeaware_replay_export.py"


class IdentityExportError(RuntimeError):
    """Base fail-closed error for the identity export."""


class TicketContentError(IdentityExportError):
    """A ticket cannot be represented under the committed parser contract."""


class BetIndexContentConflict(IdentityExportError):
    """One bet_index maps to more than one eligible canonical ticket."""


class IdentityArtifactAlignmentError(IdentityExportError):
    """Computed identity aggregates disagree with the immutable source artifact."""


def verify_source_artifact(
    path: str, expected_raw_sha256: str, expected_canonical_digest: str
) -> dict:
    """Verify complete-file and canonical-payload identity for one JSON artifact."""
    raw_sha = sha256_file(path)
    if raw_sha != expected_raw_sha256:
        raise IdentityExportError(
            f"raw SHA-256 mismatch for {path}: {raw_sha} != {expected_raw_sha256}"
        )
    with open(path, "r", encoding="utf-8") as fh:
        artifact = json.load(fh)
    canonical = compute_payload_digest(artifact)
    embedded = artifact.get("canonical_payload_digest")
    if embedded != canonical:
        raise IdentityExportError(
            f"embedded canonical digest mismatch for {path}: "
            f"{embedded} != {canonical}"
        )
    if canonical != expected_canonical_digest:
        raise IdentityExportError(
            f"canonical digest mismatch for {path}: "
            f"{canonical} != {expected_canonical_digest}"
        )
    return {
        "path": path,
        "raw_sha256": raw_sha,
        "canonical_payload_digest": canonical,
        "artifact": artifact,
    }


def _canonical_ticket_content(row: dict) -> dict:
    """Return the governed normalized player-selected ticket content.

    The row must already have passed the committed adapter's eligibility check.
    Main numbers are parsed with the committed parser and sorted ascending.
    BIG_LOTTO's drawn special number is deliberately excluded. POWER_LOTTO's
    stored predicted second-zone number is included.
    """
    lottery = row["lottery_type"]
    try:
        main_numbers = sorted(_parse_number_list(row["predicted_numbers"]))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise TicketContentError(
            f"unable to parse predicted ticket content for {lottery}"
        ) from exc

    expected = 5 if lottery == "DAILY_539" else 6
    upper = {
        "DAILY_539": 39,
        "BIG_LOTTO": 49,
        "POWER_LOTTO": 38,
    }.get(lottery)
    if upper is None:
        raise TicketContentError(f"unsupported lottery type: {lottery!r}")
    if (
        len(main_numbers) != expected
        or len(set(main_numbers)) != expected
        or any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 1
            or value > upper
            for value in main_numbers
        )
    ):
        raise TicketContentError(
            f"invalid canonical main-number content for {lottery}: {main_numbers!r}"
        )

    content = {"main_numbers": main_numbers}
    if lottery == "POWER_LOTTO":
        second_zone = row.get("predicted_special")
        if (
            isinstance(second_zone, bool)
            or not isinstance(second_zone, int)
            or not 1 <= second_zone <= 8
        ):
            raise TicketContentError(
                "POWER_LOTTO canonical identity requires predicted_special 1-8"
            )
        content["predicted_second_zone"] = second_zone
    return content


def canonical_ticket_serialization(content: dict) -> str:
    """Stable compact JSON representation used for identity fingerprints."""
    return json.dumps(
        content, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def canonical_ticket_fingerprint(content: dict) -> str:
    blob = canonical_ticket_serialization(content).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def normalize_ticket_identity(row: dict) -> dict:
    """Validate scoreability and return content, serialization and fingerprint."""
    eligible, reason = _check_eligibility(row)
    if not eligible:
        raise TicketContentError(f"row is not scoreable: {reason}")
    content = _canonical_ticket_content(row)
    return {
        "canonical_ticket_content": content,
        "canonical_serialization": canonical_ticket_serialization(content),
        "fingerprint_sha256": canonical_ticket_fingerprint(content),
    }


def _group_rows_by_bet_index(rows: Iterable[tuple]) -> Tuple[List[str], dict]:
    """Group query rows while preserving committed CAST-DESC draw ordering."""
    draw_order: List[str] = []
    seen_draws = set()
    grouped: dict = defaultdict(lambda: defaultdict(list))
    for raw in rows:
        row = _row_dict(raw)
        draw = row["target_draw"]
        if draw not in seen_draws:
            seen_draws.add(draw)
            draw_order.append(draw)
        grouped[draw][row["bet_index"]].append(row)
    return draw_order, grouped


def process_cell_rows(rows: Iterable[tuple], lottery: str, strategy: str) -> dict:
    """Resolve per-bet-index rows and deduplicate cross-index ticket content."""
    draw_order, grouped = _group_rows_by_bet_index(rows)
    draw_summaries = {}
    duplicate_rows_collapsed = 0

    for draw in draw_order:
        eligible_by_index = {}
        exclusion_by_reason = Counter()
        excluded_rows = 0
        for bet_index, candidates in grouped[draw].items():
            identities = {}
            ineligible_reasons = []
            for row in candidates:
                eligible, reason = _check_eligibility(row)
                if eligible:
                    ident = normalize_ticket_identity(row)
                    identities[ident["canonical_serialization"]] = ident
                else:
                    ineligible_reasons.append(reason or "UNKNOWN_EXCLUSION")

            if len(identities) > 1:
                raise BetIndexContentConflict(
                    f"{lottery}/{strategy}/{draw}/bet_index={bet_index} maps "
                    f"to {len(identities)} eligible canonical tickets"
                )
            if identities:
                eligible_by_index[int(bet_index)] = next(iter(identities.values()))
                duplicate_rows_collapsed += max(0, len(candidates) - 1)
            else:
                # The committed exporter resolves duplicate rows by bet_index
                # before aggregation. Count a fully excluded bet_index once.
                reason = sorted(ineligible_reasons)[0]
                exclusion_by_reason[reason] += 1
                excluded_rows += 1
                duplicate_rows_collapsed += max(0, len(candidates) - 1)

        by_serialization = defaultdict(list)
        identities_by_serialization = {}
        for bet_index, ident in eligible_by_index.items():
            key = ident["canonical_serialization"]
            by_serialization[key].append(bet_index)
            identities_by_serialization[key] = ident

        canonical_groups = []
        for key in sorted(by_serialization):
            bet_indexes = sorted(by_serialization[key])
            ident = identities_by_serialization[key]
            canonical_groups.append(
                {
                    "canonical_ticket_content": ident[
                        "canonical_ticket_content"
                    ],
                    "fingerprint_sha256": ident["fingerprint_sha256"],
                    "bet_index_values": bet_indexes,
                    "group_multiplicity": len(bet_indexes),
                }
            )

        eligible_count = len(eligible_by_index)
        distinct_count = len(canonical_groups)
        draw_summaries[draw] = {
            "lottery_type": lottery,
            "strategy_id": strategy,
            "target_draw": draw,
            "eligible_bet_index_count": eligible_count,
            "distinct_ticket_count": distinct_count,
            "duplicate_ticket_count": eligible_count - distinct_count,
            "excluded_rows": excluded_rows,
            "excluded_missing_special_rows": exclusion_by_reason.get(
                EXCLUSION_MISSING_PREDICTED_SECOND_ZONE, 0
            ),
            "exclusion_by_reason": dict(sorted(exclusion_by_reason.items())),
            "canonical_ticket_groups": canonical_groups,
        }

    return {
        "distinct_draws_desc": draw_order,
        "draw_summaries": draw_summaries,
        "same_bet_index_duplicate_rows_collapsed": duplicate_rows_collapsed,
    }


def _distribution(values: Iterable[int]) -> dict:
    return {str(k): v for k, v in sorted(Counter(values).items())}


def aggregate_identity_window(
    processed: dict,
    window: int,
    lottery: str,
    strategy: str,
) -> dict:
    """Aggregate identity evidence using the committed primary-window selection."""
    window_draws = processed["distinct_draws_desc"][:window]
    summaries = [processed["draw_summaries"][draw] for draw in window_draws]
    supported = [rec for rec in summaries if rec["eligible_bet_index_count"] >= 1]
    exclusion_by_reason = Counter()
    for rec in summaries:
        exclusion_by_reason.update(rec["exclusion_by_reason"])

    draw_ints = [int(draw) for draw in window_draws]
    return {
        "lottery_type": lottery,
        "strategy_id": strategy,
        "window": window,
        "window_label": PRIMARY_WINDOW_LABELS[window],
        "requested_window": window,
        "distinct_draws_in_window": len(window_draws),
        "support_draws": len(supported),
        "eligible_bet_index_count_distribution": _distribution(
            rec["eligible_bet_index_count"] for rec in supported
        ),
        "distinct_ticket_count_distribution": _distribution(
            rec["distinct_ticket_count"] for rec in supported
        ),
        "duplicate_content_draw_count": sum(
            rec["duplicate_ticket_count"] > 0 for rec in supported
        ),
        "total_duplicate_ticket_content_count": sum(
            rec["duplicate_ticket_count"] for rec in supported
        ),
        "excluded_rows": sum(rec["excluded_rows"] for rec in summaries),
        "excluded_missing_special_rows": exclusion_by_reason.get(
            EXCLUSION_MISSING_PREDICTED_SECOND_ZONE, 0
        ),
        "exclusion_by_reason": dict(sorted(exclusion_by_reason.items())),
        "latest_target_draw": str(max(draw_ints)) if draw_ints else None,
        "earliest_target_draw": str(min(draw_ints)) if draw_ints else None,
    }


def _observed_index(primary_artifact: dict) -> dict:
    cells = primary_artifact.get("cells")
    if not isinstance(cells, list) or len(cells) != EXPECTED_FROZEN_CELL_COUNT:
        raise IdentityArtifactAlignmentError(
            f"primary artifact must contain {EXPECTED_FROZEN_CELL_COUNT} cells"
        )
    result = {}
    for cell in cells:
        key = (cell["lottery_type"], cell["strategy_id"])
        windows = cell.get("windows")
        if [w.get("window") for w in windows or []] != list(PRIMARY_WINDOWS):
            raise IdentityArtifactAlignmentError(
                f"primary windows mismatch for {key}: "
                f"{[w.get('window') for w in windows or []]}"
            )
        result[key] = {int(w["window"]): w for w in windows}
    if len(result) != EXPECTED_FROZEN_CELL_COUNT:
        raise IdentityArtifactAlignmentError("primary artifact has duplicate cells")
    return result


def verify_window_alignment(identity_window: dict, observed_window: dict) -> dict:
    """Require identity aggregates to reproduce every immutable count invariant."""
    pairs = {
        "support_draws": (
            identity_window["support_draws"],
            observed_window["support_draws"],
        ),
        "eligible_bet_index_count_distribution": (
            identity_window["eligible_bet_index_count_distribution"],
            observed_window["bet_count_distribution"],
        ),
        "latest_target_draw": (
            identity_window["latest_target_draw"],
            observed_window["latest_target_draw"],
        ),
        "earliest_target_draw": (
            identity_window["earliest_target_draw"],
            observed_window["earliest_target_draw"],
        ),
        "distinct_draws_in_window": (
            identity_window["distinct_draws_in_window"],
            observed_window["distinct_draws_in_window"],
        ),
        "excluded_rows": (
            identity_window["excluded_rows"],
            observed_window["excluded_rows"],
        ),
        "excluded_missing_special_rows": (
            identity_window["excluded_missing_special_rows"],
            observed_window["excluded_missing_special_rows"],
        ),
        "exclusion_by_reason": (
            identity_window["exclusion_by_reason"],
            observed_window["exclusion_by_reason"],
        ),
    }
    mismatches = {
        name: {"identity": actual, "observed": expected}
        for name, (actual, expected) in pairs.items()
        if actual != expected
    }
    if mismatches:
        raise IdentityArtifactAlignmentError(
            f"identity/observed alignment mismatch for "
            f"{identity_window['lottery_type']}/"
            f"{identity_window['strategy_id']}/w{identity_window['window']}: "
            f"{mismatches}"
        )
    return {
        "status": "PASS",
        "checked_fields": sorted(pairs),
        "mismatches": {},
    }


def compute_cell_identity(
    conn,
    lottery: str,
    strategy: str,
    observed_windows: Dict[int, dict],
) -> dict:
    rows = conn.execute(CELL_QUERY, (lottery, strategy)).fetchall()
    processed = process_cell_rows(rows, lottery, strategy)
    windows = []
    for window in PRIMARY_WINDOWS:
        rec = aggregate_identity_window(processed, window, lottery, strategy)
        rec["artifact_alignment"] = verify_window_alignment(
            rec, observed_windows[window]
        )
        windows.append(rec)

    long_draws = set(processed["distinct_draws_desc"][: max(PRIMARY_WINDOWS)])
    supported_draws = [
        processed["draw_summaries"][draw]
        for draw in processed["distinct_draws_desc"]
        if draw in long_draws
        and processed["draw_summaries"][draw]["eligible_bet_index_count"] >= 1
    ]
    return {
        "lottery_type": lottery,
        "strategy_id": strategy,
        "distinct_draws_available": len(processed["distinct_draws_desc"]),
        "identity_scope_max_primary_window": max(PRIMARY_WINDOWS),
        "same_bet_index_duplicate_rows_collapsed": processed[
            "same_bet_index_duplicate_rows_collapsed"
        ],
        "supported_draws": supported_draws,
        "windows": windows,
    }


def run_export(
    db_path: str = PRODUCTION_DB_PATH,
    primary_path: str = PRIMARY_ARTIFACT_PATH,
    reference_path: str = REFERENCE_ARTIFACT_PATH,
    p267c_path: str = P267C_JSON_PATH,
    p271a_path: str = P271A_JSON_PATH,
    scorer_path: str = P271C_SOURCE_PATH,
    adapter_path: str = P271E_SOURCE_PATH,
    primary_expected_raw: str = PRIMARY_RAW_SHA256,
    primary_expected_canonical: str = PRIMARY_CANONICAL_DIGEST,
    reference_expected_raw: str = REFERENCE_RAW_SHA256,
    reference_expected_canonical: str = REFERENCE_CANONICAL_DIGEST,
) -> dict:
    """Build one canonical identity result from one read-only DB snapshot."""
    primary = verify_source_artifact(
        primary_path, primary_expected_raw, primary_expected_canonical
    )
    reference = verify_source_artifact(
        reference_path, reference_expected_raw, reference_expected_canonical
    )
    frozen_cells = load_frozen_cells(p267c_path)
    committed_conditions = verify_endpoints_against_p271a(p271a_path)
    observed_by_cell = _observed_index(primary["artifact"])
    source_paths = {
        "identity_export_source": IDENTITY_EXPORT_SOURCE_PATH,
        "primary_export_source": PRIMARY_EXPORT_SOURCE_PATH,
        "replay_export_source": REPLAY_EXPORT_SOURCE_PATH,
        "p267c_json": p267c_path,
        "p271a_json": p271a_path,
        "p271c_scorer": scorer_path,
        "p271e_adapter": adapter_path,
    }
    source_hashes = {
        f"{name}_sha256": sha256_file(path)
        for name, path in source_paths.items()
    }

    expected_cells = {
        (cell["lottery_type"], cell["strategy_id"]) for cell in frozen_cells
    }
    if set(observed_by_cell) != expected_cells:
        raise IdentityArtifactAlignmentError(
            "primary observed-counts cell set differs from frozen P267C cells"
        )

    conn, query_only_evidence = open_readonly_connection(db_path)
    transaction_start_at = _now_iso()
    try:
        conn.execute("BEGIN")
        schema = verify_schema(conn)
        cells = [
            compute_cell_identity(
                conn,
                cell["lottery_type"],
                cell["strategy_id"],
                observed_by_cell[
                    (cell["lottery_type"], cell["strategy_id"])
                ],
            )
            for cell in frozen_cells
        ]
        conn.execute("ROLLBACK")
    finally:
        conn.close()
    transaction_end_at = _now_iso()

    supported_draw_records = [
        draw for cell in cells for draw in cell["supported_draws"]
    ]
    windows = [window for cell in cells for window in cell["windows"]]
    duplicate_groups = [
        {
            "lottery_type": draw["lottery_type"],
            "strategy_id": draw["strategy_id"],
            "target_draw": draw["target_draw"],
            "duplicate_ticket_count": draw["duplicate_ticket_count"],
            "canonical_ticket_groups": [
                group
                for group in draw["canonical_ticket_groups"]
                if group["group_multiplicity"] > 1
            ],
        }
        for draw in supported_draw_records
        if draw["duplicate_ticket_count"] > 0
    ]

    result = {
        "meta": {
            "task_id": TASK_ID,
            "artifact_version": ARTIFACT_VERSION,
            "generated_at": _now_iso(),
            "source_main_commit": SOURCE_MAIN_COMMIT,
            "export_worktree_base_commit": SOURCE_MAIN_COMMIT,
            "task_branch": TASK_BRANCH,
            "frozen_strategy_cell_count": len(frozen_cells),
            "lotteries": list(LOTTERY_TYPES),
            "primary_windows": list(PRIMARY_WINDOWS),
            "planned_hypothesis_family_m": CORRECTION_FAMILY_PLANNED,
            "classification": "P273A_DISTINCT_TICKET_IDENTITY_EXPORT_COMPLETE",
        },
        "safety_flags": {
            "db_read_only": True,
            "production_write": False,
            "services_controlled": False,
            "inference_performed": False,
            "baseline_computed": False,
            "p_value_computed": False,
            "edge_claim_made": False,
            "go_recommendation_made": False,
            "registry_mutation": False,
            "migration_deployment_or_controlled_apply": False,
            "p273b_started": False,
        },
        "source_artifacts": {
            "primary": {
                **{
                    key: value
                    for key, value in primary.items()
                    if key != "artifact"
                },
                "source_export_commit": PRIMARY_EXPORT_COMMIT,
            },
            "reference": {
                **{
                    key: value
                    for key, value in reference.items()
                    if key != "artifact"
                },
                "source_export_commit": REFERENCE_EXPORT_COMMIT,
            },
        },
        "provenance": {
            "source_db_path": db_path,
            "db_open_mode": DB_OPEN_MODE,
            "query_only_evidence": query_only_evidence,
            "single_connection": True,
            "single_snapshot": True,
            "transaction_start_at": transaction_start_at,
            "transaction_end_at": transaction_end_at,
            "permitted_tables": ["draws", "strategy_prediction_replays"],
            "normalized_cell_query": CELL_QUERY,
            "schema": schema,
            "source_paths": source_paths,
            "source_hashes": source_hashes,
            "canonical_payload_digest_excludes": sorted(_VOLATILE_KEYS),
            "scoring_version": SCORING_VERSION,
            "adapter_version": ADAPTER_VERSION,
            "source_verification_status": SOURCE_VERIFICATION_STATUS,
            "frozen_cells": frozen_cells,
        },
        "ticket_identity_contract": {
            "parser_provenance": (
                "lottery_api.prize_aware_replay_adapter._check_eligibility "
                "and _parse_number_list"
            ),
            "canonical_serialization": (
                "compact UTF-8 JSON with sort_keys=True, ensure_ascii=False, "
                "separators=(',', ':')"
            ),
            "DAILY_539": (
                "sorted five-number main_numbers array; no auxiliary component"
            ),
            "BIG_LOTTO": (
                "sorted six-number main_numbers array; drawn special number "
                "is not a player-selected identity component"
            ),
            "POWER_LOTTO": (
                "sorted six-number main_numbers array plus stored "
                "predicted_second_zone; missing/invalid values excluded"
            ),
            "same_bet_index_rule": (
                "same identity collapses; two eligible identities STOP with "
                "P273A_BLOCKED_BET_INDEX_CONTENT_CONFLICT"
            ),
            "cross_bet_index_rule": (
                "identical canonical contents share one ticket group; later "
                "inference must use distinct_ticket_count"
            ),
        },
        "endpoint_definitions": {
            lottery: {
                "endpoint_id": GOVERNED_ENDPOINT[lottery]["endpoint_id"],
                "committed_condition_sql": committed_conditions[lottery],
            }
            for lottery in LOTTERY_TYPES
        },
        "cells": cells,
        "summary": {
            "per_draw_identity_record_count": len(supported_draw_records),
            "same_bet_index_content_conflict_count": 0,
            "same_bet_index_duplicate_rows_collapsed": sum(
                cell["same_bet_index_duplicate_rows_collapsed"]
                for cell in cells
            ),
            "duplicate_content_draw_count_long_window_records": len(
                duplicate_groups
            ),
            "total_duplicate_ticket_content_count_long_window_records": sum(
                draw["duplicate_ticket_count"] for draw in supported_draw_records
            ),
            "duplicate_content_groups": duplicate_groups,
            "distinct_ticket_count_distribution_all_supported_draw_records": (
                _distribution(
                    draw["distinct_ticket_count"]
                    for draw in supported_draw_records
                )
            ),
            "distinct_ticket_count_distribution_by_window": {
                str(window): _distribution(
                    count
                    for rec in windows
                    if rec["window"] == window
                    for count, frequency in (
                        (int(value), frequency)
                        for value, frequency in rec[
                            "distinct_ticket_count_distribution"
                        ].items()
                    )
                    for _ in range(frequency)
                )
                for window in PRIMARY_WINDOWS
            },
            "duplicate_content_summary_by_window": {
                str(window): {
                    "duplicate_content_draw_count": sum(
                        rec["duplicate_content_draw_count"]
                        for rec in windows
                        if rec["window"] == window
                    ),
                    "total_duplicate_ticket_content_count": sum(
                        rec["total_duplicate_ticket_content_count"]
                        for rec in windows
                        if rec["window"] == window
                    ),
                }
                for window in PRIMARY_WINDOWS
            },
            "power_excluded_missing_special_rows_by_window": {
                str(window): sum(
                    rec["excluded_missing_special_rows"]
                    for rec in windows
                    if rec["lottery_type"] == "POWER_LOTTO"
                    and rec["window"] == window
                )
                for window in PRIMARY_WINDOWS
            },
            "power_excluded_missing_special_rows_across_primary_windows": sum(
                window["excluded_missing_special_rows"]
                for window in windows
                if window["lottery_type"] == "POWER_LOTTO"
            ),
            "artifact_alignment_status": "PASS",
            "artifact_alignment_windows_checked": len(windows),
        },
        "final_classification": "P273A_DISTINCT_TICKET_IDENTITY_EXPORT_COMPLETE",
    }
    result["canonical_payload_digest"] = compute_payload_digest(result)
    return result


def render_markdown(result: dict) -> str:
    """Render a compact summary without complete per-draw identity tables."""
    meta = result["meta"]
    prov = result["provenance"]
    summ = result["summary"]
    lines: List[str] = []
    add = lines.append
    add("# P273A Distinct-Ticket Identity Export")
    add("")
    add(
        "> Read-only identity evidence only. No baseline, expected successes, "
        "p-value, correction, stability, EDGE/NULL decision, GO recommendation, "
        "or production decision is computed."
    )
    add("")
    add("## Scope and safety")
    add("")
    add(f"- Task: `{meta['task_id']}`")
    add(f"- Classification: `{result['final_classification']}`")
    add(f"- Frozen groups: **{meta['frozen_strategy_cell_count']}**")
    add(f"- Primary windows: **{meta['primary_windows']}**")
    add(f"- Planned family only: **m={meta['planned_hypothesis_family_m']}**")
    add("- Production write: `false`; services controlled: `false`")
    add("- Inference/baseline/p-value/EDGE/GO: `false`")
    add("")
    add("## Provenance")
    add("")
    add(f"- DB mode: `{prov['db_open_mode']}`")
    add(
        f"- query_only: "
        f"`{prov['query_only_evidence']['query_only_pragma_value']}`"
    )
    add("- Single connection / single snapshot: `true` / `true`")
    add(f"- Permitted tables: {', '.join(prov['permitted_tables'])}")
    add(
        f"- Primary raw SHA-256: "
        f"`{result['source_artifacts']['primary']['raw_sha256']}`"
    )
    add(
        f"- Primary canonical digest: "
        f"`{result['source_artifacts']['primary']['canonical_payload_digest']}`"
    )
    add(
        f"- Reference raw SHA-256: "
        f"`{result['source_artifacts']['reference']['raw_sha256']}`"
    )
    add(
        f"- Reference canonical digest: "
        f"`{result['source_artifacts']['reference']['canonical_payload_digest']}`"
    )
    add(f"- Identity artifact digest: `{result['canonical_payload_digest']}`")
    add("")
    add("## Integrity summary")
    add("")
    add(
        f"- Per-draw identity records: "
        f"**{summ['per_draw_identity_record_count']}**"
    )
    add(
        f"- Same-bet-index content conflicts: "
        f"**{summ['same_bet_index_content_conflict_count']}**"
    )
    add(
        f"- Duplicate-content draw records: "
        f"**{summ['duplicate_content_draw_count_long_window_records']}**"
    )
    add(
        f"- Duplicate ticket contents removed: "
        f"**{summ['total_duplicate_ticket_content_count_long_window_records']}**"
    )
    add(
        f"- Artifact alignment: "
        f"**{summ['artifact_alignment_status']}** "
        f"({summ['artifact_alignment_windows_checked']} windows)"
    )
    add("")
    add("## Per-window identity summary")
    add("")
    add(
        "| Lottery | Strategy | Window | Support | Eligible-index dist | "
        "Distinct-ticket dist | Duplicate draws | Duplicate tickets | "
        "POWER missing-special | Alignment |"
    )
    add("|---|---|---:|---:|---|---|---:|---:|---:|---|")
    for cell in result["cells"]:
        for window in cell["windows"]:
            add(
                f"| {cell['lottery_type']} | {cell['strategy_id']} | "
                f"{window['window']} | {window['support_draws']} | "
                f"`{json.dumps(window['eligible_bet_index_count_distribution'], sort_keys=True)}` | "
                f"`{json.dumps(window['distinct_ticket_count_distribution'], sort_keys=True)}` | "
                f"{window['duplicate_content_draw_count']} | "
                f"{window['total_duplicate_ticket_content_count']} | "
                f"{window['excluded_missing_special_rows']} | "
                f"{window['artifact_alignment']['status']} |"
            )
    return "\n".join(lines)


def write_artifacts(
    result: dict,
    out_json: str = DEFAULT_OUT_JSON,
    out_md: str = DEFAULT_OUT_MD,
) -> None:
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(out_md, "w", encoding="utf-8") as fh:
        markdown = render_markdown(result)
        fh.write(markdown)
        if not markdown.endswith("\n"):
            fh.write("\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="P273A read-only distinct-ticket identity export"
    )
    parser.add_argument("--db", default=PRODUCTION_DB_PATH)
    parser.add_argument("--primary", default=PRIMARY_ARTIFACT_PATH)
    parser.add_argument("--reference", default=REFERENCE_ARTIFACT_PATH)
    parser.add_argument("--p267c", default=P267C_JSON_PATH)
    parser.add_argument("--p271a", default=P271A_JSON_PATH)
    parser.add_argument("--scorer-src", default=P271C_SOURCE_PATH)
    parser.add_argument("--adapter-src", default=P271E_SOURCE_PATH)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    result = run_export(
        db_path=args.db,
        primary_path=args.primary,
        reference_path=args.reference,
        p267c_path=args.p267c,
        p271a_path=args.p271a,
        scorer_path=args.scorer_src,
        adapter_path=args.adapter_src,
    )
    write_artifacts(result, args.out_json, args.out_md)
    print(
        json.dumps(
            {
                "task_id": TASK_ID,
                "classification": result["final_classification"],
                "canonical_payload_digest": result[
                    "canonical_payload_digest"
                ],
                "out_json": args.out_json,
                "out_md": args.out_md,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
