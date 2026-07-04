# P367 Big Lotto no-DB evidence API

Generated at: DETERMINISTIC_PLACEHOLDER

This local API facade reads merged P363/P364/P365/P366 Big Lotto no-DB evidence artifacts and exposes stable Python functions plus a flag-based CLI for future Workers.

## Python API

```python
from recovered_strategies.biglotto import no_db_evidence_api as api

adapters = api.list_adapters()
adapter = api.get_adapter(adapters[0])
subsets = api.list_subsets(subset_size=2)
comparison = api.compare_adapters("adapt_biglotto_p0_2bet", "adapt_predict_biglotto_echo_2bet")
validation_rows = api.validate_evidence_stack()
```

## CLI

```bash
python3 -m recovered_strategies.biglotto.no_db_evidence_api --help
python3 -m recovered_strategies.biglotto.no_db_evidence_api --list-adapters
python3 -m recovered_strategies.biglotto.no_db_evidence_api --get-adapter adapt_predict_biglotto_echo_mixed_3bet
python3 -m recovered_strategies.biglotto.no_db_evidence_api --list-subsets --subset-size 2
python3 -m recovered_strategies.biglotto.no_db_evidence_api --get-subset adapt_biglotto_p0_2bet\;adapt_predict_biglotto_echo_2bet
python3 -m recovered_strategies.biglotto.no_db_evidence_api --compare-adapters adapt_biglotto_p0_2bet adapt_predict_biglotto_echo_2bet
python3 -m recovered_strategies.biglotto.no_db_evidence_api --compact-shortlist
python3 -m recovered_strategies.biglotto.no_db_evidence_api --validate
python3 -m recovered_strategies.biglotto.no_db_evidence_api --emit-contract
```

With no action flag, the CLI writes the P367 artifacts into `artifacts/`.

## Scope

- Historical descriptive evidence only.
- No future prediction guarantee.
- No betting advice.
- No DB open/write.
- No production registry import.
- No deploy.
- No adapter calls.
- No new scoring cohort.
- No blended leaderboard.
- Shape-only and blocked targets remain excluded.

The facade builds only on merged P363/P364/P365/P366 evidence. It does not create a new scoring cohort, blended leaderboard, shape-only scoring, or blocked target scoring. It does not import production registries, deploy, call adapters, open a DB, or write a DB.
