# P541B-R2 — BIG_LOTTO Legacy Method Evidence Remediation

> generated_at_utc: `2026-07-11T12:43:50Z`

## Decision

The historical Boolean safety evidence is superseded by a fail-closed, tri-state static evidence contract. Historical P541B artifacts remain unchanged.

## Summary

| Metric | Value |
|---|---:|
| Frozen source records | 580 |
| Complete scans | 554 |
| Unknown scans | 26 |
| Risk `high` | 466 |
| Risk `low` | 18 |
| Risk `medium` | 70 |
| Risk `unknown` | 26 |

## Tri-State Evidence

| Evidence | detected | not_detected | unknown |
|---|---:|---:|---:|
| `database_access` | 379 | 175 | 26 |
| `filesystem_write` | 147 | 407 | 26 |
| `network_io` | 17 | 537 | 26 |
| `subprocess_execution` | 12 | 542 | 26 |
| `other_external_effect` | 32 | 522 | 26 |
| `import_time_execution` | 505 | 49 | 26 |
| `hardcoded_absolute_path` | 56 | 498 | 26 |
| `hardcoded_draw_or_date` | 55 | 499 | 26 |
| `valid_main_guard` | 523 | 31 | 26 |
| `malformed_main_guard` | 1 | 553 | 26 |

## Detector Contract

- Evidence states are exactly `detected`, `not_detected`, and `unknown`.
- Decode failure, AST failure, star imports, dynamic code/imports, and dynamic file modes fail closed.
- Main-guard recognition accepts only an exact top-level `__name__ == '__main__'` comparison (either operand order).
- A valid main guard mitigates import-time execution only; effects inside guarded or deferred code remain detected.
- DB, filesystem-write, network, subprocess, and other external-effect detection resolves supported aliases.
- Low-risk eligibility requires a complete scan and every relevant evidence category explicitly `not_detected`.

## Frozen Provenance

- Base main: `c50137583243d4f9f4915a3e1d9babee50b5bbd7`
- Frozen source commit: `49a25effa62fc24f40789c16be6f11bdfb41a4a9`
- Historical JSON blob: `12f1595c96e3f9deddc7a7d2d9549c03144635f0` — verification **PASS**
- Historical Markdown blob: `3b28e39bfe747c5f196b9aec6610284709466cf8` — verification **PASS**
- Frozen manifest: 580 Git blobs, canonical SHA-256 `ca2cd66375033a91f1f89667c959d032e967bdf8d4322d8a3b5bed7ff317bc16` — verification **PASS**
- Source discovery from the current working tree is prohibited.

## Downstream Requirement

PR #663 was not changed. A separately authorized replacement P541C task must consume this tri-state evidence, regenerate all derived counts and shortlist membership, and must never coerce `unknown` to `false`.

## Limitations

- Static detection is conservative and does not prove runtime safety.
- Unknown blocks low-risk eligibility and requires targeted review or detector support.
- Historical identity/method-family classifications are retained as context, not re-proven.
- No database, source import, source execution, replay, or predictive evaluation was performed.

**Disclaimer:** Historical static safety-evidence remediation only. This artifact does not establish prediction quality, replay readiness, betting edge, ROI, or production safety.
