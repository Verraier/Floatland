"""Shared process-local launch and live settings export for optional integrations."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'src'))

def diagnostic(message):
    print(message, file=sys.stderr, flush=True)
    try:
        log=ROOT/'logs'/'integrations.log'
        log.parent.mkdir(exist_ok=True)
        with log.open('a') as file: file.write(time.strftime('%Y-%m-%d %H:%M:%S ')+message+'\n')
    except OSError:
        pass

def gtk_status(path, pid):
    try:
        state=json.loads(Path(str(path)+'.'+str(pid)).read_text())
        return state if state.get('pid')==pid else {}
    except (OSError,ValueError,AttributeError): return {}

def gtk_settings(settings):
    return '[appearance]\n'+'\n'.join(str(k)+'='+('true' if v is True else 'false' if v is False else str(v)) for k,v in settings.items())+'\n'

def gtk_css(settings):
    size=settings['button_size']
    spacing=min(20,settings['button_spacing'])
    rules=[f'.floatland-controls button.floatland-control {{ min-width: {size}px; min-height: {size}px; padding: 0; margin: 0 {spacing/2}px; border-radius: 999px; border: 1px solid alpha(white,0.22); }}']
    for name in ('close','minimize','maximize'):
        color=settings[name+'_color']
        rules.append(f'.floatland-control.{name} {{ background: {color}; }}')
    rules.append('.floatland-control:active { opacity: 0.8; }')
    return '\n'.join(rules)

def launch(command, environment, cwd=None):
    from floatland.config import load
    from floatland.lua_config import config_home
    def fingerprint():
        return [(str(p),p.stat().st_mtime_ns,p.stat().st_size) for p in sorted(config_home().rglob('*.lua'))]
    with tempfile.TemporaryDirectory(prefix='floatland-integration-') as folder:
        settings=Path(folder)/'appearance.json'; css=Path(folder)/'controls.css'
        gtk_ini=Path(folder)/'gtk-settings.ini'
        status=Path(folder)/'status.json'; started=time.monotonic(); last_status=None; warned=False
        def publish():
            value=load(create=True)['appearance']
            for path,text in ((settings,json.dumps(value)),(css,gtk_css(value)),(gtk_ini,gtk_settings(value))):
                temporary=path.with_suffix('.tmp'); temporary.write_text(text); temporary.replace(path)
        publish(); stamp=fingerprint()
        env=dict(os.environ,**environment,FLOATLAND_SETTINGS=str(settings),FLOATLAND_GTK_CSS=str(css),FLOATLAND_INTEGRATION_STATUS=str(status),FLOATLAND_GTK_SETTINGS=str(gtk_ini))
        child=subprocess.Popen(command,env=env,cwd=cwd)
        try:
            while True:
                try:
                    result=child.wait(timeout=1)
                    if environment.get('FLOATLAND_GTK_ENABLE') and time.monotonic()-started<5:
                        diagnostic('WARNING GTK: application exited early; it may have forwarded startup to an existing single-instance process. No integration is confirmed.')
                    return result
                except subprocess.TimeoutExpired:
                    if environment.get('FLOATLAND_GTK_ENABLE'):
                        state=gtk_status(status,child.pid)
                        if state != last_status and state:
                            diagnostic('GTK integration status: '+json.dumps(state))
                            last_status=state
                        if not warned and time.monotonic()-started>8 and not state.get('headers',0):
                            diagnostic('WARNING GTK: no controls attached. Close any existing GNOME Software process and launch again. Check GTK/Wayland and module status in logs/integrations.log.')
                            warned=True
                    current=fingerprint()
                    if current!=stamp:
                        try: publish()
                        except (ValueError,OSError) as error: print('Integration settings rejected:',error,file=sys.stderr)
                        stamp=current
        finally:
            if child.poll() is None:
                child.terminate()
                try: child.wait(timeout=5)
                except subprocess.TimeoutExpired: child.kill(); child.wait()
