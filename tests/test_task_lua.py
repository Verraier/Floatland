import unittest
from floatland.ipc import Hyprland
from floatland.geometry import Rect
try:
    from lupa import LuaRuntime
except ImportError:
    LuaRuntime = None

@unittest.skipIf(LuaRuntime is None, 'lupa not installed')
class TaskLuaTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute('''
            calls = {}; active = false; native_geometry = true
            local function record(name, ...) table.insert(calls, {name, ...}) end
            hl = {plugin = {floatland = {}, hyprtasking = {}}, dsp = {window = {}}}
            hl.get_window = function(address) return address end
            hl.dispatch = function(action) record('dispatch', action) end
            hl.config = function(value) config = value end
            hl.dsp.window.resize = function(value) return value end
            hl.dsp.window.move = function(value) return value end
            hl.plugin.floatland.remember_preview = function(...) record('preview', ...) end
            hl.plugin.floatland.prepare_tab = function(...) record("prepare-tab", ...) end
            hl.plugin.floatland.prepare_overview = function(...) record('prepare', ...) end
            hl.plugin.floatland.selection_valid = function(token) return token == 7 end
            hl.plugin.floatland.finish_selection = function(...) record('finish', ...) end
            hl.plugin.floatland.tasks = function(...) record('tasks', ...) end
            hl.plugin.floatland.appearance = function(value) appearance = value; return 1 end
            hl.plugin.floatland.geometry = function(...) record('geometry', ...); return native_geometry end
            hl.plugin.floatland.restore_size = function(...) record('restore_size', ...) end
            hl.plugin.floatland.raise_window = function(...) record('raise', ...) end
            hl.plugin.floatland.overview_active = function(value) overview_active = value end
            hl.plugin.hyprtasking.toggle = function(mode) active = not active end
            hl.plugin.hyprtasking.is_active = function() return active end
        ''')
        self.ipc = Hyprland('/tmp')
        self.ipc.evaluate = lambda source, operation='eval': self.lua.execute(source)
        self.ipc.query = lambda name: [{'height':1080,'scale':1}]
        self.w = {'address':'0xabc', 'pid':123}

    def test_appearance_boolean_and_numeric_settings_are_valid_lua(self):
        self.ipc.configure_appearance({'overview_blur':False,'button_texture':False,'button_shift':1.2,'overview_key':35})
        settings=self.lua.globals().appearance
        self.assertIs(settings['overview_blur'],False)
        self.assertIs(settings['button_texture'],False)
        self.assertEqual(settings['button_shift'],1.2)
        self.assertEqual(settings['overview_key'],35)

    def test_old_native_plugin_cannot_silently_accept_reload(self):
        self.lua.execute('hl.plugin.floatland.appearance = function(value) end')
        with self.assertRaisesRegex(Exception, 'did not acknowledge'):
            self.ipc.configure_appearance({})

    def test_layout_and_feature_switches_reach_native(self):
        self.ipc.configure_appearance({'buttons_side':'left','buttons_order':'close,minimize',
                                      'title_alignment':'center','snap_palette':False,'button_highlight':.3})
        value=self.lua.globals().appearance
        self.assertEqual(value.buttons_order,'close,minimize')
        self.assertEqual(value.buttons_side,'left')
        self.assertEqual(value.title_alignment,'center')
        self.assertIs(value.snap_palette,False)
        self.assertEqual(value.button_highlight,.3)

    def test_switcher_styles_are_validated(self):
        for style in ('icons',):
            self.ipc.configure_appearance({'tab_style':style,'tab_mouse':False,'tab_preview_width':280})
            self.assertEqual(self.lua.globals().appearance.tab_style,style)
            self.assertIs(self.lua.globals().appearance.tab_mouse,False)
        with self.assertRaises(ValueError): self.ipc.configure_appearance({'tab_style':'bad'})

    def test_overview_generation_and_ack_lua(self):
        self.ipc.prepare_overview(7)
        self.ipc.check_selection(7)
        self.ipc.finish_selection(7, True)
        self.ipc.finish_selection(8, False)
        calls = self.lua.globals().calls
        self.assertEqual([calls[1][i] for i in range(1,3)], ['prepare', 7])
        self.assertEqual([calls[2][i] for i in range(1,4)], ['finish', 7, True])
        self.assertEqual([calls[3][i] for i in range(1,4)], ['finish', 8, False])
        with self.assertRaises(Exception): self.ipc.check_selection(8)

    def test_minimized_preview_uses_window_identity_and_can_be_released(self):
        self.ipc.remember_preview(self.w)
        self.ipc.remember_preview(self.w, False)
        calls = self.lua.globals().calls
        self.assertEqual([calls[1][i] for i in range(1, 5)], ['preview', '0xabc', 123, True])
        self.assertEqual([calls[2][i] for i in range(1, 5)], ['preview', '0xabc', 123, False])

    def test_preview_optional_with_older_or_missing_plugin(self):
        self.lua.execute('hl.plugin.floatland = nil')
        self.ipc.remember_preview(self.w)
        self.assertEqual(len(self.lua.globals().calls), 0)

    def test_native_geometry_is_one_atomic_call(self):
        self.ipc.place_geometry(self.w, Rect(-800,40,700,500))
        calls = self.lua.globals().calls
        self.assertEqual(len(calls), 1)
        self.assertEqual([calls[1][i] for i in range(1,8)], ['geometry','0xabc',123,-800,40,700,500])

    def test_geometry_falls_back_when_target_has_no_native_bar(self):
        self.lua.execute('native_geometry = false')
        self.ipc.place_geometry(self.w, Rect(-800,40,700,500))
        calls = self.lua.globals().calls
        self.assertEqual(len(calls),3)
        self.assertEqual(calls[3][2]['x'], -800)
        self.assertFalse(calls[3][2]['relative'])

    def test_task_table_and_selected_index(self):
        self.ipc.present_tasks(1, [self.w], 0)
        call = self.lua.globals().calls[1]
        self.assertEqual(call[2], 1)
        self.assertEqual(call[3][1]['address'], '0xabc')
        self.assertEqual(call[4], 0)

    def test_toggle_poll_and_close_overview(self):
        self.lua.execute('overview_active = true')
        self.lua.execute("hl.plugin.floatland.tick_ui = function() end")
        self.ipc.close_overview(); self.ipc.poll_overview()
        self.assertFalse(self.lua.globals().overview_active)

    def test_appearance_reaches_native_with_defaults(self):
        self.ipc.configure_appearance({'snap_color':'#123abc','tab_icon_size':64})
        appearance=self.lua.globals().appearance
        self.assertEqual(appearance.snap_color, '#123abc')
        self.assertEqual(appearance.tab_icon_size, 64)
        self.assertEqual(appearance.titlebar_opacity, 1)

    def test_focus_keeps_cursor_without_dispatching_when_native_handles_it(self):
        self.ipc.query=lambda name:[self.w]
        self.lua.execute('hl.plugin.floatland.focus=function(address,pid) focused={address,pid}; return true end; hl.dsp.focus=function() error("unexpected warp-capable dispatcher") end')
        self.ipc.dispatch('focuswindow','address:0xabc')
        self.assertEqual(self.lua.globals().focused[1],'0xabc')
        self.assertEqual(self.lua.globals().focused[2],123)

    def test_focus_legacy_fallback_when_native_declines(self):
        self.ipc.query=lambda name:[self.w]
        self.lua.execute('hl.plugin.floatland.focus=function() return false end; hl.dsp.focus=function(w) return w end')
        self.ipc.dispatch('focuswindow','address:0xabc')
        self.assertEqual(self.lua.globals().calls[1][1],'dispatch')

    def test_settings_page_labels_flags_and_identity_are_encoded(self):
        self.lua.execute('hl.plugin.floatland.menu_page=function(rows) menu_rows=rows end')
        self.ipc.menu_page([{'label':'Test "window"','action':'rule-mini','address':'0xabc','pid':123,'checked':True}])
        row=self.lua.globals().menu_rows[1]
        self.assertEqual(row['label'],'Test "window"')
        self.assertEqual(row['pid'],123)
        self.assertTrue(row['checked'])
        self.assertTrue(row['check'])
