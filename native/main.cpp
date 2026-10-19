// Native decoration and input routing for Hyprland 0.56.2 only.
#include "titlebar.hpp"
#include "snap.hpp"
#include "style.hpp"
#include <hyprland/src/config/lua/bindings/LuaBindingsInternal.hpp>
#include <hyprland/src/render/OpenGL.hpp>
#include <hyprland/src/render/pass/PassElement.hpp>
#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/desktop/view/Window.hpp>
#include <hyprland/src/desktop/state/FocusState.hpp>
#include <hyprland/src/desktop/state/ViewState.hpp>
#include <hyprland/src/desktop/state/WindowState.hpp>
#include <hyprland/src/desktop/state/ViewHitTester.hpp>
#include <hyprland/src/event/EventBus.hpp>
#include <hyprland/src/helpers/signal/Signal.hpp>
#include <hyprland/src/managers/EventManager.hpp>
#include <hyprland/src/managers/SeatManager.hpp>
#include <hyprland/src/managers/SessionLockManager.hpp>
#include <hyprland/src/managers/input/InputManager.hpp>
#include <hyprland/src/layout/LayoutManager.hpp>
#include <hyprland/src/layout/target/WindowTarget.hpp>
#include <hyprland/src/layout/supplementary/DragController.hpp>
#include <hyprland/src/render/Renderer.hpp>
#include <hyprland/src/state/MonitorState.hpp>
#include <algorithm>
#include <chrono>
#include <format>

#include "tasks.hpp"
#include "overview-filter.hpp"

using namespace Floatland;
static HANDLE handle;
static std::vector<FloatlandBar*> bars;
static FloatlandBar* captured = nullptr;
static Click click;
static bool ownedDrag = false;
static bool consumeRelease = false;
static bool movedDuringPress = false;
static bool restoredDuringDrag = false;
static Point dragGrip;
static PHLWINDOWREF lastClickWindow;
static Point lastClickPoint;
static auto lastClickTime = std::chrono::steady_clock::time_point{};

