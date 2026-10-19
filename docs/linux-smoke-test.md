# Check in a real Hyprland session

This check has not been done yet. Record the doctor output, the shell version and the result.

1. Run `daemon --verbose` from a terminal. Open two applications and a floating dialog.
   The applications should become floating; the dialog should keep its size.
2. Move/resize the applications. Toggle twice: regular windows should go to tiling; after
   returning to floating their coordinates should be restored.
3. Open a window in each mode. Move a window to a workspace with a different mode.
4. Check `window-toggle`, `toggle` and `window-auto`: an explicit exception is kept,
   `window-auto` returns the workspace policy.
5. Check every snap zone and restore, repeated maximize, center.
   Do a snap from tiling and restore: the window should go back to tiling.
6. Check minimize, stop, a second daemon, `restore-minimized`.
   Restore should also work for a named workspace.
7. Check a fullscreen video: the mode change is deferred until fullscreen is left.
8. On a second monitor with a different scale and a panel, check snap and restore;
   repeat with a rotated monitor and negative coordinates.
9. Restart the shell: panels/launcher/notifications should keep working.
   Floatland must not change the theme, focus or binding config.
10. `stop --restore`: minimized windows come back, originally tiled windows are tiled again.
    Then turn off the test autostart if it is no longer needed.

Pay special attention to: size constraints of GTK/Qt/XWayland clients, native scrolling,
window groups, transient dialogs, monitor disconnect, late-applied window rules.
They are not fully modeled by the test compositor.

## Titlebars (if hyprbars is installed)

1. `floatland titlebars status` shows `"loaded": true`.
2. A floating window has a title bar, a tiled one does not; check after `floatland toggle`.
3. The ×, □, – buttons and a double click act on the window whose title bar was clicked,
   including when it was not the active one. If it acts on another window, report it.
4. `snap bottom` and `maximize` leave no gap and do not go under the title bar.
