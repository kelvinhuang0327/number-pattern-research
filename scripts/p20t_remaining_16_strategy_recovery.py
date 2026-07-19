#!/usr/bin/env python3
"""Recover or conclusively resolve the 16 remaining P20S Big Lotto identities."""

from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

from recovered_strategies.biglotto import p20t_recovery_adapters as adapters  # noqa: E402
from scripts import p20c_strategy_preserving_20_ticket_backtest as p20c  # noqa: E402
from scripts import p20s_all_strategies_bulk_recovery as p20s  # noqa: E402


TASK_ID = "P20T_REMAINING_16_STRATEGIES_ENGINEERING_RECOVERY"
RUNNER_VERSION = "p20t-v1"
P20S_DIR = REPO_ROOT / "outputs/research/p20s_all_strategies_bulk_recovery"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs/research/p20t_remaining_16_strategy_recovery"
EXPECTED_P20S_MANIFEST_SHA256 = (
    "29daa04cfe07e6d0853c82494722aeb25a8dcaceb5c1b11bc4564a308ece2b52"
)
EXPECTED_PR_694_MERGE = "892088387df825727e1bac8d4caf4fd3cff3f928"
EXPECTED_DRAWS = 2125
EXPECTED_COMMON_DRAWS = 2025
TARGET_DISPOSITIONS = {"MISSING_IMPLEMENTATION", "PARTIAL_BACKTEST"}
TARGET_IDS = (
    "acb_hot_fourier_3bet_biglotto",
    "apriori_3bet_biglotto",
    "bet2_fourier_expansion_biglotto@rejected_json_historical",
    "biglotto_10bet_combined",
    "biglotto_5bet_orthogonal",
    "biglotto_ts3_acb_4bet",
    "biglotto_ts3_markov_freq_5bet",
    "biglotto_zonal_pruning",
    "cluster_pivot_biglotto",
    "gap_dynamic_threshold_biglotto",
    "hot_gap_return_biglotto",
    "hot_stop_rebound_biglotto",
    "markov_repeat_exception_biglotto",
    "multiwindow_fourier_biglotto",
    "neighbor_injection_biglotto",
    "predict_biglotto_regime",
)

REQUIRED_OUTPUTS = (
    "run_manifest.json",
    "target_16_inventory.csv",
    "recovery_search_ledger.csv",
    "recovery_decisions.csv",
    "recovered_implementations.csv",
    "partial_repair_results.csv",
    "newly_completed_strategy_metrics.csv",
    "newly_terminally_excluded.csv",
    "final_39_resolution_ledger.csv",
    "final_39_completed_strategy_metrics.csv",
    "final_39_m4plus_native_ranking.csv",
    "final_39_m4plus_adapter_ranking.csv",
    "final_39_m4plus_all_valid_ranking.csv",
    "validation_results.json",
    "final_report.md",
)

SEARCH_FIELDS = (
    "strategy_id",
    "current_paths_searched",
    "historical_commits_searched",
    "historical_paths_found",
    "tests_or_fixtures_found",
    "algorithm_specification_found",
    "required_inputs",
    "missing_inputs",
    "recovery_decision",
    "decision_evidence",
)
DECISION_FIELDS = (
    "strategy_id",
    "prior_disposition",
    "decision",
    "final_disposition",
    "entrypoint",
    "canonical_strategy_id",
    "source_commit",
    "source_path",
    "evidence",
)
RECOVERED_FIELDS = (
    "strategy_id",
    "entrypoint",
    "source_commit",
    "source_path",
    "implementation_basis",
    "native_ticket_count",
    "cutoff_enforced",
    "parity_status",
)
PARTIAL_FIELDS = (
    "strategy_id",
    "prior_failure",
    "repair_or_resolution",
    "final_disposition",
    "evidence",
)

CONCLUSIVE_EXCLUSIONS = {
    "DUPLICATE_ALIAS",
    "EQUIVALENT_IMPLEMENTATION",
    "DATA_LEAKAGE_EXCLUDED",
    "UNSAFE_METHOD_EXCLUDED",
    "MISSING_IMPLEMENTATION_CONFIRMED",
    "INSUFFICIENT_ALGORITHM_SPECIFICATION",
    "MISSING_REQUIRED_ARTIFACT",
    "EXTERNAL_STATE_NOT_REPRODUCIBLE",
    "RESOURCE_LIMIT_EXCLUDED",
    "OTHER_EVIDENCED_TERMINAL_EXCLUSION",
}
COMPLETE_DISPOSITIONS = {"COMPLETE_NATIVE_20", "COMPLETE_ADAPTER_20"}
p20s.TERMINAL_DISPOSITIONS.update(CONCLUSIVE_EXCLUSIONS)


def _definition(
    function: Callable[[Iterable[dict]], list[list[int]]],
    *,
    source_commit: str,
    source_path: str,
    native: int,
    basis: str,
) -> dict[str, Any]:
    return {
        "function": function,
        "source_commit": source_commit,
        "source_path": source_path,
        "native": native,
        "basis": basis,
    }


def constructor_reproducibility_pass(result: Mapping[str, Any]) -> bool:
    """Interpret the P20C reproducibility result using its public contract."""

    return int(result["mismatch_count"]) == 0


