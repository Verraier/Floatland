"""MRU task selection, with no focus mutations until selection is committed."""
from .controller import identity, workspace


class Tasks:
    def __init__(self, controller):
        self.c = controller
        self.history = []
        self.cycle = []
        self.index = 0
        self.cycle_workspace = None

    def candidates(self):
        c = self.c
        result = []
        current = c.active_workspace()
        for w in c.clients:
            minimized = 'minimized' in c.windows.get(w['address'], {})
            normal = c.eligible(dict(w, pinned=False))
            origin = c.windows.get(w['address'], {}).get('minimized', {}).get('workspace', workspace(w))
            if (minimized or normal) and (w.get('pinned') or origin == current):
                result.append(w)
        return result

    @staticmethod
    def key(w):
        return (w['address'], tuple(identity(w)))

    def focused(self, address):
        w = next((w for w in self.c.clients if w['address'] == address), None)
        if w:
            key = self.key(w)
            self.history = [key] + [k for k in self.history if k != key]

    def ordered(self):
        windows = self.candidates()
        live = {self.key(w) for w in self.c.clients}
        self.history = [key for key in self.history if key in live]
        rank = {k: i for i, k in enumerate(self.history)}
        return sorted(windows, key=lambda w: rank.get(self.key(w), len(rank) + max(0, w.get('focusHistoryID', 999999))))

    def show(self, kind, windows, selected=0):
        if hasattr(self.c.ipc, 'present_tasks'):
            self.c.ipc.present_tasks(kind, windows, selected)

    def next(self, reverse=False):
        if not self.c.config.get("appearance", {}).get("switching_enabled", True):
            self.cancel()
            return {"selected": None, "disabled": True}
        if not self.cycle and hasattr(self.c.ipc, 'close_overview'):
            self.c.ipc.close_overview()
        self.c.refresh()
        current = self.c.active_workspace()
        if self.cycle_workspace != current:
            self.cycle = []
        self.cycle_workspace = current
        valid = {self.key(w): w for w in self.candidates()}
        if not self.cycle:
            self.focused(self.c.ipc.query('activewindow').get('address'))
            self.cycle = [self.key(w) for w in self.ordered()]
            self.index = 0
        else:
            selected = self.cycle[self.index] if self.cycle else None
            self.cycle = [k for k in self.cycle if k in valid]
            self.index = self.cycle.index(selected) if selected in self.cycle else -1
        if not self.cycle:
            self.show(0, [])
            return {'selected': None}
        self.index = (self.index + (-1 if reverse else 1)) % len(self.cycle)
        windows = [valid[k] for k in self.cycle]
        self.show(1, windows, self.index)
        return {'selected': windows[self.index]['address'], 'count': len(windows)}

    def cancel(self):
        self.cycle = []
        self.cycle_workspace = None
        self.show(0, [])
        return {'cancelled': True}

    def select(self, key, close_ui=True):
        self.c.refresh()
        w = next((w for w in self.candidates() if self.key(w) == key), None)
        if w is None:
            raise ValueError('Selected window has closed or changed identity')
        record = self.c.windows.get(w['address'], {})
        if 'minimized' in record:
            self.c.restore_minimized(w, record)
        if close_ui and hasattr(self.c.ipc, 'close_overview'):
            self.c.ipc.close_overview()
        self.c.dispatch(w, 'focuswindow')
        if hasattr(self.c.ipc, 'raise_window'):
            self.c.ipc.raise_window(w)
        self.focused(w['address'])
        self.c.state.save()
        return {'focused': w['address']}

    def commit(self):
        key = self.cycle[self.index] if self.cycle and self.cycle_workspace == str(self.c.ipc.query("activeworkspace").get("name", "")) else None
        self.cancel()
        return self.select(key) if key else {'focused': None}

    def click(self, address, pid):
        self.c.refresh()
        w = next((w for w in self.candidates() if w['address'] == address and w.get('pid') == pid), None)
        if w is None:
            raise ValueError('Selected task no longer exists')
        key = self.key(w)
        self.cancel()
        return self.select(key)

    def choose(self, address, pid, generation):
        # Always acknowledge failure as well as success: native UI must not wait
        # indefinitely after a window closes between the click and this event.
        success = False
        self.cycle = []
        self.cycle_workspace = None
        try:
            self.c.ipc.check_selection(generation)
            self.c.refresh()
            w = next((w for w in self.candidates() if w['address'] == address and w.get('pid') == pid), None)
            if w is None:
                raise ValueError('Selected overview window no longer exists')
            result = self.select(self.key(w), close_ui=False)
            success = True
            return result
        finally:
            self.c.ipc.finish_selection(generation, success)

    def overview(self):
        if not self.c.config.get("appearance", {}).get("overview_enabled", True):
            return {"overview": "disabled"}
        self.c.refresh()
        self.cycle = []
        current = self.c.active_workspace()
        windows = [w for w in self.ordered()
                   if w.get('pinned') or self.c.windows.get(w['address'], {}).get('minimized', {}).get('workspace', workspace(w)) == current]
        minimized = sum('minimized' in self.c.windows.get(w['address'], {}) for w in windows)
        self.show(3, windows)
        return {'overview': 'toggled', 'workspace': current, 'minimized': minimized}
