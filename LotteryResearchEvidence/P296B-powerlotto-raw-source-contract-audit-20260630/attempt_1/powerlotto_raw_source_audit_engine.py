#!/usr/bin/env python3
"""
P296B — PowerLotto raw-source contract audit engine.

LOCAL, READ-ONLY, DESCRIPTIVE-CONTRACT-ONLY. Opens the authorized DB strictly read-only
(URI mode=ro, PRAGMA query_only=1), inventories the schema, verifies the exact PowerLotto
`lottery_type` representation, reads ONLY those rows, and classifies each row's validity for a
PROPOSED logical source contract (frozen rules in FROZEN_RAW_SOURCE_AUDIT_SPEC.md).

Forbidden/absent: any write SQL / DB write / schema change / view creation / DB copy; immutable mode;
network; random / simulation; frequency scoring / candidate selection / prediction / future ticket;
reading any other lottery type; printing actual six-number combinations or the special value (only
ids/draws/dates, field-shape metadata, validity classes, and hash-derived fingerprints are emitted).

Standard library only. Writes only under the --out directory (a run dir under the P296B root).
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys

DB_PATH = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db"
TABLE = "draws"
POWER_CANONICAL = "POWER_LOTTO"          # verified representation = lottery_type whose UPPER == this
POWER_VIEW = "draws_power_lotto_canonical_main"
REQUIRED_COLS = ("id", "draw", "date", "lottery_type", "numbers", "special")
MAIN_LO, MAIN_HI, MAIN_K = 1, 38, 6
SPECIAL_LO, SPECIAL_HI = 1, 8
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PLAIN_INT = re.compile(r"^[0-9]+$")


def stop(code, msg):
    sys.stderr.write(code + ": " + msg + "\n")
    sys.exit(2)


def open_readonly():
    if not os.path.isfile(DB_PATH):
        stop("P296B_STOPPED_DB_ASSET_MISSING_OR_UNSAFE", "db not a regular file")
    con = sqlite3.connect("file:" + DB_PATH + "?mode=ro", uri=True)
    con.execute("PRAGMA query_only=1")
    if int(con.execute("PRAGMA query_only").fetchone()[0]) != 1:
        stop("P296B_STOPPED_DB_ASSET_MISSING_OR_UNSAFE", "query_only not enforced")
    return con


def parse_ints_json_first(raw):
    """Return (ints, method). method in {'json','regex','empty'}."""
    if raw is None:
        return [], "empty"
    s = raw if isinstance(raw, str) else str(raw)
    s_strip = s.strip()
    if s_strip:
        try:
            v = json.loads(s_strip)
            if isinstance(v, list) and all(isinstance(x, (int,)) and not isinstance(x, bool) for x in v):
                return [int(x) for x in v], "json"
            if isinstance(v, list) and all(isinstance(x, str) and x.strip().isdigit() for x in v):
                return [int(x) for x in v], "json"
            if isinstance(v, int) and not isinstance(v, bool):
                return [v], "json"
        except (ValueError, TypeError):
            pass
    toks = re.findall(r"\d+", s)
    if toks:
        return [int(t) for t in toks], "regex"
    return [], "empty"


def date_class(d):
    if d is None:
        return "UNPARSEABLE_NULL"
    s = str(d).strip()
    if not s:
        return "UNPARSEABLE_EMPTY"
    return "PARSEABLE_ISO" if ISO_DATE.match(s) else "PARSEABLE_OTHER"


def main():
    ap = argparse.ArgumentParser(description="P296B PowerLotto raw-source contract audit engine")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    con = open_readonly()
    try:
        # ---- schema inventory ----
        master = con.execute(
            "SELECT type, name, tbl_name FROM sqlite_master WHERE type IN ('table','view','index') ORDER BY type, name"
        ).fetchall()
        views = sorted(n for (t, n, _tb) in master if t == "view")
        tables = sorted(n for (t, n, _tb) in master if t == "table")
        draws_indexes = sorted(n for (t, n, tb) in master if t == "index" and tb == TABLE)
        power_view_absent = POWER_VIEW not in views

        if TABLE not in tables:
            stop("P296B_STOPPED_SCHEMA_OR_TYPE_MISMATCH", "base table 'draws' absent")

        colinfo = con.execute("PRAGMA table_info(%s)" % TABLE).fetchall()
        columns = [c[1] for c in colinfo]  # (cid,name,type,notnull,dflt,pk)
        col_pk = {c[1]: c[5] for c in colinfo}
        missing_required = [c for c in REQUIRED_COLS if c not in columns]
        if "lottery_type" in missing_required or "id" in missing_required or "draw" in missing_required:
            stop("P296B_STOPPED_SCHEMA_OR_TYPE_MISMATCH",
                 "critical column(s) missing: " + ",".join(missing_required))

        # ---- PowerLotto type representation ----
        type_dist = con.execute(
            "SELECT lottery_type, COUNT(*) FROM %s GROUP BY lottery_type ORDER BY lottery_type" % TABLE
        ).fetchall()
        type_dist = [(("" if t is None else str(t)), int(n)) for (t, n) in type_dist]
        power_like = [(t, n) for (t, n) in type_dist if t.upper() == POWER_CANONICAL]
        verified_rep = power_like[0][0] if len(power_like) == 1 else None
        type_rep_ok = verified_rep is not None

        # ---- read PowerLotto rows (only the verified representation) ----
        rows = []
        if type_rep_ok:
            sel_cols = [c for c in ("id", "draw", "date", "lottery_type", "numbers", "special") if c in columns]
            sql = ("SELECT " + ", ".join(sel_cols) + " FROM " + TABLE +
                   " WHERE lottery_type = ? ORDER BY CAST(draw AS INTEGER) ASC, id ASC")
            raw_rows = con.execute(sql, (verified_rep,)).fetchall()
            for rr in raw_rows:
                rec = dict(zip(sel_cols, rr))
                rows.append(rec)
    finally:
        con.close()

    # ---- per-row classification (frozen rules) ----
    audit = []
    draw_seen = {}
    for rec in rows:
        rid = rec.get("id")
        draw = rec.get("draw")
        draw_s = "" if draw is None else str(draw)
        date_c = date_class(rec.get("date"))
        mains, m_method = parse_ints_json_first(rec.get("numbers"))
        specials, s_method = parse_ints_json_first(rec.get("special"))
        m_count = len(mains)
        m_unique = len(set(mains))
        m_in_range = all(MAIN_LO <= x <= MAIN_HI for x in mains) if mains else False
        main_ok = (m_count == MAIN_K and m_unique == MAIN_K and m_in_range)
        s_count = len(specials)
        special_ok = (s_count == 1 and SPECIAL_LO <= specials[0] <= SPECIAL_HI)
        is_plain = bool(PLAIN_INT.match(draw_s)) and not (len(draw_s) == 8 and draw_s.startswith("20"))

        # fingerprint over MAIN combo (hashed; never printed in plaintext) + shape (no special value)
        fp_pre = "main:" + "-".join(str(x) for x in sorted(mains)) + "|mc:%d|mu:%d|sc:%d" % (m_count, m_unique, s_count)
        fingerprint = hashlib.sha256(fp_pre.encode("utf-8")).hexdigest()

        if (not is_plain):
            cls, reason = "EXCLUDED_WITH_EXACT_REASON", "DRAW_NOT_PLAIN_SEQUENCE_INTEGER"
        elif main_ok and special_ok and rid is not None:
            cls, reason = "VALID_FOR_PROPOSED_CONTRACT", ""
        else:
            reasons = []
            if rid is None:
                reasons.append("ID_NULL")
            if m_count != MAIN_K:
                reasons.append("MAIN_COUNT_NE_6(%d)" % m_count)
            elif m_unique != MAIN_K:
                reasons.append("MAIN_NOT_UNIQUE")
            elif not m_in_range:
                reasons.append("MAIN_OUT_OF_RANGE")
            if s_count != 1:
                reasons.append("SPECIAL_COUNT_NE_1(%d)" % s_count)
            elif not (SPECIAL_LO <= specials[0] <= SPECIAL_HI):
                reasons.append("SPECIAL_OUT_OF_RANGE")
            if m_method == "empty":
                reasons.append("NUMBERS_UNPARSEABLE")
            cls, reason = "AMBIGUOUS_REQUIRES_OWNER_DECISION", "+".join(reasons) if reasons else "UNCLASSIFIED"

        audit.append({
            "id": rid, "draw": draw_s, "date_class": date_c,
            "draw_is_plain_sequence": is_plain,
            "main_parse_method": m_method, "main_count": m_count, "main_unique": m_unique,
            "main_all_in_1_38": m_in_range,
            "special_parse_method": s_method, "special_count": s_count, "special_in_1_8": special_ok,
            "classification": cls, "reason": reason, "fingerprint": fingerprint,
        })
        draw_seen.setdefault(draw_s, []).append(rid)

    # ---- duplicate detection (frozen) ----
    valid_idx = [i for i, a in enumerate(audit) if a["classification"] == "VALID_FOR_PROPOSED_CONTRACT"]
    valid_draw_counts = {}
    for i in valid_idx:
        valid_draw_counts[audit[i]["draw"]] = valid_draw_counts.get(audit[i]["draw"], 0) + 1
    dup_valid_draws = sorted(d for d, c in valid_draw_counts.items() if c > 1)
    for i in valid_idx:
        if audit[i]["draw"] in set(dup_valid_draws):
            audit[i]["classification"] = "AMBIGUOUS_REQUIRES_OWNER_DECISION"
            audit[i]["reason"] = "DUPLICATE_DRAW_IDENTITY"
    # ordered-key uniqueness (CAST(draw AS INTEGER), id) over all power rows
    ordered_keys = [(int(a["draw"]) if PLAIN_INT.match(a["draw"]) else None, a["id"]) for a in audit]
    dup_ordered_key = len(ordered_keys) != len(set(ordered_keys))

    # ---- recount after duplicate promotion ----
    def count_cls(c):
        return sum(1 for a in audit if a["classification"] == c)
    valid_count = count_cls("VALID_FOR_PROPOSED_CONTRACT")
    excluded_count = count_cls("EXCLUDED_WITH_EXACT_REASON")
    ambiguous_count = count_cls("AMBIGUOUS_REQUIRES_OWNER_DECISION")
    reason_breakdown = {}
    for a in audit:
        if a["reason"]:
            reason_breakdown[a["reason"]] = reason_breakdown.get(a["reason"], 0) + 1
    reason_breakdown = dict(sorted(reason_breakdown.items()))
    valid_draws_int = sorted(int(a["draw"]) for a in audit if a["classification"] == "VALID_FOR_PROPOSED_CONTRACT")
    first_valid_draw = valid_draws_int[0] if valid_draws_int else None
    last_valid_draw = valid_draws_int[-1] if valid_draws_int else None
    all_power_draw_dupes = sorted(d for d, ids in draw_seen.items() if len(ids) > 1)

    # ---- decision (frozen) ----
    schema_gap = bool(missing_required)
    not_ready_reasons = []
    if schema_gap:
        not_ready_reasons.append("MISSING_REQUIRED_COLUMNS:" + ",".join(missing_required))
    if not type_rep_ok:
        not_ready_reasons.append("POWER_TYPE_REP_NOT_UNIQUE:%d" % len(power_like))
    if dup_ordered_key:
        not_ready_reasons.append("DUPLICATE_ORDERED_KEY")
    if dup_valid_draws:
        not_ready_reasons.append("DUPLICATE_DRAW_IDENTITY_AMONG_VALID:%d" % len(dup_valid_draws))
    if ambiguous_count > 0:
        not_ready_reasons.append("AMBIGUOUS_ROWS:%d" % ambiguous_count)
    if not rows:
        not_ready_reasons.append("NO_POWER_ROWS")
    decision = "SOURCE_READY_FOR_OWNER_REVIEW" if not not_ready_reasons else "SOURCE_NOT_READY_FOR_OWNER_DECISION"

    # ---- write per-row audit CSV (NO winning-number combinations) ----
    cols = ["id", "draw", "date_class", "draw_is_plain_sequence", "main_parse_method", "main_count",
            "main_unique", "main_all_in_1_38", "special_parse_method", "special_count", "special_in_1_8",
            "classification", "reason", "fingerprint"]
    lines = [",".join(cols)]
    for a in audit:
        lines.append(",".join(str(a[c]) for c in cols))
    csv_data = "\n".join(lines) + "\n"
    with open(os.path.join(out_dir, "POWERLOTTO_RAW_ROW_AUDIT.csv"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(csv_data)
    row_csv_sha = hashlib.sha256(csv_data.encode("utf-8")).hexdigest()

    # ---- schema inventory text ----
    with open(os.path.join(out_dir, "SCHEMA_INVENTORY.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("draws_table_present=True\n")
        fh.write("draws_columns=" + ",".join(columns) + "\n")
        fh.write("missing_required_columns=" + (",".join(missing_required) if missing_required else "NONE") + "\n")
        fh.write("draws_indexes=" + (",".join(draws_indexes) if draws_indexes else "NONE") + "\n")
        fh.write("primary_key_cols=" + ",".join(sorted(c for c, pk in col_pk.items() if pk)) + "\n")
        fh.write("all_tables=" + ",".join(tables) + "\n")
        fh.write("all_views=" + (",".join(views) if views else "NONE") + "\n")
        fh.write("power_view_present=" + str(not power_view_absent) + "\n")

    # ---- type mapping text ----
    with open(os.path.join(out_dir, "TYPE_MAPPING.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("lottery_type_distribution (name=count):\n")
        for (t, n) in type_dist:
            fh.write("  %s=%d\n" % (t, n))
        fh.write("power_like_values(upper==POWER_LOTTO)=" + (",".join(t for t, _ in power_like) if power_like else "NONE") + "\n")
        fh.write("verified_power_representation=" + (verified_rep if verified_rep else "NOT_UNIQUE") + "\n")
        fh.write("power_row_count=%d\n" % len(rows))

    # ---- audit samples (first/middle/last by ordered position; no combinations) ----
    with open(os.path.join(out_dir, "AUDIT_SAMPLES.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("PowerLotto ordered audit samples (no winning-number combinations):\n")
        if audit:
            idxs = [("first", 0), ("middle", len(audit) // 2), ("last", len(audit) - 1)]
            for lab, k in idxs:
                a = audit[k]
                fh.write("  %-6s pos=%d id=%s draw=%s date_class=%s class=%s reason=%s fp=%s\n"
                         % (lab, k, a["id"], a["draw"], a["date_class"], a["classification"],
                            a["reason"] or "-", a["fingerprint"][:16]))
        else:
            fh.write("  NONE\n")

    # ---- source validation text ----
    with open(os.path.join(out_dir, "SOURCE_VALIDATION.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("power_row_count=%d\n" % len(rows))
        fh.write("valid_count=%d\n" % valid_count)
        fh.write("excluded_count=%d\n" % excluded_count)
        fh.write("ambiguous_count=%d\n" % ambiguous_count)
        fh.write("first_valid_draw=%s\n" % first_valid_draw)
        fh.write("last_valid_draw=%s\n" % last_valid_draw)
        fh.write("duplicate_draw_identities_all=%s\n" % (",".join(all_power_draw_dupes) if all_power_draw_dupes else "NONE"))
        fh.write("duplicate_draw_identities_among_valid=%s\n" % (",".join(dup_valid_draws) if dup_valid_draws else "NONE"))
        fh.write("duplicate_ordered_key=%s\n" % dup_ordered_key)
        fh.write("power_view_absent=%s\n" % power_view_absent)
        fh.write("decision=%s\n" % decision)

    canonical = {
        "schema": "P296B-powerlotto-raw-source-contract-audit/v1",
        "task_id": "P296B-POWERLOTTO-RAW-SOURCE-CONTRACT-AUDIT",
        "db_sha256_expected": "41e9c37948650c1d881502f7d204a2656c16e61e8e7b96058d23da76dd666cab",
        "schema_inventory": {
            "draws_table_present": True, "draws_columns": columns,
            "missing_required_columns": missing_required, "draws_indexes": draws_indexes,
            "all_views": views, "power_view_present": (not power_view_absent),
        },
        "type_mapping": {
            "lottery_type_distribution": [{"type": t, "count": n} for (t, n) in type_dist],
            "power_like_values": [t for t, _ in power_like],
            "verified_power_representation": verified_rep, "type_rep_unique": type_rep_ok,
            "power_row_count": len(rows),
        },
        "row_audit": {
            "ordering": "CAST(draw AS INTEGER) ASC, id ASC",
            "total_power_rows": len(audit),
            "valid_count": valid_count, "excluded_count": excluded_count, "ambiguous_count": ambiguous_count,
            "reason_breakdown": reason_breakdown,
            "first_valid_draw": first_valid_draw, "last_valid_draw": last_valid_draw,
            "duplicate_draw_identities_all": all_power_draw_dupes,
            "duplicate_draw_identities_among_valid": dup_valid_draws,
            "duplicate_ordered_key": dup_ordered_key,
            "row_audit_csv_sha256": row_csv_sha,
        },
        "decision": {
            "result": decision,
            "not_ready_reasons": not_ready_reasons,
            "power_view_absent": power_view_absent,
        },
        "boundary": (
            "Read-only raw-source contract audit. No DB object created, no source declared canonical, "
            "no scoring/selection/prediction/future-ticket. No winning-number combinations or special "
            "values are emitted; only ids/draws/date-classes, field-shape metadata, validity classes, "
            "and hash-derived fingerprints."
        ),
    }
    cbytes = (json.dumps(canonical, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    with open(os.path.join(out_dir, "CANONICAL_RESULT.json"), "wb") as fh:
        fh.write(cbytes)
    digest = hashlib.sha256(cbytes).hexdigest()
    with open(os.path.join(out_dir, "CANONICAL_RESULT.sha256"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(digest + "  CANONICAL_RESULT.json\n")

    sys.stdout.write("P296B engine OK: power_rows=%d valid=%d excluded=%d ambiguous=%d decision=%s sha=%s\n"
                     % (len(audit), valid_count, excluded_count, ambiguous_count, decision, digest))


if __name__ == "__main__":
    main()
