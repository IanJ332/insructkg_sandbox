"""Recompute local synthetic results after engine changes, retaining a backup."""
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'artifacts/synthetic.sqlite3'
if path.exists():
    target=ROOT/'artifacts'/('rebuild-backup-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.sqlite3')
    shutil.move(path,target)
    print('Prior synthetic store preserved:',target.name)
for command in [['seed.py'],['import_pl.py','artifacts/pl_all_submissions.csv','--local-synthetic-only']]:
    if command[0]=='import_pl.py' and not (ROOT/'artifacts/pl_all_submissions.csv').exists():continue
    subprocess.run([sys.executable,str(ROOT/'scripts'/command[0]),*command[1:]],cwd=ROOT,check=True)