static PHLMONITORREF snapMonitor;
static std::string selectedZone;
static Rect snapFrom, snapTo;
static double snapAlphaFrom=0, snapAlphaTo=0;
static auto snapStart=std::chrono::steady_clock::now();
static double snapProgress() { return easeOverview(std::chrono::duration<double>(std::chrono::steady_clock::now()-snapStart).count()/Style::snapDuration); }
static double snapAlpha() { return snapAlphaFrom+(snapAlphaTo-snapAlphaFrom)*snapProgress(); }
static bool draggingOurWindow() {
    const auto target = g_layoutManager->dragController()->target();
    return ownedDrag && captured && captured->visible() && target &&
        target->window() == captured->owner() && (restoredDuringDrag || g_layoutManager->dragController()->dragThresholdReached());
}
static void clearSnap() {
    if (auto m = snapMonitor.lock()) g_pHyprRenderer->damageMonitor(m);
    snapMonitor.reset();
    selectedZone.clear();
    snapAlphaFrom=snapAlphaTo=0;
}
static void updateSnap(Point p, bool ownedRelease = false) {
    if (!Style::snapEnabled) { clearSnap(); return; }
    if (!ownedRelease && !draggingOurWindow()) { clearSnap(); return; }
    auto m=State::monitorState()->query().vec(Vector2D{p.x,p.y}).run();
    if (!m) { clearSnap(); return; }
    const auto area=m->m_reservedArea.apply(CBox{m->m_position,m->m_size});
    const auto zone=snapZone({m->m_position.x,m->m_position.y,m->m_size.x,m->m_size.y},{area.x,area.y,area.w,area.h},p,Style::snap_palette,Style::snap_edges);
    const bool changedMonitor=snapMonitor.lock()!=m;
    if (changedMonitor || zone!=selectedZone) {
        const double alpha=changedMonitor?0:snapAlpha();
        auto current=interpolate(snapFrom,snapTo,snapProgress());
        if (auto old=snapMonitor.lock()) g_pHyprRenderer->damageMonitor(old);
        if (!zone.empty()) {
            const auto destination=zoneRect({area.x,area.y,area.w,area.h},zone);
            // Retarget from the displayed rectangle, even in the middle of a transition.
            snapFrom=alpha>.001?current:destination; snapTo=destination;
        } else snapFrom=snapTo=current;
        snapAlphaFrom=alpha; snapAlphaTo=zone.empty()?0:1;
        snapStart=std::chrono::steady_clock::now();
    }
    snapMonitor=m; selectedZone=zone;
    g_pHyprRenderer->damageMonitor(m);
}
class PalettePass : public IPassElement {
  public:
    std::vector<UP<IPassElement>> draw() override {
        auto m = snapMonitor.lock();
        if (!draggingOurWindow() || !m || g_pHyprRenderer->m_renderData.pMonitor.lock() != m) return {};
        const auto box = m->m_reservedArea.apply(CBox{m->m_position, m->m_size});
        const Rect area{box.x, box.y, box.w, box.h};
        auto rect = [&](Rect r, CHyprColor color) {
            r = pixels(r, {m->m_position.x, m->m_position.y}, m->m_scale);
            Render::GL::g_pHyprOpenGL->renderRect(CBox{r.x,r.y,r.w,r.h}, color, {});
        };
        const double fade=snapAlpha();
        if (Style::snap_preview && fade>0) {
            auto r=pixels(interpolate(snapFrom,snapTo,snapProgress()),{m->m_position.x,m->m_position.y},m->m_scale);
            Render::GL::CHyprOpenGLImpl::SRectRenderData data{};
            data.round=captured && captured->owner()?static_cast<int>(captured->owner()->rounding()*m->m_scale):0;
            if (captured && captured->owner()) data.roundingPower=captured->owner()->roundingPower();
            Render::GL::g_pHyprOpenGL->renderRect(CBox{r.x,r.y,r.w,r.h},CHyprColor(Style::snap[0],Style::snap[1],Style::snap[2],Style::snapOpacity*fade),data);
        }
        if (snapProgress()<1) g_pHyprRenderer->damageMonitor(m);
        for (int i = 0; Style::snap_palette && i < 5; ++i) {
            auto cell = paletteCell(area, i);
            rect(cell, CHyprColor(.08,.10,.14,.96));
            cell = {cell.x+6, cell.y+8, std::max(1.0,cell.w-12), cell.h-16};
            rect(cell, CHyprColor(.3,.34,.4,1.));
            rect(zoneRect(cell, PALETTE_ZONES[i]), selectedZone == PALETTE_ZONES[i] ?
                CHyprColor(.4,.7,1.,1.) : CHyprColor(.65,.7,.78,1.));
        }
        return {};
    }
    bool needsLiveBlur() override { return false; }
    bool needsPrecomputeBlur() override { return false; }
    const char* passName() override { return "FloatlandPalettePass"; }
    ePassElementType type() override { return EK_CUSTOM; }
};

