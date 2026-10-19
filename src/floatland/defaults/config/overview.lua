-- Overview appearance and transition durations in seconds. No automatic unminimizing of all windows.
return {
    enabled = true, -- Enable this interface, including CLI requests.
    -- color = "#090a0f", -- Optional override of theme.overview.
    blur = true, -- Blur the background; tint still applies when false.
    opacity = 0.22, -- Background tint opacity: 0 = transparent, 1 = opaque.
    enter_duration = 0.24, -- Enter transition in seconds, 0.035..1.
    exit_duration = 0.24 -- Exit transition in seconds, 0.035..1.
}
