#!/usr/bin/env python3
"""
P1 Strategy Universe Inventory — READ ONLY
===========================================
Builds a complete strategy universe inventory by scanning:
  1. Canonical registry  (lottery_api/models/replay_strategy_registry.py)
  2. Drift guard tombstone IDs  (scripts/replay_lifecycle_drift_guard.py)
  3. DB read-only query  (strategy_prediction_replays)
  4. Existing inventory artifacts  (outputs/replay/*.json)
  5. Repo code search  (strategy_*.py, *.strategy.py patterns)

STRICT CONSTRAINTS
  - No DB writes
  - No replay row generation
  - No backtest
  - No strategy code modification
  - No registry mutation
  - UNKNOWN stays UNKNOWN — no forced classification

Outputs:
  outputs/replay/p1_strategy_universe_inventory_20260515.json
  outputs/replay/p1_strategy_universe_inventory_20260515.csv
"""

import argparse
import csv
import datetime
import json
import re
import sqlite3
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent

DEFAULT_DB     = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
DEFAULT_JSON   = REPO_ROOT / "outputs" / "replay" / "p1_strategy_universe_inventory_20260515.json"
DEFAULT_CSV    = REPO_ROOT / "outputs" / "replay" / "p1_strategy_universe_inventory_20260515.csv"

# ── Canonical registry (from replay_strategy_registry.py) ──────────────────
# Source-of-truth: lottery_api/models/replay_strategy_registry.py
# Extracted 2026-05-15 — do not edit here; re-run script to refresh.
CANONICAL_REGISTRY = [
    # strategy_id,                    lifecycle_status,  lottery_type
    ("power_precision_3bet",          "ONLINE",          "POWER_LOTTO"),
    ("power_orthogonal_5bet",         "ONLINE",          "POWER_LOTTO"),
    ("biglotto_triple_strike",        "ONLINE",          "BIG_LOTTO"),
    ("biglotto_deviation_2bet",       "ONLINE",          "BIG_LOTTO"),
    ("daily539_f4cold",               "ONLINE",          "DAILY_539"),
    ("daily539_markov_cold",          "ONLINE",          "DAILY_539"),
    ("biglotto_ts3_acb_4bet",         "REJECTED",        "BIG_LOTTO"),
    ("biglotto_ts3_markov_freq_5bet", "REJECTED",        "BIG_LOTTO"),
    ("power_shlc_midfreq",            "REJECTED",        "POWER_LOTTO"),
    ("p1_deviation_2bet_539",         "REJECTED",        "DAILY_539"),
    ("acb_1bet",                      "RETIRED",         "DAILY_539"),
    ("acb_markov_midfreq",            "RETIRED",         "DAILY_539"),
    ("acb_markov_midfreq_3bet",       "RETIRED",         "DAILY_539"),
    ("midfreq_acb_2bet",              "RETIRED",         "DAILY_539"),
    ("midfreq_fourier_2bet",          "RETIRED",         "DAILY_539"),
    ("h6_gate_mk20_ew85",             "OBSERVATION",     "POWER_LOTTO"),
]
REGISTRY_IDS = {r[0] for r in CANONICAL_REGISTRY}

# ── V3 CODE_MISSING tombstone IDs (from drift guard) ───────────────────────
# These strategies exist in registry but have 0 DB rows by design
V3_TOMBSTONE_IDS = frozenset([
    "acb_1bet",
    "acb_markov_midfreq",
    "acb_markov_midfreq_3bet",
    "midfreq_acb_2bet",
    "midfreq_fourier_2bet",
    "h6_gate_mk20_ew85",
])

# ── Strategies that are generic placeholders / noise ───────────────────────
# "strategy" and "big_lotto"/"daily_539"/"power_lotto" are internal test IDs
NOISE_IDS = frozenset(["strategy", "big_lotto", "daily_539", "power_lotto"])

# ── Lifecycle from existing p1 inventory (2026-05-11) for non-canonical ────
_P1_PREV_LIFECYCLE: dict[str, str] = {}  # filled at runtime from artifact

