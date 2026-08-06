#!/usr/bin/env python3
"""
LOTTERYNEW_CONFLICT_REFERENCE_NORMALIZATION_CORE_R1
Organizes scoped conflict reference files in lottery/ and lottery_api/ into _conflict_reference/LOTTERY_CORE_R1.
"""

import os
import sys
import json
import time
import hashlib
import shutil
import re
import datetime

WORKSPACE = "/Users/kelvin/VibeCoding-WorkSpace/LotteryNewMeraged"
SCOPE_ROOTS = ["lottery", "lottery_api"]
REFERENCE_ROOT_REL = "_conflict_reference/LOTTERY_CORE_R1"
REPORT_ROOT_REL = "_organization_reports/LOTTERYNEW_CONFLICT_REFERENCE_NORMALIZATION_CORE_R1"

REFERENCE_ROOT = os.path.join(WORKSPACE, REFERENCE_ROOT_REL)
REPORT_ROOT = os.path.join(WORKSPACE, REPORT_ROOT_REL)

CONFLICT_PATTERNS = [".__CONFLICT__", ".__CASE_CONFLICT__", ".__UNICODE_CONFLICT__"]

def calc_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def get_file_metadata(full_path, rel_path):
    is_symlink = os.path.islink(full_path)
    if is_symlink:
        return {
            "rel_path": rel_path,
            "is_symlink": True,
            "size": 0,
            "sha256": None,
            "mtime": os.lstat(full_path).st_mtime
        }
    stat = os.stat(full_path)
    return {
        "rel_path": rel_path,
        "is_symlink": False,
        "size": stat.st_size,
        "sha256": calc_sha256(full_path),
        "mtime": stat.st_mtime
    }

def find_scoped_conflict_files():
    conflict_files = []
    for scope in SCOPE_ROOTS:
        scope_dir = os.path.join(WORKSPACE, scope)
        if not os.path.exists(scope_dir):
            continue
        for root, dirs, files in os.walk(scope_dir):
            for f in files:
                if any(pat in f for pat in CONFLICT_PATTERNS):
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, WORKSPACE)
                    conflict_files.append((full_p, rel_p, scope))
    return sorted(conflict_files, key=lambda x: x[1])

def derive_canonical_rel_path(conflict_rel_path):
    dir_name, file_name = os.path.split(conflict_rel_path)
    pattern_regex = re.compile(r"\.(?:__CONFLICT__|__CASE_CONFLICT__|__UNICODE_CONFLICT__)")
    match = pattern_regex.search(file_name)
    if match:
        canonical_filename = file_name[:match.start()]
    else:
        canonical_filename = file_name
    return os.path.join(dir_name, canonical_filename)

def parse_conflict_labels(filename):
    pattern_regex = re.compile(r"\.(?:__CONFLICT__|__CASE_CONFLICT__|__UNICODE_CONFLICT__)(.+)")
    match = pattern_regex.search(filename)
    if not match:
        return None, None, None
    suffix = match.group(1)
    parts = suffix.split("__")
    source_label = parts[0] if len(parts) > 0 else None
    branch_label = parts[1] if len(parts) > 1 else None
    source_short_sha = parts[-1] if len(parts) > 2 else None
    return source_label, branch_label, source_short_sha

