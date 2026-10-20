-- Alt+Tab appearance. Font and icon sizes are numeric, in logical units.
return {
    style = "icons", -- "icons", "preview", or "legacy" (fixed-size old layout).
    mouse = true, -- Hover selects; release Alt or click to activate.
    preview_width = 240, -- Maximum preview card width in logical px, 160..360.
    enabled = true, -- Enable this interface, including CLI requests.
    -- color = "#1c1f2b", -- Optional override of theme.switching.
    opacity = 0.93, -- Panel opacity: 0 = transparent, 1 = opaque.
    font_size = 14,
    icon_size = 80,
    enter_duration = 0.09, -- Fade-in time in seconds, 0.035..0.5.
    exit_duration = 0.07 -- Fade-out time in seconds, 0.035..0.5.
}
