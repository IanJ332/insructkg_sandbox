"""Reproducible local commands. Never opens a hosted course or invokes paid inference."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
COMPOSE=['docker','compose','-f',str(ROOT/'infrastructure/compose.yaml')]
PYTHON=str(ROOT/'.venv/bin/python') if (ROOT/'.venv/bin/python').exists() else sys.executable

def run(command,**kwargs):return subprocess.run(command,cwd=ROOT,check=True,**kwargs)
def script(name,*args):return run([PYTHON,str(ROOT/'scripts'/name),*args])
def prerequisites():
    report={'platform':platform.platform(),'architecture':platform.machine(),'python':sys.version.split()[0],
            'tools':{tool:shutil.which(tool) for tool in ['git','python3','node','docker']}}
    for port in [3000,8080]:
        with socket.socket() as s: report[f'port_{port}_listening']=s.connect_ex(('127.0.0.1',port))==0
    (ROOT/'artifacts').mkdir(exist_ok=True)
    (ROOT/'artifacts/environment.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    run(['docker','info','--format','{{.ServerVersion}}'])
def dashboard_start():
    pidfile=ROOT/'artifacts/dashboard.pid'
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1',8080))==0:
            print('Port 8080 is already listening; verify /health belongs to SIIP.');return
    log=(ROOT/'artifacts/dashboard.log').open('a')
    p=subprocess.Popen([PYTHON,str(ROOT/'scripts/dashboard.py')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    pidfile.write_text(str(p.pid));print('Dashboard PID',p.pid)
def dashboard_stop():
    pidfile=ROOT/'artifacts/dashboard.pid'
    if pidfile.exists():
        pid=int(pidfile.read_text())
        # Validate process identity before sending any signal.
        observed=subprocess.run(['ps','-p',str(pid),'-o','command='],text=True,capture_output=True).stdout
        if str(ROOT/'scripts/dashboard.py') in observed:
            import signal
            try:os.kill(pid,signal.SIGTERM)
            except ProcessLookupError:pass
        pidfile.unlink()
def tests(pattern=None):
    command=[PYTHON,'-m','unittest','discover','-s','tests','-v']
    if pattern:command+=['-k',pattern]
    p=subprocess.run(command,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (ROOT/'artifacts/tests.log').write_text(p.stdout);print(p.stdout)
    if p.returncode:raise SystemExit(p.returncode)

parser=argparse.ArgumentParser()
parser.add_argument('command',choices=['check','install','init','start-pl','start-dashboard','start','seed','graph','test-sql','test-feedback','test','evaluate','fresh-preflight','stop','reset','demo','smoke'])
args=parser.parse_args()
cmd=args.command
if cmd=='check':prerequisites()
elif cmd=='install':
    if not (ROOT/'.venv').exists():run([sys.executable,'-m','venv','.venv'])
    run([str(ROOT/'.venv/bin/python'),'-m','pip','install','-r','requirements-dev.txt'])
elif cmd=='init':
    for name in ['prepare.py','expected.py','graph_audit.py','seed.py']:script(name)
elif cmd=='start-pl':run(COMPOSE+['up','-d'])
elif cmd=='start-dashboard':dashboard_start()
elif cmd=='start':run(COMPOSE+['up','-d']);dashboard_start()
elif cmd=='seed':script('seed.py')
elif cmd=='graph':script('graph_audit.py')
elif cmd=='test-sql':tests('SQLTests')
elif cmd=='test-feedback':tests('FeedbackTests')
elif cmd=='test':tests()
elif cmd=='evaluate':script('evaluate.py')
elif cmd=='fresh-preflight':script('extract.py')
elif cmd=='smoke':script('smoke.py')
elif cmd=='stop':dashboard_stop();run(COMPOSE+['stop'])
elif cmd=='reset':
    # Reversible reset: keep all current state in timestamped backups; no volume deletion.
    dashboard_stop();run(COMPOSE+['stop'])
    saved=ROOT/'artifacts'/('reset-backup-'+datetime.now().strftime('%Y%m%d-%H%M%S'));saved.mkdir()
    if (ROOT/'artifacts/synthetic.sqlite3').exists():shutil.move(ROOT/'artifacts/synthetic.sqlite3',saved/'synthetic.sqlite3')
    script('seed.py');print('Synthetic store reset; prior database saved to',saved)
    print('PrairieLearn history retained. Use Regenerate your assessment instance for a fresh local demo.')
elif cmd=='demo':
    script('seed.py');script('graph_audit.py');script('evaluate.py');run(COMPOSE+['up','-d']);dashboard_start()
    print('Open http://localhost:3000/pl and http://127.0.0.1:8080; follow docs/DEMO.md. UI actions are manual; fixture runs do not prove UI success.')
