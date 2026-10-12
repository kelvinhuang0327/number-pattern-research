#!/usr/bin/env python3
"""
LOTTERYNEW_GIT_BRANCH_REF_INVENTORY_EXTRACTION_R1 - Inventory Tool
Performs discovery of Lottery repositories, parses local & remote advertised refs,
constructs isolated bare mirrors, classifies materialization, deduplicates trees,
and prepares extraction plan.
"""

import os
import sys
import json
import re
import subprocess
import shutil
import hashlib
from pathlib import Path

SOURCE_ROOT = "/Users/kelvin/Kelvin-WorkSpace"
TARGET_WORKSPACE = "/Users/kelvin/VibeCoding-WorkSpace/LotteryNewMeraged"
REPORT_DIR = os.path.join(TARGET_WORKSPACE, "_organization_reports/LOTTERYNEW_GIT_BRANCH_REF_INVENTORY_EXTRACTION_R1")
REF_BASE_DIR = os.path.join(TARGET_WORKSPACE, "_git_ref_reference/LOTTERY_BRANCH_REF_EXTRACTION_R1")

KEYWORDS = ["lottery", "lotto", "lottolab", "biglotto", "powerlotto", "number-pattern", "number_pattern"]

def sanitize_url(url: str) -> str:
    if not url:
        return ""
    # Strip user:pass@ or tokens from http/https/git URLs
    sanitized = re.sub(r'https?://([^:]+):([^@]+)@', 'https://***:***@', url)
    sanitized = re.sub(r'https?://([^@]+)@', 'https://***@', sanitized)
    return sanitized

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

