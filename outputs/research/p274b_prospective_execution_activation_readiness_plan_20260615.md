# P274B Prospective Execution and Activation Readiness Plan

- **Task:** `P274B_PROSPECTIVE_EXECUTION_ACTIVATION_READINESS_PLAN`
- **Mode:** design and readiness assessment only
- **Source commit:** `6d3c6f8ebda45e88f4ae7ae93bd8fcd7ae41a753`
- **Canonical payload digest:** `bf8ae32f8dbd208da4939ee46cdbe19125827f36c3a80aedefc8fee21a994744`
- **Final classification:** `P274B_PROSPECTIVE_EXECUTION_ACTIVATION_READINESS_PLAN_COMPLETE`

> This plan authorizes no implementation, production DB access, deployment, controlled apply, activation, boundary assignment, prospective capture, registry/recommendation mutation, P273B, predictive-success claim, betting advice, or merge.

## Executive Readiness Verdict

- Current position: **G1_PARTIAL_PENDING_OWNER_APPROVAL**; highest fully complete gate: **G0**.
- Implementation: **NOT_READY_FOR_IMPLEMENTATION_AUTHORIZATION**.
- Activation: **NOT_READY_FOR_ACTIVATION** and not authorized.
- Overall: **HOLD_RECOMMENDED**.
- Recommended next gate: **G1_OWNER_REVIEW_AND_DECISION**. Review and approve or reject the architecture, resolve owner decision points, then issue a separately scoped G2 authorization only if the evidence becomes complete.

The evidence supports a frozen protocol and a tested isolated ledger library, not an operational prospective system. Production prospective schema state is `ABSENT_CLEAN`; runtime capture, authoritative schedule resolution, trusted time, monitoring, access control, retention, recovery, audit export, and the frozen prospective evaluator are incomplete.

## Immutable P274A Contract

P274A digest `f2294716699368a9c2b21fb14301d84d70f662b882aef9eab896f96825f18ffc` was independently recomputed twice with its documented Python canonicalizer. State Marker remains `P271L_PREFLIGHT_COMPLETE_NOT_READY_FOR_APPLY`; production apply remains `NOT_READY_FOR_APPLY`; boundary values remain `UNSET_PENDING_SEPARATE_ACTIVATION_AUTHORIZATION`.

| Candidate | Lottery | Expected distinct N | H80 | H90 |
|---|---|---:|---:|---:|
| acb_markov_midfreq_3bet | DAILY_539 | 3 | 2730 | 3605 |
| daily539_f4cold_3bet | DAILY_539 | 3 | 1986 | 2612 |
| daily539_f4cold_5bet | DAILY_539 | 5 | 695 | 915 |

Common final horizon: **3605 future draws**. Bonferroni m=3, per-candidate alpha=0.0166666666666667. Draw count governs; approximately 11.5 years is descriptive only. The 50-draw checkpoint is integrity/data-quality only; 300 draws permits non-binding futility only; there is no interim efficacy or optional final extension.

## Readiness Ladder

| Gate | Status | Exit criterion | Next authorization |
|---|---|---|---|
| G0 Protocol And Governance Frozen | CONFIRMED | Immutable facts match and concrete boundary remains unset | G1 design review |
| G1 Execution Architecture Design Approved | PARTIAL | Owner explicitly approves architecture and resolves required operating decisions | Separate G2 implementation authorization |
| G2 Implementation Authorization | MISSING | Authorization names components, files, environments and forbidden actions | G3 implementation tasks, each separately scoped |
| G3 Implementation And Isolated Validation Complete | PARTIAL | All required components implemented and isolated tests, restart, fault and security evidence pass | G4 production-safety preflight authorization |
| G4 Production-Safety Preflight Complete | PARTIAL | All apply-time blockers cleared and post-apply verification plan approved | Separate production apply authorization, then P271M verification |
| G5 Activation Authorization | MISSING | Owner authorizes a separate boundary-assignment task | G6 boundary assignment authorization |
| G6 Boundary Assignment | MISSING | Boundary sealed, exported and independently verified | G7 capture-start authorization |
| G7 Prospective Capture Start | MISSING | Each eligible draw is handled prospectively and evidence remains auditable | Continue under monitoring; no efficacy authorization |
| G8 Monitoring And Final Analysis | MISSING | Protocol closes with governed candidate/project classes | Any production promotion is a separate future gate |

