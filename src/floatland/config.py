from copy import deepcopy
import json
import os
from pathlib import Path
import re

DEFAULTS = {
    "default_mode": "floating", "gap": 10, "width": .65, "height": .72,
    "cascade_step": 28, "exclude_classes": [], "workspace_modes": {}, "titlebar_height": 0,
    "titlebar_style": {}, "appearance": {},
}


APPEARANCE = {'titlebar_color': '#1b2029',
 'titlebar_opacity': 1.0,
 'snap_color': '#4d99ff',
 'snap_opacity': 0.18,
 'tab_color': '#1c1f2b',
 'tab_opacity': 0.93,
 'tab_font_size': 14,
 'tab_icon_size': 80,
 'titlebar_text_color': '#edf2ff',
 'titlebar_font_size': 10,
 'close_color': '#f55c57',
 'minimize_color': '#fabe2e',
 'maximize_color': '#33c459',
 'button_shift': 0.9,
 'button_stretch': 1.5,
 'button_return_duration': 0.28,
 'button_rebound': 0.12,
 'button_texture': True,
 'titlebars_enabled': True,
 'snap_enabled': True,
 'snap_duration': 0.14,
 'overview_enabled': True,
 'overview_blur': True,
 'overview_color': '#090a0f',
 'overview_opacity': 0.22,
 'overview_enter_duration': 0.24,
 'overview_exit_duration': 0.24,
 'switching_enabled': True,
 'tab_enter_duration': 0.09,
 'tab_exit_duration': 0.07,
 'bindings_enabled': True,
 'alt_tab_key': 15,
 'overview_key': 34,
 'buttons_side': 'right',
 'buttons_order': 'maximize,minimize,close',
 'title_alignment': 'left',
 'title_enabled': True,
 'button_highlight': 0.22,
 'button_growth': 0.8,
 'button_hinting': True,
 'button_icons': True,
 'button_hover_only': True,
 'snap_palette': True,
 'snap_edges': True,
 'snap_preview': True}

APPEARANCE_RULES = {'titlebar_color': ['color'],
 'titlebar_opacity': [0, 1],
 'snap_color': ['color'],
 'snap_opacity': [0, 1],
 'tab_color': ['color'],
 'tab_opacity': [0, 1],
 'tab_font_size': [8, 24, 'int'],
 'tab_icon_size': [32, 128, 'int'],
 'titlebar_text_color': ['color'],
 'titlebar_font_size': [6, 24, 'int'],
 'close_color': ['color'],
 'minimize_color': ['color'],
 'maximize_color': ['color'],
 'button_shift': [0, 2],
 'button_stretch': [0, 2],
 'button_return_duration': [0.05, 0.5],
 'button_rebound': [0, 0.15],
 'button_texture': ['bool'],
 'titlebars_enabled': ['bool'],
 'snap_enabled': ['bool'],
 'snap_duration': [0.035, 1],
 'overview_enabled': ['bool'],
 'overview_blur': ['bool'],
 'overview_color': ['color'],
 'overview_opacity': [0, 1],
 'overview_enter_duration': [0.035, 1],
 'overview_exit_duration': [0.035, 1],
 'switching_enabled': ['bool'],
 'tab_enter_duration': [0.035, 0.5],
 'tab_exit_duration': [0.035, 0.5],
 'bindings_enabled': ['bool'],
 'alt_tab_key': [1, 255, 'int'],
 'overview_key': [1, 255, 'int'],
 'buttons_side': ['enum', 'left', 'right'],
 'buttons_order': ['order'],
 'title_alignment': ['enum', 'left', 'center', 'right'],
 'title_enabled': ['bool'],
 'button_highlight': [0, 0.6],
 'button_growth': [0, 2],
 'button_hinting': ['bool'],
 'button_icons': ['bool'],
 'button_hover_only': ['bool'],
 'snap_palette': ['bool'],
 'snap_edges': ['bool'],
 'snap_preview': ['bool']}


