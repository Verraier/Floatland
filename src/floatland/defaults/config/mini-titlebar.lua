-- User settings: ~/.config/floatland/config/mini-titlebar.lua
-- Live reload; no compilation required. Applies only to the mini capsule.
-- Button colors follow titlebars.lua. The button group is centered.
return {
    color = "#1b2029",
    opacity = 0.94, -- 0..1, capsule background alpha.
    border_color = "#aeb8ca",
    border_opacity = 0.35, -- 0..1; set to 0 to hide the outline.
    border_width = 1, -- Logical px, 0..4.
    width = 128, -- Preferred width, 96..320 px; grows if buttons need more room.
    height = 32, -- 28..64 px.
    button_size = 14, -- Circle diameter, 8..24 px.
    button_spacing = 16, -- Gap between circles, 0..40 px.
    offset = 4, -- Distance from the window's top and side, 0..32 px.
    duration = 0.16, -- Slide in/out duration in seconds, 0.035..0.5.
    timeout = 4, -- Seconds while hovered. Leaving hides immediately unless held.
}
