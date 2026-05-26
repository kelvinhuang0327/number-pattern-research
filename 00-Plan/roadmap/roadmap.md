# Lottery Replay Roadmap

**Last Updated:** 2026-05-25 Asia/Taipei (P60 update after P59 — POWER_LOTTO Wave 5 fourier30_markov30_2bet production apply complete)
**Owner:** CTO agent
**Primary Goal:** Strategy Historical Replay must become production-usable: the operator can select lottery type, strategy, date range, and 100/500/1000/1500-period presets, then inspect per-draw prediction-vs-actual comparisons in the existing historical prediction-list style. All system-developed strategies must be visible with an honest state: row-backed, artifact-only, retired, rejected-registered, observation, no-data, reconstructible, manual-review, unsupported, or dry-run. The core delivery is not catalog visibility alone and not dry-run artifacts alone: it is a governed backfill/replay engine with 1500-period prediction-vs-actual rows for all executable strategies, without fake rows or unguarded production writes.
**Repo Policy:** Use `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` only. Do not create a new repo.

---

## 1. Current Phase Snapshot

| Phase | Status | Evidence | CTO Note |
|---|---|---|---|
| P14D-P21B baseline ONLINE backfill | [Confirmed] Complete | Git history through P21B; P40/P45 reports | Three-lottery ONLINE baseline reached 12460 rows. |
| P31B Wave 1 DAILY_539 apply | [Confirmed] Complete | P40 report; production rows 12460 -> 19960 | Five retired DAILY_539 strategies became replay-backed. |
| P37 Wave 2 DAILY_539 apply | [Confirmed] Complete | `3a8fb31`; P40 report | Six DAILY_539 DRY_RUN strategies applied; rows 19960 -> 28960. |
| P43 Wave 3 BIG_LOTTO apply | [Confirmed] Complete | `72ad4e7`; P45 report | Six BIG_LOTTO DRY_RUN strategies applied; rows 28960 -> 37960. |
| P44 BIG_LOTTO performance analysis | [Confirmed] Complete | `a2a7e19`; P45 report | Promotion gate failed; BIG_LOTTO remains maintenance mode. |
| P46 POWER_LOTTO expansion planning | [Confirmed] Complete and merged | `da9ae6f`; `docs/replay/p46_powerlotto_expansion_planning_20260524.md` | Three POWER_LOTTO candidates selected for Wave 4 readiness. |
| P47 POWER_LOTTO Wave 4 dry-run + temp rehearsal | [Confirmed] Complete and merged | `7893a9d`; `docs/replay/p47_powerlotto_wave4_dryrun_rehearsal_20260524.md` | 4500 dry-run rows generated; R1/R2/R3 PASS; production rows unchanged at 37960. |
| P48 POWER_LOTTO Wave 4 production apply | [Confirmed] Complete and merged | HEAD `b4206c5`; `docs/replay/p48_powerlotto_wave4_production_apply_20260524.md` | 4500 rows inserted; production rows 37960 -> 42460; lifecycle remains DRY_RUN. |
| P49 POWER_LOTTO post-apply API verification | [Confirmed] Local evidence PASS; [Blocked] not committed/merged | Untracked P49 docs/json/tests; local 170/170 PASS | DB/API verification is available locally, but artifact governance must be closed before P50. |
| P49HYG Artifact / git hygiene closure | [Confirmed] Complete and merged | `79ab784`; PR #185; 191/191 PASS | P49 docs/json/tests committed; worktree hygiene closed; rows remained 42460. |
| P50 POWER_LOTTO Wave 4 performance analysis | [Confirmed] Complete | `docs/replay/p50_powerlotto_wave4_performance_analysis_20260525.md` | Analysis-only; all three strategies analyzed; no DB write; no lifecycle promotion. |
| P51 POWER_LOTTO Wave 4 rolling-window + McNemar gate | [Confirmed] Complete and merged | `0415cc8`; `docs/replay/p51_powerlotto_wave4_rolling_window_mcnemar_gate_20260525.md`; 250/250 PASS | `midfreq_fourier_mk_3bet` classified P52_PROMOTION_CANDIDATE (6/7 gates PASS); `pp3_freqort_4bet` and `midfreq_fourier_2bet` INCONCLUSIVE. |
| P52 POWER_LOTTO promotion readiness decision | [Confirmed] Complete and merged | `1b32e6a`; `docs/replay/p52_powerlotto_midfreq_fourier_mk_3bet_promotion_readiness_20260525.md`; 250/250 PASS | G4 McNemar b=42, c=50, champion-favored → `G4_REQUIRES_WAIVER`; ONLINE promotion not justified without waiver. |
| P53 POWER_LOTTO WATCHLIST waiver staging | [Confirmed] Complete and merged | `5992b27`; `docs/replay/p53_powerlotto_midfreq_fourier_mk_3bet_watchlist_waiver_20260525.md`; 307/307 PASS | G4 waiver granted; `midfreq_fourier_mk_3bet` staged as WATCHLIST via docs-only; champion `fourier_rhythm_3bet` remains active; rows unchanged at 42460. |
| P54 Roadmap / CTO update after P53 | [Confirmed] Complete and merged | `e6ca756`; `docs/replay/p54_replay_roadmap_update_after_p53_watchlist_20260525.md` | Roadmap and CTO docs updated to reflect P49HYG–P53 chain completion. |
| P55 Wave 5 POWER_LOTTO candidate planning | [Confirmed] Complete and merged | `776c173`; `docs/replay/p55_powerlotto_wave5_candidate_planning_20260525.md` | Three Wave 5 candidates identified: `fourier30_markov30_2bet`, `cold_complement_2bet`, `zonal_entropy_2bet`; plan-only, no DB write. |
| P56 Wave 5 POWER_LOTTO adapter bootstrap + dry-run rehearsal | [Confirmed] Complete and merged | `c3f0325`; `docs/replay/p56_powerlotto_wave5_adapter_bootstrap_dryrun_20260525.md` | Adapters bootstrapped; dry-run rows generated; production rows unchanged at 42460. |
| P57 Wave 5 POWER_LOTTO controlled rehearsal readiness | [Confirmed] Complete and merged | `aea8ff7`; `docs/replay/p57_powerlotto_wave5_controlled_rehearsal_readiness_20260525.md` | Rehearsal readiness confirmed; no production DB write; rows unchanged at 42460. |
| P58 Wave 5 POWER_LOTTO controlled apply proposal | [Confirmed] Complete and merged | `4b6a0c4`; `outputs/replay/p58_powerlotto_wave5_controlled_apply_proposal_20260525.json` | Proposal-only (Mode A); `fourier30_markov30_2bet` selected for apply; `cold_complement_2bet` and `zonal_entropy_2bet` excluded as WATCHLIST_REHEARSAL_ONLY; no DB write. |
| P59 Wave 5 POWER_LOTTO controlled production apply | [Confirmed] Complete and merged | `b4afa65`; `outputs/replay/p59_powerlotto_wave5_controlled_apply_20260525.json`; 295/295 PASS | 1500 rows inserted (`fourier30_markov30_2bet`); production rows 42460 → 43960; M3+ hit rate 4.07% vs baseline 3.87%; no ONLINE promotion; no champion replacement. |
| P60 Post-P59 remote sync / evidence consolidation / roadmap update | [In Progress] This task | `docs/replay/p60_post_p59_remote_sync_and_roadmap_update_20260525.md` | Remote push blocked by branch protection (GH006); roadmap updated to reflect P55–P59 chain; no DB write. |