# ---------------------------------------------------------------------------
# Source scanning helpers
# ---------------------------------------------------------------------------

def _scan_db(db_path: Path) -> dict[str, dict]:
    """Read-only DB query. Returns {strategy_id: {truth_level: count}}."""
    result: dict[str, dict] = {}
    if not db_path.exists():
        print(f"[WARN] DB not found: {db_path}", file=sys.stderr)
        return result
    conn = sqlite3.connect(str(db_path))
    try:
        c = conn.cursor()
        c.execute(
            "SELECT strategy_id, truth_level, COUNT(*) "
            "FROM strategy_prediction_replays "
            "GROUP BY strategy_id, truth_level"
        )
        for sid, tl, cnt in c.fetchall():
            tl_key = tl if tl else "NULL"
            if sid not in result:
                result[sid] = {}
            result[sid][tl_key] = result[sid].get(tl_key, 0) + cnt
    finally:
        conn.close()
    return result


def _scan_artifacts(repo_root: Path) -> dict[str, list[str]]:
    """Scan outputs/replay JSON/JSONL for strategy_id references.
    Returns {strategy_id: [source_files]}."""
    result: dict[str, list[str]] = defaultdict(list)
    pattern = re.compile(r'"strategy_id"\s*:\s*"([^"]+)"')
    for ext in ("*.json", "*.jsonl"):
        for fp in (repo_root / "outputs" / "replay").glob(ext):
            try:
                text = fp.read_text(errors="replace")
                for m in pattern.finditer(text):
                    sid = m.group(1)
                    rel = str(fp.relative_to(repo_root))
                    if rel not in result[sid]:
                        result[sid].append(rel)
            except Exception as e:
                print(f"[WARN] Could not read {fp}: {e}", file=sys.stderr)
    return dict(result)


def _scan_code(repo_root: Path) -> dict[str, list[str]]:
    """Find Python files referencing specific strategy IDs as string literals.
    Returns {strategy_id: [source_files]}."""
    result: dict[str, list[str]] = defaultdict(list)
    candidate_dirs = [
        repo_root / "lottery_api",
        repo_root / "scripts",
        repo_root / "tests",
        repo_root / "tools",
    ]
    pat = re.compile(r'["\']([a-z][a-z0-9_]{3,})["\']')
    known_non_strategy = {
        "strategy_id", "strategy_name", "lifecycle_status", "replay_status",
        "lottery_type", "truth_level", "controlled_apply_id", "target_draw",
        "daily_539", "power_lotto", "big_lotto", "strategy",
        "generated_at", "checked_at", "status", "notes", "NULL",
        "ONLINE", "OFFLINE", "REJECTED", "RETIRED", "OBSERVATION",
        "LIVE", "FROZEN", "NO_DATA", "RETROSPECTIVE",
    }
    for d in candidate_dirs:
        if not d.exists():
            continue
        for fp in d.rglob("*.py"):
            if "__pycache__" in str(fp):
                continue
            try:
                text = fp.read_text(errors="replace")
                for m in pat.finditer(text):
                    val = m.group(1)
                    if val in known_non_strategy:
                        continue
                    if val in REGISTRY_IDS:
                        rel = str(fp.relative_to(repo_root))
                        if rel not in result[val]:
                            result[val].append(rel)
            except Exception:
                pass
    return dict(result)


def _load_prev_inventory(repo_root: Path) -> dict[str, str]:
    """Load lifecycle status from previous p1 inventory for cross-reference."""
    prev = repo_root / "outputs" / "replay" / "p1_strategy_lifecycle_inventory_20260511.json"
    if not prev.exists():
        return {}
    try:
        data = json.loads(prev.read_text())
        return {c["strategy_id"]: c.get("lifecycle_status", "UNKNOWN")
                for c in data.get("candidates", [])
                if c.get("strategy_id")}
    except Exception:
        return {}


