---
source_path: /Users/kelvin/Kelvin-WorkSpace/workspace-AI/LotteryNew/ai-wiki/flows/strategy-research-cycle.md
source_mtime: 2026-04-27T17:57:35+0800
source_sha256: fc7c58a9b8082a2c00cbde74a6f32e6be7b83b9856e351907ab796e4a5af22c6
legacy_warning: "COPY-IN from legacy workspace-AI overlay; may be stale. Source retained in place; do not treat as canonical without re-analysis."
---

# Strategy Research Cycle

Intent: describe the documented research loop used by the project.

Flow:
1. Form a hypothesis or generate a candidate strategy.
2. Run simulation and backtest scripts from `tools/` and related research directories.
3. Validate significance, robustness, and guardrails.
4. Promote outputs into `strategies/` or monitoring data when accepted.
5. Archive failed ideas or unsupported claims under rejected or report paths.

Primary actors:
- Research engineer
- Backtest and validation scripts
- Strategy output storage
- Reporting artifacts

Observed source statement:
- SYSTEM_MAP.md describes `Idea -> Simulation -> Backtest -> Validation -> Evolution -> Ensemble`.

Notes:
- The project contains many specialized research scripts; this page records only the shared lifecycle.