---

## 2. Current Production Replay / Coverage Baseline

Verified during CTO review on 2026-05-25.

| Metric | Value |
|---|---:|
| Production replay rows | 43960 |
| Legacy rows | 460 |
| P48 controlled apply rows | 4500 |
| P48 controlled apply ID | `P48_POWERLOTTO_WAVE4_4500_PROD_20260524` |
| P59 controlled apply rows | 1500 |
| P59 controlled apply ID | `P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525` |
| POWER_LOTTO Wave 4 strategies applied | 3 |
| POWER_LOTTO Wave 5 strategies applied | 1 |
| Strategy groups with production rows | 29 / 59 |
| Approximate remaining rows to 1500-period full executable coverage | ~45000 |

Production replay coverage groups:

| Group | Strategy count | Rows | Status |
|---|---:|---:|---|
| ONLINE baseline strategies | 8 | 12460 | [Confirmed] Production row-backed |
| P31B Wave 1 DAILY_539 retired replay-backed | 5 | 7500 | [Confirmed] Production row-backed |
| P37 Wave 2 DAILY_539 DRY_RUN | 6 | 9000 | [Confirmed] Production row-backed, not ONLINE |
| P43 Wave 3 BIG_LOTTO DRY_RUN | 6 | 9000 | [Confirmed] Production row-backed, not ONLINE |
| P48 Wave 4 POWER_LOTTO DRY_RUN | 3 | 4500 | [Confirmed] Production row-backed, not ONLINE |
| P59 Wave 5 POWER_LOTTO DRY_RUN | 1 | 1500 | [Confirmed] Production row-backed, not ONLINE |