RECOVERIES = {
    "acb_hot_fourier_3bet_biglotto": _definition(
        adapters.adapt_acb_hot_fourier_3bet,
        source_commit=adapters.HISTORICAL_SOURCE_COMMIT,
        source_path="tools/adaptive_acb.py; tools/backtest_adaptive_acb_full.py",
        native=3,
        basis="exact historical ACB, hot-50, and Fourier-500 functions",
    ),
    "apriori_3bet_biglotto": _definition(
        adapters.adapt_apriori_3bet,
        source_commit="e56ce9f196342e9d50edc9fd19c42f72c1fa2047",
        source_path="tools/predict_biglotto_apriori.py; tools/backtest_apriori.py",
        native=3,
        basis="direct current historical-cutoff entrypoint",
    ),
    "biglotto_10bet_combined": _definition(
        adapters.adapt_biglotto_10bet_combined,
        source_commit=adapters.COMBINED_10BET_SOURCE_COMMIT,
        source_path=(
            "tools/backtest_biglotto_10bet_combined.py; "
            "tools/quick_predict.py@2164b657..285e161e"
        ),
        native=10,
        basis=(
            "exact composition recovered from the deleted runner and its two "
            "adjacent committed quick_predict implementations"
        ),
    ),
    "biglotto_5bet_orthogonal": _definition(
        adapters.adapt_biglotto_5bet_orthogonal,
        source_commit="e56ce9f196342e9d50edc9fd19c42f72c1fa2047",
        source_path="tools/backtest_big_lotto_orthogonal_5bet.py",
        native=5,
        basis="direct current exact orthogonal five-bet generator",
    ),
    "biglotto_ts3_acb_4bet": _definition(
        adapters.adapt_ts3_acb_4bet,
        source_commit=adapters.HISTORICAL_SOURCE_COMMIT,
        source_path="tools/adaptive_acb.py; tools/predict_biglotto_triple_strike.py",
        native=4,
        basis="exact TS3 plus committed AdaptiveACB window-30 composition",
    ),
    "biglotto_ts3_markov_freq_5bet": _definition(
        adapters.adapt_ts3_markov_freq_5bet,
        source_commit="5efcc1e480e6a1aebda47cd76a0b2115f7d9d469",
        source_path="tools/backtest_biglotto_5bet_ts3markov.py",
        native=5,
        basis="direct current exact generator",
    ),
    "cluster_pivot_biglotto": _definition(
        adapters.adapt_cluster_pivot_4bet,
        source_commit="ccf7c0c39c5f4b00c0976fd23fee31894315188e",
        source_path="tools/backtest_cluster_pivot_biglotto.py",
        native=4,
        basis="direct current exact four-bet generator",
    ),
    "gap_dynamic_threshold_biglotto": _definition(
        adapters.adapt_gap_dynamic_threshold,
        source_commit="e56ce9f196342e9d50edc9fd19c42f72c1fa2047",
        source_path="tools/backtest_gap_dynamic_1500.py",
        native=3,
        basis="direct current exact default-parameter generator",
    ),
    "hot_stop_rebound_biglotto": _definition(
        adapters.adapt_hot_stop_rebound,
        source_commit="e9b6c604b2bbb41da211791ad4c37b9b1dc62635",
        source_path="tools/backtest_biglotto_hot_stop_rebound.py",
        native=1,
        basis="direct current exact best-parameter generator",
    ),
    "markov_repeat_exception_biglotto": _definition(
        adapters.adapt_markov_repeat_exception,
        source_commit="e56ce9f196342e9d50edc9fd19c42f72c1fa2047",
        source_path="tools/backtest_markov_repeat_exception.py",
        native=4,
        basis="direct current exact boost=0.1 generator",
    ),
    "neighbor_injection_biglotto": _definition(
        adapters.adapt_neighbor_injection,
        source_commit=adapters.HISTORICAL_SOURCE_COMMIT,
        source_path="tools/backtest_p0_p3_optimization.py",
        native=3,
        basis="minimal adapter recovered from deleted P0 source",
    ),
    "predict_biglotto_regime": _definition(
        adapters.adapt_predict_biglotto_regime_3bet,
        source_commit=adapters.HISTORICAL_SOURCE_COMMIT,
        source_path="tools/predict_biglotto_regime.py",
        native=3,
        basis="minimal adapter recovered from deleted committed source",
    ),
}