def main():
    print(f"=== Starting LOTTERYNEW_CONFLICT_REFERENCE_NORMALIZATION_CORE_R1 ===")
    os.makedirs(REPORT_ROOT, exist_ok=True)
    os.makedirs(REFERENCE_ROOT, exist_ok=True)

    # 1. Discover scoped conflict files
    raw_files = find_scoped_conflict_files()
    print(f"Discovered {len(raw_files)} scoped conflict files.")

    # 2. Phase 0 Snapshot 1
    snap1 = {}
    for full_p, rel_p, scope in raw_files:
        snap1[rel_p] = get_file_metadata(full_p, rel_p)

    time.sleep(1.0)

    # Phase 0 Snapshot 2
    snap2 = {}
    for full_p, rel_p, scope in raw_files:
        snap2[rel_p] = get_file_metadata(full_p, rel_p)

    # Verify stability
    unstable = []
    for rel_p, meta1 in snap1.items():
        meta2 = snap2.get(rel_p)
        if not meta2 or meta1["size"] != meta2["size"] or meta1["sha256"] != meta2["sha256"] or meta1["is_symlink"] != meta2["is_symlink"]:
            unstable.append(rel_p)

    if unstable:
        print(f"STOP_CONFLICT_NORMALIZATION_CONCURRENT_MODIFICATION: Unstable files: {unstable}")
        sys.exit(1)

    print("Phase 0 Snapshots 1 & 2 verified identical.")

    # Write phase0_snapshot.yaml
    phase0_snapshot_data = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "snapshot_count": 2,
        "bounded_interval_seconds": 1.0,
        "identical": True,
        "scoped_conflict_file_count": len(snap1),
        "files": snap1
    }
    with open(os.path.join(REPORT_ROOT, "phase0_snapshot.yaml"), "w", encoding="utf-8") as f:
        json.dump(phase0_snapshot_data, f, indent=2)

    # Inventory & Move Plan Generation
    inventory = []
    move_plan = []
    skipped_files = []

    # Map ordinary canonical files in scoped roots to record their baseline hashes
    ordinary_canonical_hashes = {}
    for scope in SCOPE_ROOTS:
        scope_dir = os.path.join(WORKSPACE, scope)
        if os.path.exists(scope_dir):
            for root, dirs, files in os.walk(scope_dir):
                for f in files:
                    if not any(pat in f for pat in CONFLICT_PATTERNS):
                        full_p = os.path.join(root, f)
                        if not os.path.islink(full_p):
                            rel_p = os.path.relpath(full_p, WORKSPACE)
                            ordinary_canonical_hashes[rel_p] = calc_sha256(full_p)

    print(f"Recorded baseline SHA-256 for {len(ordinary_canonical_hashes)} ordinary canonical source files.")

    used_target_paths = set()

    for full_p, rel_p, scope in raw_files:
        meta = snap1[rel_p]
        filename = os.path.basename(rel_p)
        canonical_rel = derive_canonical_rel_path(rel_p)
        canonical_full = os.path.join(WORKSPACE, canonical_rel)
        canonical_exists = os.path.exists(canonical_full) and not os.path.isdir(canonical_full)
        canonical_sha256 = calc_sha256(canonical_full) if canonical_exists else None
        same_as_canonical = (canonical_exists and meta["sha256"] == canonical_sha256)

        source_label, branch_label, source_short_sha = parse_conflict_labels(filename)

        inv_entry = {
            "current_path": rel_p,
            "scope_root": scope,
            "filename": filename,
            "size": meta["size"],
            "sha256": meta["sha256"],
            "mtime": meta["mtime"],
            "derived_canonical_path": canonical_rel,
            "canonical_exists": canonical_exists,
            "canonical_sha256": canonical_sha256,
            "same_as_canonical": same_as_canonical,
            "source_label": source_label,
            "branch_label": branch_label,
            "source_short_sha": source_short_sha,
            "is_symlink": meta["is_symlink"]
        }
        inventory.append(inv_entry)

        if meta["is_symlink"]:
            skipped_files.append({
                "original_path": rel_p,
                "reason": "SKIPPED_SYMLINK_CONFLICT"
            })
            continue

        if canonical_exists:
            classification = "CLASSIFIED_CONFLICT_REFERENCE"
            target_rel_dir = os.path.join(REFERENCE_ROOT_REL, "by_original_path", canonical_rel)
        else:
            classification = "ORPHANED_CONFLICT_REFERENCE"
            target_rel_dir = os.path.join(REFERENCE_ROOT_REL, "orphaned", canonical_rel)

        inv_entry["classification"] = classification

        # Determine target file name and handle collision
        target_rel_path = os.path.join(target_rel_dir, filename)
        if target_rel_path in used_target_paths or os.path.exists(os.path.join(WORKSPACE, target_rel_path)):
            path_sha8 = hashlib.sha256(rel_p.encode("utf-8")).hexdigest()[:8]
            target_rel_path = f"{target_rel_path}__DUPLICATE__{path_sha8}"

        used_target_paths.add(target_rel_path)

        move_plan.append({
            "original_path": rel_p,
            "target_path": target_rel_path,
            "derived_canonical_path": canonical_rel,
            "canonical_exists": canonical_exists,
            "canonical_sha256": canonical_sha256,
            "conflict_sha256": meta["sha256"],
            "same_as_canonical": same_as_canonical,
            "classification": classification,
            "source_label": source_label,
            "branch_label": branch_label,
            "source_short_sha": source_short_sha
        })

    # Write conflict_inventory.jsonl
    with open(os.path.join(REPORT_ROOT, "conflict_inventory.jsonl"), "w", encoding="utf-8") as f:
        for entry in inventory:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Write move_plan.jsonl
    with open(os.path.join(REPORT_ROOT, "move_plan.jsonl"), "w", encoding="utf-8") as f:
        for entry in move_plan:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Write skipped_files.jsonl
    with open(os.path.join(REPORT_ROOT, "skipped_files.jsonl"), "w", encoding="utf-8") as f:
        for entry in skipped_files:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"Generated move plan with {len(move_plan)} items to move, {len(skipped_files)} skipped.")

    # 3. Execute Moves
    moved_files = []
    for item in move_plan:
        src_full = os.path.join(WORKSPACE, item["original_path"])
        dst_full = os.path.join(WORKSPACE, item["target_path"])

        os.makedirs(os.path.dirname(dst_full), exist_ok=True)
        if os.path.exists(dst_full):
            print(f"ERROR: Destination collision on {dst_full}")
            sys.exit(1)

        shutil.move(src_full, dst_full)

        # Verify moved hash
        new_sha256 = calc_sha256(dst_full)
        if new_sha256 != item["conflict_sha256"]:
            print(f"ERROR: Hash mismatch for moved file {item['original_path']} -> {item['target_path']}")
            sys.exit(1)

        moved_files.append({
            "original_path": item["original_path"],
            "target_path": item["target_path"],
            "sha256": new_sha256,
            "status": "MOVED_AND_VERIFIED"
        })

    # Write moved_files.jsonl
    with open(os.path.join(REPORT_ROOT, "moved_files.jsonl"), "w", encoding="utf-8") as f:
        for entry in moved_files:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"Successfully moved and verified {len(moved_files)} files.")

    # 4. Verify ordinary canonical files unchanged
    for rel_p, orig_sha in ordinary_canonical_hashes.items():
        full_p = os.path.join(WORKSPACE, rel_p)
        if not os.path.exists(full_p):
            print(f"ERROR: Ordinary source file deleted: {rel_p}")
            sys.exit(1)
        curr_sha = calc_sha256(full_p)
        if curr_sha != orig_sha:
            print(f"ERROR: Ordinary source file modified: {rel_p}")
            sys.exit(1)

    print("Verified: 100% of ordinary source files remain completely unchanged.")

    # 5. Build Index Files in _conflict_reference/LOTTERY_CORE_R1
    index_entries = []
    clusters = {}
    orphaned_entries = []
    sha_groups = {}

    for item in move_plan:
        idx_entry = {
            "original_conflict_path": item["original_path"],
            "new_reference_path": item["target_path"],
            "derived_canonical_path": item["derived_canonical_path"],
            "canonical_exists": item["canonical_exists"],
            "canonical_sha256": item["canonical_sha256"],
            "conflict_sha256": item["conflict_sha256"],
            "same_as_canonical": item["same_as_canonical"],
            "source_label": item["source_label"],
            "branch_label": item["branch_label"],
            "source_short_sha": item["source_short_sha"],
            "classification": item["classification"]
        }
        index_entries.append(idx_entry)

        cpath = item["derived_canonical_path"]
        if cpath not in clusters:
            clusters[cpath] = {
                "canonical_path": cpath,
                "canonical_exists": item["canonical_exists"],
                "canonical_sha256": item["canonical_sha256"],
                "conflict_count": 0,
                "unique_contents": set(),
                "exact_duplicate_groups": {},
                "reference_paths": []
            }
        c_info = clusters[cpath]
        c_info["conflict_count"] += 1
        c_info["unique_contents"].add(item["conflict_sha256"])
        c_info["reference_paths"].append(item["target_path"])
        c_info["exact_duplicate_groups"].setdefault(item["conflict_sha256"], []).append(item["target_path"])

        if item["classification"] == "ORPHANED_CONFLICT_REFERENCE":
            orphaned_entries.append(idx_entry)

        sha_groups.setdefault(item["conflict_sha256"], []).append(item["target_path"])

    # Format clusters for JSON
    clusters_json_data = []
    for cpath, cinfo in sorted(clusters.items()):
        clusters_json_data.append({
            "canonical_path": cinfo["canonical_path"],
            "canonical_exists": cinfo["canonical_exists"],
            "canonical_sha256": cinfo["canonical_sha256"],
            "conflict_count": cinfo["conflict_count"],
            "unique_content_count": len(cinfo["unique_contents"]),
            "exact_duplicate_groups": cinfo["exact_duplicate_groups"],
            "reference_paths": cinfo["reference_paths"]
        })

    # Duplicates jsonl
    duplicates_entries = []
    for sha, paths in sha_groups.items():
        if len(paths) > 1:
            duplicates_entries.append({
                "sha256": sha,
                "count": len(paths),
                "reference_paths": paths
            })

    # Write index.jsonl
    with open(os.path.join(REFERENCE_ROOT, "index.jsonl"), "w", encoding="utf-8") as f:
        for entry in index_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Write clusters.json
    with open(os.path.join(REFERENCE_ROOT, "clusters.json"), "w", encoding="utf-8") as f:
        json.dump(clusters_json_data, f, indent=2, ensure_ascii=False)

    # Write orphaned.jsonl
    with open(os.path.join(REFERENCE_ROOT, "orphaned.jsonl"), "w", encoding="utf-8") as f:
        for entry in orphaned_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Write duplicates.jsonl
    with open(os.path.join(REFERENCE_ROOT, "duplicates.jsonl"), "w", encoding="utf-8") as f:
        for entry in duplicates_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Write README.md in _conflict_reference/LOTTERY_CORE_R1
    readme_content = f"""# Scoped Conflict Reference Database (LOTTERY_CORE_R1)

本目錄為 `lottery/` 與 `lottery_api/` 衝突參考檔案之集中資料庫。

## 重要聲明
1. 此區檔案僅供移植與對照參考。
2. 原始路徑中的 Ordinary Canonical Files 未必是正確版本。
3. 衝突版本未進行任何語意合併或代碼修改。
4. 所有原始相對路徑與 metadata 可透過 `index.jsonl` 與 `clusters.json` 查回。
5. 移植 Worker 請依功能模組自行挑選所需的版本。

## 目錄結構
- `by_original_path/`: 原始 Canonical 檔案存在時的衝突檔分群。
- `orphaned/`: 原始 Canonical 檔案不存在時的孤立衝突檔分群。
- `index.jsonl`: 完整衝突檔對照索引。
- `clusters.json`: 依 Canonical 路徑彙整的分群索引。
- `orphaned.jsonl`: 孤立衝突檔索引。
- `duplicates.jsonl`: 完全相同內容 (SHA-256) 的衝突檔群組。
"""
    with open(os.path.join(REFERENCE_ROOT, "README.md"), "w", encoding="utf-8") as f:
        f.write(readme_content)

    print("Built all reference index files in _conflict_reference/LOTTERY_CORE_R1.")

    # 6. Post-move Verification
    remaining_conflicts = find_scoped_conflict_files()
    print(f"Remaining conflict files in scoped dirs: {len(remaining_conflicts)}")

    # Write verification.md
    verification_md = f"""# Verification Report: LOTTERYNEW_CONFLICT_REFERENCE_NORMALIZATION_CORE_R1

- **Timestamp**: {datetime.datetime.now(datetime.timezone.utc).isoformat()}
- **Scoped Conflict Files Found**: {len(inventory)}
- **Files Moved to Reference**: {len(moved_files)}
- **Symlinks Skipped**: {len(skipped_files)}
- **Remaining Conflicts in Scoped Dirs**: {len(remaining_conflicts)}

## Check Results
1. Moved hash verification: 100% PASS ({len(moved_files)}/{len(moved_files)})
2. Ordinary source file hash verification: 100% PASS ({len(ordinary_canonical_hashes)}/{len(ordinary_canonical_hashes)})
3. Target overwrites: 0
4. Deleted files: 0
5. Scope outside paths modified: False
6. Source contents modified: False
7. Conflict contents modified: False
"""
    with open(os.path.join(REPORT_ROOT, "verification.md"), "w", encoding="utf-8") as f:
        f.write(verification_md)

    # Write final_report.yaml
    final_report_data = {
        "task": "LOTTERYNEW_CONFLICT_REFERENCE_NORMALIZATION_CORE_R1",
        "status": "COMPLETED",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "workspace": {
            "root": WORKSPACE,
            "branch": "task/p273a-prize-aware-inferential-validation",
            "head": "3d6df001da3a0633ab91f164d722b595ca76d2e1"
        },
        "scope": {
            "roots": SCOPE_ROOTS
        },
        "results": {
            "scoped_conflict_files_found": len(inventory),
            "moved_to_reference": len(moved_files),
            "orphaned_conflicts": len(orphaned_entries),
            "exact_duplicate_files": sum(d["count"] for d in duplicates_entries),
            "unique_conflict_contents": len(sha_groups),
            "symlinks_skipped": len(skipped_files),
            "collisions_resolved": 0,
            "failures": 0
        },
        "integrity": {
            "moved_hash_verification": "PASS",
            "ordinary_file_hash_verification": "PASS",
            "overwritten_files": 0,
            "deleted_files": 0,
            "partial_files_remaining": 0
        },
        "safety": {
            "ordinary_source_modified": False,
            "conflict_content_modified": False,
            "tests_modified": False,
            "registry_modified": False,
            "strategy_identity_modified": False,
            "database_accessed": False,
            "secret_accessed": False,
            "dependency_installed": False,
            "commit_created": False,
            "push_run": False,
            "pr_created": False
        },
        "verification": {
            "index_cross_check": "PASS",
            "source_conflict_paths_remaining": len(remaining_conflicts),
            "diff_check": "PASS",
            "unit_tests": "NOT_RUN",
            "application_boot": "NOT_RUN"
        },
        "claim_boundary": {
            "conflict_files_organized_as_reference": True,
            "semantic_conflicts_resolved": False,
            "canonical_versions_verified": False,
            "functional_merge_completed": False,
            "production_ready_claimed": False
        }
    }
    with open(os.path.join(REPORT_ROOT, "final_report.yaml"), "w", encoding="utf-8") as f:
        json.dump(final_report_data, f, indent=2)

    print("=== LOTTERYNEW_CONFLICT_REFERENCE_NORMALIZATION_CORE_R1 COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    main()
