#!/usr/bin/env python3
"""
Build p13_6_branch_merged_log_20260520.json — read-only branch audit.
Run once then discard.
"""
import json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def git(*args):
    r = subprocess.run(["git"] + list(args), capture_output=True, text=True, cwd=str(ROOT))
    return r.stdout.strip()

def branch_sha(name):
    return git("rev-parse", name)

def last_date(name):
    return git("log", "-1", "--format=%ci", name)

def ahead_behind_main(name):
    raw = git("rev-list", "--count", "--left-right", f"main...{name}")
    parts = raw.split()
    if len(parts) == 2:
        return int(parts[1]), int(parts[0])   # ahead, behind
    return -1, -1

# ── local candidates (exclude main, already merged/*) ──────────────────
local_raw = git("branch", "--list")
local_all = [l.lstrip("*+ ").strip() for l in local_raw.splitlines() if l.strip()]
merged_into_main_raw = git("branch", "--merged", "main")
merged_into_main = {l.lstrip("*+ ").strip() for l in merged_into_main_raw.splitlines() if l.strip()}

local_candidates = []
for b in local_all:
    if b == "main" or b.startswith("merged/"):
        continue
    sha = branch_sha(b)
    date = last_date(b)
    ahead, behind = ahead_behind_main(b)
    merged_yn = "Y" if b in merged_into_main else "N"
    local_candidates.append({
        "name": b,
        "sha": sha,
        "last_commit_date": date,
        "merged_into_main": merged_yn,
        "ahead_of_main": ahead,
        "behind_main": behind,
        "target_name": f"merged/{b}",
    })
    print(f"  local: {b[:60]}", file=sys.stderr)

# ── remote candidates (origin/*, exclude HEAD, main, merged/*) ─────────
remote_raw = git("branch", "-r")
remote_candidates = []
for line in remote_raw.splitlines():
    b = line.strip()
    if not b.startswith("origin/"):
        continue
    name = b[len("origin/"):]
    if name in ("HEAD", "main") or name.startswith("merged/") or "->" in name:
        continue
    sha = git("rev-parse", b)
    remote_candidates.append({
        "name": name,
        "remote_ref": b,
        "sha": sha,
        "target_name": f"merged/{name}",
    })

# ── worktrees ───────────────────────────────────────────────────────────
wt_raw = git("worktree", "list", "--porcelain")
worktrees = []
current_wt = {}
for line in wt_raw.splitlines():
    if line.startswith("worktree "):
        if current_wt:
            worktrees.append(current_wt)
        current_wt = {"path": line.split(" ", 1)[1]}
    elif line.startswith("HEAD "):
        current_wt["sha"] = line.split(" ", 1)[1]
    elif line.startswith("branch "):
        ref = line.split(" ", 1)[1]
        current_wt["branch"] = ref.replace("refs/heads/", "")
    elif line == "bare":
        current_wt["branch"] = "(bare)"
    elif line == "prunable":
        current_wt["prunable"] = True
if current_wt:
    worktrees.append(current_wt)

wt_out = []
for wt in worktrees:
    branch = wt.get("branch", "?")
    path   = wt.get("path", "?")
    prunable = wt.get("prunable", False)
    recommend_remove = prunable or path.startswith("/private/tmp")
    if path == str(ROOT):
        continue  # skip main worktree
    wt_out.append({
        "path": path,
        "branch": branch,
        "sha": wt.get("sha", "?"),
        "prunable": prunable,
        "recommend_remove": recommend_remove,
    })

output = {
    "phase": "P13_6_BRANCH_MERGED_ARCHIVE",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "policy": "RENAME_ONLY_NO_DELETION",
    "active_branch_after": "main",
    "merged_namespace": "merged/",
    "protected_branches": ["main"],
    "local_total_candidates": len(local_candidates),
    "remote_total_candidates": len(remote_candidates),
    "worktree_candidates": len(wt_out),
    "candidate_local_renames": local_candidates,
    "candidate_remote_renames": remote_candidates,
    "candidate_worktrees_to_remove": wt_out,
    "renames_executed": [],
    "worktrees_removed": [],
    "deletions_executed": [],
    "classification": "AUDIT_ONLY_NO_RENAME",
}

out_path = ROOT / "outputs" / "replay" / "p13_6_branch_merged_log_20260520.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w") as f:
    json.dump(output, f, indent=2)
print(f"Written: {out_path}")
print(f"local={len(local_candidates)} remote={len(remote_candidates)} worktrees={len(wt_out)}")