P48 POWER_LOTTO Wave 4 production rows and P50–P53 classification:

| Strategy | Production rows | Lifecycle semantics | P50–P53 Classification |
|---|---:|---|---|
| `pp3_freqort_4bet` | 1500 | DRY_RUN, not ONLINE | [P53] INCONCLUSIVE — W1500 delta positive (+0.055) but early windows underperform; 500 additional draws recommended before re-evaluation. |
| `midfreq_fourier_mk_3bet` | 1500 | DRY_RUN, **WATCHLIST** (docs-only governance) | [P53] WATCHLIST_STAGED_WITH_G4_WAIVER — mean hit 1.027 (+0.035 vs champion); perm p=0.0003; G4 McNemar b=42/c=50 champion-favored; champion `fourier_rhythm_3bet` remains active. |
| `midfreq_fourier_2bet` | 1500 | DRY_RUN, not ONLINE | [P53] INCONCLUSIVE — G2/G3/G6 all FAIL; mean hit 0.973 does not significantly exceed theoretical baseline. |

WATCHLIST OOS holdout plan for `midfreq_fourier_mk_3bet`:

| Gate | Draws from 115000041 | Calendar | Trigger |
|---|---:|---|---|
| Interim 1 | 150 | ~18 months | WATCHLIST continuation review |
| Interim 2 | 300 | ~36 months | G4 direction parity check; promotion eligibility assessment |
| Final | 500 | ~48 months | Full OOS evaluation — promote or archive |

ONLINE promotion for `midfreq_fourier_mk_3bet` requires: 300+ additional draws, McNemar `hit_count >= 3` direction parity (b >= c), McNemar `hit_count >= 2` p < 0.05, and explicit P55+ authorization.

POWER_LOTTO semantics that must remain stable:

| Field | Required Meaning |
|---|---|
| `predicted_numbers` / `actual_numbers` | First zone: exactly 6 unique integers in [1, 38] |
| `predicted_special` / `actual_special` | Second zone: exactly one integer in [1, 8] |
| `hit_count` | First-zone hits only; never includes special |
| `special_hit` | `predicted_special == actual_special`, represented as 0/1 |
| `actual_special is NULL` | P48 Policy A: skip; P48 `skip_count=0` |

---

## 3. Roadmap Alignment Assessment

| Item | Classification | Assessment |
|---|---|---|
| P48 controlled production apply | [Aligned] | P48 correctly followed gated apply governance and converted P47 readiness into production rows. |
| P48 row-count baseline | [Aligned] | Production rows are now 42460; drift and branch governance guards pass at 42460. |
| P49 API/DB verification | [Confirmed] | Local evidence verified `/api/replay/history`, `/api/replay/summary`, DB counts, and POWER_LOTTO semantics. |
| P49HYG artifact commit/merge | [Confirmed] Complete | P49 docs/json/tests committed at `79ab784`, PR #185. Artifact governance closed. |
| P49 browser visual evidence | [Deferred] | Explicitly deferred to P11. DB/API verification confirmed; UI smoke is separate. |
| P50 performance analysis | [Confirmed] Complete | Analysis-only; all three P48 strategies classified; no DB write; rows remained 42460. |
| P51 rolling-window + McNemar | [Confirmed] Complete | `midfreq_fourier_mk_3bet` 6/7 gates PASS; perm p=0.0003; G4 McNemar waiver required. |
| P52 promotion readiness | [Confirmed] Complete | G4 direction champion-favored; `G4_REQUIRES_WAIVER`; waiver required for WATCHLIST. |
| P53 WATCHLIST staging | [Confirmed] Complete | G4 waiver granted; docs-only WATCHLIST declaration; champion unchanged; 307/307 PASS. |
| Lifecycle ONLINE promotion | [Deferred] | ONLINE promotion for `midfreq_fourier_mk_3bet` requires 300+ draws + explicit P55+ authorization. |
| Wave 5 planning (P55–P59) | [Confirmed] Complete and merged | P55 candidate planning → P56 dry-run → P57 rehearsal → P58 proposal → P59 apply; `fourier30_markov30_2bet` row-backed; WATCHLIST: `cold_complement_2bet`, `zonal_entropy_2bet`. |
| Date-range default half-year | [Missing] | Still a UX gap; deferred to P3. |

---

## 4. Reprioritized P0-P10

