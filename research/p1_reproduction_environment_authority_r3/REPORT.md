# LOTTERYNEW_P1_REPRODUCTION_ENVIRONMENT_AUTHORITY_CONSOLE_SCRIPT_NORMALIZATION_R3

Status: VERIFIED, sealed, and ready for Draft PR publication.

## Outcome

R1 and R2 remain immutable. R3 supersedes only path-dependent raw
console-script launcher acceptance and replaces it with
`ConsoleScriptSemanticV1`, while retaining raw launcher hashes diagnostically.

## Preserved authority

- R2 merge commit: `8bfb4acce43e45a7920799699d9f946b442a3ec6`
- R2 environment authority: `eeb0bdf0f6b4c3a5e49a02e540828a1917dcee11f3f716ebc53f72b4b6c1d5e8`
- R2 runtime fingerprint: `040f9c261a716460a760f6b72496fd42f9dafe5fb8b9423f4269e97f3d69ddec`
- CPython: `3.12.12`, build `20251028`, macOS arm64
- Python artifact SHA-256: `194997bc8cc08f1ed19a7e6a72544d8ce6688ef5e8969d61de2848aeb68fbf6c`
- Direct / locked / approved distributions: `7 / 25 / 23`
- Affected distributions: `fastapi, idna, numpy, pygments, pytest`
- Affected launchers: `bin/fastapi, bin/idna, bin/f2py, bin/numpy-config, bin/pygmentize, bin/pytest, bin/py.test`

## Independently reproduced defect

Three fresh offline hashed installs used the same wheelhouse under
installation roots of materially different absolute path length. All
non-launcher distribution content and `METADATA` hashes match across all
three; raw launcher hashes differ for every one of the 7 affected launchers
whenever the absolute root differs.

## RuntimeFingerprintV3

`LauncherNormalizationPolicyV1` replaces only the resolved interpreter-path
segment of each declared console-script launcher with `${PYTHON_INTERPRETER}`
before hashing.

Per-install RuntimeFingerprintV3 identities:

- install-short: `8f1db9d6169474224ca62038ac1045d9214f25306d8edecb54497145191942e6`
- install-long-path-for-normalization-proof: `8f1db9d6169474224ca62038ac1045d9214f25306d8edecb54497145191942e6`
- verification-install: `8f1db9d6169474224ca62038ac1045d9214f25306d8edecb54497145191942e6`

All are byte-identical at `8f1db9d6169474224ca62038ac1045d9214f25306d8edecb54497145191942e6`.
`7` launchers were compared; every raw hash differed across the two
differently-rooted installs, and every normalized hash and
`ConsoleScriptSemanticV1` row matched.

## Safety boundary

No database was opened, read, hashed, copied, or snapshotted. No P1 backtest
ran. No production, deployment, registry, strategy status, or rejection state
was changed.


## Verification and Judge

- Focused tests: see FOCUSED_TEST_COUNT in the sealed MANIFEST
- Negative integrity cases: `PASS`
- Canonical authority regeneration: `PASS`
- `uv lock --check --offline`: `PASS`
- `git diff --check`: `PASS`
- Judge provider/depth: `FABLE_JUDGE_SKILL / BOUNDED`
- Judge input HEAD: `b5b15bbc9fe8149a1910caca103c0d6cf228a669`
- Judge input tree: `e6ef7030e94a3b7d2607462c86563783f413b627`
- Final Judge verdict: `VERIFIED`
