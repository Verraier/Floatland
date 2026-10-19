-- Edge snapping and the top palette. Commands such as "snap left" remain available.
return {
    enabled = true, -- Enable snapping while dragging a titlebar.
    edges = true, -- Detect screen edges and corners.
    palette = true, -- Show and activate the layout choices near the top of the screen.
    preview = true, -- Draw the snap-area preview; disabling it does not disable snapping.
    -- color = "#4d99ff", -- Optional #RRGGBB override of theme.snap.
    opacity = 0.18, -- Snap-area opacity: 0 = transparent, 1 = opaque.
    duration = 0.14, -- Seconds, 0.035..1, for the preview to fade and change shape.
}
