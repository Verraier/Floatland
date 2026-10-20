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
- `native/hyprbars/stacking-input.hpp` and `stacking-snap.hpp` — the limits of native input
  and IPC capabilities;
- `shell/services/Tiling.qml` — the link between the shell and layout control;
- `README.en.md` and the Lua configuration — requirements and integration.

Floatland stays under GPL-3.0-or-later; the full GPL v3 text is in `LICENSE`.
The control principles and the set of snap zones were borrowed; the Python code was written anew.
The full shell source, its images, fonts and third-party libraries are not included.
The origin of the separate native extension is given below.
The license does not imply support or endorsement by Hyprstack.

## Native title bars (0.2.0a1)

This separate plugin develops the Floatland 0.2.0a1 code and uses the decorations/render-pass
integration structure, the Pango/Cairo rendering and the native input of Hyprbars and of the
studied Hyprstack. The BSD-3-Clause notice of Hypr Development is kept in `LICENSE.hyprbars`.
`check_sdk.py` adapts the ABI check from Hyprstack's `distribution/check_headers.py`.
The coordinate core, click state, addressed bridge and the minimal titlebar were written for
Floatland. The API was checked against the official Hyprland v0.56.2 sources:
https://github.com/hyprwm/Hyprland/tree/v0.56.2

## Third-party summary

| Project | Author | License | Use in Floatland |
|---|---|---|---|
| hyprstack-shell | hase9awa and contributors | GPL-3.0 | floating/tiling model, snap zones, SDK check (adapted) |
| hyprbars (hyprland-plugins) | Hypr Development | BSD-3-Clause | native/titlebar.cpp derived; notice in native/LICENSE.hyprbars |
| Hyprland | vaxerski and contributors | BSD-3-Clause | compositor and plugin API (v0.56.2) |
| Hyprtasking | Raymond Bian and contributors | BSD-3-Clause | overview API/input behaviour reference; optional external plugin |
| Qt (qtwayland private APIs) | The Qt Company and contributors | LGPL-3.0 / GPL-3.0 / commercial | optional `integrations/qt` prototype links against the user's own Qt; no Qt source is vendored |
