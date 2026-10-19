-- Optional manual integration. Replace this absolute checkout path.
-- Do not also start run.py manually when autostart is enabled.
local executable = "python3 '/absolute/path/to/floatland/run.py'"
hl.on("hyprland.start", function()
    hl.exec_cmd(executable .. " start")
end)
local function bind(keys, command)
    hl.bind(keys, hl.dsp.exec_cmd(executable .. " " .. command),
            { description = "Floatland: " .. command })
end
-- Alt+Tab and Super+G are already handled by the native plugin.
bind("SUPER + CTRL + SHIFT + M", "toggle")
bind("SUPER + ALT + Space", "window-toggle")
bind("SUPER + ALT + Left", "snap left")
bind("SUPER + ALT + Right", "snap right")
bind("SUPER + ALT + Up", "maximize")
bind("SUPER + ALT + Down", "restore")
bind("SUPER + ALT + M", "minimize")
bind("SUPER + ALT + SHIFT + M", "restore-minimized")
