-- User settings: edit ~/.config/floatland/config/titlebars.lua, not this template.
-- Changes reload automatically after saving. Invalid settings keep the last working values.
return {
    enabled = true,
    -- Optional overrides of theme.lua; uncomment to use a component-specific color.
    -- color = "#1b2029",
    -- text_color = "#edf2ff",
    opacity = 1.0, -- 0 = transparent, 1 = opaque.
    font_size = 10, -- Integer 6..24. Title font size in points.
    title_enabled = true,
    title_alignment = "left", -- "left", "center", "right". Buttons always reserve the outer edge.
    buttons_side = "right", -- "left" or "right".
    -- Visual order from LEFT to RIGHT. Omit an action to hide its button; {} hides all.
    buttons_order = { "maximize", "minimize", "close" },
    close_color = "#f55c57",
    minimize_color = "#fabe2e",
    maximize_color = "#33c459",
    texture = true, -- Draw the gradient highlight and rim; false gives a flat fill.
    icons = true, -- Draw action symbols inside the buttons.
    hover_only = true, -- Show all symbols when any button is hovered or held.
    hinting = true, -- Fit idle symbol strokes to physical pixels for the monitor scale.
    highlight = 0.22, -- 0..0.6: blend toward white while held over the original button.
    growth = 0.8, -- 0..2: additional radius in logical px while held; 0 disables growth.
    button_shift = 0.9, -- 0..2: maximum center movement in logical px; 0 disables movement.
    button_stretch = 1.5, -- 0..2: leading-edge extension in logical px; 0 disables stretching.
    return_duration = 0.28, -- Seconds, 0.05..0.5, to settle after release.
    rebound = 0.12, -- 0..0.15: fraction of held deformation for ONE opposite bounce; 0 disables it.
}
