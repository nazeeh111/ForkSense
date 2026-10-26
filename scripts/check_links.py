"""Check repository-relative Markdown/HTML links without fetching remote URLs."""
from pathlib import Path
import re
import sys
from urllib.parse import unquote

root=Path(__file__).resolve().parents[1]
errors=[]; count=0
for path in root.rglob('*.md'):
    if any(p in ('.git','.venv','.local-evidence','build','results-v1') for p in path.relative_to(root).parts) or path.name=='TASK_STATE.md': continue
    text=path.read_text()
    targets=re.findall(r'\]\(([^)]+)\)',text)+re.findall(r'(?:src|href)="([^"]+)"',text)
    for target in targets:
        target=target.split(' "',1)[0].strip('<>')
        if '://' in target or target.startswith(('#','mailto:','data:')): continue
        target=unquote(target.split('#',1)[0].split('?',1)[0])
        if not target: continue
        count+=1
        if not (path.parent/target).exists(): errors.append(f'{path.relative_to(root)}: {target}')
if errors:
    print('\n'.join(errors));sys.exit(1)
print(f'{count} local links resolve')
