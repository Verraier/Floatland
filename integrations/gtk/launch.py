"""Build and launch the isolated GNOME Software GTK4 integration."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import shutil
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from common import launch, ROOT, diagnostic
from floatland.ipc import IPCError

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-only',action='store_true')
    parser.add_argument('application',nargs=argparse.REMAINDER)
    args=parser.parse_args(argv); command=args.application
    if command[:1]==['--']: command=command[1:]
    if not command: command=['gnome-software']
    if Path(command[0]).name!='gnome-software': parser.error('This first GTK adapter targets gnome-software only')
    if sys.platform!='linux': parser.error('GTK4 Wayland integration requires Linux')
    try:
        if shutil.which('gdbus'):
            check=subprocess.run(['gdbus','call','--session','--dest','org.freedesktop.DBus','--object-path','/org/freedesktop/DBus','--method','org.freedesktop.DBus.NameHasOwner','org.gnome.Software'],capture_output=True,text=True,timeout=5)
            if not args.build_only and check.returncode==0 and 'true' in check.stdout:
                raise ValueError('GNOME Software is already running in the background. Quit it completely before launching the GTK adapter; an existing process cannot load LD_PRELOAD.')
        build=HERE/'build' 
        subprocess.run(['cmake','-S',str(HERE),'-B',str(build),'-DCMAKE_BUILD_TYPE=RelWithDebInfo'],check=True)
        subprocess.run(['cmake','--build',str(build),'-j2'],check=True)
        if args.build_only: return 0
        from floatland.ipc import exchange,instance_dir
        import json
        reply=json.loads(exchange(instance_dir()/'floatland.sock','{"action":"status"}\n'))
        if not reply.get('ok'): raise ValueError('Start Floatland before launching the GTK integration')
        env={'FLOATLAND_GTK_ENABLE':'1','GDK_BACKEND':'wayland','LD_PRELOAD':str(build/'libfloatland-gtk.so')}
        if os.environ.get('LD_PRELOAD'): env['LD_PRELOAD']+=':'+os.environ['LD_PRELOAD']
        print('Close the existing GNOME Software process first; an existing single-instance process cannot load this module.',file=sys.stderr)
        return launch(command,env)
    except (OSError,ValueError,IPCError,subprocess.SubprocessError) as error:
        diagnostic('GTK integration failed: '+str(error)); return 1
    except KeyboardInterrupt: return 130
if __name__=='__main__': raise SystemExit(main())
