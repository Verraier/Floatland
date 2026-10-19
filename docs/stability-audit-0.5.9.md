# Stability audit 0.5.9 — 19 October 2026

Status: source audit and local regression checks are complete.
This is a candidate for testing on Linux, not a confirmation of compositor stability.
The audited version was the unified one from `development/floatland-unified`, starting from 0.5.8.

## Fixes

| Area | Problem found | Change |
|---|---|---|
| Deferred titlebar rendering | The render pass kept a raw pointer to the decoration without checking its lifetime | `DeferredPtr` with a separate lifetime marker; draw and boundingBox skip a destroyed decoration, including address reuse |
| Titlebar input | During hit-testing the surface resource was dereferenced unchecked | The surface and its resource are checked before the seat grab check |
| Overview teardown | After hide, references to the window list, icons and the pressed card remained | Full cleanup of temporary state; only the expected button releases are kept |
| Overview/Alt+Tab context change | A workspace change, monitor disconnect or window close/move did not invalidate the UI | Context is checked before building a frame; the UI and the Python cycle are cancelled; opening is forbidden during drag/lock/constrained pointer |
| Mouse | During the closing animation a release was swallowed without finishing `mouseOwned`; right/middle buttons were not accounted in pairs | Every swallowed press and its release are accounted for, even if the UI is already gone |
| Alt+Tab | An old cycle could outlive a switch to another workspace, especially with a pinned window | The cycle is bound to the workspace; the old commit is cancelled; the next cycle starts on the new workspace |
| Alt+Tab history | Closed windows stayed in the MRU without limit | Missing identities are removed when the list is built |
| Snapshots and restore | An error in the optional preview stopped minimize/restore | The error is logged, the main operation continues |
| Addressed restore | After a minimized window was moved, a repeated query did not check identity | Identity is checked before resize/focus; a foreign window at a reused address is not changed by later commands |
| Restart | `stop_previous` checked only the direct cause, although the CLI wraps the socket error again | The exception chain is checked; a timeout is not ignored |
| Build stop | After `terminate`, waiting for the process had no limit | After five seconds — `kill` and `wait` |
| State file | A JSON array/null caused `AttributeError` | A clear `ValueError`, the original file is kept |
| Legacy hyprbars remove | An unload/disable error was ignored and the install record was deleted | On error the record and the binary are kept; success is verified |
| Diagnostics | `session.log` lacked the hash of the specific loaded `.so` | Path and SHA256 of the binary are recorded |

The first items are defensive changes made after reading the code. A use-after-free was not
reproduced in a real Hyprland. They must not be credited with fixing the specific Steam crash.

## What was checked

- Startup, build, ABI check, single-instance locks, plugin replacement and unload, daemon stop
  and handling of leftover sockets.
- Addressed commands and Lua escaping, PID/identity, special/pinned/excluded and fullscreen
  windows, mode changes, a new window, controller restart.
- Snap, maximize/restore, center, positions/sizes, panel reserved areas, scale, negative
  coordinates, restore after dragging.
- Minimize, restore, state saving, operation and snapshot errors.
- Alt+Tab: MRU, reverse cycle, cancel, closing the selected window, workspace change.
- Overview: adaptive layout, mouse/keyboard, snapshots, animation completion, normal-render
  filter, live blur bounds, state cleanup.
- Buttons: single drawing and hit-test geometry, hold, drag/release; appearance configuration,
  local icons, legacy Lua and hyprbars installation.

*Note (later testing): the reverse Alt+Tab cycle (Alt+Shift+Tab) is present in the code but does
not work in practice.*

## Automated results

- 156 Python/Lua tests — PASS, including real local Unix sockets and Lua through lupa.
- An extra scenario: 100 cycles of snap → minimize → new Controller from the saved state →
  `restore-minimized` → restore. The original sizes and coordinates are preserved at every
  iteration. This models IPC; it is not 100 Hyprland restarts.
- C++ geometry, hit-testing, 1–64 window layout and `DeferredPtr` — PASS with
  `-Wall -Wextra -Werror`; a repeat run with UBSan — PASS.
- The ASan+UBSan run did not finish in this macOS environment and the processes were stopped.
  There is no ASan result; this is not counted as a successful memory check.
- The full plugin was not built or run: there is no Linux/Hyprland SDK here.
  The success of the standalone C++ test does not mean the whole plugin compiles.

## Open risks and limitations

1. [SIGSEGV after overview → another workspace → Steam](bugs/2026-10-19-steam-after-overview.md)
   remains open. A symbolized stack or a reproduction is required.
2. `renderWindow`/`renderFadeouts` are intercepted through ABI-dependent trampolines.
   The signatures were checked against the local Hyprland 0.56.2 sources. Machine-code
   relocation, driver behavior and unload on Linux are not covered by local tests.
3. Snapshots are limited by a 48-million-pixel budget. Windows without a snapshot show an icon;
   windows minimized before the plugin loaded need a restore/minimize cycle. Rotated monitors
   and invisible parts beyond the screen edge do not get a full preview.
4. Monitor state, fullscreen/direct scanout, layer-shell and animations of different compositor
   configurations need a live check.
5. If a window closes or leaves the current workspace during overview, the whole overview is
   cancelled. This is deliberate behavior of this version to clean up context; dynamic overview
   rebuild was not added.

## Minimal Linux check before release

One archive, one `python3 run.py`. No separate projects are needed.

1. Repeat the Steam scenario: overview → mouse actions → close → another workspace → Steam
   (separately a fresh start and opening an already running application).
2. During overview close one of the applications, change workspace/monitor, lock and unlock the
   session. Check that the UI does not stay on top of windows.
3. Hold a mouse button and close the overview with the keyboard, then release.
   The next click should work normally; check the right button separately.
4. Alt+Tab, Shift+Alt+Tab, Esc, a workspace change before releasing Alt; pinned and minimized
   windows. The old selection must not pull focus back.
5. Snap → restore → minimize → overview → select a window; then Ctrl+C and a new `run.py`.
6. Repeat with a fullscreen application and, if available, a second monitor.

On a new crash, save the crash report, `logs/session.log` and the corresponding `.so` binary at
the path from the log. To identify an unknown address a core dump with the loaded module map is
needed; a single absolute address from the crash report is not enough.
