# Changelog

Entries before 0.3.5 are listed at the bottom. Newest first.

## 0.6.1.1

- Highlight, press and release now test the button circle, not the whole 32×32 cell.
- The activation area no longer stretches with the animation, which caused the highlight to flip back and forth.
- The reason why a user's Lua config was not applied is still unknown: the log that was sent shows identical settings being read and no file-change events.

## 0.6.1

- Automatic reload of user Lua files, delayed after saving, without blocking the daemon loop on Lua.
- Config path, content version and confirmation from the native plugin are shown in the terminal; invalid values are not applied.
- Warning when a component's local color overrides the shared theme; the new JSON migration no longer duplicates colors.
- Button side/order/hiding, title alignment/hiding, separate switches for icons and effects.
- Removed the 500 ms cancel: leaving and returning control the highlight, releasing inside the button runs the action.
- Icon strokes fit the display scale, stronger hold/stretch, a single smooth rebound.
- Separate edges/palette/preview switches for snapping.
- `config reference` and English template comments with units and ranges.
- `run.py` keeps a rotated log and shows warnings/errors and plugin diagnostic events.
- 186 Python/Lua tests and standalone C++ tests; the full plugin still needs testing on Linux.

## 0.6.0

- Regular branch based on 0.5.92; no experimental features.
- Package moved to `src/floatland`; the single `run.py` entry point is kept.
- Lua: `init.lua` and separate `windows/titlebars/snapping/overview/switching/bindings/theme/experimental` files.
- `config.json` migration without deleting the source and without overwriting existing Lua.
- `config init/show/path` and `reload` with up-front validation of the whole settings set.
- Colors, opacity, button and transition parameters, Alt+Tab sizes, component switches and keys.
- `tools/check.py` combines the Python/Lua regression checks and the standalone C++ logic tests.
- A full plugin build and visual check of this version require Linux/Hyprland.

## 0.5.92 — moved to the regular branch

- 0.5.92e behavior is kept. According to user reports the new overview procedure survived repeated toggling, the Steam scenario did not reproduce, and no RAM growth was seen in a short test.
- This is the result of user testing, not a guarantee of no leaks or a long stress test.

## 0.5.92e — titlebar buttons

- Vector gradient and a thin edge highlight instead of a flat fill.
- Rounded close/minimize glyphs and two diagonal arrows for maximize.
- Center shift up to 0.65 logical px, directional stretch of the leading edge up to 1.05 px.
- Return in 220 ms with one weak rebound (6% deformation), without moving the click area.
- Action cancel on mouse leave/hold and the shared icon highlight of the button group are kept.
- Overview logic unchanged. A full build and visual check require Linux.

## 0.5.91e (experiment)

- State machine Preparing / Entering / Visible / Selecting / Exiting / Hidden.
- One snapshot per queue step, stale preparation generations are cancelled.
- A repeated Win+G reverses the normal animation without re-collecting the scene.
- Selection is confirmed after the window is restored and raised; wait timeout.
- Normal rendering is restored at a frame boundary.
- 160 Python/Lua tests and a standalone 10,000-reversal test with UBSan pass.
- A compact GPU cache is not implemented; fallback icons and the Steam SIGSEGV remain limitations.
- Details: `docs/experiment-0.5.91e.md`. The whole plugin was not tested on Linux.

## 0.5.9

- Audit of all main components; report in `docs/stability-audit-0.5.9.md`.
- Protection against using a destroyed decoration in a deferred render pass.
- Overview cleanup on workspace/monitor change and window close/move.
- Mouse press/release balance, cancelling an old Alt+Tab and MRU cleanup.
- The preview no longer blocks restore; window identity is re-checked.
- Fixed start after a stale socket and the legacy unload check.
- SHA256 of the downloaded plugin in `logs/session.log`.
- 156 Python/Lua tests and standalone C++ tests with UBSan pass.
- The SIGSEGV after Steam remains open; a Linux check is mandatory before release.

## 0.5.8

- Snapshots of minimized windows are kept until hidden; addressed calls with PID checks.
- The cache is limited by a total snapshot budget and cleared on restore/close.
- Minimized previews fade smoothly in the cards when leaving overview.
- Overview teardown moved to `render.preChecks`, before normal window filtering.
- Tests for snapshot save order, restore, errors and the Lua bridge.
- A full build and visual check require Linux/Hyprland 0.56.2.

## 0.5.7

- Shared adaptive overview scale, all windows without pages.
- Highlight and clicks follow the bounds of the visible previews.
- Filter for normal window rendering under overview without changing window state.
- `boundingBox` for live blur and the snapshot memory limit are kept.
- Geometry checked with 1–64 windows; the new render hooks require a Linux check.

## 0.5.6

- Added the mandatory `boundingBox` for the overview pass with live blur.
- The area is the whole current monitor in logical local coordinates; it accounts for the background and preview animation outside the final cards.
- `needsLiveBlur` is enabled only on the overview monitor, not while snapshots are being made.
- Blur restored; 0.5.5 remains the variant without blur.
- Fixed a render-pass contract violation found in the sources; live confirmation that the crash is gone is still required.

## 0.5.5

- Disabled overview live blur after a report of an assert in OpenGL `endRender` on Super+G.
- Removed the `blurMainFramebuffer` call from the late render pass; plain dimming is kept.
- Settings, geometry, snapshots and controls are kept. The fix still needs a Linux check.

## 0.5.4