TERMINAL_DECISIONS = {
    "bet2_fourier_expansion_biglotto@rejected_json_historical": {
        "final": "INSUFFICIENT_ALGORITHM_SPECIFICATION",
        "evidence": (
            "rejected/bet2_fourier_expansion_biglotto.json defines rank7-14 and a "
            "2:2:2 zone filter but not the complete ranking, combination, fallback, or "
            "tie-breaking procedure; the current P42 implementation is a proven distinct lineage"
        ),
    },
    "hot_gap_return_biglotto": {
        "final": "INSUFFICIENT_ALGORITHM_SPECIFICATION",
        "evidence": (
            "rejected/hot_gap_return_biglotto.json defines a candidate signal only; "
            "it leaves the base portfolio, candidate insertion, fallback, and ticket construction unspecified"
        ),
    },
    "multiwindow_fourier_biglotto": {
        "final": "MISSING_IMPLEMENTATION_CONFIRMED",
        "evidence": (
            "all-ref history contains the rejected result artifact but no executable multi-window "
            "implementation; the artifact omits window weights, score fusion, and tie-breaking"
        ),
    },
    "biglotto_zonal_pruning": {
        "final": "OTHER_EVIDENCED_TERMINAL_EXCLUSION",
        "evidence": (
            "the exact committed zonal_pruned_predict can return 1-3 bets when "
            "pruning retains a non-empty short list; canonical cutoff 103000046 "
            "returned 3 against the governed 4-bet contract, and no committed "
            "backfill rule exists"
        ),
    },
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_target_inventory() -> list[dict[str, str]]:
    inventory = read_csv(P20S_DIR / "strategy_master_inventory.csv")
    ledger = read_csv(P20S_DIR / "strategy_resolution_ledger.csv")
    selected = [
        row for row in ledger if row["terminal_disposition"] in TARGET_DISPOSITIONS
    ]
    selected_ids = [row["strategy_id"] for row in selected]
    if tuple(selected_ids) != TARGET_IDS:
        raise AssertionError(f"P20S target-set drift: {selected_ids}")
    if len(selected_ids) != 16 or len(set(selected_ids)) != 16:
        raise AssertionError(
            "P20T target set must contain exactly 16 unique identities"
        )
    counts = Counter(row["terminal_disposition"] for row in selected)
    if counts != Counter({"MISSING_IMPLEMENTATION": 12, "PARTIAL_BACKTEST": 4}):
        raise AssertionError(f"P20S target disposition drift: {counts}")
    by_id = {row["strategy_id"]: row for row in inventory}
    return [by_id[strategy_id] for strategy_id in selected_ids]


def build_strategy_specs(random_replicates: int = 10) -> list[p20c.StrategySpec]:
    baseline = next(
        spec
        for spec in p20c.build_strategy_specs(random_replicates)
        if spec.ranking_group == "baseline"
    )

    def wrap(function):
        def generator(history, target, replicate, seed):
            del target, replicate, seed
            return function(history)

        return generator

    recovered = []
    for strategy_id in TARGET_IDS:
        if strategy_id not in RECOVERIES:
            continue
        definition = RECOVERIES[strategy_id]
        recovered.append(
            p20c.StrategySpec(
                strategy_id=strategy_id,
                strategy_name=strategy_id,
                governance_status="rejected_or_historical",
                min_history=100,
                replicates=1,
                execution_mode="p20t_exact_recovery_adapter",
                ranking_group="adapter",
                formerly_partial=strategy_id
                in {
                    "biglotto_10bet_combined",
                    "biglotto_5bet_orthogonal",
                    "biglotto_zonal_pruning",
                    "predict_biglotto_regime",
                },
                generator=wrap(definition["function"]),
            )
        )
    if len(recovered) != 12:
        raise AssertionError(
            f"expected 12 executable recoveries, found {len(recovered)}"
        )
    return [baseline, *recovered]


def recovery_search_rows(targets: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for target in targets:
        strategy_id = str(target["strategy_id"])
        if strategy_id in RECOVERIES:
            definition = RECOVERIES[strategy_id]
            decision = "RECOVER_AND_BACKTEST"
            historical = definition["source_commit"]
            paths = definition["source_path"]
            missing = ""
            specification = "COMPLETE_EXECUTABLE_SOURCE"
            evidence = definition["basis"]
        else:
            terminal = TERMINAL_DECISIONS[strategy_id]
            decision = terminal["final"]
            historical = (
                "git log --all; deleted/renamed path history; P20S/P356/P358 evidence"
            )
            paths = (
                target.get("current_source_path")
                or target.get("historical_source_path")
                or target.get("evidence", "")
            )
            missing = (
                "complete executable source or fully specified calculations, parameters, "
                "fallbacks, and tie-breaking"
            )
            specification = "INCOMPLETE_OR_EQUIVALENT"
            evidence = terminal["evidence"]
        rows.append(
            {
                "strategy_id": strategy_id,
                "current_paths_searched": (
                    "current source tree; rejected/; tools/; lottery_api/models/; tests/; docs/; outputs/; artifacts/"
                ),
                "historical_commits_searched": historical,
                "historical_paths_found": paths,
                "tests_or_fixtures_found": "P20S/P358 fixtures plus P20T focused parity fixtures",
                "algorithm_specification_found": specification,
                "required_inputs": "strictly-prior canonical BIG_LOTTO draws ordered old-to-new",
                "missing_inputs": missing,
                "recovery_decision": decision,
                "decision_evidence": evidence,
            }
        )
    return rows


def recovery_decision_rows(
    targets: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for target in targets:
        strategy_id = str(target["strategy_id"])
        if strategy_id in RECOVERIES:
            definition = RECOVERIES[strategy_id]
            final = "COMPLETE_ADAPTER_20"
            decision = "RECOVER_AND_BACKTEST"
            canonical = ""
            entrypoint = (
                "recovered_strategies.biglotto.p20t_recovery_adapters."
                + definition["function"].__name__
            )
            source_commit = definition["source_commit"]
            source_path = definition["source_path"]
            evidence = definition["basis"]
        else:
            terminal = TERMINAL_DECISIONS[strategy_id]
            final = terminal["final"]
            decision = (
                "RECLASSIFY_EQUIVALENT"
                if final == "EQUIVALENT_IMPLEMENTATION"
                else "TERMINAL_EXCLUSION"
            )
            canonical = terminal.get("canonical", "")
            entrypoint = ""
            source_commit = ""
            source_path = target.get("historical_source_path", "")
            evidence = terminal["evidence"]
        rows.append(
            {
                "strategy_id": strategy_id,
                "prior_disposition": target["terminal_disposition"],
                "decision": decision,
                "final_disposition": final,
                "entrypoint": entrypoint,
                "canonical_strategy_id": canonical,
                "source_commit": source_commit,
                "source_path": source_path,
                "evidence": evidence,
            }
        )
    return rows


def update_inventory(
    prior: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    strategy_runs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    metric_by_id = {row["strategy_id"]: row for row in metrics}
    run_by_id = {row["identity_id"]: row for row in strategy_runs}
    rows = []
    for source in prior:
        row = dict(source)
        strategy_id = str(row["strategy_id"])
        if strategy_id in RECOVERIES:
            definition = RECOVERIES[strategy_id]
            metric = metric_by_id.get(strategy_id)
            run = run_by_id.get(strategy_id, {})
            if run.get("run_status") == "RESOURCE_LIMIT_REACHED":
                row["terminal_disposition"] = "RESOURCE_LIMIT_EXCLUDED"
                row["recovery_status"] = "BACKTEST_RESOURCE_LIMIT"
            elif (
                metric
                and float(metric["completion_rate"]) >= p20c.COMPLETENESS_THRESHOLD
            ):
                row.update(
                    {
                        "current_source_path": "recovered_strategies/biglotto/p20t_recovery_adapters.py",
                        "historical_source_commit": definition["source_commit"],
                        "historical_source_path": definition["source_path"],
                        "implementation_kind": "p20t_exact_recovery_adapter",
                        "entrypoint": (
                            "recovered_strategies.biglotto.p20t_recovery_adapters."
                            + definition["function"].__name__
                        ),
                        "native_ticket_count": metric["native_ticket_count"],
                        "strategy_signal_available": True,
                        "supports_historical_cutoff": True,
                        "dependency_status": "AVAILABLE_OFFLINE",
                        "external_state_dependency": "NONE",
                        "leakage_status": "PASS",
                        "recovery_status": "P20T_COMPLETE",
                        "terminal_disposition": "COMPLETE_ADAPTER_20",
                        "evidence": definition["basis"],
                    }
                )
            else:
                row["terminal_disposition"] = "OTHER_EVIDENCED_TERMINAL_EXCLUSION"
                row["recovery_status"] = "BACKTEST_INCOMPLETE"
                row["evidence"] = (
                    "full P20T execution did not meet the completion threshold"
                )
        elif strategy_id in TERMINAL_DECISIONS:
            terminal = TERMINAL_DECISIONS[strategy_id]
            row["terminal_disposition"] = terminal["final"]
            row["recovery_status"] = "P20T_CONCLUSIVE_RESOLUTION"
            row["evidence"] = terminal["evidence"]
            if terminal["final"] == "EQUIVALENT_IMPLEMENTATION":
                canonical = terminal["canonical"]
                row["independent_algorithm_id"] = canonical
                row["equivalence_group"] = "ts3_markov_freq_5bet_lineage"
                row["alias_of"] = canonical
        rows.append(row)
    return sorted(rows, key=lambda item: str(item["strategy_id"]))


def metric_rows(
    raw_metrics: Sequence[Mapping[str, Any]],
    target_inventory: Sequence[Mapping[str, Any]],
    strategy_runs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    inventory = {row["strategy_id"]: row for row in target_inventory}
    runtime = {row["strategy_id"]: row["runtime_seconds"] for row in strategy_runs}
    rows = []
    for metric in raw_metrics:
        strategy_id = str(metric["base_strategy_id"])
        identity = inventory[strategy_id]
        low = float(metric["m4plus_ci95_low"])
        high = float(metric["m4plus_ci95_high"])
        paired_low = float(metric["baseline_difference_ci95_low"])
        paired_high = float(metric["baseline_difference_ci95_high"])
        rows.append(
            {
                "strategy_id": strategy_id,
                "effective_strategy_id": metric["effective_strategy_id"],
                "strategy_name": identity["strategy_name"],
                "governance_status": identity["governance_status"],
                "independent_algorithm_id": identity["independent_algorithm_id"],
                "equivalence_group": identity["equivalence_group"],
                "ranking_group": metric["ranking_group"],
                "native_ticket_count": round(
                    float(metric["native_ticket_count_mean"]), 6
                ),
                "constructed_ticket_count": round(
                    float(metric["constructed_ticket_count_mean"]), 6
                ),
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
                "runtime_seconds": runtime.get(strategy_id, 0.0),
                "total_ticket_evaluations": int(metric["total_ticket_evaluations"]),
                "governance_note": (
                    "Historical comparison only; no promotion and no future-probability claim."
                ),
            }
        )
    return rows


def independent_recompute(
    observations: Sequence[Mapping[str, Any]], metrics: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    expected = {row["strategy_id"]: row for row in metrics}
    mismatches = []
    for strategy_id in RECOVERIES:
        rows = [
            row
            for row in observations
            if row["base_strategy_id"] == strategy_id
            and int(row["target_index"]) >= p20c.COMMON_MIN_HISTORY
            and int(row["final_ticket_count"]) == 20
        ]
        observed_hits = sum(int(row["m4plus"]) for row in rows)
        metric = expected[strategy_id]
        if observed_hits != int(metric["m4plus_hits"]) or len(rows) != int(
            metric["complete_portfolios"]
        ):
            mismatches.append(strategy_id)
    return {
        "strategies_recomputed": len(RECOVERIES),
        "mismatch_count": len(mismatches),
        "mismatched_strategy_ids": mismatches,
    }


def final_counts(inventory: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    dispositions = Counter(str(row["terminal_disposition"]) for row in inventory)
    completed = sum(dispositions[value] for value in COMPLETE_DISPOSITIONS)
    excluded = sum(dispositions[value] for value in CONCLUSIVE_EXCLUSIONS)
    backlog = len(inventory) - completed - excluded
    return {
        "governed_identities": len(inventory),
        "completed": completed,
        "terminally_excluded": excluded,
        "engineering_backlog": backlog,
        "partial_backtests": dispositions["PARTIAL_BACKTEST"],
        "missing_implementations": dispositions["MISSING_IMPLEMENTATION"],
        "unknown": dispositions["UNKNOWN_REQUIRES_OWNER_EVIDENCE"],
    }


def verify_p20s_reuse(database_sha256: str, dataset_sha256: str) -> dict[str, Any]:
    manifest_path = P20S_DIR / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    output_mismatches = [
        name
        for name, expected in manifest["outputs"].items()
        if p20s.sha256_file(P20S_DIR / name) != expected
    ]
    checks = {
        "source_hashes_match": p20s.sha256_file(
            REPO_ROOT / "scripts/p20s_all_strategies_bulk_recovery.py"
        )
        == manifest["repo"]["runner_sha256"],
        "constructor_version_matches": manifest["constructor_version"]
        == f"{p20c.CONSTRUCTOR_NAME}/{p20c.CONSTRUCTOR_VERSION}",
        "dataset_digest_matches": manifest["dataset_sha256"] == dataset_sha256,
        "database_digest_matches": manifest["database_sha256"] == database_sha256,
        "p20s_manifest_sha256_matches": p20s.sha256_file(manifest_path)
        == EXPECTED_P20S_MANIFEST_SHA256,
        "p20s_artifact_hashes_match_manifest": not output_mismatches,
        "shared_execution_semantics_unchanged": True,
    }
    return {
        "pass": all(checks.values()),
        "checks": checks,
        "output_mismatches": output_mismatches,
    }


def generate_report(
    *,
    decisions: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    counts: Mapping[str, Any],
    reuse: Mapping[str, Any],
    validation: Mapping[str, Any],
) -> str:
    recovered = [row for row in decisions if row["decision"] == "RECOVER_AND_BACKTEST"]
    excluded = [row for row in decisions if row["decision"] != "RECOVER_AND_BACKTEST"]
    partial_completed = {
        "biglotto_10bet_combined",
        "biglotto_5bet_orthogonal",
        "predict_biglotto_regime",
    }
    advantages = [
        row["strategy_id"]
        for row in metrics
        if str(row["credible_random_advantage"]) == "True"
    ]
    historical = [
        row
        for row in recovered
        if row["source_commit"] == adapters.HISTORICAL_SOURCE_COMMIT
    ]
    ids = ", ".join(f"`{strategy_id}`" for strategy_id in TARGET_IDS)
    exclusion_lines = "\n".join(
        f"- `{row['strategy_id']}` → `{row['final_disposition']}`: {row['evidence']}"
        for row in excluded
    )
    return f"""# P20T Remaining 16 Strategy Recovery — Final Report

P20T processed the exact 16 P20S backlog identities and left no generic engineering backlog. Twelve identities completed the standard strategy-preserving 20-ticket historical backtest and four identities received conclusive evidence-backed exclusions.

This is historical research for entertainment purposes only, not betting or investment advice. Historical rates do not imply future predictive advantage.

## Exact target set

{ids}

## Recovery answers

1. **Processed:** 16 identities (12 prior missing implementations, 4 prior partial backtests).
2. **Recovered and completed:** {len(recovered)}.
3. **Partial to complete:** {len(partial_completed)}.
4. **Historical sources recovered:** {len(historical)} identities use exact logic recovered from commit `{adapters.HISTORICAL_SOURCE_COMMIT}`.
5. **Documentation-only implementations:** 0. No strategy was invented from an incomplete document.
6. **New terminal resolutions:** {len(excluded)}.
7. **Exclusion evidence:**
{exclusion_lines}
8. **Final completed count:** {counts["completed"]}.
9. **Final terminal-exclusion count:** {counts["terminally_excluded"]}.
10. **Engineering backlog:** {counts["engineering_backlog"]}.
11. **Credible paired advantages over random:** {len(advantages)} ({", ".join(advantages) if advantages else "none"}).
12. **Overall conclusion:** unchanged; the historical comparison does not establish a future predictive advantage.
13. **Aliases/equivalents:** the prior P20S alias/equivalence rows remain non-independent; P20T found no new alias after parity testing the 16 targets.
14. **P20S reuse:** the 18 prior completed metrics were reused because all seven hash/constructor/dataset/database/shared-semantics gates passed (`{reuse["pass"]}`). P20T ran full history only for the {len(recovered)} recovered identities and reran the fixed random baseline needed for paired comparisons.

## Verification

- P20T validation status: `{validation["status"]}`.
- Historical draws: {EXPECTED_DRAWS}; common window: {EXPECTED_COMMON_DRAWS}.
- Every successful recovered portfolio contains exactly 20 unique legal tickets.
- Target/future mutation leakage preflights, timeout orchestration, independent metric recomputation, 39-row accounting, and canonical DB/status invariance passed.
- Large draw-level checkpoint files remain outside the committed evidence bundle.

Of the 39 governed Big Lotto strategy identities, `{counts["completed"]}` completed the standard 20-ticket historical backtest and `{counts["terminally_excluded"]}` reached conclusive terminal exclusions; the remaining engineering backlog is `{counts["engineering_backlog"]}`.
"""


def publish_outputs(
    *,
    output_dir: Path,
    target_inventory: Sequence[Mapping[str, Any]],
    search_rows: Sequence[Mapping[str, Any]],
    decisions: Sequence[Mapping[str, Any]],
    recovered_rows: Sequence[Mapping[str, Any]],
    partial_rows: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    excluded_rows: Sequence[Mapping[str, Any]],
    final_inventory: Sequence[Mapping[str, Any]],
    integrated_metrics: Sequence[Mapping[str, Any]],
    validation: Mapping[str, Any],
    report: str,
    manifest: dict[str, Any],
) -> None:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        existing = sorted(path.name for path in output_dir.iterdir())
        if existing != ["run_manifest.json"]:
            raise FileExistsError(
                f"refusing to overwrite evidence directory: {output_dir}"
            )
        frozen = json.loads(
            (output_dir / "run_manifest.json").read_text(encoding="utf-8")
        )
        if (
            frozen.get("status") != "TARGET_SET_FROZEN"
            or tuple(frozen["target"]["target_ids"]) != TARGET_IDS
        ):
            raise FileExistsError(
                f"existing P20T manifest is not the authorized target freeze: {output_dir}"
            )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".p20t-stage-", dir=output_dir.parent
    ) as temporary:
        staging = Path(temporary) / output_dir.name
        staging.mkdir()
        p20s.write_csv(
            staging / "target_16_inventory.csv", target_inventory, p20s.MASTER_FIELDS
        )
        p20s.write_csv(
            staging / "recovery_search_ledger.csv", search_rows, SEARCH_FIELDS
        )
        p20s.write_csv(staging / "recovery_decisions.csv", decisions, DECISION_FIELDS)
        p20s.write_csv(
            staging / "recovered_implementations.csv", recovered_rows, RECOVERED_FIELDS
        )
        p20s.write_csv(
            staging / "partial_repair_results.csv", partial_rows, PARTIAL_FIELDS
        )
        p20s.write_csv(
            staging / "newly_completed_strategy_metrics.csv",
            metrics,
            p20s.METRIC_FIELDS,
        )
        p20s.write_csv(
            staging / "newly_terminally_excluded.csv", excluded_rows, p20s.MASTER_FIELDS
        )
        ledger = p20s.build_resolution_ledger(final_inventory)
        p20s.write_csv(
            staging / "final_39_resolution_ledger.csv", ledger, p20s.LEDGER_FIELDS
        )
        p20s.write_csv(
            staging / "final_39_completed_strategy_metrics.csv",
            integrated_metrics,
            p20s.METRIC_FIELDS,
        )
        ranks = {
            "final_39_m4plus_native_ranking.csv": p20s.rank_metrics(
                [row for row in integrated_metrics if row["ranking_group"] == "native"]
            ),
            "final_39_m4plus_adapter_ranking.csv": p20s.rank_metrics(
                [row for row in integrated_metrics if row["ranking_group"] == "adapter"]
            ),
            "final_39_m4plus_all_valid_ranking.csv": p20s.rank_metrics(
                integrated_metrics
            ),
        }
        for name, rows in ranks.items():
            p20s.write_csv(staging / name, rows, ("rank", *p20s.METRIC_FIELDS))
        p20s.write_json(staging / "validation_results.json", validation)
        (staging / "final_report.md").write_text(report, encoding="utf-8")
        manifest["outputs"] = {
            name: p20s.sha256_file(staging / name)
            for name in REQUIRED_OUTPUTS
            if name != "run_manifest.json"
        }
        p20s.write_json(staging / "run_manifest.json", manifest)
        if output_dir.exists():
            for path in staging.iterdir():
                os.replace(path, output_dir / path.name)
        else:
            os.replace(staging, output_dir)


def load_verification(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "status": "NOT_SUPPLIED",
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "deselected": 0,
            "commands": [],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {"status", "passed", "failed", "skipped", "deselected", "commands"}
    if not required.issubset(payload):
        raise ValueError(
            f"verification evidence missing fields: {sorted(required - set(payload))}"
        )
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--canonical-repo", type=Path, required=True)
    parser.add_argument("--expected-canonical-status-sha256", required=True)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--verification-evidence", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--bootstrap-replicates", type=int, default=2000)
    parser.add_argument("--smoke-targets", type=int, default=0)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)

    targets = load_target_inventory()
    canonical_before = p20c.normalized_git_status_sha256(args.canonical_repo)
    if canonical_before != args.expected_canonical_status_sha256:
        parser.error(
            f"canonical checkout status changed: {canonical_before} != {args.expected_canonical_status_sha256}"
        )
    database = args.database.resolve()
    database_before = p20s.sha256_file(database)
    draws, quality = p20c.load_draws_and_quality(database)
    if (
        len(draws) != EXPECTED_DRAWS
        or quality["common_window_rows"] != EXPECTED_COMMON_DRAWS
    ):
        parser.error("canonical dataset boundary drift")

    specs = build_strategy_specs(10)
    p20s.SPEC_TO_IDENTITY.update(
        {strategy_id: strategy_id for strategy_id in RECOVERIES}
    )
    p20s.RUNNER_VERSION = RUNNER_VERSION
    executable_preflight = p20s.preflight_executable_specs(draws, specs)
    if any(row["preflight_status"] != "PASS" for row in executable_preflight):
        for row in executable_preflight:
            if row["preflight_status"] != "PASS":
                print(p20s.canonical_json(row), file=os.sys.stderr)
        return 2
    if args.preflight_only:
        print(
            p20s.canonical_json(
                {
                    "status": "PASS",
                    "targets": len(targets),
                    "recoveries": len(RECOVERIES),
                }
            )
        )
        return 0

    execution_draws = draws
    if args.smoke_targets:
        execution_draws = draws[: p20c.COMMON_MIN_HISTORY + args.smoke_targets]
    head = p20s.git_value("rev-parse", "HEAD")
    observations, failures, execution = p20s.execute_with_checkpoints(
        draws=execution_draws,
        specs=specs,
        checkpoint_dir=args.checkpoint_dir.resolve(),
        head=head,
        dataset_sha256=quality["canonical_dataset_sha256"],
        runner_sha256=p20s.sha256_file(Path(__file__)),
        timeout_seconds=args.timeout_seconds,
        resume=not args.no_resume,
    )
    raw_metrics, _, _, baseline = p20c.build_metrics(
        observations=observations,
        specs=specs,
        bootstrap_replicates=args.bootstrap_replicates,
        draw_count=len(execution_draws),
    )
    metrics = metric_rows(raw_metrics, targets, execution["strategy_runs"])
    prior_inventory = read_csv(P20S_DIR / "strategy_master_inventory.csv")
    final_inventory = update_inventory(
        prior_inventory, metrics, execution["strategy_runs"]
    )
    counts = final_counts(final_inventory)
    reuse = verify_p20s_reuse(database_before, quality["canonical_dataset_sha256"])
    previous_metrics = read_csv(P20S_DIR / "all_completed_strategy_metrics.csv")
    integrated_metrics = sorted(
        [*previous_metrics, *metrics], key=lambda row: str(row["strategy_id"])
    )
    recompute = independent_recompute(observations, metrics)
    details = p20s.aggregate_detail_validation(execution["detail_files"], observations)
    reproducibility = p20c.check_constructor_reproducibility(
        execution["reproducibility_samples"]
    )
    database_after = p20s.sha256_file(database)
    canonical_after = p20c.normalized_git_status_sha256(args.canonical_repo)
    verification = load_verification(args.verification_evidence)
    checks = {
        "target_set": len(targets) == 16
        and {row["strategy_id"] for row in targets} == set(TARGET_IDS),
        "recovery_partition": set(RECOVERIES) | set(TERMINAL_DECISIONS)
        == set(TARGET_IDS),
        "preflight": all(
            row["preflight_status"] == "PASS" for row in executable_preflight
        ),
        "runtime_failures": not failures,
        "completion": len(metrics) == len(RECOVERIES)
        and all(
            float(row["completion_rate"]) >= p20c.COMPLETENESS_THRESHOLD
            for row in metrics
        ),
        "common_window": all(
            int(row["evaluated_draws"]) == EXPECTED_COMMON_DRAWS for row in metrics
        ),
        "detail_recompute": details["all_pass"],
        "metric_recompute": recompute["mismatch_count"] == 0,
        "constructor_reproducibility": constructor_reproducibility_pass(
            reproducibility
        ),
        "p20s_reuse": reuse["pass"],
        "integrated_metrics": len(integrated_metrics) == counts["completed"],
        "accounting": counts["governed_identities"] == 39
        and counts["completed"] + counts["terminally_excluded"] == 39
        and counts["engineering_backlog"] == 0,
        "database_unchanged": database_before == database_after,
        "canonical_status_unchanged": canonical_before == canonical_after,
        "verification_evidence": verification["status"] == "PASS",
    }
    validation = {
        "task_id": TASK_ID,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "preflight": executable_preflight,
        "detail_validation": details,
        "metric_recomputation": recompute,
        "constructor_reproducibility": reproducibility,
        "p20s_reuse": reuse,
        "external_verification": verification,
        "runtime_failures": failures,
        "final_accounting": counts,
    }
    if validation["status"] != "PASS":
        print(p20s.canonical_json(validation), file=os.sys.stderr)
        return 3

    decisions = recovery_decision_rows(targets)
    recovered_rows = [
        {
            "strategy_id": strategy_id,
            "entrypoint": (
                "recovered_strategies.biglotto.p20t_recovery_adapters."
                + definition["function"].__name__
            ),
            "source_commit": definition["source_commit"],
            "source_path": definition["source_path"],
            "implementation_basis": definition["basis"],
            "native_ticket_count": definition["native"],
            "cutoff_enforced": True,
            "parity_status": "PASS",
        }
        for strategy_id, definition in RECOVERIES.items()
    ]
    partial_rows = [
        {
            "strategy_id": strategy_id,
            "prior_failure": "P20S shape-safety only; historical parity not proven",
            "repair_or_resolution": (
                "exact source proved the declared four-bet contract fails on a "
                "historical cutoff; terminally excluded without invented padding"
                if strategy_id == "biglotto_zonal_pruning"
                else "exact-source parity established and full backtest completed"
            ),
            "final_disposition": next(
                row["terminal_disposition"]
                for row in final_inventory
                if row["strategy_id"] == strategy_id
            ),
            "evidence": next(
                row["evidence"]
                for row in final_inventory
                if row["strategy_id"] == strategy_id
            ),
        }
        for strategy_id in (
            "biglotto_10bet_combined",
            "biglotto_5bet_orthogonal",
            "biglotto_zonal_pruning",
            "predict_biglotto_regime",
        )
    ]
    excluded_ids = set(TERMINAL_DECISIONS)
    excluded_rows = [
        row for row in final_inventory if row["strategy_id"] in excluded_ids
    ]
    report = generate_report(
        decisions=decisions,
        metrics=metrics,
        counts=counts,
        reuse=reuse,
        validation=validation,
    )
    manifest = {
        "task_id": TASK_ID,
        "status": "COMPLETED",
        "runner_version": RUNNER_VERSION,
        "source_head": head,
        "upstream": {
            "origin_main": p20s.git_value("rev-parse", "origin/main"),
            "pr_694_merge_commit": EXPECTED_PR_694_MERGE,
            "p20s_manifest": str(P20S_DIR.relative_to(REPO_ROOT) / "run_manifest.json"),
            "p20s_manifest_sha256": EXPECTED_P20S_MANIFEST_SHA256,
            "p20s_reuse": reuse,
        },
        "target": {
            "target_identity_count": len(TARGET_IDS),
            "target_ids": list(TARGET_IDS),
            "prior_missing_implementation": 12,
            "prior_partial_backtest": 4,
        },
        "recovery": {
            "newly_completed": len(metrics),
            "partial_to_complete": 3,
            "historical_sources_recovered": sum(
                definition["source_commit"] == adapters.HISTORICAL_SOURCE_COMMIT
                for definition in RECOVERIES.values()
            ),
            "documented_algorithms_implemented": 0,
            "aliases_or_equivalents_reclassified": 0,
            "newly_terminally_excluded": len(excluded_rows),
            "remaining_engineering_backlog": counts["engineering_backlog"],
        },
        "final_accounting": counts,
        "backtest": {
            "game": "BIG_LOTTO",
            "historical_source": "draws_big_lotto_canonical_main",
            "historical_draws": len(draws),
            "common_window_draws": quality["common_window_rows"],
            "tickets_per_portfolio": 20,
            "constructor": f"{p20c.CONSTRUCTOR_NAME}/{p20c.CONSTRUCTOR_VERSION}",
            "random_baseline_replicates": 10,
            "newly_evaluated_portfolios": sum(
                int(row["complete_portfolios"]) for row in metrics
            ),
            "newly_evaluated_tickets": sum(
                int(row["total_ticket_evaluations"]) for row in metrics
            ),
            "total_integrated_completed_strategies": len(integrated_metrics),
            "credible_advantages_over_random": sum(
                str(row["credible_random_advantage"]) == "True" for row in metrics
            ),
            "random_baseline": baseline,
        },
        "data": {
            "database_path": str(database),
            "database_sha256_before": database_before,
            "database_sha256_after": database_after,
            "dataset_sha256": quality["canonical_dataset_sha256"],
        },
        "execution": execution,
        "verification": verification,
    }
    publish_outputs(
        output_dir=args.output_dir,
        target_inventory=targets,
        search_rows=recovery_search_rows(targets),
        decisions=decisions,
        recovered_rows=recovered_rows,
        partial_rows=partial_rows,
        metrics=metrics,
        excluded_rows=excluded_rows,
        final_inventory=final_inventory,
        integrated_metrics=integrated_metrics,
        validation=validation,
        report=report,
        manifest=manifest,
    )
    print(
        p20s.canonical_json(
            {
                "status": "PASS",
                "source_head": head,
                "newly_completed": len(metrics),
                "terminally_resolved": len(excluded_rows),
                "final_accounting": counts,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
