"""Resolve application icons locally; never execute desktop-file commands."""
import configparser
from glob import escape
from functools import lru_cache
import os
from pathlib import Path


def data_roots():
    return [Path(os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local/share')))] + [
        Path(p) for p in os.environ.get('XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(':') if p]


@lru_cache(maxsize=1)
def desktop_icons():
    entries = {}
    for root in data_roots():
        for file in sorted((root/'applications').glob('**/*.desktop')):
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(file, encoding='utf-8')
                entry = parser['Desktop Entry']
                icon = entry.get('Icon', '')
                for key in (file.stem, entry.get('StartupWMClass', '')):
                    if key and icon:
                        entries.setdefault(key.casefold(), icon)
            except (OSError, ValueError, configparser.Error, KeyError):
                continue
    return entries


@lru_cache(maxsize=128)
def resolve(app_class):
    if not app_class:
        return ''
    app_class = app_class.partition(".floatland-csd-")[0]
    name = desktop_icons().get(app_class.casefold(), app_class)
    absolute = Path(name)
    if absolute.is_absolute():
        return str(absolute) if absolute.suffix.lower() in ('.svg', '.png') and absolute.is_file() else ''
    if '/' in name or name in ('.', '..'):
        return ''
    candidates = []
    roots = [Path.home()/'.icons'] + [r/'icons' for r in data_roots()]
    for root in roots:
        for suffix in ('.svg', '.png'):
            filename = name if name.lower().endswith(suffix) else name + suffix
            for file in root.glob('*/**/' + escape(filename)):
                if file.is_file():
                    # Prefer scalable artwork, then the largest raster available.
                    size = next((int(p.split('x')[0]) for p in file.parts if p.split('x')[0].isdigit()), 0)
                    candidates.append((suffix != '.svg', -size, str(file)))
    if candidates:
        return min(candidates)[2]
    for root in data_roots():
        for suffix in ('.svg', '.png'):
            file = root/'pixmaps'/(name if name.endswith(suffix) else name+suffix)
            if file.is_file():
                return str(file)
    return ''
