#!/usr/bin/env python3
"""Scoped xauusd entry point; original infra stays authoritative."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

HERE=Path(__file__).resolve().parent
HELPER=HERE/'shared82.py'
CENTRAL=Path('/opt/infra/platform82/maintenance/release.py')
PROJECT='xauusd'

def main():
    args=sys.argv[1:]
    if args and args[0] in ('config','images'):
        os.execv(sys.executable,[sys.executable,str(HELPER),*args])
    if args==['status']:
        if socket.gethostname()!='vps-ee74ce1d':
            raise SystemExit('Runtime status is only available on VPS82; use config locally.')
        spec=importlib.util.spec_from_file_location('project_authority',HELPER)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.render()
        argv,env=module.invocation()
        result=subprocess.run(argv+['ps','--format','json'],env=env,capture_output=True,text=True)
        if result.returncode:raise SystemExit('Runtime inspection failed; private output suppressed.')
        text=result.stdout.strip()
        rows=json.loads(text) if text.startswith('[') else [json.loads(line) for line in text.splitlines() if line]
        print(json.dumps([{k:row.get(k) for k in ('Name','State','Health','Image')} for row in rows]))
        return
    if not CENTRAL.is_file():
        raise SystemExit('Normal release controller must be installed on VPS82. Use the local config/images commands for preparation.')
    if any(a=='--project' or a.startswith('--project=') for a in args):
        raise SystemExit('Project scope is fixed by this original-project entry point.')
    os.execv(sys.executable,[sys.executable,str(CENTRAL),*args,'--project',PROJECT])

if __name__=='__main__':main()
