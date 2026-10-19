"""Execute user Lua in an isolated process, then validate all returned data."""
import importlib.util
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys

from .ipc import lua_string

SECTIONS = {
    'windows': None,
    'titlebars': {'enabled':'titlebars_enabled','color':'titlebar_color','opacity':'titlebar_opacity',
                 'text_color':'titlebar_text_color','font_size':'titlebar_font_size',
                 'close_color':'close_color','minimize_color':'minimize_color','maximize_color':'maximize_color',
                 'button_shift':'button_shift','button_stretch':'button_stretch',
                 'return_duration':'button_return_duration','rebound':'button_rebound','texture':'button_texture',
                 'buttons_side':'buttons_side','buttons_order':'buttons_order','title_alignment':'title_alignment',
                 'title_enabled':'title_enabled','highlight':'button_highlight','growth':'button_growth',
                 'hinting':'button_hinting','icons':'button_icons','hover_only':'button_hover_only'},
    'snapping': {'enabled':'snap_enabled','color':'snap_color','opacity':'snap_opacity','duration':'snap_duration','palette':'snap_palette','edges':'snap_edges','preview':'snap_preview'},
    'overview': {'enabled':'overview_enabled','blur':'overview_blur','color':'overview_color','opacity':'overview_opacity',
                 'enter_duration':'overview_enter_duration','exit_duration':'overview_exit_duration'},
    'switching': {'enabled':'switching_enabled','color':'tab_color','opacity':'tab_opacity',
                  'font_size':'tab_font_size','icon_size':'tab_icon_size',
                  'enter_duration':'tab_enter_duration','exit_duration':'tab_exit_duration'},
    'bindings': {'enabled':'bindings_enabled','alt_tab_key':'alt_tab_key','overview_key':'overview_key'},
    'theme': {'titlebar':'titlebar_color','text':'titlebar_text_color','snap':'snap_color','switching':'tab_color','overview':'overview_color'},
    'experimental': {},
}
MARKER = '\x1eFLOATLAND_CONFIG\n'
SERIALIZER = r'''
local function encode(v, seen)
  local t=type(v)
  if t=='boolean' then return v and 'true' or 'false' end
  if t=='number' then
    assert(v==v and v~=math.huge and v~=-math.huge, 'non-finite number in config')
    return tostring(v)
  end
  if t=='string' then
    return string.char(34) .. v:gsub('.', function(c)
      local n=string.byte(c)
      if n==34 or n==92 then return string.char(92)..c end
      if n<32 then return string.char(92)..string.format('u%04x',n) end
      return c
    end) .. string.char(34)
  end
  assert(t=='table', 'configuration contains unsupported value: '..t)
  assert(not seen[v], 'cyclic configuration table')
  seen[v]=true
  local count,max,array=0,0,true
  for k in pairs(v) do
    count=count+1
    if type(k)~='number' or k<1 or k%1~=0 then array=false else max=math.max(max,k) end
  end
  local items={}
  if array and count>0 and count==max then
    for i=1,max do items[#items+1]=encode(v[i],seen) end
    seen[v]=nil; return '['..table.concat(items,',')..']'
  end
  for k,x in pairs(v) do
    assert(type(k)=='string', 'config map keys must be strings (workspace names: ["1"])')
    items[#items+1]=encode(k,seen)..':'..encode(x,seen)
  end
  seen[v]=nil; return '{'..table.concat(items,',')..'}'
end
'''


def config_home():
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config'))) / 'floatland'


def runtime():
    for name in ('lua', 'lua5.4', 'lua5.3', 'luajit'):
        if shutil.which(name):
            return [shutil.which(name), '-']
    if importlib.util.find_spec('lupa') is not None:
        return [sys.executable, str(Path(__file__).with_name('lua_worker.py'))]
    raise ValueError('Lua interpreter not found. Install lua (or Python lupa) before starting Floatland.')


def read_lua(path):
    path = Path(path).resolve()
    root = path.parent
    program = ('package.path=' + lua_string(str(root/'?.lua')+';'+str(root/'?/init.lua')+';') + '..package.path\n' +
               'function section(name)\n' +
               'local path=' + lua_string(str(root/'config')+'/') + '..name..".lua"\n' +
               'local f,err,code=io.open(path,"r"); if not f then if code==2 then return {} else error(err) end end; f:close()\n' +
               'return assert(loadfile(path))() end\n' + SERIALIZER + '\n' +
               'local value=assert(loadfile(' + lua_string(str(path)) + '))()\n' +
               'assert(type(value)=="table", "init.lua must return a table")\n' +
               'io.write(' + lua_string(MARKER) + ',encode(value,{}))\n')
    try:
        result = subprocess.run(runtime(), input=program, text=True, capture_output=True, timeout=5)
    except subprocess.TimeoutExpired as error:
        raise ValueError(str(path)+': Lua configuration exceeded 5 seconds; previous settings retained') from error
    if result.returncode:
        raise ValueError(str(path)+': '+result.stderr.strip())
    _, separator, output = result.stdout.rpartition(MARKER)
    if not separator:
        raise ValueError(str(path)+': Lua did not return configuration data')
    try:
        return json.loads(output)
    except ValueError as error:
        raise ValueError(str(path)+': invalid Lua configuration output') from error


