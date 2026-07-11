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
- Detector: `p541b-r2-detector-v2`
- Every evidence family publishes `state`, `scope`, `detector_id`, and deterministic `findings`.
- Every finding publishes separate `resolved_api` and `resolved_syntax` fields plus `imported_module_path`; exactly one resolved field is populated.
- States are exactly `detected`, `not_detected`, and `unknown`.
- Scan-status taxonomy (ordered): `complete`, `syntax_error`, `unreadable`, `unsupported`.
- Read/decode, AST parse, unsupported-structure, provenance, and ambiguous one-hop failures fail closed.
- Only an exact top-level `__name__ == '__main__'` comparison is a valid guard; it mitigates import-time reachability only.

## Detector Families

- Direct and aliased database access, including DatabaseManager/db_manager and supported SQLAlchemy APIs.
- Filesystem reads separated from filesystem writes, deletes, moves, and mutations.
- Requests/urllib/http.client/httpx/aiohttp/socket network I/O and external URLs.
- Direct and aliased subprocess/process-spawning APIs.
- Hardcoded absolute, DB-like, draw/date, and external-service inputs.
- Bounded one-hop project imports with cycle stops and ambiguity routed to `unknown`.

## Summary

| Metric | Value |
|---|---:|
| Frozen source records | 580 |
| Complete scans | 554 |
| Unknown scans | 26 |
| Direct findings | 3498 |
| Transitive findings | 77 |
| Scan `complete` | 554 |
| Scan `syntax_error` | 1 |
| Scan `unsupported` | 25 |
| Risk `high` | 427 |
| Risk `low` | 58 |
| Risk `medium` | 9 |
| Risk `unknown` | 86 |

## Tri-State Evidence

| Evidence | detected | not_detected | unknown |
|---|---:|---:|---:|
| `database_access` | 379 | 171 | 30 |
| `filesystem_write` | 147 | 407 | 26 |
| `network_io` | 17 | 537 | 26 |
| `process_execution` | 12 | 542 | 26 |
| `other_external_effect` | 32 | 522 | 26 |
| `transitive_external_state` | 34 | 464 | 82 |
| `import_time_execution` | 8 | 546 | 26 |
| `hardcoded_absolute_path` | 56 | 498 | 26 |
| `hardcoded_draw_or_date` | 42 | 512 | 26 |
| `database_like_path` | 379 | 175 | 26 |
| `external_service_url` | 21 | 533 | 26 |
| `filesystem_read` | 162 | 392 | 26 |
| `valid_main_guard` | 523 | 31 | 26 |
| `malformed_main_guard` | 1 | 553 | 26 |

## Superseded Historical Artifacts

- `outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.json`
- `outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.md`
- R2 supersedes their Boolean evidence semantics without overwriting or deleting them.

## Frozen Provenance

- Generator SHA-256: `0cccda9da05b416f1cc5efb9284a8f9c926b4a24190f272a89908194b6d063b9`
- Historical P541B JSON blob: `12f1595c96e3f9deddc7a7d2d9549c03144635f0` — verification **PASS**
- Historical P541B Markdown blob: `3b28e39bfe747c5f196b9aec6610284709466cf8` — verification **PASS**
- Historical P541A JSON blob: `7557f364160dc09c91a19c07b370cb4b231c0194` — verification **PASS**
- Historical P541A Markdown blob: `7c2574dd80e8fbef147da0d4477a0c8eda56afe0` — verification **PASS**
- Frozen manifest: 580 Git blobs, canonical SHA-256 `002ece91381453954911397608f2899b1eec0b5fc299521500b39ea469f227e7` — verification **PASS**
- Source discovery from the current working tree is prohibited.

## Downstream Requirement

PR #663 remains **HOLD_DO_NOT_MERGE** and was not changed. A separately authorized replacement P541C task must consume this schema, regenerate all derived counts and shortlist membership, and must never coerce `unknown` to `false`.

## Limitations

- Static detection is conservative and does not prove runtime safety.
- Unknown blocks low-risk eligibility and requires targeted review or detector support.
- Historical identity/method-family classifications are retained as context, not re-proven.
- No database, source import, source execution, replay, or predictive evaluation was performed.

**Disclaimer:** This is static classification, not source execution, replay, production, predictive, ROI, or betting validation.