No gate promotes automatically. G5 and later are neither complete nor authorized.

## P271 Evidence Inventory

| ID | Component | Status | Current evidence | Missing before activation |
|---|---|---|---|---|
| P271-01 | Prospective boundary and preregistration | CONFIRMED | Design contract is committed; strict outcome blindness was not claimed because prior P271F outcomes were exposed. | Concrete P274A activation boundary remains unset. |
| P271-02 | Ledger architecture design | CONFIRMED | Design is committed with transaction, causality, uniqueness and failure contracts. | Broader operating model, ownership, access, retention and monitoring were not completed. |
| P271-03 | Isolated ledger module | CONFIRMED | Implemented and tested only as an isolated library; no route, scheduler, network, DB path or production wiring. | P274A-specific field mapping and runtime integration are absent. |
| P271-04 | Temporary DB migration rehearsal | CONFIRMED | Temporary SQLite rehearsal passed; source-grounded legacy fixture only. | Production concurrency, full schema, WAL behavior, backup and restore remain unproven. |
| P271-05 | Production deployment preflight | PARTIAL | Preflight package exists but is explicitly NOT_READY_FOR_APPLY. | Fresh apply-time hash, maintenance window, writer shutdown, backup and WAL/SHM reconciliation. |
| P271-06 | Production schema inspection | CONFIRMED | Historical read-only inspection found ABSENT_CLEAN; table/column presence only, not full schema equivalence. | Apply-time state must be reverified; this task did not reopen the DB. |
| P271-07 | Canonical ticket normalization and fingerprinting | PARTIAL | Main numbers are sorted and payload_hash/ledger_id are deterministic. | P274A candidate_id, canonical ticket identity list, cross-ticket distinct-count proof and explicit ticket_fingerprint fields are not fully represented. |
| P271-08 | Append-only and immutability guarantees | PARTIAL | DB triggers cover all five prospective data tables in isolated schema. | No external digest anchor, WORM copy or production enforcement evidence. |
| P271-09 | Capture-before-outcome enforcement | PARTIAL | Strict inequality and explicit skew margin are implemented on caller-supplied values; capture imports no result path. | No authoritative resolver, trusted clock, drift monitor or outcome-availability oracle. |
| P271-10 | Official target-draw identity | PARTIAL | target_draw is persisted and unique within activation. | Official exception-aware resolver and source verification are missing. |
| P271-11 | Strategy and candidate version pinning | PARTIAL | capture_batch accepts a caller-supplied known_strategy_versions set. | Immutable candidate manifest, source digest mapping and candidate_id persistence are missing. |
| P271-12 | Scorer and endpoint version pinning | MISSING | P271J deliberately does not import the scorer and has no scorer_endpoint_version column. | Schema/data contract and immutable endpoint digest mapping are absent. |
| P271-13 | Activation identity and lifecycle | PARTIAL | Synthetic activation APIs and event-derived active state exist. | Owner-authorized G5/G6 workflow, real boundary fields and production evidence are absent. |
| P271-14 | Outcome availability tracking | MISSING | An outcome-link table schema exists, but no public append API or availability-state workflow exists. | Outcome availability status, trusted publication source and ingestion API are missing. |
| P271-15 | Result-ingestion separation | PARTIAL | Separate table is designed; capture never reads or writes results. | Result linker, authorization, idempotency and provenance implementation are missing. |
| P271-16 | Missing and late record handling | MISSING | No operational policy or threshold is implemented. | Maximum tolerated gaps and pause/invalidation thresholds are OWNER_DECISION_REQUIRED. |
| P271-17 | Duplicate detection and idempotency | CONFIRMED | Derived primary key plus semantic unique index; atomic failure and rejection event. | Production behavior remains unverified until installation and preflight. |
| P271-18 | Structured provenance and source trace | PARTIAL | Events have actor/service/code/transaction/hash; ticket source_provenance is only a non-empty string. | Structured provenance schema, candidate manifest digest and official source response digest enforcement are incomplete. |
| P271-19 | Operational scheduling | MISSING | No route, scheduler, capture worker or network integration exists. | Disabled-by-default one-shot worker, scheduler policy and deployment evidence are missing. |
| P271-20 | Restart and recovery behavior | MISSING | Transaction rollback is tested, but runtime restart recovery is not designed or exercised. | Checkpointing, retry-before-close, crash reconciliation and operator runbook are missing. |
| P271-21 | Monitoring and alerting | MISSING | No prospective monitor or alert interface is committed. | Metrics, alert routes, escalation owner and thresholds are OWNER_DECISION_REQUIRED. |
| P271-22 | Audit export | PARTIAL | Read-only list/get/hash helpers exist. | Canonical export schema, signed manifest, batch digest and independent verification tool are missing. |
| P271-23 | Access control | MISSING | Library accepts actor strings but performs no authentication or authorization. | Role model, credential ownership, least privilege and incident response are missing. |
| P271-24 | Trusted clock and drift control | MISSING | Explicit timezone-aware timestamps and caller-supplied margin are validated. | Clock source, synchronization telemetry, maximum drift and outage behavior are OWNER_DECISION_REQUIRED. |
| P271-25 | Retention and archival | MISSING | No retention, archive or legal/operational ownership contract exists. | Retention duration, archive format, restore tests and deletion authority are OWNER_DECISION_REQUIRED. |
| P271-26 | Maintenance ownership | MISSING | No named service owner, on-call rotation or handoff process is committed. | Primary/backup owner, succession, budget and periodic review cadence are OWNER_DECISION_REQUIRED. |
| P271-27 | Correction and amendment policy | PARTIAL | Append-only pre-close amendments are supported; post-close and identity-changing amendments are rejected. | Operational approval workflow and classification of permissible pre-close corrections are missing. |
| P271-28 | Evidence digesting and tamper detection | PARTIAL | Per-ticket payload hashes are implemented. | No batch Merkle/digest chain, external anchor, signing key or periodic audit exists. |
| P271-29 | Evaluation and final-analysis implementation | MISSING | Statistical protocol is designed but no prospective evaluator is implemented. | Outcome linker, evaluator, conditional-power calculation and frozen analysis package are missing. |
| P271-30 | Secrets or signing-key ownership | NOT_APPLICABLE | Current P271 design uses no secrets or signatures. | If signing is chosen, key custody, rotation and revocation become OWNER_DECISION_REQUIRED. |

