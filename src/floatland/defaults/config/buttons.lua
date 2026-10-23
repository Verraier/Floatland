-- Capsule button appearance and motion; capsule geometry stays in capsule.lua.
return {
    icons = true,
    hover_only = true,
    hinting = true,
    highlight = 0.22,
    growth = 0.8,
    button_shift = 0.9,
    button_stretch = 1.5,
    return_duration = 0.28,
    rebound = 0.12,
    maximize_icon_scale = 0.9, -- Optical size multiplier, 0.5..1.5.
    minimize_icon_scale = 1.0, -- Optical size multiplier, 0.5..1.5.
    close_icon_scale = 1.22, -- Optical size multiplier, 0.5..1.5.
    button_size = 14,
    button_spacing = 16,
    texture = true,
    close_icon = "icons/mini/close.svg", -- SVG file; empty string uses built-in lines.
    minimize_icon = "icons/mini/minimize.svg", -- SVG file; empty string uses built-in lines.
    maximize_icon = "icons/mini/maximize.svg", -- SVG file; empty string uses built-in lines.
    icon_size = 0.55, -- Fraction of button diameter.
    icon_tint = true, -- Tint SVG using the button color; false preserves SVG colors.
    button_shadow = 0.18, -- Opacity 0..1; 0 disables the effect.
    button_glow = 0, -- Opacity 0..1; 0 disables the effect.
    close_color = "#f55c57",
    minimize_color = "#fabe2e",
    maximize_color = "#33c459",
}
