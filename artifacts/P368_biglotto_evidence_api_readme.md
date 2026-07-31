# P368 Big Lotto no-DB evidence API snapshots

Generated at: DETERMINISTIC_PLACEHOLDER

This local snapshot harness locks the merged P367 Big Lotto no-DB evidence API facade with deterministic golden snapshots, compatibility rows, contract drift rows, CLI transcripts, and a manifest.

## Local usage

```bash
python3 -m recovered_strategies.biglotto.no_db_evidence_api_snapshots
python3 -m recovered_strategies.biglotto.no_db_evidence_api_snapshots --emit-golden-snapshots
python3 -m recovered_strategies.biglotto.no_db_evidence_api_snapshots --compatibility-matrix
python3 -m recovered_strategies.biglotto.no_db_evidence_api_snapshots --contract-drift
python3 -m recovered_strategies.biglotto.no_db_evidence_api_snapshots --cli-transcripts
python3 -m recovered_strategies.biglotto.no_db_evidence_api_snapshots --validate
```

The harness calls only P367 facade functions backed by committed P366/P367 artifacts. It is intended for future Workers to detect accidental API or evidence-shape regressions quickly.

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

The harness builds only on merged P366/P367 evidence. It does not create a new scoring cohort, blended leaderboard, shape-only scoring, or blocked target scoring. It does not import production registries, deploy, call adapters, open a DB, or write a DB.