Inventory counts: CONFIRMED=6, PARTIAL=12, MISSING=11, CONFLICT=0, NOT_APPLICABLE=1, UNKNOWN=0.

P271J is real implementation evidence, but only for a caller-supplied isolated SQLite library. P271K is rehearsal evidence, not production readiness. P271L is preflight/inspection evidence, not apply or activation authorization.

## Execution Architecture

| Component | Status | Responsibility |
|---|---|---|
| A1 Frozen candidate manifest | MISSING | Map C1-C3 to exact strategy source digests, versions, expected ticket counts and scorer endpoint digest. |
| A2 Prediction producer adapter | MISSING | Invoke frozen candidate versions without result access and return normalized ticket payloads. |
| A3 Official draw identity and close resolver | MISSING | Resolve target draw, scheduled close, source version and exceptions in Asia/Taipei then UTC. |
| A4 Trusted time service | MISSING | Provide capture time, drift telemetry and fail-closed trust state. |
| A5 Normalization and fingerprint service | PARTIAL | Sort/validate ticket numbers, map bet indexes, compute distinct tickets and deterministic fingerprints. |
| A6 Append-only evidence writer | CONFIRMED | Atomically write activation, batch, ticket and event records with uniqueness and tamper evidence. |
| A7 Evidence seal and audit exporter | PARTIAL | Create canonical draw/batch manifests, digest them and export independently verifiable evidence. |
| A8 Outcome availability and result linker | MISSING | Track publication separately and append result links only after official completion. |
| A9 Prospective evaluator | MISSING | Read only sealed prospective records and enforce 50/300/3605 rules with m=3. |
| A10 Monitoring and operations plane | MISSING | Observe schedules, capture latency, gaps, drift, duplicates, storage, digests and operator coverage. |

