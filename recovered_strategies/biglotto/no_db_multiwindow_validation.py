"""P360 no-DB multi-window walk-forward validation for parity-tier Big Lotto adapters.

Quarantined from production registries and DB-backed loaders: the only data
source is the committed P268D1 JSONL fixture, and the only strategy source is
``recovered_strategies.biglotto.historical_adapters``. Scoring is restricted to
the five PARITY_ACCEPTABLE adapters; shape/safety-only adapters and blocked
targets fail closed. Output is historical descriptive validation only — no
future prediction guarantee and no betting advice.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Callable, Iterable, Mapping

from recovered_strategies.biglotto import historical_adapters

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_RELPATH = "outputs/research/p268d1_draw_order_full_history_artifact_backfill_20260610.jsonl"
EXPECTED_FIXTURE_SHA256 = "f4accb6f527694e739689242c929e87e4b031a364becb4fadb4aaea50ef2e3f8"
EXPECTED_BIG_LOTTO_ROWS = 2139

LOOKBACK = 520
WINDOWS = (30, 150, 750, 1500)
BASELINE_SINGLE_TICKET_P = 0.0186375
BASELINE_FORMULA = "1 - (1 - 0.0186375) ** bet_count"
HIT_THRESHOLD_MAINS = 3
TIER = "parity"
REQUIRED_PARITY_STATUS = "PARITY_ACCEPTABLE_FOR_NO_DB_HARNESS"

ALLOWLISTED_ADAPTERS = (
    "adapt_biglotto_p0_2bet",
    "adapt_predict_biglotto_echo_2bet",
    "adapt_predict_biglotto_echo_phase2_2bet",
    "adapt_predict_biglotto_echo_phase2_3bet",
    "adapt_predict_biglotto_echo_mixed_3bet",
)

RESULTS_COLUMNS = (
    "adapter_function",
    "strategy_id",
    "tier",
    "parity_status",
    "bet_count",
    "window_size",
    "period_count",
    "hit_count",
    "hit_rate",
    "same_bet_count_baseline",
    "edge_vs_same_bet_count_baseline",
    "positive_edge",
    "first_period",
    "last_period",
    "fixture_sha256",
)

COVERAGE_COLUMNS = (
    "row_type",
    "adapter_a",
    "adapter_b",
    "scope",
    "both_hit_count",
    "union_hit_count",
    "jaccard",
    "unique_hit_count",
    "total_hit_count",
    "cohort_any_hit_count",
)

MANIFEST_COLUMNS = ("key", "value")

ARTIFACT_BASENAMES = {
    "results": "P360_biglotto_no_db_multiwindow_validation_results.csv",
    "manifest": "P360_biglotto_no_db_multiwindow_validation_manifest.csv",
    "coverage": "P360_biglotto_no_db_multiwindow_validation_coverage.csv",
    "report": "P360_biglotto_no_db_multiwindow_validation_report.md",
}


class FixtureValidationError(RuntimeError):
    """The committed fixture failed a fail-closed schema/content check."""


class AdapterSelectionError(RuntimeError):
    """A non-allowlisted or non-parity adapter was requested for scoring."""


@dataclass(frozen=True)
class Draw:
    period: int
    mains: tuple
    special: int


@dataclass(frozen=True)
class AdapterSpec:
    name: str
    fn: Callable
    strategy_id: str
    bet_count: int
    parity_status: str


@dataclass(frozen=True)
class ValidationOutput:
    fixture_sha256: str
    draw_count: int
    scoreable_period_count: int
    results_rows: tuple
    coverage_rows: tuple
    manifest_rows: tuple


def compute_fixture_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_big_lotto_draws(fixture_path: Path | None = None) -> tuple:
    """Load, validate and sort the BIG_LOTTO rows; returns (draws, sha256)."""
    path = Path(fixture_path) if fixture_path is not None else REPO_ROOT / FIXTURE_RELPATH
    if not path.is_file():
        raise FixtureValidationError(f"fixture missing: {path}")
    sha256 = compute_fixture_sha256(path)
    draws = []
    with open(path, "r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("lottery_type") != "BIG_LOTTO":
                continue
            try:
                period = int(row["period"])
                sequence = [int(n) for n in row["drawNumberSize"]]
            except (KeyError, TypeError, ValueError) as exc:
                raise FixtureValidationError(f"line {line_no}: unparseable BIG_LOTTO row: {exc}")
            if len(sequence) != 7:
                raise FixtureValidationError(f"line {line_no}: drawNumberSize must have 7 values")
            mains = tuple(sequence[:6])
            special = sequence[6]
            if len(set(mains)) != 6:
                raise FixtureValidationError(f"line {line_no}: mains not unique: {mains}")
            if any(n < 1 or n > 49 for n in mains):
                raise FixtureValidationError(f"line {line_no}: main out of 1-49 range: {mains}")
            if list(mains) != sorted(mains):
                raise FixtureValidationError(f"line {line_no}: first 6 values not ascending: {mains}")
            if special < 1 or special > 49:
                raise FixtureValidationError(f"line {line_no}: special out of 1-49 range: {special}")
            draws.append(Draw(period=period, mains=mains, special=special))
    if len(draws) != EXPECTED_BIG_LOTTO_ROWS:
        raise FixtureValidationError(
            f"expected {EXPECTED_BIG_LOTTO_ROWS} BIG_LOTTO rows, found {len(draws)}"
        )
    draws.sort(key=lambda d: d.period)
    periods = [d.period for d in draws]
    if len(set(periods)) != len(periods):
        raise FixtureValidationError("duplicate BIG_LOTTO periods in fixture")
    return draws, sha256


def resolve_scoring_adapters(requested: Iterable = ALLOWLISTED_ADAPTERS) -> tuple:
    """Fail closed: only the 5 allowlisted PARITY_ACCEPTABLE adapters may score."""
    requested = tuple(requested)
    extra = [name for name in requested if name not in ALLOWLISTED_ADAPTERS]
    if extra:
        raise AdapterSelectionError(f"non-allowlisted adapters requested for scoring: {extra}")
    if set(requested) != set(ALLOWLISTED_ADAPTERS) or len(requested) != len(ALLOWLISTED_ADAPTERS):
        raise AdapterSelectionError(
            "scoring cohort must be exactly the 5 allowlisted parity adapters"
        )
    specs = []
    for name in ALLOWLISTED_ADAPTERS:
        metadata = historical_adapters.ADAPTER_METADATA.get(name)
        if metadata is None:
            raise AdapterSelectionError(f"adapter metadata missing: {name}")
        if metadata.get("parity_status") != REQUIRED_PARITY_STATUS:
            raise AdapterSelectionError(
                f"adapter {name} is not {REQUIRED_PARITY_STATUS}: {metadata.get('parity_status')}"
            )
        fn = getattr(historical_adapters, name, None)
        if not callable(fn):
            raise AdapterSelectionError(f"adapter function missing: {name}")
        specs.append(
            AdapterSpec(
                name=name,
                fn=fn,
                strategy_id=str(metadata["source_strategy_id"]),
                bet_count=int(metadata["bet_count"]),
                parity_status=str(metadata["parity_status"]),
            )
        )
    return tuple(specs)


def compute_baseline(bet_count: int) -> float:
    """Independent-ticket approximation of P(any of bet_count tickets matches >=3 mains)."""
    return 1.0 - (1.0 - BASELINE_SINGLE_TICKET_P) ** bet_count


def run_walk_forward(
    draws: Iterable,
    adapters: Mapping,
    lookback: int = LOOKBACK,
) -> tuple:
    """Score each adapter on trailing `lookback` draws against the next draw only.

    Returns tuples (period, adapter_name, bet_count, hit). History passed to the
    adapter is strictly draws[i - lookback : i]; the target draw i is never
    included, so no future information can leak into any adapter call.
    """
    draws = list(draws)
    if len(draws) <= lookback:
        raise FixtureValidationError(f"need more than {lookback} draws, have {len(draws)}")
    records = []
    for i in range(lookback, len(draws)):
        history = [
            {"period": d.period, "numbers": list(d.mains)} for d in draws[i - lookback : i]
        ]
        target = draws[i]
        target_mains = set(target.mains)
        for name, fn in adapters.items():
            bets = fn(history)
            hit = any(len(set(bet) & target_mains) >= HIT_THRESHOLD_MAINS for bet in bets)
            records.append((target.period, name, len(bets), hit))
    return tuple(records)


def _records_by_adapter(records: Iterable) -> dict:
    grouped = {}
    for period, name, bet_count, hit in records:
        grouped.setdefault(name, []).append((period, bet_count, hit))
    for name in grouped:
        grouped[name].sort(key=lambda item: item[0])
    return grouped


def compute_results_rows(records: Iterable, specs: Iterable, fixture_sha256: str) -> tuple:
    grouped = _records_by_adapter(records)
    rows = []
    for spec in specs:
        adapter_records = grouped.get(spec.name, [])
        if not adapter_records:
            raise AdapterSelectionError(f"no walk-forward records for {spec.name}")
        observed_bet_counts = {bet_count for _, bet_count, _ in adapter_records}
        if observed_bet_counts != {spec.bet_count}:
            raise AdapterSelectionError(
                f"{spec.name} produced bet counts {sorted(observed_bet_counts)}, "
                f"metadata says {spec.bet_count}"
            )
        for window in WINDOWS:
            if window > len(adapter_records):
                raise FixtureValidationError(
                    f"window {window} exceeds scoreable periods {len(adapter_records)}"
                )
            tail = adapter_records[-window:]
            hit_count = sum(1 for _, _, hit in tail if hit)
            hit_rate = hit_count / window
            baseline = compute_baseline(spec.bet_count)
            edge = hit_rate - baseline
            rows.append(
                {
                    "adapter_function": spec.name,
                    "strategy_id": spec.strategy_id,
                    "tier": TIER,
                    "parity_status": spec.parity_status,
                    "bet_count": str(spec.bet_count),
                    "window_size": str(window),
                    "period_count": str(window),
                    "hit_count": str(hit_count),
                    "hit_rate": f"{hit_rate:.8f}",
                    "same_bet_count_baseline": f"{baseline:.8f}",
                    "edge_vs_same_bet_count_baseline": f"{edge:.8f}",
                    "positive_edge": "true" if edge > 0 else "false",
                    "first_period": str(tail[0][0]),
                    "last_period": str(tail[-1][0]),
                    "fixture_sha256": fixture_sha256,
                }
            )
    return tuple(rows)


def compute_coverage_rows(records: Iterable, specs: Iterable) -> tuple:
    """Coverage within the parity cohort only: pairwise overlap/Jaccard over the
    full scoreable range, unique hit contribution per adapter, and cohort
    any-adapter hit counts per trailing window."""
    grouped = _records_by_adapter(records)
    names = [spec.name for spec in specs]
    hit_sets = {
        name: {period for period, _, hit in grouped[name] if hit} for name in names
    }
    all_periods = [period for period, _, _ in grouped[names[0]]]
    scope_full = f"full_{len(all_periods)}"
    rows = []
    for name_a, name_b in combinations(names, 2):
        both = hit_sets[name_a] & hit_sets[name_b]
        union = hit_sets[name_a] | hit_sets[name_b]
        jaccard = (len(both) / len(union)) if union else 0.0
        rows.append(
            {
                "row_type": "pairwise",
                "adapter_a": name_a,
                "adapter_b": name_b,
                "scope": scope_full,
                "both_hit_count": str(len(both)),
                "union_hit_count": str(len(union)),
                "jaccard": f"{jaccard:.8f}",
                "unique_hit_count": "",
                "total_hit_count": "",
                "cohort_any_hit_count": "",
            }
        )
    for name in names:
        others = set()
        for other in names:
            if other != name:
                others |= hit_sets[other]
        unique = hit_sets[name] - others
        rows.append(
            {
                "row_type": "unique_contribution",
                "adapter_a": name,
                "adapter_b": "",
                "scope": scope_full,
                "both_hit_count": "",
                "union_hit_count": "",
                "jaccard": "",
                "unique_hit_count": str(len(unique)),
                "total_hit_count": str(len(hit_sets[name])),
                "cohort_any_hit_count": "",
            }
        )
    cohort_hits = set()
    for name in names:
        cohort_hits |= hit_sets[name]
    for window in WINDOWS + (len(all_periods),):
        tail = set(all_periods[-window:])
        rows.append(
            {
                "row_type": "cohort_window",
                "adapter_a": "",
                "adapter_b": "",
                "scope": f"trailing_{window}",
                "both_hit_count": "",
                "union_hit_count": "",
                "jaccard": "",
                "unique_hit_count": "",
                "total_hit_count": "",
                "cohort_any_hit_count": str(len(cohort_hits & tail)),
            }
        )
    return tuple(rows)


def build_manifest_rows(output_fields: Mapping) -> tuple:
    rows = [{"key": key, "value": str(value)} for key, value in output_fields.items()]
    return tuple(rows)


def run_validation(fixture_path: Path | None = None) -> ValidationOutput:
    draws, sha256 = load_big_lotto_draws(fixture_path)
    if fixture_path is None and sha256 != EXPECTED_FIXTURE_SHA256:
        raise FixtureValidationError(
            f"fixture SHA256 mismatch: expected {EXPECTED_FIXTURE_SHA256}, got {sha256}"
        )
    specs = resolve_scoring_adapters()
    adapters = {spec.name: spec.fn for spec in specs}
    records = run_walk_forward(draws, adapters)
    scoreable = len(draws) - LOOKBACK
    results_rows = compute_results_rows(records, specs, sha256)
    coverage_rows = compute_coverage_rows(records, specs)
    manifest_rows = build_manifest_rows(
        {
            "task": "P360_biglotto_no_db_multiwindow_validation",
            "fixture_relpath": FIXTURE_RELPATH,
            "fixture_sha256": sha256,
            "big_lotto_row_count": len(draws),
            "lookback_draws": LOOKBACK,
            "scoreable_period_count": scoreable,
            "first_scoreable_period": draws[LOOKBACK].period,
            "last_scoreable_period": draws[-1].period,
            "windows": ";".join(str(w) for w in WINDOWS),
            "hit_definition": f"any ticket matching >={HIT_THRESHOLD_MAINS} main numbers",
            "baseline_formula": BASELINE_FORMULA,
            "baseline_single_ticket_p": BASELINE_SINGLE_TICKET_P,
            "baseline_note": "independent-ticket approximation, not proof of edge",
            "tier": TIER,
            "required_parity_status": REQUIRED_PARITY_STATUS,
            "adapter_count": len(specs),
            "adapters": ";".join(spec.name for spec in specs),
            "db_opened": "NO",
            "production_registry_imported": "NO",
        }
    )
    return ValidationOutput(
        fixture_sha256=sha256,
        draw_count=len(draws),
        scoreable_period_count=scoreable,
        results_rows=results_rows,
        coverage_rows=coverage_rows,
        manifest_rows=manifest_rows,
    )


def _markdown_table(columns: Iterable, rows: Iterable) -> str:
    columns = list(columns)
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join(" --- " for _ in columns) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row[c]) for c in columns) + " |")
    return "\n".join(lines)


def render_report(output: ValidationOutput) -> str:
    excluded_shape_only = sorted(
        name
        for name, meta in historical_adapters.ADAPTER_METADATA.items()
        if meta.get("parity_status") != REQUIRED_PARITY_STATUS
    )
    parts = []
    parts.append("# P360 Big Lotto no-DB Multi-window Walk-forward Validation (parity tier only)")
    parts.append("")
    parts.append("## Scope statements")
    parts.append("")
    parts.append("- This is historical descriptive validation only.")
    parts.append("- No future prediction guarantee. Past hit rates do not predict future draws.")
    parts.append("- No betting advice. Nothing here recommends placing any bet.")
    parts.append("- No DB was opened or written. The only data source is the committed JSONL fixture below.")
    parts.append("- No blended leaderboard: P356/P358 baseline strategies are excluded from every table in this report.")
    parts.append("- Shape/safety-only adapters and blocked targets were excluded from scoring: "
                 + ", ".join(f"`{name}`" for name in excluded_shape_only) + ".")
    parts.append("")
    parts.append("## Method")
    parts.append("")
    parts.append(f"- Fixture: `{FIXTURE_RELPATH}`")
    parts.append(f"- Fixture SHA256: `{output.fixture_sha256}`")
    parts.append(f"- BIG_LOTTO rows: {output.draw_count} (validated; 6 unique ascending mains in 1-49, special in 1-49)")
    parts.append(f"- Walk-forward: fixed {LOOKBACK}-draw trailing lookback; each adapter scored against the next draw only; "
                 f"{output.scoreable_period_count} scoreable periods; no future leakage, no parameter tuning, no randomization.")
    parts.append(f"- Hit definition: any ticket matching >= {HIT_THRESHOLD_MAINS} main numbers.")
    parts.append(f"- Baseline: `{BASELINE_FORMULA}` — an independent-ticket approximation "
                 "(real tickets within a strategy overlap, so this is approximate context, not proof of edge).")
    parts.append(f"- Trailing evaluation windows: {', '.join(str(w) for w in WINDOWS)} periods.")
    parts.append("- Null expectation (pre-registered): prior L90/L91 evidence found BIG_LOTTO indistinguishable "
                 "from fair random, so edge is expected to be approximately zero in every window.")
    parts.append("")
    parts.append("## Included adapters (parity tier)")
    parts.append("")
    spec_rows = [
        {
            "adapter_function": row["adapter_function"],
            "strategy_id": row["strategy_id"],
            "bet_count": row["bet_count"],
            "parity_status": row["parity_status"],
        }
        for row in output.results_rows
        if row["window_size"] == str(WINDOWS[0])
    ]
    parts.append(_markdown_table(("adapter_function", "strategy_id", "bet_count", "parity_status"), spec_rows))
    parts.append("")
    parts.append("## Results by trailing window")
    parts.append("")
    display_columns = (
        "adapter_function",
        "bet_count",
        "hit_count",
        "hit_rate",
        "same_bet_count_baseline",
        "edge_vs_same_bet_count_baseline",
        "positive_edge",
    )
    for window in WINDOWS:
        window_rows = [row for row in output.results_rows if row["window_size"] == str(window)]
        parts.append(f"### Trailing {window} periods")
        parts.append("")
        parts.append(_markdown_table(display_columns, window_rows))
        parts.append("")
    parts.append("## Cohort coverage (parity tier only, full scoreable range)")
    parts.append("")
    pair_rows = [row for row in output.coverage_rows if row["row_type"] == "pairwise"]
    parts.append(_markdown_table(("adapter_a", "adapter_b", "both_hit_count", "union_hit_count", "jaccard"), pair_rows))
    parts.append("")
    unique_rows = [row for row in output.coverage_rows if row["row_type"] == "unique_contribution"]
    parts.append(_markdown_table(("adapter_a", "unique_hit_count", "total_hit_count"), unique_rows))
    parts.append("")
    cohort_rows = [row for row in output.coverage_rows if row["row_type"] == "cohort_window"]
    parts.append(_markdown_table(("scope", "cohort_any_hit_count"), cohort_rows))
    parts.append("")
    parts.append("## Excluded cohorts")
    parts.append("")
    parts.append("- Shape/safety-only adapters (`PARITY_PARTIAL_SHAPE_ONLY`) and blocked targets: excluded from scoring.")
    parts.append("- P356 baseline strategies: excluded from scoring and from every table above; "
                 "prior P356 evidence lives in its own artifacts and is intentionally not blended here.")
    parts.append("")
    return "\n".join(parts)


def _write_csv(path: Path, columns: Iterable, rows: Iterable) -> None:
    columns = list(columns)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_artifacts(output: ValidationOutput, artifacts_dir: Path | None = None) -> dict:
    directory = Path(artifacts_dir) if artifacts_dir is not None else REPO_ROOT / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    paths = {key: directory / name for key, name in ARTIFACT_BASENAMES.items()}
    _write_csv(paths["results"], RESULTS_COLUMNS, output.results_rows)
    _write_csv(paths["manifest"], MANIFEST_COLUMNS, output.manifest_rows)
    _write_csv(paths["coverage"], COVERAGE_COLUMNS, output.coverage_rows)
    with open(paths["report"], "w", encoding="utf-8") as handle:
        handle.write(render_report(output))
    return paths


def main(argv: Iterable = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=None, help="override fixture path (tests only)")
    parser.add_argument("--artifacts-dir", type=Path, default=None, help="override artifacts directory")
    args = parser.parse_args(argv)
    first = run_validation(args.fixture)
    second = run_validation(args.fixture)
    if (
        first.results_rows != second.results_rows
        or first.coverage_rows != second.coverage_rows
        or first.manifest_rows != second.manifest_rows
    ):
        raise RuntimeError("determinism double-run mismatch: results are not reproducible")
    paths = write_artifacts(first, args.artifacts_dir)
    print("P360 no-DB multi-window validation: determinism double-run PASS")
    print(f"fixture sha256: {first.fixture_sha256}")
    print(f"scoreable periods: {first.scoreable_period_count}")
    for key, path in sorted(paths.items()):
        print(f"artifact[{key}]: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
