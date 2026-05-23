# Lottery Replay Roadmap

**Last Updated:** 2026-05-23 Asia/Taipei (P33 update after P31B + P32)
**Owner:** CTO agent
**Primary Goal:** Strategy Historical Replay must become production-usable: the operator can select lottery type, strategy, date range, and 100/500/1000/1500-period presets, then inspect per-draw prediction-vs-actual comparisons in the existing historical prediction-list style. All system-developed strategies must be visible with an honest state: row-backed, artifact-only, retired, rejected-registered, observation, no-data, reconstructible, manual-review, or unsupported. The final product direction is not catalog visibility alone: it is 1500-period replay coverage for all executable strategies, with no fake replay rows and no unguarded production writes.
**Repo Policy:** Use `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` only. Do not create a new repo.

---

## 1. Current Phase Snapshot

| Phase | Status | Evidence | CTO Note |
|---|---|---|---|
| P0 Schema stabilization | [Confirmed] Complete | `docs/replay/p0_schema_diff_20260519.md`; API contract PASS | Baseline no longer blocks replay work. |
| P14D-P21B replay backfill | [Confirmed] Complete for ONLINE strategies | git history through `a0b2867`; drift guard baseline 12460 | Three-lottery ONLINE replay store is row-backed. |
| P22 DAILY_539 API/UI verification | [Confirmed] Complete | `docs/replay/p22_daily539_api_ui_verification_20260521.md` | DAILY_539 5-number/no-special semantics verified. |
| P23 period preset quick-select | [Confirmed] Complete | `docs/replay/p23_replay_ui_period_preset_20260521.md` | 100/500/1000/1500 period presets exist. |
| P24 full strategy universe inventory | [Confirmed] Complete | `docs/replay/p24_full_strategy_universe_inventory_20260521.md` | 59-strategy universe established. |
| P25a browser verification | [Confirmed] Complete | `docs/replay/p25a_full_replay_page_browser_verification_20260521.md` | All 3 lotteries and 8 ONLINE strategies verified in browser. |
| P26 strategy state label module | [Confirmed] Complete | `docs/replay/p26_non_online_strategy_state_labels_20260521.md` | 9 canonical labels exist; pure/read-only source of label truth. |
| P27A console/404 cleanup | [Confirmed] Complete | `docs/replay/p27a_replay_ui_console_404_cleanup_20260521.md` | Wrong-port replay/API issues cleaned up. |
| P28 strategy-catalog API | [Confirmed] Complete and merged | HEAD history `cf80626`; PR #163; `docs/replay/p28_replay_strategy_catalog_label_integration_20260521.md` | `GET /api/replay/strategy-catalog` exposes 59 strategies with P26 labels. |
| P29 catalog UI section | [Confirmed] Complete and merged | HEAD history `8f9b2ce`; PR #164; `docs/replay/p29_replay_strategy_catalog_ui_section_20260521.md` | Replay page shows strategy status overview; non-queryable rows do not trigger replay query. |
| P30 reconstructible-candidacy evaluation | [Confirmed] Complete and merged | HEAD `2b6a657`; PR #165; `docs/replay/p30_reconstructible_candidacy_evaluation_20260521.md` | 51 non-row-backed strategies classified: 24 needs_promotion, 15 manual_review, 12 executable_no. |
| P31A Wave 1 adapter readiness | [Confirmed] Complete and merged | PR #166; `docs/replay/p31a_wave1_daily539_retired_adapter_readiness_20260523.md`; no-db-write; dry-run 7500 rows | Adapters wired, dry-run candidate rows generated, temp DB rehearsal passed, production rows remained 12460. |
| P31B Wave 1 production apply | [Confirmed] Complete and merged | PR #167; HEAD `f6b05e8`; production rows 12460 → 19960; 7500 rows inserted | Controlled apply under `P31B_DAILY539_RETIRED_7500_PROD_20260523`; drift guard PASS; 257 tests passed. |
| P32 Replay UI/API verification post-P31B | [Confirmed] Complete and merged | PR #168; HEAD `e704154`; production rows unchanged at 19960 | All 5 retired DAILY_539 strategies confirmed queryable via API and UI; 126 tests passed. |

