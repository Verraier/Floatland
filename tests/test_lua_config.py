import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from floatland.config import load, APPEARANCE, DEFAULTS
from floatland.lua_config import initialize, read_lua, normalize
from floatland.controller import Controller
from floatland.state import State
from floatland.ipc import IPCError
from test_floatland import FakeHyprland, window


class LuaConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.entry = self.root/'init.lua'

    def write(self, section, text):
        (self.root/'config'/(section+'.lua')).write_text(text)

    def test_button_diameter_roundtrip(self):
        load(self.entry, create=True)
        self.write('titlebars', 'return { button_size=18, button_spacing=4 }')
        settings = load(self.entry)['appearance']
        self.assertEqual(settings['button_size'],18)
        self.assertEqual(settings['button_spacing'],4)

    def test_init_default_sections_and_theme_precedence(self):
        settings = load(self.entry, create=True)
        self.assertEqual(settings['appearance'], APPEARANCE)
        self.write('theme', 'return { titlebar="#123456", overview="#abcdef" }')
        self.write('titlebars', 'return { opacity=.8 }')
        self.assertEqual(load(self.entry)['appearance']['titlebar_color'], '#123456')
        self.write('titlebars', 'return { color="#654321" }')
        self.assertEqual(load(self.entry)['appearance']['titlebar_color'], '#654321')

    def test_button_layout_is_explicit_and_validated(self):
        load(self.entry,create=True)
        self.write('titlebars', 'return {buttons_side="left", buttons_order={"close","minimize"}, title_alignment="center", highlight=.3}')
        settings=load(self.entry)['appearance']
        self.assertEqual(settings['buttons_order'],'close,minimize')
        self.assertEqual(settings['buttons_side'],'left')
        for order in ('{"close","close"}', '{"unknown"}', '"close,minimize"'):
            self.write('titlebars','return {buttons_order='+order+'}')
            with self.assertRaisesRegex(ValueError,'buttons_order'): load(self.entry)
        self.write('titlebars','return {buttons_order={}}')
        self.assertEqual(load(self.entry)['appearance']['buttons_order'],'')

    def test_new_json_migration_leaves_theme_colors_editable(self):
        (self.root/'config.json').write_text('{"appearance":{"snap_color":"#123456"}}')
        load(self.entry,create=True)
        self.write('theme','return {snap="#abcdef"}')
        self.assertEqual(load(self.entry)['appearance']['snap_color'],'#abcdef')

    def test_missing_sections_use_defaults_and_existing_files_are_preserved(self):
        load(self.entry, create=True)
        self.write('overview', 'return { blur=false, enter_duration=.4 }')
        original = (self.root/'config/overview.lua').read_bytes()
        (self.root/'config/switching.lua').unlink()
        value = load(self.entry, create=True)
        self.assertEqual((self.root/'config/overview.lua').read_bytes(), original)
        self.assertFalse(value['appearance']['overview_blur'])
        self.assertEqual(value['appearance']['tab_icon_size'], 80)

    def test_lua_expressions_and_unicode_strings_are_real_lua(self):
        load(self.entry, create=True)
        self.write('windows', 'local size=0.3; return {width=size*2, exclude_classes={"Терминал", "a\\\\b", "line\\nnext"}, workspace_modes={["2"]="tiling"}}')
        value = load(self.entry)
        self.assertEqual(value['width'], .6)
        self.assertEqual(value['exclude_classes'], ['Терминал', 'a\\b', 'line\nnext'])
        self.assertEqual(value['workspace_modes'], {'2':'tiling'})

    def test_migration_preserves_json_and_values(self):
        legacy={'gap':17,'exclude_classes':['kitty'], 'appearance':{'titlebar_color':'#445566','tab_font_size':18}}
        original=json.dumps(legacy)
        (self.root/'config.json').write_text(original)
        value=load(self.entry,create=True)
        self.assertEqual(value['gap'],17)
        self.assertEqual(value['appearance']['titlebar_color'],'#445566')
        self.assertEqual(value['appearance']['tab_font_size'],18)
        self.assertEqual((self.root/'config.json').read_text(),original)
        before={p:p.read_bytes() for p in self.root.rglob('*.lua')}
        load(self.entry,create=True)
        self.assertEqual({p:p.read_bytes() for p in before},before)

    def test_bad_json_migration_writes_no_lua(self):
        (self.root/'config.json').write_text('{"gap":-2}')
        with self.assertRaises(ValueError): load(self.entry,create=True)
        self.assertEqual(list(self.root.rglob('*.lua')),[])

    def test_migration_does_not_merge_over_existing_lua(self):
        (self.root/'config').mkdir()
        self.write('theme','return {titlebar="#111111"}')
        (self.root/'config.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'migration refused'): initialize(self.root)
        self.assertFalse(self.entry.exists())

    def test_invalid_values_name_the_source_file(self):
        load(self.entry,create=True)
        for section,text,error in [('overview','return {blur="false"}','overview.lua'),
                                    ('theme','return {snap="red"}','theme.lua'),
                                    ('bindings','return {alt_tab_key=56}','bindings.lua'),
                                    ('titlebars','return {typo=1}','titlebars.lua')]:
            with self.subTest(section=section):
                old=(self.root/'config'/(section+'.lua')).read_text()
                self.write(section,text)
                with self.assertRaisesRegex(ValueError,error): load(self.entry)
                self.write(section,old)

    def test_syntax_error_and_cycle_are_rejected(self):
        load(self.entry,create=True)
        self.write('overview','return { broken = ')
        with self.assertRaisesRegex(ValueError,'overview.lua'): load(self.entry)
        self.write('overview','local t={};t.self=t;return t')
        with self.assertRaisesRegex(ValueError,'cyclic'): load(self.entry)

    def test_long_running_config_times_out(self):
        self.entry.write_text('while true do end')
        with patch('floatland.lua_config.subprocess.run',side_effect=subprocess.TimeoutExpired('lua',5)) as run:
            with self.assertRaisesRegex(ValueError,'5 seconds'): read_lua(self.entry)
        self.assertEqual(run.call_args.kwargs['timeout'],5)

    def test_old_config_is_read_without_writing(self):
        (self.root/'config.json').write_text('{"gap":23}')
        self.assertEqual(load(self.entry)['gap'],23)
        self.assertFalse(self.entry.exists())

    def test_subprocess_configuration_does_not_need_hyprland_or_project_cwd(self):
        runner=Path(__file__).resolve().parents[1]/'run.py'
        env=dict(os.environ)
        env['PYTHONPATH']=os.pathsep.join(str(Path(x).resolve()) for x in env.get('PYTHONPATH','').split(os.pathsep) if x)
        env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
        command=[sys.executable,str(runner),'config','init','--dir',str(self.root)]
        result=subprocess.run(command,cwd='/tmp',env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(self.entry.exists())


class ReloadTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.ipc=FakeHyprland([window()]);self.ipc.configure_appearance=Mock()
        self.c=Controller(self.ipc,State(Path(self.temp.name)/'state'),dict(DEFAULTS))
        self.c.reconcile()

    def test_bad_config_does_not_apply_anything(self):
        previous=self.c.config
        with self.assertRaises(ValueError): self.c.replace_config({'gap':-1})
        self.assertIs(self.c.config,previous)
        self.ipc.configure_appearance.assert_not_called()

    def test_native_rejection_keeps_previous_python_settings_and_records(self):
        previous=self.c.config
        self.ipc.configure_appearance.side_effect=IPCError('rejected')
        before=self.c.windows['0x1']['applied']
        with self.assertRaises(IPCError): self.c.replace_config({'gap':19})
        self.assertIs(self.c.config,previous)
        self.assertEqual(self.c.windows['0x1']['applied'],before)

    def test_valid_reload_updates_policy_without_losing_restore_geometry(self):
        self.c.command('snap','left')
        saved=self.c.windows['0x1']['before_snap'].copy()
        self.c.replace_config({'gap':19,'appearance':{'titlebars_enabled':False}})
        self.assertEqual(self.c.config['titlebar_height'],0)
        self.assertEqual(self.c.config['gap'],19)
        self.assertEqual(self.c.windows['0x1']['before_snap'],saved)
        self.assertNotIn('applied',self.c.windows['0x1'])
