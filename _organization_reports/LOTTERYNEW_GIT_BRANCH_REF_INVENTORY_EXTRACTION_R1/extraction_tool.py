#!/usr/bin/env python3
"""
LOTTERYNEW_GIT_BRANCH_REF_INVENTORY_EXTRACTION_R1 - Extraction Tool
Extracts unmaterialized ref delta content into isolated reference store,
applies sensitive/DB exclusions, computes blob SHA-256 store, and performs
target coverage comparison against target workspace.
"""

import os
import sys
import json
import re
import subprocess
import shutil
import hashlib
import fnmatch
from pathlib import Path

TARGET_WORKSPACE = "/Users/kelvin/VibeCoding-WorkSpace/LotteryNewMeraged"
REPORT_DIR = os.path.join(TARGET_WORKSPACE, "_organization_reports/LOTTERYNEW_GIT_BRANCH_REF_INVENTORY_EXTRACTION_R1")
REF_BASE_DIR = os.path.join(TARGET_WORKSPACE, "_git_ref_reference/LOTTERY_BRANCH_REF_EXTRACTION_R1")

ELIGIBLE_EXTENSIONS = {
    '.py', '.pyi', '.js', '.jsx', '.ts', '.tsx', '.vue', '.svelte',
    '.java', '.kt', '.go', '.rs', '.c', '.cc', '.cpp', '.h', '.hpp',
    '.cs', '.rb', '.php', '.sh', '.bash', '.zsh', '.ps1', '.sql',
    '.proto', '.graphql', '.toml', '.yaml', '.yml', '.json', '.ini',
    '.cfg', '.conf', '.md', '.txt'
}

SENSITIVE_REGEX = re.compile(
    r'(\.env(\..*)?|\.pem$|\.key$|\.p12$|\.pfx$|^id_rsa|^id_ed25519|^credentials|^credential|^secret|^secrets|^token|^service-account)',
    re.IGNORECASE
)

DATABASE_REGEX = re.compile(
    r'(\.db$|\.sqlite$|\.sqlite3$|\.duckdb$|\.mdb$|\.accdb$|\.parquet$|\.csv$|\.tsv$|\.xlsx$|\.xls$|\.dump$|\.bak$)',
    re.IGNORECASE
)

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB

def run_cmd(cmd, cwd=None, env=None, timeout=60):
    cmd_env = os.environ.copy()
    cmd_env["GIT_TERMINAL_PROMPT"] = "0"
    cmd_env["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes -o ConnectTimeout=5"
    if env:
        cmd_env.update(env)
    try:
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=cmd_env, timeout=timeout)
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout expired"
    except Exception as e:
        return -1, "", str(e)

def run_cmd_bytes(cmd, cwd=None, timeout=60):
    cmd_env = os.environ.copy()
    cmd_env["GIT_TERMINAL_PROMPT"] = "0"
    cmd_env["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes -o ConnectTimeout=5"
    try:
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, env=cmd_env, timeout=timeout)
        return res.returncode, res.stdout, res.stderr
    except Exception as e:
        return -1, b"", str(e).encode()

def is_sensitive(filepath):
    basename = os.path.basename(filepath)
    return bool(SENSITIVE_REGEX.search(filepath) or SENSITIVE_REGEX.search(basename))

def is_database(filepath):
    basename = os.path.basename(filepath)
    return bool(DATABASE_REGEX.search(filepath) or DATABASE_REGEX.search(basename))

def is_eligible_file(path):
    basename = os.path.basename(path)
    ext = os.path.splitext(path)[1].lower()

    if ext in ELIGIBLE_EXTENSIONS:
        return True
    if basename.startswith("Dockerfile") or basename == "Makefile":
        return True
    if basename in ["pyproject.toml", "package.json"]:
        return True
    if fnmatch.fnmatch(basename, "requirements*.txt"):
        return True
    return False

def sanitize_ref_id(ref_name):
    # Create clean directory name for ref
    clean = re.sub(r'[^a-zA-Z0-9_\-]', '_', ref_name)
    h = hashlib.sha256(ref_name.encode('utf-8')).hexdigest()[:8]
    return f"{clean[:40]}_{h}"