---

## 2. Current Production Replay / Catalog Baseline

Verified during P33 CTO review on 2026-05-23 (post P31B + P32).

| Metric | Value |
|---|---:|
| Production replay rows | 19960 |
| Legacy rows | 460 |
| Verified backfill rows (ONLINE strategies, P14D-P21B) | 12000 |
| P31B Wave 1 rows (retired DAILY_539 strategies) | 7500 |
| Row-backed strategies | 13 (8 ONLINE + 5 RETIRED) |
| Full strategy catalog universe | 59 |
| Non-row-backed strategies evaluated in P30 | 51 |
| DB writes in P29/P30/P32/P33 | 0 |
| Migrations in P29-P33 | 0 |
| Baseline before P31B | 12460 |
| P31B Wave 1 rows inserted | 7500 |

Strategy catalog label summary after P31B + P32:

| Label | Count | Queryable | Notes |
|---|---:|---|---|
| `row-backed` | 8 | yes | ONLINE strategies with P14D-P21B backfill |
| `artifact-only` | 41 | no | — |
| `retired` | 5 | no (catalog) | Row-backed via P31B; queryable via `/api/replay/history` with lifecycle filter |
| `rejected-registered` | 4 | no | — |
| `observation` | 1 | no | — |
| `no-data` | 0 | no | — |
| `reconstructible` | 0 | no | — |
| `manual-review` | 0 | no | — |
| `unsupported` | 0 | no | — |

> **Note on retired strategies:** The 5 P31B DAILY_539 retired strategies (`acb_1bet`, `acb_markov_midfreq`, `acb_markov_midfreq_3bet`, `midfreq_acb_2bet`, `midfreq_fourier_2bet`) are replay-backed (1500 rows each) but **remain retired**. They are NOT promoted to ONLINE. The catalog `queryable=False` and `row_count=0` fields reflect P26 label model / P24 static inventory behavior. Live row counts via `/api/replay/history?lifecycle_status=RETIRED` are authoritative (total=7500).

P30 reconstructible-candidacy summary:

| Classification | Count | Meaning |
|---|---:|---|
| `needs_promotion` | 24 | Underlying code exists; thin replay adapter wrapper is needed. |
| `manual_review` | 15 | Human judgment needed before promotion or rejection. |
| `executable_no` | 12 | Rejected, superseded, or no viable implementation path. |

Replay-store row-backed strategy distribution (post P31B):

| Lottery | Strategy | Rows | Lifecycle | Notes |
|---|---|---:|---|---|
| BIG_LOTTO | `biglotto_deviation_2bet` | 1570 | ONLINE | 1500 verified backfill + 70 legacy |
| BIG_LOTTO | `biglotto_triple_strike` | 1570 | ONLINE | 1500 verified backfill + 70 legacy |
| BIG_LOTTO | `ts3_regime_3bet` | 1500 | ONLINE | verified backfill |
| POWER_LOTTO | `fourier_rhythm_3bet` | 1500 | ONLINE | verified backfill |
| POWER_LOTTO | `power_orthogonal_5bet` | 1570 | ONLINE | 1500 verified backfill + 70 legacy |
| POWER_LOTTO | `power_precision_3bet` | 1570 | ONLINE | 1500 verified backfill + 70 legacy |
| DAILY_539 | `daily539_f4cold` | 1590 | ONLINE | 1500 verified backfill + 90 legacy |
| DAILY_539 | `daily539_markov_cold` | 1590 | ONLINE | 1500 verified backfill + 90 legacy |
| DAILY_539 | `acb_1bet` | 1500 | RETIRED (replay-backed) | P31B Wave 1; lifecycle remains retired |
| DAILY_539 | `acb_markov_midfreq` | 1500 | RETIRED (replay-backed) | P31B Wave 1; lifecycle remains retired |
| DAILY_539 | `acb_markov_midfreq_3bet` | 1500 | RETIRED (replay-backed) | P31B Wave 1; lifecycle remains retired |
| DAILY_539 | `midfreq_acb_2bet` | 1500 | RETIRED (replay-backed) | P31B Wave 1; lifecycle remains retired |
| DAILY_539 | `midfreq_fourier_2bet` | 1500 | RETIRED (replay-backed) | P31B Wave 1; lifecycle remains retired |