| Priority | Phase | Focus | Current Status | Acceptance Criteria |
|---|---|---|---|---|
| **P0** | P49HYG artifact / git hygiene closure | Resolve untracked P49 docs/json/tests | [Confirmed] **Complete** — `79ab784`, PR #185 | ✅ Done. |
| **P1** | P50–P53 POWER_LOTTO Wave 4 analysis + WATCHLIST staging | Analysis, promotion gate, and WATCHLIST governance | [Confirmed] **Complete** — commits `0415cc8`, `1b32e6a`, `5992b27` | ✅ Done. `midfreq_fourier_mk_3bet` = WATCHLIST. Others = INCONCLUSIVE. Rows = 42460. |
| **P2** | `midfreq_fourier_mk_3bet` WATCHLIST OOS monitoring | Monitor 150/300/500 draw gates; re-evaluate G4 direction | [Active] 500-draw plan created in P53 | Interim gate at 150 additional draws from 115000041. Pass/fail criteria in `p53_*.md`. |
| **P3** | ~~Wave 5 candidate planning~~ | P55–P59 complete | [Confirmed] **Complete** — P55–P59 merged; `fourier30_markov30_2bet` row-backed (43960 rows) | ✅ Done. |
| **P4** | P11 Browser visual evidence closure | Confirm Replay UI displays P48 POWER_LOTTO strategies and special fields | [Deferred] Explicitly deferred from P49 | Browser smoke/screenshot or explicit CTO waiver; no DB write. |
| **P5** | DRY_RUN -> ONLINE promotion criteria | Formalize cross-lottery promotion gate | [Deferred] | Statistical criteria and governance; no automatic lifecycle mutation. |
| **P6** | Freshness cadence guard | Keep replay rows current after new draws | [Deferred] | Read-only or gated cadence report for missing latest rows. |
| **P7** | Catalog freshness / inventory guard | Prevent catalog drift | [Deferred] | Guard detects catalog/source mismatch without DB writes. |
| **P8** | P12 Worktree-wide housekeeping | Clean untracked files, fuse_hidden, pid files | [Deferred] Explicitly deferred from P49 | `git status` clean or explicitly acknowledged; no production DB changes. |
| **P9** | Evidence consolidation | Index P31B-P54 docs and apply IDs | [Deferred] | One durable reference separates planning, rehearsal, apply, verification, analysis. |
| **P10** | Post-launch operations | Ongoing replay freshness and coverage monitoring | [Deferred] | Operational reports flag missing rows after future draws. |

Items to downgrade, merge, pause, or retire:

| Item | Decision | Reason |
|---|---|---|
| Re-running P48 production apply | Retire | [Confirmed] P48 already inserted 4500 rows and rows are 42460. |
| Treating P50 as promotion execution | Pause / forbid | [Confirmed] P50 must be analysis-only; lifecycle mutation needs separate authorization. |
| Starting P50 before P49 artifact closure | Pause | [Confirmed] P49 files are currently untracked locally. |
| Wave 5 adapter wiring before P50 | Downgrade | [Inferred] P50 Wave 4 results should inform Wave 5 priorities. |
| Broad UI redesign | Pause | [Confirmed] Replay should remain based on existing historical prediction-list style. |

---

## 5. Critical Blockers

| Blocker | Impact | Status | Resolution |
|---|---|---|---|
| P49 artifacts untracked | Traceability | **[Resolved]** | P49HYG commit `79ab784`, PR #185. Worktree debt acknowledged. |
| P50 analysis not started | Strategy governance | **[Resolved]** | P50–P53 complete; all three strategies classified. |
| P50 promotion boundary | Governance | **[Resolved]** | No ONLINE promotion occurred through P53; lifecycle remains DRY_RUN. |
| P49 browser visual evidence unclear | Product readiness | **[Deferred]** | Explicitly deferred to P11. Not blocking P50–P53 chain. |
| POWER_LOTTO special semantics | Metric correctness | **[Resolved]** | P50–P53 kept `hit_count` (first-zone) and `special_hit` (second-zone) strictly separate. |
| `midfreq_fourier_mk_3bet` ONLINE promotion | Promotion governance | **[Active gate]** | WATCHLIST declared. 300+ OOS draws required before P55+ promotion review. Champion `fourier_rhythm_3bet` remains active. |
| Wave 5 planning pending | Coverage gap | **[Ready to unlock]** | P3 ready to start after P54 roadmap update. |

---

## 6. Most Valuable System Optimization Directions

### Direction A: ~~P49 Artifact / Git Hygiene Closure~~ [COMPLETE]

- **Status:** [Confirmed] Complete — `79ab784`, PR #185.
- **Priority:** ~~P0~~ → **Resolved**