static void endDrag() {
    clearSnap();
    if (ownedDrag) {
        // Never terminate a different drag started by another input path.
        const auto target = g_layoutManager->dragController()->target();
        if (captured && target && target->window() == captured->owner())
            g_layoutManager->dragController()->dragEnd();
        ownedDrag = false;
    }
}
void forgetBar(FloatlandBar* bar) {
    if (captured == bar) {
        endDrag();
        captured = nullptr;
        click.active = false;
        // A swallowed press still owns the matching release after window closure.
    }
    std::erase(bars, bar);
}
static void addBar(PHLWINDOW w) {
    if (!w || w->m_X11DoesntWantBorders) return;
    for (const auto& decoration : w->m_windowDecorations)
        if (decoration->getDisplayName() == "FloatlandTitlebar" || decoration->getDisplayName() == "Hyprbar")
            return; // Do not stack two server-side titlebars.
    auto bar = makeUnique<FloatlandBar>(w);
    bars.push_back(bar.get());
    HyprlandAPI::addWindowDecoration(handle, w, std::move(bar));
}
static void resyncBars() {
    for (const auto& w : Desktop::windowState()->windows()) {
        if (!w->m_isMapped || w->isHidden()) continue;
        addBar(w);
        // Registration and render caches must not depend on a future resize or
        // workspace change to initialize an already floating window after reload.
        for (auto* bar : bars) {
            if (bar->owner() != w) continue;
            bar->updateWindow(w);
            g_pDecorationPositioner->repositionDeco(bar);
        }
        g_pDecorationPositioner->forceRecalcFor(w);
        w->updateWindowDecos();
        g_pHyprRenderer->damageWindow(w);
    }
}
static int appearanceLua(lua_State* L) {
    luaL_checktype(L,1,LUA_TTABLE);
    auto color=[&](const char* key,std::array<double,3>& target) {
        lua_getfield(L,1,key); const std::string value=luaL_checkstring(L,-1); lua_pop(L,1);
        if (value.size()!=7 || value[0]!='#' || value.find_first_not_of("0123456789abcdefABCDEF",1)!=std::string::npos)
            luaL_error(L,"invalid appearance color: %s",key);
        const auto rgb=std::stoul(value.substr(1),nullptr,16);
        target={((rgb>>16)&255)/255.,((rgb>>8)&255)/255.,(rgb&255)/255.};
    };
    auto boolean=[&](const char* key) {
        lua_getfield(L,1,key);
        if (!lua_isboolean(L,-1)) luaL_error(L,"invalid appearance boolean: %s",key);
        const bool v=lua_toboolean(L,-1); lua_pop(L,1); return v;
    };
    auto number=[&](const char* key,double low,double high) {
        lua_getfield(L,1,key); const double v=luaL_checknumber(L,-1); lua_pop(L,1);
        if (!std::isfinite(v) || v<low || v>high) luaL_error(L,"invalid appearance number: %s",key);
        return v;
    };
    std::array<double,3> next_titlebar; color("titlebar_color",next_titlebar);
    const auto next_titlebarOpacity=number("titlebar_opacity",0,1);
    std::array<double,3> next_snap; color("snap_color",next_snap);
    const auto next_snapOpacity=number("snap_opacity",0,1);
    std::array<double,3> next_tab; color("tab_color",next_tab);
    const auto next_tabOpacity=number("tab_opacity",0,1);
    const auto next_fontSize=number("tab_font_size",8,24);
    if (std::floor(next_fontSize)!=next_fontSize) return luaL_error(L,"tab_font_size must be an integer");
    const auto next_iconSize=number("tab_icon_size",32,128);
    if (std::floor(next_iconSize)!=next_iconSize) return luaL_error(L,"tab_icon_size must be an integer");
    std::array<double,3> next_titleText; color("titlebar_text_color",next_titleText);
    const auto next_titleFontSize=number("titlebar_font_size",6,24);
    if (std::floor(next_titleFontSize)!=next_titleFontSize) return luaL_error(L,"titlebar_font_size must be an integer");
    std::array<double,3> next_closeColor; color("close_color",next_closeColor);
    std::array<double,3> next_minimizeColor; color("minimize_color",next_minimizeColor);
    std::array<double,3> next_maximizeColor; color("maximize_color",next_maximizeColor);
    const auto next_buttonShift=number("button_shift",0,2);
    const auto next_buttonStretch=number("button_stretch",0,2);
    const auto next_buttonReturnDuration=number("button_return_duration",0.05,0.5);
    const auto next_buttonRebound=number("button_rebound",0,0.15);
    const bool next_buttonTexture=boolean("button_texture");
    const bool next_titlebarsEnabled=boolean("titlebars_enabled");
    const bool next_snapEnabled=boolean("snap_enabled");
    const auto next_snapDuration=number("snap_duration",0.035,1);
    const bool next_overviewEnabled=boolean("overview_enabled");
    const bool next_overviewBlur=boolean("overview_blur");
    std::array<double,3> next_overviewColor; color("overview_color",next_overviewColor);
    const auto next_overviewOpacity=number("overview_opacity",0,1);
    const auto next_overviewEnterDuration=number("overview_enter_duration",0.035,1);
    const auto next_overviewExitDuration=number("overview_exit_duration",0.035,1);
    const bool next_switchingEnabled=boolean("switching_enabled");
    const auto next_tabEnterDuration=number("tab_enter_duration",0.035,0.5);
    const auto next_tabExitDuration=number("tab_exit_duration",0.035,0.5);
    const bool next_bindingsEnabled=boolean("bindings_enabled");
    const auto next_altTabKey=number("alt_tab_key",1,255);
    if (std::floor(next_altTabKey)!=next_altTabKey) return luaL_error(L,"alt_tab_key must be an integer");
    const auto next_overviewKey=number("overview_key",1,255);
    if (std::floor(next_overviewKey)!=next_overviewKey) return luaL_error(L,"overview_key must be an integer");
    auto textValue=[&](const char* key) {
        lua_getfield(L,1,key); std::string value=luaL_checkstring(L,-1); lua_pop(L,1); return value;
    };
    const auto next_buttons_side=textValue("buttons_side");
    if (next_buttons_side!="left" && next_buttons_side!="right") return luaL_error(L,"invalid buttons_side");
    const auto next_buttons_order=textValue("buttons_order");
    const auto next_title_alignment=textValue("title_alignment");
    if (next_title_alignment!="left" && next_title_alignment!="center" && next_title_alignment!="right") return luaL_error(L,"invalid title_alignment");
    const auto next_title_enabled=boolean("title_enabled");
    const auto next_button_highlight=number("button_highlight",0,0.6);
    const auto next_button_growth=number("button_growth",0,2);
    const auto next_button_hinting=boolean("button_hinting");
    const auto next_button_icons=boolean("button_icons");
    const auto next_button_hover_only=boolean("button_hover_only");
    const auto next_snap_palette=boolean("snap_palette");
    const auto next_snap_edges=boolean("snap_edges");
    const auto next_snap_preview=boolean("snap_preview");
    if (!validButtonOrder(next_buttons_order)) return luaL_error(L,"invalid buttons_order");
    // Commit only after every field has passed validation.
    Style::titlebar=next_titlebar;
    Style::titlebarOpacity=next_titlebarOpacity;
    Style::snap=next_snap;
    Style::snapOpacity=next_snapOpacity;
    Style::tab=next_tab;
    Style::tabOpacity=next_tabOpacity;
    Style::fontSize=next_fontSize;
    Style::iconSize=next_iconSize;
    Style::titleText=next_titleText;
    Style::titleFontSize=next_titleFontSize;
    Style::closeColor=next_closeColor;
    Style::minimizeColor=next_minimizeColor;
    Style::maximizeColor=next_maximizeColor;
    Style::buttonShift=next_buttonShift;
    Style::buttonStretch=next_buttonStretch;
    Style::buttonReturnDuration=next_buttonReturnDuration;
    Style::buttonRebound=next_buttonRebound;
    Style::buttonTexture=next_buttonTexture;
    Style::titlebarsEnabled=next_titlebarsEnabled;
    Style::snapEnabled=next_snapEnabled;
    Style::snapDuration=next_snapDuration;
    Style::overviewEnabled=next_overviewEnabled;
    Style::overviewBlur=next_overviewBlur;
    Style::overviewColor=next_overviewColor;
    Style::overviewOpacity=next_overviewOpacity;
    Style::overviewEnterDuration=next_overviewEnterDuration;
    Style::overviewExitDuration=next_overviewExitDuration;
    Style::switchingEnabled=next_switchingEnabled;
    Style::tabEnterDuration=next_tabEnterDuration;
    Style::tabExitDuration=next_tabExitDuration;
    Style::bindingsEnabled=next_bindingsEnabled;
    Style::altTabKey=next_altTabKey;
    Style::overviewKey=next_overviewKey;
    Style::buttons_side=next_buttons_side;
    Style::buttons_order=next_buttons_order;
    Style::title_alignment=next_title_alignment;
    Style::title_enabled=next_title_enabled;
    Style::button_highlight=next_button_highlight;
    Style::button_growth=next_button_growth;
    Style::button_hinting=next_button_hinting;
    Style::button_icons=next_button_icons;
    Style::button_hover_only=next_button_hover_only;
    Style::snap_palette=next_snap_palette;
    Style::snap_edges=next_snap_edges;
    Style::snap_preview=next_snap_preview;
    // Cancel an existing button grab before changing its layout.
    if (captured && click.pressed != Control::None) {
        captured->releaseButton(); captured=nullptr; click.active=false;
    }
    TaskUI::hide();
    TaskUI::flow.enterSeconds=Style::overviewEnterDuration;
    TaskUI::flow.exitSeconds=Style::overviewExitDuration;
    ++Style::revision;
    TaskUI::texture.reset(); TaskUI::damage();
    for (auto* bar:bars) { bar->updateWindow(bar->owner()); bar->damageEntire(); }
    lua_pushinteger(L,Style::revision);
    return 1;
}
static int refreshLua(lua_State*) {
    resyncBars();
    return 0;
}
static void refresh(PHLWINDOW w) {
    if (!w) return;
    for (auto* bar : bars) if (bar->owner() == w) bar->updateWindow(w);
    g_pDecorationPositioner->onWindowUpdate(w);
}
static FloatlandBar* hit(Point point) {
    if (g_pSessionLockManager->isSessionLocked() || g_pInputManager->isConstrained()) return nullptr;
    const Vector2D p{point.x, point.y};
    auto monitor = State::monitorState()->query().vec(p).run();
    if (!monitor || monitor->m_activeSpecialWorkspace) return nullptr;
    // Layer-shell panels and popups take precedence over window decorations.
    Desktop::CViewHitTester tester{*Desktop::viewState()};
    Vector2D local;
    PHLLS surface;
    for (const auto layer : {2U, 3U}) {
        if (tester.layerSurfaceAt(p, &monitor->m_layerSurfaceLayers[layer], &local, &surface))
            return nullptr;
        if (tester.layerPopupSurfaceAt(p, &monitor->m_layerSurfaceLayers[layer], &local, &surface))
            return nullptr;
    }
    const auto w = tester.windowAt(p, Desktop::View::ALLOW_FLOATING |
                                     Desktop::View::RESERVED_EXTENTS | Desktop::View::INPUT_EXTENTS);
    if (!w || w->hasPopupAt(p)) return nullptr;
    if (!w->wlSurface() || !w->wlSurface()->resource()) return nullptr;
    if (g_pSeatManager->m_seatGrab && !g_pSeatManager->m_seatGrab->accepts(w->wlSurface()->resource()))
        return nullptr;
    refresh(w);
    for (auto* bar : bars)
        if (bar->owner() == w && bar->visible() && bar->globalBox().contains(point)) return bar;
    return nullptr;
}
static void action(FloatlandBar* bar, Control control) {
    const auto w = bar ? bar->owner() : nullptr;
    if (!w || !w->m_isMapped) return;
    const char* name = control == Control::Close ? "close" :
        control == Control::Minimize ? "minimize" :
        control == Control::Maximize ? "maximize" : nullptr;
    if (!name) return;
    g_pEventManager->postEvent({"floatland_bars",
        std::format("1,{},0x{:x},{},", name, reinterpret_cast<uintptr_t>(w.get()), w->getPID())});
}
static void dragEvent(PHLWINDOW w, const char* actionName, const std::string& value = "") {
    if (w) g_pEventManager->postEvent({"floatland_bars", std::format("1,{},0x{:x},{},{}",
        actionName, reinterpret_cast<uintptr_t>(w.get()), w->getPID(), value)});
}
static std::string rectPayload(const CBox& box) {
    return std::format("{};{};{};{}", std::lround(box.x), std::lround(box.y),
                       std::lround(box.w), std::lround(box.h));
}
static FloatlandBar* luaBar(lua_State* L) {
    const std::string addr = luaL_checkstring(L, 1);
    const auto pid = luaL_checkinteger(L, 2);
    for (auto* bar : bars) {
        const auto w = bar->owner();
        if (w && w->m_isMapped && w->getPID() == pid &&
            std::format("0x{:x}", reinterpret_cast<uintptr_t>(w.get())) == addr) return bar;
    }
    return nullptr;
}
static int restoreSizeLua(lua_State* L) {
    auto* bar = luaBar(L);
    const double w = luaL_checknumber(L, 3), h = luaL_checknumber(L, 4);
    if (bar) {
        bar->restoreSize.reset();
        if (std::isfinite(w) && std::isfinite(h) && w > 0 && h > 0)
            bar->restoreSize = Point{w, h};
    }
    return 0;
}
static int geometryLua(lua_State* L) {
    auto* bar = luaBar(L);
    const double x = luaL_checknumber(L, 3), y = luaL_checknumber(L, 4);
    const double w = luaL_checknumber(L, 5), h = luaL_checknumber(L, 6);
    const auto owner = bar ? bar->owner() : nullptr;
    if (!owner || !owner->m_isFloating || !std::isfinite(x) || !std::isfinite(y) ||
        !std::isfinite(w) || !std::isfinite(h) || w <= 0 || h <= 0) {
        lua_pushboolean(L, false);
        return 1;
    }
    owner->layoutTarget()->setPositionGlobal(CBox{x, y, w, h});
    lua_pushboolean(L, true);
    return 1;
}
static void restoreDuringDrag(Point pointer) {
    if (!draggingOurWindow() || !click.moved(pointer) || restoredDuringDrag || !captured->restoreSize) return;
    const auto w = captured->owner();
    const auto target = w->layoutTarget();
    auto monitor = State::monitorState()->query().vec(Vector2D{pointer.x, pointer.y}).run();
    if (!monitor) return;
    auto size = *captured->restoreSize;
    if (const auto minimum = target->minSize()) {
        size.x = std::max(size.x, minimum->x); size.y = std::max(size.y, minimum->y);
    }
    if (const auto maximum = target->maxSize()) {
        if (maximum->x > 0) size.x = std::min(size.x, maximum->x);
        if (maximum->y > 0) size.y = std::min(size.y, maximum->y);
    }
    const auto area = monitor->m_reservedArea.apply(CBox{monitor->m_position, monitor->m_size});
    const auto rect = restoredDragRect(pointer, size, dragGrip,
        {area.x, area.y + HEIGHT, area.w, std::max(1.0, area.h - HEIGHT)});
    // Restart the compositor's drag origin after an atomic resize, otherwise the
    // next mouse delta would reapply its cached snapped size and position.
    g_layoutManager->dragController()->dragEnd();
    target->setPositionGlobal(CBox{rect.x, rect.y, rect.w, rect.h});
    target->warpPositionSize();
    captured->restoreSize.reset();
    restoredDuringDrag = true;
    g_layoutManager->dragController()->dragBegin(target, MBIND_MOVE, std::nullopt, true);
    dragEvent(w, "drag-restored", rectPayload(CBox{rect.x, rect.y, rect.w, rect.h}));
}
static void mouseButton(IPointer::SButtonEvent e, Event::SCallbackInfo& info) {
    if (TaskUI::button(e, info)) return;
    if (e.button != 272) return;
    const auto cursor = g_pInputManager->getMouseCoordsInternal();
    const Point point{cursor.x, cursor.y};
    if (e.state == WL_POINTER_BUTTON_STATE_RELEASED && consumeRelease) {
        info.cancelled = true;
        consumeRelease = false;
        auto* bar = captured;
        // Core may have ended DragController before our release callback after
        // plugin reload. Our swallowed press/motion still owns this release.
        const bool dragged = ownsSnapDrop(ownedDrag, bar && bar->visible(),
            movedDuringPress || click.moved(point), draggingOurWindow());
        updateSnap(point, dragged);
        const auto zone = selectedZone;
        const auto dropWindow = bar ? bar->owner() : nullptr;
        endDrag();
        if (dragged && !zone.empty() && dropWindow) {
            click.active = false;
            captured = nullptr;
            lastClickWindow.reset();
            g_pEventManager->postEvent({"floatland_bars", std::format("1,snap,0x{:x},{},{}",
                reinterpret_cast<uintptr_t>(dropWindow.get()), dropWindow->getPID(), zone)});
            return;
        }
        if (dropWindow && click.pressed == Control::None) dragEvent(dropWindow, "drag-end");
        const bool valid = bar && bar->visible() && hit(point) == bar;
        const auto over = valid ? bar->controlAt(point) : Control::None;
        const auto pressed = click.pressed;
        const auto result = click.release(over, !valid || (pressed == Control::None && (dragged || movedDuringPress)));
        if (bar) bar->releaseButton();
        captured = nullptr;
        if (!valid) { lastClickWindow.reset(); return; }
        if (pressed != Control::None) {
            lastClickWindow.reset();
            action(bar, result);
            return;
        }
        if (dragged || movedDuringPress || over != Control::None) {
            lastClickWindow.reset();
            return;
        }
        const auto now = std::chrono::steady_clock::now();
        const bool doubleClick = lastClickWindow.lock() == bar->owner() &&
            now - lastClickTime < std::chrono::milliseconds(350) &&
            std::hypot(point.x-lastClickPoint.x, point.y-lastClickPoint.y) <= 4;
        if (doubleClick) {
            lastClickWindow.reset();
            action(bar, Control::Maximize);
        } else {
            lastClickWindow = bar->owner();
            lastClickPoint = point;
            lastClickTime = now;
        }
        return;
    }
    if (e.state != WL_POINTER_BUTTON_STATE_PRESSED || info.cancelled || consumeRelease) return;
    if (g_layoutManager->dragController()->target()) return;
    auto* bar = hit(point);
    if (!bar) return;
    info.cancelled = true; // Both press and release bypass client delivery.
    consumeRelease = true;
    captured = bar;
    movedDuringPress = false;
    restoredDuringDrag = false;
    click.begin(bar->controlAt(point), point);
    bar->pressedControl = click.pressed;
    bar->hovered = click.pressed;
    bar->pressOffset = {};
    bar->pressStarted = std::chrono::steady_clock::now();
    bar->damageEntire();
    Desktop::focusState()->fullWindowFocus(bar->owner(), Desktop::FOCUS_REASON_CLICK);
    Desktop::windowState()->raise(bar->owner());
    if (click.pressed == Control::None) {
        const auto box = bar->globalBox();
        dragGrip = {(point.x - box.x) / std::max(1.0, box.w), point.y - box.y};
        dragEvent(bar->owner(), "drag-start", rectPayload(bar->owner()->layoutTarget()->position()));
        g_layoutManager->dragController()->dragBegin(bar->owner()->layoutTarget(), MBIND_MOVE,
                                                     std::nullopt, true);
        ownedDrag = true;
    }
}
struct Listeners {
    CHyprSignalListener overviewPre, open, floating, fullscreen, rules, pin, workspace, render, button, move, lock, tasksKey, tasksAxis;
    Listeners() {
        overviewPre=Event::bus()->m_events.render.preChecks.listen([](PHLMONITOR m) {
            OverviewFilter::restoreSolitary();
            TaskUI::prepareFrame(m);
            if(OverviewFilter::suppress(g_pHyprRenderer.get(),m)) {
                OverviewFilter::solitaryMonitor=m; OverviewFilter::savedSolitary=m->m_solitaryClient;
                m->m_solitaryClient.reset();
            }
        });
        tasksKey = Event::bus()->m_events.input.keyboard.key.listen(TaskUI::key);
        tasksAxis = Event::bus()->m_events.input.mouse.axis.listen(TaskUI::scroll);
        open = Event::bus()->m_events.window.open.listen([](PHLWINDOW w) {
            // A newly mapped window is not part of the frozen overview scene.
            // Cancel instead of suppressing an application absent from its cards.
            if (TaskUI::kind==3) { TaskUI::hide(); TaskUI::emit("cancel"); }
            addBar(w);
        });
        floating = Event::bus()->m_events.window.floating.listen([](PHLWINDOW w) { refresh(w); });
        fullscreen = Event::bus()->m_events.window.fullscreen.listen([](PHLWINDOW w) { refresh(w); });
        rules = Event::bus()->m_events.window.updateRules.listen([](PHLWINDOW w) { refresh(w); });
        pin = Event::bus()->m_events.window.pin.listen([](PHLWINDOW w) { refresh(w); });
        workspace = Event::bus()->m_events.window.moveToWorkspace.listen([](PHLWINDOW w, PHLWORKSPACE) { refresh(w); });
        render = Event::bus()->m_events.render.stage.listen([](eRenderStage stage) {
            if(stage==RENDER_POST) OverviewFilter::restoreSolitary();
            if (stage == RENDER_LAST_MOMENT && TaskUI::kind && !TaskUI::capturing)
                g_pHyprRenderer->addPassElement(makeUnique<TaskUI::Pass>());
            if (stage == RENDER_POST_WINDOWS && draggingOurWindow())
                g_pHyprRenderer->addPassElement(makeUnique<PalettePass>());
            if (stage != RENDER_PRE_WINDOW) return;
            const auto w = g_pHyprRenderer->m_renderData.currentWindow.lock();
            if (w) g_pDecorationPositioner->onWindowUpdate(w); // Current animated size, never goal size.
        });
        button = Event::bus()->m_events.input.mouse.button.listen(mouseButton);
        move = Event::bus()->m_events.input.mouse.move.listen([](Vector2D p, Event::SCallbackInfo&) {
            TaskUI::pointerMove({p.x,p.y});
            if (captured && click.active && click.pressed != Control::None) {
                captured->pressOffset = buttonPull({p.x-click.origin.x,p.y-click.origin.y});
                captured->damageEntire();
            }
            restoreDuringDrag({p.x, p.y});
            updateSnap({p.x, p.y});
            if (click.active && click.moved({p.x, p.y})) movedDuringPress = true;
            auto* over = hit({p.x, p.y});
            for (auto* bar : bars) {
                const auto control = bar == over ? bar->controlAt({p.x, p.y}) : Control::None;
                if (control != bar->hovered) { bar->hovered = control; bar->damageEntire(); }
            }
        });
        lock = g_pSessionLockManager->m_events.lock.listen([] {
            TaskUI::reset();
            TaskUI::emit("cancel");
            if (captured) dragEvent(captured->owner(), "drag-end");
            endDrag();
            if (captured) { captured->pressedControl=Control::None; captured->pressOffset={}; captured->damageEntire(); }
            captured = nullptr;
            click.active = false;
            lastClickWindow.reset();
        });
    }
};
static UP<Listeners> listeners;

