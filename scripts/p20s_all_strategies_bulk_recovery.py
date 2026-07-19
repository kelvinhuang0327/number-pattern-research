#!/usr/bin/env python3
"""P20S Big Lotto governed-identity recovery and 20-ticket backtest.

The runner separates raw evidence records from governed strategy identities,
reuses the reviewed P20C constructor/backtest contract, and fails closed when
an implementation cannot be tied to a reproducible historical-cutoff entrypoint.
Large draw-level details live only in caller-selected resumable checkpoints;
the published result is a compact, deterministic evidence bundle.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import gzip
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import p20c_strategy_preserving_20_ticket_backtest as p20c  # noqa: E402


TASK_ID = "P20S_ALL_STRATEGIES_BULK_RECOVERY_BACKTEST"
RUNNER_VERSION = "p20s-v1"
EXPECTED_IDENTITY_COUNT = 39
EXPECTED_EVIDENCE_RECORDS = 607
EXPECTED_RANDOM_BASELINES = 1
EXPECTED_DRAWS = 2125
EXPECTED_COMMON_DRAWS = 2025
DEFAULT_TIMEOUT_SECONDS = 1800
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "outputs" / "research" / "p20s_all_strategies_bulk_recovery"
)
P0_UNIVERSE = REPO_ROOT / "outputs/replay/p0_strategy_universe_inventory_20260711.json"
P24_UNIVERSE = REPO_ROOT / "outputs/replay/p24_full_strategy_universe_inventory_20260521.json"
P356_INVENTORY = REPO_ROOT / "artifacts/P356A_strategy_inventory_all.csv"
P357_RECOVERY = REPO_ROOT / "artifacts/P357B_historical_strategy_recovery_manifest.csv"
P358_RECOVERY = REPO_ROOT / "artifacts/P358A_biglotto_historical_recovery_manifest.csv"
P541B_EVIDENCE = (
    REPO_ROOT
    / "outputs/research/p541b_r2_biglotto_legacy_method_classification_audit_20260711.json"
)

TERMINAL_DISPOSITIONS = {
    "COMPLETE_NATIVE_20",
    "COMPLETE_ADAPTER_20",
    "PARTIAL_BACKTEST",
    "DUPLICATE_ALIAS",
    "EQUIVALENT_IMPLEMENTATION",
    "DOCUMENT_ONLY",
    "MISSING_IMPLEMENTATION",
    "MISSING_ENTRYPOINT",
    "MISSING_ARTIFACT",
    "MISSING_DEPENDENCY",
    "EXTERNAL_STATE_NOT_REPRODUCIBLE",
    "INVALID_OUTPUT",
    "NO_VALID_STRATEGY_SIGNAL",
    "DATA_LEAKAGE_EXCLUDED",
    "UNSAFE_METHOD_EXCLUDED",
    "RESOURCE_LIMIT_REACHED",
    "RUNTIME_FAILURE",
    "UNKNOWN_REQUIRES_OWNER_EVIDENCE",
}

MASTER_FIELDS = (
    "strategy_id",
    "strategy_name",
    "game",
    "governance_status",
    "independent_algorithm_id",
    "alias_of",
    "equivalence_group",
    "current_source_path",
    "historical_source_commit",
    "historical_source_path",
    "implementation_kind",
    "entrypoint",
    "native_ticket_count",
    "strategy_signal_available",
    "supports_historical_cutoff",
    "required_inputs",
    "dependency_status",
    "external_state_dependency",
    "leakage_status",
    "recovery_status",
    "terminal_disposition",
    "evidence",
)

LEDGER_FIELDS = (
    "evidence_record_id",
    "evidence_kind",
    "source_identity",
    "source_path",
    "source_commit",
    "governance_status",
    "resolution_class",
    "resolved_strategy_id",
    "is_strategy_claim",
    "reason",
)

PREFLIGHT_FIELDS = (
    "strategy_id",
    "preflight_status",
    "entrypoint",
    "import_ok",
    "cutoff_contract_ok",
    "target_mutation_invariant",
    "future_mutation_invariant",
    "native_output_valid",
    "final_ticket_count",
    "constructor_metadata_ok",
    "reason",
)

METRIC_FIELDS = (
    "strategy_id",
    "effective_strategy_id",
    "strategy_name",
    "governance_status",
    "independent_algorithm_id",
    "equivalence_group",
    "ranking_group",
    "native_ticket_count",
    "constructed_ticket_count",
    "evaluated_draws",
    "replicates",
    "complete_portfolios",
    "completion_rate",
    "m4plus_hits",
    "m4plus_rate",
    "confidence_interval_95",
    "paired_difference_vs_random",
    "paired_interval_95",
    "credible_random_advantage",
    "runtime_seconds",
    "total_ticket_evaluations",
    "governance_note",
)

REQUIRED_OUTPUTS = (
    "run_manifest.json",
    "strategy_master_inventory.csv",
    "strategy_resolution_ledger.csv",
    "strategy_equivalence_groups.csv",
    "recovered_entrypoints.csv",
    "preflight_results.csv",
    "all_completed_strategy_metrics.csv",
    "newly_recovered_strategy_metrics.csv",
    "m4plus_native_ranking.csv",
    "m4plus_adapter_ranking.csv",
    "m4plus_all_valid_ranking.csv",
    "partial_results.csv",
    "excluded_strategies.csv",
    "failed_strategies.csv",
    "validation_results.json",
    "final_report.md",
)

# These are the only governed additions beyond the current registry/P24 union.
HISTORICAL_IDENTITIES = (
    (
        "history::lottery_api/models/core_satellite.py",
        "core_satellite",
        "lottery_api/models/core_satellite.py",
    ),
    (
        "history::lottery_api/models/social_wisdom_predictor.py",
        "social_wisdom_predictor",
        "lottery_api/models/social_wisdom_predictor.py",
    ),
    (
        "history::lottery_api/models/zone_split.py",
        "zone_split",
        "lottery_api/models/zone_split.py",
    ),
)

RECOVERY_IDENTITIES = {
    "biglotto_p0_2bet": {
        "name": "Big Lotto P0 2-bet",
        "source": "tools/quick_predict.py",
        "entrypoint": "recovered_strategies.biglotto.historical_adapters.adapt_biglotto_p0_2bet",
        "status": "UNKNOWN",
        "native": 2,
        "terminal": "COMPLETE_ADAPTER_20",
        "evidence": "P357B-CURRENT-011; P358 parity acceptable",
    },
    "predict_biglotto_echo_2bet": {
        "name": "Echo-aware deviation 2-bet",
        "source": "tools/predict_biglotto_echo_2bet.py",
        "entrypoint": "recovered_strategies.biglotto.historical_adapters.adapt_predict_biglotto_echo_2bet",
        "status": "UNKNOWN",
        "native": 2,
        "terminal": "COMPLETE_ADAPTER_20",
        "evidence": "P357B-CURRENT-014; P358 parity acceptable",
    },
    "predict_biglotto_echo_phase2": {
        "name": "Adaptive echo phase 2 (3-bet version)",
        "source": "tools/predict_biglotto_echo_phase2.py",
        "entrypoint": "recovered_strategies.biglotto.historical_adapters.adapt_predict_biglotto_echo_phase2_3bet",
        "status": "UNKNOWN",
        "native": 3,
        "terminal": "COMPLETE_ADAPTER_20",
        "evidence": "P357B-CURRENT-015; P358 versioned 2/3-bet parity evidence",
    },
    "predict_biglotto_mixed_3bet": {
        "name": "Deterministic mixed 3-bet",
        "source": "tools/predict_biglotto_mixed_3bet.py",
        "entrypoint": "tools.predict_biglotto_mixed_3bet.mixed_3bet",
        "status": "UNKNOWN",
        "native": 3,
        "terminal": "COMPLETE_ADAPTER_20",
        "evidence": "P357B-CURRENT-016; current pure deterministic callable",
    },
    "biglotto_5bet_orthogonal": {
        "name": "Historical Big Lotto orthogonal 5-bet",
        "source": "tools/quick_predict.py; tools/backtest_biglotto_5bet_ts3markov.py",
        "entrypoint": "recovered_strategies.biglotto.historical_adapters.adapt_biglotto_5bet_orthogonal",
        "status": "UNKNOWN",
        "native": 5,
        "terminal": "PARTIAL_BACKTEST",
        "evidence": "P358/P359 shape-safety only; historical parity not proven",
    },
    "biglotto_zonal_pruning": {
        "name": "Historical Big Lotto zonal pruning",
        "source": "tools/biglotto_zonal_pruning.py; tools/predict_biglotto_zonal.py",
        "entrypoint": "recovered_strategies.biglotto.historical_adapters.adapt_biglotto_zonal_pruning",
        "status": "UNKNOWN",
        "native": 4,
        "terminal": "PARTIAL_BACKTEST",
        "evidence": "P358/P359 shape-safety only; local cluster-pivot replica is not parity proof",
    },
    "biglotto_10bet_combined": {
        "name": "Deleted combined orthogonal/P1 10-bet",
        "source": "tools/backtest_biglotto_10bet_combined.py",
        "entrypoint": "recovered_strategies.biglotto.historical_adapters.adapt_biglotto_10bet_combined",
        "status": "DELETED",
        "native": 10,
        "terminal": "PARTIAL_BACKTEST",
        "historical_commit": "73062646^",
        "evidence": "P357B-HIST-010; P358/P359 shape-safety only",
    },
    "predict_biglotto_regime": {
        "name": "Deleted Big Lotto sum-regime 3-bet",
        "source": "tools/predict_biglotto_regime.py",
        "entrypoint": "recovered_strategies.biglotto.historical_adapters.adapt_predict_biglotto_regime_3bet",
        "status": "DELETED",
        "native": 3,
        "terminal": "PARTIAL_BACKTEST",
        "historical_commit": "73062646^",
        "evidence": "P357B-HIST-011; P358/P359 shape-safety only",
    },
}

ALIAS_OF = {
    "ts3_acb_4bet_biglotto": "biglotto_ts3_acb_4bet",
    "ts3_markov_freq_5bet_biglotto": "biglotto_ts3_markov_freq_5bet",
}

EQUIVALENT_TO = {
    "core_satellite_biglotto": "history::lottery_api/models/core_satellite.py",
    "biglotto_social_wisdom_anti_popularity": "history::lottery_api/models/social_wisdom_predictor.py",
    "biglotto_zone_split_3bet_bet1": "history::lottery_api/models/zone_split.py",
}

EQUIVALENCE_GROUPS = {
    "core_satellite_family": {
        "canonical": "history::lottery_api/models/core_satellite.py",
        "members": (
            "history::lottery_api/models/core_satellite.py",
            "core_satellite_biglotto",
        ),
        "basis": "same CoreSatelliteStrategy implementation; artifact is governance evidence",
    },
    "social_wisdom_family": {
        "canonical": "history::lottery_api/models/social_wisdom_predictor.py",
        "members": (
            "history::lottery_api/models/social_wisdom_predictor.py",
            "biglotto_social_wisdom_anti_popularity",
        ),
        "basis": "registry observation names the historical anti-popularity implementation",
    },
    "zone_split_family": {
        "canonical": "history::lottery_api/models/zone_split.py",
        "members": (
            "history::lottery_api/models/zone_split.py",
            "biglotto_zone_split_3bet_bet1",
        ),
        "basis": "registry observation is a budget/version view of ZoneSplitStrategy",
    },
    "ts3_acb_aliases": {
        "canonical": "biglotto_ts3_acb_4bet",
        "members": ("biglotto_ts3_acb_4bet", "ts3_acb_4bet_biglotto"),
        "basis": "P358B confirms rejected-artifact alias and missing runnable source",
    },
    "ts3_markov_freq_aliases": {
        "canonical": "biglotto_ts3_markov_freq_5bet",
        "members": (
            "biglotto_ts3_markov_freq_5bet",
            "ts3_markov_freq_5bet_biglotto",
        ),
        "basis": "same governed TS3/Markov/frequency 5-bet claim; lineage remains incomplete",
    },
}

SPEC_TO_IDENTITY = {
    "history::lottery_api/models/core_satellite.py": "history::lottery_api/models/core_satellite.py",
    "history::lottery_api/models/social_wisdom_predictor.py": "history::lottery_api/models/social_wisdom_predictor.py",
    "history::lottery_api/models/zone_split.py": "history::lottery_api/models/zone_split.py",
    "registry::biglotto_triple_strike": "biglotto_triple_strike",
    "registry::biglotto_deviation_2bet": "biglotto_deviation_2bet",
    "registry::ts3_regime_3bet": "ts3_regime_3bet",
    "registry::biglotto_echo_aware_3bet": "biglotto_echo_aware_3bet",
    "registry::biglotto_ts3_markov_4bet_w30": "biglotto_ts3_markov_4bet_w30",
    "registry::markov_single_biglotto": "markov_single_biglotto",
    "registry::markov_2bet_biglotto": "markov_2bet_biglotto",
    "registry::bet2_fourier_expansion_biglotto": "bet2_fourier_expansion_biglotto@p42_p280_frozen_code",
    "registry::fourier30_markov30_biglotto": "fourier30_markov30_biglotto",
    "registry::cold_complement_biglotto": "cold_complement_biglotto",
    "registry::coldpool15_biglotto": "coldpool15_biglotto",
    "biglotto_p0_2bet": "biglotto_p0_2bet",
    "predict_biglotto_echo_2bet": "predict_biglotto_echo_2bet",
    "predict_biglotto_echo_phase2": "predict_biglotto_echo_phase2",
    "predict_biglotto_mixed_3bet": "predict_biglotto_mixed_3bet",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _registry_rows() -> dict[str, dict[str, Any]]:
    from lottery_api.models.replay_strategy_registry import list_strategy_lifecycle_metadata

    return {
        row["strategy_id"]: row
        for row in list_strategy_lifecycle_metadata()
        if "BIG_LOTTO" in row["supported_lottery_types"]
    }


def _p24_rows() -> dict[str, dict[str, Any]]:
    payload = json.loads(P24_UNIVERSE.read_text(encoding="utf-8"))
    return {
        row["strategy_id"]: row
        for row in payload["strategies"]
        if row["lottery_type"] == "BIG_LOTTO"
    }


def _equivalence_group(strategy_id: str) -> str:
    for group, definition in EQUIVALENCE_GROUPS.items():
        if strategy_id in definition["members"]:
            return group
    return ""


def _base_master_row(strategy_id: str, name: str) -> dict[str, Any]:
    return {
        "strategy_id": strategy_id,
        "strategy_name": name,
        "game": "BIG_LOTTO",
        "governance_status": "UNKNOWN",
        "independent_algorithm_id": strategy_id,
        "alias_of": "",
        "equivalence_group": _equivalence_group(strategy_id),
        "current_source_path": "",
        "historical_source_commit": "",
        "historical_source_path": "",
        "implementation_kind": "",
        "entrypoint": "",
        "native_ticket_count": "",
        "strategy_signal_available": False,
        "supports_historical_cutoff": False,
        "required_inputs": "strictly-prior BIG_LOTTO draws ordered old-to-new",
        "dependency_status": "NOT_EVALUATED",
        "external_state_dependency": "NONE",
        "leakage_status": "NOT_EVALUATED",
        "recovery_status": "NOT_ATTEMPTED",
        "terminal_disposition": "MISSING_IMPLEMENTATION",
        "evidence": "",
    }


def build_master_inventory() -> list[dict[str, Any]]:
    registry = _registry_rows()
    p24 = _p24_rows()
    rows: list[dict[str, Any]] = []

    for source_id in sorted(set(registry) | set(p24)):
        registry_row = registry.get(source_id, {})
        p24_row = p24.get(source_id, {})
        identities = [source_id]
        if source_id == "bet2_fourier_expansion_biglotto":
            identities = [
                "bet2_fourier_expansion_biglotto@p42_p280_frozen_code",
                "bet2_fourier_expansion_biglotto@rejected_json_historical",
            ]
        for strategy_id in identities:
            row = _base_master_row(
                strategy_id,
                registry_row.get("strategy_name")
                or p24_row.get("display_name")
                or source_id,
            )
            row["governance_status"] = registry_row.get(
                "lifecycle_status", p24_row.get("lifecycle_state", "REJECTED")
            )
            row["current_source_path"] = registry_row.get("source_path", "")
            row["historical_source_path"] = p24_row.get("source_artifact", "") or ""
            row["implementation_kind"] = (
                "registry"
                if registry_row
                else "rejected_strategy_artifact"
            )
            row["evidence"] = "; ".join(
                value
                for value in (
                    "current replay lifecycle registry" if registry_row else "",
                    p24_row.get("source_artifact", "") or "",
                )
                if value
            )
            if strategy_id.endswith("@p42_p280_frozen_code"):
                row["current_source_path"] = "lottery_api/models/p42_wave3_biglotto_adapters.py"
                row["implementation_kind"] = "current_id_reuse_lineage"
                row["entrypoint"] = "lottery_api.models.p42_wave3_biglotto_adapters.predict_fourier_expansion_bet1"
                row["evidence"] += "; P358B confirmed distinct current lineage"
            elif strategy_id.endswith("@rejected_json_historical"):
                row["implementation_kind"] = "historical_id_reuse_lineage"
                row["historical_source_path"] = "rejected/bet2_fourier_expansion_biglotto.json"
                row["evidence"] += "; P358B confirmed distinct historical lineage"
            if source_id in ALIAS_OF:
                row["alias_of"] = ALIAS_OF[source_id]
                row["independent_algorithm_id"] = ALIAS_OF[source_id]
                row["terminal_disposition"] = "DUPLICATE_ALIAS"
                row["recovery_status"] = "RESOLVED_ALIAS"
            if source_id in EQUIVALENT_TO:
                row["independent_algorithm_id"] = EQUIVALENT_TO[source_id]
                row["terminal_disposition"] = "EQUIVALENT_IMPLEMENTATION"
                row["recovery_status"] = "RESOLVED_EQUIVALENT"
            rows.append(row)

    for strategy_id, name, source_path in HISTORICAL_IDENTITIES:
        row = _base_master_row(strategy_id, name)
        row.update(
            {
                "governance_status": "CANDIDATE",
                "current_source_path": source_path,
                "implementation_kind": "p20c_historical_entrypoint",
                "entrypoint": source_path,
                "strategy_signal_available": True,
                "supports_historical_cutoff": True,
                "dependency_status": "AVAILABLE",
                "leakage_status": "PREFLIGHT_REQUIRED",
                "recovery_status": "PREVIOUSLY_COMPLETE_P20C",
                "terminal_disposition": "COMPLETE_ADAPTER_20",
                "evidence": "P20C committed historical backtest identity",
            }
        )
        rows.append(row)

    for strategy_id, definition in sorted(RECOVERY_IDENTITIES.items()):
        row = _base_master_row(strategy_id, definition["name"])
        row.update(
            {
                "governance_status": definition["status"],
                "current_source_path": definition["source"] if definition["status"] != "DELETED" else "",
                "historical_source_commit": definition.get("historical_commit", ""),
                "historical_source_path": definition["source"] if definition["status"] == "DELETED" else "",
                "implementation_kind": "recovered_exact_adapter"
                if definition["terminal"] == "COMPLETE_ADAPTER_20"
                else "shape_safety_adapter_without_parity",
                "entrypoint": definition["entrypoint"],
                "native_ticket_count": definition["native"],
                "strategy_signal_available": definition["terminal"] == "COMPLETE_ADAPTER_20",
                "supports_historical_cutoff": True,
                "dependency_status": "AVAILABLE",
                "leakage_status": "PREFLIGHT_REQUIRED"
                if definition["terminal"] == "COMPLETE_ADAPTER_20"
                else "NOT_RANKABLE_WITHOUT_PARITY",
                "recovery_status": "RECOVERED_ENTRYPOINT"
                if definition["terminal"] == "COMPLETE_ADAPTER_20"
                else "PARTIAL_SHAPE_EVIDENCE",
                "terminal_disposition": definition["terminal"],
                "evidence": definition["evidence"],
            }
        )
        rows.append(row)

    for row in rows:
        if row["terminal_disposition"] in {"DUPLICATE_ALIAS", "EQUIVALENT_IMPLEMENTATION"}:
            continue
        if row["strategy_id"] in SPEC_TO_IDENTITY.values():
            row["strategy_signal_available"] = True
            row["supports_historical_cutoff"] = True
            row["dependency_status"] = "AVAILABLE"
            row["leakage_status"] = "PREFLIGHT_REQUIRED"
            row["entrypoint"] = row["entrypoint"] or "P20C reviewed strategy specification"
            row["recovery_status"] = (
                "RECOVERED_ENTRYPOINT"
                if row["strategy_id"] in RECOVERY_IDENTITIES
                else "PREVIOUSLY_COMPLETE_P20C"
            )
        if row["strategy_id"] == "history::lottery_api/models/zone_split.py":
            row["terminal_disposition"] = "COMPLETE_NATIVE_20"
            row["native_ticket_count"] = 20
        elif row["strategy_id"] == "history::lottery_api/models/core_satellite.py":
            row["terminal_disposition"] = "COMPLETE_NATIVE_20"
            row["native_ticket_count"] = 20
        elif row["strategy_id"] in SPEC_TO_IDENTITY.values():
            row["terminal_disposition"] = "COMPLETE_ADAPTER_20"

    rows.sort(key=lambda row: row["strategy_id"])
    ids = [row["strategy_id"] for row in rows]
    if len(rows) != EXPECTED_IDENTITY_COUNT or len(ids) != len(set(ids)):
        raise AssertionError(
            f"governed denominator drift: rows={len(rows)} unique={len(set(ids))} expected={EXPECTED_IDENTITY_COUNT}"
        )
    if any(row["terminal_disposition"] not in TERMINAL_DISPOSITIONS for row in rows):
        raise AssertionError("inventory contains an invalid terminal disposition")
    return rows


def build_resolution_ledger() -> list[dict[str, Any]]:
    p541b = json.loads(P541B_EVIDENCE.read_text(encoding="utf-8"))
    ledger: list[dict[str, Any]] = []
    for record in p541b["method_classification_records"]:
        historical = record.get("historical_p541b_classification", {})
        actual = historical.get("is_actual_prediction_method", "unknown")
        duplicate = historical.get("duplicate_of_existing_strategy")
        resolution = "SOURCE_EVIDENCE_ONLY"
        resolved = ""
        reason = (
            "Source-file method surface is evidence, not a governed strategy ID; "
            "preserved for provenance without denominator inflation."
        )
        source_path = record["source_path"]
        for strategy_id, _, path in HISTORICAL_IDENTITIES:
            if source_path == path:
                resolution = "GOVERNED_HISTORICAL_IDENTITY"
                resolved = strategy_id
                reason = "P20C established a reviewed executable identity for this source."
        if duplicate:
            resolution = "DUPLICATE_SOURCE_EVIDENCE"
            resolved = str(duplicate)
            reason = "P541B records an explicit duplicate_of relationship."
        ledger.append(
            {
                "evidence_record_id": f"p541b::{record['method_id']}",
                "evidence_kind": "historical_source_surface",
                "source_identity": record["method_id"],
                "source_path": source_path,
                "source_commit": record["source_identity"].get("source_commit", ""),
                "governance_status": "UNGoverned_SOURCE_EVIDENCE",
                "resolution_class": resolution,
                "resolved_strategy_id": resolved,
                "is_strategy_claim": str(actual).lower(),
                "reason": reason,
            }
        )

    registry = _registry_rows()
    p24 = _p24_rows()
    for strategy_id in sorted(set(registry) | set(p24)):
        current = registry.get(strategy_id, {})
        historical = p24.get(strategy_id, {})
        resolved = strategy_id
        resolution = "GOVERNED_STRATEGY_IDENTITY"
        if strategy_id == "bet2_fourier_expansion_biglotto":
            resolved = (
                "bet2_fourier_expansion_biglotto@p42_p280_frozen_code;"
                "bet2_fourier_expansion_biglotto@rejected_json_historical"
            )
            resolution = "CONFIRMED_ID_REUSE_SPLIT"
        elif strategy_id in ALIAS_OF:
            resolution = "GOVERNED_DUPLICATE_ALIAS"
        elif strategy_id in EQUIVALENT_TO:
            resolution = "GOVERNED_EQUIVALENT_IMPLEMENTATION"
        ledger.append(
            {
                "evidence_record_id": f"governed::{strategy_id}",
                "evidence_kind": "governance_record",
                "source_identity": strategy_id,
                "source_path": current.get("source_path", "")
                or historical.get("source_artifact", "")
                or "lottery_api/models/replay_strategy_registry.py",
                "source_commit": git_value("rev-parse", "HEAD"),
                "governance_status": current.get(
                    "lifecycle_status", historical.get("lifecycle_state", "REJECTED")
                ),
                "resolution_class": resolution,
                "resolved_strategy_id": resolved,
                "is_strategy_claim": "true",
                "reason": "Current registry/P24 governed record; aliases and ID reuse remain explicit.",
            }
        )
    ledger.sort(key=lambda row: row["evidence_record_id"])
    if len(ledger) != EXPECTED_EVIDENCE_RECORDS:
        raise AssertionError(
            f"evidence denominator drift: {len(ledger)} != {EXPECTED_EVIDENCE_RECORDS}"
        )
    return ledger


def build_strategy_specs(random_replicates: int = 10) -> list[p20c.StrategySpec]:
    from recovered_strategies.biglotto.historical_adapters import (
        adapt_biglotto_p0_2bet,
        adapt_predict_biglotto_echo_2bet,
        adapt_predict_biglotto_echo_phase2_3bet,
    )
    from tools.predict_biglotto_mixed_3bet import mixed_3bet

    def wrap(function):
        def generator(history, target, replicate, seed):
            del target, replicate, seed
            return function(history)

        return generator

    specs = p20c.build_strategy_specs(random_replicates)
    specs.extend(
        [
            p20c.StrategySpec(
                "biglotto_p0_2bet",
                RECOVERY_IDENTITIES["biglotto_p0_2bet"]["name"],
                "unknown",
                50,
                1,
                "p358_parity_adapter",
                "adapter",
                True,
                wrap(adapt_biglotto_p0_2bet),
            ),
            p20c.StrategySpec(
                "predict_biglotto_echo_2bet",
                RECOVERY_IDENTITIES["predict_biglotto_echo_2bet"]["name"],
                "unknown",
                10,
                1,
                "p358_parity_adapter",
                "adapter",
                True,
                wrap(adapt_predict_biglotto_echo_2bet),
            ),
            p20c.StrategySpec(
                "predict_biglotto_echo_phase2",
                RECOVERY_IDENTITIES["predict_biglotto_echo_phase2"]["name"],
                "unknown",
                60,
                1,
                "p358_versioned_parity_adapter_3bet",
                "adapter",
                True,
                wrap(adapt_predict_biglotto_echo_phase2_3bet),
            ),
            p20c.StrategySpec(
                "predict_biglotto_mixed_3bet",
                RECOVERY_IDENTITIES["predict_biglotto_mixed_3bet"]["name"],
                "unknown",
                50,
                1,
                "current_pure_deterministic_callable",
                "adapter",
                True,
                wrap(mixed_3bet),
            ),
        ]
    )
    baseline = [spec for spec in specs if spec.ranking_group == "baseline"]
    real = sorted(
        (spec for spec in specs if spec.ranking_group != "baseline"),
        key=lambda spec: spec.strategy_id,
    )
    result = [*baseline, *real]
    mapped = {SPEC_TO_IDENTITY[spec.strategy_id] for spec in real}
    if len(real) != 18 or len(mapped) != 18:
        raise AssertionError(f"execution-spec drift: specs={len(real)} mapped={len(mapped)}")
    return result


def _legal_native(raw: Sequence[Sequence[int]]) -> bool:
    cleaned, _, invalid = p20c.normalise_native_tickets(raw)
    return bool(cleaned) and invalid == 0


def preflight_executable_specs(
    draws: list[dict[str, Any]], specs: Sequence[p20c.StrategySpec]
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for spec in specs:
        if spec.ranking_group == "baseline":
            continue
        target_index = max(spec.min_history, p20c.COMMON_MIN_HISTORY)
        history = draws[:target_index]
        target = dict(draws[target_index])
        seed = p20c.stable_seed("p20s-preflight-v1", spec.strategy_id, target["draw"])
        try:
            raw = spec.generator(history, target, 0, seed)
            mutated_target = {**target, "numbers": [1, 2, 3, 4, 5, 6], "special": 7}
            mutated = spec.generator(history, mutated_target, 0, seed)
            future_draws = [*draws]
            if target_index + 1 < len(future_draws):
                future_draws[target_index + 1] = {
                    **future_draws[target_index + 1],
                    "numbers": [44, 45, 46, 47, 48, 49],
                }
            future = spec.generator(future_draws[:target_index], target, 0, seed)
            portfolio = p20c.prepare_portfolio(
                strategy_id=spec.strategy_id,
                draw_id=target["draw"],
                replicate_id=0,
                cutoff_identity=history[-1]["draw"],
                raw_tickets=raw,
                actual_numbers=target["numbers"],
                constructor_mode=p20c.TICKET_CONSTRUCTOR_V1,
            )
            metadata = portfolio.get("metadata")
            metadata_ok = (
                spec.ranking_group == "native"
                or (
                    metadata is not None
                    and metadata.constructor_name == p20c.CONSTRUCTOR_NAME
                    and metadata.constructor_version == p20c.CONSTRUCTOR_VERSION
                )
            )
            result = {
                "strategy_id": SPEC_TO_IDENTITY[spec.strategy_id],
                "preflight_status": "PASS"
                if portfolio["ok"]
                and len(portfolio["tickets"]) == 20
                and raw == mutated == future
                and _legal_native(raw)
                and metadata_ok
                else "FAIL",
                "entrypoint": spec.execution_mode,
                "import_ok": True,
                "cutoff_contract_ok": True,
                "target_mutation_invariant": raw == mutated,
                "future_mutation_invariant": raw == future,
                "native_output_valid": _legal_native(raw),
                "final_ticket_count": len(portfolio["tickets"]),
                "constructor_metadata_ok": metadata_ok,
                "reason": portfolio.get("failure_reason", ""),
            }
        except Exception as exc:
            result = {
                "strategy_id": SPEC_TO_IDENTITY[spec.strategy_id],
                "preflight_status": "FAIL",
                "entrypoint": spec.execution_mode,
                "import_ok": False,
                "cutoff_contract_ok": False,
                "target_mutation_invariant": False,
                "future_mutation_invariant": False,
                "native_output_valid": False,
                "final_ticket_count": 0,
                "constructor_metadata_ok": False,
                "reason": f"{type(exc).__name__}: {exc}",
            }
        results.append(result)
    return sorted(results, key=lambda row: row["strategy_id"])


def full_preflight(
    inventory: Sequence[Mapping[str, Any]], executable: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    by_id = {row["strategy_id"]: dict(row) for row in executable}
    results: list[dict[str, Any]] = []
    for identity in inventory:
        strategy_id = str(identity["strategy_id"])
        if strategy_id in by_id:
            results.append(by_id[strategy_id])
            continue
        terminal = str(identity["terminal_disposition"])
        results.append(
            {
                "strategy_id": strategy_id,
                "preflight_status": "TERMINAL_RESOLUTION"
                if terminal != "PARTIAL_BACKTEST"
                else "PARTIAL_EVIDENCE_ONLY",
                "entrypoint": identity["entrypoint"],
                "import_ok": terminal == "PARTIAL_BACKTEST",
                "cutoff_contract_ok": terminal == "PARTIAL_BACKTEST",
                "target_mutation_invariant": "NOT_RANKED",
                "future_mutation_invariant": "NOT_RANKED",
                "native_output_valid": "SHAPE_ONLY"
                if terminal == "PARTIAL_BACKTEST"
                else "NOT_ATTEMPTED",
                "final_ticket_count": 0,
                "constructor_metadata_ok": "NOT_APPLICABLE",
                "reason": identity["evidence"],
            }
        )
    return sorted(results, key=lambda row: row["strategy_id"])


@contextlib.contextmanager
def strategy_timeout(seconds: int):
    if seconds <= 0 or not hasattr(signal, "SIGALRM"):
        yield
        return

    def handler(signum, frame):
        del signum, frame
        raise TimeoutError(f"strategy exceeded {seconds} seconds")

    prior = signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, prior)


def checkpoint_header(
    *, head: str, dataset_sha256: str, runner_sha256: str, strategy_id: str
) -> dict[str, Any]:
    return {
        "runner_version": RUNNER_VERSION,
        "source_head": head,
        "dataset_sha256": dataset_sha256,
        "constructor_name": p20c.CONSTRUCTOR_NAME,
        "constructor_version": p20c.CONSTRUCTOR_VERSION,
        "runner_sha256": runner_sha256,
        "strategy_id": strategy_id,
    }


def checkpoint_compatible(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    return all(actual.get(key) == value for key, value in expected.items())


def _checkpoint_stem(strategy_id: str) -> str:
    return sha256_bytes(strategy_id.encode("utf-8"))[:20]


def _read_detail(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def execute_with_checkpoints(
    *,
    draws: list[dict[str, Any]],
    specs: Sequence[p20c.StrategySpec],
    checkpoint_dir: Path,
    head: str,
    dataset_sha256: str,
    runner_sha256: str,
    timeout_seconds: int,
    resume: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    all_observations: list[dict[str, Any]] = []
    all_failures: list[dict[str, Any]] = []
    samples: dict[str, dict[str, Any]] = {}
    strategy_runs: list[dict[str, Any]] = []
    detail_files: list[dict[str, Any]] = []

    for spec in specs:
        stem = _checkpoint_stem(spec.strategy_id)
        metadata_path = checkpoint_dir / f"{stem}.json"
        detail_path = checkpoint_dir / f"{stem}.csv.gz"
        expected = checkpoint_header(
            head=head,
            dataset_sha256=dataset_sha256,
            runner_sha256=runner_sha256,
            strategy_id=spec.strategy_id,
        )
        reused = False
        metadata: dict[str, Any] = {}
        if resume and metadata_path.is_file() and detail_path.is_file():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if checkpoint_compatible(metadata, expected) and metadata.get("detail_sha256") == sha256_file(detail_path):
                reused = True
        if reused:
            observations = _read_detail(detail_path)
            failures = list(metadata.get("runtime_failures", []))
            execution = metadata.get("execution", {})
        else:
            started = time.monotonic()
            try:
                with strategy_timeout(timeout_seconds):
                    observations, failures, execution = p20c.execute_backtest(
                        draws=draws,
                        specs=[spec],
                        constructor_mode=p20c.TICKET_CONSTRUCTOR_V1,
                        detail_path=detail_path,
                    )
                run_status = "COMPLETE"
            except TimeoutError as exc:
                run_status = "RESOURCE_LIMIT_REACHED"
                failures = [
                    {
                        "strategy_id": spec.strategy_id,
                        "governance_status": spec.governance_status,
                        "failure_stage": "STRATEGY_TIMEOUT",
                        "reason_code": "RESOURCE_LIMIT_REACHED",
                        "target_draw": "",
                        "replicate_id": "",
                        "detailed_reason": str(exc),
                    }
                ]
                observations = []
                execution = {
                    "detail_row_count": 0,
                    "detail_stream_sha256": sha256_bytes(b""),
                    "reproducibility_samples": {},
                }
                with gzip.open(detail_path, "wt", encoding="utf-8", newline="") as handle:
                    csv.DictWriter(handle, fieldnames=p20c.DETAIL_FIELDS).writeheader()
            elapsed = time.monotonic() - started
            metadata = {
                **expected,
                "run_status": run_status,
                "runtime_seconds": round(elapsed, 6),
                "detail_sha256": sha256_file(detail_path),
                "detail_rows": len(observations),
                "runtime_failures": failures,
                "execution": execution,
            }
            temporary = metadata_path.with_suffix(".json.tmp")
            write_json(temporary, metadata)
            os.replace(temporary, metadata_path)
        all_observations.extend(observations)
        all_failures.extend(failures)
        samples.update(execution.get("reproducibility_samples", {}))
        strategy_runs.append(
            {
                "strategy_id": spec.strategy_id,
                "identity_id": "baseline::uniform_random_20"
                if spec.ranking_group == "baseline"
                else SPEC_TO_IDENTITY[spec.strategy_id],
                "runtime_seconds": metadata.get("runtime_seconds", 0.0),
                "checkpoint_reused": reused,
                "detail_rows": len(observations),
                "run_status": metadata.get("run_status", "COMPLETE"),
            }
        )
        detail_files.append(
            {
                "strategy_id": spec.strategy_id,
                "path": str(detail_path),
                "sha256": sha256_file(detail_path),
                "rows": len(observations),
            }
        )
    return all_observations, all_failures, {
        "reproducibility_samples": samples,
        "strategy_runs": strategy_runs,
        "detail_files": detail_files,
    }


def _metric_rows(
    *,
    raw_metrics: Sequence[Mapping[str, Any]],
    inventory: Sequence[Mapping[str, Any]],
    strategy_runs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    inventory_by_id = {row["strategy_id"]: row for row in inventory}
    runtime = {row["strategy_id"]: row["runtime_seconds"] for row in strategy_runs}
    rows: list[dict[str, Any]] = []
    for metric in raw_metrics:
        spec_id = str(metric["base_strategy_id"])
        identity_id = SPEC_TO_IDENTITY[spec_id]
        identity = inventory_by_id[identity_id]
        low = float(metric["m4plus_ci95_low"])
        high = float(metric["m4plus_ci95_high"])
        paired_low = float(metric["baseline_difference_ci95_low"])
        paired_high = float(metric["baseline_difference_ci95_high"])
        rows.append(
            {
                "strategy_id": identity_id,
                "effective_strategy_id": metric["effective_strategy_id"],
                "strategy_name": identity["strategy_name"],
                "governance_status": identity["governance_status"],
                "independent_algorithm_id": identity["independent_algorithm_id"],
                "equivalence_group": identity["equivalence_group"],
                "ranking_group": metric["ranking_group"],
                "native_ticket_count": round(float(metric["native_ticket_count_mean"]), 6),
                "constructed_ticket_count": round(float(metric["constructed_ticket_count_mean"]), 6),
                "evaluated_draws": int(metric["unique_target_draws"]),
                "replicates": int(metric["replicates"]),
                "complete_portfolios": int(metric["completed_common_portfolios"]),
                "completion_rate": float(metric["completion_ratio"]),
                "m4plus_hits": int(metric["m4plus_draw_hits"]),
                "m4plus_rate": float(metric["m4plus_draw_rate"]),
                "confidence_interval_95": f"[{low:.12f},{high:.12f}]",
                "paired_difference_vs_random": float(metric["baseline_difference"]),
                "paired_interval_95": f"[{paired_low:.12f},{paired_high:.12f}]",
                "credible_random_advantage": paired_low > 0,
                "runtime_seconds": runtime.get(spec_id, 0.0),
                "total_ticket_evaluations": int(metric["total_ticket_evaluations"]),
                "governance_note": "Historical comparison only; no promotion and no future-probability claim.",
            }
        )
    return rows


def rank_metrics(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        (dict(row) for row in rows),
        key=lambda row: (-float(row["m4plus_rate"]), -int(row["m4plus_hits"]), row["strategy_id"]),
    )
    for index, row in enumerate(ranked, 1):
        row["rank"] = index
    return ranked


def finalize_inventory(
    inventory: Sequence[Mapping[str, Any]], metrics: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    metric_by_id = {row["strategy_id"]: row for row in metrics}
    result: list[dict[str, Any]] = []
    for source in inventory:
        row = dict(source)
        metric = metric_by_id.get(row["strategy_id"])
        if metric:
            completed = float(metric["completion_rate"]) >= p20c.COMPLETENESS_THRESHOLD
            if completed:
                row["terminal_disposition"] = (
                    "COMPLETE_NATIVE_20"
                    if metric["ranking_group"] == "native"
                    else "COMPLETE_ADAPTER_20"
                )
                row["native_ticket_count"] = metric["native_ticket_count"]
                row["leakage_status"] = "PASS"
            else:
                row["terminal_disposition"] = "RUNTIME_FAILURE"
                row["recovery_status"] = "BACKTEST_INCOMPLETE"
        result.append(row)
    if any(row["terminal_disposition"] not in TERMINAL_DISPOSITIONS for row in result):
        raise AssertionError("terminal disposition lost during finalization")
    return sorted(result, key=lambda row: row["strategy_id"])


def independent_recompute(
    observations: Sequence[Mapping[str, Any]], metrics: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    expected = {row["strategy_id"]: row for row in metrics}
    spec_groups = {
        spec.strategy_id: spec.ranking_group for spec in build_strategy_specs(10)
    }
    mismatches: list[str] = []
    for spec_id, identity_id in SPEC_TO_IDENTITY.items():
        rows = [
            row
            for row in observations
            if row["base_strategy_id"] == spec_id
            and int(row["target_index"]) >= p20c.COMMON_MIN_HISTORY
            and int(row["final_ticket_count"]) == 20
            and (
                spec_groups[spec_id] != "native"
                or row["effective_strategy_id"] == spec_id
            )
        ]
        observed_hits = sum(int(row["m4plus"]) for row in rows)
        metric = expected[identity_id]
        if observed_hits != int(metric["m4plus_hits"]) or len(rows) != int(metric["complete_portfolios"]):
            mismatches.append(identity_id)
    return {
        "strategies_recomputed": len(SPEC_TO_IDENTITY),
        "mismatch_count": len(mismatches),
        "mismatched_strategy_ids": mismatches,
    }


def aggregate_detail_validation(
    detail_files: Sequence[Mapping[str, Any]], observations: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    totals: Counter[str] = Counter()
    offset = 0
    validations = []
    for detail in detail_files:
        count = int(detail["rows"])
        subset = observations[offset : offset + count]
        validation = p20c.independent_detail_validation(Path(detail["path"]), subset)
        validations.append({"strategy_id": detail["strategy_id"], **validation})
        offset += count
        for key, value in validation.items():
            if key.endswith("failures") or key.endswith("mismatches"):
                totals[key] += int(value)
    return {
        "files_validated": len(detail_files),
        "rows_validated": offset,
        "observation_rows": len(observations),
        "row_count_matches": offset == len(observations),
        "failure_totals": dict(sorted(totals.items())),
        "all_pass": offset == len(observations) and not any(totals.values()),
        "per_strategy": validations,
    }


def inventory_counts(inventory: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    dispositions = Counter(str(row["terminal_disposition"]) for row in inventory)
    alias_count = dispositions["DUPLICATE_ALIAS"]
    equivalent_count = dispositions["EQUIVALENT_IMPLEMENTATION"]
    complete_native = dispositions["COMPLETE_NATIVE_20"]
    complete_adapter = dispositions["COMPLETE_ADAPTER_20"]
    backlog_dispositions = {
        "PARTIAL_BACKTEST",
        "MISSING_IMPLEMENTATION",
        "MISSING_ENTRYPOINT",
        "MISSING_ARTIFACT",
        "MISSING_DEPENDENCY",
        "EXTERNAL_STATE_NOT_REPRODUCIBLE",
        "INVALID_OUTPUT",
        "RESOURCE_LIMIT_REACHED",
        "RUNTIME_FAILURE",
        "UNKNOWN_REQUIRES_OWNER_EVIDENCE",
    }
    conclusive = {
        "DUPLICATE_ALIAS",
        "EQUIVALENT_IMPLEMENTATION",
        "DOCUMENT_ONLY",
        "NO_VALID_STRATEGY_SIGNAL",
        "DATA_LEAKAGE_EXCLUDED",
        "UNSAFE_METHOD_EXCLUDED",
    }
    return {
        "unique_strategy_identities": len(inventory),
        "independent_algorithms": len(inventory) - alias_count - equivalent_count,
        "aliases": alias_count,
        "equivalent_implementations": equivalent_count,
        "equivalence_groups": len(EQUIVALENCE_GROUPS),
        "document_only": dispositions["DOCUMENT_ONLY"],
        "native_20_ticket": complete_native,
        "adapter_20_ticket": complete_adapter,
        "total_complete": complete_native + complete_adapter,
        "partial": dispositions["PARTIAL_BACKTEST"],
        "terminally_excluded": sum(dispositions[name] for name in conclusive),
        "missing_implementation": dispositions["MISSING_IMPLEMENTATION"],
        "external_state_not_reproducible": dispositions["EXTERNAL_STATE_NOT_REPRODUCIBLE"],
        "remaining_engineering_backlog": sum(dispositions[name] for name in backlog_dispositions),
        "failed": dispositions["RUNTIME_FAILURE"] + dispositions["RESOURCE_LIMIT_REACHED"],
        "remaining_unknown": dispositions["UNKNOWN_REQUIRES_OWNER_EVIDENCE"],
    }


def generate_report(
    *,
    inventory: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    baseline: Mapping[str, Any],
    data_quality: Mapping[str, Any],
    validation: Mapping[str, Any],
) -> str:
    counts = inventory_counts(inventory)
    credible = [row for row in metrics if row["credible_random_advantage"]]
    equivalent_leaders = [
        f"{group}: {', '.join(definition['members'])}"
        for group, definition in sorted(EQUIVALENCE_GROUPS.items())
    ]
    backlog = [
        row["strategy_id"]
        for row in inventory
        if row["terminal_disposition"]
        in {
            "PARTIAL_BACKTEST",
            "MISSING_IMPLEMENTATION",
            "MISSING_ENTRYPOINT",
            "MISSING_ARTIFACT",
            "MISSING_DEPENDENCY",
            "EXTERNAL_STATE_NOT_REPRODUCIBLE",
            "INVALID_OUTPUT",
            "RESOURCE_LIMIT_REACHED",
            "RUNTIME_FAILURE",
            "UNKNOWN_REQUIRES_OWNER_EVIDENCE",
        }
    ]
    lines = [
        "# P20S All-Strategies Bulk Recovery Backtest",
        "",
        f"Status: **{'COMPLETED' if validation['status'] == 'PASS' else 'PARTIALLY_COMPLETED'}**.",
        "",
        "This is a historical empirical research result for entertainment and audit use. "
        "It is not a future winning probability, betting recommendation, or strategy promotion.",
        "",
        "## Exact denominator",
        "",
        f"- Unique governed Big Lotto strategy identities: {counts['unique_strategy_identities']}",
        f"- Non-baseline evidence records: {EXPECTED_EVIDENCE_RECORDS}",
        f"- Random comparison baselines: {EXPECTED_RANDOM_BASELINES}",
        f"- Aliases: {counts['aliases']}",
        f"- Equivalent implementations: {counts['equivalent_implementations']}",
        f"- Independent algorithms after alias/equivalence collapse: {counts['independent_algorithms']}",
        "",
        "The denominator rule admits current registry/P24 governed IDs, a proven ID-reuse split, "
        "reviewed P20C historical identities, and explicit P357/P358 recovery identities. Source files, "
        "helper functions, fixtures, composite DB scopes, publication runners, and evidence gaps remain "
        "in the resolution ledger but do not inflate the strategy count.",
        "",
        "## Execution outcome",
        "",
        "- Previously complete strategies: 14",
        f"- Newly recovered standard backtests: {counts['total_complete'] - 14}",
        f"- Complete native 20-ticket identities: {counts['native_20_ticket']}",
        f"- Complete adapter-assisted identities: {counts['adapter_20_ticket']}",
        f"- Total complete identities: {counts['total_complete']}",
        f"- Partial shape/parity results: {counts['partial']}",
        f"- Conclusive alias/equivalence/document/safety exclusions: {counts['terminally_excluded']}",
        f"- Missing implementations: {counts['missing_implementation']}",
        f"- External state not reproducible: {counts['external_state_not_reproducible']}",
        f"- Remaining engineering backlog: {counts['remaining_engineering_backlog']}",
        "",
        "## Historical backtest contract",
        "",
        f"- Canonical draws: {data_quality['historical_draws']}",
        f"- Common window after 100 prior draws: {data_quality['common_window_rows']}",
        f"- Constructor: {p20c.CONSTRUCTOR_NAME}/{p20c.CONSTRUCTOR_VERSION}",
        "- Exactly 20 unique legal tickets per completed draw/replicate portfolio",
        "- Ten deterministic random-baseline replicates; deterministic strategies use one replicate",
        f"- Random M4+ rate: {float(baseline['m4plus_draw_rate']):.6%}",
        "",
        "## Random comparison",
        "",
        f"Strategies whose paired 95% historical interval is strictly above zero: {len(credible)}.",
        "No historical confidence interval is interpreted as a future advantage. Multiple comparisons, "
        "shared histories, and correlated strategy families remain material limitations.",
        "",
        "## Equivalent and alias families",
        "",
        *[f"- {item}" for item in equivalent_leaders],
        "",
        "Aliases and equivalent implementations are excluded from independent-evidence counts and valid rankings.",
        "",
        "## Remaining engineering backlog",
        "",
        *([f"- {strategy_id}" for strategy_id in backlog] or ["- None"]),
        "",
        "No resource boundary was reached; next unprocessed strategy: null.",
        "",
        "## Data quality and verification",
        "",
        f"The immutable read-only source contained {data_quality['raw_big_lotto_rows']} raw Big Lotto rows, "
        f"{data_quality['historical_draws']} canonical rows, and {data_quality['excluded_noncanonical_rows']} "
        "excluded noncanonical rows. Duplicate IDs/dates, malformed number rows, range errors, negative "
        "financial fields, and cutoff violations were all checked. Positional-order fields are null and were "
        "not treated as signal.",
        "",
        f"Validation status: {validation['status']}.",
        "",
        f"> Out of {counts['unique_strategy_identities']} Big Lotto strategy identities, "
        f"{counts['total_complete']} completed the standard 20-ticket historical backtest, "
        f"{counts['terminally_excluded']} were conclusively excluded, and "
        f"{counts['remaining_engineering_backlog']} still require implementation work.",
        "",
    ]
    return "\n".join(lines)


def publish_outputs(
    *,
    output_dir: Path,
    inventory: Sequence[Mapping[str, Any]],
    ledger: Sequence[Mapping[str, Any]],
    preflight: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    baseline: Mapping[str, Any],
    data_quality: Mapping[str, Any],
    validation: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite output directory: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".p20s-stage-", dir=output_dir.parent) as temporary:
        staging = Path(temporary) / output_dir.name
        staging.mkdir()
        equivalence_rows = [
            {
                "equivalence_group": group,
                "canonical_strategy_id": definition["canonical"],
                "member_strategy_ids": ";".join(definition["members"]),
                "member_count": len(definition["members"]),
                "basis": definition["basis"],
            }
            for group, definition in sorted(EQUIVALENCE_GROUPS.items())
        ]
        recovered = [
            {
                "strategy_id": strategy_id,
                "entrypoint": definition["entrypoint"],
                "source_path": definition["source"],
                "historical_source_commit": definition.get("historical_commit", ""),
                "parity_status": "PARITY_ACCEPTABLE"
                if definition["terminal"] == "COMPLETE_ADAPTER_20"
                else "SHAPE_SAFETY_ONLY",
                "terminal_disposition": definition["terminal"],
            }
            for strategy_id, definition in sorted(RECOVERY_IDENTITIES.items())
        ]
        complete = [row for row in metrics if float(row["completion_rate"]) >= p20c.COMPLETENESS_THRESHOLD]
        newly = [row for row in complete if row["strategy_id"] in RECOVERY_IDENTITIES]
        native = rank_metrics([row for row in complete if row["ranking_group"] == "native"])
        adapter = rank_metrics([row for row in complete if row["ranking_group"] == "adapter"])
        all_valid = rank_metrics(complete)
        partial = [row for row in inventory if row["terminal_disposition"] == "PARTIAL_BACKTEST"]
        conclusive = {
            "DUPLICATE_ALIAS",
            "EQUIVALENT_IMPLEMENTATION",
            "DOCUMENT_ONLY",
            "NO_VALID_STRATEGY_SIGNAL",
            "DATA_LEAKAGE_EXCLUDED",
            "UNSAFE_METHOD_EXCLUDED",
        }
        excluded = [row for row in inventory if row["terminal_disposition"] in conclusive]
        failed = [
            row
            for row in inventory
            if row["terminal_disposition"]
            in {
                "MISSING_IMPLEMENTATION",
                "MISSING_ENTRYPOINT",
                "MISSING_ARTIFACT",
                "MISSING_DEPENDENCY",
                "EXTERNAL_STATE_NOT_REPRODUCIBLE",
                "INVALID_OUTPUT",
                "RESOURCE_LIMIT_REACHED",
                "RUNTIME_FAILURE",
                "UNKNOWN_REQUIRES_OWNER_EVIDENCE",
            }
        ]

        write_csv(staging / "strategy_master_inventory.csv", inventory, MASTER_FIELDS)
        write_csv(staging / "strategy_resolution_ledger.csv", ledger, LEDGER_FIELDS)
        write_csv(
            staging / "strategy_equivalence_groups.csv",
            equivalence_rows,
            ("equivalence_group", "canonical_strategy_id", "member_strategy_ids", "member_count", "basis"),
        )
        write_csv(
            staging / "recovered_entrypoints.csv",
            recovered,
            ("strategy_id", "entrypoint", "source_path", "historical_source_commit", "parity_status", "terminal_disposition"),
        )
        write_csv(staging / "preflight_results.csv", preflight, PREFLIGHT_FIELDS)
        write_csv(staging / "all_completed_strategy_metrics.csv", complete, METRIC_FIELDS)
        write_csv(staging / "newly_recovered_strategy_metrics.csv", newly, METRIC_FIELDS)
        rank_fields = ("rank", *METRIC_FIELDS)
        write_csv(staging / "m4plus_native_ranking.csv", native, rank_fields)
        write_csv(staging / "m4plus_adapter_ranking.csv", adapter, rank_fields)
        write_csv(staging / "m4plus_all_valid_ranking.csv", all_valid, rank_fields)
        write_csv(staging / "partial_results.csv", partial, MASTER_FIELDS)
        write_csv(staging / "excluded_strategies.csv", excluded, MASTER_FIELDS)
        write_csv(staging / "failed_strategies.csv", failed, MASTER_FIELDS)
        write_json(staging / "validation_results.json", validation)
        (staging / "final_report.md").write_text(
            generate_report(
                inventory=inventory,
                metrics=metrics,
                baseline=baseline,
                data_quality=data_quality,
                validation=validation,
            ),
            encoding="utf-8",
        )
        manifest["outputs"] = {
            name: sha256_file(staging / name)
            for name in REQUIRED_OUTPUTS
            if name != "run_manifest.json"
        }
        write_json(staging / "run_manifest.json", manifest)
        os.replace(staging, output_dir)


def load_verification_evidence(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"status": "NOT_SUPPLIED", "passed": 0, "failed": 0, "skipped": 0, "commands": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {"status", "passed", "failed", "skipped", "commands"}
    if not required.issubset(payload):
        raise ValueError(f"verification evidence missing fields: {sorted(required - set(payload))}")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--canonical-repo", type=Path, required=True)
    parser.add_argument("--expected-canonical-status-sha256", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--bootstrap-replicates", type=int, default=2000)
    parser.add_argument("--verification-evidence", type=Path)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--smoke-targets", type=int, default=0)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)

    if args.bootstrap_replicates <= 0:
        parser.error("bootstrap replicates must be positive")
    canonical_before = p20c.normalized_git_status_sha256(args.canonical_repo)
    if canonical_before != args.expected_canonical_status_sha256:
        parser.error(
            "canonical checkout status changed before run: "
            f"{canonical_before} != {args.expected_canonical_status_sha256}"
        )

    database = args.database.resolve()
    database_sha_before = sha256_file(database)
    draws, quality = p20c.load_draws_and_quality(database)
    if len(draws) != EXPECTED_DRAWS or quality["common_window_rows"] != EXPECTED_COMMON_DRAWS:
        parser.error(
            f"canonical dataset boundary drift: draws={len(draws)} common={quality['common_window_rows']}"
        )
    inventory = build_master_inventory()
    ledger = build_resolution_ledger()
    specs = build_strategy_specs(10)
    executable_preflight = preflight_executable_specs(draws, specs)
    preflight = full_preflight(inventory, executable_preflight)
    if any(row["preflight_status"] == "FAIL" for row in executable_preflight):
        for row in executable_preflight:
            if row["preflight_status"] == "FAIL":
                print(canonical_json(row), file=sys.stderr)
        return 2
    if args.preflight_only:
        print(canonical_json({"status": "PASS", "identities": len(inventory), "preflight_rows": len(preflight)}))
        return 0

    execution_draws = draws
    if args.smoke_targets:
        if args.smoke_targets <= 0:
            parser.error("smoke target count must be positive")
        execution_draws = draws[: p20c.COMMON_MIN_HISTORY + args.smoke_targets]

    head = git_value("rev-parse", "HEAD")
    runner_sha = sha256_file(Path(__file__))
    observations, runtime_failures, execution = execute_with_checkpoints(
        draws=execution_draws,
        specs=specs,
        checkpoint_dir=args.checkpoint_dir.resolve(),
        head=head,
        dataset_sha256=quality["canonical_dataset_sha256"],
        runner_sha256=runner_sha,
        timeout_seconds=args.timeout_seconds,
        resume=not args.no_resume,
    )
    raw_metrics, _, _, baseline = p20c.build_metrics(
        observations=observations,
        specs=specs,
        bootstrap_replicates=args.bootstrap_replicates,
        draw_count=len(execution_draws),
    )
    metrics = _metric_rows(
        raw_metrics=raw_metrics,
        inventory=inventory,
        strategy_runs=execution["strategy_runs"],
    )
    inventory = finalize_inventory(inventory, metrics)
    detail_validation = aggregate_detail_validation(execution["detail_files"], observations)
    recompute = independent_recompute(observations, metrics)
    reproducibility = p20c.check_constructor_reproducibility(execution["reproducibility_samples"])
    database_sha_after = sha256_file(database)
    canonical_after = p20c.normalized_git_status_sha256(args.canonical_repo)
    verification = load_verification_evidence(args.verification_evidence)
    counts = inventory_counts(inventory)
    expected_complete = 18
    validation_checks = {
        "inventory_contract": {
            "pass": len(inventory) == EXPECTED_IDENTITY_COUNT
            and len({row["strategy_id"] for row in inventory}) == EXPECTED_IDENTITY_COUNT
            and all(row["terminal_disposition"] in TERMINAL_DISPOSITIONS for row in inventory),
            "details": counts,
        },
        "evidence_separation": {
            "pass": len(ledger) == EXPECTED_EVIDENCE_RECORDS,
            "details": {"evidence_records": len(ledger), "random_baselines": 1},
        },
        "full_preflight": {
            "pass": len(preflight) == EXPECTED_IDENTITY_COUNT
            and not any(row["preflight_status"] == "FAIL" for row in preflight),
            "details": dict(Counter(row["preflight_status"] for row in preflight)),
        },
        "completed_strategy_contract": {
            "pass": counts["total_complete"] == expected_complete and not runtime_failures,
            "details": {
                "expected": expected_complete,
                "actual": counts["total_complete"],
                "runtime_failure_rows": len(runtime_failures),
            },
        },
        "detail_recomputation": {"pass": detail_validation["all_pass"], "details": detail_validation},
        "aggregate_recomputation": {"pass": recompute["mismatch_count"] == 0, "details": recompute},
        "constructor_reproducibility": {
            "pass": reproducibility["mismatch_count"] == 0,
            "details": reproducibility,
        },
        "database_unchanged": {
            "pass": database_sha_before == database_sha_after,
            "details": {"sha256_before": database_sha_before, "sha256_after": database_sha_after},
        },
        "canonical_checkout_unchanged": {
            "pass": canonical_before == canonical_after == args.expected_canonical_status_sha256,
            "details": {
                "sha256_before": canonical_before,
                "sha256_after": canonical_after,
                "expected": args.expected_canonical_status_sha256,
            },
        },
        "external_verification": {
            "pass": verification["status"] in {"PASS", "NOT_SUPPLIED"}
            and int(verification["failed"]) == 0,
            "details": verification,
        },
    }
    validation_pass = all(check["pass"] for check in validation_checks.values())
    validation = {
        "task_id": TASK_ID,
        "status": "PASS" if validation_pass else "FAIL",
        "checks": validation_checks,
    }

    credible = sum(bool(row["credible_random_advantage"]) for row in metrics)
    total_portfolios = sum(int(row["complete_portfolios"]) for row in metrics) + int(
        baseline["evaluated_portfolios"]
    )
    manifest = {
        "task_id": TASK_ID,
        "runner_version": RUNNER_VERSION,
        "status": "COMPLETED" if validation_pass else "PARTIALLY_COMPLETED",
        "repo": {
            "task_base_commit": head,
            "branch": git_value("branch", "--show-current"),
            "pr_693_merge_commit": "59bde7ea0dad3128a1142adbe78d2c048ff117a3",
            "runner_sha256": runner_sha,
        },
        "inventory": {
            "evidence_records": len(ledger),
            "random_baselines": 1,
            **counts,
            "denominator_rule": (
                "current registry/P24 governed union + proven ID reuse split + "
                "P20C reviewed historical identities + explicit P357/P358 recoveries"
            ),
        },
        "execution": {
            "previously_complete_strategies": 14,
            "newly_recovered_strategies": counts["total_complete"] - 14,
            "total_complete_strategies": counts["total_complete"],
            "next_unprocessed_strategy": None,
            "strategy_runs": execution["strategy_runs"],
            "checkpoint_contract": {
                "source_head": head,
                "dataset_sha256": quality["canonical_dataset_sha256"],
                "constructor_version": p20c.CONSTRUCTOR_VERSION,
                "runner_version": RUNNER_VERSION,
            },
        },
        "backtest": {
            "game": "BIG_LOTTO",
            "historical_source": "draws_big_lotto_canonical_main",
            "historical_draws": len(draws),
            "common_window_draws": quality["common_window_rows"],
            "tickets_per_draw": 20,
            "constructor": f"{p20c.CONSTRUCTOR_NAME}/{p20c.CONSTRUCTOR_VERSION}",
            "random_replicates": 10,
            "total_portfolios": total_portfolios,
            "total_ticket_evaluations": total_portfolios * 20,
            "strategies_with_credible_random_advantage": credible,
            "random_baseline": baseline,
        },
        "data": {
            **quality,
            "historical_draws": len(draws),
            "database_path": str(database),
            "database_sha256_before": database_sha_before,
            "database_sha256_after": database_sha_after,
        },
        "verification": verification,
        "limitations": [
            "Historical rates are not future winning probabilities.",
            "Aliases and equivalent implementations are not independent evidence.",
            "Multiple comparisons and shared historical reuse remain material.",
            "Four partial adapters have shape-safety evidence but no historical parity proof.",
        ],
    }
    publish_outputs(
        output_dir=args.output_dir.resolve(),
        inventory=inventory,
        ledger=ledger,
        preflight=preflight,
        metrics=metrics,
        baseline=baseline,
        data_quality={**quality, "historical_draws": len(draws)},
        validation=validation,
        manifest=manifest,
    )
    print(
        canonical_json(
            {
                "status": manifest["status"],
                "output_dir": str(args.output_dir.resolve()),
                "identities": len(inventory),
                "complete": counts["total_complete"],
                "validation": validation["status"],
            }
        )
    )
    return 0 if validation_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
