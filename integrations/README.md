# Optional native integrations — 0.6.10e

These are opt-in prototypes. The normal daemon and compositor decoration do not
import this folder: removing `integrations/` leaves ordinary Floatland working.
They add controls to application windows; they do not extract video into PiP.
Start the ordinary session first with `python3 run.py`.

## Qt Wayland

```sh
python3 run.py qt -- your-qt-application
```

The existing Qt decoration plugin is retained. It requires matching Qt Gui and
Qt Wayland private development headers. Firefox is not a Qt application.
See `qt/README.md`. The launcher detects Qt from linked libraries, not the application name.
Qt5 uses the ordinary Floatland compositor titlebar with client decorations
disabled; it does not load the Qt6 plugin. For shell launchers that hide the Qt
version, select `--qt-major 5` explicitly. Native Qt5 embedding is not implemented.
This experiment does not claim compatibility with every Qt build.

## GNOME Software: GTK4/libadwaita

Close the existing GNOME Software process, then run:

```sh
python3 run.py gtk -- gnome-software
```

The launcher builds a process-local preload module using CMake, pkg-config and
the GTK4, GTK4 Wayland and libadwaita development packages. It does not modify
GNOME Software or install a system-wide GTK module. A running single-instance
process cannot acquire the module: close it before using the launcher.

The module finds existing GTK/libadwaita header bars, hides their original
window controls, and inserts a custom Cairo control group. It does not add another
header bar. Actions identify the owning window by a generated app ID and PID,
then use Floatland's daemon; they do not act on the currently focused window.

This adapter uses a fixed left-hand close/minimize/maximize group. Size,
spacing, colors, texture, hover symbols, press highlight, growth, pull strength,
center shift, return duration and rebound follow titlebars.lua live. Motion
uses the same pure C++ calculations as the compositor decoration. Rendering
and gesture routing are toolkit-specific and require Linux validation.
Tab focuses the group; Left/Right selects a control and Enter/Space activates.
Per-button accessibility roles and arbitrary button order/side are not yet
implemented in this GTK prototype.
Transient dialogs are excluded. Flatpak/sandbox injection is not supported.
Changing app IDs may affect shell grouping and class-based window rules.
The launcher now detects an existing GNOME Software D-Bus instance and reports
why it cannot inject into that process. Module loading, non-Wayland displays and
missing headerbars are reported in the terminal and `logs/integrations.log`.
These diagnostics do not by themselves prove the controls are visible.

## Equibop: Electron/Ozone

For the AUR package, close the running Equibop process and use:

```sh
python3 run.py ozone
```

The launcher reads the installed AUR launcher to find its Electron runtime and
`app.asar` payload. It prepares a cached private copy, preserving packaged
helpers such as arrpc. It does not compile Equibop or require a source checkout.
The original AUR package remains unchanged. Its existing flags file is read.

Node.js/npm or the `asar` CLI is required for archive adaptation. If the CLI is
missing, `npx` obtains the official `@electron/asar` utility on first use. This is
an archive conversion step, not an Equibop build. The private copy is reused
until the installed payload or adapter changes. A bundled installation can be
selected with `--installed /path/to/equibop`. Flatpak and AppImage launchers are
not supported by this path. `--source` retains the older source-build experiment.

The adapter replaces the existing in-app control group only after finding it.
Use Equibop's custom titlebar setting. If the group is missing it retains the
original controls and emits a warning. It reuses the existing application window
bridge and keeps sandboxing/context isolation enabled; no debug port is opened.

Size, spacing, colors, order and side follow Lua. Minimize still uses Electron's
native behavior, not Floatland's minimized-window storage. Auxiliary windows,
app-ID grouping and overview integration need live validation. This remains an
Equibop adapter, not a universal Ozone injector. Integrity-protected packages
may refuse the private archive; no integrity or sandbox protection is disabled.

## Validation boundaries

233 Python/Lua tests and four standalone C++ interaction suites pass on macOS.
Installed-package preparation is covered with fixtures; actual AUR application
launch and archive repacking are not validated here. The full Hyprland plugin, GTK module, Qt module and Equibop build
have not been compiled or run in Linux for this release. Treat these adapters
as experimental until those checks pass.
