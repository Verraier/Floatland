# FloatLand

[English](README.md) · [Русский](README.ru.md)

> **Disclaimer:** this project was made with AI.

Floating window management for [Hyprland](https://hyprland.org/) with quality-of-life features built in.
This is not a serious project — I made it for myself — but you may like it too.

**Target:** Hyprland **0.56.2** (headers of the exact installed version are required to build).

## Features

- **Floating / tiling toggle** with remembered window geometry
- **Title bars** — native, configurable buttons (close / minimize / maximize), animations
- **Snapping** — drag a title bar to a screen edge or the top palette
- **Alt+Tab** window switcher with icons
- **Overview** — window overview of the current workspace (`Super+G`)
- **Lua configuration** with live reload on save

## Requirements

- Python 3.9+
- CMake 3.22+, a C++23 compiler, pkg-config
- Hyprland 0.56.2 headers
- pixman, libdrm, libinput, libudev, wayland-server, xkbcommon, pangocairo, librsvg
- A Lua interpreter (`lua`, `lua5.4`, `lua5.3` or `luajit`) — or the Python package `lupa`

## Install & run

```sh
git clone https://github.com/Verraier/Floatland.git
cd Floatland
python3 run.py
```

Building, loading the plugin and starting the daemon are automatic. Keep the terminal open.
Log: `logs/session.log`. Stop with `Ctrl+C` or `python3 run.py stop`.

Your Hyprland config is **not** modified automatically. To wire it up manually, see
[examples/hyprland.lua](examples/hyprland.lua).

## Configuration

On first run, a config is created in `~/.config/floatland/` (respects `$XDG_CONFIG_HOME`):

```text
~/.config/floatland/
├── init.lua
└── config/
    ├── windows.lua
    ├── titlebars.lua
    ├── snapping.lua
    ├── overview.lua
    ├── switching.lua
    ├── bindings.lua
    └── theme.lua
```

```sh
python3 run.py config init        # create the config without starting Hyprland
python3 run.py config path        # print the path to init.lua
python3 run.py config show        # validate and show effective values
python3 run.py config reference   # documented list of all options
python3 run.py reload             # apply manually (auto-reload also happens on save)
```

Full reference: [docs/configuration.md](docs/configuration.md).

## Controls

| Key / action | What it does |
|---|---|
| `Alt+Tab` | Switch windows (release Alt to select, `Esc` to cancel) |
| `Super+G` | Overview of the current workspace |
| Drag title bar to edge / palette | Snap |
| `python3 run.py toggle` | Floating ⇄ tiling |
| `python3 run.py snap left`, `maximize`, `restore`, `center`, `minimize`, `pin` | Window commands |

## Development

```sh
python3 tools/check.py   # Python/Lua tests + standalone C++ tests
```

Layout: `src/floatland/` (Python), `native/` (C++ plugin), `tests/`, `docs/`, `examples/`.
See [docs/architecture.md](docs/architecture.md).

## Status

Tested logic-wise on macOS; the full plugin needs more testing on real Hyprland.
Expect rough edges. Known: `Alt+Shift+Tab` (switching backwards) does **not** work yet. See [CHANGELOG.md](CHANGELOG.md) and [docs/bugs/](docs/bugs/) for known issues.

## Credits

Big thank you — without these projects this wouldn't have happened:

- **[hyprstack-shell](https://github.com/hase9awa/hyprstack-shell)** by hase9awa and contributors (GPL-3.0) —
  the floating/tiling model, geometry memory and snap zones were studied from it; `native/check_sdk.py`
  adapts its header/ABI check.
- **[hyprbars](https://github.com/hyprwm/hyprland-plugins/tree/428bfcd1c9ee34965400bb359349f518140c9920/hyprbars)**
  by Hypr Development (BSD-3-Clause) — the title bar decoration / render-pass / input approach in
  `native/titlebar.cpp` is derived from it.
- **[Hyprland](https://github.com/hyprwm/Hyprland)** by vaxerski and contributors (BSD-3-Clause) — the compositor
  and plugin API this is built on (checked against v0.56.2).
- **[Hyprtasking](https://github.com/raybbian/hyprtasking)** by Raymond Bian and contributors (BSD-3-Clause) —
  overview API and input behaviour were checked against it; the optional legacy integration in
  `src/floatland/overview.py` uses it via hyprpm.
- Libraries used at build/run time: Pango, Cairo, librsvg, pixman, libdrm, libinput, xkbcommon,
  wayland, and Lua / [lupa](https://github.com/scoder/lupa) for configuration.

Details and third-party notices: [NOTICE.md](NOTICE.md), [native/NOTICE.md](native/NOTICE.md).

## License

GPL-3.0-or-later — see [LICENSE](LICENSE). Native code derived from Hyprbars keeps its
BSD-3-Clause notice in [native/LICENSE.hyprbars](native/LICENSE.hyprbars).
