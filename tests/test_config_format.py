import json
import tempfile
import unittest
from pathlib import Path
from floatland.lua_config import initialize, load_lua, format_migrated, read_lua


class FormatTests(unittest.TestCase):
    def test_migration_preserves_inline_comments_and_values(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'config.json').write_text(json.dumps({'appearance': {'tab_icon_size': 92, 'tab_opacity': .7}}))
            initialize(root)
            text = (root / 'config/switching.lua').read_text()
            self.assertIn('icon_size = 92,', text)
            self.assertIn('Panel opacity:', text)
            self.assertIn('Maximum preview card width', text)
            self.assertEqual(load_lua(root / 'init.lua')['appearance']['tab_opacity'], .7)

    def test_old_generated_file_reformatted_without_effective_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            initialize(root)
            path = root / 'config/switching.lua'
            original = '-- Migrated from config.json; original JSON preserved.\nreturn {["enabled"]=true,["color"]="#123456",["opacity"]=0.63,["icon_size"]=94}\n'
            path.write_text(original)
            before = load_lua(root / 'init.lua')
            self.assertEqual(format_migrated(root), [str(path)])
            self.assertEqual(before, load_lua(root / 'init.lua'))
            self.assertIn('color = "#123456",', path.read_text())
            self.assertIn('Panel opacity:', path.read_text())
            self.assertEqual(path.with_name(path.name+'.before-format').read_text(), original)
            self.assertEqual(format_migrated(root), [])
            self.assertNotIn('style', read_lua(path))