def main():
    print("=== Starting Ref Content Extraction & Coverage Comparison ===")

    # Load extraction plan
    plan_file = os.path.join(REPORT_DIR, "extraction_plan.jsonl")
    if not os.path.exists(plan_file):
        print(f"Error: {plan_file} not found. Run inventory_tool.py first.")
        sys.exit(1)

    plan_entries = []
    with open(plan_file, "r") as f:
        for line in f:
            if line.strip():
                plan_entries.append(json.loads(line))

    print(f"Loaded {len(plan_entries)} extraction plan targets.")

    sensitive_skipped = []
    large_binary_skipped = []
    extraction_results = []

    total_extracted_files = 0
    total_extracted_bytes = 0
    unique_blobs = set()
    submodule_entries_count = 0
    lfs_pointer_entries_count = 0

    global_coverage_counts = {
        'same_path_same_content': 0,
        'same_path_different_content': 0,
        'target_path_missing': 0,
        'target_path_is_directory': 0,
        'skipped_sensitive': 0,
        'skipped_large': 0,
        'deleted_in_ref': 0,
        'renamed_paths': 0
    }

    blob_store_dir = os.path.join(REF_BASE_DIR, "blob_store")
    blob_cache = {}

    for plan in plan_entries:
        repo_id = plan['repository_id']
        rep_ref = plan['representative_ref']
        tree_oid = plan['tree_oid']
        commit_oid = plan['peeled_commit_oid']
        merge_base_tree = plan['merge_base_tree']
        mode = plan['extraction_mode']
        mirror_path = os.path.join(REF_BASE_DIR, "mirrors", f"{repo_id}.git")

        ref_id = sanitize_ref_id(rep_ref)
        ref_dir = os.path.join(REF_BASE_DIR, "by_repository", repo_id, "by_ref", ref_id)
        files_dir = os.path.join(ref_dir, "files")
        os.makedirs(files_dir, exist_ok=True)

        print(f"\nExtracting Ref: {rep_ref} (Repo: {repo_id}, Mode: {mode}, Tree: {tree_oid[:8]})...")

        # 1. Full Tree Manifest
        # git ls-tree -r -z -l --full-name <tree_oid>
        code_lst, out_lst, _ = run_cmd_bytes(['git', '-C', mirror_path, 'ls-tree', '-r', '-z', '-l', '--full-name', tree_oid])
        tree_manifest_entries = []
        
        if code_lst == 0 and out_lst:
            # Output format with -l: <mode> <type> <object> <size>\t<file>\0 (or - for commit/tree size)
            raw_entries = out_lst.split(b'\0')
            for entry in raw_entries:
                if not entry:
                    continue
                try:
                    meta, filepath_bytes = entry.split(b'\t', 1)
                    filepath = filepath_bytes.decode('utf-8', errors='replace')
                    meta_parts = meta.decode('utf-8').split()
                    if len(meta_parts) >= 3:
                        fmode = meta_parts[0]
                        ftype = meta_parts[1]
                        foid = meta_parts[2]
                        fsize = int(meta_parts[3]) if len(meta_parts) >= 4 and meta_parts[3] != '-' else 0
                        is_submodule = (fmode == '160000' or ftype == 'commit')
                        if is_submodule:
                            submodule_entries_count += 1

                        tree_manifest_entries.append({
                            'path': filepath,
                            'mode': fmode,
                            'object_type': ftype,
                            'blob_oid': foid,
                            'size': fsize,
                            'is_submodule': is_submodule
                        })
                except Exception as e:
                    pass

        # Write tree_manifest.jsonl
        with open(os.path.join(ref_dir, "tree_manifest.jsonl"), "w") as f:
            for tme in tree_manifest_entries:
                f.write(json.dumps(tme, ensure_ascii=False) + "\n")

        # Build dictionary map for O(1) path lookups
        tree_map = {tm['path']: tm for tm in tree_manifest_entries}

        # 2. Delta Manifest
        delta_entries = []
        if mode == "BRANCH_DELTA" and merge_base_tree:
            code_diff, out_diff, _ = run_cmd_bytes(['git', '-C', mirror_path, 'diff-tree', '-r', '-z', '--name-status', merge_base_tree, tree_oid])
            if code_diff == 0 and out_diff:
                raw_diff = out_diff.split(b'\0')
                idx = 0
                while idx < len(raw_diff):
                    status_bytes = raw_diff[idx]
                    if not status_bytes:
                        idx += 1
                        continue
                    status = status_bytes.decode('utf-8', errors='replace')
                    idx += 1
                    if idx >= len(raw_diff):
                        break
                    
                    if status.startswith('R') or status.startswith('C'):
                        old_path = raw_diff[idx].decode('utf-8', errors='replace')
                        idx += 1
                        new_path = raw_diff[idx].decode('utf-8', errors='replace') if idx < len(raw_diff) else ""
                        idx += 1
                        filepath = new_path
                    else:
                        old_path = ""
                        filepath = raw_diff[idx].decode('utf-8', errors='replace')
                        idx += 1

                    # Look up in tree manifest if not deleted (O(1) dict lookup)
                    foid = ""
                    fmode = ""
                    fsize = 0
                    if not status.startswith('D'):
                        tm = tree_map.get(filepath)
                        if tm:
                            foid = tm['blob_oid']
                            fmode = tm['mode']
                            fsize = tm['size']

                    delta_entries.append({
                        'status': status,
                        'path': filepath,
                        'old_path': old_path,
                        'blob_oid': foid,
                        'mode': fmode,
                        'size': fsize
                    })
        else:
            # Full tree treated as ADDED
            for tm in tree_manifest_entries:
                if tm['object_type'] == 'blob':
                    delta_entries.append({
                        'status': 'A',
                        'path': tm['path'],
                        'old_path': '',
                        'blob_oid': tm['blob_oid'],
                        'mode': tm['mode'],
                        'size': tm['size']
                    })

        # Write delta_manifest.jsonl
        with open(os.path.join(ref_dir, "delta_manifest.jsonl"), "w") as f:
            for de in delta_entries:
                f.write(json.dumps(de, ensure_ascii=False) + "\n")

        # 3. Extract Eligible Delta Files & Perform Target Coverage Comparison
        ref_coverage = {
            'same_content': 0,
            'different_content': 0,
            'missing_paths': 0,
            'deleted_in_ref': 0,
            'renamed_paths': 0,
            'skipped_sensitive': 0,
            'skipped_large': 0
        }

        extracted_files_in_ref = 0
        extracted_bytes_in_ref = 0

        for de in delta_entries:
            st = de['status']
            filepath = de['path']
            foid = de['blob_oid']
            fsize = de['size']

            if st.startswith('D'):
                ref_coverage['deleted_in_ref'] += 1
                global_coverage_counts['deleted_in_ref'] += 1
                continue
            if st.startswith('R'):
                ref_coverage['renamed_paths'] += 1
                global_coverage_counts['renamed_paths'] += 1

            # Check sensitive patterns
            if is_sensitive(filepath):
                ref_coverage['skipped_sensitive'] += 1
                global_coverage_counts['skipped_sensitive'] += 1
                sensitive_skipped.append({
                    'repository_id': repo_id,
                    'ref_name': rep_ref,
                    'path': filepath,
                    'blob_oid': foid,
                    'size': fsize,
                    'classification': 'SENSITIVE_KEY_OR_CREDENTIAL',
                    'content_extracted': False
                })
                continue

            # Check DB patterns
            if is_database(filepath):
                ref_coverage['skipped_large'] += 1
                global_coverage_counts['skipped_large'] += 1
                large_binary_skipped.append({
                    'repository_id': repo_id,
                    'ref_name': rep_ref,
                    'path': filepath,
                    'blob_oid': foid,
                    'size': fsize,
                    'classification': 'DATABASE_OR_DATA_FILE',
                    'content_extracted': False
                })
                continue

            # Check file size limit (> 25MB)
            if fsize > MAX_FILE_SIZE:
                ref_coverage['skipped_large'] += 1
                global_coverage_counts['skipped_large'] += 1
                large_binary_skipped.append({
                    'repository_id': repo_id,
                    'ref_name': rep_ref,
                    'path': filepath,
                    'blob_oid': foid,
                    'size': fsize,
                    'classification': 'MANIFEST_ONLY_LARGE_FILE',
                    'content_extracted': False
                })
                continue

            # Scope check
            if not is_eligible_file(filepath):
                continue

            # Extract blob content (using memory cache)
            if foid in blob_cache:
                blob_bytes = blob_cache[foid]
            else:
                code_cat, blob_bytes, _ = run_cmd_bytes(['git', '-C', mirror_path, 'cat-file', 'blob', foid])
                if code_cat != 0:
                    continue
                blob_cache[foid] = blob_bytes

            # Check if Git LFS pointer
            if blob_bytes.startswith(b'version https://git-lfs.github.com/spec/v1'):
                lfs_pointer_entries_count += 1

            sha256 = hashlib.sha256(blob_bytes).hexdigest()
            unique_blobs.add(sha256)

            # Store in content-addressable blob_store
            blob_sub_dir = os.path.join(blob_store_dir, sha256[:2])
            os.makedirs(blob_sub_dir, exist_ok=True)
            blob_path = os.path.join(blob_sub_dir, sha256)
            if not os.path.exists(blob_path):
                with open(blob_path, "wb") as bf:
                    bf.write(blob_bytes)

            # Write file to per-ref files/ directory
            out_file_path = os.path.join(files_dir, filepath)
            os.makedirs(os.path.dirname(out_file_path), exist_ok=True)
            with open(out_file_path, "wb") as f:
                f.write(blob_bytes)

            extracted_files_in_ref += 1
            extracted_bytes_in_ref += len(blob_bytes)
            total_extracted_files += 1
            total_extracted_bytes += len(blob_bytes)

            # Target Coverage Comparison against TARGET_WORKSPACE
            target_file_path = os.path.join(TARGET_WORKSPACE, filepath)
            if os.path.isdir(target_file_path):
                ref_coverage['missing_paths'] += 1
                global_coverage_counts['target_path_is_directory'] += 1
            elif not os.path.exists(target_file_path):
                ref_coverage['missing_paths'] += 1
                global_coverage_counts['target_path_missing'] += 1
            else:
                try:
                    with open(target_file_path, "rb") as tf:
                        target_bytes = tf.read()
                    if target_bytes == blob_bytes:
                        ref_coverage['same_content'] += 1
                        global_coverage_counts['same_path_same_content'] += 1
                    else:
                        ref_coverage['different_content'] += 1
                        global_coverage_counts['same_path_different_content'] += 1
                except Exception:
                    ref_coverage['different_content'] += 1
                    global_coverage_counts['same_path_different_content'] += 1

        # Write ref_metadata.json & target_coverage.json for this ref
        ref_metadata = {
            'repository_id': repo_id,
            'representative_ref': rep_ref,
            'all_matching_refs': plan['all_matching_refs'],
            'tree_oid': tree_oid,
            'peeled_commit_oid': commit_oid,
            'extraction_mode': mode,
            'extracted_files_count': extracted_files_in_ref,
            'extracted_bytes': extracted_bytes_in_ref,
            'coverage_summary': ref_coverage
        }
        with open(os.path.join(ref_dir, "ref_metadata.json"), "w") as f:
            json.dump(ref_metadata, f, indent=2, ensure_ascii=False)

        with open(os.path.join(ref_dir, "target_coverage.json"), "w") as f:
            json.dump(ref_coverage, f, indent=2, ensure_ascii=False)

        extraction_results.append(ref_metadata)

    # Write skipped files outputs
    with open(os.path.join(REPORT_DIR, "sensitive_paths_skipped.jsonl"), "w") as f:
        for s in sensitive_skipped:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    with open(os.path.join(REPORT_DIR, "large_or_binary_paths_skipped.jsonl"), "w") as f:
        for l in large_binary_skipped:
            f.write(json.dumps(l, ensure_ascii=False) + "\n")

    with open(os.path.join(REPORT_DIR, "extraction_results.jsonl"), "w") as f:
        for er in extraction_results:
            f.write(json.dumps(er, ensure_ascii=False) + "\n")

    with open(os.path.join(REPORT_DIR, "target_coverage_summary.json"), "w") as f:
        json.dump(global_coverage_counts, f, indent=2, ensure_ascii=False)

    print("\n=== Extraction & Coverage Summary ===")
    print(f"Total Extracted Files: {total_extracted_files}")
    print(f"Total Extracted Bytes: {total_extracted_bytes} bytes ({total_extracted_bytes / (1024*1024):.2f} MB)")
    print(f"Unique SHA-256 Blobs in Store: {len(unique_blobs)}")
    print(f"Sensitive Paths Skipped: {len(sensitive_skipped)}")
    print(f"Large/DB Paths Skipped: {len(large_binary_skipped)}")
    print(f"Submodule Entries Recorded: {submodule_entries_count}")
    print(f"LFS Pointer Entries Recorded: {lfs_pointer_entries_count}")
    print("Target Coverage Counts:")
    for k, v in global_coverage_counts.items():
        print(f"  {k}: {v}")

    print("=== Extraction Complete ===")

if __name__ == "__main__":
    main()
