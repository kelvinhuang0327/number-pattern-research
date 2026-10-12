# LOTTERYNEW_P1_REPRODUCTION_ENVIRONMENT_AUTHORITY_CONSOLE_SCRIPT_NORMALIZATION_R3

Status: VERIFIED, sealed, and ready for Draft PR publication.

## Outcome

R1 and R2 remain immutable. R3 supersedes only path-dependent raw
console-script launcher acceptance and replaces it with
`ConsoleScriptSemanticV2`, while retaining raw launcher template types, hashes,
and sizes diagnostically.

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

`LauncherNormalizationPolicyV2` maps both approved uv raw bootstraps to the
canonical `#!${PYTHON_INTERPRETER}` semantic prefix while preserving the
complete non-bootstrap Python payload before hashing.

Per-install RuntimeFingerprintV3 identities:

- install-short: `372f2ec1ed250e4ad2b994196a0e7c2125b0a45a9ce9edf04d6064f86e33204e`
- install-long-path-for-normalization-proof: `372f2ec1ed250e4ad2b994196a0e7c2125b0a45a9ce9edf04d6064f86e33204e`
- verification-install: `372f2ec1ed250e4ad2b994196a0e7c2125b0a45a9ce9edf04d6064f86e33204e`

All are byte-identical at `372f2ec1ed250e4ad2b994196a0e7c2125b0a45a9ce9edf04d6064f86e33204e`.
`7` launchers were compared; every raw hash differed across the two
differently-rooted installs, and every normalized hash and
`ConsoleScriptSemanticV2` row matched with
`launcher_type: uv_console_script`.

## Safety boundary

No database was opened, read, hashed, copied, or snapshotted. No P1 backtest
ran. No production, deployment, registry, strategy status, or rejection state
was changed.

## Acceptance provenance

The mandatory non-skipping regeneration command is defined in
`installation_recipe.json`. Focused test counts and skip counts are execution
provenance recorded with the PR and handoff; they are not MANIFEST fields.
General Replay Governance CI does not replace focused R3 acceptance.

The prior fixed head `063293ae157a3d392235292cfb754faf535394c8` and tree `d8528c0ee6e6e7f1f29973aa7fa109cfbb99dd9b`
were REFUTED and are superseded by the corrected PR head. Final sealed-tree
Judge identity belongs in PR and handoff execution provenance rather than in
this non-recursive sealed package.


## Verification and Judge

- Focused test counts/skips: PR and handoff execution provenance, not MANIFEST
- Negative integrity cases: `PASS`
- Canonical authority regeneration: `PASS`
- `uv lock --check --offline`: `PASS`
- `git diff --check`: `PASS`
- Pre-seal Judge provider/depth: `FABLE_JUDGE_SKILL / DELTA`
- Pre-seal Judge input HEAD: `0ecf3ef61d974b6ac194912a9fbd34227312184d`
- Pre-seal Judge input tree: `ea2fb4872584ec212691c5249b20a3c1b983ca29`
- Pre-seal Judge verdict: `VERIFIED`
- Final sealed-tree Judge: PR and handoff execution provenance; not recursively embedded
