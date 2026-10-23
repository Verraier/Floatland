# Floatland Lite native plugin

Built automatically by `python3 run.py` on Linux with exact Hyprland 0.56.2 headers. The historical module name floatland-bars is retained.

The plugin provides zero-reserved-height capsules, native drag handling and snap feedback, icons-only task switching, and snapshot thumbnails in a sidebar. It does not install renderWindow/renderFadeouts suppression hooks or inject toolkit controls. Snapshot capture and blur still use Hyprland rendering APIs and require Linux graphics validation.

Run `python3 tools/check.py` from the project root for portable logic tests. See ../docs/linux-smoke-test.md for full runtime checks. Preserve LICENSE.hyprbars and the project NOTICE.md when redistributing.
