# Changelog

## 0.7.0-lite3

- Give the collapsed indicator equal top and side insets, matching capsule.offset for either side and all capsule heights.

## 0.7.0-lite2

- Anchor the collapsed indicator to the configured capsule side instead of always its right edge.
- Align the native initial side with the Lua left-side default.
- Suspend capsule timeout during drag/button interaction and owned menus; restart a full timeout after finishing.

## 0.7.0-lite1 — first lite test release

- Make the capsule and passive indicator the primary window controls, with an explicit drag handle.
- Remove toolkit integrations and full-width external titlebars.
- Replace fullscreen overview presentation with a compact sidebar; remove normal-window suppression hooks.
- Keep icons-only Alt+Tab, floating policy, snapping, geometry memory and per-window rules.
- Isolate settings under floatland-lite with capsule.lua and buttons.lua.
- Add a versioned window listing and PID-checked addressed commands for future shell integration.
- Retain attribution and legacy history. Full Linux build and graphics validation are pending.
