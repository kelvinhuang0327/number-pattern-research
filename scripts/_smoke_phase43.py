"""Quick smoke test for Phase 43 audit module."""
import sys
sys.path.insert(0, '.')
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from wbc_backend.evaluation.prediction_persistence import load_prediction_rows, DEFAULT_PREDICTIONS_PATH
from orchestrator.phase43_model_value_market_blend_stability import run_phase43_audit

rows = load_prediction_rows(DEFAULT_PREDICTIONS_PATH)
print(f"Loaded {len(rows)} rows")

report = run_phase43_audit(rows, input_path=str(DEFAULT_PREDICTIONS_PATH))

print("=" * 60)
print(f"Gate:            {report.gate.recommendation}")
print(f"Fold stability:  {report.fold_stability_label}")
bs = report.bootstrap_blend_vs_market
print(f"Bootstrap blend: {bs.significance_label}  CI=[{bs.ci_lower:+.4f}, {bs.ci_upper:+.4f}]  p_improve={bs.prob_improvement:.1%}")
bsr = report.bootstrap_raw_vs_market
print(f"Bootstrap raw:   {bsr.significance_label}  CI=[{bsr.ci_lower:+.4f}, {bsr.ci_upper:+.4f}]  p_improve={bsr.prob_improvement:.1%}")
print(f"Segment summary: {report.segment_value_summary}")
print(f"overall raw_bss={report.overall_raw_bss:+.4f}  blend_bss={report.overall_blend_bss:+.4f}")
print(f"Folds {report.folds_with_positive_blend_bss}/{len(report.fold_results)} with blend_bss >= 0")
print()
print("Per-fold detail:")
for f in report.fold_results:
    diag = "DIAG-ONLY" if f.diagnostic_only else "ERROR"
    print(f"  {f.fold_id}  n={f.n}  raw_bss={f.raw_bss:+.4f}  blend_bss={f.blend_bss:+.4f}  best_alpha={f.best_alpha_per_fold}  [{diag}]")
print()
print("Gate reasoning:")
for r in report.gate.reasoning:
    print(f"  - {r}")
print()
print("Segment detail (by type):")
for sr in report.segment_results:
    print(f"  {sr.segment_type}/{sr.segment_label:25s} n={sr.n:4d}  blend_bss={sr.blend_bss:+.4f}  {sr.value_classification}")
