"""Prepare and run an isolated source build of Equibop with embedded controls."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from common import launch

def prepare(source,destination):
    source=Path(source).resolve(); destination=Path(destination).resolve()
    if not (source/'src/main/mainWindow.ts').is_file(): raise ValueError('Expected an Equibop source checkout')
    if destination==source or source in destination.parents: raise ValueError('The output must be outside the original checkout')
    shutil.copytree(source,destination,ignore=shutil.ignore_patterns('.git','node_modules','dist','out','release','build'))
    def edit(name,old,new):
        path=destination/name; text=path.read_text()
        if text.count(old)!=1: raise ValueError('Unsupported Equibop source layout: '+name)
        path.write_text(text.replace(old,new))
    edit('src/renderer/index.ts','import "./themedSplash";','import "./floatland-controls";\nimport "./themedSplash";')
    shutil.copy2(HERE/'controls.ts',destination/'src/renderer/floatland-controls.ts')
    edit('src/renderer/patches/windowsTitleBar.tsx','if (!Settings.store.nativeTitleBar)','if (true)')
    edit('src/main/mainWindow.ts','const frameless = !nativeTitleBar;', 'const frameless = true; // This isolated build supplies in-header controls.')
    p=destination/'src/preload/index.ts'
    p.write_text(p.read_text()+'''\nimport { ipcRenderer as floatlandIpc, contextBridge as floatlandBridge } from "electron";
floatlandBridge.exposeInMainWorld("FloatlandSettings", { read: () => floatlandIpc.invoke("floatland:appearance") });
''')
    p=destination/'src/main/mainWindow.ts'
    p.write_text(p.read_text()+'''\nimport { ipcMain as floatlandIpc } from "electron";
import { readFileSync as floatlandRead } from "node:fs";
floatlandIpc.handle("floatland:appearance", event => {
    if (!mainWin || event.sender !== mainWin.webContents || !process.env.FLOATLAND_SETTINGS) return {};
    try { return JSON.parse(floatlandRead(process.env.FLOATLAND_SETTINGS, "utf8")); } catch { return {}; }
});
''')
    return destination

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',help='Existing Equibop source checkout; never modified')
    parser.add_argument('--installed', nargs='?', const='', help='Use an installed Equibop bundle; default path comes from PATH')
    parser.add_argument('--output',help='New directory for the patched copy')
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args(argv)
    try:
        destination=Path(args.output) if args.output else HERE/'build'/('equibop-'+uuid.uuid4().hex[:8])
        destination.parent.mkdir(parents=True,exist_ok=True)
        if not args.source:
            sys.path.insert(0,str(HERE))
            from installed import locate,prepare_installed,cache_key,locate_system,prepare_system,user_flags
            try:
                binary=locate(args.installed or None)
                archive=None
            except ValueError:
                archive,binary=locate_system(args.installed or None)
            key=cache_key(binary,archive)
            if not args.output: destination=HERE/'build'/('installed-'+key)
            ready=destination/'.floatland-ready'
            cached=ready.is_file() and ready.read_text()==key
            if archive is not None:
                command=[str(binary),str(destination/'app.asar')] if cached else prepare_system(archive,binary,destination)
            else:
                executable=destination/binary.name if cached else prepare_installed(binary,destination)
                command=[str(executable)]
            ready.write_text(key)
            print('Prepared private Equibop package:',destination)
            if args.prepare_only: return 0
            if sys.platform!='linux': raise ValueError('Running Equibop requires Linux')
            print('Close the existing Equibop process before testing. The AUR package is unchanged.',file=sys.stderr)
            return launch(command+user_flags()+['--ozone-platform=wayland','--class=equibop.floatland-csd-'+uuid.uuid4().hex],{},cwd=destination)
        copy=prepare(args.source,destination)
        print('Prepared isolated Equibop copy:',copy)
        if args.prepare_only: return 0
        if sys.platform!='linux': raise ValueError('Running the Ozone integration requires Linux; source preparation succeeded')
        bun=shutil.which('bun')
        if not bun: raise ValueError('Install Bun to build this Equibop checkout; the prepared source is retained')
        subprocess.run([bun,'install','--frozen-lockfile'],cwd=copy,check=True)
        subprocess.run([bun,'run','build'],cwd=copy,check=True)
        electron=copy/'node_modules/.bin/electron'
        marker='equibop.floatland-csd-'+uuid.uuid4().hex
        print('Close existing Equibop first. This integration uses Equibop native window actions, not Floatland minimize storage.',file=sys.stderr)
        return launch([str(electron),'.','--ozone-platform=wayland','--class='+marker],{},cwd=copy)
    except (OSError,ValueError,subprocess.CalledProcessError) as error:
        print('Equibop integration failed:',error,file=sys.stderr); return 1
    except KeyboardInterrupt: return 130
if __name__=='__main__': raise SystemExit(main())