**Pre-outcome sequence:**
1. Load sealed activation and candidate manifests
2. Resolve official target draw and close time from a verified versioned source
3. Verify trusted clock and drift state
4. Generate predictions from frozen versions without outcome access
5. Normalize tickets and compute distinct-ticket identities/fingerprints
6. Validate candidate/scorer/source versions and strict pre-close causality
7. Atomically append batch, ticket and event evidence
8. Seal and export a canonical batch digest before outcome availability
9. Only then mark capture complete for monitoring

Prediction capture, outcome availability/result linkage, and evaluation are separate planes. No recovery rule permits retrospective backfill. Candidate and family membership never shrink because of unavailability or retirement.

### Storage Decision Options

- **Existing P271J SQLite append-only schema:** advantages: Already implemented and temp-DB tested; Strong local transaction and uniqueness semantics. Risks: Production DB coupling; No external immutability anchor; Access and long-horizon migration not designed. **OWNER_DECISION_REQUIRED**.
- **Separate append-only evidence database or object store:** advantages: Isolation from production operational DB; Independent retention and access policy. Risks: New technology, deployment and migration scope; Needs transaction/idempotency design. **OWNER_DECISION_REQUIRED**.
- **Dual evidence: transactional ledger plus WORM/signed export:** advantages: Operational writes plus independent tamper evidence; Stronger migration resilience. Risks: Highest complexity and key/retention ownership. **OWNER_DECISION_REQUIRED**.

## Prospective Capture Requirements

| ID | Status | Required by | Requirement |
|---|---|---|---|
| PCR-01 | PARTIAL | G3 | Persist protocol_version and activation_id |
| PCR-02 | MISSING | G3 | Persist candidate_id and immutable candidate manifest digest |
| PCR-03 | PARTIAL | G3 | Persist lottery_type, official target_draw and official scheduled timestamp |
| PCR-04 | PARTIAL | G3 | Persist strategy_id and exact strategy_version/source digest |
| PCR-05 | MISSING | G3 | Persist scorer_endpoint_version/digest |
| PCR-06 | PARTIAL | G3 | Persist normalized canonical ticket identities, bet indexes and distinct_ticket_count |
| PCR-07 | PARTIAL | G3 | Persist deterministic ticket fingerprints and batch digest |
| PCR-08 | MISSING | G3 | Use trusted capture timestamp with drift evidence |
| PCR-09 | PARTIAL | G3 | Enforce capture before outcome availability |
| PCR-10 | PARTIAL | G4 | Append-only DB enforcement and tamper detection |
| PCR-11 | CONFIRMED | G3 | Atomic idempotent capture and duplicate protection |
| PCR-12 | PARTIAL | G3 | Separate outcome availability, result ingestion and evaluation |
| PCR-13 | CONFIRMED | G0 | No retrospective backfill or family replacement |
| PCR-14 | MISSING | G3 | Restart recovery without post-outcome retry |
| PCR-15 | MISSING | G4 | Monitoring, alerting and operator escalation |
| PCR-16 | MISSING | G3 | Canonical audit export with reload/digest verification |
| PCR-17 | MISSING | G4 | Role-based access and audited manual operations |
| PCR-18 | MISSING | G4 | Retention, archival, backup and restore across migrations |
| PCR-19 | MISSING | G3 | Frozen prospective evaluator for 50/300/final rules |
| PCR-20 | MISSING | G6 | Activation boundary sealed before any eligible outcome |

