"""Window policy. All compositor mutations are explicitly addressed."""
from . import __version__
import logging
import re
import time

from .geometry import Rect, cascade, content_rect, geometry, snap, workarea
from .ipc import IPCError, address

HIDDEN = "special:floatland-minimized"


def workspace(client):
    return str(client["workspace"]["name"])


def identity(client):
    return [client.get("pid"), client.get("initialClass", client.get("class")), client.get("initialTitle", "")]


class Controller:
    def __init__(self, ipc, state, config, size_memory=None):
        self.ipc, self.state, self.config = ipc, state, config
        self.size_memory = size_memory
        self.windows = state.data["windows"]
        self.modes = state.data["modes"]
        self.clients, self.monitors = [], {}
        from .tasks import Tasks
        self.tasks = Tasks(self)
        from .pip import PictureInPicture
        self.pip = PictureInPicture(self)
        for record in self.windows.values():
            record.pop("drag_origin", None)  # Never resume a pointer grab after restart.
            record.pop("applied", None)  # Live compositor state may change while stopped.

    def replace_config(self, candidate, native=True):
        from .config import validate
        candidate = validate(candidate)
        if native:
            candidate['titlebar_height'] = 32 if candidate['appearance']['titlebars_enabled'] else 0
            # Native side validates every field before committing any of them.
            self.ipc.configure_appearance(candidate['appearance'])
        self.config = candidate
        self.tasks.cycle = []
        self.tasks.cycle_workspace = None
        for record in self.windows.values():
            record.pop('applied', None)
        return {'reloaded': True}

    def size_memory_allowed(self, client):
        return (self.config.get("remember_sizes", True)
                and (not client.get("xwayland", False) or self.config.get("remember_xwayland_sizes", False))
                and not self.pip.active(client)
                and not client.get("modal") and not client.get("transient")
                and not client.get("override_redirect") and not client.get("nofocus"))

    def remember_sizes(self, clients):
        if self.size_memory is None or not self.config.get("remember_sizes", True):
            return
        for client in clients:
            record = self.windows.get(client["address"])
            if (not record or record["identity"] != identity(client) or not record.get("applied")
                    or not self.eligible(client) or not self.size_memory_allowed(client) or not client.get("floating")
                    or client.get("fullscreen") or client.get("fullscreenClient")
                    or client.get("modal") or client.get("transient")
                    or any(record.get(k) for k in ("zone", "minimized", "drag_origin"))):
                continue
            size = client.get("size")
            if record.get("observed_size") != size:
                self.size_memory.remember(client)
                record["observed_size"] = list(size)

    def refresh(self):
        self.remember_sizes(self.clients)
        self.clients = self.ipc.query("clients")
        self.monitors = {m["id"]: m for m in self.ipc.query("monitors")}
        self.remember_sizes(self.clients)
        if self.size_memory is not None:
            self.size_memory.flush()
        live = {c["address"]: c for c in self.clients}
        for key in list(self.windows):
            if key not in live or self.windows[key]["identity"] != identity(live[key]):
                del self.windows[key]

    def eligible(self, client):
        return (client.get("mapped", True) and not client.get("hidden", False)
                and not client.get("pinned", False)
                and not client.get("override_redirect", False)
                and not client.get("nofocus", False)
                and client["workspace"]["id"] != -1
                and not workspace(client).startswith("special:")
                and workspace(client) != "special"
                and not any(re.search(p, client.get("class", "")) for p in self.config["exclude_classes"]))

    def record(self, client):
        key = client["address"]
        if key not in self.windows:
            self.windows[key] = {
                "identity": identity(client), "original_floating": bool(client["floating"]),
                "original_geometry": geometry(client).values(),
                "workspace": workspace(client),
            }
            if client.get("xwayland") and not self.config.get("remember_xwayland_sizes", False):
                logging.getLogger("floatland").debug("XWayland size restore skipped: class=%s address=%s size=%s",
                    client.get("class", ""), key, client.get("size"))
            if self.size_memory is not None and self.size_memory_allowed(client):
                size = self.size_memory.get(client)
                if size and not client.get("modal") and not client.get("transient"):
                    self.windows[key]["remembered_size"] = list(size)
        return self.windows[key]

    def mode(self, name):
        return self.modes.get(name, self.config["workspace_modes"].get(name, self.config["default_mode"]))

    def frame_bounds(self, client):
        monitor = self.monitors.get(client["monitor"])
        if not monitor:
            raise ValueError("Window monitor is unavailable")
        return workarea(monitor, self.config["gap"])

    def bounds(self, client):
        return content_rect(self.frame_bounds(client), 0 if ".floatland-csd-" in client.get("class", "") else self.config["titlebar_height"])

    def dispatch(self, client, command):
        self.ipc.dispatch(command, address(client["address"]))

    def place(self, client, rect, monitor=None):
        target = address(client["address"])
        bounds_client = dict(client, monitor=monitor) if monitor in self.monitors else client
        rect = rect.fit(self.bounds(bounds_client))
        self.state.save()  # Keep recovery metadata before a multi-dispatch operation.
        self.dispatch(client, "setfloating")
        if hasattr(self.ipc, 'place_geometry'):
            self.ipc.place_geometry(client, rect)
        else:
            self.ipc.dispatch("resizewindowpixel", f"exact {rect.w} {rect.h},{target}")
            self.ipc.dispatch("movewindowpixel", f"exact {rect.x} {rect.y},{target}")
        client["floating"], client["at"], client["size"] = True, [rect.x, rect.y], [rect.w, rect.h]

    def apply(self, client, record, index=0):
        if client.get("fullscreen", 0):
            return  # Retry on fullscreen exit; do not steal focus to unset it.
        name = workspace(client)
        mode = self.mode(name)
        target_float = record.get("override", record["original_floating"] or mode == "floating")
        remembered = record.get("remembered_size") if self.size_memory_allowed(client) else None
        if target_float and (not client["floating"] or remembered):
            bounds = self.bounds(client)
            value = record.get("geometry")
            rect = Rect(*value) if value else cascade(
                bounds, index, self.config["width"], self.config["height"], self.config["cascade_step"])
            if remembered:
                logging.getLogger("floatland").info("Restoring application size: class=%s address=%s size=%s",
                    client.get("class", ""), client["address"], remembered)
                rect = Rect(rect.x, rect.y, *remembered)
            self.place(client, rect)
            record.pop("remembered_size", None)
        elif not target_float and client["floating"]:
            record["geometry"] = geometry(client).values()
            self.state.save()
            self.dispatch(client, "settiled")
            client["floating"] = False
        record["workspace"], record["applied"] = name, [name, mode]

    def sync_restore(self, client, record):
        if hasattr(self.ipc, 'sync_restore'):
            self.ipc.sync_restore(client, record.get('before_snap') if record.get('zone') else None)

    def reconcile(self):
        self.refresh()
        for index, client in enumerate(self.clients):
            if not self.eligible(client):
                continue
            record = self.record(client)
            desired = [workspace(client), self.mode(workspace(client))]
            if record.get("applied") != desired:
                self.apply(client, record, index)
            self.sync_restore(client, record)
        self.pip.raise_all()
        self.state.save()

    def active(self, target=None, pid=None):
        target = target or self.ipc.query("activewindow").get("address")
        client = next((c for c in self.clients if c["address"] == target), None)
        if client is not None and pid is not None and client.get("pid") != pid:
            raise ValueError("Titlebar target no longer belongs to the original process")
        if client is None or (not self.eligible(client) and not self.pip.active(client)):
            raise ValueError("No eligible active window (special, pinned and excluded windows are ignored)")
        if client.get("fullscreen", 0):
            raise ValueError("Exit fullscreen/maximized compositor mode before changing this window")
        return client

    def active_workspace(self):
        current = self.ipc.query("activeworkspace")
        name = str(current.get("name", ""))
        if current.get("id", -1) == -1 or name == "special" or name.startswith("special:"):
            raise ValueError("Special workspaces are not managed")
        return str(current["name"])

    def preview(self, client, remember):
        if hasattr(self.ipc, "remember_preview"):
            try:
                self.ipc.remember_preview(client, remember)
            except (IPCError, OSError) as error:
                logging.getLogger("floatland").warning("Preview unavailable: %s", error)

    def restore_minimized(self, client, record):
        destination = record["minimized"]["workspace"]
        if any(c in destination for c in ",;\n\r"):
            raise ValueError("Unsupported workspace name for IPC")
        selector = destination if destination.isdecimal() else "name:" + destination
        self.ipc.dispatch("movetoworkspacesilent", f"{selector},{address(client['address'])}")
        updated = next((c for c in self.ipc.query("clients") if c["address"] == client["address"]), None)
        if updated is None or identity(updated) != identity(client):
            raise ValueError("Window closed while restoring")
        client.update(updated)
        if record["minimized"]["floating"]:
            self.place(client, Rect(*record["minimized"]["geometry"]))
        else:
            self.dispatch(client, "settiled")
            client["floating"] = False
        self.preview(client, False)
        del record["minimized"]
        record.pop("applied", None)

    def bars_event(self, payload):
        """Versioned native bridge; never fall back to the focused window."""
        version, action, target, process, value = payload.split(",")
        if version != "1" or action not in ("pip", "close", "minimize", "maximize", "snap", "drag-start", "drag-restored", "drag-end"):
            raise ValueError("Unsupported bars event")
        if not target or not process.isdecimal() or int(process) <= 0:
            raise ValueError("Bars event requires a window address and positive PID")
        address(target)
        if action.startswith('drag-'):
            self.refresh()
            client = self.active(target, int(process))
            record = self.record(client)
            if action == 'drag-end':
                if value:
                    raise ValueError('Unexpected drag-end argument')
                record.pop('drag_origin', None)
            else:
                if not re.fullmatch(r'-?\d+;-?\d+;[1-9]\d*;[1-9]\d*', value):
                    raise ValueError('Invalid drag geometry')
                rect = list(map(int, value.split(';')))
                record['drag_origin'] = {'geometry': rect, 'floating': True, 'monitor': client['monitor']}
                if action == 'drag-restored':
                    record.pop('before_snap', None)
                    record.pop('zone', None)
            self.state.save()
            return {'window': target, 'action': action}
        if action == "snap":
            from .geometry import ZONES
            if value not in ZONES:
                raise ValueError("Unknown snap zone")
        elif value:
            raise ValueError("Unexpected bars event argument")
        return self.command(action, value or None, target=target, pid=int(process))

    def command(self, action, value=None, target=None, pid=None):
        self.refresh()
        if action == "pip":
            client = self.active(target, pid)
            return {"window": client["address"], "pip": self.pip.toggle(client)}
        if action in ("maximize", "minimize", "restore", "snap", "window-toggle", "pin"):
            selected = target or self.ipc.query("activewindow").get("address")
            client = next((w for w in self.clients if w["address"] == selected), None)
            if client and self.pip.active(client):
                client = self.active(selected, pid)
                self.pip.restore(client)
                if action in ("maximize", "restore", "pin"):
                    return {"window": selected, "pip": False}
        if action == "qt-action":
            if (not isinstance(value, dict) or value.get("action") not in ("close", "minimize", "maximize")
                    or not isinstance(value.get("class"), str) or ".floatland-csd-" not in value["class"]
                    or type(value.get("pid")) is not int):
                raise ValueError("Invalid Qt decoration action")
            candidates = [w for w in self.clients if w.get("class") == value["class"] and w.get("pid") == value["pid"]]
            if len(candidates) != 1:
                raise ValueError("Qt decoration window is unavailable or ambiguous")
            return self.command(value["action"], target=candidates[0]["address"], pid=value["pid"])

        if action == 'alt-tab':
            return self.tasks.next(value == 'reverse')
        if action == 'alt-tab-commit':
            return self.tasks.commit()
        if action == 'alt-tab-cancel':
            return self.tasks.cancel()
        if action == 'overview':
            return self.tasks.overview()
        if action == "status":
            return {"version": __version__, "bars_protocol": 1, "modes": self.modes, "default_mode": self.config["default_mode"],
                    "workspace_modes": self.config["workspace_modes"],
                    "managed_windows": len(self.windows),
                    "pip": [k for k,r in self.windows.items() if r.get("pip")],
                    "minimized": [k for k, r in self.windows.items() if "minimized" in r]}
        if action in ("mode", "toggle"):
            name = self.active_workspace()
            mode = value if action == "mode" else ("tiling" if self.mode(name) == "floating" else "floating")
            if mode not in ("floating", "tiling"):
                raise ValueError("Mode must be floating or tiling")
            # Snapshot before the first dispatcher changes the native tiling layout.
            clients = [c for c in self.clients if self.eligible(c) and workspace(c) == name]
            for client in clients:
                self.record(client)
            self.modes[name] = mode
            self.state.save()
            for index, client in enumerate(clients):
                self.apply(client, self.record(client), index)
            result = {"workspace": name, "mode": mode}
        elif action == "restore-minimized":
            candidates = [(c, self.windows[c["address"]]) for c in self.clients
                          if c["address"] in self.windows and "minimized" in self.windows[c["address"]]]
            if not candidates:
                raise ValueError("No minimized windows")
            client, record = max(candidates, key=lambda pair: pair[1]["minimized"]["time"])
            self.restore_minimized(client, record)
            self.dispatch(client, "focuswindow")
            result = {"restored": client["address"]}
        elif action == "pin":
            # Pinned windows are deliberately not "eligible", yet they must be unpinnable.
            target = self.ipc.query("activewindow").get("address")
            client = next((c for c in self.clients if c["address"] == target), None)
            if client is None or not client.get("mapped", True) or workspace(client).startswith("special"):
                raise ValueError("No window to pin")
            pinned = bool(client.get("pinned"))
            if not pinned and not client["floating"]:
                raise ValueError("Only floating windows can be pinned")
            self.ipc.dispatch("pinwindow", f"{'disable' if pinned else 'enable'},{address(client['address'])}")
            result = {"window": client["address"], "action": action, "pinned": not pinned}
        else:
            client = self.active(target, pid)
            record = self.record(client)
            if action == "window-toggle":
                floating = not client["floating"]
                record["override"] = floating
                self.apply(client, record)
            elif action == "window-auto":
                record.pop("override", None)
                self.apply(client, record)
            elif action in ("snap", "maximize", "restore", "center"):
                if action == "restore" or (action == "maximize" and record.get("zone") == "full"):
                    saved = record.get("before_snap")
                    if not saved:
                        raise ValueError("No saved geometry to restore")
                    self.place(client, Rect(*saved["geometry"]), saved.get("monitor"))
                    if not saved["floating"]:
                        self.dispatch(client, "settiled")
                        client["floating"] = False
                    record.pop("before_snap", None)
                    record.pop("zone", None)
                else:
                    zone = "full" if action == "maximize" else value
                    if action == "center":
                        rect = geometry(client)
                        bounds = self.bounds(client)
                        rect = Rect(bounds.x + (bounds.w-rect.w)//2, bounds.y + (bounds.h-rect.h)//2, rect.w, rect.h)
                    else:
                        rect = content_rect(snap(self.frame_bounds(client), zone, self.config["gap"]),
                                            self.config["titlebar_height"])
                    origin = record.pop('drag_origin', None) if action == 'snap' else None
                    record.setdefault("before_snap", origin or {"geometry": geometry(client).values(), "floating": client["floating"], "monitor": client['monitor']})
                    self.place(client, rect)
                    record["zone"] = "center" if action == "center" else zone
            elif action == "close":
                self.dispatch(client, "closewindow")
            elif action == "minimize":
                self.preview(client, True)
                record["minimized"] = {"workspace": workspace(client), "geometry": geometry(client).values(),
                                       "floating": client["floating"], "time": time.time()}
                self.state.save()  # Persist recovery metadata before moving out of sight.
                try:
                    self.ipc.dispatch("movetoworkspacesilent", f"{HIDDEN},{address(client['address'])}")
                except Exception:
                    record.pop("minimized", None)
                    self.state.save()
                    self.preview(client, False)
                    raise
            else:
                raise ValueError("Unknown command: " + action)
            if action != "close":
                self.sync_restore(client, record)
            result = {"window": client["address"], "action": action}
        self.state.save()
        return result

    def release(self):
        """Restore original floating flags and recover hidden windows before exit."""
        self.refresh()
        if any(c.get("fullscreen", 0) for c in self.clients if c["address"] in self.windows):
            raise ValueError("Exit fullscreen on managed windows before stop --restore")
        for client in self.clients:
            record = self.windows.get(client["address"])
            if not record:
                continue
            if self.pip.active(client):
                self.pip.restore(client)
            if "minimized" in record:
                self.restore_minimized(client, record)
            if not self.eligible(client) or client.get("fullscreen", 0):
                continue
            if record["original_floating"]:
                self.place(client, Rect(*record["original_geometry"]))
            else:
                self.dispatch(client, "settiled")
        self.windows.clear()
        self.modes.clear()
        self.state.save()