def normalize(value):
    from .config import DEFAULTS, APPEARANCE, validate
    if not isinstance(value, dict) or set(value)-set(SECTIONS):
        raise ValueError('init.lua: expected sections: '+', '.join(SECTIONS))
    appearance = dict(APPEARANCE)
    origins = {}
    windows = {}
    for name in ['theme'] + [n for n in SECTIONS if n != 'theme']:
        section = value.get(name, {})
        if not isinstance(section, dict):
            raise ValueError('config/'+name+'.lua: must return a table of named settings')
        if name == 'windows':
            if set(section)-(set(DEFAULTS)-{'appearance'}):
                raise ValueError('config/windows.lua: unknown setting')
            windows = dict(section)
            if windows.get('exclude_classes') == {}:
                windows['exclude_classes'] = []
            continue
        mapping = SECTIONS[name]
        unknown = set(section)-set(mapping)
        if unknown:
            raise ValueError('config/'+name+'.lua: unknown setting '+', '.join(sorted(unknown)))
        for key, v in section.items():
            if mapping[key] == 'buttons_order':
                if v == {}: v = []
                if not isinstance(v, list) or any(not isinstance(x, str) for x in v):
                    raise ValueError('config/titlebars.lua: buttons_order must be a list of action names')
                v = ','.join(v)
            previous = origins.get(mapping[key])
            if previous and previous[0] == 'theme' and appearance[mapping[key]] != v:
                logging.getLogger('floatland').warning(
                    'config/%s.lua:%s overrides config/theme.lua:%s; remove the component color to use the theme',
                    name, key, previous[1])
            appearance[mapping[key]] = v
            origins[mapping[key]] = (name, key)
    try:
        return validate(dict(windows, appearance=appearance))
    except ValueError as error:
        message = str(error)
        for flat, (name, key) in origins.items():
            if 'appearance.'+flat in message:
                raise ValueError('config/'+name+'.lua: invalid '+key) from error
        if message.startswith('bindings:'):
            raise ValueError('config/bindings.lua: '+message) from error
        raise ValueError('config/windows.lua: '+message) from error


def lua_value(value):
    if isinstance(value, str): return lua_string(value)
    if value is True: return 'true'
    if value is False: return 'false'
    if isinstance(value, (int, float)): return str(value)
    if isinstance(value, list): return '{'+', '.join(lua_value(v) for v in value)+'}'
    if isinstance(value, dict): return '{'+',\n'.join('['+lua_string(k)+'] = '+lua_value(v) for k,v in value.items())+'}'
    raise ValueError('Unsupported migration value')


def initialize(root):
    """Publish init.lua last; never replace user files or remove legacy JSON."""
    from .config import validate
    root = Path(root)
    if (root/'init.lua').exists(): return
    runtime()  # Check dependencies before creating files.
    templates = Path(__file__).with_name('defaults')
    legacy = root/'config.json'
    migrated = None
    if legacy.exists():
        migrated = validate(json.loads(legacy.read_text()))
        if any((root/'config').glob('*.lua')):
            raise ValueError('Existing config/*.lua: automatic JSON migration refused; keep files and create init.lua explicitly')
    (root/'config').mkdir(parents=True, exist_ok=True)
    for name, mapping in SECTIONS.items():
        target = root/'config'/(name+'.lua')
        text = (templates/'config'/(name+'.lua')).read_text()
        if migrated is not None:
            data = ({k:v for k,v in migrated.items() if k!='appearance'} if name=='windows'
                    else {key:migrated['appearance'][flat] for key,flat in (mapping or {}).items()} if name!='theme' else {key:migrated['appearance'][flat] for key,flat in mapping.items()})
            if name not in ('windows', 'theme'):
                shared = set(SECTIONS['theme'].values())
                data = {key:value for key,value in data.items() if mapping[key] not in shared}
            if name == 'titlebars' and 'buttons_order' in data:
                data['buttons_order'] = data['buttons_order'].split(',') if data['buttons_order'] else []
            comments = '\n'.join(line for line in text.splitlines() if line.lstrip().startswith('--'))
            text = comments+'\n-- Migrated from config.json; original JSON preserved.\nreturn '+lua_value(data)+'\n'
        try:
            with target.open('x') as file: file.write(text)
        except FileExistsError:
            pass
    with (root/'init.lua').open('x') as file:
        file.write((templates/'init.lua').read_text())


def load_lua(path=None, create=False):
    path = Path(path) if path is not None else config_home()/'init.lua'
    if path.is_dir(): path = path/'init.lua'
    if create and not path.exists():
        if path.name != 'init.lua': raise ValueError('New configuration entry must be named init.lua')
        initialize(path.parent)
    if not path.exists():
        # Read-only legacy fallback; migration happens only during init/start.
        legacy = path.parent/'config.json'
        from .config import validate
        return validate(json.loads(legacy.read_text()) if legacy.exists() else {})
    return normalize(read_lua(path))
