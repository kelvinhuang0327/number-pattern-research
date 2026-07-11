# P545B — Canonical Full 50/300/750 Per-Draw Evaluation

> Retrospective research reconciliation only. No predictive-validity or betting recommendation claim.

## Published contract

- Schema: `p545b_full_50_300_750_per_draw_evaluation.v1`
- Implementation base: `72e55acde36792912873315eb75f8a5b74c7470a`
- Deterministic timestamp: `2026-07-11T07:58:26+00:00`
- Timestamp policy: `implementation base commit committer timestamp normalized to UTC seconds`
- Canonical payload digest: `0823fab8aa4de6f474212eb19955b493c7432bfa3582a55ab14e967fc8de6ae2`

## Evidence lineage

- Sole row-level input: `outputs/research/p545c_r4_strategy_draw_opportunity_registry_20260711.json`
- Input bytes / SHA-256: **52,393,107** / `ea0a712fa5ba702c51271b5664fc95e5cac2feec5967ead3bd7d01cfcd7bc5d8`
- Semantic projection digest: `f2c28075a3b7020629a0c6bd41504609031ff84532a672dde4f26f0485434b39`
- Input canonical digest: `34bbee9b9a3cd275025db282486f8bdd3dd5c14834813061acefce220ae0ed84`
- Verified contract sources: **7**

## Global accounting

- Cells / opportunities / attempts: **36 / 27,000 / 47,250**
- Eligible / excluded attempts: **33,749 / 13,501**
- Supported / identity-missing opportunities: **23,999 / 3,001**
- Evaluable / unevaluable windows: **86 / 22**

## Reconciliation

- Primary: **108/108 PASS**
- Identity: **108/108 PASS**
- Inferential: **108/108 PASS**
- Unexplained mismatches: **0**
- Legacy numerical equivalence: **PASS**
- Numerical projection digest: `e7fdc41afcf5794e35929f72f461c31bada9d4d89a03ec4f4707f4640f14be2c`

## Four unsupported POWER_LOTTO cells

- Opportunities / gross attempts: **3,000 / 9,750**
- Eligible / excluded: **0 / 9,750**
- Exclusion: `MISSING_PREDICTED_SECOND_ZONE`

## Determinism and safety

- Two independent JSON builds byte-identical: **PASS**
- Two independent Markdown builds byte-identical: **PASS**
- Non-finite JSON rejected: **YES**
- SQLite/database/snapshot opened: **NO**
- Strategy search or parameter tuning: **NO**
- Predictive-validity, ROI, EV, staking, deployment, or betting claim: **NO**

## Limitations

- Frozen retrospective evidence only.
- Legacy P545B R2 evidence remains immutable and is not superseded numerically.
- This publication contract does not authorize any operational or wagering action.
