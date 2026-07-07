---
source_path: /Users/kelvin/Kelvin-WorkSpace/workspace-AI/LotteryNew/ai-wiki/modules/research-tooling.md
source_mtime: 2026-04-27T17:57:35+0800
source_sha256: 4336eff3ab9d6e1d0587a6484e419d117a9d42f996d97a10cbc6591f049c2c79
legacy_warning: "COPY-IN from legacy workspace-AI overlay; may be stale. Source retained in place; do not treat as canonical without re-analysis."
---

# Research Tooling

Scope: script-heavy research, backtesting, validation, and maintenance layer.

Primary paths:
- `tools/`
- `research/`
- `strategies/`
- `analysis/`
- `tests/`

Responsibilities:
- Run CLI predictions and backtests.
- Evaluate hypotheses and validate strategy quality.
- Generate reports, benchmarks, and monitoring artifacts.
- Maintain research data and derived outputs.

Observed entry points:
- `python3 tools/quick_predict.py all`
- `python3 tools/orchestrator_status.py`
- `python3 tools/verify_prediction_api.py`

Key integrations:
- Local JSON artifacts
- Strategy output directories
- Internal simulation and validation engines

Notes:
- `tools/` is very large and heterogeneous; this page intentionally stays high-level.
- Lightweight scan only captured the main operational scripts and broad script categories.