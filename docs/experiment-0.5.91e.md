# 0.5.91e — overview lifecycle experiment

User-facing version name: 0.5.91e. 0.5.9 remains a separate archive for rollback.
In `pyproject` the version is 0.5.91.dev1 (a valid experimental PEP 440 version),
in CMake it is 0.5.91. The log, CLI, plugin and archive name show 0.5.91e.

## New sequence

Hidden → Preparing → Entering → Visible → Exiting → Hidden.
Window selection: Entering/Visible → Selecting → Exiting → Hidden.

- Preparing: one scene is assembled, and each snapshot is handled by a separate request through
  the event queue. At this stage normal windows are still drawn; the filter and blur are not
  enabled until the scene is ready.
- Every preparation run gets a generation. Late steps of a cancelled preparation change nothing.
  Win+G/Esc during preparation cancel it.
- Entering/Exiting: Win+G reverses the current transition from its current value.
  Window enumeration, icons and snapshots are not created again. The plugin's handler does not
  contact the daemon for such a toggle; autorepeat of a held G is ignored.
- Visible: ready snapshots are shown, and normal windows are not duplicated under the blur.
- Selecting: the current selection frame is held; Python checks the generation, restores only
  the selected window, focuses and raises it, and saves the state. The plugin receives a positive
  or negative confirmation.
- After successful confirmation the selected preview is drawn last (on top of the others) and
  returns to the position of the restored window. On error the UI is cleared. Waiting for
  confirmation is limited to three seconds in rendering.
- A confirmed selection is not reversed by a repeated Win+G: that is already the end of the
  selection operation. A normal exit without a selection remains reversible.
- Exiting finishes only before the next frame is built: the filter is disabled together with
  removing the previews. The scene is not cleared in the middle of a render pass.
- A workspace/monitor change, or a window appearing or disappearing, still cancels the overview.
  Automatic scene rebuild when a window closes is not part of this experiment.

## What remains a limitation

This is an experiment in process control, not a rewritten GPU capture.
The 48-million-pixel budget and monitor-sized snapshots are kept. Minimized windows use snapshots
saved before minimizing. If a snapshot is missing/evicted, the monitor is rotated, or the window
was minimized before the plugin loaded, an icon is shown. Compact snapshots of the window area
are not implemented yet. Mass restoring of all minimized applications is not used.

A single `makeSnapshotFB` is still executed synchronously in the compositor. Splitting the queue
allows later steps to be cancelled between snapshots but does not interrupt a single capture call.
The first load of desktop icons in Python is also not sped up.

The render hooks are kept. The cause of the SIGSEGV after overview → another workspace → Steam
has not been established. The new state machine does not prove that this crash is fixed.

## Checks

- 160 Python/Lua tests: PASS. They include confirmation after the window is restored and raised,
  negative confirmation after a close, rejection of a stale selection without changing windows,
  and real Lua syntax of the protocol.
- Standalone C++ test of `OverviewFlow` with UBSan: PASS. 10,000 reversals, position continuity
  at the moment of reversal, preparation cancel, stale generations, selection wait/timeout,
  completion only at a frame boundary.
- The full plugin was not built or run on this Mac. Performance, smoothness, the Hyprland build
  and driver behavior still need a Linux check.

## When it can be tested

Plain `python3 run.py` from the new archive; stop the old run first.
Check short repeated Win+G on enter/exit, Esc during preparation, selecting a normal and a
minimized window, a workspace change, and then the Steam scenario separately.
No testing is required right now. `0.5.9.zip` is unchanged.
