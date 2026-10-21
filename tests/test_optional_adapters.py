import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from floatland.config import APPEARANCE

ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    obj=importlib.util.module_from_spec(spec); spec.loader.exec_module(obj); return obj

class OptionalAdapters(unittest.TestCase):
    def test_css_uses_validated_colors_and_diameter(self):
        common=module('flcommon',ROOT/'integrations/common.py')
        settings=dict(APPEARANCE,button_size=19,close_color='#123456')
        css=common.gtk_css(settings)
        self.assertIn('19px',css);self.assertIn('#123456',css)

    def test_equibop_rejects_wrong_source_without_modifying_it(self):
        launcher=module('flozone',ROOT/'integrations/ozone/launch.py')
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source';source.mkdir()
            with self.assertRaises(ValueError):launcher.prepare(source,Path(folder)/'copy')
            self.assertEqual(list(source.iterdir()),[])

    def test_equibop_patch_preserves_sandbox_and_original_files(self):
        launcher=module('flozone2',ROOT/'integrations/ozone/launch.py')
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source';output=Path(folder)/'output'
            files={'src/main/mainWindow.ts':'const frameless = !nativeTitleBar;\nconst options = {sandbox: true, contextIsolation: true};',
                   'src/renderer/index.ts':'import "./themedSplash";',
                   'src/renderer/patches/windowsTitleBar.tsx':'if (!Settings.store.nativeTitleBar) {}',
                   'src/preload/index.ts':'// existing preload'}
            for path,content in files.items():
                p=source/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
            launcher.prepare(source,output)
            for path,content in files.items():self.assertEqual((source/path).read_text(),content)
            text=(output/'src/main/mainWindow.ts').read_text()
            self.assertIn('sandbox: true',text);self.assertIn('contextIsolation: true',text)
            self.assertTrue((output/'src/renderer/floatland-controls.ts').exists())

    def test_packaged_adapter_preserves_main_and_security_flags(self):
        import json
        adapter=module('flinstalled',ROOT/'integrations/ozone/installed.py')
        with tempfile.TemporaryDirectory() as folder:
            app=Path(folder); main=app/'main.js'
            original='const options = {sandbox:true,contextIsolation:true};'
            main.write_text(original)
            (app/'package.json').write_text(json.dumps({'name':'equibop','main':'main.js'}))
            adapter.adapt_directory(app)
            self.assertEqual(main.read_text(),original)
            self.assertEqual(json.loads((app/'package.json').read_text())['main'],'floatland-bootstrap.cjs')
            self.assertEqual(json.loads((app/'floatland-entry.json').read_text()),'main.js')
            bootstrap=(app/'floatland-bootstrap.cjs').read_text()
            self.assertNotIn('remote-debugging',bootstrap)
            self.assertNotIn('sandbox:false',bootstrap)

    def test_packaged_adapter_rejects_other_applications(self):
        adapter=module('flinstalled2',ROOT/'integrations/ozone/installed.py')
        with tempfile.TemporaryDirectory() as folder:
            app=Path(folder); p=app/'package.json'; p.write_text('{"name":"other"}')
            original=p.read_bytes()
            with self.assertRaises(ValueError): adapter.adapt_directory(app)
            self.assertEqual(p.read_bytes(),original)

    def test_qt_detection_uses_linked_library_not_application_name(self):
        from unittest.mock import patch,Mock
        qt=module('flqt',ROOT/'integrations/qt/launch.py')
        with patch.object(qt.subprocess,'run',return_value=Mock(stdout='libQt5Core.so.5 => /lib/libQt5Core.so.5')):
            self.assertEqual(qt.detect_qt_major('kate'),'5')
        with patch.object(qt.subprocess,'run',return_value=Mock(stdout='libQt6Core.so.6 => /lib/libQt6Core.so.6')):
            self.assertEqual(qt.detect_qt_major('kate'),'6')

    def test_aur_launcher_is_read_not_executed(self):
        from unittest.mock import patch
        adapter=module('flaur',ROOT/'integrations/ozone/installed.py')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); archive=root/'app.asar'; archive.write_text('fixture')
            launcher=root/'equibop'; launcher.write_text('#!/bin/sh\nexec electron43 '+str(archive)+' "$@"\n')
            with patch.object(adapter.shutil,'which',side_effect=lambda name:'/usr/bin/electron43' if name=='electron43' else None):
                found,runtime=adapter.locate_system(str(launcher))
            self.assertEqual(found,archive)
            self.assertEqual(str(runtime),'/usr/bin/electron43')

    def test_system_adapter_keeps_helpers_and_original_archive(self):
        import json
        from unittest.mock import patch
        adapter=module('flaurpack',ROOT/'integrations/ozone/installed.py')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'package'; source.mkdir()
            archive=source/'app.asar'; archive.write_text('original')
            (source/'arrpc').mkdir(); (source/'arrpc/helper').write_text('helper')
            def run(command,**kwargs):
                if command[1]=='extract':
                    extracted=Path(command[3]);extracted.mkdir()
                    (extracted/'package.json').write_text(json.dumps({'name':'equibop','main':'main.js'}))
                    (extracted/'main.js').write_text('// original entry')
                else:
                    Path(command[3]).write_text('adapted')
            with patch.object(adapter.shutil,'which',return_value='asar'), patch.object(adapter.subprocess,'run',side_effect=run):
                command=adapter.prepare_system(archive,Path('/usr/bin/electron43'),root/'private')
            self.assertEqual(archive.read_text(),'original')
            self.assertEqual((root/'private/arrpc/helper').read_text(),'helper')
            self.assertEqual(command,['/usr/bin/electron43',str(root/'private/app.asar')])

    def test_gtk_status_cannot_be_overwritten_by_helper_pid(self):
        import json
        common=module('flstatus',ROOT/'integrations/common.py')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'status.json'
            Path(str(path)+'.123').write_text(json.dumps({'pid':123,'phase':'controls-attached','headers':1}))
            Path(str(path)+'.456').write_text(json.dumps({'pid':456,'phase':'module-loaded','headers':0}))
            self.assertEqual(common.gtk_status(path,123)['headers'],1)
            self.assertEqual(common.gtk_status(path,789),{})
            Path(str(path)+'.123').write_text('{"pid":456,"headers":0}')
            self.assertEqual(common.gtk_status(path,123),{})

    def test_gtk_settings_exports_motion_and_live_style_values(self):
        common=module('flgtksettings',ROOT/'integrations/common.py')
        text=common.gtk_settings(dict(APPEARANCE,button_stretch=.8,button_hover_only=False))
        self.assertIn('button_stretch=0.8\n',text)
        self.assertIn('button_hover_only=false\n',text)
        self.assertIn('button_return_duration=',text)
