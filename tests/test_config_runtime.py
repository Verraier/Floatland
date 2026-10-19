import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from floatland.config_runtime import ConfigRuntime, fingerprint
from floatland.config import load
from floatland.controller import Controller
from floatland.state import State
from test_floatland import FakeHyprland, window


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.path=self.root/'init.lua'
        config=load(self.path,create=True)
        self.ipc=FakeHyprland([window()]); self.ipc.configure_appearance=Mock()
        self.controller=Controller(self.ipc,State(self.root/'state.json'),config)
        self.runtime=ConfigRuntime(self.controller,self.path)

    async def test_manual_reload_reports_actual_path_and_applies_values(self):
        (self.root/'config/titlebars.lua').write_text('return {color="#123456",buttons_side="left"}')
        result=await self.runtime.reload()
        self.assertEqual(result['config_path'],str(self.path.resolve()))
        self.assertEqual(result['fingerprint'],fingerprint(self.path)[:12])
        self.assertEqual(self.controller.config['appearance']['buttons_side'],'left')
        self.assertEqual(self.ipc.configure_appearance.call_args.args[0]['titlebar_color'],'#123456')

    async def test_missing_or_invalid_config_preserves_running_settings(self):
        previous=self.controller.config
        self.path.unlink()
        with self.assertRaisesRegex(ValueError,'missing'): await self.runtime.reload()
        self.path.write_text('return {titlebars={opacity=2}}')
        with self.assertRaises(ValueError): await self.runtime.reload()
        self.assertIs(self.controller.config,previous)
        self.ipc.configure_appearance.assert_not_called()

    async def test_loading_runs_off_event_loop_and_changed_file_is_rejected(self):
        tick=asyncio.Event()
        async def heartbeat():
            await asyncio.sleep(.02); tick.set()
        def slow_load(path):
            import time
            time.sleep(.1)
            self.assertTrue(tick.is_set(), "Lua loading blocked the event loop")
            self.path.write_text('return {windows={gap=11}}')
            return load(path)
        task=asyncio.create_task(heartbeat())
        with patch('floatland.config_runtime.load',side_effect=slow_load):
            with self.assertRaisesRegex(ValueError,'changed while loading'): await self.runtime.reload()
        await task
        self.assertTrue(tick.is_set())
        self.ipc.configure_appearance.assert_not_called()

    async def test_watch_debounces_saves_recovers_after_error_and_stops(self):
        stop=asyncio.Event()
        task=asyncio.create_task(self.runtime.watch(stop))
        try:
            await asyncio.sleep(.05)
            self.path.write_text('return {windows={gap=-1}}')
            await asyncio.sleep(1.2)
            self.ipc.configure_appearance.assert_not_called()
            self.path.write_text('return {windows={gap=21}}')
            for _ in range(25):
                await asyncio.sleep(.1)
                if self.controller.config['gap']==21: break
            self.assertEqual(self.controller.config['gap'],21)
            self.ipc.configure_appearance.assert_called_once()
        finally:
            stop.set(); await task

    async def test_initial_watch_catches_edits_during_build(self):
        self.path.write_text('return {windows={gap=29}}')
        stop=asyncio.Event()
        task=asyncio.create_task(self.runtime.watch(stop))
        try:
            for _ in range(20):
                await asyncio.sleep(.1)
                if self.controller.config['gap']==29: break
            self.assertEqual(self.controller.config['gap'],29)
        finally:
            stop.set(); await task

    async def test_comment_only_save_does_not_close_native_ui(self):
        self.controller.config['titlebar_height']=32
        await self.runtime.reload(automatic=True)
        self.ipc.configure_appearance.assert_not_called()
        self.path.write_text(self.path.read_text()+'\n-- Updated comment\n')
        result=await self.runtime.reload(automatic=True)
        self.assertFalse(result['reloaded'])
        self.ipc.configure_appearance.assert_not_called()
