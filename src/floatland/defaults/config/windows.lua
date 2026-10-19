-- Window policy. Class exclusions are Python regular expressions. Workspace names must be strings: ["1"].
return {
    -- Remember normal floating sizes by application class across closing and restarting.
    remember_sizes = true,
    default_mode = "floating",
    gap = 10,
    width = 0.65,
    height = 0.72,
    cascade_step = 28,
    exclude_classes = {},
    workspace_modes = {}
}
