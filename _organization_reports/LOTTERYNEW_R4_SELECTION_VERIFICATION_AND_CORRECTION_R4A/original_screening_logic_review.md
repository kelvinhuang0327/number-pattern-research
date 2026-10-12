# Review of Original R4 Screening Logic

## Overview

This report audits the candidate screening logic utilized in `LOTTERYNEW_NEXT_VERIFIED_BRANCH_VERTICAL_SELECTION_R4`.

## Detailed Findings

| Check Point | Verdict | Findings & Evidence |
| :--- | :--- | :--- |
| **1. Equating File Absence to Safety** | **CONFIRMED** | R4 assumed that candidates whose target files were absent in the destination repo were automatically "safe" without evaluating the internal risk of the candidate's code itself. |
| **2. Equating File Presence to Functional Equivalence** | **CONFIRMED** | R4 treated existing target paths as blocking collisions regardless of whether the content was functionally identical or dirty baseline noise. |
| **3. Path-only DB Risk Assessment** | **CONFIRMED** | R4 checked directory names (e.g. `migrations/`) for DB risk, missing executable scripts such as `scripts/apply_p0_schema_migration.py` that perform `ALTER TABLE` and `CREATE INDEX` on `lottery_v2.db`. |
| **4. Searching `migrations` vs `migration`** | **CONFIRMED** | The search logic only scanned for plural `migrations/` paths and missed standalone `migration` scripts and functions. |
| **5. Treating Tests and Outputs as Consumers** | **CONFIRMED** | Unit tests (`test_p0_canonical_universe.py`) and JSON reports (`outputs/replay/*.json`) were mistakenly classified as production consumer entrypoints. |
| **6. Ignoring Corrected Backlog Ranking** | **CONFIRMED** | R4 bypassed `corrected_priority_backlog.jsonl` from R2A, re-ranking candidates arbitrarily without respecting the verified functional cluster hierarchy. |
| **7. Manual Scoring of Unread/Unmaterialized Candidates** | **CONFIRMED** | Candidates `cand_063` through `cand_013` were assigned subjective safety scores (92, 90, 88...) in `top_10_safe_candidates.md` even though their source refs were unmaterialized in R1 extraction. |
| **8. Including Owner-Decision Candidates in Top Safe** | **CONFIRMED** | `top_10_safe_candidates.md` included 10 candidates classified as `OWNER_DECISION_REQUIRED` in `candidate_screening.jsonl` as "Top Safe Candidates", including winner `cand_059`. |

## Conclusion

The original R4 screening logic contained major gaps in source AST inspection, DB risk detection, and statistical reporting consistency.