## Operational Readiness and Long-Horizon Sustainability

The protocol governs 3605 draws, not an exact calendar duration. approximately 11.5 years assumes the historical regular cadence and can change.

**Minimum ongoing commitments:**
- Named primary and backup service owners
- Documented on-call and escalation coverage for every scheduled draw
- Verified schedule-source refresh and exception handling
- Trusted-clock health and drift monitoring
- Pre-draw capture health check and post-capture evidence seal verification
- Daily/weekly audit of missing, duplicate, late and digest-mismatch events
- Regular backup and restore rehearsal
- Dependency, credential and security patch maintenance
- Periodic owner-approved protocol ownership and scientific-value review
- Immutable handoff package for staff or agent transitions

**Maximum tolerated capture gaps:** OWNER_DECISION_REQUIRED. P274A freezes no numerical missingness threshold. A threshold must be pre-registered with statistical sensitivity before activation.

| Long-horizon area | Status | Required mitigation |
|---|---|---|
| Maintenance ownership | MISSING | Named primary/backup owner, succession plan and owner-approved periodic review. |
| Staff or agent handoff | MISSING | Versioned runbook, architecture decision record, credential map and signed handoff checklist. |
| Strategy dependency drift | PARTIAL | Frozen source/container digest and reproducible build; no silent upgrade. |
| Scorer drift | MISSING | Persist endpoint digest and run compatibility fixtures before every release. |
| Lottery-rule change | UNKNOWN | Pause immediately; owner decides invalidation, new protocol or closure. |
| Draw-calendar change | UNKNOWN | Versioned official schedule resolver; draw count remains governing. |
| Infrastructure migration | MISSING | Dual-read verification, digest reconciliation and separate owner authorization. |
| Credential rotation | MISSING | Rotation runbook and overlap test; no missed capture during rotation. |
| Backup and restore | PARTIAL | P271L plan exists; production restore rehearsal and recurring cadence absent. |
| Evidence durability | PARTIAL | Append-only local design plus independent archive/digest anchor decision. |
| Monitoring fatigue | MISSING | Actionable alerts, escalation tiers and periodic alert-quality review. |
| Extended outage | MISSING | No backfill; classify gaps, pause, and trigger owner reauthorization/closure. |
| Candidate retirement | MISSING | Retirement never shrinks m=3; affected candidate closes per governed class. |
| Cost and resources | UNKNOWN | Budget storage, monitoring, maintenance, audits, migrations, security and independent review. |
| Scientific value decay | UNKNOWN | Annual review may recommend continue, HOLD or scientific closure without peeking for efficacy. |

Temporary suspension is allowed for safety; missed draws remain missing. Permanent invalidation is required when timing, identity, boundary or evidence integrity cannot be proven. Candidate retirement does not shrink m=3 and cannot introduce a replacement.

## Failure-Mode Matrix