APICALL EXPORT std::string PLUGIN_API_VERSION() { return HYPRLAND_API_VERSION; }
APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE h) {
    handle = h;
    TaskUI::reset();
    captured = nullptr;
    click = {};
    ownedDrag = consumeRelease = movedDuringPress = restoredDuringDrag = false;
    lastClickWindow.reset();
    selectedZone.clear();
    snapMonitor.reset();
    if (std::string(__hyprland_api_get_hash()) != std::string(__hyprland_api_get_client_hash()))
        throw std::runtime_error("Floatland titlebars: compositor/header ABI mismatch; rebuild for installed Hyprland");
    if (!HyprlandAPI::addLuaFunction(handle, "floatland", "appearance", appearanceLua) ||
        !HyprlandAPI::addLuaFunction(handle, "floatland", "geometry", geometryLua) ||
        !HyprlandAPI::addLuaFunction(handle, "floatland", "restore_size", restoreSizeLua) ||
        !HyprlandAPI::addLuaFunction(handle, "floatland", "refresh", refreshLua))
        throw std::runtime_error("Floatland: could not register geometry bridge");
    if (!HyprlandAPI::addLuaFunction(handle, "floatland", "tasks", TaskUI::show) ||
        !HyprlandAPI::addLuaFunction(handle, "floatland", "prepare_overview", TaskUI::prepareOverview) ||
        !HyprlandAPI::addLuaFunction(handle, "floatland", "selection_valid", TaskUI::selectionValid) ||
        !HyprlandAPI::addLuaFunction(handle, "floatland", "finish_selection", TaskUI::finishSelection) ||
        !HyprlandAPI::addLuaFunction(handle, "floatland", "remember_preview", TaskUI::rememberPreview) ||
        !HyprlandAPI::addLuaFunction(handle, "floatland", "overview_active", TaskUI::overviewState) ||
        !HyprlandAPI::addLuaFunction(handle, "floatland", "raise_window", TaskUI::raiseWindow))
        throw std::runtime_error("Floatland task UI registration failed");
    OverviewFilter::install(handle);
    try { listeners = makeUnique<Listeners>(); resyncBars(); }
    catch(...) { listeners.reset(); OverviewFilter::remove(handle); throw; }
    return {"floatland-bars", "Native floating titlebars with shared render/input geometry", "Floatland / Hypr Development", "0.6.1.1"};
}
APICALL EXPORT void PLUGIN_EXIT() {
    TaskUI::reset();
    OverviewFilter::remove(handle);
    listeners.reset();
    TaskUI::reset();
    g_pHyprRenderer->m_renderPass.removeAllOfType("FloatlandTaskPass");
    endDrag();
    captured = nullptr;
    click.active = false;
    // Don't unload while holding LMB: no listener remains to consume its release.
    g_pHyprRenderer->m_renderPass.removeAllOfType("FloatlandTitlebarPass");
    g_pHyprRenderer->m_renderPass.removeAllOfType("FloatlandPalettePass");
    const auto remaining = bars;
    for (auto* bar : remaining) HyprlandAPI::removeWindowDecoration(handle, bar);
    bars.clear();
}