def _all_artifact_strategy_ids(repo_root: Path) -> set[str]:
    """All strategy IDs found in artifacts (JSON/JSONL files in outputs/replay)."""
    result = set()
    pattern = re.compile(r'"strategy_id"\s*:\s*"([^"]+)"')
    for ext in ("*.json", "*.jsonl"):
        for fp in (repo_root / "outputs" / "replay").glob(ext):
            try:
                text = fp.read_text(errors="replace")
                for m in pattern.finditer(text):
                    result.add(m.group(1))
            except Exception:
                pass
    return result


# ---------------------------------------------------------------------------
# Truth classification helper
# ---------------------------------------------------------------------------

def _classify_truth(sid: str, tl_counts: dict[str, int]) -> str:
    if sid in V3_TOMBSTONE_IDS and sum(tl_counts.values()) == 0:
        return "CODE_MISSING"
    if "REGENERATED_RETROSPECTIVE" in tl_counts:
        return "REGENERATED_RETROSPECTIVE"
    if "ARTIFACT_RECONSTRUCTED_RETROSPECTIVE" in tl_counts:
        return "ARTIFACT_RECONSTRUCTED_RETROSPECTIVE"
    if "NULL" in tl_counts and len(tl_counts) == 1:
        return "LEGACY_NULL"
    if tl_counts:
        return "MIXED"
    return "UNKNOWN"


def _display_semantics(lifecycle: str, truth: str) -> str:
    if lifecycle == "ONLINE":
        return "LIVE"
    if lifecycle in ("OFFLINE", "RETIRED"):
        return "FROZEN"
    if lifecycle in ("REJECTED", "OBSERVATION"):
        if truth in ("REGENERATED_RETROSPECTIVE", "ARTIFACT_RECONSTRUCTED_RETROSPECTIVE", "LEGACY_NULL", "MIXED"):
            return "RETROSPECTIVE"
        return "NO_DATA"
    if lifecycle == "UNKNOWN":
        return "UNKNOWN"
    return "UNKNOWN"