def discover_repositories():
    git_paths = []
    for dirpath, dirnames, filenames in os.walk(SOURCE_ROOT):
        if '.git' in dirnames or '.git' in filenames:
            if '.git' in dirnames:
                dirnames.remove('.git')
            git_paths.append(dirpath)

    discovered = []
    for gp in git_paths:
        gp_lower = gp.lower()
        match_path = any(kw in gp_lower for kw in KEYWORDS)
        
        remotes = []
        code, out, err = run_cmd(['git', '-C', gp, 'remote', '-v'])
        if code == 0:
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    remotes.append((parts[0], parts[1]))
        
        match_remote = any(any(kw in url.lower() for kw in KEYWORDS) for _, url in remotes)
        
        match_meta = False
        if os.path.isdir(gp):
            for rf in os.listdir(gp):
                if rf.lower().startswith('readme'):
                    try:
                        with open(os.path.join(gp, rf), 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read(2000).lower()
                            if any(kw in content for kw in KEYWORDS) or '彩券' in content or '樂透' in content:
                                match_meta = True
                                break
                    except Exception:
                        pass

        is_candidate = match_path or match_remote or match_meta
        if not is_candidate:
            continue

        # Resolve git dir & common dir
        code1, out1, _ = run_cmd(['git', '-C', gp, 'rev-parse', '--git-dir'])
        git_dir = os.path.abspath(os.path.join(gp, out1.strip())) if code1 == 0 else ""
        
        code2, out2, _ = run_cmd(['git', '-C', gp, 'rev-parse', '--path-format=absolute', '--git-common-dir'])
        git_common_dir = os.path.abspath(out2.strip()) if code2 == 0 else ""

        # Handle broken/pruned linked worktrees if rev-parse failed
        if not git_common_dir and os.path.isfile(os.path.join(gp, '.git')):
            try:
                with open(os.path.join(gp, '.git'), 'r') as f:
                    txt = f.read().strip()
                    if txt.startswith('gitdir:'):
                        gdir_path = txt.split(':', 1)[1].strip()
                        if not os.path.isabs(gdir_path):
                            gdir_path = os.path.abspath(os.path.join(gp, gdir_path))
                        git_dir = gdir_path
                        # Infer common dir
                        if '/.git/worktrees/' in gdir_path:
                            git_common_dir = gdir_path.split('/.git/worktrees/')[0] + '/.git'
            except Exception:
                pass

        if not git_common_dir and git_dir:
            git_common_dir = git_dir

        discovered.append({
            'path': gp,
            'match_path': match_path,
            'match_remote': match_remote,
            'match_meta': match_meta,
            'git_dir': git_dir,
            'git_common_dir': git_common_dir,
            'remotes': [{'name': name, 'raw_url': url, 'url': sanitize_url(url)} for name, url in set(remotes)]
        })

    return discovered

def main():
    print("=== Starting Discovery & Ref Inventory ===")
    os.makedirs(REPORT_DIR, exist_ok=True)
    os.makedirs(os.path.join(REF_BASE_DIR, "mirrors"), exist_ok=True)
    os.makedirs(os.path.join(REF_BASE_DIR, "by_repository"), exist_ok=True)
    os.makedirs(os.path.join(REF_BASE_DIR, "blob_store"), exist_ok=True)

    discovered = discover_repositories()
    print(f"Discovered {len(discovered)} worktree/repo paths matching Lottery candidates.")

    # Deduplicate by git_common_dir
    common_dir_map = {}
    for d in discovered:
        gcd = d['git_common_dir']
        if not gcd:
            continue
        if gcd not in common_dir_map:
            common_dir_map[gcd] = []
        common_dir_map[gcd].append(d)

    # Assign deterministic repository_id
    repositories = []
    repo_counter = 1
    for gcd, paths in sorted(common_dir_map.items()):
        # Primary path preference: shorter path, non-worktree
        primary_path = sorted(paths, key=lambda x: (len(x['path']), x['path']))[0]['path']
        
        # Name hint
        base_name = os.path.basename(primary_path)
        if base_name in ['.git', 'LotteryNew']:
            repo_id = f"repo_{repo_counter}_lotterynew"
        else:
            repo_id = f"repo_{repo_counter}_{base_name.replace('-', '_').replace('.', '_')}"
        repo_counter += 1

        # Check remotes
        remotes_dict = {}
        for p in paths:
            for r in p['remotes']:
                remotes_dict[r['name']] = r['url']

        # Get object format & bare status
        code_fmt, out_fmt, _ = run_cmd(['git', '--git-dir=' + gcd, 'rev-parse', '--show-object-format'])
        obj_fmt = out_fmt.strip() if code_fmt == 0 else "sha1"

        code_bare, out_bare, _ = run_cmd(['git', '--git-dir=' + gcd, 'rev-parse', '--is-bare-repository'])
        is_bare = out_bare.strip() == "true" if code_bare == 0 else False

        # Worktree inventory
        worktree_list = []
        dirty_worktrees = []
        current_heads = set()

        for p in paths:
            wpath = p['path']
            code_head, out_head, _ = run_cmd(['git', '-C', wpath, 'rev-parse', 'HEAD'])
            head_oid = out_head.strip() if code_head == 0 else ""
            if head_oid:
                current_heads.add(head_oid)

            code_br, out_br, _ = run_cmd(['git', '-C', wpath, 'branch', '--show-current'])
            branch_name = out_br.strip() if code_br == 0 else ""

            code_st, out_st, _ = run_cmd(['git', '-C', wpath, 'status', '--porcelain=v1'])
            is_dirty = bool(out_st.strip()) if code_st == 0 else False
            if is_dirty:
                dirty_worktrees.append(wpath)

            worktree_list.append({
                'path': wpath,
                'head_oid': head_oid,
                'branch': branch_name,
                'is_bare': is_bare,
                'is_detached': not bool(branch_name),
                'is_dirty': is_dirty
            })

        repo_info = {
            'repository_id': repo_id,
            'git_common_dir': gcd,
            'primary_path': primary_path,
            'repository_paths': [p['path'] for p in paths],
            'bare': is_bare,
            'remotes': [{'name': k, 'url': v} for k, v in remotes_dict.items()],
            'current_worktrees': worktree_list,
            'current_heads': sorted(list(current_heads)),
            'dirty_worktrees': dirty_worktrees,
            'object_format': obj_fmt
        }
        repositories.append(repo_info)

    # Add Target Workspace HEAD to known materialized worktree HEADs
    all_known_worktree_heads = set()
    all_known_worktree_trees = set()

    code_t_head, out_t_head, _ = run_cmd(['git', '-C', TARGET_WORKSPACE, 'rev-parse', 'HEAD'])
    target_head_oid = out_t_head.strip() if code_t_head == 0 else "3d6df001da3a0633ab91f164d722b595ca76d2e1"
    all_known_worktree_heads.add(target_head_oid)

    code_t_tree, out_t_tree, _ = run_cmd(['git', '-C', TARGET_WORKSPACE, 'rev-parse', 'HEAD^{tree}'])
    if code_t_tree == 0 and out_t_tree.strip():
        all_known_worktree_trees.add(out_t_tree.strip())

    for r in repositories:
        for wt in r['current_worktrees']:
            if wt['head_oid']:
                all_known_worktree_heads.add(wt['head_oid'])
                # Get tree OID for worktree HEAD
                code_tree, out_tree, _ = run_cmd(['git', '--git-dir=' + r['git_common_dir'], 'rev-parse', wt['head_oid'] + '^{tree}'])
                if code_tree == 0 and out_tree.strip():
                    all_known_worktree_trees.add(out_tree.strip())

    # Write repository_discovery.jsonl & repository_deduplication.json
    with open(os.path.join(REPORT_DIR, "repository_discovery.jsonl"), "w") as f:
        for d in discovered:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    dedup_report = {
        'total_discovered_paths': len(discovered),
        'unique_repositories_count': len(repositories),
        'repositories': repositories
    }
    with open(os.path.join(REPORT_DIR, "repository_deduplication.json"), "w") as f:
        json.dump(dedup_report, f, indent=2, ensure_ascii=False)

    # Write worktree_inventory.jsonl
    with open(os.path.join(REPORT_DIR, "worktree_inventory.jsonl"), "w") as f:
        for r in repositories:
            for wt in r['current_worktrees']:
                item = dict(wt)
                item['repository_id'] = r['repository_id']
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Unique Lottery Repositories: {len(repositories)}")

    # Inventory Refs for each repository & construct isolated mirror
    all_refs = []
    remote_advertised_refs = []
    remote_failures = []

    for r in repositories:
        repo_id = r['repository_id']
        gcd = r['git_common_dir']
        mirror_path = os.path.join(REF_BASE_DIR, "mirrors", f"{repo_id}.git")

        print(f"Processing local refs and creating mirror for {repo_id} ({gcd})...")
        if os.path.exists(mirror_path):
            shutil.rmtree(mirror_path)
        run_cmd(['git', 'init', '--bare', mirror_path])

        # Fetch local refs into mirror
        code_fetch, out_fetch, err_fetch = run_cmd(['git', '-C', mirror_path, 'fetch', gcd,
            '+refs/heads/*:refs/local/heads/*',
            '+refs/tags/*:refs/local/tags/*',
            '+refs/remotes/*:refs/local/remotes/*'])
        if code_fetch != 0:
            print(f"Warning fetching local refs into mirror for {repo_id}: {err_fetch}")

        # Parse local refs using for-each-ref
        cmd_refs = ['git', '--git-dir=' + gcd, 'for-each-ref',
            '--format=%(refname)|%(objectname)|%(objecttype)|%(*objectname)|%(authorname)|%(authordate:iso8601)|%(committerdate:iso8601)|%(subject)|%(symref)']
        code_r, out_r, err_r = run_cmd(cmd_refs)
        
        repo_refs = []
        if code_r == 0:
            for line in out_r.splitlines():
                if not line.strip():
                    continue
                parts = line.split('|')
                if len(parts) < 9:
                    continue
                ref_name, obj_oid, obj_type, peeled_oid, author, author_date, commit_date, subject, symref = parts[:9]
                
                # Determine peeled commit OID and tree OID
                target_commit_oid = peeled_oid if (peeled_oid and obj_type == 'tag') else obj_oid
                
                tree_oid = ""
                if obj_type in ['commit', 'tag'] or target_commit_oid:
                    code_tr, out_tr, _ = run_cmd(['git', '-C', mirror_path, 'rev-parse', target_commit_oid + '^{tree}'])
                    if code_tr == 0:
                        tree_oid = out_tr.strip()

                namespace = "other"
                if ref_name.startswith("refs/heads/"):
                    namespace = "heads"
                elif ref_name.startswith("refs/remotes/"):
                    namespace = "remotes"
                elif ref_name.startswith("refs/tags/"):
                    namespace = "tags"
                elif ref_name.startswith("refs/stash"):
                    namespace = "stash"

                short_name = ref_name
                for prefix in ["refs/heads/", "refs/remotes/", "refs/tags/"]:
                    if ref_name.startswith(prefix):
                        short_name = ref_name[len(prefix):]
                        break

                ref_item = {
                    'repository_id': repo_id,
                    'ref_name': ref_name,
                    'ref_namespace': namespace,
                    'short_name': short_name,
                    'object_oid': obj_oid,
                    'peeled_commit_oid': target_commit_oid,
                    'tree_oid': tree_oid,
                    'object_type': obj_type,
                    'author_date': author_date,
                    'committer_date': commit_date,
                    'subject': subject,
                    'is_symbolic': bool(symref),
                    'is_annotated_tag': obj_type == 'tag'
                }
                repo_refs.append(ref_item)
                all_refs.append(ref_item)

        # Remote advertised refs
        for rm in r['remotes']:
            r_name = rm['name']
            r_url = rm['url']
            print(f"Checking remote ls-remote for {repo_id} ({r_name}: {r_url})...")
            code_ls, out_ls, err_ls = run_cmd(['git', 'ls-remote', '--symref', '--heads', '--tags', r_url], timeout=10)
            if code_ls == 0:
                for line in out_ls.splitlines():
                    if line.startswith('ref:') or not line.strip():
                        continue
                    parts = line.split()
                    if len(parts) == 2:
                        oid, rname = parts
                        remote_ref_item = {
                            'repository_id': repo_id,
                            'remote_name': r_name,
                            'remote_url': r_url,
                            'ref_name': rname,
                            'object_oid': oid
                        }
                        remote_advertised_refs.append(remote_ref_item)

                # Attempt fetch remote refs into mirror
                fetch_spec_heads = f"+refs/heads/*:refs/remote/{r_name}/heads/*"
                fetch_spec_tags = f"+refs/tags/*:refs/remote/{r_name}/tags/*"
                run_cmd(['git', '-C', mirror_path, 'fetch', r_url, fetch_spec_heads, fetch_spec_tags], timeout=15)
            else:
                remote_failures.append({
                    'repository_id': repo_id,
                    'remote_name': r_name,
                    'remote_url': r_url,
                    'remote_state': 'REMOTE_INVENTORY_BLOCKED',
                    'reason': err_ls.strip() or f"Exit code {code_ls}"
                })

        # Save per-repository repository.json & refs.jsonl
        repo_ref_dir = os.path.join(REF_BASE_DIR, "by_repository", repo_id)
        os.makedirs(repo_ref_dir, exist_ok=True)
        with open(os.path.join(repo_ref_dir, "repository.json"), "w") as f:
            json.dump(r, f, indent=2, ensure_ascii=False)
        with open(os.path.join(repo_ref_dir, "refs.jsonl"), "w") as f:
            for rf in repo_refs:
                f.write(json.dumps(rf, ensure_ascii=False) + "\n")

    # Write global local_ref_inventory.jsonl, remote_advertised_ref_inventory.jsonl, remote_failures.jsonl
    with open(os.path.join(REPORT_DIR, "local_ref_inventory.jsonl"), "w") as f:
        for rf in all_refs:
            f.write(json.dumps(rf, ensure_ascii=False) + "\n")

    with open(os.path.join(REPORT_DIR, "remote_advertised_ref_inventory.jsonl"), "w") as f:
        for rf in remote_advertised_refs:
            f.write(json.dumps(rf, ensure_ascii=False) + "\n")

    with open(os.path.join(REPORT_DIR, "remote_failures.jsonl"), "w") as f:
        for rf in remote_failures:
            f.write(json.dumps(rf, ensure_ascii=False) + "\n")

    print(f"Total Local Refs Inventoried: {len(all_refs)}")
    print(f"Total Remote Advertised Refs: {len(remote_advertised_refs)}")

    # Materialization Classification
    classified_refs = []
    unmaterialized_refs = []

    for rf in all_refs:
        commit_oid = rf['peeled_commit_oid']
        tree_oid = rf['tree_oid']
        
        status = "UNMATERIALIZED_REF"
        if commit_oid and commit_oid in all_known_worktree_heads:
            status = "MATERIALIZED_EXACT_HEAD"
        elif tree_oid and tree_oid in all_known_worktree_trees:
            status = "MATERIALIZED_EQUIVALENT_TREE"

        c_item = dict(rf)
        c_item['materialization_status'] = status
        classified_refs.append(c_item)

        if status == "UNMATERIALIZED_REF" and tree_oid:
            unmaterialized_refs.append(c_item)

    with open(os.path.join(REPORT_DIR, "materialization_classification.jsonl"), "w") as f:
        for cr in classified_refs:
            f.write(json.dumps(cr, ensure_ascii=False) + "\n")

    with open(os.path.join(REF_BASE_DIR, "unmaterialized_refs.jsonl"), "w") as f:
        for ur in unmaterialized_refs:
            f.write(json.dumps(ur, ensure_ascii=False) + "\n")

    print(f"Materialization Classification Summary:")
    print(f"  Exact Heads: {sum(1 for c in classified_refs if c['materialization_status'] == 'MATERIALIZED_EXACT_HEAD')}")
    print(f"  Equivalent Trees: {sum(1 for c in classified_refs if c['materialization_status'] == 'MATERIALIZED_EQUIVALENT_TREE')}")
    print(f"  Unmaterialized Refs: {len(unmaterialized_refs)}")

    # Group unmaterialized refs by tree_oid for deduplication
    tree_groups = {}
    for ur in unmaterialized_refs:
        toid = ur['tree_oid']
        if toid not in tree_groups:
            tree_groups[toid] = []
        tree_groups[toid].append(ur)

    duplicate_groups = []
    for toid, rlist in tree_groups.items():
        rep_ref = rlist[0]
        duplicate_groups.append({
            'tree_oid': toid,
            'repository_id': rep_ref['repository_id'],
            'representative_ref': rep_ref['ref_name'],
            'ref_count': len(rlist),
            'refs': [r['ref_name'] for r in rlist],
            'commit_oids': list(set(r['peeled_commit_oid'] for r in rlist))
        })

    with open(os.path.join(REF_BASE_DIR, "duplicate_tree_groups.jsonl"), "w") as f:
        for dg in duplicate_groups:
            f.write(json.dumps(dg, ensure_ascii=False) + "\n")

    print(f"Unique Unmaterialized Trees: {len(tree_groups)}")

    # Determine Default Branch & Build Extraction Plan
    extraction_plan = []

    for r in repositories:
        repo_id = r['repository_id']
        gcd = r['git_common_dir']
        mirror_path = os.path.join(REF_BASE_DIR, "mirrors", f"{repo_id}.git")

        # Find default branch
        default_branch_commit = ""
        default_branch_name = ""
        
        # Check symbolic HEAD in mirror
        code_sh, out_sh, _ = run_cmd(['git', '-C', mirror_path, 'symbolic-ref', 'refs/remote/origin/HEAD'])
        if code_sh == 0 and out_sh.strip():
            default_branch_name = out_sh.strip()
        
        if not default_branch_name:
            for candidate in ['refs/local/heads/main', 'refs/local/heads/master', 'refs/local/remotes/origin/main', 'refs/local/remotes/origin/master', 'refs/heads/main', 'refs/heads/master', 'refs/remotes/origin/main', 'refs/remotes/origin/master']:
                code_c, out_c, _ = run_cmd(['git', '-C', mirror_path, 'rev-parse', candidate])
                if code_c == 0 and out_c.strip():
                    default_branch_name = candidate
                    break

        if default_branch_name:
            code_dbc, out_dbc, _ = run_cmd(['git', '-C', mirror_path, 'rev-parse', default_branch_name])
            if code_dbc == 0:
                default_branch_commit = out_dbc.strip()

        # Plan for each unique unmaterialized tree in this repo
        repo_unmat = [ur for ur in unmaterialized_refs if ur['repository_id'] == repo_id]
        repo_tree_groups = {}
        for ur in repo_unmat:
            toid = ur['tree_oid']
            if toid not in repo_tree_groups:
                repo_tree_groups[toid] = []
            repo_tree_groups[toid].append(ur)

        for toid, rlist in repo_tree_groups.items():
            rep = rlist[0]
            ref_commit = rep['peeled_commit_oid']
            
            merge_base_commit = ""
            merge_base_tree = ""
            extraction_mode = "FULL_TREE"

            if default_branch_commit and ref_commit:
                code_mb, out_mb, _ = run_cmd(['git', '-C', mirror_path, 'merge-base', default_branch_commit, ref_commit])
                if code_mb == 0 and out_mb.strip():
                    merge_base_commit = out_mb.strip()
                    code_mbt, out_mbt, _ = run_cmd(['git', '-C', mirror_path, 'rev-parse', merge_base_commit + '^{tree}'])
                    if code_mbt == 0:
                        merge_base_tree = out_mbt.strip()
                        extraction_mode = "BRANCH_DELTA"

            plan_entry = {
                'repository_id': repo_id,
                'representative_ref': rep['ref_name'],
                'short_name': rep['short_name'],
                'tree_oid': toid,
                'peeled_commit_oid': ref_commit,
                'default_branch_name': default_branch_name,
                'default_branch_commit': default_branch_commit,
                'merge_base_commit': merge_base_commit,
                'merge_base_tree': merge_base_tree,
                'extraction_mode': extraction_mode,
                'all_matching_refs': [r['ref_name'] for r in rlist]
            }
            extraction_plan.append(plan_entry)

    with open(os.path.join(REPORT_DIR, "extraction_plan.jsonl"), "w") as f:
        for ep in extraction_plan:
            f.write(json.dumps(ep, ensure_ascii=False) + "\n")

    print(f"Extraction Plan Prepared: {len(extraction_plan)} unique tree extraction targets.")
    print("=== Inventory Complete ===")

if __name__ == "__main__":
    main()