def validate_appearance(value):
    if not isinstance(value, dict) or set(value)-set(APPEARANCE):
        raise ValueError("appearance keys: " + ", ".join(APPEARANCE))
    result = dict(APPEARANCE, **value)
    for key, v in result.items():
        rule = APPEARANCE_RULES[key]
        if rule[0] == 'enum':
            valid = isinstance(v, str) and v in rule[1:]
        elif rule[0] == 'order':
            parts = v.split(',') if isinstance(v, str) and v else []
            valid = isinstance(v, str) and len(parts) == len(set(parts)) and all(x in ('close', 'minimize', 'maximize') for x in parts)
        elif rule[0] == 'color':
            valid = isinstance(v, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', v)
        elif rule[0] == 'bool':
            valid = type(v) is bool
        else:
            valid = type(v) in (int, float) and rule[0] <= v <= rule[1]
            if len(rule) == 3:
                valid = valid and type(v) is int
        if not valid:
            raise ValueError('Invalid appearance.' + key)
    if result['alt_tab_key'] in (1,28,42,54,56,100,103,105,106,108,125,126) or result['overview_key'] in (1,28,42,54,56,100,103,105,106,108,125,126):
        raise ValueError('bindings: keycode conflicts with navigation or modifier keys')
    return result


def load(path=None, create=False):
    # Explicit JSON paths remain supported for older command lines.
    if path is not None and Path(path).suffix == '.json':
        path = Path(path)
        if create and not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('x') as file:
                json.dump(dict(DEFAULTS, appearance=APPEARANCE), file, indent=2)
        return validate(json.loads(path.read_text()) if path.exists() else {})
    from .lua_config import load_lua
    return load_lua(path, create=create)


def validate(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise ValueError("Invalid config keys (see examples/config.json)")
    config = dict(deepcopy(DEFAULTS), **value)
    if config["default_mode"] not in ("floating", "tiling"):
        raise ValueError("default_mode must be floating or tiling")
    for key in ("gap", "cascade_step", "titlebar_height"):
        if type(config[key]) is not int or not 0 <= config[key] <= 100:
            raise ValueError(key + " must be an integer from 0 to 100")
    for key in ("width", "height"):
        if type(config[key]) not in (float, int) or not .1 <= config[key] <= 1:
            raise ValueError(key + " must be a fraction from 0.1 to 1")
    modes = config["workspace_modes"]
    if not isinstance(modes, dict) or any(v not in ("floating", "tiling") for v in modes.values()):
        raise ValueError("workspace_modes must map workspace names to floating/tiling")
    if not isinstance(config["exclude_classes"], list) or any(not isinstance(p, str) for p in config["exclude_classes"]):
        raise ValueError("exclude_classes must be a list of regular expressions")
    for pattern in config["exclude_classes"]:
        try:
            re.compile(pattern)
        except re.error as error:
            raise ValueError("Invalid exclude_classes pattern: " + str(error)) from error
    config["titlebar_style"] = validate_style(config["titlebar_style"])
    config["appearance"] = validate_appearance(config["appearance"])
    return config


STYLE_KEYS = ("color", "text_color", "font", "font_size")
COLOR = re.compile(r"rgb\([0-9a-fA-F]{6}\)|rgba\([0-9a-fA-F]{8}\)|0x[0-9a-fA-F]{8}")


def validate_style(style):
    if not isinstance(style, dict) or set(style) - set(STYLE_KEYS):
        raise ValueError("titlebar_style keys: " + ", ".join(STYLE_KEYS))
    for key in ("color", "text_color"):
        if key in style and not (isinstance(style[key], str) and COLOR.fullmatch(style[key])):
            raise ValueError(key + " must look like rgb(rrggbb), rgba(rrggbbaa) or 0xaarrggbb")
    if "font" in style and not (isinstance(style["font"], str) and 0 < len(style["font"]) <= 64
                                and style["font"].isprintable()):
        raise ValueError("font must be a printable name up to 64 characters")
    if "font_size" in style and (type(style["font_size"]) is not int or not 6 <= style["font_size"] <= 40):
        raise ValueError("font_size must be an integer from 6 to 40")
    return style
