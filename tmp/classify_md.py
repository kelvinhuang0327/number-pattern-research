import re
from pathlib import Path

base = Path('/Users/kelvin/Kelvin-WorkSpace/LotteryNew')
md_list_file = Path('/tmp/md_list.txt')
if not md_list_file.exists():
    print('Missing /tmp/md_list.txt')
    raise SystemExit(1)
md_list = md_list_file.read_text(encoding='utf-8').splitlines()
output = []
merge_candidates = []

for p in md_list:
    cls = 'ARCHIVE'
    reason = ''
    lp = p
    name = Path(lp).name
    # KEEP rules
    if lp.startswith('wiki/') or lp.startswith('memory/'):
        cls = 'KEEP'
        reason = 'Official wiki or memory (source-of-truth)'
    elif lp in ('CLAUDE.md','SYSTEM_MAP.md','AGENT_RULES.md','README.md','README_NAVIGATION.md'):
        cls = 'KEEP'
        reason = 'Root knowledge entry exception'
    elif lp.startswith('.agent/') or lp.startswith('.claude/') or lp.startswith('.gstack/'):
        cls = 'KEEP'
        reason = 'Agent/skill config and SKILL.md files (operational)'
    elif '/.venv/' in lp or lp.startswith('.venv/') or lp.startswith('node_modules/') or '/site-packages/' in lp:
        cls = 'REMOVE'
        reason = 'Third-party vendored files (not knowledge)'
    elif lp.startswith('docs/archive/') or lp.startswith('archive/') or '/archive/' in lp:
        cls = 'ARCHIVE'
        reason = 'Already archived/historical'
    else:
        # Patterns for ARCHIVE
        if re.match(r'RESEARCH_PROGRESS_', name) or re.match(r'RESEARCH_breakthrough_', name) or name.startswith('failure_analysis_') or name.startswith('draw_analysis_') or name.startswith('PREDICTION_REPORT_'):
            cls = 'ARCHIVE'
            reason = 'Single-run/experimental reports — archive by default'
        else:
            # MERGE candidates logic
            if lp.startswith('docs/') or lp.startswith('analysis/') or lp.startswith('ai_lab/'):
                lower = name.lower()
                if any(k in lower for k in ('protocol','guide','implementation','master_guide','backtest_protocol','system_guide','id_unification','implementation_guide','master_guide','implementation_guide','guide')):
                    cls = 'MERGE_TO_WIKI'
                    reason = 'Procedural/operational guide — extract rules/logic into wiki'
                    merge_candidates.append(lp)
                else:
                    cls = 'ARCHIVE'
                    reason = 'Non-wiki docs; preserve as archive unless explicit guide'
            elif lp.endswith('_strategy_report.md') or lp.endswith('_report.md') or 'strategy_report' in lp:
                cls = 'ARCHIVE'
                reason = 'Strategy/report files (historical/experimental)'
            else:
                cls = 'ARCHIVE'
                reason = 'Uncertain — archive to reduce agent risk'

    output.append((lp, cls, reason))

# write CSV
outp = Path('/Users/kelvin/Kelvin-WorkSpace/LotteryNew/docs/archive/classification.csv')
with outp.open('w', encoding='utf-8') as f:
    f.write('file,classification,reason\n')
    for lp,cls,reason in output:
        f.write(f'"{lp}","{cls}","{reason}"\n')

print('Wrote', outp)
print('Total files:', len(output))
print('MERGE_TO_WIKI candidates (sample 50):')
for m in merge_candidates[:50]:
    print(m)
