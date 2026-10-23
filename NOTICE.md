# Origin and license

Floatland is a new Python implementation of the floating/tiling model studied from the
provided archive `hyprstack-shell-main.zip`. It is an independent project, not an official
Hyprstack release and not a full port of the shell.

Original project: https://github.com/hase9awa/hyprstack-shell (license: GPL-3.0)
Author of the original project: hase9awa and the Hyprstack contributors.
The archive contained no Git history, so the exact commit SHA is not known.

Studied:
- `shell/assets/hyprland/layouts.lua` — stacking/scrolling switching, geometry memory,
  exclusion of pinned/special windows, fitting and snap zones;
- the limits of native input and IPC capabilities (which functions need code inside the compositor);
- `shell/services/Tiling.qml` — the link between the shell and layout control;
- `README.en.md` and the Lua configuration — requirements and integration.

Floatland stays under GPL-3.0-or-later; the full GPL v3 text is in `LICENSE`.
The control principles and the set of snap zones were borrowed; the Python code was written anew.
The full shell source, its images, fonts and third-party libraries are not included.
The origin of the separate native extension is given below.
The license does not imply support or endorsement by Hyprstack.

## Window title bars (0.2.0a2)

Floatland did not contain or distribute Hyprbars code or its own C++ plugin at that point.
It downloaded the official hyprbars plugin (hyprwm/hyprland-plugins, BSD-3-Clause) through
`hyprpm`, or accepted a prebuilt `.so` over HTTPS with mandatory SHA-256 verification,
and generated a Lua configuration for it. Version 0.2.0a1, which bundled a C++ plugin that
referred to the Hyprbars structure, is no longer supported.

## Unified package 0.4.0a3

Starting with this alpha, Floatland's own C++ plugin is part of the package again, in `native/`.
The 0.2.0a2 description above applies only to the former variant.
Origin of the native code and notices: `native/NOTICE.md` and `native/LICENSE.hyprbars`.

## Overview 0.5.0

Hyprtasking (Raymond Bian and the project contributors): https://github.com/raybbian/hyprtasking
was used as an external plugin installed through hyprpm. Its sources and binary are not part of
the Floatland archive. The API and input behavior were checked against upstream.
Floatland's native task panel extends the existing code in `native/`.

## Third-party summary

| Project | Author | License | Use in Floatland |
|---|---|---|---|
| hyprstack-shell | hase9awa and contributors | GPL-3.0 | floating/tiling model, snap zones, SDK check (adapted) |
| hyprbars (hyprland-plugins) | Hypr Development | BSD-3-Clause | native/titlebar.cpp derived; notice in native/LICENSE.hyprbars |
| Hyprland | vaxerski and contributors | BSD-3-Clause | compositor and plugin API (v0.56.2) |
| Hyprtasking | Raymond Bian and contributors | BSD-3-Clause | overview API/input behaviour reference; optional external plugin |
| Qt (qtwayland private APIs) | The Qt Company and contributors | LGPL-3.0 / GPL-3.0 / commercial | optional `integrations/qt` prototype links against the user's own Qt; no Qt source is vendored |

## User-contributed control symbols

Close, minimize and fullscreen SVG symbols were contributed by Acrillate for Floatland. Original files are preserved in assets/icon-originals. The distributed close symbol uses equivalent plain SVG transforms for renderer portability; the other symbols retain the contributed geometry.

## Lite 0.7.0

Toolkit integrations and the external Hyprtasking installation path are removed from lite. References above document historical use; the native decoration attribution remains applicable. Lite retains the existing project license and all relevant notices.