| ID | Failure | Severity | Immediate safe action | Record validity | Invalidated? |
|---|---|---|---|---|---|
| FM-01 | Outcome known before capture | CRITICAL | Reject record, freeze candidate/family and preserve incident evidence | Affected record invalid | YES if exposure scope cannot be isolated |
| FM-02 | Clock drift | CRITICAL | Fail closed before write | Existing sealed records remain valid; uncertain interval quarantined | POSSIBLE |
| FM-03 | Scheduler outage | HIGH | Attempt recovery only before close; otherwise mark missing | Prior records valid; missed draw has no record | NO unless missingness/integrity limit crossed |
| FM-04 | Duplicate capture | MEDIUM | Reject duplicate idempotently and alert on conflicting payload | Original valid if digest matches | NO unless conflict implies tampering |
| FM-05 | Missing ticket identity | CRITICAL | Reject entire affected batch | No affected record valid | YES for post-outcome repair attempt |
| FM-06 | Unexpected distinct-ticket count | HIGH | Pause affected candidate and investigate before close | May remain valid only if actual identities are complete and protocol test handles actual N | POSSIBLE if caused by drift |
| FM-07 | Candidate-version drift | CRITICAL | Reject capture and disable candidate | Affected records invalid | YES for exposed interval |
| FM-08 | Scorer-version drift | CRITICAL | Pause capture/evaluation; do not rescore opportunistically | Capture may be quarantined; evaluation invalid until frozen scorer restored | POSSIBLE |
| FM-09 | Registry mismatch | HIGH | Do not mutate registry; reject and alert | Affected records invalid | POSSIBLE |
| FM-10 | Target-draw mismatch | CRITICAL | Reject batch and pause resolver | Affected records invalid | YES if outcome mapping occurred |
| FM-11 | Official schedule change | HIGH | Pause until change is verified before close | Earlier sealed draws valid | POSSIBLE |
| FM-12 | Lottery rule change | CRITICAL | Suspend protocol immediately | Prior records valid under old rules; future comparability uncertain | YES unless new preregistration governs a separate family |
| FM-13 | DB or schema migration | CRITICAL | Pause writes; preserve pre-migration snapshot | Existing records valid only after digest reconciliation | POSSIBLE |
| FM-14 | Corrupted evidence | CRITICAL | Quarantine store and use only independently sealed copies | Affected evidence invalid absent verified pre-outcome copy | YES if unrecoverable |
| FM-15 | Digest mismatch | CRITICAL | Stop capture and evaluation; preserve both versions | Affected record quarantined | POSSIBLE |
| FM-16 | Unauthorized manual correction | CRITICAL | Freeze affected family and revoke access | Affected evidence invalid | YES |
| FM-17 | Partial write | HIGH | Rollback; retry only before close with same deterministic identity | Failed attempt creates no eligible record | NO unless repaired after outcome |
| FM-18 | Replay or backfill attempt | CRITICAL | Reject, alert and preserve rejection event | No new valid record | YES if accepted into family |
| FM-19 | Prolonged outage | HIGH | Remain paused; no historical substitution | Prior records valid; gaps remain missing | OWNER_DECISION_REQUIRED |
| FM-20 | Operator absence | HIGH | Pause before unattended capture if safety cannot be assured | Prior records valid | NO unless gaps exceed rule |
| FM-21 | Monitoring silence | HIGH | Treat system as unsafe and pause | Recent records quarantined until audit | POSSIBLE |
| FM-22 | Candidate unavailable | HIGH | Mark candidate/draw missing; do not replace candidate | Other candidates may remain valid; m stays 3 | NO unless substitution occurs |
| FM-23 | Dependency deprecation | HIGH | Freeze upgrades and pause affected component | Prior records valid | POSSIBLE |
| FM-24 | Security or access-control breach | CRITICAL | Revoke access, pause all capture and preserve forensic evidence | Affected interval invalid unless integrity/timing independently proven | POSSIBLE/YES |
| FM-25 | Outcome ingestion before evidence seal | CRITICAL | Reject linkage and invalidate affected draw evidence | Affected draw invalid | YES |
| FM-26 | Retention or archive loss | CRITICAL | Stop analysis and recover from verified archive only | Lost interval invalid if no verified copy | YES if unrecoverable |
| FM-27 | Official source unavailable | HIGH | Fail closed; do not use manual source as confirmatory | Prior records valid | NO unless unverified data was accepted |
| FM-28 | Credential rotation failure | HIGH | Pause affected operations before close | Prior records valid | NO unless gaps exceed rule |

Every recovery path preserves the original evidence and forbids retrospective backfill into the prospective family.

## Evidence Matrix Summary

Rows: 40. CONFIRMED=6, PARTIAL=14, MISSING=17, CONFLICT=0, NOT_APPLICABLE=1, UNKNOWN=2.

