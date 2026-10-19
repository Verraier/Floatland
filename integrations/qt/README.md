# Experimental Qt client-side titlebar

This optional module is a **first prototype**, not a replacement for all native
Floatland titlebars. GTK, libadwaita and Electron/Ozone are not implemented here.
The compositor and daemon work without this entire directory.

## Try it

Start this version of Floatland normally with `python3 run.py`. In another terminal:

```sh
python3 run.py qt -- your-qt6-application
```

The launcher configures and builds the optional module automatically, then starts
only the named application with its environment. Close existing instances first:
single-instance programs may forward the request to an older unmodified process.
Use a small Qt application for the first test, not a session-critical application.

Firefox is not a Qt application and cannot use this module. Installing Qt 5
does not help: this module targets Qt 6 only. Known non-Qt launch commands are
rejected before compilation.

Requirements: Linux, CMake, C++17, Qt 6.8+ Core/Gui/Network/WaylandClient and matching
**private development headers**. The application must use a compatible Qt build.
Qt 5, bundled incompatible Qt versions, Flatpak/Snap containers and applications
that draw their own frameless headers are not supported by this prototype.
Build without launching: `python3 run.py qt --build-only`.

The code was checked against the upstream Qt 6.8 and 6.10 decoration interfaces,
but has NOT been compiled or exercised on Linux in this development environment.
The normal Floatland build does not require Qt and does not build this module.

## Implemented

- A decoration rendered by Qt in the application's own Wayland surface, with
  vector buttons, gradients, side/order settings, title alignment and colors.
- Circle hit testing and cancellation when releasing outside the pressed button.
- Moving/resizing through Qt's Wayland input API.
- Addressed close/minimize/maximize requests to the Floatland daemon. These use a
  per-window random app-ID marker plus the application's PID, not active-window focus.
- Normal Floatland titlebar suppression only for windows tagged by the loaded CSD.
- Lua appearance export and reload while the launcher is running. Invalid edits
  retain the previous settings. Diagnostics go to the launching terminal.

## Limits of this first prototype

- Native Floatland snap-by-drag and its palette are not connected to Qt moves yet.
  Addressed window commands remain available.
- Automatic hiding of the client titlebar in tiling mode is not implemented.
- The native elastic drag/spring effect and rounded frame are not ported yet.
- Only the appearance properties used by the implementation are supported;
  animation/texture options are not feature-identical to the compositor titlebar.
- The experimental app ID contains `.floatland-csd-<token>`. This may affect external
  desktop grouping and app-ID-specific rules; Floatland strips the suffix for icon
  lookup and size memory. This marker is a prototype bridge, not a final protocol.
- The launcher must remain running for live appearance updates. Applications that
  fork/detach may keep their initial appearance after the launcher exits.
- If Qt rejects the module, its own decoration fallback may appear alongside the
  normal Floatland titlebar. Restart the application normally to recover.
- If the daemon stops, CSD button actions report an error rather than guessing a
  target. Restart the application normally to return to the ordinary titlebar.

## Roll back

Close the test application and launch it normally, without `run.py qt`.
No desktop files, system plugin paths or global environment variables are modified.
The `integrations/` directory can be removed; ordinary `run.py` remains usable.

## API references

No Qt source is vendored. The implementation uses Qt private APIs, whose ABI is
version-specific:

- https://github.com/qt/qtwayland/blob/6.8/src/client/qwaylandabstractdecoration_p.h
- https://github.com/qt/qtbase/blob/6.10/src/plugins/platforms/wayland/qwaylandabstractdecoration_p.h
- https://github.com/qt/qtwayland/blob/6.8/src/client/qwaylanddisplay.cpp

The last source defines `QT_WAYLAND_DISABLED_INTERFACES`, used only for the child
process to avoid server-side decoration negotiation. Qt retains its own licenses;
Floatland's optional module is GPL-3.0-or-later like the parent project.
