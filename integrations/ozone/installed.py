"""Adapt a private copy of an installed Equibop bundle; never edit the installation."""
import json
import hashlib
import shutil
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent

def locate(executable=None):
    command=executable or shutil.which('equibop')
    if not command:
        raise ValueError('Equibop executable not found; use --installed /path/to/equibop')
    binary=Path(command).resolve()
    header=b''
    if binary.is_file():
        with binary.open('rb') as file: header=file.read(4)
    if header!=b'\x7fELF':
        raise ValueError('Expected the actual Linux Equibop executable, not a shell wrapper or Flatpak command; pass --installed /path/to/the/binary')
    if not (binary.parent/'resources'/'app.asar').is_file():
        raise ValueError('This layout has no resources/app.asar beside the executable; AppImage/Flatpak bundles are not supported by this adapter')
    return binary

def cache_key(binary, archive=None):
    binary=Path(binary).resolve(); archive=Path(archive) if archive else binary.parent/'resources'/'app.asar'
    digest=hashlib.sha256(str(binary).encode())
    for p in (binary,archive,HERE/'installed-bootstrap.cjs',HERE/'controls.js',Path(__file__)):
        stat=p.stat(); digest.update(str((stat.st_mtime_ns,stat.st_size)).encode())
    return digest.hexdigest()[:16]

def adapt_directory(app):
    """Patch an extracted application copy, preserving its original entry point."""
    app=Path(app)
    path=app/'package.json'; package=json.loads(path.read_text())
    if 'equibop' not in str(package.get('name','')).lower():
        raise ValueError('The selected archive is not Equibop')
    original=package.get('main','index.js')
    if not isinstance(original,str) or not (app/original).resolve().is_relative_to(app.resolve()):
        raise ValueError('Invalid application entry point')
    if not (app/original).is_file(): raise ValueError('Application entry point is missing')
    if original.endswith('.mjs') or package.get('type')=='module':
        raise ValueError('This adapter currently requires Equibop CommonJS packaging')
    shutil.copy2(HERE/'installed-bootstrap.cjs',app/'floatland-bootstrap.cjs')
    shutil.copy2(HERE/'controls.js',app/'floatland-controls.js')
    (app/'floatland-entry.json').write_text(json.dumps(original))
    package['main']='floatland-bootstrap.cjs'
    path.write_text(json.dumps(package,indent=2)+'\n')

def prepare_installed(binary,destination):
    binary=locate(str(binary)); destination=Path(destination).resolve()
    if destination==binary.parent or binary.parent in destination.parents:
        raise ValueError('The private copy must be outside the installation')
    asar=shutil.which('asar')
    if asar: command=[asar]
    else:
        npx=shutil.which('npx')
        if not npx: raise ValueError('Install Node.js/npm (or @electron/asar) to adapt the packaged app; no Equibop source build is needed')
        command=[npx,'--yes','--package=@electron/asar','asar']
    shutil.copytree(binary.parent,destination,symlinks=False)
    archive=destination/'resources'/'app.asar'; extracted=destination/'floatland-package'
    subprocess.run(command+['extract',str(archive),str(extracted)],check=True)
    adapt_directory(extracted)
    # Pack payload files outside ASAR as needed by native modules and subprocesses.
    prepared=archive.with_name('floatland-prepared.asar')
    subprocess.run(command+['pack',str(extracted),str(prepared),'--unpack','**/*'],check=True)
    prepared.replace(archive)
    unpacked=prepared.with_name(prepared.name+'.unpacked')
    old=archive.with_name(archive.name+'.unpacked')
    if old.exists(): shutil.rmtree(old)
    if unpacked.exists(): unpacked.rename(old)
    shutil.rmtree(extracted)
    (destination/'.floatland-ready').write_text(cache_key(binary))
    return destination/binary.name

def locate_system(executable=None):
    """Read a distribution launcher; never execute or source its shell text."""
    import re
    command=executable or shutil.which('equibop')
    if not command: raise ValueError('Equibop is not on PATH')
    launcher=Path(command).resolve()
    text=launcher.read_text(errors='replace')
    archives=[Path(p) for p in re.findall(r'(/[^\s\"\'`$;]+\.asar)',text) if Path(p).is_file()]
    runtimes=set(re.findall(r'\b(electron[0-9]*)\b',text))
    runtimes=[shutil.which(name) for name in runtimes if shutil.which(name)]
    if not archives and shutil.which('pacman'):
        owner=subprocess.run(['pacman','-Qoq',str(launcher)],capture_output=True,text=True,timeout=5)
        packages=owner.stdout.splitlines() if owner.returncode==0 else []
        for package in packages:
            listing=subprocess.run(['pacman','-Qlq',package],capture_output=True,text=True,timeout=5)
            if listing.returncode==0:
                archives.extend(Path(p) for p in listing.stdout.splitlines() if p.endswith('.asar') and Path(p).is_file())
    archives=list(dict.fromkeys(archives))
    if len(archives)!=1 or len(runtimes)!=1:
        raise ValueError('Could not uniquely identify app.asar and Electron from the AUR launcher. Include the launcher path in the bug report; the installed files were not changed.')
    return archives[0],Path(runtimes[0])

def prepare_system(archive,runtime,destination):
    """Reuse the distribution Electron runtime with a private ASAR payload."""
    archive=Path(archive); destination=Path(destination)
    asar=shutil.which('asar')
    command=[asar] if asar else [shutil.which('npx') or '', '--yes','--package=@electron/asar','asar']
    if not command[0]: raise ValueError('Install Node.js/npm or @electron/asar to adapt the installed package')
    # Keep packaged helpers (including arrpc) beside the adapted archive.
    shutil.copytree(archive.parent,destination,symlinks=False)
    local=destination/'app.asar'
    if archive.name!='app.asar': shutil.copy2(archive,local)
    extracted=destination/'floatland-package'
    subprocess.run(command+['extract',str(local),str(extracted)],check=True)
    adapt_directory(extracted)
    prepared=destination/'prepared.asar'
    subprocess.run(command+['pack',str(extracted),str(prepared),'--unpack','**/*'],check=True)
    prepared.replace(local)
    old=destination/'app.asar.unpacked'
    if old.exists(): shutil.rmtree(old)
    unpacked=destination/'prepared.asar.unpacked'
    if unpacked.exists(): unpacked.rename(old)
    shutil.rmtree(extracted)
    return [str(runtime),str(local)]


def user_flags():
    import os
    import shlex
    config=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'equibop-flags.conf'
    return shlex.split(config.read_text(),comments=True) if config.is_file() else []
