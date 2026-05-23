# Lottery Replay Roadmap

**Last Updated:** 2026-05-24 Asia/Taipei (P40 update after P39 — Wave 2 DAILY_539 pipeline complete)
**Owner:** CTO agent
**Primary Goal:** Strategy Historical Replay must become production-usable: the operator can select lottery type, strategy, date range, and 100/500/1000/1500-period presets, then inspect per-draw prediction-vs-actual comparisons in the existing historical prediction-list style. All system-developed strategies must be visible with an honest state: row-backed, artifact-only, retired, rejected-registered, observation, no-data, reconstructible, manual-review, or unsupported. The final product direction is not catalog visibility alone: it is 1500-period replay coverage for all executable strategies, with no fake replay rows and no unguarded production writes.

**CEO Goal:** 1500-period replay × all executable strategies.

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
| P33 Roadmap update after P31B + P32 | [Confirmed] Complete and merged | PR #169; `outputs/replay/p33_roadmap_update_after_p31b_p32_20260523.json` | Roadmap baseline updated to 19960; P34/P35/P36 prioritized. |
| P34 Replay UI usability gap closure | [Confirmed] Complete and merged | PR #170; `outputs/replay/p34_replay_ui_usability_gap_closure_20260523.json` | Half-year date default + RETIRED labeling clarity; no production DB write. |
| P35 Wave 2 candidate planning | [Confirmed] Complete and merged | PR #171; `outputs/replay/p35_wave2_candidate_planning_20260523.json` | 19 remaining needs_promotion evaluated; 6 DAILY_539 selected for Wave 2. |
| P36 Wave 2 DAILY_539 dry-run + temp rehearsal | [Confirmed] Complete and merged | PR #172; `outputs/replay/p36_wave2_daily539_dryrun_rehearsal_20260523.json` | 9000 dry-run rows; R1/R2/R3 temp rehearsal PASS; production rows remained 19960. |
| P37 Wave 2 DAILY_539 production apply | [Confirmed] Complete and merged | PR #173; `outputs/replay/p37_wave2_daily539_production_apply_20260523.json`; production rows 19960 → 28960; 9000 rows inserted | Controlled apply under `P37_DAILY539_WAVE2_9000_PROD_20260523`; drift guard PASS; lifecycle DRY_RUN. |
| P38 Post-P37 verification + freshness registry audit | [Confirmed] Complete and merged | PR #174; `outputs/replay/p38_post_p37_verification_registry_audit_20260523.json` | P37 rows verified; strategy_replay_runs ids 8-10 ACCEPTED; API verified; no production DB change. |
| P39 Replay UI smoke closure after P38 | [Confirmed] Complete and merged | PR #175; `outputs/replay/p39_replay_ui_smoke_closure_after_p38_20260523.json`; merge commit 2558f00 | P38 deferred UI smoke RESOLVED; 0 console errors; all Wave 2 strategies queryable; 28960 rows confirmed. |

---

## 2. Current Production Replay / Catalog Baseline

Verified during P40 CTO review on 2026-05-24 (post P39 — Wave 2 DAILY_539 complete).

## Replay Coverage Baseline (as of 2026-05-24)

| Milestone | Rows | Cumulative |
|---|---:|---:|
| Pre-Wave-1 baseline (ONLINE strategies, P14D-P21B) | 12460 | 12460 |
| P31B Wave 1 retired DAILY_539 (+7500 rows) | 7500 | 19960 |
| P37 Wave 2 DAILY_539 DRY_RUN (+9000 rows) | 9000 | 28960 |
| **Current total** | — | **28960** |

> **Note on Wave 2 DRY_RUN strategies:** Wave 2 strategies (`lifecycle_status=DRY_RUN`) are not shown in the strategy selector dropdown. They are visible and queryable in the replay table via the `lottery_type=DAILY_539` filter. This is accepted current behavior pending live monitoring evidence for DRY_RUN → ONLINE promotion.

