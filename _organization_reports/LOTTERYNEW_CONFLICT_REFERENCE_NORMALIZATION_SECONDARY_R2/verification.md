# Verification Report: LOTTERYNEW_CONFLICT_REFERENCE_NORMALIZATION_SECONDARY_R2

## Summary
- **Scoped Conflict Files Found**: 2586
- **Moved to Reference**: 2586
- **Symlinks Skipped**: 0
- **Orphaned Conflicts**: 0
- **Exact Duplicate Files**: 2536
- **Unique Conflict Contents**: 189
- **Failures**: 0

## Integrity Checklist
- [x] Moved files SHA-256 verified identical before and after move.
- [x] Every moved file has a corresponding entry in `index.jsonl`.
- [x] All original conflict paths in scoped roots no longer exist.
- [x] Scoped roots (`tests`, `strategies`, `orchestrator`, `tools`, `wbc_backend`) clean of conflict files (count = 0).
- [x] All ordinary canonical files in scoped roots verified untouched via SHA-256.
- [x] Previous R1 reference root untouched.
- [x] Git diff --check: PASS
- [x] Remaining conflict counts distribution generated.
