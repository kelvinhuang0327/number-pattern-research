# Phase 1 — Data Ingestion Audit

## Current Upload Page
- **File**: `index.html` (lines 194–250)
- **Card**: "快速開獎入庫" inside `#upload-section`
- **Controller**: `src/ui/DrawEntryManager.js`
- **API endpoint used**: `POST /api/draws`

## Backend Ingestion Logic
| File | Role |
|------|------|
| `lottery_api/routes/data.py` | Handles `/api/draws` POST, validates, calls `db_manager.insert_draws()` |
| `lottery_api/database.py` | `DatabaseManager.insert_draws()` — batch insert with `INSERT OR IGNORE` |
| `lottery_api/schemas.py` | `CreateDrawRequest` Pydantic schema |
| `lottery_api/common.py` | `normalize_lottery_type()` — handles Chinese/English name mapping |

## Database Schema
```sql
CREATE TABLE draws (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    draw         TEXT NOT NULL,        -- Period number as TEXT (e.g. "115000037")
    date         TEXT NOT NULL,        -- YYYY/MM/DD
    lottery_type TEXT NOT NULL,        -- BIG_LOTTO | POWER_LOTTO | DAILY_539
    numbers      TEXT NOT NULL,        -- JSON array e.g. "[11,15,33,38,41,43]"
    special      INTEGER DEFAULT 0,    -- Special/bonus number (0 if none)
    created_at   TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(draw, lottery_type)         -- Prevents duplicates
);
```

### Critical: draw field is TEXT
- Always query with `ORDER BY CAST(draw AS INTEGER) DESC`
- Never use `ORDER BY draw DESC` (string sort is wrong for 9-digit numbers)

## Draw Number Format
```
Format:  {ROC_year}{6-digit-sequence}
Example: 115000037
           ^^^          = ROC year 115 (= 2026 Gregorian)
              ^^^^^^    = sequential issue 37 within year 115
```

## Supported Lottery Games
| Type | Label | Count | Range | Special |
|------|-------|-------|-------|---------|
| `BIG_LOTTO` | 大樂透 | 6 | 1–49 | Yes (1–49) |
| `POWER_LOTTO` | 威力彩 | 6 | 1–38 | Yes (1–8) |
| `DAILY_539` | 今彩539 | 5 | 1–39 | No |

## Existing Data Counts (2026-03-23)
| Game | Records | Earliest | Latest |
|------|---------|----------|--------|
| BIG_LOTTO | 2119 | 96000001 | 115000037 |
| POWER_LOTTO | 1895 | 97000001 | 115000023 |
| DAILY_539 | 5816 | 96000001 | 115000072 |

## CLI Tools (Existing)
- `tools/update_draw.py` — interactive/batch CLI insert with RSM bootstrap
- `tools/post_draw_pipeline.py` — 5-step post-draw automation (insert→RSM→PSI→Quality→Alert)
