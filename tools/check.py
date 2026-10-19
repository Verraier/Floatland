#!/usr/bin/env python3
"""Run Python/Lua regressions and SDK-independent native logic tests."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

root=Path(__file__).resolve().parents[1]
env=dict(os.environ)
env['PYTHONPATH']=str(root/'src')+os.pathsep+env.get('PYTHONPATH','')
subprocess.run([sys.executable,'-m','unittest','discover','-s','tests'],cwd=root,env=env,check=True)
compiler=shutil.which('c++')
if not compiler:
    raise SystemExit('Python tests passed; C++ compiler unavailable, native logic tests NOT run.')
with tempfile.TemporaryDirectory() as temporary:
    for name in ('geometry_test','overview_flow_test','switcher_layout_test'):
        output=Path(temporary)/name
        subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror',str(root/'native'/(name+'.cpp')),'-o',str(output)],check=True)
        subprocess.run([str(output)],check=True)
print('Logic checks passed. Full plugin build and graphics still require Linux/Hyprland.')