| Metric | Value |
|---|---:|
| Production replay rows | 28960 |
| Legacy rows | 460 |
| Verified backfill rows (ONLINE strategies, P14D-P21B) | 12000 |
| P31B Wave 1 rows (retired DAILY_539 strategies) | 7500 |
| P37 Wave 2 rows (DRY_RUN DAILY_539 strategies) | 9000 |
| Row-backed strategies | 19 (8 ONLINE + 5 RETIRED + 6 DRY_RUN) |
| Full strategy catalog universe | 59 |
| Non-row-backed strategies evaluated in P30 | 51 |
| DB writes in P33-P40 roadmap/docs-only phases | 0 |
| Baseline before P31B | 12460 |
| Baseline before P37 | 19960 |
| P31B Wave 1 rows inserted | 7500 |
| P37 Wave 2 rows inserted | 9000 |

Strategy catalog label summary after P37 + P38 + P39:

| Label | Count | Queryable | Notes |
|---|---:|---|---|
| `row-backed` | 8 | yes | ONLINE strategies with P14D-P21B backfill |
| `artifact-only` | 41 | no | — |
| `retired` | 5 | no (catalog) | Row-backed via P31B; queryable via `/api/replay/history` with lifecycle filter |
| `dry-run` | 6 | no (catalog dropdown) | Row-backed via P37; queryable via `/api/replay/history?lottery_type=DAILY_539` |
| `rejected-registered` | 4 | no | — |
| `observation` | 1 | no | — |
| `no-data` | 0 | no | — |
| `reconstructible` | 0 | no | — |
| `manual-review` | 0 | no | — |
| `unsupported` | 0 | no | — |

> **Note on retired strategies:** The 5 P31B DAILY_539 retired strategies (`acb_1bet`, `acb_markov_midfreq`, `acb_markov_midfreq_3bet`, `midfreq_acb_2bet`, `midfreq_fourier_2bet`) are replay-backed (1500 rows each) but **remain retired**. They are NOT promoted to ONLINE. The catalog `queryable=False` and `row_count=0` fields reflect P26 label model / P24 static inventory behavior. Live row counts via `/api/replay/history?lifecycle_status=RETIRED` are authoritative (total=7500).

> **Note on Wave 2 DRY_RUN strategies:** The 6 P37 DAILY_539 DRY_RUN strategies (`acb_single_539`, `539_3bet_orthogonal`, `markov_1bet_539`, `zone_gap_3bet_539`, `p0b_539_3bet_f_cold_fmid`, `p0c_539_3bet_f_cold_x2`) are replay-backed (1500 rows each, total=9000). They are NOT in the strategy dropdown (controlled by `_REGISTRY`). Queryable via `/api/replay/history?lottery_type=DAILY_539`. DRY_RUN → ONLINE promotion requires live monitoring evidence (200+ draws). This is accepted current behavior.

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

P37 Wave 2 — completed DAILY_539 DRY_RUN strategies:

| Strategy | Lifecycle label | Lottery | Rows (P37) | P38+P39 Verification |
|---|---|---|---:|---|
| `acb_single_539` | DRY_RUN | DAILY_539 | 1500 | ✅ API total=1500, UI queryable |
| `539_3bet_orthogonal` | DRY_RUN | DAILY_539 | 1500 | ✅ API total=1500, UI queryable |
| `markov_1bet_539` | DRY_RUN | DAILY_539 | 1500 | ✅ API total=1500, UI queryable |
| `zone_gap_3bet_539` | DRY_RUN | DAILY_539 | 1500 | ✅ API total=1500, UI queryable |
| `p0b_539_3bet_f_cold_fmid` | DRY_RUN | DAILY_539 | 1500 | ✅ API total=1500, UI queryable |
| `p0c_539_3bet_f_cold_x2` | DRY_RUN | DAILY_539 | 1500 | ✅ API total=1500, UI queryable |

---

## 3. Roadmap Alignment Assessment

