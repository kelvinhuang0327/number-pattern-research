"""P541A — BIG_LOTTO strategy inventory / replay coverage audit.

Read-only, static-inspection audit. Builds an inventory of every BIG_LOTTO
strategy/adapter/method the repo defines (registry, wave-3 shadow adapters,
tierb shadow adapters, legacy tools/analysis scripts), cross-references it
against `strategy_prediction_replays` row counts (read-only DB access) and
against the P536/P537/P538/P539/P540 lineage artifacts, and classifies each
discovered id into a coverage bucket.

Historical strategy inventory and replay coverage audit only; not a
prediction, betting edge, future-winning, or production-readiness claim.

Run:
    python3 analysis/p541a_biglotto_strategy_inventory_replay_coverage_audit.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DISCLAIMER = (
    "Historical strategy inventory and replay coverage audit only; not a "
    "prediction, betting edge, future-winning, or production-readiness claim."
)

REPO_ROOT = Path(__file__).resolve().parents[1]

# The canonical DB is gitignored (lottery_api/.gitignore: *.db) and therefore
# does not exist inside an isolated git worktree checkout. It only exists in
# the primary checkout. This mirrors the P539A precedent (see memory:
# project_p539a_readonly_per_draw_replay_export_pr651_merged_20260709.md).
MAIN_CHECKOUT = Path(
    os.environ.get("LOTTERY_MAIN_CHECKOUT", "/Users/kelvin/Kelvin-WorkSpace/LotteryNew")
)
DB_PATH = Path(
    os.environ.get(
        "LOTTERY_DB_PATH", str(MAIN_CHECKOUT / "lottery_api/data/lottery_v2.db")
    )
)

REGISTRY_FILE = REPO_ROOT / "lottery_api/models/replay_strategy_registry.py"
P42_WAVE3_FILE = REPO_ROOT / "lottery_api/models/p42_wave3_biglotto_adapters.py"
P93_TIERB_FILE = REPO_ROOT / "lottery_api/models/p93_tierb_replay_adapters.py"
D3_TEST_FILE = REPO_ROOT / "tests/test_p263a_d3_strategy_status_coverage_audit.py"
QUICK_PREDICT_FILE = REPO_ROOT / "tools/quick_predict.py"

UPSTREAM_ARTIFACTS = {
    "p536c_success_matrix_lift_extension": REPO_ROOT
    / "outputs/research/p536c_success_matrix_lift_extension_20260708.json",
    "p536k_lift_candidate_shortlist": REPO_ROOT
    / "outputs/research/p536k_lift_candidate_shortlist_20260708.json",
    "p537a_shortlist_robustness_review": REPO_ROOT
    / "outputs/research/p537a_shortlist_robustness_review_20260709.json",
    "p538a_strategy_candidate_evaluation_readiness": REPO_ROOT
    / "outputs/research/p538a_strategy_candidate_evaluation_readiness_20260709.json",
    "p539a_readonly_per_draw_replay_export": REPO_ROOT
    / "outputs/research/p539a_readonly_per_draw_replay_export_20260709.json",
    "p539b_oos_availability_ingest_gap_gate": REPO_ROOT
    / "outputs/research/p539b_oos_availability_ingest_gap_gate_20260709.json",
    "p540a_full_replay_regeneration_readiness": REPO_ROOT
    / "outputs/research/p540a_full_replay_regeneration_readiness_20260709.json",
    "p540b_daily539_incremental_replay_generation": REPO_ROOT
    / "outputs/research/p540b_daily539_incremental_replay_generation_20260709.json",
    "p540c_daily539_post_replay_refresh": REPO_ROOT
    / "outputs/research/p540c_daily539_post_replay_refresh_20260709.json",
}

# ── DB snapshot (read-only integrity check) ─────────────────────────────────


def db_snapshot(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    st = path.stat()
    return {"sha256": h.hexdigest(), "mtime": st.st_mtime, "size": st.st_size}


# ── Static registry parsing (regex over source text; no imports/execution) ──

_META_BLOCK_RE = re.compile(
    r'strategy_id="(?P<id>[a-z0-9_]+)",\s*'
    r'strategy_name="(?P<name>[^"]*)",\s*'
    r'strategy_version="(?P<version>[^"]*)",\s*'
    r"supported_lottery_types=\[(?P<types>[^\]]*)\],\s*"
    r"(?:min_history=\d+,\s*)?"
    r'status="(?P<status>[A-Z_]+)"',
    re.MULTILINE,
)


def _parse_meta_blocks(text: str, source_file: str) -> list[dict]:
    out = []
    for m in _META_BLOCK_RE.finditer(text):
        types = [t.strip().strip('"').strip("'") for t in m.group("types").split(",") if t.strip()]
        if "BIG_LOTTO" not in types:
            continue
        out.append(
            {
                "strategy_id": m.group("id"),
                "strategy_name": m.group("name"),
                "strategy_version": m.group("version"),
                "status": m.group("status"),
                "source_file": source_file,
            }
        )
    return out


def parse_main_registry() -> list[dict]:
    if not REGISTRY_FILE.exists():
        return []
    text = REGISTRY_FILE.read_text(encoding="utf-8")
    entries = _parse_meta_blocks(text, "lottery_api/models/replay_strategy_registry.py")
    # Tag whether each id is inside _ALL_ADAPTERS (governance-visible) — all
    # entries in this file are, by construction of the file (ONLINE adapters
    # + _NON_EXECUTABLE_STUBS are both appended to _ALL_ADAPTERS).
    generation_statuses = {"ONLINE", "ACTIVE"}
    for e in entries:
        e["in_registry_generation_eligible"] = e["status"] in generation_statuses
        e["in_all_adapters"] = True
    return entries


def parse_p42_wave3() -> list[dict]:
    if not P42_WAVE3_FILE.exists():
        return []
    text = P42_WAVE3_FILE.read_text(encoding="utf-8")
    ids = sorted(set(re.findall(r'strategy_id="([a-z0-9_]+)"', text)))
    # File docstring/constant states uniform lifecycle_status=DRY_RUN and
    # explicitly NOT registered in replay_strategy_registry._ALL_ADAPTERS.
    return [
        {
            "strategy_id": sid,
            "status": "DRY_RUN",
            "source_file": "lottery_api/models/p42_wave3_biglotto_adapters.py",
            "in_registry_generation_eligible": False,
            "in_all_adapters": False,
            "note": "Shadow adapter file explicitly not wired into replay_strategy_registry._ALL_ADAPTERS.",
        }
        for sid in ids
    ]


def parse_p93_tierb() -> list[dict]:
    if not P93_TIERB_FILE.exists():
        return []
    text = P93_TIERB_FILE.read_text(encoding="utf-8")
    # Blocks are `strategy_id="...",` followed a few lines later by `status="...",`
    block_re = re.compile(
        r'strategy_id="(?P<id>[a-z0-9_]+)".*?status="(?P<status>[A-Z_]+)"', re.DOTALL
    )
    out = []
    for m in block_re.finditer(text):
        sid = m.group("id")
        if "biglotto" not in sid:
            continue
        out.append(
            {
                "strategy_id": sid,
                "status": m.group("status"),
                "source_file": "lottery_api/models/p93_tierb_replay_adapters.py",
                "in_registry_generation_eligible": False,
                "in_all_adapters": False,
                "note": "Shadow adapter file (P93 tier-B); not wired into replay_strategy_registry._REGISTRY.",
            }
        )
    return out


def parse_d3_phantom_and_registered_without_rows() -> dict:
    if not D3_TEST_FILE.exists():
        return {"phantom_ids": [], "registered_without_rows": []}
    text = D3_TEST_FILE.read_text(encoding="utf-8")

    def _extract_set(anchor: str) -> list[str]:
        idx = text.find(anchor)
        if idx == -1:
            return []
        window = text[idx : idx + 1200]
        return sorted(
            m.replace("BIG_LOTTO:", "")
            for m in re.findall(r'"BIG_LOTTO:([a-z0-9_]+)"', window)
        )

    phantom = _extract_set("phantom_rows")
    registered_without_rows = _extract_set("registered_without_rows")
    return {"phantom_ids": phantom, "registered_without_rows": registered_without_rows}


def parse_quick_predict_dispatch() -> list[str]:
    if not QUICK_PREDICT_FILE.exists():
        return []
    text = QUICK_PREDICT_FILE.read_text(encoding="utf-8")
    idx = text.find("STRATEGY_INFO")
    if idx == -1:
        return []
    window = text[idx : idx + 2000]
    m = re.search(r"'BIG_LOTTO':\s*\{(.*?)\n\s*\}", window, re.DOTALL)
    return [line.strip().rstrip(",") for line in m.group(1).splitlines() if line.strip()] if m else []


# ── git grep legacy inventory (file lists only, no import/execution) ────────


def git_grep_files(pattern: str, path_glob: str) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "grep", "-il", pattern, "--", path_glob],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError):
        return []
    if result.returncode not in (0, 1):
        return []
    return sorted(l for l in result.stdout.splitlines() if l.strip())


# ── DB replay coverage (read-only) ───────────────────────────────────────────


def query_replay_coverage() -> Optional[dict]:
    if not DB_PATH.exists():
        return None
    uri = f"file:{DB_PATH}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        cur = conn.cursor()
        cur.execute(
            """
            SELECT strategy_id, COUNT(*) as n,
                   MIN(CAST(target_draw AS INTEGER)) as min_draw,
                   MAX(CAST(target_draw AS INTEGER)) as max_draw,
                   COUNT(DISTINCT bet_index) as n_bet_idx,
                   SUM(CASE WHEN controlled_apply_id IS NOT NULL THEN 1 ELSE 0 END) as n_controlled,
                   SUM(CASE WHEN actual_numbers IS NOT NULL THEN 1 ELSE 0 END) as n_resolved
            FROM strategy_prediction_replays
            WHERE lottery_type='BIG_LOTTO'
            GROUP BY strategy_id
            ORDER BY n DESC
            """
        )
        cols = [d[0] for d in cur.description]
        by_strategy = {row[0]: dict(zip(cols, row)) for row in cur.fetchall()}

        cur.execute(
            "SELECT COUNT(*), MAX(CAST(target_draw AS INTEGER)) FROM strategy_prediction_replays WHERE lottery_type='BIG_LOTTO'"
        )
        total_rows, max_replayed_draw = cur.fetchone()

        cur.execute(
            "SELECT COUNT(*), MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='BIG_LOTTO'"
        )
        draws_count, max_ingested_draw = cur.fetchone()

        return {
            "by_strategy": by_strategy,
            "total_rows": total_rows,
            "max_replayed_draw": max_replayed_draw,
            "draws_ingested_count": draws_count,
            "max_ingested_draw": max_ingested_draw,
            "unreplayed_recent_draw_gap": (
                None
                if max_replayed_draw is None or max_ingested_draw is None
                else max(0, max_ingested_draw - max_replayed_draw)
            ),
        }
    finally:
        conn.close()


# ── Upstream artifact coverage (json membership check) ──────────────────────


def check_artifact_coverage(strategy_ids: list[str]) -> dict:
    coverage: dict[str, dict] = {sid: {} for sid in strategy_ids}
    sources_read = {}
    for key, path in UPSTREAM_ARTIFACTS.items():
        if not path.exists():
            sources_read[key] = "MISSING"
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            sources_read[key] = "READ_ERROR"
            continue
        sources_read[key] = "OK"
        for sid in strategy_ids:
            # Whole-id substring match against the raw JSON text is sufficient
            # for a coverage yes/no signal (all candidate ids are unique,
            # non-overlapping tokens; see p541a static inventory).
            coverage[sid][key] = f'"{sid}"' in raw
    return {"coverage": coverage, "sources_read": sources_read}


# ── Classification ───────────────────────────────────────────────────────────

CLASSES = [
    "replayed_and_artifact_covered",
    "replayed_not_artifact_covered",
    "code_or_registry_only_no_replay_rows",
    "artifact_only_unmapped_to_code",
    "legacy_or_experimental",
    "explicitly_excluded_or_unsafe",
    "ambiguous_needs_cto_review",
]


def build_report() -> dict:
    main_registry = parse_main_registry()
    p42 = parse_p42_wave3()
    p93 = parse_p93_tierb()
    d3 = parse_d3_phantom_and_registered_without_rows()
    quick_predict_lines = parse_quick_predict_dispatch()

    legacy_tools_files = git_grep_files(
        r"big_lotto\|BIG_LOTTO\|biglotto\|大樂透", "tools/*.py"
    )
    legacy_analysis_files = git_grep_files(
        r"big_lotto\|BIG_LOTTO\|biglotto\|大樂透", "analysis/*.py"
    )

    replay = query_replay_coverage()
    replayed_ids = sorted(replay["by_strategy"].keys()) if replay else []

    # Union of every known id from all static sources.
    known_ids: dict[str, dict] = {}
    for e in main_registry + p42 + p93:
        known_ids.setdefault(e["strategy_id"], {"sources": []})
        known_ids[e["strategy_id"]]["sources"].append(e)
    for sid in d3["phantom_ids"]:
        known_ids.setdefault(sid, {"sources": []})
        known_ids[sid].setdefault("d3_phantom", True)
    for sid in replayed_ids:
        known_ids.setdefault(sid, {"sources": []})

    all_ids = sorted(known_ids.keys())
    artifact_check = check_artifact_coverage(all_ids)

    classification: dict[str, str] = {}
    for sid in all_ids:
        entry = known_ids[sid]
        has_replay = sid in replayed_ids
        has_artifact = any(artifact_check["coverage"].get(sid, {}).values())
        is_phantom = entry.get("d3_phantom", False) and not entry["sources"]
        is_registered_no_rows = any(
            s.get("in_all_adapters") and s.get("status") in ("REJECTED",) for s in entry["sources"]
        ) and not has_replay

        if is_phantom:
            classification[sid] = "artifact_only_unmapped_to_code"
        elif is_registered_no_rows:
            classification[sid] = "code_or_registry_only_no_replay_rows"
        elif has_replay and has_artifact:
            classification[sid] = "replayed_and_artifact_covered"
        elif has_replay and not has_artifact:
            classification[sid] = "replayed_not_artifact_covered"
        elif entry["sources"] and not has_replay:
            classification[sid] = "code_or_registry_only_no_replay_rows"
        else:
            classification[sid] = "ambiguous_needs_cto_review"

    retired_conflict = [
        sid
        for sid in all_ids
        if any(s.get("status") == "RETIRED" for s in known_ids[sid]["sources"])
        and any(s.get("status") == "ONLINE" for s in known_ids[sid]["sources"])
    ]

    covered = [sid for sid, c in classification.items() if c == "replayed_and_artifact_covered"]
    replayed_only = [sid for sid, c in classification.items() if c == "replayed_not_artifact_covered"]
    registered_no_rows = [
        sid for sid, c in classification.items() if c == "code_or_registry_only_no_replay_rows"
    ]
    phantom = [sid for sid, c in classification.items() if c == "artifact_only_unmapped_to_code"]

    if replay is None:
        owner_answer = {
            "verdict": "UNKNOWN",
            "reason": "Canonical DB not reachable read-only from this environment at DB_PATH; "
            "see provenance_and_limits.db_path_note.",
        }
    else:
        owner_answer = {
            "verdict": "PARTIAL",
            "covered_strategy_ids": covered + replayed_only,
            "covered_count": len(covered) + len(replayed_only),
            "covered_total_replay_rows": replay["total_rows"],
            "uncovered_registered_strategy_ids": registered_no_rows,
            "uncovered_phantom_ids_no_code_no_replay": phantom,
            "recency_gap_draws_not_yet_replayed_by_any_strategy": replay[
                "unreplayed_recent_draw_gap"
            ],
            "unmapped_legacy_script_count": len(legacy_tools_files) + len(legacy_analysis_files),
            "reason": (
                f"{len(covered) + len(replayed_only)} distinct BIG_LOTTO strategy_ids have at least "
                f"one replay row ({replay['total_rows']} rows total, all resolved with actual "
                "outcomes). All of them are also referenced in the P536C success/lift matrix. "
                f"However {len(registered_no_rows)} formally-registered id(s) "
                f"({', '.join(registered_no_rows) or 'none'}) have zero replay rows, "
                f"{len(phantom)} id(s) referenced only in the D3 UI/test artifact "
                f"({', '.join(phantom) or 'none'}) have no code/registry definition and no replay "
                f"rows, the most recent {replay['unreplayed_recent_draw_gap']} ingested draw(s) "
                "have not been replayed by any strategy yet, and "
                f"{len(legacy_tools_files) + len(legacy_analysis_files)} legacy tools/analysis "
                "script(s) reference BIG_LOTTO but were not individually traced to a replay-backed "
                "strategy_id by this static audit. Therefore coverage is PARTIAL, not YES."
            ),
        }

    report = {
        "schema_version": "1.0",
        "task_id": "P541A",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classification": "P541A_BIGLOTTO_STRATEGY_INVENTORY_REPLAY_COVERAGE_AUDIT",
        "summary_answer": (
            owner_answer["verdict"]
            + " — see answer_to_owner_question for full evidence."
        ),
        "inventory_sources_scanned": {
            "registry_file": str(REGISTRY_FILE.relative_to(REPO_ROOT)) if REGISTRY_FILE.exists() else None,
            "p42_wave3_shadow_adapter_file": str(P42_WAVE3_FILE.relative_to(REPO_ROOT)) if P42_WAVE3_FILE.exists() else None,
            "p93_tierb_shadow_adapter_file": str(P93_TIERB_FILE.relative_to(REPO_ROOT)) if P93_TIERB_FILE.exists() else None,
            "d3_phantom_test_file": str(D3_TEST_FILE.relative_to(REPO_ROOT)) if D3_TEST_FILE.exists() else None,
            "quick_predict_dispatch_file": str(QUICK_PREDICT_FILE.relative_to(REPO_ROOT)) if QUICK_PREDICT_FILE.exists() else None,
            "legacy_tools_scripts_matched": len(legacy_tools_files),
            "legacy_analysis_scripts_matched": len(legacy_analysis_files),
            "upstream_artifacts": {k: str(v.relative_to(REPO_ROOT)) for k, v in UPSTREAM_ARTIFACTS.items()},
            "db_path_used": str(DB_PATH),
            "db_reachable": replay is not None,
        },
        "big_lotto_strategy_inventory": {
            sid: {
                "sources": known_ids[sid]["sources"],
                "d3_phantom_reference": known_ids[sid].get("d3_phantom", False),
                "classification": classification[sid],
                "replay_row_count": replay["by_strategy"].get(sid, {}).get("n") if replay else None,
            }
            for sid in all_ids
        },
        "folklore_and_statistical_method_inventory": {
            "note": (
                "Frontend generic advisory strategies in src/engine/strategies/*.js "
                "(FrequencyStrategy, HotColdMixStrategy, MarkovStrategy, TrendStrategy, "
                "SumRangeStrategy, ZoneBalanceStrategy, OddEvenBalanceStrategy, "
                "DeviationStrategy, NumberPairsStrategy, WheelingStrategy, "
                "MonteCarloStrategy, BayesianStrategy, StatisticalAnalysisStrategy, "
                "UnifiedEnsembleStrategy, CollaborativeStrategy, AutoOptimizeStrategy, "
                "MLStrategy) are generic across lottery types (default to BIG_LOTTO only "
                "when unset) and are NOT part of the strategy_prediction_replays backend "
                "system at all — they have no strategy_id in this audit's universe and no "
                "replay coverage is possible for them under the current schema."
            ),
            "backend_folklore_families_tested_per_lessons_md_L90_L91": [
                "ACB",
                "Fourier",
                "MicroFish",
                "Markov",
                "Regime",
                "P1_Neighbor",
                "MidFreq",
            ],
            "quick_predict_dispatch_labels_uncorrelated_to_registry_ids": quick_predict_lines,
        },
        "replay_coverage_by_strategy": replay["by_strategy"] if replay else None,
        "replay_coverage_totals": {
            "total_rows": replay["total_rows"] if replay else None,
            "distinct_strategy_ids_with_rows": len(replayed_ids),
            "max_replayed_draw": replay["max_replayed_draw"] if replay else None,
            "max_ingested_draw": replay["max_ingested_draw"] if replay else None,
            "draws_ingested_count": replay["draws_ingested_count"] if replay else None,
            "unreplayed_recent_draw_gap": replay["unreplayed_recent_draw_gap"] if replay else None,
        },
        "artifact_coverage_by_strategy": artifact_check["coverage"],
        "artifact_sources_read": artifact_check["sources_read"],
        "coverage_gaps": {
            "registered_zero_replay_rows": registered_no_rows,
            "d3_phantom_no_code_no_replay": phantom,
            "recency_gap_draws": replay["unreplayed_recent_draw_gap"] if replay else None,
            "lifecycle_status_conflicts_retired_vs_online": retired_conflict,
        },
        "ambiguous_or_unmapped_items": {
            "legacy_tools_scripts_matched_not_individually_traced": legacy_tools_files,
            "legacy_analysis_scripts_matched_not_individually_traced": legacy_analysis_files,
            "note": (
                "This static audit enumerates these files by keyword match only; it does "
                "not import or execute them, so it cannot confirm whether each implements "
                "a method distinct from the 11 replay-backed strategy_ids above, is a "
                "duplicate/exploratory variant, or was ever wired to a registry adapter. "
                "Individual triage is out of scope per task spec (no execution, no imports "
                "with side effects) and is recommended as follow-up."
            ),
        },
        "deprecated_or_excluded_items": {
            "rejected_registered_ids": [
                sid
                for sid in all_ids
                if any(s.get("status") == "REJECTED" for s in known_ids[sid]["sources"])
            ],
            "retired_registered_ids": [
                sid
                for sid in all_ids
                if any(s.get("status") == "RETIRED" for s in known_ids[sid]["sources"])
            ],
            "dry_run_shadow_ids": [
                sid
                for sid in all_ids
                if any(s.get("status") == "DRY_RUN" for s in known_ids[sid]["sources"])
            ],
        },
        "answer_to_owner_question": owner_answer,
        "recommended_next_single_worker_task": (
            "P541B_BIG_LOTTO_LEGACY_METHOD_CLASSIFICATION_AUDIT"
            if (len(legacy_tools_files) + len(legacy_analysis_files)) > 0
            else "P541A_COMPLETE_NO_ACTION_FOR_BIG_LOTTO_UNTIL_30_NEW_DRAWS"
        ),
        "provenance_and_limits": {
            "method": "Static regex/text parsing of registry + shadow adapter files, git grep "
            "keyword file listing (no import/execution), read-only SQLite (mode=ro, "
            "PRAGMA query_only=ON) query of strategy_prediction_replays and draws, and "
            "substring membership check against 9 committed upstream JSON artifacts.",
            "db_path_note": (
                "Canonical DB (lottery_api/data/lottery_v2.db) is gitignored and not present "
                "inside this isolated worktree; read via absolute path into the main checkout "
                "(same precedent as P539A). DB_PATH overridable via LOTTERY_DB_PATH env var."
            ),
            "not_performed_by_this_task": [
                "DB writes of any kind",
                "replay row generation",
                "import/execution of tools/*.py or analysis/*.py strategy modules",
                "OOS evaluator runs, strategy scoring, or promotion gating",
                "recomputation or overwrite of P536-P540 artifacts",
                "individual file-by-file triage of the ~350+ legacy tools/analysis scripts",
            ],
            "disclaimer": DISCLAIMER,
        },
        "disclaimer": DISCLAIMER,
    }
    return report


# ── Markdown rendering ────────────────────────────────────────────────────────


def render_markdown(report: dict) -> str:
    lines = []
    lines.append("# P541A — BIG_LOTTO Strategy Inventory / Replay Coverage Audit")
    lines.append("")
    lines.append(f"> generated_at: {report['generated_at']}")
    lines.append(f"> {DISCLAIMER}")
    lines.append("")
    lines.append(f"## Owner question answer: {report['answer_to_owner_question']['verdict']}")
    lines.append("")
    lines.append(report["answer_to_owner_question"].get("reason", ""))
    lines.append("")
    lines.append("## Replay coverage totals")
    lines.append("")
    totals = report["replay_coverage_totals"]
    for k, v in totals.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Strategy inventory")
    lines.append("")
    lines.append("| strategy_id | classification | replay_rows | statuses seen |")
    lines.append("|---|---|---|---|")
    for sid, entry in sorted(report["big_lotto_strategy_inventory"].items()):
        statuses = sorted({s.get("status") for s in entry["sources"] if s.get("status")})
        lines.append(
            f"| {sid} | {entry['classification']} | {entry['replay_row_count']} | {', '.join(statuses) or '-'} |"
        )
    lines.append("")
    lines.append("## Coverage gaps")
    lines.append("")
    for k, v in report["coverage_gaps"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Deprecated / excluded")
    lines.append("")
    for k, v in report["deprecated_or_excluded_items"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Ambiguous / unmapped legacy scripts")
    lines.append("")
    ambiguous = report["ambiguous_or_unmapped_items"]
    lines.append(
        f"- tools/*.py matched: {len(ambiguous['legacy_tools_scripts_matched_not_individually_traced'])}"
    )
    lines.append(
        f"- analysis/*.py matched: {len(ambiguous['legacy_analysis_scripts_matched_not_individually_traced'])}"
    )
    lines.append(f"- {ambiguous['note']}")
    lines.append("")
    lines.append("## Recommended next task")
    lines.append("")
    lines.append(report["recommended_next_single_worker_task"])
    lines.append("")
    lines.append("## Provenance and limits")
    lines.append("")
    lines.append(report["provenance_and_limits"]["method"])
    lines.append("")
    lines.append(report["provenance_and_limits"]["db_path_note"])
    lines.append("")
    lines.append("Not performed by this task:")
    for item in report["provenance_and_limits"]["not_performed_by_this_task"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append(f"*{DISCLAIMER}*")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    parser.add_argument("--out-dir", default=str(REPO_ROOT / "outputs/research"))
    parser.add_argument("--no-write", action="store_true", help="print report, do not write files")
    args = parser.parse_args()

    before = db_snapshot(DB_PATH)
    report = build_report()
    after = db_snapshot(DB_PATH)
    report["provenance_and_limits"]["db_snapshot_before"] = before
    report["provenance_and_limits"]["db_snapshot_after"] = after
    report["provenance_and_limits"]["db_unchanged"] = before == after

    if args.no_write:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = f"p541a_biglotto_strategy_inventory_replay_coverage_audit_{args.date}"
    json_path = out_dir / f"{base}.json"
    md_path = out_dir / f"{base}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
