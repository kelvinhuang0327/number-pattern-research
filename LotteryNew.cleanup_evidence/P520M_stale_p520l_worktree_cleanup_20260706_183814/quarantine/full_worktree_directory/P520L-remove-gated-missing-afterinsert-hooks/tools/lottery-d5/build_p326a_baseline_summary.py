#!/usr/bin/env python3
"""Deterministically derive the P326A D5 baseline-summary render payload + provenance.

Inputs are IN-REPO ONLY (the byte-identical P325A artifacts copied under
public/demo-data/lottery-d5/p325a/). No DB is opened, no network, no randomness.
Re-running produces byte-identical JSON, so the committed files can be regenerated
and audited from repo contents alone.

The numeric fields are recomputed from the copied, SHA256-verified P325A metrics CSV
(equal_budget_baseline_metrics.csv). This does NOT change any P325A conclusion; it only
re-expresses the same descriptive aggregates for the D5 product surface.
"""
from __future__ import annotations

import collections
import csv
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
P325A_DIR = REPO_ROOT / "public" / "demo-data" / "lottery-d5" / "p325a"

CARRIER = "daily539_f4cold_5bet"

# From the verified P325A evidence root manifest.json (payload_artifacts + repo_head).
SOURCE_TASK_ID = "P325A_D5_EQUAL_BUDGET_BASELINE_ANALYSIS_READ_ONLY"
SOURCE_CLASSIFICATION = "P325A_D5_EQUAL_BUDGET_BASELINE_COMPLETE_WITH_LIMITATIONS"
SOURCE_EVIDENCE_ROOT = "/Users/kelvin/Kelvin-WorkSpace/p325a_d5_equal_budget_baseline_analysis_20260701_145150"
SOURCE_REPO_HEAD = "fce02f0dc271274f7cffc54de527f0262e4f4830"
SOURCE_MANIFEST_SHA256 = "4f70f257eefe5bd165c88e6579e9f97047139d80e884c3621e9163ebd36466d7"

