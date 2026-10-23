# Floatland Lite — 0.7.0-lite3

Standalone floating window management for Hyprland. This is the first test release of the `lite` branch; it does not replace stable main yet.

Developed with AI assistance. [Русский](README.ru.md) · [Configuration and architecture](docs/lite.md) · [Shell API](docs/shell-api.md)

## What stays

- Floating/tiling modes, remembered geometry and per-application size memory.
- A compact capsule with close, minimize and fullscreen controls, an explicit drag handle, window menu, SVG icons and configurable effects.
- A tiny passive indicator when the capsule is collapsed. Hover reveals the controls; only the handle starts dragging. Right-click opens the window menu.
- Snap zones and the top snap palette, always-on-top and all-workspaces controls.
- Icons-only Alt+Tab and a compact right-hand overview sidebar on Super+G.
- Lua settings, reload, window rules, logs and an addressed local control socket.

Toolkit integrations and full-width external titlebars are removed. Overview no longer suppresses normal windows or installs renderWindow/renderFadeouts hooks. It still captures thumbnails through the native plugin; it is not independent of Hyprland's graphics ABI.

## Run

Extract the archive, enter its folder and run:

```sh
python3 run.py
```

The launcher builds and loads the plugin and starts the daemon. Keep this terminal open. Stop the old Floatland session before launching lite: both use the same per-session lock/socket. Disable any old global integration launcher overrides through the old installation before removing it.

Requirements: Linux, Hyprland **0.56.2** with matching development headers, Python 3.9+, CMake 3.22+, a C++23 compiler, pkg-config, pixman, libdrm, libinput, libudev, wayland-server, xkbcommon, pangocairo and librsvg. Lua requires `lua`, `lua5.4`, `lua5.3`, `luajit` or Python `lupa`.

```sh
python3 run.py config path
python3 run.py reload
python3 run.py windows
python3 run.py stop
```

Settings live in `~/.config/floatland-lite/` (or `$XDG_CONFIG_HOME/floatland-lite/`). Old Floatland settings are not migrated automatically. Edit these installed settings, not `src/floatland/defaults`. Logs: `logs/session.log`. Optional autostart example: [examples/hyprland.lua](examples/hyprland.lua).

## Validation

```sh
python3 tools/check.py
```

This runs Python/Lua regressions and five standalone C++ logic suites. It does not compile the complete plugin or verify graphics. Full Linux build, blur, input handling and multi-monitor testing remain required; see [smoke checks](docs/linux-smoke-test.md).

License and attribution are retained in LICENSE, NOTICE.md and native/LICENSE.hyprbars.
