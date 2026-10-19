import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from floatland import icons

class IconTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        patcher=patch.object(icons, 'data_roots', return_value=[self.root]); patcher.start(); self.addCleanup(patcher.stop)
        icons.resolve.cache_clear(); icons.desktop_icons.cache_clear()
        self.addCleanup(icons.resolve.cache_clear); self.addCleanup(icons.desktop_icons.cache_clear)

    def test_startup_class_maps_to_svg_preferred_over_png(self):
        apps=self.root/'applications'; apps.mkdir()
        (apps/'org.example.App.desktop').write_text('[Desktop Entry]\nStartupWMClass=Example\nIcon=example-app\nExec=never-run-this\n')
        svg=self.root/'icons/hicolor/scalable/apps/example-app.svg'; svg.parent.mkdir(parents=True); svg.write_text('<svg/>')
        png=self.root/'icons/hicolor/256x256/apps/example-app.png'; png.parent.mkdir(parents=True); png.touch()
        self.assertEqual(icons.resolve('EXAMPLE'), str(svg))
        self.assertEqual(icons.resolve('org.example.App'), str(svg))

    def test_unknown_and_traversal_are_empty(self):
        self.assertEqual(icons.resolve('../untrusted'), '')
        self.assertEqual(icons.resolve('missing-app-unique'), '')

    def test_absolute_desktop_icon(self):
        apps=self.root/'applications'; apps.mkdir()
        icon=self.root/'my icon.svg'; icon.write_text('<svg/>')
        (apps/'example.desktop').write_text('[Desktop Entry]\nIcon='+str(icon)+'\n')
        self.assertEqual(icons.resolve('example'), str(icon))
