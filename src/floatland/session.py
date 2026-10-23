"""One foreground session owns the matching daemon and native plugin."""
import asyncio
import fcntl
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from . import __version__
from .cli import daemon_request
from .config import load
from .daemon import run
from .ipc import Hyprland, IPCError, instance_dir

LOG = logging.getLogger('floatland')
ROOT = Path(__file__).resolve().parents[2]


class SessionAlreadyRunning(IPCError):
    """Expected startup conflict, before this session's log exists."""


def command(args, capture=False):
    LOG.info('$ %s', ' '.join(map(str, args)))
    if capture:
        result = subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=30)
        output = (result.stdout + result.stderr).strip()
        if output:
            LOG.info('%s', output)
        if result.returncode:
            raise IPCError('Command failed: ' + ' '.join(map(str, args)))
        return result.stdout.strip()
    with subprocess.Popen(list(map(str, args)), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True) as child:
        try:
            for line in child.stdout:
                LOG.info('%s', line.rstrip())
            if child.wait():
                raise IPCError('Build failed; see logs/session.log')
        except BaseException:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            raise


def plugins():
    result = json.loads(command(['hyprctl', '-j', 'plugin', 'list'], capture=True))
    if not isinstance(result, list):
        raise IPCError('Unexpected plugin list')
    return result


def plugin_operation(action, path):
    # hyprctl 0.56.2 splits paths on spaces; our own copy lives in XDG_RUNTIME_DIR.
    if any(c.isspace() for c in str(path)):
        raise IPCError('Hyprland plugin path contains whitespace: ' + str(path))
    result = command(['hyprctl', 'plugin', action, path], capture=True)
    if result.strip() != 'ok':
        raise IPCError('Plugin ' + action + ' failed: ' + result)


def mapped_plugins():
    """Get actual loaded paths, absent from Hyprland's JSON plugin list."""
    instances = json.loads(command(['hyprctl', '-j', 'instances'], capture=True))
    signature = os.environ['HYPRLAND_INSTANCE_SIGNATURE']
    current = next((i for i in instances if i.get('instance') == signature), None)
    if not current or not isinstance(current.get('pid'), int):
        raise IPCError('Cannot identify current Hyprland process to replace titlebars')
    paths = set()
    for line in Path('/proc/{}/maps'.format(current['pid'])).read_text().splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) == 6 and fields[5].startswith('/'):
            path = fields[5]
            if path.endswith(' (deleted)'):
                path = path[:-10]
            name = Path(path).name
            if ('hyprbars' in name or 'floatland-bars' in name or 'floatland-titlebars' in name) and name.endswith('.so'):
                paths.add(path)
    return sorted(paths)


def stop_previous(directory):
    if not (directory / 'floatland.sock').exists():
        return
    try:
        reply = daemon_request(directory, 'stop')
    except IPCError as error:
        cause = error
        while cause is not None:
            if isinstance(cause, (FileNotFoundError, ConnectionRefusedError)):
                return
            cause = cause.__cause__
        raise
    if not reply.get('ok'):
        raise IPCError('Previous daemon refused stop: ' + str(reply))
    deadline = time.monotonic() + 5
    while (directory / 'floatland.sock').exists():
        if time.monotonic() > deadline:
            raise IPCError('Previous daemon did not stop within 5 seconds')
        time.sleep(.05)
    LOG.info('Previous daemon stopped; session state preserved.')


def start():
    directory = instance_dir()
    with (directory / 'floatland-session.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise SessionAlreadyRunning(
                'Floatland is already running. Stop the previous run.py with Ctrl+C, '
                'or run: python3 run.py stop\n'
                'Wait for the previous session to finish, then run python3 run.py again.'
            ) from error
        log_dir = ROOT / 'logs'
        log_dir.mkdir(exist_ok=True)
        log = log_dir / 'session.log'
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                            handlers=[logging.StreamHandler(), RotatingFileHandler(log, maxBytes=2 * 1024 * 1024, backupCount=2)], force=True)
        LOG.info('Floatland %s | Python %s | log: %s', __version__, sys.version.split()[0], log)
        from .lua_config import config_home
        LOG.info('Configuration: %s', config_home() / 'init.lua')
        LOG.info('Edit user Lua files here, not src/floatland/defaults. Changes reload automatically.')
        config = load(create=True)
        config['titlebar_height'] = 0
        ipc = Hyprland(directory)
        ipc.check_api()
        LOG.info('Hyprland: %s', json.dumps(ipc.query('version')))
        # Build and test before interrupting the working session.
        build = ROOT / 'build'
        command(['cmake', '-S', ROOT / 'native', '-B', build, '-DCMAKE_BUILD_TYPE=Debug'])
        command(['cmake', '--build', build, '-j2'])
        command(['ctest', '--test-dir', build, '--output-on-failure'])
        loaded = plugins()
        conflicts = any(p.get('name') in ('hyprbars', 'floatland-bars', 'floatland-titlebars') for p in loaded)
        previous = mapped_plugins() if conflicts else []
        if conflicts and not previous:
            raise IPCError('Cannot locate loaded titlebar plugin; leaving current session unchanged')
        removed = []
        installed = False
        target = directory / ('floatland-bars-' + __version__ + '.so')
        try:
            stop_previous(directory)
            for path in previous:
                plugin_operation('unload', path)
                removed.append(path)
            # Never overwrite a mapped shared object: unload above before copying.
            staging = target.with_suffix('.so.tmp')
            try:
                shutil.copy2(build / 'floatland-bars.so', staging)
                os.replace(staging, target)
            finally:
                staging.unlink(missing_ok=True)
            LOG.info('Native binary: %s | SHA256 %s', target, hashlib.sha256(target.read_bytes()).hexdigest())
            plugin_operation('load', target)
            installed = True
            if not any(p.get('name') == 'floatland-bars' and p.get('version') == __version__ for p in plugins()):
                raise IPCError('Matching native plugin not present after load')
            ipc.configure_appearance(config.get("appearance", {}))
            LOG.info("Initial native appearance acknowledged: %s", config.get("appearance", {}))
            LOG.info('Native plugin loaded. Starting matching daemon; keep this terminal open. Ctrl+C stops the session.')
            asyncio.run(run(directory, config, unified=True))
        finally:
            try:
                ipc.close_overview()
            except Exception:
                LOG.exception("Could not restore overview settings")
            if installed:
                try:
                    plugin_operation('unload', target)
                except Exception:
                    LOG.exception('Could not unload native plugin')
            for path in removed:
                if "hyprbars" in Path(path).name and Path(path).exists():
                    try:
                        plugin_operation('load', path)
                    except Exception:
                        LOG.exception('Could not restore previous plugin: %s', path)
        LOG.info('Session stopped. Log: %s', log)


def main():
    try:
        start()
    except KeyboardInterrupt:
        print('Floatland stopped.')
        return 130
    except SessionAlreadyRunning as error:
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, ValueError, IPCError, subprocess.SubprocessError):
        LOG.exception('Launch failed. Send logs/session.log; no separate debugging steps are required.')
        return 1
    return 0
