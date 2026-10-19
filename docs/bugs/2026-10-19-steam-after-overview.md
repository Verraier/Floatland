# Hyprland crash when opening Steam after the overlay

Registered: 2026-10-19. Status: open, cause not established.
Priority: high — the whole compositor session terminates.

## User report

Sequence as clarified by the user:

1. Open the Floatland overview and interact with it.
2. Close the overview.
3. Switch to another workspace.
4. Open Steam — Hyprland crashes after that.

At the moment Steam is opened, the overview is already closed. The switch to another workspace
happens between closing the overview and opening Steam. The specific actions inside the overview,
reproducibility, and whether Steam was started fresh or an already running application was
opened are not known yet.

## Attached data

The [original crash report](2026-10-19-steam-crash-report.txt) contains two reports:

- floatland-bars 0.5.4: SIGABRT (6), `assertImpl` → `CHyprGLRenderer::endRender`.
- floatland-bars 0.5.8: SIGSEGV (11), last frame #4 — address `0x7fd30c1adce6` with no function
  name, module or source line.

The second report is relevant to the current case. It must not be identified with the earlier
assert in 0.5.4, nor treated as a confirmed repeat of the same error.
Both reports: Hyprland v0.56.2, commit `efb50993780079460b0cbed1363e2166a2de1d9f`, CachyOS,
kernel 7.2.11-1-cachyos-polyacrylate, AMD Navi 48 and Radeon 610M.

The end of the new log contains mouse events and cursor buffer import events.
There is no OpenGL error message or assert text. The log tail alone does not establish the
cause of the crash or the guilty component.

## Further diagnostics

A symbolized stack of a new crash (a core dump with the matching plugin binary) or a reproduction
on Linux is needed. Check the lifetime of windows/previews and the render hooks after closing the
overview, changing the workspace and then opening Steam. Check whether references or state from
the previous monitor/workspace remain. These are directions for investigation, not established
causes.

No fix has been made for this case yet; 0.5.8 is not considered verified for this scenario.
The original report is kept unchanged.

## Audit 0.5.9

Decoration lifetime protection and overview context cleanup were added.
A link between these changes and this SIGSEGV has not been established; the bug remains open.
[Audit report](../stability-audit-0.5.9.md).
