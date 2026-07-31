# Limitations

- No betting, profitability, production readiness, or future prediction claim is made.
- All hit-rate matrix values are retrospective replay observations only.
- Baselines are not computed in this MVP; `baseline_mode=not_computed`, `baseline_value=NULL`, `delta=NULL`, and `delta_pp=NULL` must not be interpreted as edge.
- Prospective thresholds and prospective evaluation horizon remain absent.
- POWER_LOTTO full prize-aware scoring is out of scope because P298A confirmed no POWER_LOTTO canonical view/source contract and missing `predicted_special` values for 27,104 of 36,104 replay rows.
- The POWER_LOTTO 9,000-row non-null subset is research-only and is not included in the P299A matrix.
- Repo was already dirty at Phase 0; this run intentionally wrote only repo-external artifacts.
