# P541B R2 — Fail-Closed Structured Evidence Classification

> generated_at_utc: `2026-07-11T12:43:50Z`

## Scope and Frozen Corpus

- Implementation base: `c50137583243d4f9f4915a3e1d9babee50b5bbd7`
- Frozen source commit: `49a25effa62fc24f40789c16be6f11bdfb41a4a9`
- Ordered corpus: exactly **580** unique historical method IDs and source paths.
- Source bytes were read only with Git plumbing from the frozen commit.
- No source module was imported or executed; no database was opened or hashed.

## Evidence Schema and Fail-Closed Rules

- Schema: `p541b-r2-evidence-v1`
- Detector: `p541b-r2-detector-v4`
- Canonical generation runtime: `CPython==3.9.6` — verification **PASS**.
- Every evidence family publishes `state`, `scope`, `detector_id`, and deterministic `findings`.
- Every finding publishes separate `resolved_api` and `resolved_syntax` fields plus `imported_module_path`; exactly one resolved field is populated.
- States are exactly `detected`, `not_detected`, and `unknown`.
- Scan-status taxonomy (ordered): `complete`, `syntax_error`, `unreadable`, `unsupported`.
- Each record publishes truthful Git-read, UTF-8 decode, AST parse, and scan-completion statuses.
- Recoverable per-file blob-read, decode, parse, detector, category-detector, unsupported-structure, and ambiguous one-hop failures retain the original manifest record as `unknown` and continue in original order.
- Completed `detected` evidence is preserved when another detector category fails; an incomplete scan can never be low risk.
- Failure reasons use bounded deterministic codes and exclude exception text and private host paths.
- Repository/Git unavailability, baseline or frozen-manifest failure, duplicates, top-level invariants, and serialization failures remain terminal.
- Only an exact top-level `__name__ == '__main__'` comparison is a valid guard; it mitigates import-time reachability only.

## Detector Families

- Direct and aliased database access, including DatabaseManager/db_manager and supported SQLAlchemy APIs.
- Filesystem reads separated from filesystem writes, deletes, moves, and mutations.
- Requests/urllib/http.client/httpx/aiohttp/socket network I/O and external URLs.
- Direct and aliased subprocess/process-spawning APIs.
- Hardcoded absolute, DB-like, draw/date, and external-service inputs.
- Bounded one-hop project imports promote module-load effects and effects reachable through invoked functions, classes, instance methods, same-module inheritance, and helper calls; cycles stop and unresolved direct imports or invoked deeper project dependencies route to `unknown`.

## Summary

| Metric | Value |
|---|---:|
| Frozen source records | 580 |
| Complete scans | 544 |
| Unknown scans | 36 |
| Direct findings | 3545 |
| Transitive findings | 11484 |
| Scan `complete` | 544 |
| Scan `syntax_error` | 1 |
| Scan `unreadable` | 0 |
| Scan `unsupported` | 35 |
| Risk `high` | 110 |
| Risk `low` | 22 |
| Risk `medium` | 4 |
| Risk `unknown` | 444 |

## Tri-State Evidence

| Evidence | detected | not_detected | unknown |
|---|---:|---:|---:|
| `database_access` | 390 | 169 | 21 |
| `filesystem_write` | 160 | 394 | 26 |
| `network_io` | 17 | 527 | 36 |
| `process_execution` | 12 | 532 | 36 |
| `other_external_effect` | 57 | 512 | 11 |
| `transitive_external_state` | 0 | 137 | 443 |
| `import_time_execution` | 12 | 536 | 32 |
| `hardcoded_absolute_path` | 56 | 489 | 35 |
| `hardcoded_draw_or_date` | 42 | 503 | 35 |
| `database_like_path` | 390 | 174 | 16 |
| `external_service_url` | 22 | 523 | 35 |
| `filesystem_read` | 166 | 385 | 29 |
| `valid_main_guard` | 539 | 30 | 11 |
| `malformed_main_guard` | 1 | 543 | 36 |

## Superseded Historical Artifacts

- `outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.json`
- `outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.md`
- R2 supersedes their Boolean evidence semantics without overwriting or deleting them.

## Frozen Provenance

- Generator SHA-256: `0afccd775dfdee114e709e6648248d4c8f277247ed00bb4246e5e25648d4c7c8`
- Historical P541B JSON blob: `12f1595c96e3f9deddc7a7d2d9549c03144635f0` — verification **PASS**
- Historical P541B Markdown blob: `3b28e39bfe747c5f196b9aec6610284709466cf8` — verification **PASS**
- Historical P541A JSON blob: `7557f364160dc09c91a19c07b370cb4b231c0194` — verification **PASS**
- Historical P541A Markdown blob: `7c2574dd80e8fbef147da0d4477a0c8eda56afe0` — verification **PASS**
- Frozen manifest: 580 Git blobs, canonical SHA-256 `ca0f84b23f1a3f6613c5f78d6020ec954a3e28fb702152fbf1fa1fb53dbf4e40` — verification **PASS**
- Recovered source blob-read failures: **0**
- Source discovery from the current working tree is prohibited.

## Downstream Requirement

PR #663 remains **HOLD_DO_NOT_MERGE** and was not changed. A separately authorized replacement P541C task must consume this schema, regenerate all derived counts and shortlist membership, and must never coerce `unknown` to `false`.

## Limitations

- Static detection is conservative and does not prove runtime safety.
- Unknown blocks low-risk eligibility and requires targeted review or detector support.
- Canonical artifact generation is pinned to CPython 3.9.6; other runtimes fail closed before source reads.
- Historical identity/method-family classifications are retained as context, not re-proven.
- No database, source import, source execution, replay, or predictive evaluation was performed.

**Disclaimer:** This is static classification, not source execution, replay, production, predictive, ROI, or betting validation.
