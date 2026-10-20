# 0.6.8e: titlebar context menu and mini-mode

Status: agreed design, not implemented. Stable baseline: 0.6.7.

## Context menu

Right-clicking a normal titlebar opens two sections:

- Actions: Close, Minimize, Fullscreen. They remain available when titlebar buttons are disabled.
- Independent checkboxes: Pin above and Mini-mode.

Pin above controls stacking without forcing a compact window size. Mini-mode removes Floatland's titlebar and its reserved height, retaining a compact hover-revealed capsule with the three window controls. It does not remove application-owned headers.

## Mini-mode interaction contract

- Reveal the capsule by entering its small activation area at the top of the window.
- Use a brief transition without jelly motion or spring effects.
- Hide after four seconds from appearance, even if the pointer remains over it.
- Defer hiding while a button is held or a drag is active, until release.
- After timeout, require pointer exit and re-entry before revealing again.
- Hidden controls must pass left clicks through to the application.
- Right-click anywhere on the capsule or its hidden activation area immediately exits mini-mode and restores the ordinary titlebar. No context-menu navigation is required to escape.
- Free capsule space can move the window. Button actions always target the owning window, not the focused one.

## Acceptance checks

Verify hover, timeout, drag/release, disabled buttons, fractional scale, multiple monitors, workspace changes, window closure and Floatland restart. Check that no hidden left-click region blocks application content and that the emergency right-click exit works in every state. Preserve original geometry and existing Steam/XWayland safeguards.