### Direction B: ~~P50–P53 POWER_LOTTO Wave 4 Analysis + WATCHLIST Staging~~ [COMPLETE]

- **Status:** [Confirmed] Complete — P50 (`docs/replay/p50_*`), P51 (`0415cc8`), P52 (`1b32e6a`), P53 (`5992b27`).
- **Result:** `midfreq_fourier_mk_3bet` = WATCHLIST (docs-only, G4 waiver); others = INCONCLUSIVE.
- **Priority:** ~~P1~~ → **Resolved**

### Direction C: `midfreq_fourier_mk_3bet` WATCHLIST OOS Monitoring [ACTIVE]

- **Roadmap phase:** P2
- **Why important:** Candidate has stable mean-hit advantage (+0.035) but G4 McNemar direction is champion-favored. Monitoring is required to determine whether direction improves over time.
- **System maturity gain:** Converts WATCHLIST declaration into evidence-based ONLINE promotion decision or archive decision.
- **Expected benefit:** At 150-draw interim gate, early signal whether candidate holds advantage.
- **Risk:** Promoting ONLINE before G4 direction parity would replace champion on a metric the champion wins.
- **Acceptance:** 300+ additional draws + McNemar `hit_count >= 3` direction parity + explicit P55+ authorization.
- **Priority:** P2 (Active monitoring, no immediate action required)

### Direction D: Wave 5 Candidate Planning [READY TO START]

- **Roadmap phase:** P3
- **Why important:** Coverage gap remains large (~46,500 rows to full 1500-period coverage). P50–P53 decisions are now complete.
- **System maturity gain:** Continues coverage expansion beyond Wave 4.
- **Expected benefit:** Next 3-6 executable strategies identified and staged for Wave 5 dry-run.
- **Risk:** Wave 5 wiring should not preempt WATCHLIST OOS monitoring or P11/P12 closure.
- **Acceptance:** Plan-only; no adapter wiring or DB writes before Wave 5 dry-run authorization.
- **Priority:** P3

### Direction E: Replay UI Browser Evidence Closure (P11)

- **Roadmap phase:** P4
- **Why important:** API verification is strong; UI visual evidence for POWER_LOTTO special fields not confirmed.
- **Status:** Explicitly deferred from P49; ready when operator chooses P11.
- **Priority:** P4

### Direction F: Freshness, Pagination, Evidence Consolidation (P6–P9)

- **Roadmap phase:** P6–P9
- **Status:** Deferred; begin after P3 Wave 5 planning.
- **Priority:** P6+

---

## 7. Today's Focus

**P60 complete.** Roadmap updated to reflect P55–P59 Wave 5 chain completion.

### Immediate State (post-P60)
- P55–P59 all merged to main. ✅
- Production rows: **43960** (+1500 from P59). ✅
- `fourier30_markov30_2bet`: **row-backed** (DRY_RUN, 1500 rows, no ONLINE promotion). ✅
- `cold_complement_2bet`: **WATCHLIST_REHEARSAL_ONLY** (not applied). ✅
- `zonal_entropy_2bet`: **WATCHLIST_REHEARSAL_ONLY** (not applied). ✅
- `midfreq_fourier_mk_3bet`: **WATCHLIST** (docs-only, G4 waiver, champion remains active). ✅
- Remote push blocked by branch protection (GH006: `replay-default-validation` required). ⚠️

### Governance Boundaries (Permanent)
- Do not re-run P48 or P59 production apply.
- Do not write new replay rows without explicit production apply authorization.
- Do not promote `fourier30_markov30_2bet`, `midfreq_fourier_mk_3bet`, or any Wave 5 strategy to ONLINE without explicit authorization.
- Do not replace champion `fourier_rhythm_3bet`.
- Do not mutate registry.
- Do not force push main without explicit authorization.

### Recommended Next Session (P61 options — operator chooses one)

| Option | Task | Scope |
|---|---|---|
| P61-A | Post-P59 API/DB verification | Verify `/api/replay/history` returns P59 rows; confirm POWER_LOTTO semantics; read-only |
| P61-B | P11 Browser visual evidence closure | Replay UI smoke for POWER_LOTTO Wave 5 strategies |
| P61-C | P12 Worktree-wide housekeeping | Clean pre-existing dirty files; no production DB change |
| P61-D | Wave 6 candidate planning | Plan-only; next strategies after Wave 5 |

Final roadmap marker:

```text
CTO_ROADMAP_AFTER_P59_POWERLOTTO_WAVE5_APPLY_20260525
```
