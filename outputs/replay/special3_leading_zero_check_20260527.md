# 三星彩 Leading-Zero Check — 2026-05-27

## Result: PASS

| Check | Value |
|-------|-------|
| Total 3_STAR draws verified | 4,115 |
| Errors found | **0** |
| Draws with leading zero at position 0 | 1,261 (30.6%) |
| Format tested | `numbers` JSON array → `"{d[0]}{d[1]}{d[2]}"` |

## Verification Protocol

- All 4,115 rows read from `draws` table (`lottery_type='3_STAR'`)
- `numbers` column parsed via `json.loads()` → Python list of integers
- Each list verified: length == 3, each element ∈ {0..9}
- Serialized as `f"{nums[0]}{nums[1]}{nums[2]}"` — single-char concatenation preserves order and zero
- String length verified == 3 for every record

## Leading-Zero Sample Verification

| draw | date | DB value | Serialized |
|------|------|----------|------------|
| 96000003 | 2007/01/03 | [0, 1, 2] | `012` ✅ |
| 96000004 | 2007/01/04 | [0, 3, 9] | `039` ✅ |
| 96000008 | 2007/01/10 | [0, 2, 7] | `027` ✅ |
| 96000009 | 2007/01/11 | [0, 5, 8] | `058` ✅ |
| 96000012 | 2007/01/16 | [0, 3, 6] | `036` ✅ |

## Key Finding

DB stores digits as integers (no leading zero loss at storage). The `int → single-char string`
concatenation (`f"{d}"` for d in 0..9) always produces a single character, so the 3-character
join is always exactly 3 chars with no leading-zero loss.

⚠️ **Note**: If digits were ever stored as a single integer (e.g., `12` for `012`), this would
fail. The current schema stores as `[0, 1, 2]` (list of ints), which is safe. Any future
ingestion must preserve the list-of-int format, not collapse to a single int.

## Classification

`PASS` — No leading-zero issues found. Safe to proceed with baseline replay.
