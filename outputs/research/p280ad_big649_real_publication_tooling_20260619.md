# P280AD BIG 6/49 Real-Publication Tooling

## Classification

`P280AD_BIG649_REAL_PUBLICATION_TOOLING_PR_OPEN_NOT_ACTIVATED`

This task adds validate-only tooling and synthetic-fixture coverage. It does not
authorize or perform a real publication.

## Scope

- Candidate manifest builder with caller-supplied target, official source,
  official deadline, history cutoff, source/tool digests, and all 11 tickets.
- Strict schema, ticket, duplicate, idempotency, randomness, and self-hash guards.
- Deterministic paths:
  - `outputs/publications/big649/pre_draw/<target_draw>/manifest.json`
  - `outputs/publications/big649/pre_draw/<target_draw>/manifest.md`
- Default mode: `SAFE_VALIDATE_ONLY`; the runner does not write either path.

## Guard Behavior

- Exact 11 frozen BIG strategies, `N=1`, `bet_index=1`, and endpoint
  `BIG_ANY_PRIZE_AWARE_WIN` are mandatory.
- Six unique integer numbers in `1..49` are required per ticket; duplicate
  complete tickets are rejected.
- Same manifest for an existing target is idempotent. A different manifest for
  the same target is a STOP.
- Deterministic rerun mismatch is a STOP. Stochastic output without both a seed
  and a policy is a STOP.
- Target traversal, missing official metadata/deadline, false outcome guards,
  claims/promotion/activation flags, and manifest mutation are rejected.

## Non-Actions

- Real target selected: **NO**
- Official deadline lookup: **NO**
- Real ticket generated: **NO**
- Publication PR created: **NO**
- Future evaluation started: **NO**
- DB opened / queried / copied / written: **NO / NO / NO / NO**
- Prediction success claimed: **NO**
- Strategy promoted or activated: **NO**

## Remaining Blocker

This runner deliberately requires already-generated outputs. It does not wire or
invent an adapter for generating the 11 real strategy tickets. A separately
authorized real-publication task must verify an exact safe no-DB adapter (or
implement one within its own authorized scope); if that adapter is unavailable,
the real task must STOP.

## Next Step

Run an independent P280AD audit. Do not automatically merge, choose a target,
look up a deadline, generate a ticket, create a publication PR, or evaluate an
outcome.