**Confirmed capabilities:** Prospective boundary and preregistration; Ledger architecture design; Isolated ledger module; Temporary DB migration rehearsal; Production schema inspection; Duplicate detection and idempotency.

**Principal partial capabilities:** Production deployment preflight; Canonical ticket normalization and fingerprinting; Append-only and immutability guarantees; Capture-before-outcome enforcement; Official target-draw identity; Strategy and candidate version pinning; Activation identity and lifecycle; Result-ingestion separation; Structured provenance and source trace; Audit export; Correction and amendment policy; Evidence digesting and tamper detection.

**Principal missing capabilities:** Scorer and endpoint version pinning; Outcome availability tracking; Missing and late record handling; Operational scheduling; Restart and recovery behavior; Monitoring and alerting; Access control; Trusted clock and drift control; Retention and archival; Maintenance ownership; Evaluation and final-analysis implementation; Long-horizon service ownership; Gap threshold; Lottery rule surveillance; Operational runbooks; Security model.

**Unknowns:** Scientific value review; Cost and resource plan. **Conflicts:** None found in committed evidence.

The complete row-level evidence matrix, including source evidence, remediation, allowed future task type, owner decision, activation blocker and production blocker, is in the canonical JSON artifact.

## Implementation Prerequisites

1. Owner approves G1 architecture and selects the evidence-store pattern.
2. Owner names service, operations, security and scientific owners with backups.
3. Official target-draw/close source hierarchy and exception policy are selected and manually verified.
4. Trusted clock source, drift telemetry and fail-closed policy are defined; numerical drift threshold is OWNER_DECISION_REQUIRED.
5. A sealed P274A candidate manifest maps C1-C3 to exact source/dependency digests and expected ticket semantics.
6. P271J contract is extended or adapted to persist candidate_id, scorer_endpoint_version, explicit canonical ticket fingerprints, distinct_ticket_count and outcome availability status.
7. Disabled-by-default prediction producer, draw resolver and one-shot capture worker are implemented without result access.
8. Outcome availability/result linker and prospective evaluator are implemented as separate read-only/write-limited components.
9. Canonical audit export, batch digest and independent verifier are implemented.
10. Monitoring, alerting, access control, restart recovery, retention and migration interfaces are implemented.
11. Synthetic fault, concurrency, restart, security and long-horizon migration tests pass with no production DB access.
12. Operations runbooks and missingness policy are approved before any production preflight.

## Activation Prerequisites

1. G1 through G4 exit criteria are complete with current evidence.
2. A separate owner decision authorizes production installation/apply; P274B does not.
3. Prospective schema/runtime deployment is verified under P271M or equivalent post-apply evidence.
4. P271N-style activation authorization is explicitly granted after evidence review.
5. Official schedule source and trusted clock are healthy and independently checked.
6. Candidate, strategy, scorer and dependency manifests are sealed and reproducible.
7. Monitoring, on-call, backup, restore, access-control and security incident processes are active.
8. Maximum tolerated capture gaps and missingness classifications are owner-governed.
9. A separate G6 task records activation_timestamp_utc and first_eligible_target_draw before outcome exposure.
10. Boundary export/digest is independently verified before G7 capture begins.
11. No production apply, activation or capture is inferred from implementation completion.

## Production Blockers

- Production prospective namespace is ABSENT_CLEAN; schema is not installed.
- Production apply remains NOT_READY_FOR_APPLY and unauthorized.
- Fresh apply-time DB hash, maintenance window, writer quiescence, backup/restore and WAL/SHM evidence are absent.
- P271M post-apply verification and P271N activation are unstarted.
- No production capture worker, scheduler or authoritative draw-close resolver exists.
- Official schedule source remains MANUAL_VERIFICATION_REQUIRED.
- No trusted clock/drift monitoring contract is approved.
- P274A-required candidate_id, scorer endpoint version, explicit distinct-ticket evidence and outcome availability status are incomplete in P271J.
- No live monitoring, alert escalation, restart recovery, access control or security model exists.
- No long-horizon retention, independent archive or migration continuity evidence exists.
- No named maintenance/on-call ownership or gap threshold exists.
- No frozen prospective evaluator or audit-export interface exists.
- Concrete activation boundary remains unset and unauthorized.

