"""Reload trusted user configuration without blocking the event loop."""
import asyncio
import hashlib
import logging
from pathlib import Path

from .config import load
from .lua_config import config_home

LOG = logging.getLogger("floatland")


def entry_path(path=None):
    path = Path(path) if path is not None else config_home() / "init.lua"
    return (path / "init.lua" if path.is_dir() else path).resolve()


def fingerprint(entry):
    entry = Path(entry).resolve()
    files = {entry}
    if entry.suffix == '.lua':
        files.update(entry.parent.rglob('*.lua'))
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(str(path).encode())
        try:
            digest.update(path.read_bytes())
        except FileNotFoundError:
            digest.update(b'<missing>')
    return digest.hexdigest()


class ConfigRuntime:
    def __init__(self, controller, path=None, native=True):
        self.controller = controller
        self.path = entry_path(path)
        self.native = native
        self.lock = asyncio.Lock()
        self.applied = None

    async def reload(self, automatic=False):
        async with self.lock:
            if not self.path.is_file():
                raise ValueError(str(self.path) + ': config entry is missing; previous settings retained')
            before = fingerprint(self.path)
            candidate = await asyncio.to_thread(load, self.path)
            if fingerprint(self.path) != before:
                raise ValueError('Configuration changed while loading; retry after saving all files')
            if self.native:
                candidate['titlebar_height'] = 32 if candidate['appearance']['titlebars_enabled'] else 0
            if automatic and candidate == self.controller.config:
                self.applied = before
                LOG.info('Config checked: %s | revision %s | settings unchanged', self.path, before[:12])
                return {'reloaded': False, 'config_path': str(self.path), 'fingerprint': before[:12]}
            result = self.controller.replace_config(candidate, native=self.native)
            self.applied = before
            result.update(config_path=str(self.path), fingerprint=before[:12], native=self.native)
            try:
                self.controller.reconcile()
            except Exception as error:
                result['warning'] = 'Config applied; window reconciliation will retry: ' + str(error)
                LOG.warning('%s', result['warning'])
            LOG.info('Config applied (%s): %s | revision %s | native=%s',
                     'automatic' if automatic else 'manual', self.path, before[:12], self.native)
            LOG.info('Appearance: %s', self.controller.config['appearance'])
            return result

    async def watch(self, stop):
        observed = fingerprint(self.path)
        pending = True  # Catch saves made while the native plugin was building.
        while not stop.is_set():
            await asyncio.sleep(.5)
            try:
                current = fingerprint(self.path)
                if current != observed:
                    observed, pending = current, True
                    continue
                if not pending:
                    continue
                pending = False
                if current != self.applied:
                    await self.reload(automatic=True)
            except Exception as error:
                LOG.warning('Config reload rejected; previous settings retained: %s', error)
