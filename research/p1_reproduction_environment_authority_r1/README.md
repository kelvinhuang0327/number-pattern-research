# P1 Reproduction Environment Authority R1

This isolated subproject freezes the Python runtime and third-party distribution
closure approved for a future clean-room reproduction of the historical Big
Lotto P1 4-bet and 5-bet research sources.

It establishes runtime authority only. It does not copy or rewrite strategy
code, execute a backtest, inspect a lottery database, decide whether a strategy
passes, or modify production behavior.

## Approved source identity

- Contract authority commit: `2aaa1874320ac50f2a08ed1414094faac7098146`
- Contract authority tree: `806cd3aec4a2b290f40b647f0310aa51b010039a`
- Historical source commit: `28940a2572c051c6ba8b2ab6a077f706e800477d`
- 4-bet source blob: `2efa426d7f24d9baefb6ed6dcedf467fa2542dee`
- 5-bet source blob: `5ece590b40bd3d731dc98f5cfdd7c85aa3a5b347`

Static imports establish the direct runtime dependencies:

- `apscheduler==3.11.3`
- `fastapi==0.140.0`
- `numpy==2.5.1`
- `pydantic==2.13.4`
- `scikit-learn==1.9.0`
- `scipy==1.18.0`
- `pytest==9.1.1` for this package's focused verification

The historical source path reaches a function-local import when
`DatabaseManager.get_all_draws("BIG_LOTTO")` is called:

`database → common → scheduler/config → advanced_auto_learning → advanced_strategies`

That import-time chain introduces FastAPI, APScheduler, Pydantic, and
scikit-learn. NetworkX occurs only inside unrelated strategy methods and is not
loaded by this approved P1 path. Database loading itself remains outside this
environment bootstrap and must not be invoked by its tests or build tooling.

## Reproduction boundary

All mutable runtime outputs must be redirected to a task-owned runtime root.
The committed package contains no database, wheel, virtual environment, cache,
or interpreter binary. `uv.lock` and `requirements.lock.txt` are the dependency
resolution authorities; the JSON records bind that resolution to the approved
macOS arm64 interpreter, selected wheels, installed metadata, and exact runtime
fingerprint.
