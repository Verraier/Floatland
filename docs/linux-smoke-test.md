# Linux smoke checks for 0.7.0-lite3

Stop legacy Floatland, then run `python3 run.py` in the lite folder. The complete native build and SDK checks must succeed before runtime testing. Save logs/session.log if startup fails.

- Open several Wayland apps and Steam/XWayland. Confirm no extra titlebar height, unchanged client rounding and a capsule on eligible floating windows.
- Hover the indicator; test close/minimize/fullscreen on an unfocused window. Confirm collapsed indicators cannot accidentally close windows.
- Drag using the handle; test edge snaps, palette, restore size and positions, and movement between monitors at different scales.
- Open the capsule menu using right-click and green-button hover. Check Always on top and All workspaces; ensure input reaches client content after the capsule hides.
- Open more windows than fit in the sidebar. Use Super+G, wheel, pointer and keyboard selection, including minimized and closed windows. Repeat rapidly and switch workspaces during transitions.
- Check normal windows stay visible behind the sidebar; closing overview must not flash wallpaper or steal focus after cancellation.
- Use Alt+Tab with few and many windows. Verify icons, mouse selection and release-to-commit.
- Edit installed capsule/buttons settings and reload. Try invalid values and confirm the previous valid configuration remains active.
- Stop/restart Floatland without logging out. Check dragging and snap on existing windows, restored minimized windows, state memory and no duplicate input hooks.

Standalone logic checks on macOS cannot validate any of the rendering or compositor lifetime behavior above.