- Swapped minimize/maximize; shorter, thicker icons.
- `appearance` in `config.json`: titlebar color/opacity, snap area, Alt+Tab; Alt+Tab font and icon size.
- The snap area smoothly changes its rectangle and opacity and uses the window rounding.
- Alt+Tab limited to the current workspace, short fade-in/fade-out added.
- Overview: removed the background/border of the shared panel, added live blur of the backdrop; shrunken cards are laid out by window proportions.
- The config is created only if missing; an existing one is kept.
- Added checks for settings, the Lua bridge, workspace filtering and card layout.

## 0.5.3

- Smooth shared icon fade-in when hovering any titlebar button.
- 6 px icons, 1.2 px lines, dark shades of the button colors instead of near-black.
- Fixed button center with slight deformation instead of following the cursor.
- Reduced magnification and stretch amplitude; the action-cancel logic is kept.

## 0.5.2

- Overview enter/exit animation from the original on-screen snapshot rectangles.
- Snap-drop keeps gesture ownership when DragController finishes early.
- Dark colored button icons, lower saturation of inactive buttons.
- Magnification and limited stretch of the pressed button, action cancelled after 500 ms.
- A custom bottom content mask is not implemented; rounding settings unchanged.

## 0.5.1

- Alt+Tab: horizontal cards, system application SVG/PNG icons, vector fallback.
- Overview: own grid of current-workspace windows instead of Hyprtasking; static snapshots, pages, selection by mouse/arrows/Enter.
- Minimized windows of the current workspace can be selected without restoring the other windows.
- Top corners of the title strip follow the window rounding; content corners unchanged for now.
- The expected second-instance lock prints instructions without a traceback.
- New native dependency: `librsvg-2.0`. The external overview is no longer installed automatically.

## 0.5.0 — Alt+Tab and overview

- MRU Alt+Tab (Shift+Tab backwards exists in the code but does not work in practice), commit on Alt release, Escape without changing focus.
- Addressed window selection across all regular workspaces, including minimized ones; only the selected window is restored.
- Native text task-switcher panel, no separate toolkit process.
- Super+G: Hyprtasking, connected automatically through hyprpm, plus a list of minimized windows.
- The temporary linear layout and the provider's mouse buttons are restored on normal exit.
- hyprpm output and interactive questions are available in the terminal; output is written to the shared log.
- 130 Python/Lua tests pass. The new C++ UI was not built locally on macOS.

## 0.4.0a5 — restart

- Only the service `applied` cache is reset when a new daemon starts.
- Native resync of existing windows on load and after the daemon subscribes to events.
- Forced recomputation of titlebar geometry and damage of existing windows.
- Mouse-capture state is reset on plugin re-initialization.
- The new `.so` is installed by atomic file replacement, not by overwriting the inode.
- Three restart regression tests: mode, position and snap memory.
- Changes from a4 included; a live native reload of a5 has not been tested here.

## 0.4.0a4 — snap and restore geometry

- The original coordinates are saved before drag, not the position near the palette.
- Leaving snap during drag restores the pre-snap size and keeps the grab point.
- DragController receives the new initial geometry after the size change.
- Native position and size update in one call instead of an intermediate resize.
- The old IPC without the plugin keeps the resize/move fallback.
- Restore uses the original monitor if available; otherwise it fits the window into the current one.
- Six geometry-memory regression tests, extra C++ drag checks.

## 0.4.0a3 — single launcher

- Python and native in one archive, started with `python3 run.py`.
- Build before stopping the old daemon, automatic replacement and plugin loading.
- Shared log `logs/session.log`, plugin version check, daemon version in `status`.
- Native titlebar height 32 is applied without changing `config.json`.
- On stop the new plugin is unloaded and the previous hyprbars is restored.
- Eight launch and error-handling tests. Native a2 kept.

## 0.4.0a1 — experimental bridge

- Versioned addressed events of the separate `floatland-bars` plugin.
- PID and window-existence check without falling back to the active window on error.
- Eight tests: addressed actions, stale and malformed messages.
- The upstream hyprbars integration 0.3.5 is kept unchanged.

## 0.3.5
Titlebars you can configure (everything below ships together because it is one generator).

### 0.3.0 – buttons
- New `pin` command: pin/unpin a floating window on all workspaces (also unpins windows
  Floatland otherwise ignores because they are pinned).
- Titlebar buttons are data, not code: any `floatland <action>` or shell command can be a
  button (`close`, `maximize`, `minimize`, `pin`, `window-toggle`, `snap left`, …).

### 0.3.1 – button polish
- Icons appear on hover (`icons = "hover"`, default) or always.
- Buttons can be aligned right or left; space above and below each button is always equal
  (bar height minus button size is forced even).
- Different colours for the focused and unfocused window; inactive button colour.

### 0.3.5 – your own file
- `floatland titlebars init` writes `floatland-titlebars.lua` (regenerated) and
  `floatland-buttons.lua` (yours: created once, never overwritten) into `~/.config/hypr/`.
- Mistakes in your file are reported with the offending key, never silently ignored.
- `own_header_classes`: no Floatland bar on apps that draw their own header.
- `decorations = { gtk3, qt }`: ask GTK3/Qt apps not to draw their own header.
- Tiled windows never get a titlebar.
- `config.json` `titlebar_style` still works as a default beneath your Lua file.

### Not done (needs changes inside the plugin itself)
- Vertical position of the glyph inside a button; sharper icons at fractional scales.

## 0.2.0a2
- No bundled native code: titlebars use the official hyprbars (hyprpm or a SHA-256
  verified prebuilt `.so`).
- Removed `native/` and the private titlebar event bridge.
