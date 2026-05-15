# Data Ingestion System — Release Summary

## Changed Files

| File | Change |
|------|--------|
| `lottery_api/app.py` | Import + register `ingest` router |
| `lottery_api/requirements.txt` | Added `requests>=2.31.0`, `beautifulsoup4>=4.12.0` |
| `src/core/App.js` | Import + instantiate `AutoFetchManager` |
| `index.html` | Added CSS + 3 new UI cards + ingest log panel |

## New Modules

| File | Purpose |
|------|---------|
| `lottery_api/fetcher/__init__.py` | Package marker |
| `lottery_api/fetcher/taiwan_lottery_fetcher.py` | HTTP fetcher from Taiwan Lottery official site |
| `lottery_api/fetcher/missing_issue_detector.py` | DB vs official gap detection |
| `lottery_api/fetcher/backfill_engine.py` | Safe idempotent backfill orchestrator |
| `lottery_api/fetcher/ingest_logger.py` | JSONL audit log writer/reader |
| `lottery_api/routes/ingest.py` | 6 new FastAPI endpoints |
| `src/ui/AutoFetchManager.js` | Frontend UI controller for all 3 new panels |

## New Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/ingest/status` | Source health check (all 3 games) |
| POST | `/api/ingest/fetch-latest` | Fetch latest draw from official site |
| GET | `/api/ingest/scan-missing` | Scan DB vs official for missing draws |
| POST | `/api/ingest/backfill` | Run backfill (auto-detect or explicit list) |
| GET | `/api/ingest/log` | View recent ingest log entries |
| POST | `/api/ingest/log/clear` | Clear ingest log |

## Frontend Changes

New section added to the 數據上傳 page (inside `#upload-section`):

1. **抓取最新開獎** — one-click fetch from official site with optional auto-insert
2. **掃描缺漏期數** — compare DB vs official, show missing draw numbers
3. **自動補入缺漏** — safe backfill with dry-run preview and confirmation gate
4. **入庫操作記錄** — live log table of all ingest operations

## Manual Upload Unchanged
The existing `DrawEntryManager` and `POST /api/draws` endpoint are **untouched**.
All CSV/TXT upload flows are unaffected.

## Audit Trail
All automated operations are logged to:
```
lottery_api/data/ingest_log.jsonl
```
Schema per entry: `timestamp, action, lottery_type, draw, status, message, data`

## Safety Guarantees
- **No silent overwrites**: existing records are never modified
- **Conflict detection**: data mismatch logs a CONFLICT and skips
- **Idempotent**: safe to re-run backfill multiple times
- **Dry-run mode**: preview without writing (both API and UI)
- **Confirmation gate**: UI backfill requires explicit checkbox before executing

## Remaining Risks / Assumptions
1. **Source URL stability**: Taiwan Lottery website HTML structure may change;
   fetcher will return clear error messages if parsing fails
2. **No complete history fetch**: The fetcher reads the most recent ~50 draws per page;
   for very old gaps the user should use manual CSV upload
3. **Rate limiting**: 0.8s polite delay between requests; not tested under high load
4. **Missing period detection scope**: Only draws present on the official history page
   (last ~50) are compared; older gaps rely on within-year DB gap scan
5. **requests/bs4 dependency**: Added to requirements.txt; already installed in env
