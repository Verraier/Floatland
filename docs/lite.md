# Lite architecture and settings

The Python daemon owns policy, remembered geometry, rules and commands. The native plugin owns the capsule, input routing, snap preview and task UI. A future shell is optional; closing it must not disable Floatland.

The capsule reserves no client height and does not replace client decorations or window rounding. Its translucent background requests compositor blur only within its own area. A collapsed indicator has no close/minimize actions. Reveal/hide currently crossfades; it is not a finished geometric shrink animation. Holding over the controls hides them after the configured timeout so content remains reachable. Leaving normally hides them. Dragging or using the window/settings menu suspends expiry; finishing grants a fresh full timeout even outside the capsule. Right-click opens the menu; hovering the green button opens it after menu_delay.

Super+G shows current-workspace thumbnails in a right-hand sidebar. Wheel and keyboard navigation keep the selected card visible; pointer hover highlights a card. Thumbnails are snapshots prepared in separate IPC turns with generation cancellation, not live video. Minimized windows use a cached snapshot when available and an icon fallback otherwise. Ordinary windows remain rendered behind the panel. Only the panel background is blurred.

Alt+Tab uses adaptive icon tiles and pointer selection. Old preview and legacy styles are not public options in lite.

## Configuration

`python3 run.py config path` prints the active init.lua. `config reference` prints commented templates. `config show` prints effective values. `reload` validates and applies settings; invalid input retains the last accepted configuration.

The init.lua loads eight files under config/:

| File | Purpose |
| --- | --- |
| windows.lua | Floating policy and geometry behavior |
| capsule.lua | Placement, size, blur, opacity, focus policy, menu delay and hide timing |
| buttons.lua | SVG icons, size, spacing, colors, glow, shadows and deformation |
| snapping.lua | Snap zones, palette and preview appearance |
| overview.lua | Sidebar tint, blur and transition duration |
| switching.lua | Icon switcher appearance and transitions |
| bindings.lua | Keyboard shortcuts |
| theme.lua | Shared colors |

Explicit component colors override theme colors. Removing a component override restores the shared theme value. SVG paths resolve relative to the config directory; shipped icons are copied on initialization. Configuration comments are English. Generated per-window rules are stored separately in config/set-rules.json and currently expose Always on top and All workspaces.

The lite config directory is separate from legacy. Per-session state/socket ownership remains shared to prevent two managers controlling the same windows concurrently. Persistent size memory remains available. Do not run legacy and lite together.

## Scope

No toolkit injection, full titlebar, global application menu, media playback integration or shell widgets are included. Native SDK coupling remains for decorations, dragging and snapshot rendering. Some internal names and validation fields retain legacy names; they are not additional supported lite features.
