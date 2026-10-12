# LOTTERYNEW_BIG_LOTTO_P1_REPRODUCTION_ENVIRONMENT_BOOTSTRAP_R1

Status: verified and sealed.

## Outcome

An isolated runtime authority was built for the exact historical Big Lotto P1
4-bet and 5-bet source identities. It freezes a uv-managed standalone CPython,
the exact dependency closure, one approved wheel per macOS arm64 distribution,
an offline installation receipt, and a canonical `RuntimeFingerprintV1`.

This task did not execute the P1 strategy, open or copy a database, create a DB
snapshot, make a strategy decision, or modify production code.

## Authority and runtime

- Contract commit/tree:
  `2aaa1874320ac50f2a08ed1414094faac7098146` /
  `806cd3aec4a2b290f40b647f0310aa51b010039a`
- Task base commit/tree:
  `10951263f4e1c5094a92ed6083ccd100e8f1bc04` /
  `61941f6bea3c531b725eeb4e0d588c5bb2b2f0b8`
- Historical source commit:
  `28940a2572c051c6ba8b2ab6a077f706e800477d`
- Python: CPython 3.12.12, build `20251028`,
  `cpython-3.12.12-macos-aarch64-none`
- Python artifact:
  `cpython-3.12.12+20251028-aarch64-apple-darwin-install_only_stripped.tar.gz`
- Python artifact SHA-256:
  `194997bc8cc08f1ed19a7e6a72544d8ce6688ef5e8969d61de2848aeb68fbf6c`

Python 3.12 is the lowest minor supported by every exact direct dependency;
3.12.12 is the newest uv-catalogued patch in that minor.

## Dependency closure

The exact reachable import path is:

`backtests → DatabaseManager.get_all_draws → common → scheduler/config → advanced_auto_learning → advanced_strategies`

Seven exact direct distributions are pinned:

- `apscheduler==3.11.3`
- `fastapi==0.140.0`
- `numpy==2.5.1`
- `pydantic==2.13.4`
- `pytest==9.1.1`
- `scikit-learn==1.9.0`
- `scipy==1.18.0`

The lock contains 25 registry distributions across platforms. The approved
macOS arm64 closure contains 23 distributions; only Windows-marker `colorama`
and `tzdata` are excluded. No editable, VCS, local-path, AutoGluon, TensorFlow,
CatBoost, LightGBM, or NetworkX dependency is present.

## Deterministic evidence

- Lock SHA-256:
  `93eecfff998fe16f1bdd63e40d05637a5e0a57357fa12ea20fed43a28a3a412d`
- Hashed export SHA-256:
  `7da26cb702b3a20c1ddcc9dc0414d1ac25653dcc19621f062dd6c3f07a56e88b`
- Expected distribution set SHA-256:
  `752615e2a1da9aaa01cbaf12d64f7377c26c9704a937d522d0142b93a16566b6`
- Approved artifact set SHA-256:
  `4b6c98fb8a6df100628d3111650dfc5230f0994c960c8b74674ef14523b75a05`
- Platform fingerprint SHA-256:
  `296bceb6077d0a9e83f075a6fb19d1a73b6ea4f4e24b0614085888801bc489b3`
- Runtime fingerprint SHA-256:
  `d11006142d814ddf69313056210780c3ff0e16506cee923b39c07d8740d80388`
- Environment authority SHA-256:
  `8db59e2bba1ac3b448c60c3cb73771aa61a7ca5f1ccf2e1e9562439d5df42ca9`

The fresh verification environment installed 23 distributions with network
disabled, hashes required, indexes disabled, and only the approved wheelhouse
available. Expected and actual distribution sets match. A second generator run
was byte-identical. The final focused verification result was `10 passed`.

## Judge chronology

The Initial bounded Judge reviewed HEAD
`10951263f4e1c5094a92ed6083ccd100e8f1bc04`, candidate tree
`142a266904a840b60cc85cd4df0d193c2c3e09f6`, and returned `REFUTED` because
the first import scan missed the function-local `common` chain.

One authorized remediation traced and froze that exact chain. The fresh DELTA
Judge reviewed candidate tree `eb58b1b2137084363352f542d94a882133797f93`
and returned `VERIFIED`. No source or test file was edited after that verdict.

`MANIFEST.json` records the payload hashes. `SHA256SUMS` is the second-level
seal: it hashes every payload plus the manifest, while excluding itself.
