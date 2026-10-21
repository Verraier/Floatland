-- Window policy. Class exclusions are Python regular expressions. Workspace names must be strings: ["1"].
return {
    -- Remember normal floating sizes by application class across closing and restarting.
    remember_sizes = true,
    -- XWayland apps may share a class with menus and startup helper windows.
    remember_xwayland_sizes = false,
    default_mode = "floating",
    gap = 10,
    width = 0.65,
    height = 0.72,
    cascade_step = 28,
    exclude_classes = {},
    workspace_modes = {}
}
