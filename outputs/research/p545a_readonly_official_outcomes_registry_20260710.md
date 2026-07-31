# P545A — Official Outcomes Registry from Committed P268D1 JSONL

> Deterministic historical outcome evidence for research only. This is not betting or investment advice and makes no predictive-edge, improved-odds, betting-readiness, or production-readiness claim.

## Purpose

Export exactly one validated official outcome for every draw requested by the frozen P273A manifest and P543C contract.

## Frozen source manifest

- Pinned repository commit: `fead482e4ffbc501ea07928e338d2416ba3bd126`
- Deterministic timestamp: `2026-07-10T11:18:28+00:00`
- Timestamp policy: pinned input commit committer timestamp normalized to UTC seconds

| source | role | path | SHA-256 | bytes |
|---|---|---|---|---:|
| p268d1 | sole_official_outcome_source | `outputs/research/p268d1_draw_order_full_history_artifact_backfill_20260610.jsonl` | `f4accb6f527694e739689242c929e87e4b031a364becb4fadb4aaea50ef2e3f8` | 7745520 |
| p273a | requested_draw_manifest | `outputs/research/p273a_distinct_ticket_identity_20260615.json` | `b10b916c00f807ace7342250b788dbf1d62c12a0b8e2d5aa627b5a4eb25089b0` | 26707364 |
| p543c | independent_outcome_cross_check | `outputs/research/p543c_candidate_per_draw_validation_contract_20260710.json` | `71be8549daddbc0e810e17e3e6afbd49eedc02eee402c017e562a834ef1448a5` | 515478 |

P268D1 is the selected authoritative source because it is a frozen, committed full-history artifact with an exact raw-byte hash and an explicit ordered/size outcome contract. No alternate or fallback source is permitted.

## P268D1 full-source validation

- Parsed JSONL lines: 21682
- Relevant official records: 9930
- Duplicate identical keys / conflicting keys: 0 / 0
- Malformed / invalid date / invalid number: 0 / 0 / 0
- Invalid range / duplicate number / missing auxiliary: 0 / 0 / 0
- `drawNumberAppear` checked / mismatched: 9930 / 0
- Stable numeric draw ordering: `True`

| lottery | source records | earliest draw | latest draw | earliest date | latest date |
|---|---:|---|---|---|---|
| BIG_LOTTO | 2139 | 96000001 | 115000057 | 2007-01-02 | 2026-05-29 |
| DAILY_539 | 5876 | 96000001 | 115000132 | 2007-01-01 | 2026-05-30 |
| POWER_LOTTO | 1915 | 97000001 | 115000043 | 2008-01-24 | 2026-05-28 |

## Requested manifest and complete coverage

- P273A unique draws: 2252
- P543C rows / candidates / unique draws: 500 / 10 / 52
- P543C draws overlapping P273A: 52

| lottery | requested | found valid | missing | conflicting | invalid |
|---|---:|---:|---:|---:|---:|
| BIG_LOTTO | 752 | 752 | 0 | 0 | 0 |
| DAILY_539 | 750 | 750 | 0 | 0 | 0 |
| POWER_LOTTO | 750 | 750 | 0 | 0 | 0 |
| **Total** | **2252** | **2252** | **0** | **0** | **0** |

## P543C cross-check

- Compared rows / unique draws: 500 / 52
- Main-number mismatches: 0
- Special-number mismatches: 0
- Internally conflicting draws: 0
- Result: `PASS`

## Deterministic generation and safety evidence

- Inputs are raw blobs from the pinned commit and are verified by exact byte size and SHA-256.
- Records are sorted by lottery type, numeric draw, then draw text.
- The timestamp is derived from the pinned commit; wall-clock time, file metadata, random order, external services, and fallback sources are not used.
- Complete registry emitted: `True` (2252 records)
- Database opened / written: `False` / `False`
- Network used: `False`
- Upstream artifact modified / partial registry emitted: `False` / `False`

## Limitations

- This registry contains deterministic historical outcome evidence only.
- It does not evaluate strategies, predictions, returns, ROI, EV, or future draws.
- It is for research and entertainment only and is not betting or investment advice.
- It does not establish improved winning odds, predictive advantage, betting readiness, or production readiness.

## Digest evidence

- JSON raw-byte SHA-256: `a787c025579de924f9b37b0e43fbda2526c36e157561f8f0b39fa913a55287c8`
- Markdown canonical-body SHA-256 (this digest section excluded): `6b6fc5a6e6fc0615dbe53b612b7b36cbfa7afe608264a00c8c234fe4c0c6d2e8`
- Canonical payload digest: `69453706adf697afb67f8dbbcfb0e0f63c36f7c9aefcabef8201383e18e25dde`
