# Source to Target Map

Task: `P0_CANONICAL_STRATEGY_UNIVERSE_INVENTORY_MIGRATION_R4`

| Source Path | Source SHA-256 | Target Path | Target Initial State | Migration Action | Source Role |
|---|---|---|---|---|---|
| `scripts/p0_per_draw_coverage_matrix.py` | `d9ea26acd4fa897b8f06f37a66daf6beea45ee419f6e4d36d5258014a09d80e5` | `scripts/p0_per_draw_coverage_matrix.py` | ABSENT | MIGRATE_WITH_MINIMAL_ADAPTATION | Read-only coverage matrix CLI script |
| `tests/test_p0_canonical_universe.py` | `a26424b58384aeb4c35aa679bd59fe4db5cc1bd36f062dea51d1586f67a62472` | `tests/test_p0_canonical_universe.py` | ABSENT | MIGRATE_WITH_MINIMAL_ADAPTATION | Focused test suite for canonical universe & matrix |
| `docs/replay/p0_canonical_strategy_universe_20260518.md` | `76548f92f288c259320da9e13807d3be94647e5eeb450c9ac1075a8b095b2517` | `docs/replay/p0_canonical_strategy_universe_20260518.md` | ABSENT | COPY_DIRECTLY | Canonical strategy universe documentation |
| `outputs/replay/p0_canonical_strategy_universe_20260518.json` | `3454e8b5a71816dd96347b0fcf5797ba3e255af9521c72dfdd4a75d696bd341a` | `outputs/replay/p0_canonical_strategy_universe_20260518.json` | ABSENT | COPY_AS_FIXTURE | Canonical strategy universe JSON contract fixture |
| `outputs/replay/p0_per_draw_coverage_matrix_20260518.json` | `092799a16c47ee7f976e3008b66fd56bb88848cb155de4efcf918a03ea2b0521` | `_integration_reports/P0_CANONICAL_STRATEGY_UNIVERSE_INVENTORY_MIGRATION_R4/runtime_sandbox/p0_per_draw_coverage_matrix.generated.json` | ABSENT | REGENERATE_IN_SANDBOX_ONLY | Historical generated output (DO NOT promote to ordinary output path) |

## Excluded Migration Authority
- `scripts/apply_p0_schema_migration.py`
- `tests/test_p0_schema_migration_idempotent.py`
- `docs/replay/p0_schema_diff_20260518.md`
- `outputs/replay/p0_migration_log_20260518.json`
- `outputs/replay/p0_schema_diff_20260518.json`
