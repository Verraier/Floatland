#!/usr/bin/env python3
"""Opt-in Qt CSD launcher; environment changes apply only to the child process."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / 'src'))


def child_environment(base, plugins, settings):
    env = dict(base)
    env['QT_QPA_PLATFORM'] = 'wayland'
    env['QT_WAYLAND_DECORATION'] = 'floatland'
    env['QT_WAYLAND_DISABLE_WINDOWDECORATION'] = '0'
    # Qt's documented-in-source interface blacklist bypasses server decoration
    # negotiation only for this process. Other applications are unaffected.
    disabled = [v for v in env.get('QT_WAYLAND_DISABLED_INTERFACES', '').split(',') if v]
    if 'zxdg_decoration_manager_v1' not in disabled:
        disabled.append('zxdg_decoration_manager_v1')
    env['QT_WAYLAND_DISABLED_INTERFACES'] = ','.join(disabled)
    env['QT_PLUGIN_PATH'] = str(plugins) + (os.pathsep + env['QT_PLUGIN_PATH'] if env.get('QT_PLUGIN_PATH') else '')
    env['FLOATLAND_QT_SETTINGS'] = str(settings)
    return env


def detect_qt_major(command):
    executable=shutil.which(command) or command
    try:
        result=subprocess.run(['ldd',executable],capture_output=True,text=True,timeout=5)
    except (OSError,subprocess.SubprocessError): return None
    if 'libQt6Core.so' in result.stdout: return '6'
    if 'libQt5Core.so' in result.stdout: return '5'
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qt-major', choices=('auto','5','6'), default='auto')
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('application', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.application
    if command[:1] == ['--']:
        command = command[1:]
    if not command and not args.build_only:
        parser.error('specify an application: python3 run.py qt -- application')
    if command and Path(command[0]).name.lower() in {
        'firefox', 'firefox-esr', 'firefox-bin', 'thunderbird', 'chromium',
        'chromium-browser', 'google-chrome', 'google-chrome-stable', 'electron'
    }:
        parser.error('this application does not use Qt decorations. Launch it normally; '
                     'this prototype supports Qt 6 applications only, not Firefox/GTK/Electron')
    if sys.platform != 'linux':
        parser.error('Qt Wayland integration requires Linux; normal Floatland is unaffected')
    major=args.qt_major if args.qt_major!='auto' else detect_qt_major(command[0]) if command else '6'
    if major=='5' and not args.build_only:
        print('Qt 5 detected: using the full Floatland compositor titlebar (including jelly), not a Qt 6 decoration in a Qt 5 process. Native Qt 5 embedding is not implemented.',file=sys.stderr)
        env=dict(os.environ, QT_QPA_PLATFORM='wayland', QT_WAYLAND_DISABLE_WINDOWDECORATION='1')
        env.pop('QT_WAYLAND_DECORATION',None)
        try: return subprocess.call(command,env=env)
        except OSError as error:
            print('Qt launch failed:',error,file=sys.stderr); return 1
        except KeyboardInterrupt: return 130
    if major is None:
        print('WARNING: Qt major version could not be detected. This native decoration requires Qt 6. Use --qt-major 5 for the compositor-decoration fallback.',file=sys.stderr)
    build = HERE / 'build' 
    try:
        subprocess.run(['cmake', '-S', str(HERE), '-B', str(build), '-DCMAKE_BUILD_TYPE=RelWithDebInfo'], check=True)
        subprocess.run(['cmake', '--build', str(build), '-j2'], check=True)
        if args.build_only:
            return 0
        from floatland.config import load
        from floatland.lua_config import config_home
        config = config_home()
        def fingerprint():
            return tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size)
                         for p in sorted(config.rglob('*.lua')) if p.is_file())
        with tempfile.TemporaryDirectory(prefix='floatland-qt-') as folder:
            settings = Path(folder) / 'appearance.json'
            def publish():
                value = load(create=True)['appearance']
                temporary = settings.with_suffix('.tmp')
                temporary.write_text(json.dumps(value))
                temporary.replace(settings)
            publish()
            stamp = fingerprint()
            child = subprocess.Popen(command, env=child_environment(os.environ, build / 'plugins', settings))
            try:
                while True:
                    try:
                        return child.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        current = fingerprint()
                        if current != stamp:
                            try:
                                publish()
                            except (OSError, ValueError) as error:
                                print('Qt configuration rejected; previous settings retained:', error, file=sys.stderr)
                            stamp = current
            finally:
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        print('Qt integration failed:', error, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
