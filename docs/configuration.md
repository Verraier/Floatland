# Floatland settings (0.6.5e)

Working directory: `$XDG_CONFIG_HOME/floatland` or `~/.config/floatland`.
`python3 run.py config init` creates the files; `config show` validates them without Hyprland;
`reload` applies them in a running unified session. During a normal `run.py` session, Lua changes
are also applied automatically after a short pause in saving.
`config reference` prints the new templates with English comments without changing user files.
`config format` rewrites old auto-generated Lua files into commented templates, keeping the values;
the originals are kept next to them as `*.lua.before-format`. Files without a migration marker are not touched.
For another directory, `config init/show/path` accept `--dir /path`; this does not change the
directory of the running session.

Each file in `config/` returns a table. The main `init.lua` assembles them:

```lua
return {
    windows = section("windows"),
    titlebars = section("titlebars"),
    snapping = section("snapping"),
    overview = section("overview"),
    switching = section("switching"),
    bindings = section("bindings"),
    theme = section("theme"),
    experimental = section("experimental"),
}
```

You can use local variables, expressions and `require`; module lookup includes the directory of
`init.lua`. A missing section file means default values. An unknown key or a wrong type is an
error. `false` and `true` are not numbers. Lua runs as the user in a separate process with a
5-second timeout; this is not an isolated security environment, so only run trusted configs.

## windows.lua

| Field | Default | Values |
| --- | --- | --- |
| default_mode | floating | floating / tiling |
| gap | 10 | integer 0–100 |
| width / height | 0.65 / 0.72 | fraction of the work area, 0.1–1 |
| cascade_step | 28 | integer 0–100 |
| exclude_classes | {} | list of Python regular expressions |
| workspace_modes | {} | map of workspace names to floating/tiling |

```lua
return {
    default_mode = "floating",
    gap = 10,
    workspace_modes = { ["2"] = "tiling" },
    exclude_classes = { "^example-dialog$" },
}
```

Workspace names are string keys: `["2"]`, not `[2]`.
A workspace mode already chosen via `toggle` and `window-toggle` take priority over the default
settings. Migration also keeps the old `titlebar_height` and `titlebar_style`; they are meant for
the former separate daemon/hyprbars. The unified session sets the native titlebar height itself:
32 px, or 0 when disabled.

## Colors and units

Colors are `#RRGGBB` strings, opacity is a number 0–1. Time is in seconds.
Numeric sizes are logical units; the monitor scale is applied at render time.
The shared theme sets colors before components: for example `titlebars.color` overrides
`theme.titlebar`. These duplicate fields are omitted from the standard component files.
In the 0.6.1 migration, shared colors are written to the theme. If the config was migrated in
0.6.0, the local fields are kept: move the colors into the theme and remove the duplicate
component fields. A warning is now printed when a component color overrides the theme.

## titlebars.lua

| Field | Default | Range / type |
| --- | --- | --- |
| `enabled` | `true` | boolean |
| `color` | `#1b2029` | #RRGGBB |
| `opacity` | `1.0` | 0–1 |
| `text_color` | `#edf2ff` | #RRGGBB |
| `font_size` | `10` | 6–24 (integer) |
| `close_color` | `#f55c57` | #RRGGBB |
| `minimize_color` | `#fabe2e` | #RRGGBB |
| `maximize_color` | `#33c459` | #RRGGBB |
| `button_shift` | `0.9` | 0–2 |
| `button_stretch` | `1.5` | 0–2 |
| `return_duration` | `0.28` | 0.05–0.5 |
| `rebound` | `0.12` | 0–0.15 |
| `texture` | `true` | boolean |

## snapping.lua

| Field | Default | Range / type |
| --- | --- | --- |
| `enabled` | `true` | boolean |
| `color` | `#4d99ff` | #RRGGBB |
| `opacity` | `0.18` | 0–1 |
| `duration` | `0.14` | 0.035–1 |

## overview.lua