| Item | Classification | Assessment |
|---|---|---|
| P29 catalog UI | [Aligned] | Complete and merged. Replay page shows 59-strategy catalog. |
| P30 reconstructible-candidacy evaluation | [Aligned] | Complete and merged. 51 strategies classified. |
| P31A Wave 1 adapter readiness | [Aligned] | Complete and merged (PR #166). 5 strategies wired, 7500 dry-run rows generated, no production DB write. |
| P31B Wave 1 production apply | [Aligned] | Complete and merged (PR #167). Production rows advanced from 12460 to 19960. 257 tests passed. |
| P32 UI/API verification post-P31B | [Aligned] | Complete and merged (PR #168). All 5 retired strategies confirmed queryable. 126 tests passed. |
| P33 Roadmap update after P31B+P32 | [Aligned] | Complete and merged. Baseline updated; P34-P36 prioritized. |
| P34 Replay UI usability gap | [Aligned] | Complete and merged. Half-year default + RETIRED labeling clarity shipped. |
| P35 Wave 2 candidate planning | [Aligned] | Complete and merged (PR #171). 19 remaining strategies evaluated; 6 DAILY_539 selected. |
| P36 Wave 2 DAILY_539 dry-run + rehearsal | [Aligned] | Complete and merged (PR #172). 9000 dry-run rows; R1/R2/R3 rehearsal PASS. |
| P37 Wave 2 DAILY_539 production apply | [Aligned] | Complete and merged (PR #173). 19960 → 28960 rows; lifecycle DRY_RUN; drift guard PASS. |
| P38 Post-P37 verification + registry audit | [Aligned] | Complete and merged (PR #174). 9000 rows verified; ids 8-10 ACCEPTED operational updates. |
| P39 Replay UI smoke closure | [Aligned] | Complete and merged (PR #175; commit 2558f00). P38 deferred UI smoke RESOLVED; 0 console errors. |
| Wave 3 BIG_LOTTO adapter bootstrap | [Missing] | 6 LOW-effort + 5 MEDIUM-effort BIG_LOTTO strategies deferred; adapter bootstrap needed. Now P0 for P41. |
| Wave 2 DRY_RUN monitoring design | [Missing] | DRY_RUN → ONLINE promotion criteria not defined. Now P2 for P43. |
| Catalog freshness guard | [Drift] | Remains P3; deferred behind Wave 3 bootstrap. |
| Manual-review strategy resolution | [Drift] | Remains P5; 15 strategies in holding state. |

---

## 4. Reprioritized P0-P9+ (Updated 2026-05-24)

| Priority | Phase | Focus | Current Status | Acceptance Criteria |
|---|---|---|---|---|
| **P0** | P41 Wave 3 BIG_LOTTO adapter bootstrap planning | Plan adapter bootstrap for 6 LOW-effort BIG_LOTTO strategies before any dry-run | [Not started] | Wave 3 plan produced; adapter bootstrap design complete; no production DB write. |
| **P1** | P42 Wave 3 BIG_LOTTO dry-run + temp rehearsal | Generate Wave 3 BIG_LOTTO dry-run rows and temp DB rehearsal | [Not started] | Wave 3 strategies generate dry-run rows; rehearsal passes; production rows remain 28960; no production DB write. |
| **P2** | P43 Wave 2 live monitoring design | Define DRY_RUN → ONLINE promotion criteria for Wave 2 strategies after 200+ draws | [Not started] | Promotion criteria defined: edge stability over 200 draws + McNemar gate; no production write. |
| **P3** | P44 Freshness cadence guard improvement | Auto-insert DONE records in cadence guard; reduce manual fix burden | [Deferred] | Read-only guard with auto-insert; no DB writes to strategy rows. |
| **P4** | P45 POWER_LOTTO expansion planning | Extend replay coverage to POWER_LOTTO remaining strategies | [Deferred] | POWER_LOTTO adapter complexity assessed; Wave plan produced. |
| **P5** | P46 Manual-review strategy resolution | Resolve 15 `manual_review` strategies with a decision rubric | [Deferred] | Decision rubric separates monitoring frameworks, unclear composites, and true executable candidates. |
| **P6** | P47 Replay performance / pagination hardening | Keep replay/API/UI practical as rows grow toward 37960+ | [Deferred] | Query and UI remain responsive for period presets and catalog/history flows. |
| **P7** | P48 Apply authorization governance hardening | Formalize multi-wave apply authorization patterns | [Deferred] | Each apply wave requires phase-specific exact YES and post-apply verification. |
| **P8** | P49 Artifact consolidation | Index P21B-P40 docs, outputs, scripts, and test evidence | [Deferred] | One durable reference points to all backfill/catalog/evaluation/apply/verification evidence. |
| **P9** | Post-launch operations | Monitor future draw replay coverage and stale strategy states | [Deferred] | Reports show missing replay rows after new draws and stale strategy catalog states. |

Items completed and retired as active items (P40 update):

| Item | Decision | Reason |
|---|---|---|
| P34 UI usability gap | Retired as active item | [Confirmed] Complete and merged; half-year default + RETIRED labeling shipped. |
| P35 Wave 2 candidate planning | Retired as active item | [Confirmed] Complete and merged (PR #171); 6 DAILY_539 strategies selected. |
| P36 Wave 2 DAILY_539 dry-run | Retired as active item | [Confirmed] Complete and merged (PR #172); 9000 dry-run rows; rehearsal PASS. |
| P37 Wave 2 production apply | Retired as active item | [Confirmed] Complete and merged (PR #173); 19960 → 28960 rows. |
| P38 Post-P37 verification | Retired as active item | [Confirmed] Complete and merged (PR #174); rows verified; ids 8-10 ACCEPTED. |
| P39 UI smoke closure | Retired as active item | [Confirmed] Complete and merged (PR #175); 0 console errors; all Wave 2 strategies queryable. |
| Wave 2 production apply (was P10) | Completed | P37 executed Wave 2 apply under governance; retired as active item. |
| Incremental refresh before monitoring design | Downgrade to P3/P4 | Operating cadence matters after coverage expansion. |
| Broad UI redesign | Pause | CEO wants existing historical prediction-list style. |
| `manual_review=15` in Wave 2 | Downgrade to P5 | Need separate decision rubric; should not enter Wave 3 without human judgment. |
| `executable_no=12` backfill | Retired unless new evidence appears | P30 classified as rejected, superseded, or not viable. |

---

## 5. Critical Blockers (Updated 2026-05-24)

All previous P0/P1/P2 blockers (P34/P35/P36/P37/P38/P39) are resolved. New blockers:

| Blocker | Impact | Why It Blocks | Risk If Ignored | Priority | Acceptance Standard |
|---|---|---|---|---|---|
| Wave 3 BIG_LOTTO adapter bootstrap missing | Coverage expansion | 6 LOW-effort + 5 MEDIUM-effort BIG_LOTTO strategies have no adapter; cannot generate replay rows | Coverage stalls at 28960 rows with no BIG_LOTTO Wave 3 path | P0 (P41) | Adapter bootstrap design complete; at least one BIG_LOTTO strategy generates dry-run rows; no production write. |
| DRY_RUN → ONLINE promotion criteria undefined | Strategy lifecycle governance | 6 Wave 2 DRY_RUN strategies are live in production but have no defined promotion path | Strategies remain DRY_RUN indefinitely; operator cannot trust live monitoring signal | P2 (P43) | Promotion criteria defined: edge stability threshold, McNemar gate, minimum 200 draws. |
| BIG_LOTTO Wave 3 dry-run not done | Data integrity | Cannot apply Wave 3 rows without adapter readiness and rehearsal evidence | Unsafe production write risk | P1 (P42) | Wave 3 BIG_LOTTO strategies generate dry-run rows; temp DB rehearsal passes; production rows remain 28960. |

---

## 6. Most Valuable System Optimization Directions (Updated 2026-05-24)

### Direction A: P41 Wave 3 BIG_LOTTO Adapter Bootstrap Planning

- **Roadmap phase:** P0
- **Why important:** Wave 2 DAILY_539 is complete (28960 rows). BIG_LOTTO expansion requires adapter bootstrap before any dry-run.
- **System maturity gain:** Extends governance from DAILY_539 to BIG_LOTTO; unblocks 11 deferred strategies.
- **Expected benefit:** Blueprint for Wave 3 apply wave; adapter interface standardization.
- **Risk:** BIG_LOTTO pool size (49C6) means low edge per strategy; adapter complexity may be higher than DAILY_539.
- **Acceptance:** Adapter bootstrap design complete; no-db-write; BIG_LOTTO strategies catalogued with effort/risk estimate.
- **Priority:** P0

### Direction B: P42 Wave 3 BIG_LOTTO Dry-Run + Temp Rehearsal

- **Roadmap phase:** P1
- **Why important:** The P31A/P36 governance pattern must be applied to BIG_LOTTO before any production apply.
- **System maturity gain:** Extends the rehearsal-before-apply governance to a second lottery type.
- **Expected benefit:** Confirms Wave 3 BIG_LOTTO adapters generate correct rows; catches issues before production.
- **Risk:** Skipping rehearsal risks applying rows with incorrect prediction metadata.
- **Acceptance:** Wave 3 dry-run rows generated; temp DB rehearsal passes; production rows remain 28960.
- **Priority:** P1

### Direction C: P43 Wave 2 Live Monitoring Design

- **Roadmap phase:** P2
- **Why important:** 6 Wave 2 DRY_RUN strategies are in production (9000 rows) but have no defined promotion criteria.
- **System maturity gain:** Creates a clear DRY_RUN → ONLINE promotion ladder with quantitative gates.
- **Expected benefit:** Operators have a defined path for promoting DRY_RUN strategies if evidence warrants.
- **Risk:** Setting criteria too loose could promote underperforming strategies; too strict could stall promotion indefinitely.
- **Acceptance:** Promotion criteria documented: edge stability over 200+ draws, McNemar gate, no adverse PSI signals.
- **Priority:** P2

### Direction D: P44 Freshness Cadence Guard Improvement

- **Roadmap phase:** P3
- **Why important:** P38 registry ids 8-10 required manual insertion; auto-insert would reduce toil.
- **System maturity gain:** Automates cadence guard DONE record creation; reduces manual fix burden each wave.
- **Expected benefit:** Guard auto-inserts DONE records when all strategies in scope have been refreshed.
- **Risk:** Auto-insert could mask underlying data freshness issues.
- **Acceptance:** Read-only guard improved; auto-insert documented; no DB writes to strategy rows.
- **Priority:** P3

### Direction E: P46 Manual-Review Strategy Resolution

- **Roadmap phase:** P5
- **Why important:** P30 left 15 `manual_review` strategies in a holding state; these need human judgment before Wave 3 or Wave 4 inclusion.
- **System maturity gain:** Converts an open classification into actionable accept/reject decisions.
- **Expected benefit:** Shrinks the unknown pool and clarifies maximum replay coverage ceiling.
- **Risk:** Rushing decisions on complex composites can produce wrong coverage estimates.
- **Acceptance:** Decision rubric separates monitoring frameworks, unclear composites, and true executable candidates.
- **Priority:** P5

---

## 7. Today's Focus (Updated 2026-05-24)

**Recommended focus:** P41 Wave 3 BIG_LOTTO Adapter Bootstrap Planning.

Expected deliverable:

- Wave 3 adapter bootstrap design document produced.
- At least one BIG_LOTTO strategy classified with effort/risk/expected rows estimate.
- No production DB write.
- No lifecycle promotion.
- All existing replay tests still pass.

Do not apply Wave 3 rows without completing P41 (planning) and P42 (dry-run + rehearsal) first.
Do not promote Wave 2 DRY_RUN strategies to ONLINE without P43 monitoring evidence (200+ draws).

Final roadmap marker:

```text
CTO_ROADMAP_AFTER_P35_P36_P37_P38_P39_P40_20260524
```