def _coverage_status(lifecycle: str, db_rows: int, in_db: bool) -> str:
    if lifecycle == "ONLINE" and in_db:
        return "COVERED"
    if lifecycle in ("OFFLINE", "RETIRED") and in_db:
        return "COVERED"
    if lifecycle == "REJECTED" and in_db:
        return "PARTIAL"
    if lifecycle in ("OBSERVATION",) and in_db:
        return "PARTIAL"
    if lifecycle in ("ONLINE", "OFFLINE") and not in_db:
        return "NOT_COVERED"
    if lifecycle == "UNKNOWN":
        return "UNKNOWN"
    if not in_db and lifecycle != "RETIRED":
        return "NOT_COVERED"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def build_inventory(db_path: Path, repo_root: Path) -> dict:
    print(f"[INFO] DB: {db_path}", file=sys.stderr)
    print(f"[INFO] Repo: {repo_root}", file=sys.stderr)

    # Load sources
    db_data   = _scan_db(db_path)
    art_data  = _scan_artifacts(repo_root)
    code_data = _scan_code(repo_root)
    prev_lc   = _load_prev_inventory(repo_root)

    # Collect all strategy IDs from all sources
    artifact_ids = _all_artifact_strategy_ids(repo_root)
    all_ids = (
        REGISTRY_IDS
        | set(db_data.keys())
        | artifact_ids
        | set(code_data.keys())
    )

    # Remove generic noise IDs
    all_ids -= NOISE_IDS

    strategies = []
    for sid in sorted(all_ids):
        in_registry = sid in REGISTRY_IDS
        in_db       = sid in db_data
        in_artifacts = sid in art_data
        in_code     = sid in code_data

        # Lifecycle from registry (authoritative); fallback to prev inventory
        registry_entry = next((r for r in CANONICAL_REGISTRY if r[0] == sid), None)
        if registry_entry:
            lifecycle = registry_entry[1]
        else:
            lifecycle = prev_lc.get(sid, "UNKNOWN")

        # DB counts
        tl_counts  = db_data.get(sid, {})
        db_row_count = sum(tl_counts.values())

        # Sources list
        sources = []
        if in_registry:   sources.append("registry")
        if in_db:         sources.append("db")
        if in_artifacts:  sources.append("artifact")
        if in_code:       sources.append("code")
        if sid in prev_lc and not (in_registry or in_db or in_artifacts or in_code):
            sources.append("prev_inventory")

        # Source files
        source_files = sorted(
            list(art_data.get(sid, []))
            + list(code_data.get(sid, []))
        )

        truth = _classify_truth(sid, tl_counts)
        display = _display_semantics(lifecycle, truth)
        coverage = _coverage_status(lifecycle, db_row_count, in_db)

        # Risk flags
        risk_flags = []
        if lifecycle == "UNKNOWN":
            risk_flags.append("UNKNOWN_LIFECYCLE")
        if in_db and not in_registry:
            risk_flags.append("DB_WITHOUT_REGISTRY")
        if sid in V3_TOMBSTONE_IDS and db_row_count > 0:
            risk_flags.append("TOMBSTONE_HAS_ROWS_DRIFT_VIOLATION")
        if sid in NOISE_IDS:
            risk_flags.append("NOISE_ID")

        # Notes
        notes_parts = []
        if registry_entry:
            notes_parts.append(f"lottery_type={registry_entry[2]}")
        if sid in V3_TOMBSTONE_IDS:
            notes_parts.append("V3 CODE_MISSING tombstone — 0 rows enforced by drift guard")
        if lifecycle in ("RETIRED", "OBSERVATION") and sid in V3_TOMBSTONE_IDS:
            notes_parts.append("registry entry exists; code unavailable for re-run")
        if not in_registry and in_artifacts:
            notes_parts.append("artifact-only: appeared in historical backtest/research outputs")
        if lifecycle == "UNKNOWN" and in_artifacts:
            notes_parts.append("lifecycle not determinable from registry; needs operator review")
        notes = "; ".join(notes_parts) if notes_parts else ""

        strategies.append({
            "strategy_id":              sid,
            "normalized_strategy_id":   sid,
            "display_name":             sid.replace("_", " ").title(),
            "sources":                  sources,
            "source_files":             source_files[:5],  # cap for readability
            "in_registry":              in_registry,
            "in_db":                    in_db,
            "in_artifacts":             in_artifacts,
            "in_code":                  in_code,
            "lifecycle_status":         lifecycle,
            "truth_classification":     truth,
            "db_row_count":             db_row_count,
            "truth_level_counts":       tl_counts,
            "replay_display_semantics": display,
            "coverage_status":          coverage,
            "risk_flags":               risk_flags,
            "notes":                    notes,
        })

    # ── Coverage gaps ────────────────────────────────────────────────────────
    coverage_gaps = []
    for s in strategies:
        sid = s["strategy_id"]
        lc  = s["lifecycle_status"]
        if s["in_db"] and not s["in_registry"]:
            coverage_gaps.append({
                "strategy_id": sid,
                "gap_type": "db_only",
                "recommended_next_action":
                    "Operator review: determine if this strategy should be added to registry "
                    "or classified as superseded research artifact.",
            })
        elif not s["in_db"] and s["in_artifacts"] and not s["in_registry"]:
            coverage_gaps.append({
                "strategy_id": sid,
                "gap_type": "artifact_only",
                "recommended_next_action":
                    "Artifact-only strategy: no DB rows and not in registry. "
                    "Candidate for research archive classification (not replay-covered).",
            })
        elif s["in_registry"] and not s["in_db"] and sid not in V3_TOMBSTONE_IDS:
            coverage_gaps.append({
                "strategy_id": sid,
                "gap_type": "registry_without_rows",
                "recommended_next_action":
                    "Strategy is in registry but has zero DB rows. "
                    "If lifecycle is ONLINE/OFFLINE: investigate missing replay run. "
                    "If REJECTED with no artifact: tombstone display only.",
            })
        elif lc == "UNKNOWN":
            coverage_gaps.append({
                "strategy_id": sid,
                "gap_type": "unknown_lifecycle",
                "recommended_next_action":
                    "Lifecycle unknown: needs operator to classify as "
                    "REJECTED/RETIRED/OFFLINE/OBSERVATION or confirm as research artifact.",
            })
        elif sid in NOISE_IDS:
            coverage_gaps.append({
                "strategy_id": sid,
                "gap_type": "ambiguous_duplicate",
                "recommended_next_action":
                    "Generic/noise ID — likely internal test placeholder. "
                    "Should not be included in the strategy universe denominator.",
            })

    # ── Summary ──────────────────────────────────────────────────────────────
    total              = len(strategies)
    canonical_count    = sum(1 for s in strategies if s["in_registry"])
    db_count           = sum(1 for s in strategies if s["in_db"])
    artifact_count     = sum(1 for s in strategies if s["in_artifacts"] and not s["in_registry"] and not s["in_db"])
    code_only_count    = sum(1 for s in strategies if s["in_code"] and not s["in_registry"] and not s["in_db"] and not s["in_artifacts"])
    unknown_lc_count   = sum(1 for s in strategies if s["lifecycle_status"] == "UNKNOWN")
    covered_count      = sum(1 for s in strategies if s["coverage_status"] == "COVERED")
    gap_count          = len(coverage_gaps)

    try:
        import subprocess
        base_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(repo_root), text=True
        ).strip()
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(repo_root), text=True
        ).strip()
    except Exception:
        base_commit = "unknown"
        branch = "unknown"

    return {
        "generated_at":          datetime.datetime.utcnow().isoformat() + "Z",
        "source_branch":         branch,
        "base_commit":           base_commit,
        "final_classification":  "P1_STRATEGY_UNIVERSE_INVENTORY_READY",
        "summary": {
            "total_unique_strategy_candidates": total,
            "canonical_registry_count":         canonical_count,
            "db_distinct_strategy_count":       db_count,
            "artifact_strategy_count":          artifact_count,
            "code_only_strategy_count":         code_only_count,
            "unknown_lifecycle_count":          unknown_lc_count,
            "replay_covered_count":             covered_count,
            "coverage_gap_count":               gap_count,
        },
        "strategies":     strategies,
        "coverage_gaps":  coverage_gaps,
    }


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------

