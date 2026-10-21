-- Floatland: user configuration. Missing section files use built-in defaults.
-- Each file returns a Lua table. Reload with: python3 run.py reload
return {
    ["mini-titlebar"] = section("mini-titlebar"),
    windows = section("windows"),
    titlebars = section("titlebars"),
    snapping = section("snapping"),
    overview = section("overview"),
    switching = section("switching"),
    bindings = section("bindings"),
    theme = section("theme"),
    experimental = section("experimental"),
}
