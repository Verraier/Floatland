# Architecture (0.6.1)

`run.py` puts the package from `src/` on the path and starts a single supervisor (`session.py`):
ABI check → build/load `native/` → read configuration → Python daemon.
A second launch is blocked by `flock`. Stopping releases the session and the plugin.

CLI → local `floatland.sock` → Controller → Hyprland Lua IPC.
Hyprland events and addressed plugin events → daemon → window state reconciliation.
Python is responsible for window policy, geometry memory, minimize, MRU and actions.
C++ is responsible for decorations, input, rendering, the snap preview and the overview lifecycle.
The unified launcher does not use the external hyprbars; the old commands for configuring it
are kept for compatibility but do not configure the built-in plugin.

The socket and state live in the directory of the current Hyprland instance inside
`XDG_RUNTIME_DIR`. State survives a process restart within the same session, not a compositor
restart. The address, PID and original class/title of a window are verified.
Window management is sequential. Minimize moves the window to a special workspace while
preserving its original workspace and geometry. Workspace modes and explicit per-window
exceptions are stored separately from the default settings. Reload does not reset these user
toggles or the saved positions.

## Configuration

`lua_config.py` runs the user's `init.lua` in a separate Lua process with a 5-second time limit.
This is trusted user code, not a sandbox. The returned table is serialized, validated against a
schema and normalized into policy and appearance parameters. Templates live in
`src/floatland/defaults/` and ship with the package. Shared theme colors are applied before
component settings.

Reload re-reads the files; Python validates everything before talking to the plugin.
The plugin also validates the whole set before assigning parameters. Only after that succeeds
does the Controller replace the configuration and reconcile windows. A reconciliation failure is
reported separately: the settings are already applied and the next reconciliation repeats the work.
This is not a transaction over the compositor's windows. The old JSON is kept during migration.

## Overview

The state machine is in `native/overview-flow.hpp`; UI and frames are in `tasks.hpp`.
Preparation runs in steps, stale generations are cancelled, and a repeated toggle reverses the
transition. Selection verifies the window identity and is confirmed by Python after restore and
raise. Normal rendering returns at a frame boundary. Minimized windows use the snapshot taken
before minimizing; no windows are restored just to prepare the overview.

The native code depends on the Hyprland 0.56.2 ABI. The standalone geometry and transition tests
check logic without a GPU, but they do not verify the contracts of live rendering and plugin unload.

## Reload (0.6.1)

`config_runtime.py` watches the Lua files and serializes reload requests with an async lock.
After a save it waits for a pause; Lua execution is moved to a worker thread, and Lua itself still
runs as a separate process with a timeout. File snapshots are compared before and after reading:
an intermediate result is not applied. The initial check also accounts for edits made while the
plugin was being built. Unchanged resulting values do not cause a repeated apply.

The native appearance call returns the applied revision number. Python requires that reply so that
an old plugin cannot silently ignore a new settings schema. The path and hash of the files read
are printed to the log. The `floatland_log` event delivers the plugin's diagnostic messages to
the same terminal. An unexpected failure of a background task is printed with a traceback and
ends the session; repeated overview polling errors do not clutter the log.