# Byte-identical copies; SHA256 taken from the P325A manifest payload_artifacts.
COPIED_ARTIFACTS = {
    "equal_budget_baseline_summary.md": "e7af4c900db3929d4417173c8a910c3931e306cbfdcd73b5e23ad04ee75cea38",
    "equal_budget_baseline_metrics.csv": "74bd38c01b6b1e24cf3ead12d64528ce048f4585aae3b3fb712564b8ffbe3932",
    "budget_bias_diagnostics.csv": "e49f1909463fe976f7504bf0cae0d5efe7e469cae33dc4b957cdc152ccd69d50",
    "random_baseline_reference.csv": "2fe10a459c2abb0c8ef9853458095621f9ce0004095b7eae0d380f18de28e01b",
    "baseline_method.md": "8b1d5f1a62592e870b94af0e2e17249edf3fb640e0a27563965dc1b647bdbe92",
    "limitations.md": "4902a3f35028278fa70154621df7d9a6696d00662b2a022e020fc41ef31d9af2",
    "handoff_report.md": "3b428898fa5939e65e0dabc8f206c67f310ac333f8a7cb8296f6850e4888f57a",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def attest_copies() -> None:
    for name, want in COPIED_ARTIFACTS.items():
        got = sha256(P325A_DIR / name)
        if got != want:
            raise SystemExit(f"copied artifact hash mismatch for {name}: {got} != {want}")


def read_metrics() -> list[dict]:
    with (P325A_DIR / "equal_budget_baseline_metrics.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def build_summary(rows: list[dict]) -> dict:
    n_rows = len(rows)
    n_tests = n_rows * 2  # k in {2, 3}
    alpha = 0.05 / n_tests

    def delta(key: str) -> list[float]:
        return [float(r[key]) for r in rows]

    d1 = delta("descriptive_delta_vs_baseline_hit_at_least_1")
    d2 = delta("descriptive_delta_vs_baseline_hit_at_least_2")
    d3 = delta("descriptive_delta_vs_baseline_hit_at_least_3")

    passing = [
        r for r in rows
        if float(r["binom_p_hit_at_least_2_one_sided"]) < alpha
        or float(r["binom_p_hit_at_least_3_one_sided"]) < alpha
    ]
    passing_k2 = sum(1 for r in passing if float(r["binom_p_hit_at_least_2_one_sided"]) < alpha)
    passing_k3 = sum(1 for r in passing if float(r["binom_p_hit_at_least_3_one_sided"]) < alpha)
    carrier_rows = [r for r in passing if CARRIER in r["strategy_ids"].split("|")]
    big_passing = [r for r in passing if r["lottery_type"] == "BIG_LOTTO"]

    # Same-budget cross-size decisive example (observed only, no baseline):
    # DAILY_539, recent_50, budget m=5, single vs triple, hit>=2.
    def same_budget(size: str) -> float:
        vals = [
            float(r["hit_at_least_2_rate"]) for r in rows
            if r["lottery_type"] == "DAILY_539"
            and r["window"] == "recent_50"
            and r["ticket_budget_m"] == "5"
            and r["combination_size"] == size
        ]
        return mean(vals)

    single_rate = same_budget("1")
    triple_rate = same_budget("3")

    return {
        "task_id": "P326A_D5_BASELINE_RESULTS_STATIC_UI_IMPORT",
        "source_task_id": SOURCE_TASK_ID,
        "source_classification": SOURCE_CLASSIFICATION,
        "classification": "DESCRIPTIVE_ONLY",
        "generated_from": "public/demo-data/lottery-d5/p325a/equal_budget_baseline_metrics.csv",
        "recomputation_note": (
            "Aggregates recomputed from the copied, SHA256-verified P325A metrics CSV. "
            "Same descriptive result as P325A; no conclusion changed."
        ),
        "baseline_status": "COMPUTED",
        "baseline_status_label": (
            "Matched-budget random baseline computed (analytic hypergeometric, 1-(1-q_k)^m)."
        ),
        "equal_budget_raw_subsampling_status": "INSUFFICIENT_RAW_DATA",
        "equal_budget_raw_subsampling_label": (
            "Raw per-draw equal-budget subsampling: insufficient raw data. Per-draw / per-ticket "
            "hit vectors are absent from the static aggregates, so an empirical equal-budget "
            "subsample of the strategies' own tickets is not possible. Nothing was fabricated."
        ),
        "budget_definition": (
            "Ticket budget m = sample_size_rows / sample_size_draws = the number of tickets a "
            "combination spends per draw. Member strategies emit 1-3 tickets each, so m varies "
            "within every combination size and raw hit rates are budget-confounded."
        ),
        "n_metric_rows": n_rows,
        "mean_matched_budget_delta": {
            "hit_at_least_1": round(mean(d1), 4),
            "hit_at_least_2": round(mean(d2), 4),
            "hit_at_least_3": round(mean(d3), 4),
        },
        "positive_delta_rows": {
            "hit_at_least_1": sum(1 for v in d1 if v > 0),
            "hit_at_least_2": sum(1 for v in d2 if v > 0),
            "hit_at_least_3": sum(1 for v in d3 if v > 0),
            "of_total": n_rows,
        },
        "same_budget_example": {
            "lottery": "DAILY_539",
            "window": "recent_50",
            "budget_m": 5,
            "metric": "hit_at_least_2",
            "single_rate": round(single_rate, 3),
            "triple_rate": round(triple_rate, 3),
            "conclusion": (
                "At the same ticket budget the single strategy scores higher than triples; "
                "combining dilutes rather than adds."
            ),
        },
        "big_lotto_summary": {
            "rows_passing_screen": len(big_passing),
            "label": (
                "Matched-budget deltas hover at or below zero and no BIG_LOTTO combination beats "
                "the equal-budget random null - consistent with 6/49 being indistinguishable from "
                "fair random."
            ),
        },
        "inferential_screen": {
            "method": "exact one-sided binomial vs equal-budget-random null, k in {2, 3}",
            "n_tests": n_tests,
            "bonferroni_alpha": alpha,
            "rows_passing": len(passing),
            "by_lottery": dict(sorted(collections.Counter(r["lottery_type"] for r in passing).items())),
            "by_window": dict(sorted(collections.Counter(r["window"] for r in passing).items())),
            "by_combination_size": dict(
                sorted(collections.Counter(r["combination_size"] for r in passing).items())
            ),
            "passing_via_k2": passing_k2,
            "passing_via_k3": passing_k3,
            "signal_carrier_strategy": CARRIER,
            "signal_carrier_rows": len(carrier_rows),
            "signal_carrier_of_passing": len(passing),
            "non_carrier_passing": len(passing) - len(carrier_rows),
            "interpretation": (
                "All passing rows are DAILY_539 at k=2 and are not independent (nested windows + "
                "shared members). The observed single-strategy signal carrier "
                f"{CARRIER} appears in {len(carrier_rows)} of {len(passing)} passing rows; removing "
                "it collapses the passing set. This is inherited single-strategy behaviour, not "
                "combination synergy."
            ),
        },
        "headline": (
            "Raw combination hit-rate gains mostly reflect more tickets. At equal ticket budget, "
            "larger combinations do not show a clear advantage."
        ),
        "non_claim": (
            "This is a descriptive baseline check only - not a prediction, not a betting "
            "recommendation, and it does not recommend any numbers to play."
        ),
        "caveats": [
            "DESCRIPTIVE_ONLY. A baseline result does not prove any future edge.",
            "Equal-budget comparison is against an analytic random reference (m independent uniform tickets), not an empirical subsample of the strategies' own tickets.",
            "Binomial screen tests each row against its own equal-budget-random null; rows are not independent (nested windows + shared members), so Bonferroni survivor counts are indicative, not a formal guarantee.",
            "POWER_LOTTO excluded / not scored.",
            "Windows and samples inherited verbatim from P320A (recent_50 / recent_300 / recent_750 common draws).",
        ],
    }


def build_provenance() -> dict:
    return {
        "task_id": "P326A_D5_BASELINE_RESULTS_STATIC_UI_IMPORT",
        "source_task_id": SOURCE_TASK_ID,
        "source_classification": SOURCE_CLASSIFICATION,
        "source_evidence_root": SOURCE_EVIDENCE_ROOT,
        "source_repo_head": SOURCE_REPO_HEAD,
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "copy_mode": "byte-for-byte unchanged static files",
        "derived_files": [
            {
                "path": "baseline_summary.json",
                "derivation": (
                    "Deterministic recomputation of P325A descriptive aggregates from the copied "
                    "equal_budget_baseline_metrics.csv via tools/lottery-d5/build_p326a_baseline_summary.py. "
                    "No conclusion changed."
                ),
            }
        ],
        "artifacts": [
            {
                "path": name,
                "source_sha256": want,
                "copied_sha256": sha256(P325A_DIR / name),
            }
            for name, want in sorted(COPIED_ARTIFACTS.items())
        ],
        "baseline_mode": "computed_matched_budget_random_reference",
        "inferential_status": "DESCRIPTIVE_ONLY",
        "power_lotto_scoring": "NOT RUN",
    }


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    attest_copies()
    rows = read_metrics()
    write_json(P325A_DIR / "baseline_summary.json", build_summary(rows))
    write_json(P325A_DIR / "source_provenance.json", build_provenance())
    print(f"wrote {P325A_DIR / 'baseline_summary.json'}")
    print(f"wrote {P325A_DIR / 'source_provenance.json'}")


if __name__ == "__main__":
    main()
