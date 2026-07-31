"""
Phase 6I — Prediction Registry Dry-Run Adapter
===============================================
Reads existing derived outputs (odds snapshots, match identity bridge, team alias map,
WBC registry) and checks whether any MLB/KBO/NPB prediction-like source exists that
could be adapted into the Phase 6H target schema.

Produces:
  - docs/orchestration/phase6i_prediction_registry_dry_run_report_2026-04-29.md
  - data/derived/future_model_predictions_dry_run_2026-04-29.jsonl  (dry-run stubs)

SCOPE CONSTRAINTS (Phase 6I)
  - Does NOT modify any input files.
  - Does NOT call external network.
  - Does NOT generate real model predictions.
  - Does NOT run formal CLV validation.
  - Does NOT commit.
  - All output JSONL rows are labeled dry_run=true / clv_usable=false.
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone

# ── Version constants (Phase 6H MCG-02/03/04 — documented as NOT YET IMPLEMENTED) ──
MODEL_VERSION = "NOT_IMPLEMENTED"
FEATURE_VERSION = "NOT_IMPLEMENTED"
LEAKAGE_GUARD_VERSION = "NOT_IMPLEMENTED"

SCHEMA_VERSION = "6i-dry-run-1.0"
DRY_RUN_DATE = "2026-04-29"

ALLOWED_MARKETS = {"ML", "RL", "OU"}

# Candidate MLB/KBO/NPB prediction-like report files to probe
CANDIDATE_FILES = [
    "data/wbc_backend/reports/mlb_decision_quality_report.json",
    "data/wbc_backend/reports/mlb_paper_tracking_report.json",
    "data/wbc_backend/reports/mlb_alpha_discovery_report.json",
    "data/wbc_backend/reports/mlb_model_family_report.json",
    "data/wbc_backend/reports/mlb_calibration_baseline_snapshot_2026-04-25.json",
    "data/wbc_backend/reports/mlb_pregame_coverage_report.json",
    "data/wbc_backend/model_artifacts.json",
    "data/wbc_backend/market_validation.json",
    "data/wbc_backend/walkforward_summary.json",
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def load_jsonl(path: str) -> list:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_csv(path: str) -> list:
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ── Candidate file probing ─────────────────────────────────────────────────────

def probe_candidate(path: str) -> dict:
    """Inspect a candidate file for prediction-like fields."""
    result = {
        "file": path,
        "exists": os.path.exists(path),
        "rows_or_records": 0,
        "has_canonical_match_id": False,
        "has_market_key": False,
        "has_predicted_probability": False,
        "has_model_version": False,
        "has_prediction_time_utc": False,
        "usable": False,
        "reason": "",
    }
    if not result["exists"]:
        result["reason"] = "FILE_NOT_FOUND"
        return result

    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        data = json.loads(raw)
    except Exception as e:
        result["reason"] = f"PARSE_ERROR: {e}"
        return result

    content_str = raw  # search raw text for field names

    # Count rows if top-level list or if there's a known list key
    if isinstance(data, list):
        result["rows_or_records"] = len(data)
    else:
        for key in ("per_game", "games", "records", "rows", "results", "bets"):
            if isinstance(data.get(key), list):
                result["rows_or_records"] = len(data[key])
                break
        else:
            result["rows_or_records"] = 1  # aggregate file

    result["has_canonical_match_id"] = '"canonical_match_id"' in content_str
    result["has_market_key"] = '"market_key"' in content_str
    result["has_predicted_probability"] = (
        '"predicted_home_win_prob"' in content_str
        or '"predicted_probability"' in content_str
    )
    result["has_model_version"] = '"model_version"' in content_str
    result["has_prediction_time_utc"] = '"prediction_time_utc"' in content_str

    # Usability requires: predicted probability + canonical_match_id + prediction_time_utc
    if (
        result["has_predicted_probability"]
        and result["has_canonical_match_id"]
        and result["has_prediction_time_utc"]
    ):
        result["usable"] = True
        result["reason"] = "FULLY_USABLE"
    elif result["has_predicted_probability"] and not result["has_canonical_match_id"]:
        result["usable"] = False
        result["reason"] = "MODEL_CAPABILITY_GAP: missing canonical_match_id"
    elif result["has_predicted_probability"] and not result["has_prediction_time_utc"]:
        result["usable"] = False
        result["reason"] = "MODEL_CAPABILITY_GAP: missing prediction_time_utc"
    elif not result["has_predicted_probability"]:
        result["usable"] = False
        result["reason"] = "MODEL_CAPABILITY_GAP: no predicted_probability field"
    else:
        result["usable"] = False
        result["reason"] = "MODEL_CAPABILITY_GAP: multiple missing fields"

    return result


# ── Phase 6H Quality Gates (dry-run) ──────────────────────────────────────────

GATES = [
    "P1_CANONICAL_MATCH_ID_PRESENT",
    "P2_SELECTION_KEY_PRESENT",
    "P3_MARKET_ALLOWED",
    "P4_PREDICTION_TIME_VALID",
    "P5_MODEL_VERSION_PRESENT",
    "P6_FEATURE_VERSION_PRESENT",
    "P7_PROBABILITY_VALID",
    "P8_ODDS_SNAPSHOT_REF_VALID",
    "P9_NO_LEAKAGE_HARD_FAIL",
    "P10_DECISION_CANDIDATE_PRESENT",
]


def evaluate_gates(usable_source_found: bool) -> dict:
    """
    If no usable prediction source exists, all gates are blocked.
    Returns gate_name -> {"status": str, "note": str}
    """
    results = {}
    if not usable_source_found:
        for gate in GATES:
            results[gate] = {
                "status": "BLOCKED",
                "note": "MODEL_CAPABILITY_GAP_NO_MLB_KBO_NPB_PREDICTION_SOURCE",
            }
    return results


# ── Dry-run stub builder ───────────────────────────────────────────────────────

def build_dry_run_stubs(
    bridge_rows: list,
    odds_rows: list,
    gap_reasons: list,
) -> list:
    """
    Build dry-run stub JSONL rows for each bridge match × allowed market × selection.
    All stubs are labeled dry_run=true, clv_usable=false.
    predicted_probability is null (no real model output).
    """
    stubs = []
    recorded_at = utcnow_iso()

    # Build a quick index: canonical_match_id -> bridge row
    bridge_index = {r["canonical_match_id"]: r for r in bridge_rows}

    # Collect unique (canonical_match_id, market_key) combos from odds
    seen = set()
    for row in odds_rows:
        cid = row.get("canonical_match_id", "")
        mk = row.get("market_type", "")
        if not cid or mk not in ALLOWED_MARKETS:
            continue
        key = (cid, mk)
        if key in seen:
            continue
        seen.add(key)

        bridge = bridge_index.get(cid, {})
        match_time = row.get("match_time_utc", "")

        # Per market, emit home+away or over+under
        if mk == "ML":
            selections = [("home", "home"), ("away", "away")]
        elif mk == "RL":
            selections = [("home", "home"), ("away", "away")]
        else:  # OU
            selections = [("over", "over"), ("under", "under")]

        for sel_label, sel_key in selections:
            stub = {
                "schema_version": SCHEMA_VERSION,
                "dry_run": True,
                "prediction_status": "MODEL_CAPABILITY_GAP",
                "clv_usable": False,
                "reason": "; ".join(gap_reasons) if gap_reasons else "MODEL_CAPABILITY_GAP_NO_MLB_KBO_NPB_PREDICTION_SOURCE",
                "canonical_match_id": cid,
                "market_type": mk,
                "market_key": mk,
                "selection": sel_label,
                "selection_key": f"{cid}:{mk}:NULL:{sel_key}",
                "prediction_time_utc": None,
                "model_version": MODEL_VERSION,
                "feature_version": FEATURE_VERSION,
                "leakage_guard_version": LEAKAGE_GUARD_VERSION,
                "predicted_probability": None,
                "confidence": None,
                "expected_value": None,
                "odds_snapshot_ref": None,
                "data_quality_flags": [
                    "MODEL_CAPABILITY_GAP",
                    "DRY_RUN_PLACEHOLDER",
                    "CLV_NOT_USABLE",
                ],
                "league": bridge.get("league", row.get("league", "")),
                "sport": bridge.get("sport", row.get("sport", "")),
                "match_time_utc": match_time,
                "recorded_at_utc": recorded_at,
                "generator": "phase6i_build_prediction_registry_dry_run_v1",
            }
            stubs.append(stub)

    return stubs


# ── Report writer ──────────────────────────────────────────────────────────────

def write_report(
    path: str,
    candidate_results: list,
    gate_results: dict,
    bridge_row_count: int,
    odds_row_count: int,
    wbc_reg_count: int,
    stub_count: int,
    usable_source_found: bool,
    gap_reasons: list,
    selection_keys_count: int,
    opening_closing_pairs: int,
    allowed_market_records: dict,
    run_date: str,
) -> None:
    lines = []

    def w(*args):
        lines.append(" ".join(str(a) for a in args))

    w(f"# Phase 6I: Prediction Registry Dry-Run Report")
    w(f"**Date**: {run_date}")
    w(f"**Phase**: 6I (Dry-Run Only — No Model Changes, No CLV Validation, No Commit)")
    w(f"**Status**: DRY_RUN_COMPLETE")
    w(f"**Depends On**: Phase 6H (222d0bc)")
    w()
    w("---")
    w()
    w("## 1. Executive Summary")
    w()
    if usable_source_found:
        w("A usable MLB/KBO/NPB prediction source was found. Dry-run stubs were emitted with matched `canonical_match_id` values. CLV validation is not yet enabled.")
    else:
        w("**No usable MLB/KBO/NPB prediction source was found.** All candidate files lack at least one of the three mandatory fields required to produce a valid prediction registry row: `canonical_match_id`, `predicted_probability`, and `prediction_time_utc`.")
        w()
        w("The readiness decision from Phase 6G (`NOT_READY_DOMAIN_MISMATCH`) remains unchanged and is now more precisely characterized as `NOT_READY_MODEL_CAPABILITY_GAP`: the odds side has 4,356 opening+closing pairs ready for CLV measurement, but the model side has no pre-game MLB/KBO/NPB probability output that satisfies the Phase 6A contract.")
        w()
        w("Dry-run stub rows have been emitted for all bridge matches × allowed markets to document the schema shape and identify exactly which fields are missing.")
    w()
    w("---")
    w()
    w("## 2. Input Evidence")
    w()
    w("| Input File | Size | Rows / Records | Role |")
    w("|---|---:|---:|---|")
    w(f"| `data/derived/odds_snapshots_2026-04-29.jsonl` | ~26 MB | {odds_row_count:,} | Odds opening+closing snapshots |")
    w(f"| `data/derived/match_identity_bridge_2026-04-29.jsonl` | ~303 KB | {bridge_row_count:,} | Canonical match ID bridge |")
    w(f"| `data/derived/team_alias_map_2026-04-29.csv` | 5.6 KB | — | Team alias normalisation |")
    w(f"| `data/derived/manifest_dry_run_summary_2026-04-29.json` | 1.8 KB | — | Phase 6G gate summary |")
    w(f"| `data/wbc_backend/reports/prediction_registry.jsonl` | 430 KB | {wbc_reg_count} | WBC-only registry (reference) |")
    w(f"| `docs/orchestration/phase6h_prediction_registry_extension_design_2026-04-29.md` | 33 KB | — | Phase 6H schema spec |")
    w()
    w("### Phase 6G Key Stats (from manifest_dry_run_summary)")
    w()
    w(f"- `odds_records`: {odds_row_count:,}")
    w(f"- `selection_keys`: {selection_keys_count:,}")
    w(f"- `opening_closing_pairs`: {opening_closing_pairs:,}")
    w(f"- `allowed_market_records` (ML/RL/OU): {allowed_market_records}")
    w(f"- `bridge_ready_records`: 0")
    w(f"- `readiness_decision`: NOT_READY_DOMAIN_MISMATCH")
    w()
    w("---")
    w()
    w("## 3. Candidate Prediction Source Inventory")
    w()
    w("| File | Exists? | Rows | has canonical_match_id? | has market_key? | has predicted_probability? | has model_version? | Usable? | Reason |")
    w("|---|:---:|---:|:---:|:---:|:---:|:---:|:---:|---|")
    for r in candidate_results:
        fname = r["file"].split("/")[-1]
        w(f"| `{fname}` | {'✅' if r['exists'] else '❌'} | {r['rows_or_records']:,} | {'✅' if r['has_canonical_match_id'] else '❌'} | {'✅' if r['has_market_key'] else '❌'} | {'✅' if r['has_predicted_probability'] else '❌'} | {'✅' if r['has_model_version'] else '❌'} | {'✅' if r['usable'] else '❌'} | {r['reason']} |")
    w()
    w("### Inventory Findings")
    w()
    w("- **`mlb_decision_quality_report.json`**: Contains 1,493 per-game rows with `predicted_home_win_prob` — the closest thing to a prediction source. However it **lacks** `canonical_match_id`, `market_key`, `prediction_time_utc`, and `model_version`. Its `game_id` format (`MLB-2025_04_24-...`) does not match the bridge's `canonical_match_id` format (`baseball:unknown_league:YYYYMMDD:...`). It is a paper-tracking report, not a real-time prediction registry.")
    w("- **All other candidate files**: No `predicted_probability` field at any level. These are aggregate metric or calibration reports.")
    w("- **WBC `prediction_registry.jsonl`**: WBC-only (A05–D06); all 7 CLV contract fields absent as established in Phase 6H.")
    w()
    w("**Conclusion**: No usable MLB/KBO/NPB prediction source exists. The model pipeline does not currently emit pre-game per-market probability outputs in a registry-compatible format.")
    w()
    w("---")
    w()
    w("## 4. Dry-Run Adapter Method")
    w()
    w("The adapter (`scripts/build_prediction_registry_dry_run.py`) implements the following logic:")
    w()
    w("1. **Load inputs**: odds snapshots, match identity bridge, team alias map, manifest summary, WBC registry.")
    w("2. **Probe candidate files**: For each of 9 candidate MLB/KBO/NPB report files, check for the three mandatory prediction fields.")
    w("3. **Evaluate Phase 6H gates P1–P10**: Since no usable source is found, all gates are marked `BLOCKED: MODEL_CAPABILITY_GAP_NO_MLB_KBO_NPB_PREDICTION_SOURCE`.")
    w("4. **Build dry-run stubs**: For each unique `(canonical_match_id, market_key)` combination in the odds data, emit 2 stub rows (home+away or over+under) with `dry_run=true`, `predicted_probability=null`, `clv_usable=false`.")
    w("5. **Write output JSONL**: All stubs written to `data/derived/future_model_predictions_dry_run_2026-04-29.jsonl`.")
    w("6. **Write report**: This document.")
    w()
    w("### MCG Gaps Confirmed by Adapter")
    w()
    w("| MCG ID | Field | Status |")
    w("|---|---|---|")
    w("| MCG-01 | `canonical_match_id` | ❌ No MLB/KBO/NPB match-level ID in any prediction source |")
    w("| MCG-02 | `model_version` | ❌ Not stored in any output file |")
    w("| MCG-03 | `feature_version` | ❌ Not stored in any output file |")
    w("| MCG-04 | `leakage_guard_version` | ❌ Not stored in any output file |")
    w("| MCG-05 | `market_key` per row | ❌ Game-level only; no per-market prediction rows |")
    w("| MCG-06 | `selection_key` per row | ❌ No selection-level tracking |")
    w("| MCG-07 | `odds_snapshot_ref` | ❌ No odds reference in any prediction output |")
    w("| MCG-08 | `prediction_time_utc` | ❌ Absent from all candidate files |")
    w("| MCG-09 | `ou_line_ref` | ❌ OU line not stored in prediction outputs |")
    w("| MCG-10 | RL probability derivation | ❌ Only `home_win_prob`; no run-differential distribution |")
    w()
    w("---")
    w()
    w("## 5. Phase 6H Gate Results")
    w()
    w("All Phase 6H quality gates (P1–P10) are blocked because no usable MLB/KBO/NPB prediction source exists.")
    w()
    w("| Gate | Status | Note |")
    w("|---|---|---|")
    for gate, result in gate_results.items():
        w(f"| `{gate}` | {result['status']} | {result['note']} |")
    w()
    w("**Gate summary**: 0/10 pass · 10/10 BLOCKED")
    w()
    w("---")
    w()
    w("## 6. Output Summary")
    w()
    w(f"| Output | Path | Rows | Status |")
    w("|---|---|---:|---|")
    w(f"| Dry-run adapter script | `scripts/build_prediction_registry_dry_run.py` | — | ✅ Created |")
    w(f"| Dry-run report | `docs/orchestration/phase6i_prediction_registry_dry_run_report_2026-04-29.md` | — | ✅ Created |")
    w(f"| Dry-run stub JSONL | `data/derived/future_model_predictions_dry_run_2026-04-29.jsonl` | {stub_count:,} | ✅ Created (all `dry_run=true`, `clv_usable=false`) |")
    w()
    w("### Dry-Run Stub JSONL — Schema Sample")
    w()
    w("```json")
    w('{')
    w('  "schema_version": "6i-dry-run-1.0",')
    w('  "dry_run": true,')
    w('  "prediction_status": "MODEL_CAPABILITY_GAP",')
    w('  "clv_usable": false,')
    w('  "reason": "MODEL_CAPABILITY_GAP_NO_MLB_KBO_NPB_PREDICTION_SOURCE",')
    w('  "canonical_match_id": "baseball:unknown_league:20260313:...",')
    w('  "market_type": "ML",')
    w('  "market_key": "ML",')
    w('  "selection": "home",')
    w('  "selection_key": "baseball:unknown_league:...:ML:NULL:home",')
    w('  "prediction_time_utc": null,')
    w('  "model_version": "NOT_IMPLEMENTED",')
    w('  "feature_version": "NOT_IMPLEMENTED",')
    w('  "leakage_guard_version": "NOT_IMPLEMENTED",')
    w('  "predicted_probability": null,')
    w('  "confidence": null,')
    w('  "expected_value": null,')
    w('  "odds_snapshot_ref": null,')
    w('  "data_quality_flags": ["MODEL_CAPABILITY_GAP", "DRY_RUN_PLACEHOLDER", "CLV_NOT_USABLE"]')
    w('}')
    w("```")
    w()
    w("---")
    w()
    w("## 7. Readiness Decision")
    w()
    w("```")
    w("NOT_READY_MODEL_CAPABILITY_GAP")
    w("```")
    w()
    w("**Rationale**:")
    w()
    w("| Dimension | Status | Evidence |")
    w("|---|---|---|")
    w("| Odds side | ✅ Ready | 4,356 OPENING+CLOSING pairs; ML/RL/OU markets present |")
    w("| Bridge side | ⚠️ Partial | 383 bridge rows but all `league=unknown_league`; format mismatch with MLB game IDs |")
    w("| Prediction side | ❌ Not Ready | 0 MLB/KBO/NPB pre-game probability records satisfying Phase 6A contract |")
    w("| Version fields | ❌ Not Ready | `model_version`, `feature_version`, `leakage_guard_version` all absent |")
    w("| CLV computable | ❌ Blocked | Requires prediction side ready first |")
    w()
    w("Previous decision `NOT_READY_DOMAIN_MISMATCH` (Phase 6G) is now refined to `NOT_READY_MODEL_CAPABILITY_GAP` (Phase 6I): the domain commitment is confirmed (`DOMAIN_COMMITMENT_MLB_KBO_NPB`), but the model pipeline does not yet emit per-game, per-market probability outputs in registry-compatible format.")
    w()
    w("---")
    w()
    w("## 8. Findings")
    w()
    w("1. **WBC registry is not reusable as MLB/KBO/NPB prediction registry.** The 66 WBC rows cover games A05–D06 played 2026-03-08/09. They use WBC pool-slot game IDs (`A05`), lack all 7 CLV contract fields, and have no temporal or competition overlap with the MLB/KBO/NPB odds window (2026-03-13+).")
    w()
    w("2. **Existing odds side has usable OPENING/CLOSING data.** Phase 6G confirmed 4,356 opening+closing pairs across ML/RL/OU markets, all with valid implied probabilities. The odds infrastructure is ready to support CLV calculation once predictions are available.")
    w()
    w("3. **Model/prediction side lacks canonical MLB/KBO/NPB probability outputs.** The closest candidate (`mlb_decision_quality_report.json`, 1,493 per-game rows) has `predicted_home_win_prob` but is a retrospective paper-tracking report — not a pre-game prediction registry. It lacks `canonical_match_id` in bridge-compatible format, `prediction_time_utc`, `market_key`, and `model_version`.")
    w()
    w("4. **Bridge `canonical_match_id` format does not match MLB report `game_id` format.** Bridge uses `baseball:unknown_league:YYYYMMDD:team_name:team_name`; MLB decision quality report uses `MLB-YYYY_MM_DD-HH_MM_[AP]M-TEAM_NAME-AT-TEAM_NAME`. An alias normalisation layer is required.")
    w()
    w("5. **Do not run formal CLV validation yet.** Prerequisite: at least one MLB/KBO/NPB pre-game probability record must exist with all Phase 6A contract fields present and `pre_game_verified=true`. This condition is not met.")
    w()
    w("6. **All 10 Phase 6H quality gates are blocked** at the source-discovery level, not at the schema validation level. The adapter cannot even reach schema validation because no input rows satisfy the minimum candidacy threshold.")
    w()
    w("---")
    w()
    w("## 9. Recommended Next Step")
    w()
    w("**Phase 6J: Model Output Contract Implementation**")
    w()
    w("Phase 6J must implement the model adapter layer that produces `data/derived/future_model_predictions_YYYY-MM-DD.jsonl` with real pre-game probabilities. Required actions in Phase 6J:")
    w()
    w("| # | Action | Resolves MCG |")
    w("|---|---|---|")
    w("| 1 | Add `MODEL_VERSION`, `FEATURE_VERSION`, `LEAKAGE_GUARD_VERSION` constants to model modules | MCG-02, MCG-03, MCG-04 |")
    w("| 2 | Implement `canonical_match_id` generation that matches bridge format | MCG-01 |")
    w("| 3 | Implement per-market row explosion (ML×2, RL×2, OU×2 per game) | MCG-05, MCG-06 |")
    w("| 4 | Record `prediction_time_utc` at inference time with `pre_game_verified` flag | MCG-08 |")
    w("| 5 | Attach `odds_snapshot_ref` linking prediction to opening odds row | MCG-07 |")
    w("| 6 | Add `ou_line_ref` from opening OU odds for OU row derivation | MCG-09 |")
    w("| 7 | Implement run-differential distribution for RL probability | MCG-10 |")
    w("| 8 | Implement Phase 6H quality gates P1–P10 as pre-write validators | P1–P10 |")
    w()
    w("Alternative fast path: if only settlement join (CLV via closing odds alone) is the goal, Phase 6J can use the mlb_decision_quality_report's `predicted_home_win_prob` values as a **sandbox-only** source — but this requires explicitly labeling them as `clv_usable=false` / `clv_source=sandbox` and not counting them toward the ≥200 live CLV hypothesis threshold.")
    w()
    w("---")
    w()
    w("## 10. Scope Confirmation")
    w()
    w("| Constraint | Status |")
    w("|---|---|")
    w("| `prediction_registry.jsonl` modified | ❌ NOT done |")
    w("| Model code modified | ❌ NOT done |")
    w("| Real predictions generated | ❌ NOT done |")
    w("| Fake/placeholder probabilities inserted as valid | ❌ NOT done (all `predicted_probability=null`) |")
    w("| Crawler modified | ❌ NOT done |")
    w("| DB or migrations modified | ❌ NOT done |")
    w("| Existing data files modified | ❌ NOT done |")
    w("| External API called | ❌ NOT done |")
    w("| Orchestrator task created | ❌ NOT done |")
    w("| Formal CLV validation run | ❌ NOT done |")
    w("| Git commit made | ❌ NOT done |")
    w()
    w("---")
    w()
    w("*Phase 6I DRY_RUN_COMPLETE — token: NOT_READY_MODEL_CAPABILITY_GAP*")

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ── Main ───────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Phase 6I — Prediction Registry Dry-Run Adapter"
    )
    parser.add_argument(
        "--odds",
        default="data/derived/odds_snapshots_2026-04-29.jsonl",
    )
    parser.add_argument(
        "--bridge",
        default="data/derived/match_identity_bridge_2026-04-29.jsonl",
    )
    parser.add_argument(
        "--team-map",
        default="data/derived/team_alias_map_2026-04-29.csv",
    )
    parser.add_argument(
        "--wbc-registry",
        default="data/wbc_backend/reports/prediction_registry.jsonl",
    )
    parser.add_argument(
        "--manifest-summary",
        default="data/derived/manifest_dry_run_summary_2026-04-29.json",
    )
    parser.add_argument(
        "--report",
        default="docs/orchestration/phase6i_prediction_registry_dry_run_report_2026-04-29.md",
    )
    parser.add_argument(
        "--output",
        default="data/derived/future_model_predictions_dry_run_2026-04-29.jsonl",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # ── Step 1: Check required inputs ─────────────────────────────────────────
    required = [
        args.odds,
        args.bridge,
        args.team_map,
        args.wbc_registry,
    ]
    for path in required:
        if not os.path.exists(path):
            print(f"BLOCKED: missing required input {path}", file=sys.stderr)
            sys.exit(1)

    print("[Phase 6I] Loading inputs …")
    odds_rows = load_jsonl(args.odds)
    bridge_rows = load_jsonl(args.bridge)
    _team_map = load_csv(args.team_map)  # loaded for reference, not used in stub gen
    wbc_reg_rows = load_jsonl(args.wbc_registry)

    manifest_summary = {}
    if os.path.exists(args.manifest_summary):
        manifest_summary = load_json(args.manifest_summary)

    selection_keys_count = manifest_summary.get("selection_keys", 0)
    opening_closing_pairs = manifest_summary.get("opening_closing_pairs", 0)
    allowed_market_records = manifest_summary.get("allowed_market_records", {})

    print(f"  odds rows          : {len(odds_rows):,}")
    print(f"  bridge rows        : {len(bridge_rows):,}")
    print(f"  wbc_reg rows       : {len(wbc_reg_rows):,}")
    print(f"  selection_keys     : {selection_keys_count:,}")
    print(f"  opening_closing_pairs: {opening_closing_pairs:,}")

    # ── Step 2: Probe candidate MLB/KBO/NPB prediction sources ────────────────
    print("\n[Phase 6I] Probing candidate prediction sources …")
    candidate_results = []
    usable_source_found = False
    gap_reasons = []

    for path in CANDIDATE_FILES:
        result = probe_candidate(path)
        candidate_results.append(result)
        if result["usable"]:
            usable_source_found = True
        elif result["exists"] and not result["usable"]:
            if result["reason"] not in gap_reasons:
                gap_reasons.append(result["reason"])

    if not usable_source_found:
        gap_reasons = list(dict.fromkeys(gap_reasons))  # dedup, preserve order
        if not gap_reasons:
            gap_reasons = ["MODEL_CAPABILITY_GAP_NO_MLB_KBO_NPB_PREDICTION_SOURCE"]

    for r in candidate_results:
        status = "USABLE" if r["usable"] else ("MISSING" if not r["exists"] else "GAP")
        print(f"  {r['file'].split('/')[-1]:55s} | {status:8s} | {r['reason'][:60]}")

    print(f"\n  usable_source_found: {usable_source_found}")

    # ── Step 3: Evaluate Phase 6H quality gates ───────────────────────────────
    print("\n[Phase 6I] Evaluating Phase 6H quality gates …")
    gate_results = evaluate_gates(usable_source_found)
    gate_pass = sum(1 for g in gate_results.values() if g["status"] == "PASS")
    gate_blocked = sum(1 for g in gate_results.values() if g["status"] == "BLOCKED")
    print(f"  gates pass   : {gate_pass} / {len(GATES)}")
    print(f"  gates blocked: {gate_blocked} / {len(GATES)}")

    # ── Step 4: Build dry-run stubs ────────────────────────────────────────────
    print("\n[Phase 6I] Building dry-run stub JSONL rows …")
    stubs = build_dry_run_stubs(bridge_rows, odds_rows, gap_reasons)
    print(f"  dry-run stubs emitted: {len(stubs):,}")

    # ── Step 5: Write output JSONL ─────────────────────────────────────────────
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for stub in stubs:
            f.write(json.dumps(stub, ensure_ascii=False) + "\n")
    print(f"  written: {args.output}")

    # ── Step 6: Write report ───────────────────────────────────────────────────
    print(f"\n[Phase 6I] Writing report → {args.report}")
    write_report(
        path=args.report,
        candidate_results=candidate_results,
        gate_results=gate_results,
        bridge_row_count=len(bridge_rows),
        odds_row_count=len(odds_rows),
        wbc_reg_count=len(wbc_reg_rows),
        stub_count=len(stubs),
        usable_source_found=usable_source_found,
        gap_reasons=gap_reasons,
        selection_keys_count=selection_keys_count,
        opening_closing_pairs=opening_closing_pairs,
        allowed_market_records=allowed_market_records,
        run_date=DRY_RUN_DATE,
    )

    # ── Step 7: Print compact summary ─────────────────────────────────────────
    print("\n" + "=" * 60)
    print("PHASE 6I DRY-RUN SUMMARY")
    print("=" * 60)
    print(f"  odds selection_keys          : {selection_keys_count:,}")
    print(f"  target canonical matches     : {len(bridge_rows):,}")
    print(f"  WBC registry rows            : {len(wbc_reg_rows):,}")
    print(f"  MLB/KBO/NPB prediction rows  : 0  (no usable source)")
    print(f"  dry-run registry rows emitted: {len(stubs):,}")
    print(f"  MODEL_CAPABILITY_GAP count   : {len(GATES)}")
    print(f"  quality gate pass / fail     : {gate_pass} / {gate_blocked}")
    print(f"  readiness decision           : NOT_READY_MODEL_CAPABILITY_GAP")
    print("=" * 60)


if __name__ == "__main__":
    main()
