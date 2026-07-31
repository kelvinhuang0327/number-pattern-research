# P3.1 Artifact Normalization Report

## 1. Problem Statement

V1 stopped at `V1_BLOCKED_P3_ARTIFACT_INVALID` because `provenance_hash` was missing from the P3 retrospective candidate rows.

## 2. Root Cause

The P3 artifact emitted `adapter_file_hash` for every row, but it did not emit the closure-required `provenance_hash` field.

## 3. Fix

The normalized P3.1 artifact adds `provenance_hash = adapter_file_hash` and records `provenance_hash_source = adapter_file_hash` when the field was missing.

## 4. Safety

- No DB write
- No registry change
- No strategy mining
- No row regeneration
- Original P3 artifact preserved

## 5. Validation Evidence

- Rows: 300
- Strategies: 6 x 50
- Truth level all REGENERATED_RETROSPECTIVE: True
- Dry run only all true: True
- History window end < draw date all true: True
- Provenance hash present all rows: True

## 6. Next Instruction

Resume V1 closure from Phase 3 using the normalized P3.1 JSONL as the controlled apply input.
