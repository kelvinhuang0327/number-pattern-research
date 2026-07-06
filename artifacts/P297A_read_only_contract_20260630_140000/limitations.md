# P297A Limitations

Generated: 2026-06-30T07:38:29.278339+00:00

## Confirmed Limits
- This run is read-only and artifact-only. No DB migration, production apply, registry publication, commit, push, PR, or roadmap/governance edit was performed.
- Current worktree is `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` on `task/p273a-prize-aware-inferential-validation`, which is a stale/protected worktree named by the prompt. Repo governance was not edited.
- Canonical worktree `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-main` exists, but its branch has no upstream configured and has dirty governance/roadmap files. Canonical branch relation is therefore not fully confirmed.
- The canonical replay DB inferred from local evidence is `lottery_api/data/lottery_v2.db`; this run opened it only with SQLite URI `mode=ro&immutable=1`.
- `POWER_LOTTO` canonical view is absent in inspected SQLite views. Only `draws_big_lotto_canonical_main` was found as a canonical draw view.
- `POWER_LOTTO` prize-aware scoring is partial: P271D reports missing predicted second-zone values for 27,104 of 36,104 rows, so full POWER_LOTTO prize-aware replay is blocked.
- Prospective thresholds and prospective evaluation horizon are absent. Retrospective hit-rate, prize-tier, or M3+ evidence must remain `NULL` or `NOT_READY` for future prediction claims until prospectively pre-registered and evaluated.

## Unknowns
- Whether `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-main` is the intended canonical branch for P297A is not fully knowable from read-only local state because no upstream is configured and the prompt explicitly says not to assume.
- Current untracked files and dirty DB files in the stale worktree were not classified beyond read-only status capture.
- No live service/API verification was run.

## Prohibited Claims
- Do not claim any strategy is bettable, production-ready, online-ready, or profitable from these artifacts.
- Do not convert retrospective deltas, p-values, or observed counts into future predictive ability.
- Do not use P273A observed counts as inference; P273A explicitly did not compute baseline, p-value, correction, edge, or verdict.
- Do not treat `GO_CANDIDATE_REQUIRES_PROSPECTIVE_GATE` inventory text as actual production GO.
