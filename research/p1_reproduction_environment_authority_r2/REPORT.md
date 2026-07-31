# LOTTERYNEW_P1_REPRODUCTION_ENVIRONMENT_AUTHORITY_RECORD_NORMALIZATION_R2

Status: VERIFIED; evidence sealed. Draft PR publication and exact-head CI are pending.

## Outcome

R1 remains immutable. R2 supersedes only raw installed `RECORD` SHA-256 as an
acceptance gate and replaces it with `SemanticRecordV1`, while retaining raw
hashes diagnostically.

## Preserved authority

- R1 merge commit: `2e2babbfe35f30f3939ff81cf9261eb7ffee03a4`
- R1 environment authority: `8db59e2bba1ac3b448c60c3cb73771aa61a7ca5f1ccf2e1e9562439d5df42ca9`
- R1 runtime fingerprint: `d11006142d814ddf69313056210780c3ff0e16506cee923b39c07d8740d80388`
- CPython: `3.12.12`, build `20251028`, macOS arm64
- Python artifact SHA-256: `194997bc8cc08f1ed19a7e6a72544d8ce6688ef5e8969d61de2848aeb68fbf6c`
- Direct / locked / approved distributions: `7 / 25 / 23`
- Lock SHA-256: `93eecfff998fe16f1bdd63e40d05637a5e0a57357fa12ea20fed43a28a3a412d`
- Hashed export SHA-256: `7da26cb702b3a20c1ddcc9dc0414d1ac25653dcc19621f062dd6c3f07a56e88b`
- Approved artifact set SHA-256: `4b6c98fb8a6df100628d3111650dfc5230f0994c960c8b74674ef14523b75a05`
- Platform fingerprint SHA-256: `296bceb6077d0a9e83f075a6fb19d1a73b6ea4f4e24b0614085888801bc489b3`

## Independently reproduced defect

Two fresh offline hashed installs used byte-identical wheel sets whose mtimes
were deliberately different. All `23` distribution
sets and `METADATA` hashes match; `23` raw
`RECORD` hashes differ.

Pinned uv 0.9.6 source shows that on Unix it serializes wheel `ctime` into
`uv_cache.json`. The mtime perturbation also changes `ctime`; the serialized
timestamp matched wheel `ctime` for `23`
of `23` distributions in both installs. uv hashes
that generated file into its exact `RECORD` row.

V1 raw fingerprints:

- install-a: `9c42f34d6023fb9d37bb06b2ba97df937122a0c1ac4204eef7ac6729714533eb`
- install-b: `069c14283221c05097f077f74f9f400c546472eff5766a3836924b314ae97c60`

They differ and are superseded as equality gates.

## RuntimeFingerprintV2

`SemanticRecordV1` verifies every included installed file against its exact
`RECORD` hash and size. It excludes only the self-row and exact
`.dist-info/uv_cache.json` row, sorts normalized paths by Unicode code-point
order, and hashes newline-free canonical UTF-8 JSON.

V2 acceptance fingerprints:

- install-a: `5ed1180c1ec6029719b1b456056400c8e22d9d9ef0b0453504c9ea9433e89000`
- install-b: `5ed1180c1ec6029719b1b456056400c8e22d9d9ef0b0453504c9ea9433e89000`
- verification-install: `5ed1180c1ec6029719b1b456056400c8e22d9d9ef0b0453504c9ea9433e89000`

All are byte-identical at
`5ed1180c1ec6029719b1b456056400c8e22d9d9ef0b0453504c9ea9433e89000`. The aggregate
`runtime_fingerprint.json` retains every raw per-install `RECORD` hash under a
diagnostic-only field excluded from equality.

## Safety boundary

No database was opened, read, hashed, copied, or snapshotted. No P1 backtest
ran. No production, deployment, registry, strategy status, or rejection state
was changed.


## Verification and Judge

- Focused final-tree verification: `25 passed`
- Negative integrity verification: `PASS`
- Canonical authority regeneration: `PASS`
- `uv lock --check --offline`: `PASS`
- `git diff --check`: `PASS`
- Initial Judge provider/depth: `FABLE5 / BOUNDED`
- Initial Judge input HEAD/tree: `2e2babbfe35f30f3939ff81cf9261eb7ffee03a4` / `c7c515bd1d78de2c80e1db634f27b5b53f740994`
- Initial Judge verdict: `REFUTED`
- Finding: committed `uv_cache.json` stable/unstable evidence was incomplete
- Authorized remediation cycles used: `1 / 1`
- Post-Initial source or test edit: `YES`
- DELTA Judge input HEAD/tree: `2e2babbfe35f30f3939ff81cf9261eb7ffee03a4` / `a81ec05bccdf75e7d3d32a40c8704cbf576be666`
- DELTA and final Judge verdict: `VERIFIED`
- Post-DELTA source or test edit: `NO`

The post-Judge changes are limited to this finalized report and the two evidence
seal files required by the Owner-approved sequencing contract.
