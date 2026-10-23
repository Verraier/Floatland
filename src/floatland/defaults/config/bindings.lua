-- Linux evdev keycodes, not XKB codes. 15=Tab, 34=G. Modifiers stay ALT and SUPER. Alt+Shift+Tab (reverse) is not working yet.
return {
    menu_key = 50, -- Linux evdev key code for Super+M: open window actions without titlebar buttons.
    enabled = true,
    alt_tab_key = 15,
    overview_key = 34
}