def write_csv(data: dict, csv_path: Path) -> None:
    HEADERS = [
        "strategy_id", "normalized_strategy_id", "display_name",
        "sources", "in_registry", "in_db", "in_artifacts", "in_code",
        "lifecycle_status", "truth_classification", "db_row_count",
        "replay_display_semantics", "coverage_status", "risk_flags", "notes",
    ]
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS, extrasaction="ignore")
        writer.writeheader()
        for s in data["strategies"]:
            row = dict(s)
            row["sources"]     = "|".join(s.get("sources", []))
            row["risk_flags"]  = "|".join(s.get("risk_flags", []))
            writer.writerow(row)
    print(f"[INFO] CSV written: {csv_path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="P1 Strategy Universe Inventory (read-only)")
    parser.add_argument("--db",       default=str(DEFAULT_DB),   help="Path to lottery_v2.db")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON), help="JSON output path")
    parser.add_argument("--csv-out",  default=str(DEFAULT_CSV),  help="CSV output path")
    args = parser.parse_args()

    db_path   = Path(args.db)
    json_path = Path(args.json_out)
    csv_path  = Path(args.csv_out)

    data = build_inventory(db_path, REPO_ROOT)

    s = data["summary"]
    print(f"Strategy universe total:   {s['total_unique_strategy_candidates']}")
    print(f"Canonical registry:        {s['canonical_registry_count']}")
    print(f"DB distinct strategies:    {s['db_distinct_strategy_count']}")
    print(f"Artifact-only strategies:  {s['artifact_strategy_count']}")
    print(f"Unknown lifecycle:         {s['unknown_lifecycle_count']}")
    print(f"Replay COVERED:            {s['replay_covered_count']}")
    print(f"Coverage gaps:             {s['coverage_gap_count']}")
    print(f"Final classification: {data['final_classification']}")

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"[INFO] JSON written: {json_path}", file=sys.stderr)

    write_csv(data, csv_path)


if __name__ == "__main__":
    main()
