"""Persistent normal floating sizes, separate from compositor-session recovery."""
import json
import logging
import os
from pathlib import Path
from .state import State


class SizeMemory(State):
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else Path(
            os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state"
        ) / "floatland/window-sizes.json"
        self.data = {"version": 1, "sizes": {}}
        self.dirty = False
        self.writable = True
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("sizes"), dict):
                    raise ValueError("invalid size-memory format")
                for key, size in data["sizes"].items():
                    if not isinstance(key, str) or not self.valid(size):
                        raise ValueError("invalid application size")
                self.data = data
            except (OSError, ValueError) as error:
                self.writable = False
                logging.getLogger("floatland").warning("Size memory ignored; preserving %s: %s", self.path, error)

    @staticmethod
    def valid(size):
        return isinstance(size, list) and len(size) == 2 and all(type(v) is int and 1 <= v <= 65536 for v in size)

    @staticmethod
    def key(client):
        return (client.get("initialClass") or client.get("class") or "").partition(".floatland-csd-")[0]

    def get(self, client):
        return self.data["sizes"].get(self.key(client))

    def remember(self, client):
        key, size = self.key(client), client.get("size")
        if key and self.valid(size) and self.data["sizes"].get(key) != size:
            self.data["sizes"][key] = list(size)
            self.dirty = True

    def flush(self):
        if self.dirty and self.writable:
            try:
                self.save()
                self.dirty = False
            except OSError as error:
                logging.getLogger("floatland").warning("Cannot save window sizes: %s", error)
