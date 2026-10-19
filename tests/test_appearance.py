import json
from pathlib import Path
import tempfile
import unittest
from floatland.config import load, validate_appearance

class AppearanceTests(unittest.TestCase):
    def test_validation_boundaries(self):
        self.assertEqual(validate_appearance({'tab_icon_size':128,'tab_opacity':0})['tab_icon_size'],128)
        for key, value in [('snap_color','red'),('titlebar_opacity',float('nan')),
                           ('tab_opacity',1.1),('tab_font_size',True),('tab_font_size',25),
                           ('tab_icon_size',31),('unknown',1)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_appearance({key:value})

    def test_create_once_and_preserve_user_settings(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'floatland/config.json'
            load(p,create=True)
            self.assertIn('appearance',json.loads(p.read_text()))
            p.write_text('{"gap":15,"appearance":{"tab_color":"#112233"}}')
            original=p.read_bytes()
            config=load(p,create=True)
            self.assertEqual(p.read_bytes(),original)
            self.assertEqual(config['appearance']['tab_color'],'#112233')
            self.assertEqual(config['gap'],15)

    def test_read_only_load_does_not_create_config(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'config.json'
            load(p)
            self.assertFalse(p.exists())