P31B Wave 1 — completed DAILY_539 retired strategies:

| Strategy | Lifecycle label | Lottery | Rows (P31B) | P32 Verification |
|---|---|---|---:|---|
| `acb_1bet` | RETIRED (replay-backed) | DAILY_539 | 1500 | ✅ API total=1500, UI confirmed |
| `acb_markov_midfreq` | RETIRED (replay-backed) | DAILY_539 | 1500 | ✅ API total=1500, UI confirmed |
| `acb_markov_midfreq_3bet` | RETIRED (replay-backed) | DAILY_539 | 1500 | ✅ API total=1500, UI confirmed |
| `midfreq_acb_2bet` | RETIRED (replay-backed) | DAILY_539 | 1500 | ✅ API total=1500, UI confirmed |
| `midfreq_fourier_2bet` | RETIRED (replay-backed) | DAILY_539 | 1500 | ✅ API total=1500, UI confirmed |

---

## 3. Roadmap Alignment Assessment

| Item | Classification | Assessment |
|---|---|---|
| P29 catalog UI | [Aligned] | Complete and merged. Replay page shows 59-strategy catalog. |
| P30 reconstructible-candidacy evaluation | [Aligned] | Complete and merged. 51 strategies classified. |
| P31A Wave 1 adapter readiness | [Aligned] | Complete and merged (PR #166). 5 strategies wired, 7500 dry-run rows generated, no production DB write. |
| P31B Wave 1 production apply | [Aligned] | Complete and merged (PR #167). Production rows advanced from 12460 to 19960. 257 tests passed. |
| P32 UI/API verification post-P31B | [Aligned] | Complete and merged (PR #168). All 5 retired strategies confirmed queryable. 126 tests passed. |
| Date-range default half-year | [Missing] | P29/P30 observed this UX gap. Now P0 for P34. |
| Retired replay-backed strategy labeling clarity | [Missing] | UI should better distinguish RETIRED replay-backed from ONLINE strategies. Now P0 for P34. |
| Catalog freshness guard | [Drift] | Remains P3; deferred behind P34 UI closure. |
| Incremental replay refresh design | [Drift] | Remains P4; follow P34 UI closure and Wave 2 candidate planning. |
| Wave 2 and manual-review cadence | [Missing] | P31B Wave 1 complete; 19 remaining needs_promotion and 15 manual_review need planning as P1 (P35). |

---

## 4. Reprioritized P0-P10

| Priority | Phase | Focus | Current Status | Acceptance Criteria |
|---|---|---|---|---|
| **P0** | P34 UI usability gap | Date-range default half-year; retired replay-backed strategy labeling clarity in UI/catalog | [Missing] | Replay page defaults to half-year date range; presets still pass smoke; UI clearly distinguishes RETIRED replay-backed rows from ONLINE; no production DB write. |
| **P1** | P35 Wave 2 candidate planning | Rank remaining 19 `needs_promotion` strategies from P30 after Wave 1 evidence | [Not started] | Wave 2 plan: scope, effort, lottery type, expected rows per strategy; no production write. |
| **P2** | P36 Wave 2 dry-run / temp rehearsal | Generate Wave 2 dry-run rows and temp DB rehearsal only | [Not started] | Wave 2 strategies generate dry-run rows; temp DB rehearsal passes; production rows remain 19960; no production DB write. |
| **P3** | Catalog freshness guard | Prevent P24/P28/P29/P30 catalog drift | [Deferred] | Read-only guard compares registry, rejected artifacts, and catalog inventory; no DB writes. |
| **P4** | Incremental replay refresh design | Define future-draw maintenance after Wave 1 coverage | [Deferred] | Design covers cadence, duplicate detection, rollback, and exact write authorization. |
| **P5** | Manual-review strategy resolution | Resolve 15 `manual_review` strategies with a rubric | [Deferred] | Decision rubric separates monitoring frameworks, unclear composites, and true executable candidates. |
| **P6** | Performance and pagination hardening | Keep replay/API/UI practical as rows grow 19960 → 28960+ | [Deferred] | Query and UI remain responsive for period presets and catalog/history flows. |
| **P7** | Apply authorization governance hardening | Formalize multi-wave apply authorization patterns | [Deferred] | Each apply wave requires phase-specific exact YES and post-apply verification. |
| **P8** | Artifact consolidation | Index P21B-P33 docs, outputs, scripts, and test evidence | [Deferred] | One durable reference points to all backfill/catalog/evaluation/apply/verification evidence. |
| **P9** | Post-launch operations | Monitor future draw replay coverage and stale strategy states | [Deferred] | Reports show missing replay rows after new draws and stale strategy catalog states. |
| **P10** | Wave 2 production apply (gated) | Apply Wave 2 rows after P35/P36 pass and explicit apply authorization exists | [Not authorized] | With separate YES gate; rows move to expected total; drift/governance guards pass. |

Items to downgrade, merge, pause, or retire:

| Item | Decision | Reason |
|---|---|---|
| P29 as active blocker | Retired | [Confirmed] P29 merged and verified. |
| P30 read-only evaluation | Retired as active blocker | [Confirmed] P30 merged; output consumed by P31A/P31B. |
| P31A Wave 1 adapter readiness | Retired as active item | [Confirmed] P31A merged (PR #166); no-db-write evidence confirmed. |
| P31B Wave 1 production apply | Retired as active item | [Confirmed] P31B merged (PR #167); 19960 rows; 257 tests passed. |
| P32 UI/API verification | Retired as active item | [Confirmed] P32 merged (PR #168); 126 tests passed; API/UI verified. |
| Catalog freshness before P34 | Downgrade to P3 | CEO direction prioritizes usability closure and Wave 2 planning. |
| Incremental refresh before Wave 2 | Downgrade to P4 | Operating cadence matters after coverage expansion. |
| Broad UI redesign | Pause | CEO wants existing historical prediction-list style. |
| `manual_review=15` in Wave 2 | Downgrade to P5 | Need separate decision rubric; should not enter Wave 2 without human judgment. |
| `executable_no=12` backfill | Retired unless new evidence appears | P30 classified as rejected, superseded, or not viable. |

---

## 5. Critical Blockers

| Blocker | Impact | Why It Blocks | Risk If Ignored | Priority | Acceptance Standard |
|---|---|---|---|---|---|
| Date-range default half-year absent | Replay usability | User explicitly expects a half-year default date range; P29/P32 both observed this gap | Replay page works but misses expected initial UX | P0 (P34) | Replay page defaults to half-year date range while 100/500/1000/1500 presets and pagination still pass browser smoke. |
| Retired replay-backed UI labeling unclear | Catalog/UI trust | RETIRED strategies now have replay rows but are labeled `queryable=False`; operator may be confused | Operator may not realize 7500 retired rows are queryable via lifecycle filter | P0 (P34) | UI or catalog clearly explains that RETIRED replay-backed strategies are queryable via lifecycle filter; no ONLINE relabeling. |
| Wave 2 candidate plan missing | Medium-term coverage | P31B Wave 1 complete; 19 remaining needs_promotion and 15 manual_review strategies have no plan | Coverage expansion stalls at 19960 rows | P1 (P35) | Ranked Wave 2 plan: scope, effort, lottery type, expected rows per strategy; no production write. |
| Wave 2 dry-run / temp rehearsal not done | Data integrity | Cannot apply Wave 2 rows without adapter readiness and rehearsal evidence | Unsafe production write risk | P2 (P36) | Wave 2 strategies generate dry-run rows; temp DB rehearsal passes; production rows remain 19960. |

---

## 6. Most Valuable System Optimization Directions

### Direction A: P34 Replay UI Usability Gap Closure

- **Roadmap phase:** P0
- **Why important:** Wave 1 is now live (19960 rows). The operator must be able to discover and navigate RETIRED replay-backed strategies without confusion. The half-year default is also an expected UX baseline.
- **System maturity gain:** Closes both the date-range default and the retired-vs-ONLINE labeling gap without schema changes.
- **Expected benefit:** Operators land on a sensible 6-month window; can immediately understand that RETIRED strategies are replay-backed and queryable via lifecycle filter.
- **Risk:** Date default can conflict with period preset if implemented carelessly.
- **Acceptance:** Half-year default exists; presets/pagination pass browser smoke; UI labeling does not relabel retired rows as ONLINE; no production DB write.
- **Priority:** P0

### Direction B: P35 Wave 2 Candidate Planning

- **Roadmap phase:** P1
- **Why important:** P31B Wave 1 proved the apply pipeline. Keeping 19 remaining `needs_promotion` strategies without a plan stalls medium-term coverage expansion.
- **System maturity gain:** Extends governance from 5-strategy Wave 1 to ranked multi-lottery Wave 2 candidates.
- **Expected benefit:** Provides a ranked, evidence-backed list for the next apply wave.
- **Risk:** Planning too broadly before P34 UX closure can blur priorities.
- **Acceptance:** Wave 2 list includes scope, effort, lottery type, expected rows; no production write.
- **Priority:** P1

### Direction C: P36 Wave 2 Dry-Run / Temp Rehearsal

- **Roadmap phase:** P2
- **Why important:** The P31A dry-run pattern must be applied again for Wave 2 candidates before any production apply.
- **System maturity gain:** Maintains the same governance pattern: rehearsal before production apply.
- **Expected benefit:** Confirms Wave 2 adapters generate correct rows before any production write.
- **Risk:** Skipping rehearsal risks applying rows with incorrect prediction metadata.
- **Acceptance:** Wave 2 strategies generate dry-run rows; temp DB rehearsal passes; production rows remain 19960; no production DB write.
- **Priority:** P2

### Direction D: Catalog Freshness Guard

- **Roadmap phase:** P3
- **Why important:** P24/P28/P29/P30/P31B have all expanded the catalog and row store; the guard prevents drift.
- **System maturity gain:** Automates the manual cross-check that was done in every CTO review.
- **Expected benefit:** Read-only guard catches catalog/registry divergence early.
- **Risk:** Over-engineering the guard can slow iteration.
- **Acceptance:** Read-only guard; no DB writes; alert on divergence.
- **Priority:** P3

### Direction E: Manual-Review Strategy Resolution

- **Roadmap phase:** P5
- **Why important:** P30 left 15 `manual_review` strategies in a holding state; these need human judgment before Wave 2 or Wave 3 inclusion.
- **System maturity gain:** Converts an open classification into actionable accept/reject decisions.
- **Expected benefit:** Shrinks the unknown pool and clarifies maximum replay coverage ceiling.
- **Risk:** Rushing decisions on complex composites can produce wrong coverage estimates.
- **Acceptance:** Decision rubric separates monitoring frameworks, unclear composites, and true executable candidates.
- **Priority:** P5

---

## 7. Today's Focus

**Recommended focus:** P34 Replay UI Usability Gap Closure.

Expected deliverable:

- Replay page date range defaults to half-year (approximately 6 months back from today).
- UI or catalog panel clearly communicates that RETIRED replay-backed strategies (5 strategies, 7500 rows) are queryable via lifecycle filter, not ONLINE.
- No production DB write.
- All existing replay tests still pass.
- Browser smoke confirms: half-year default displayed, period presets still work, RETIRED lifecycle filter returns 7500 rows.

Do not run production apply in P34.

Final roadmap marker:

```text
CTO_ROADMAP_AFTER_P31B_P32_P33_20260523
```
