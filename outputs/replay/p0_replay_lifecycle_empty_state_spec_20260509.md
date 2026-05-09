# P0 Replay Lifecycle Empty State Spec
**Date:** 2026-05-09  
**Branch:** codex/p0-replay-lifecycle-catalog-population-plan

Some governance/wiki source evidence was read from sibling canonical worktree /Users/kelvin/Kelvin-WorkSpace/LotteryNew because the corresponding files were missing in LotteryNew-main-postmerge.

## 1. Empty States

| lifecycle bucket | empty-state text | required explanation |
|------------------|------------------|----------------------|
| OFFLINE | 查無可信 OFFLINE 條目 | no concrete trusted row exists in the current repo |
| RETIRED | 查無可信 RETIRED 條目 | policy exists, but no concrete retired row exists |
| OBSERVATION | 目前僅有 WATCH / PROVISIONAL 候選，尚未形成 canonical OBSERVATION rows | do not coerce candidate evidence into canonical status without explicit mapping |

## 2. UI / Report Copy

Use copy that is honest about the data boundary:

- `目前沒有可信條目`
- `僅有候選證據，尚未升格為 canonical lifecycle row`
- `此欄位依目前可信來源為空`

Avoid copy that suggests a system failure when the cause is actually an empty catalog.

## 3. What Not to Render

- Do not render fake OFFLINE or RETIRED rows.
- Do not render placeholder strategy names.
- Do not claim the catalog is complete.
- Do not label WATCH evidence as RETIRED.
- Do not label PROVISIONAL evidence as OFFLINE.

## 4. Source Hints

If a user asks why a bucket is empty, point to the source boundary:

- `wiki/system/strategy_retirement_policy.md` defines retirement procedure, but does not itself create retired instances.
- `rejected/README.md` is an archive index, not a live lifecycle generator.
- `provisional/pp3_sum_reversal_power.json` is explicitly provisional.
