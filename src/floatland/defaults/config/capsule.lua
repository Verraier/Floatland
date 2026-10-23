-- Capsule position and menu behavior. No external titlebar or client integration.
return {
    enabled = true,
    blur = true, -- Use the compositor blur pass only behind the capsule.
    side = "left", -- Indicator/capsule corner: left or right.
    menu_hover = true,
    menu_delay = 1,
    menu_color = "#1b2029",
    menu_opacity = 0.97,
    focus_keep_cursor = true,
    focus_click_only = true,
    color = "#1b2029",
    opacity = 0.94, -- 0..1, capsule background alpha.
    border_color = "#aeb8ca",
    border_opacity = 0.35, -- 0..1; set to 0 to hide the outline.
    border_width = 1, -- Logical px, 0..4.
    width = 160, -- Preferred width, 96..320 px; grows if buttons need more room.
    height = 32, -- 28..64 px.
    offset = 4, -- Distance from the window's top and side, 0..32 px.
    duration = 0.16, -- Reveal/hide duration in seconds, 0.035..0.5.
    timeout = 4, -- Idle seconds. Dragging and menus pause expiry; finishing restarts it.
}
