import json
import os
from pathlib import Path
import tempfile


class State:
    def __init__(self, path):
        self.path = Path(path)
        self.data = {"version": 1, "modes": {}, "windows": {}}
        if self.path.exists():
            data = json.loads(self.path.read_text())
            if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("modes"), dict) or not isinstance(data.get("windows"), dict):
                raise ValueError("Unsupported or invalid Floatland state: " + str(self.path))
            self.data = data

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".floatland-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(self.data, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
