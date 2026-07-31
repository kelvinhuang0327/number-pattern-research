# P334A — Risk Assessment

## Risks this audit itself carries (mitigated)

| risk | mitigation applied |
|---|---|
| Reading a stale local worktree instead of canonical origin/main | All code reads used `git show origin/main:<path>` / `git grep <pattern> origin/main`; local worktree (`task/p273a-…`, dirty, stale) never trusted for content |
| Accidentally writing to the production DB while inspecting it | Every DB query used `sqlite3.connect("file:...?mode=ro", uri=True)`; SHA-256/mtime/size re-verified identical before and after |
| Accidentally staging or committing evidence files inside the repo | All 13 output files written to a repo-external evidence root under `/Users/kelvin/Kelvin-WorkSpace/`; `git status`/`git diff --cached` re-checked empty-of-new-staging after writing |
| Drawing a wrong root-cause conclusion from aggregate stats alone | Root cause was traced to specific commits (`436b2ca`, `749a01e`, `211e3aa`, `cfff33a`, `6a3f49b`, `0fd9166`) and literal source lines (`"predicted_special": None,`), not inferred from counts alone |

## Risks in the proposed forward-only design (for the future implementation task to manage)

| risk | discussion |
|---|---|
| Model choice divergence recurring | Mitigated by the "one canonical function" recommendation (Option 1) — the Generation-A/B split happened specifically because the second-zone call was duplicated per-adapter-file instead of centralized |
| Resuming a dormant pipeline is a bigger task than it looks | §3b (no POWER_LOTTO row persisted since 2026-05-29) is a precondition, not a detail — the future task must scope pipeline-resumption separately from the second-zone fix itself, or risk silently under-scoping |
| Partial fix gives false confidence | If only Pattern 2 (multi-bet extension) is fixed and Pattern 1 (4 structurally-blind strategies) is left alone, POWER_LOTTO stays permanently `PARTIAL`/`BLOCKED` at the full-population level even after the "fix" ships — must be stated explicitly in any future task's acceptance criteria |
| Guard-test coverage gap | Without the guard test proposed in `forward_only_second_zone_design.md` §5, a *third* generation of adapters could reintroduce the exact same regression; this is the single highest-leverage, lowest-cost control identified in this audit |
| Model performance, not just presence | This audit only establishes *whether* a value can be legitimately produced and persisted — it says nothing about whether `PowerLottoSpecialPredictor`'s predictions beat random (P271F/P281A already found the 9,000-row Generation-A subset NULL after Bonferroni correction). Closing the coverage gap does not, by itself, imply POWER_LOTTO second-zone predictions have any edge — that remains a separate, already-negative, prior finding (`memory/MEMORY.md` L90/L91-adjacent POWER findings) |

## Overall risk level of proceeding with the future implementation task

Low-to-moderate: the code change itself (Option 1) is small and additive
(one new/extracted function, one call-site convention, one guard test). The
main risk is scope creep into "also resume the entire dormant POWER_LOTTO
pipeline," which is a legitimately larger, separate task that should be
explicitly authorized and estimated on its own before being bundled with
the second-zone fix.