## Owner Decisions

| ID | Decision | Options |
|---|---|---|
| OD-01 | Proceed to G1 approval, HOLD, or scientific closure | Approve architecture only and resolve blockers before G2; HOLD with no implementation; Scientific closure without activation |
| OD-02 | Evidence-store architecture | P271J in production DB; Separate evidence store; Transactional ledger plus independent WORM/signed archive |
| OD-03 | Official schedule authority and fallback | Official machine-readable; Official published schedule; Verified deterministic configuration; manual remains non-confirmatory |
| OD-04 | Trusted clock and maximum drift | Host NTP with independent telemetry; External trusted timestamp; Fail closed whenever trust cannot be proven |
| OD-05 | Maximum tolerated capture gaps and missingness rule | Zero unexplained gaps; Pre-registered bounded envelope with sensitivity analysis; Close protocol when coverage cannot be sustained |
| OD-06 | Service/on-call/scientific/security ownership | Name primary and backup humans/teams; Do not proceed |
| OD-07 | Retention and independent evidence durability | Protocol lifetime plus owner-defined audit period; Longer archival; Scientific closure if durable retention cannot be funded |
| OD-08 | Signing and key custody | No signing with independently stored hashes; Signed manifests with managed key ownership; External timestamp/WORM service |
| OD-09 | Permissible pre-close correction classes | No corrections after initial seal; Append-only pre-close correction with dual approval; Pause and mark missing |
| OD-10 | Infrastructure migration and dependency upgrade policy | Frozen environment until closure; Pre-approved reproducible migrations with dual verification; Close affected candidate rather than upgrade |
| OD-11 | Prolonged outage resume/closure rule | Resume only after reauthorization; Permanent closure after owner-governed missingness limit; Scientific closure |
| OD-12 | Cost/resource commitment for 3605 draws | Fund minimum commitments; HOLD; Scientific closure |
| OD-13 | Periodic non-efficacy scientific-value review cadence | Continue operations without efficacy peeking; HOLD safely; Scientific closure |
| OD-14 | Future G2 implementation scope | Authorize isolated resolver/worker/monitor/export/evaluator only after OD-02 through OD-13; Do not authorize implementation yet |

## Recommended Next Gate

**G1_OWNER_REVIEW_AND_DECISION**: Review and approve or reject the architecture, resolve owner decision points, then issue a separately scoped G2 authorization only if the evidence becomes complete.

Activation remains unauthorized because G2 implementation authorization does not exist, G3 is incomplete, G4 remains preflight-only and NOT_READY_FOR_APPLY, G5 has no owner authorization, and G6 boundary values are deliberately unset. There are no prospective records and no predictive-success claim.

## Safety Claims

- `design_only=true`
- `readiness_assessment_only=true`
- `implementation_started=false`
- `activation_started=false`
- `activation_timestamp_assigned=false`
- `first_eligible_target_draw_assigned=false`
- `prospective_capture_started=false`
- `prospective_records_exist=false`
- `production_db_accessed=false`
- `production_write=false`
- `p271_activated=false`
- `registry_mutated=false`
- `recommendation_logic_changed=false`
- `retrospective_remining_performed=false`
- `p273b_started=false`
- `deployment_started=false`
- `controlled_apply_started=false`
- `production_apply_authorized=false`
- `prediction_success_claim=false`
- `betting_advice=false`
- `no_retrospective_backfill_path=true`

Source-focused tests: **NOT RUN**. Full repository suite: **NOT RUN**. These are not reported as PASS.

Canonicalization excludes only `generated_at` and `canonical_payload_digest`. Digest was recomputed twice and reload-verified: `bf8ae32f8dbd208da4939ee46cdbe19125827f36c3a80aedefc8fee21a994744`.
