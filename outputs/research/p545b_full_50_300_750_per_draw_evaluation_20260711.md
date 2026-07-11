# P545B — Canonical Full 50/300/750 Per-Draw Evaluation

> Retrospective research reconciliation only. No predictive-validity or betting recommendation claim.

## Published contract

- Schema: `p545b_full_50_300_750_per_draw_evaluation.v1`
- Implementation base: `72e55acde36792912873315eb75f8a5b74c7470a`
- Deterministic timestamp: `2026-07-11T07:58:26Z`
- Timestamp source: `committer_timestamp` of `72e55acde36792912873315eb75f8a5b74c7470a`
- Timestamp format: `RFC3339_Z` at `seconds` precision
- Canonical payload digest: `adcf4cd2dab60b63a7709fb88cbc7f90438c5f26a4306e1f7057c2cd84aa7f5a`

## Evidence lineage

- Sole row-level input: `outputs/research/p545c_r4_strategy_draw_opportunity_registry_20260711.json`
- Input bytes / SHA-256: **52,393,107** / `ea0a712fa5ba702c51271b5664fc95e5cac2feec5967ead3bd7d01cfcd7bc5d8`
- Semantic projection digest: `f2c28075a3b7020629a0c6bd41504609031ff84532a672dde4f26f0485434b39`
- Input canonical digest: `34bbee9b9a3cd275025db282486f8bdd3dd5c14834813061acefce220ae0ed84`
- Verified contract sources: **7**

## Global accounting

- Cells / opportunities / attempts: **36 / 27,000 / 47,250**
- Eligible / excluded attempts: **33,749 / 13,501**
- Supported / unsupported opportunities: **23,999 / 3,001**
- Evaluable / unevaluable windows: **86 / 22**

## Reconciliation

- Primary: **108/108 PASS**
- Identity: **108/108 PASS**
- Inferential: **108/108 PASS**
- Full canonical fields: **108/108 PASS**
- Unexplained mismatches: **0**
- Legacy semantic equivalence: **PASS**
- Semantic projection digest: `f5015e760e03d2841ff7c31274f8c6509585a301078948941f8dd3e1134166e1`

## Four unsupported POWER_LOTTO cells

- Opportunities / gross attempts: **3,000 / 9,750**
- Eligible / excluded: **0 / 9,750**
- Exclusion: `MISSING_PREDICTED_SECOND_ZONE`

## Determinism and safety

- Two independent JSON serializations byte-identical: **PASS**
- Two independent Markdown renders byte-identical: **PASS**
- Non-finite JSON rejected: **YES**
- Duplicate JSON keys rejected: **YES**
- SQLite/database/snapshot opened: **NO**
- Strategy search or parameter tuning: **NO**
- JSON determinism projection SHA-256: `3b32d22523d6406c405187ad7334c42530da24199c35645fd6ab7d018705a477`
- Markdown determinism projection SHA-256: `d1a01bd4d283fa5847463e1f4be41dba46788d44aa6749f0409bf5600672b934`
- Predictive-validity, ROI, EV, staking, deployment, or betting claim: **NO**

## Limitations

- Frozen retrospective evidence only.
- No untouched prospective holdout is present.
- Legacy P545B R2 evidence remains immutable and is not superseded numerically.
- This publication contract does not authorize any operational or wagering action.