| Field | Default | Range / type |
| --- | --- | --- |
| `enabled` | `true` | boolean |
| `blur` | `true` | boolean |
| `color` | `#090a0f` | #RRGGBB |
| `opacity` | `0.22` | 0–1 |
| `enter_duration` | `0.24` | 0.035–1 |
| `exit_duration` | `0.24` | 0.035–1 |

## switching.lua

| Field | Default | Range / type |
| --- | --- | --- |
| `enabled` | `true` | boolean |
| `color` | `#1c1f2b` | #RRGGBB |
| `opacity` | `0.93` | 0–1 |
| `font_size` | `14` | 8–24 (integer) |
| `icon_size` | `80` | 32–128 (integer) |
| `enter_duration` | `0.09` | 0.035–0.5 |
| `exit_duration` | `0.07` | 0.035–0.5 |

## bindings.lua

| Field | Default | Range / type |
| --- | --- | --- |
| `enabled` | `true` | boolean |
| `alt_tab_key` | `15` | 1–255 (integer) |
| `overview_key` | `34` | 1–255 (integer) |

## theme.lua

| Field | Default | Range / type |
| --- | --- | --- |
| `titlebar` | `#1b2029` | #RRGGBB |
| `text` | `#edf2ff` | #RRGGBB |
| `snap` | `#4d99ff` | #RRGGBB |
| `switching` | `#1c1f2b` | #RRGGBB |
| `overview` | `#090a0f` | #RRGGBB |

## How the switches behave

`titlebars.enabled` hides the title bars and excludes their height from window placement.
`snapping.enabled` disables snapping while dragging; the `snap left` and other commands remain
available. `overview.enabled` and `switching.enabled` turn off the corresponding interface,
including invocation through the CLI. `bindings.enabled` disables the built-in keys but leaves
the interface commands available.

`bindings.lua` uses Linux evdev codes: 15 = Tab, 34 = G. The modifiers are fixed: Alt for the
switcher and Super for the overview. Navigation keys, Esc, Enter and modifier codes are reserved.
Arbitrary bindings for other actions are still set in the Hyprland config, not in this file.
Note: reverse switching with Alt+Shift+Tab does not work yet.

`button_shift` sets a small shift of the button center, `button_stretch` sets the deformation in
the direction of the mouse; 0 turns the corresponding effect off. `rebound = 0` turns off the
rebound while keeping the return. `texture = false` removes the gradient highlights of the
buttons. `experimental.lua` currently accepts only `return {}`. There are no Vulkan/OpenGL
switches in this version: rendering is done by the existing Hyprland plugin.

## Migration and errors

If `init.lua` already exists, initialization overwrites nothing.
If only `config.json` exists, it is validated and migrated into sections; the original is kept.
If an old JSON and any `config/*.lua` exist at the same time without `init.lua`, automatic
migration stops: you need to choose the settings manually so that two sources are not mixed.
Make a backup and finish `init.lua` yourself, or move the unfinished Lua files into a separate
folder before migrating again. This situation is also possible after an interrupted file creation.

To return to 0.5.92, use the saved archive: it reads the former `config.json`.
Edits to the new Lua files are not carried back into JSON automatically.

Reload validates the whole config before changing any parameters. Read, Lua and schema errors
keep the current values. The plugin validates the complete set before applying it.
An active overview/Alt+Tab is closed on a successful reload. If the subsequent window
reconciliation fails, a warning is returned; the configuration is already applied and the
reconciliation will be repeated. This is not a transaction over windows. A standalone
`daemon --config ...` supports legacy JSON and Lua but does not manage the native plugin's
settings: for the full interface, run the unified `run.py`.

## Additions in 0.6.1

In `titlebars.lua`:

| Field | Default | Purpose |
| --- | --- | --- |
| buttons_side | "right" | left/right — side of the button group |
| buttons_order | {"maximize", "minimize", "close"} | Order from the inside of the window to the outer edge; mirrored when on the left (default close → minimize → maximize); omitted buttons are hidden; {} hides all |
| title_alignment | "left" | left/center/right, in the free space after the buttons |
| title_enabled | true | Show the title text |
| icons | true | Action icons |
| hover_only | true | Show icons only on hover or while held |
| hinting | true | Snap still strokes to physical pixels |
| highlight | 0.22 | Lightening while held inside the button, 0–0.6 |
| growth | 0.8 | Extra radius while held, 0–2 logical px |

Buttons always reserve the edge of their side. Title centering is limited to the remaining area
and the text is shortened. All settings change rendering and hit-testing consistently. A reload
during a press cancels that press so that the new layout does not run an accidental action on
release. Strokes snap to pixels at rest; during motion the geometry stays continuous to avoid
jitter.

In `snapping.lua`: `edges`, `palette` and `preview` are separate boolean switches for the
edges/corners, the top palette and the snap area. All default to true.
`color` in titlebars/snapping/switching/overview takes explicit priority over `theme.lua`.
`text_color` is also available for titlebars. Commented-out examples are in the templates.

Watching covers the Lua files under the `init.lua` directory, including local `require`s.
Files outside the directory and changes to environment variables are not tracked automatically;
use a manual reload for them. Lua runs in a separate process, and waiting is moved out of the
daemon loop. Saving during a read rejects the intermediate result. Deleting `init.lua` does not
reset the settings: an error appears in the log.

## switching.lua additions (0.6.2e)

| Field | Default | Range / type |
| --- | --- | --- |
| `style` | `"icons"` | `"icons"`, `"preview"` or `"legacy"` |
| `mouse` | `true` | Hover selects; release Alt or click to activate |
| `preview_width` | `240` | 160–360 (integer), maximum preview-card width in logical px |

`icon_size` stays the maximum for the adaptive styles and a fixed size for `legacy`.
To roll back to 0.6.1.1, remove these three fields from your file first: the old version does not know them.

- `icons`: square rounded cards that adapt to the number of windows and the screen; only the
  selected window shows a label. With many windows there are pages reachable with Tab.
- `preview`: cards with thumbnails in several rows. Snapshots are prepared one at a time and a
  repeated Tab on the same page does not re-create them. These are static snapshots, not live video.
- `legacy`: the former fixed-size scheme with permanent labels.

## Persistent application sizes (0.6.2e)

`windows.remember_sizes` defaults to `true`. Normal floating sizes are saved atomically
to `$XDG_STATE_HOME/floatland/window-sizes.json` (default `~/.local/state`).
The key is `initialClass`, falling back to `class`. Titles and process IDs are not persisted.
The last changed window of a class wins. Snap/fullscreen/minimized sizes are excluded.
Sampling runs once per second and on controller refresh; a resize immediately followed
by external close may retain the previous sample. Invalid files are preserved and logged.
Set `remember_sizes = false` to disable both recording and restoration.

## Overview ordering (0.6.3e)

Overview has no new settings. Windows are ordered by application class, then by decreasing
window area within a class; focus history does not reorder them. The label is shown only for
the selected window.

## Qt client-side titlebar (0.6.5e, experimental)

Titlebar appearance settings (colors, button side/order, title alignment) are also exported to
the optional Qt prototype while its launcher runs. See
[integrations/qt/README.md](../integrations/qt/README.md).

## Stable 0.6.7 additions

- `titlebars.button_size`: resting diameter, 8..20 logical pixels, default 14. Icons and hit targets follow the diameter.
- `titlebars.button_spacing`: gap between circles, 0..40 logical pixels, default 18.
- `windows.remember_xwayland_sizes`: false by default; avoids applying saved application sizes to Steam/XWayland windows.
- Right-click a native titlebar or run `python3 run.py pip` to enter/leave the current PiP window mode. Green restores the previous geometry. This differs from the planned 0.6.8e mini-mode.
