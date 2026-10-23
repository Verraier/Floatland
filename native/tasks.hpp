#pragma once
#include <pango/pangocairo.h>
#include <hyprland/src/devices/IKeyboard.hpp>
#include <set>
#include "style.hpp"
#include "overview-layout.hpp"
#include "lite-layout.hpp"
#include "switcher-layout.hpp"
#include "overview-flow.hpp"
#include <librsvg/rsvg.h>
#include <hyprland/src/render/Framebuffer.hpp>
#include <hyprland/src/desktop/Workspace.hpp>
#include <hyprland/src/managers/KeybindManager.hpp>

namespace TaskUI {
static void warning(const std::string& message) {
    g_pEventManager->postEvent({"floatland_log", "warning," + message});
}
static int kind = 0, selected = 0, first = 0, hoveredTask = -1;
static bool pointerSelection=false;
static std::vector<Floatland::Rect> cards;
static void arrange();
static Floatland::Rect box();
static void pointerMove(Floatland::Point p);
static Floatland::Rect visibleRect(int i);
static bool pending = false, overview = false, mouseOwned = false;
static PHLWINDOWREF pressed;
static std::vector<PHLWINDOWREF> windows;
static PHLMONITORREF monitor;
static int64_t workspaceId=0;
static std::set<uint32_t> swallowedButtons;
static std::set<uint32_t> swallowed;
static SP<Render::ITexture> texture;
static std::string textureKey;
static std::vector<std::string> icons;
static Floatland::SwitcherLayout tabLayout;
static bool tabPreview() { return false; }
static bool tabLegacy() { return false; }
static void layoutTabs() {
    const auto m=monitor.lock();
    if(!m) return;
    tabLayout=Floatland::switcherLayout({m->m_position.x,m->m_position.y,m->m_size.x,m->m_size.y},
        static_cast<int>(windows.size()),selected,Floatland::Style::iconSize,Floatland::Style::fontSize,
        tabPreview(),tabLegacy(),Floatland::Style::tab_preview_width);
    first=tabLayout.first;
}

struct Preview { SP<Render::IFramebuffer> fb; Floatland::Rect source; Vector2D monitorSize; Floatland::Rect origin; };
static std::vector<Preview> previews;
struct SavedPreview { PHLWINDOWREF window; Preview preview; double pixels; };
static std::vector<SavedPreview> savedPreviews;
static constexpr double previewBudget=48000000;
static void prunePreviews() {
    std::erase_if(savedPreviews, [](const auto& entry) {
        const auto w=entry.window.lock(); return !w || !w->m_isMapped;
    });
}
static bool capturing = false, closing = false;
static Floatland::OverviewFlow flow;
static size_t prepareIndex=0;
static double preparePixels=0;
static PHLWINDOWREF chosen;
static Floatland::Rect chosenFrom;
static double chosenPhase=1;
static double clockSeconds() {
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
static bool presenting() { return kind!=3 || flow.presenting(); }
static auto transitionStart=std::chrono::steady_clock::now();
static double closingFrom=1;
static double progress() {
    if (kind==3) return flow.value(clockSeconds());
    const double elapsed=std::chrono::duration<double>(std::chrono::steady_clock::now()-transitionStart).count();
    return closing ? closingFrom*(1-Floatland::easeOverview(elapsed/Floatland::Style::tabExitDuration)) : Floatland::easeOverview(elapsed/Floatland::Style::tabEnterDuration);
}

static void emit(const std::string& action) {
    g_pEventManager->postEvent({"floatland_tasks", action});
}
static void damage() {
    if (auto m = monitor.lock()) g_pHyprRenderer->damageMonitor(m);
}
static void hide() {
    tabLayout={};
    flow.reset(); chosen.reset();
    damage(); kind=0; overview=closing=pending=false;
    texture.reset(); textureKey.clear(); previews.clear(); cards.clear();
    windows.clear(); icons.clear(); pressed.reset(); mouseOwned=false; hoveredTask=-1;
    // Keep swallowed releases until delivered, even after the UI has gone away.
}
static bool contextValid() {
    const auto m=monitor.lock();
    return m && m->m_activeWorkspace && m->m_activeWorkspace->m_id==workspaceId && !m->m_activeSpecialWorkspace;
}
static void dismiss() {
    if (kind!=3 && kind!=1) { hide(); return; }
    if (kind==3) {
        if (flow.stage==Floatland::OverviewFlow::Stage::Selecting) return;
        flow.close(clockSeconds());
        if (!flow.presenting()) { hide(); return; }
        closing=true; overview=pending=false; damage(); return;
    }
    if (closing) return;
    closingFrom=progress(); closing=true; overview=pending=false;
    transitionStart=std::chrono::steady_clock::now(); damage();
}
static void toggleOverview() {
    if (kind!=3 || flow.stage==Floatland::OverviewFlow::Stage::Selecting || !chosen.expired()) return;
    flow.toggle(clockSeconds());
    if (!flow.presenting() && flow.stage!=Floatland::OverviewFlow::Stage::Preparing) { hide(); return; }
    closing=flow.stage==Floatland::OverviewFlow::Stage::Exiting;
    overview=flow.presenting() && !closing;
    damage();
}
static void choose(PHLWINDOW w) {
    if (!w || !w->m_isMapped) return;
    if (kind!=3) {
        emit(std::format("select,0x{:x},{}",reinterpret_cast<uintptr_t>(w.get()),w->getPID()));
        dismiss(); return;
    }
    if (!flow.presenting() || flow.stage==Floatland::OverviewFlow::Stage::Selecting) return;
    for(size_t i=0;i<windows.size();++i) if(windows[i].lock()==w) { selected=static_cast<int>(i); chosenFrom=visibleRect(selected); }
    chosenPhase=std::max(.001,progress());
    chosen=w; flow.select(clockSeconds()); overview=false; closing=true;
    emit(std::format("choose,0x{:x},{},{}",reinterpret_cast<uintptr_t>(w.get()),w->getPID(),flow.generation));
    damage();
}
static PHLWINDOW find(const std::string& address, int pid) {
    for (const auto& w : Desktop::windowState()->windows())
        if (w->m_isMapped && w->getPID() == pid && std::format("0x{:x}", reinterpret_cast<uintptr_t>(w.get())) == address) return w;
    return nullptr;
}
static double tabStep() { return Floatland::Style::iconSize+32.0; }
static double tabHeight() { return Floatland::Style::iconSize+Floatland::Style::fontSize+52.0; }
static int rowCapacity() {
    if(kind==1) return std::max(1,tabLayout.capacity);
    auto m = monitor.lock();
    return kind == 3 ? Floatland::sidebarCapacity(box()) : (m ? std::max(1, std::min(9, static_cast<int>((m->m_size.x-64)/tabStep()))) : 1);
}
// Snapshot while the window still belongs to a visible workspace. Hidden
// windows cannot be captured by Hyprland's makeSnapshotFB.
static Preview snapshot(PHLWINDOW w) {
    auto m=w->m_monitor.lock();
    if (!m || m->m_transform!=WL_OUTPUT_TRANSFORM_NORMAL) return {};
    auto r=w->getFullWindowBoundingBox();
    const double x=std::clamp(r.x-m->m_position.x,0.0,m->m_size.x);
    const double y=std::clamp(r.y-m->m_position.y,0.0,m->m_size.y);
    const double right=std::clamp(r.x+r.w-m->m_position.x,0.0,m->m_size.x);
    const double bottom=std::clamp(r.y+r.h-m->m_position.y,0.0,m->m_size.y);
    if (right<=x || bottom<=y) return {};
    struct CaptureGuard {
        bool previous=capturing;
        CaptureGuard() { capturing=true; }
        ~CaptureGuard() { capturing=previous; }
    } guard;
    auto frame=g_pHyprRenderer->makeSnapshotFB(w);
    if (!frame) warning("Window snapshot unavailable; using icon fallback");
    return {frame,{x,y,right-x,bottom-y},m->m_size,
            {x+m->m_position.x,y+m->m_position.y,right-x,bottom-y}};
}
static int rememberPreview(lua_State* L) {
    auto w=find(luaL_checkstring(L,1),luaL_checkinteger(L,2));
    const bool remember=lua_toboolean(L,3);
    prunePreviews();
    std::erase_if(savedPreviews,[&](const auto& entry) { return entry.window.lock()==w; });
    if (!remember || !w || !w->m_workspace || w->m_workspace->m_name.starts_with("special:") ||
        g_pSessionLockManager->isSessionLocked()) return 0;
    auto m=w->m_monitor.lock();
    if (!m) return 0;
    const double cost=m->m_pixelSize.x*m->m_pixelSize.y;
    if (cost>previewBudget) return 0;
    double used=cost;
    for (const auto& entry:savedPreviews) used+=entry.pixels;
    while (used>previewBudget && !savedPreviews.empty()) {
        used-=savedPreviews.front().pixels; savedPreviews.erase(savedPreviews.begin());
    }
    auto preview=snapshot(w);
    if (preview.fb) savedPreviews.push_back({w,preview,cost});
    return 0;
}
static void capture() {
    previews.clear(); previews.resize(windows.size());
    if (kind!=3) return;
    prunePreviews();
    double pixelsUsed=0;
    for (const auto& entry:savedPreviews) pixelsUsed+=entry.pixels;
    for (int i=first;i<std::min(static_cast<int>(windows.size()),first+rowCapacity());++i) {
        auto w=windows[i].lock();
        if (!w || !w->m_workspace) continue;
        if (w->m_workspace->m_name.starts_with("special:")) {
            for (const auto& entry:savedPreviews)
                if (entry.window.lock()==w) { previews[i]=entry.preview; break; }
            continue;
        }
        auto m=w->m_monitor.lock();
        if (!m) continue;
        const double cost=m->m_pixelSize.x*m->m_pixelSize.y;
        if (pixelsUsed+cost>previewBudget) continue;
        previews[i]=snapshot(w);
        if (previews[i].fb) pixelsUsed+=cost;
    }
}
// One snapshot per event-loop IPC turn. A cancelled generation cannot publish
// an old scene, and repeated Win+G never builds duplicate scenes.
static int prepareOverview(lua_State* L) {
    const auto token=static_cast<uint64_t>(luaL_checkinteger(L,1));
    if (kind!=3 || !flow.accepts(token)) return 0;
    if (!contextValid()) { hide(); emit("cancel"); return 0; }
    if (prepareIndex<windows.size()) {
        const size_t i=prepareIndex++;
        auto w=windows[i].lock();
        if (w && w->m_isMapped && w->m_workspace) {
            if (w->m_workspace->m_name=="special:floatland-minimized") {
                for (const auto& entry:savedPreviews)
                    if (entry.window.lock()==w) { previews[i]=entry.preview; break; }
            } else if (auto m=w->m_monitor.lock()) {
                const double cost=m->m_pixelSize.x*m->m_pixelSize.y;
                if (preparePixels+cost<=previewBudget) {
                    previews[i]=snapshot(w);
                    if (previews[i].fb) preparePixels+=cost;
                }
            }
        }
        emit(std::format("prepare,{}",token));
        return 0;
    }
    for(size_t i=0;i<windows.size();++i) if (auto w=windows[i].lock()) {
        if (w->m_workspace && !w->m_workspace->m_isSpecialWorkspace && previews[i].fb) {
            const auto box=w->getFullWindowBoundingBox();
            previews[i].origin={box.x,box.y,box.w,box.h};
        }
    }
    arrange(); flow.ready(token,clockSeconds()); closing=false; overview=true;
    pointerSelection=false; hoveredTask=-1; texture.reset(); damage();
    return 0;
}
static int selectionValid(lua_State* L) {
    const auto token=static_cast<uint64_t>(luaL_checkinteger(L,1));
    lua_pushboolean(L,kind==3 && token==flow.generation &&
        flow.stage==Floatland::OverviewFlow::Stage::Selecting && contextValid() &&
        !g_pSessionLockManager->isSessionLocked() && !chosen.expired());
    return 1;
}
static int finishSelection(lua_State* L) {
    const auto token=static_cast<uint64_t>(luaL_checkinteger(L,1));
    const bool success=lua_toboolean(L,2);
    if (kind!=3 || token!=flow.generation || flow.stage!=Floatland::OverviewFlow::Stage::Selecting) return 0;
    if (!success || !contextValid()) { hide(); return 0; }
    if (auto w=chosen.lock()) {
        for(size_t i=0;i<windows.size();++i) if(windows[i].lock()==w) {
            const auto box=w->getFullWindowBoundingBox();
            previews[i].origin={box.x,box.y,box.w,box.h};
        }
    }
    flow.close(clockSeconds()); closing=true; overview=false; damage();
    return 0;
}
// Change visibility before Hyprland builds the frame, never halfway through
// drawing a frame whose ordinary windows have already been filtered out.
static void prepareFrame(PHLMONITOR m) {
    if (capturing) return;
    prunePreviews();
    if (kind && (!contextValid() || std::any_of(windows.begin(),windows.end(),[](const auto& ref) {
        const auto w=ref.lock();
        return !w || !w->m_isMapped || !w->m_workspace ||
            (!w->m_pinned && w->m_workspace->m_id!=workspaceId &&
             w->m_workspace->m_name!="special:floatland-minimized");
    }))) { hide(); emit("cancel"); return; }
    if (kind==3 && monitor.lock()==m) {
        if (flow.selectionExpired(clockSeconds())) { warning("Overview selection timed out; cancelling selection"); hide(); emit("cancel"); return; }
        if (flow.finishFrame(clockSeconds())) hide();
    } else if (kind && monitor.lock()==m && closing && progress()<=0) hide();
}
static int show(lua_State* L) {
    const int next = luaL_checkinteger(L, 1);
    luaL_checktype(L, 2, LUA_TTABLE);
    const int index = luaL_checkinteger(L, 3);
    damage();
    if ((next==3 && !Floatland::Style::overviewEnabled) || (next==1 && !Floatland::Style::switchingEnabled)) { hide(); return 0; }
    if (next < 0 || next > 3) return luaL_error(L, "invalid task UI mode");
    if (next==0 && kind) { dismiss(); return 0; }
    if (next==3 && kind==3) { toggleOverview(); return 0; }
    if (next && (g_pSessionLockManager->isSessionLocked() || g_pInputManager->isConstrained() ||
                 g_layoutManager->dragController()->target())) {
        hide(); emit("cancel"); return 0;
    }
    const bool opening=kind!=next || closing;
    if (kind == 0 || next != kind) {
        const auto p = g_pInputManager->getMouseCoordsInternal();
        monitor = State::monitorState()->query().vec(p).run();
    }
    const auto m=monitor.lock();
    if (next && (!m || !m->m_activeWorkspace || m->m_activeSpecialWorkspace)) {
        hide(); emit("cancel"); return 0;
    }
    if (m && m->m_activeWorkspace) workspaceId=m->m_activeWorkspace->m_id;
    const auto previousWindows=windows;
    const int previousFirst=first;
    windows.clear(); icons.clear();
    for (size_t i = 1; i <= lua_rawlen(L, 2); ++i) {
        lua_rawgeti(L, 2, i);
        lua_getfield(L, -1, "address"); const std::string address = luaL_checkstring(L, -1); lua_pop(L, 1);
        lua_getfield(L, -1, "pid"); const int pid = luaL_checkinteger(L, -1); lua_pop(L, 1);
        lua_getfield(L, -1, "icon");
        const char* icon = lua_tostring(L, -1);
        const std::string path = icon ? icon : ""; lua_pop(L, 1);
        if (auto w = find(address, pid)) { windows.push_back(w); icons.push_back(path); }
        lua_pop(L, 1);
    }
    if (next!=3) flow.reset();
    chosen.reset();
    kind = next; closing=false;
    pending = kind == 1; overview = kind == 3;
    selected = windows.empty() ? 0 : std::clamp(index, 0, static_cast<int>(windows.size()) - 1);
    if(kind==1) layoutTabs();
    else first = std::max(0, selected - rowCapacity() + 1);
    if (kind==3) {
        const auto token=flow.prepare(); overview=false;
        prunePreviews(); previews.clear(); previews.resize(windows.size()); cards.clear();
        prepareIndex=0; preparePixels=0;
        for (const auto& entry:savedPreviews) preparePixels+=entry.pixels;
        emit(std::format("prepare,{}",token));
    } else if(kind==1) {
        bool changed=previousWindows.size()!=windows.size();
        if(!changed) for(size_t i=0;i<windows.size();++i)
            if(previousWindows[i].lock()!=windows[i].lock()) { changed=true; break; }
        (void)changed; (void)previousFirst;
        cards.clear();
    } else { capture(); arrange(); }
    pointerSelection=false; hoveredTask=-1; if (opening) transitionStart=std::chrono::steady_clock::now(); texture.reset(); textureKey.clear(); damage();
    if(kind==3) { const auto p=g_pInputManager->getMouseCoordsInternal(); pointerMove({p.x,p.y}); }
    return 0;
}
static int overviewState(lua_State* L) {
    overview = lua_toboolean(L, 1);
    if (!overview && (kind == 2 || kind == 3)) dismiss();
    return 0;
}
static int raiseWindow(lua_State* L) {
    auto w = find(luaL_checkstring(L, 1), luaL_checkinteger(L, 2));
    if (w) Desktop::windowState()->raise(w);
    return 0;
}
static Floatland::Rect box() {
    auto m = monitor.lock();
    if (!m) return {};
    if(kind==1) return tabLayout.panel;
    if (kind == 3) {
        const auto area=m->m_reservedArea.apply(CBox{m->m_position,m->m_size});
        return Floatland::sidebarPanel({area.x,area.y,area.w,area.h});
    }
    const int count=std::max(1,std::min(static_cast<int>(windows.size()),rowCapacity()));
    const double width=std::min(m->m_size.x-16,24.0+tabStep()*count), height=tabHeight();
    return {m->m_position.x+(m->m_size.x-width)/2,m->m_position.y+(m->m_size.y-height)/2,width,height};
}
static Floatland::Rect tile(int i) {
    const auto b=box(); const int j=i-first;
    if(kind==1) return j>=0 && j<static_cast<int>(tabLayout.cells.size())?tabLayout.cells[j]:Floatland::Rect{};
    if (kind != 3) return {b.x+12+j*tabStep(),b.y+12,tabStep()-4,tabHeight()-24};
    return Floatland::sidebarCard(b,j);
}
static void arrange() { cards.clear(); }
static bool isMinimized(int i) {
    auto w=windows[i].lock();
    return w && w->m_workspace && w->m_workspace->m_name=="special:floatland-minimized";
}
static Floatland::Rect visibleRect(int i) {
    if(kind!=3 || i>=static_cast<int>(previews.size()) || !previews[i].fb) return tile(i);
    const auto& p=previews[i];
    return Floatland::overviewPreview(tile(i),{p.source.w,p.source.h});
}
static int indexAt(Floatland::Point p) {
    // Later previews are painted on top while the entrance animation overlaps.
    for(int i=std::min(static_cast<int>(windows.size()),first+rowCapacity())-1;i>=first;--i)
        if(windows[i].lock() && visibleRect(i).contains(p)) return i;
    return -1;
}
static PHLWINDOW at(Floatland::Point p) {
    const int i=indexAt(p); return i<0?nullptr:windows[i].lock();
}
static void pointerMove(Floatland::Point p) {
    if((kind!=3 && !(kind==1 && Floatland::Style::tab_mouse)) || !presenting() || closing || capturing || g_pSessionLockManager->isSessionLocked()) return;
    const bool changedMode=!pointerSelection;
    const int next=indexAt(p); pointerSelection=true;
    if(changedMode || next!=hoveredTask) { hoveredTask=next; if(next>=0) selected=next; texture.reset(); damage(); }
}
static bool button(IPointer::SButtonEvent e, Event::SCallbackInfo& info) {
    // Balance every consumed press, including right/middle clicks and presses
    // during the exit animation. A release must never leak to a client.
    if (e.state==WL_POINTER_BUTTON_STATE_RELEASED) {
        if (!swallowedButtons.erase(e.button)) return false;
        info.cancelled=true;
        if (e.button==272) {
            const auto w=pressed.lock(); pressed.reset(); mouseOwned=false;
            const auto p=g_pInputManager->getMouseCoordsInternal();
            if (!closing && kind && contextValid() && !g_pSessionLockManager->isSessionLocked() &&
                w && w->m_isMapped && at({p.x,p.y})==w) {
                choose(w); pending=false;
            }
        }
        return true;
    }
    if (info.cancelled || g_pSessionLockManager->isSessionLocked() || g_pInputManager->isConstrained()) return false;
    if(kind==1 && !Floatland::Style::tab_mouse) return false;
    const auto p=g_pInputManager->getMouseCoordsInternal();
    if (closing || (kind && presenting() && contextValid() && (overview || box().contains({p.x,p.y})))) {
        swallowedButtons.insert(e.button); info.cancelled=true;
        if (e.button==272 && !closing) { mouseOwned=true; pressed=at({p.x,p.y}); }
        return true;
    }
    return false;
}
static void key(IKeyboard::SKeyEvent e, Event::SCallbackInfo& info) {
    if (e.state == WL_KEYBOARD_KEY_STATE_RELEASED) {
        if (swallowed.erase(e.keycode)) info.cancelled = true;
        // Alt press was delivered to the client, so its release must pass through.
        if ((e.keycode == 56 || e.keycode == 100) && pending) {
            pending = false;
            if(kind==1 && pointerSelection && !closing && contextValid() && selected>=0 && selected<static_cast<int>(windows.size())) {
                if(auto w=windows[selected].lock()) choose(w);
                else { dismiss(); emit("cancel"); }
            } else { dismiss(); emit("commit"); }
        }
        return;
    }
    if (info.cancelled || g_pSessionLockManager->isSessionLocked() || g_pInputManager->isConstrained()) return;
    const auto mods = g_pInputManager->getModsFromAllKBs();
    const bool overviewKey=Floatland::Style::bindingsEnabled && Floatland::Style::overviewEnabled && e.keycode==static_cast<uint32_t>(Floatland::Style::overviewKey) && (mods & HL_MODIFIER_META) && !(mods & (HL_MODIFIER_CTRL|HL_MODIFIER_ALT|HL_MODIFIER_SHIFT));
    if (overviewKey && swallowed.contains(e.keycode)) { info.cancelled=true; return; }
    if (overviewKey && kind==3) {
        // Ignore autorepeat, but every new press can reverse the animation.
        if (!swallowed.contains(e.keycode)) toggleOverview();
        swallowed.insert(e.keycode); info.cancelled=true; return;
    }
    if (e.keycode==1 && kind==3) { dismiss(); swallowed.insert(e.keycode); info.cancelled=true; return; }
    if (closing && e.keycode!=static_cast<uint32_t>(Floatland::Style::altTabKey)) { swallowed.insert(e.keycode); info.cancelled=true; return; }
    std::string action;
    if (Floatland::Style::bindingsEnabled && Floatland::Style::switchingEnabled && e.keycode == static_cast<uint32_t>(Floatland::Style::altTabKey) && (mods & HL_MODIFIER_ALT) && !(mods & (HL_MODIFIER_CTRL | HL_MODIFIER_META))) {
        pending = true;
        if(kind==1 && pointerSelection && selected>=0 && selected<static_cast<int>(windows.size())) {
            if(auto w=windows[selected].lock())
                action=std::format("step,0x{:x},{},{}",reinterpret_cast<uintptr_t>(w.get()),w->getPID(),(mods & HL_MODIFIER_SHIFT)?1:0);
        }
        pointerSelection=false; hoveredTask=-1;
        if(action.empty()) action = (mods & HL_MODIFIER_SHIFT) ? "previous" : "next";
    } else if (overviewKey) {
        pending = false; action = "overview";
    } else if (e.keycode == 1 && pending) {
        pending = false; dismiss(); action = "cancel";
    } else if (e.keycode == 1 && overview) {
        action = "overview";
    }
    if (overview && action.empty()) {
        if (e.keycode == 28 && !windows.empty()) {
            if (auto w=windows[selected].lock()) choose(w);
        } else if ((e.keycode==105 || e.keycode==106 || e.keycode==103 || e.keycode==108) && !windows.empty()) {
            pointerSelection=false; hoveredTask=-1;
            const int delta=(e.keycode==105 || e.keycode==103) ? -1 : 1;
            selected=(selected+delta+static_cast<int>(windows.size()))%static_cast<int>(windows.size());
            const int page=selected/rowCapacity()*rowCapacity();
            if (page!=first) { first=page; texture.reset(); }
            texture.reset(); damage();
        }
        swallowed.insert(e.keycode); info.cancelled=true; return;
    }
    if (!action.empty()) { swallowed.insert(e.keycode); info.cancelled = true; emit(action); }
}
static void text(cairo_t* cr, const std::string& label, double x, double y, double width) {
    auto layout = pango_cairo_create_layout(cr);
    auto font = pango_font_description_from_string("Sans");
    pango_font_description_set_absolute_size(font,(kind==1?Floatland::Style::fontSize:13)*PANGO_SCALE);
    pango_layout_set_font_description(layout, font);
    pango_layout_set_text(layout, label.c_str(), -1);
    pango_layout_set_single_paragraph_mode(layout, true);
    pango_layout_set_width(layout, static_cast<int>(width * PANGO_SCALE));
    pango_layout_set_ellipsize(layout, PANGO_ELLIPSIZE_END);
    cairo_move_to(cr,x,y); pango_cairo_show_layout(cr,layout);
    pango_font_description_free(font); g_object_unref(layout);
}
static void rounded(cairo_t* cr,double x,double y,double w,double h,double r) {
    r=std::min(r,std::min(w,h)/2); const double pi=std::acos(-1);
    cairo_new_sub_path(cr); cairo_arc(cr,x+w-r,y+r,r,-pi/2,0); cairo_arc(cr,x+w-r,y+h-r,r,0,pi/2);
    cairo_arc(cr,x+r,y+h-r,r,pi/2,pi); cairo_arc(cr,x+r,y+r,r,pi,pi*1.5); cairo_close_path(cr);
}
static void icon(cairo_t* cr,const std::string& path,double x,double y,double size) {
    bool drawn=false; cairo_save(cr);
    if (path.ends_with(".svg")) {
        GError* error=nullptr; auto svg=rsvg_handle_new_from_file(path.c_str(),&error);
        if (svg) { RsvgRectangle rect{x,y,size,size}; drawn=rsvg_handle_render_document(svg,cr,&rect,&error); g_object_unref(svg); }
        if (error) g_error_free(error);
    } else if (path.ends_with(".png")) {
        auto surface=cairo_image_surface_create_from_png(path.c_str());
        if (cairo_surface_status(surface)==CAIRO_STATUS_SUCCESS) {
            const int w=cairo_image_surface_get_width(surface),h=cairo_image_surface_get_height(surface);
            const double scale=size/std::max(w,h);
            cairo_translate(cr,x+(size-w*scale)/2,y+(size-h*scale)/2); cairo_scale(cr,scale,scale);
            cairo_set_source_surface(cr,surface,0,0); cairo_paint(cr); drawn=true;
        }
        cairo_surface_destroy(surface);
    }
    cairo_restore(cr);
    if (!drawn) {
        // Resolution-independent fallback; no font glyph or downloaded artwork.
        cairo_set_source_rgb(cr,.25,.48,.78); rounded(cr,x,y,size,size,size*.22); cairo_fill(cr);
        cairo_set_source_rgba(cr,1,1,1,.9); cairo_set_line_width(cr,size*.045);
        rounded(cr,x+size*.2,y+size*.24,size*.6,size*.52,size*.04); cairo_stroke(cr);
        cairo_move_to(cr,x+size*.2,y+size*.37); cairo_line_to(cr,x+size*.8,y+size*.37); cairo_stroke(cr);
    }
}
class Pass : public IPassElement {
  public:
    std::vector<UP<IPassElement>> draw() override {
        auto m=monitor.lock();
        if (!presenting() || capturing || g_pSessionLockManager->isSessionLocked() || !kind || !m || g_pHyprRenderer->m_renderData.pMonitor.lock()!=m) return {};
        if(kind==3 && pointerSelection) { const auto p=g_pInputManager->getMouseCoordsInternal(); pointerMove({p.x,p.y}); }
        const double phase=progress();
        // Keep the final preview frame until prepareFrame restores normal windows.
        if (closing || phase<1) damage();
        const auto b=box(); const auto px=Floatland::pixels(b,{m->m_position.x,m->m_position.y},m->m_scale);
        std::string cache=std::format("{}:{}:{}:{}:{}",kind,selected,first,px.w,px.h);
        for (const auto& ref:windows) if (auto w=ref.lock()) cache+=w->m_title;
        if (!texture || cache!=textureKey) {
            auto surface=cairo_image_surface_create(CAIRO_FORMAT_ARGB32,static_cast<int>(px.w),static_cast<int>(px.h));
            auto cr=cairo_create(surface); cairo_scale(cr,px.w/b.w,px.h/b.h);
            if (kind!=3) {
                const auto& color=Floatland::Style::tab;
                cairo_set_source_rgba(cr,color[0],color[1],color[2],Floatland::Style::tabOpacity);
                rounded(cr,0,0,b.w,b.h,24); cairo_fill(cr);
            }
            if (kind==3) {
                cairo_set_source_rgb(cr,.9,.92,1);
                if (windows.empty()) text(cr,"No windows",20,20,b.w-40);
            }
            for (int i=first;i<std::min(static_cast<int>(windows.size()),first+rowCapacity());++i) {
                auto t=tile(i); t.x-=b.x; t.y-=b.y;
                if (i==selected && (kind!=3 || (!previews[i].fb && (!pointerSelection || hoveredTask==i)))) {
                    cairo_set_source_rgba(cr,.46,.58,.94,kind==3?.85:.3);
                    rounded(cr,t.x-3,t.y-3,t.w+6,t.h+6,kind==3?10:18);
                    if (kind==3) { cairo_set_line_width(cr,2); cairo_stroke(cr); } else cairo_fill(cr);
                }
                auto w=windows[i].lock(); const bool minimized=w && w->m_workspace && w->m_workspace->m_name=="special:floatland-minimized";
                const bool preview=(kind==3 || tabPreview()) && i<static_cast<int>(previews.size()) && previews[i].fb;
                if(kind==1 && tabPreview()) {
                    icon(cr,icons[i],t.x+6,t.y+4,18);
                    cairo_set_source_rgb(cr,.95,.96,1);
                    if(i==selected) text(cr,w?w->m_title:"Closed",t.x+30,t.y+4,t.w-36);
                }
                if (!preview) { const double size=std::max(1.0,std::min({kind==3?80.0:static_cast<double>(Floatland::Style::iconSize),t.w-16,t.h-((kind==1 && !tabLegacy())?16:Floatland::Style::fontSize+12)})); icon(cr,icons[i],t.x+(t.w-size)/2,t.y+(t.h-((kind==1 && !tabLegacy())?0:28)-size)/2,size); }
                cairo_set_source_rgb(cr,.95,.96,1);
                if(((kind==3 && i==selected && (!pointerSelection || hoveredTask==i)) || (kind!=3 && (kind!=1 || tabLegacy()))) && t.w>32 && t.h>48) text(cr,w?(minimized?"↓ ":"")+w->m_title:"Closed",t.x+8,t.y+t.h-(kind==1?Floatland::Style::fontSize+8:25),t.w-16);
            }
            if(kind==1 && !tabLegacy() && !windows.empty()) {
                const auto w=windows[selected].lock();
                cairo_set_source_rgb(cr,.95,.96,1);
                text(cr,w?w->m_title:"Closed",16,b.h-Floatland::Style::fontSize-14,b.w-32);
            }
            cairo_surface_flush(surface); texture=g_pHyprRenderer->createTexture(surface);
            texture->m_imageDescription=NColorManagement::getDefaultImageDescription();
            cairo_destroy(cr); cairo_surface_destroy(surface); textureKey=cache;
        }
        if (kind==3 && phase>0) {
            Render::GL::CHyprOpenGLImpl::SRectRenderData background{};
            background.round=static_cast<int>(16*m->m_scale);
            background.blur=Floatland::Style::overviewBlur; background.blurA=phase;
            Render::GL::g_pHyprOpenGL->renderRect(CBox{px.x,px.y,px.w,px.h},CHyprColor(Floatland::Style::overviewColor[0],Floatland::Style::overviewColor[1],Floatland::Style::overviewColor[2],Floatland::Style::overviewOpacity*phase),background);
        }
        Render::GL::CHyprOpenGLImpl::STextureRenderData data{}; data.allowDim=false; data.a=phase;
        Render::GL::g_pHyprOpenGL->renderTexture(texture,CBox{px.x,px.y,px.w,px.h},data);
        std::vector<int> drawOrder;
        if (kind==3 || tabPreview()) {
            for (int i=first;i<std::min(static_cast<int>(windows.size()),first+rowCapacity());++i)
                if (windows[i].lock()!=chosen.lock()) drawOrder.push_back(i);
            if (chosen.lock()) for (int i=first;i<std::min(static_cast<int>(windows.size()),first+rowCapacity());++i)
                if (windows[i].lock()==chosen.lock()) drawOrder.push_back(i);
        }
        for (const int i:drawOrder) {
            if (i>=static_cast<int>(previews.size()) || !previews[i].fb || !windows[i].lock()) continue;
            const auto& p=previews[i];
            const auto animated=tabPreview()?Floatland::switcherPreview(tile(i),{p.source.w,p.source.h},Floatland::Style::fontSize):visibleRect(i);
            const auto d=Floatland::pixels(animated,{m->m_position.x,m->m_position.y},m->m_scale);
            if(i==selected && (!pointerSelection || hoveredTask==i)) {
                Render::GL::CHyprOpenGLImpl::SRectRenderData frame{}; frame.round=static_cast<int>(10*m->m_scale);
                const double border=2*m->m_scale;
                Render::GL::g_pHyprOpenGL->renderRect(CBox{d.x-border,d.y-border,d.w+2*border,d.h+2*border},CHyprColor(.46,.65,1.,.9*phase),frame);
            }
            data.a=phase; data.allowCustomUV=true;
            data.primarySurfaceUVTopLeft={p.source.x/p.monitorSize.x,p.source.y/p.monitorSize.y};
            data.primarySurfaceUVBottomRight={(p.source.x+p.source.w)/p.monitorSize.x,(p.source.y+p.source.h)/p.monitorSize.y};
            Render::GL::g_pHyprOpenGL->renderTexture(p.fb->getTexture(),CBox{d.x,d.y,d.w,d.h},data);
        }
        return {};
    }
    bool needsLiveBlur() override {
        const auto m=monitor.lock();
        return Floatland::Style::overviewBlur && kind==3 && presenting() && !capturing && m && g_pHyprRenderer->m_renderData.pMonitor.lock()==m;
    }
    std::optional<CBox> boundingBox() override {
        // Hyprland's render-pass requires logical monitor-local bounds for live
        // blur. Include the whole screen: the backdrop and animated previews
        // extend beyond the final card rectangles.
        const auto m=g_pHyprRenderer->m_renderData.pMonitor.lock();
        if (!m) return std::nullopt;
        const auto panel=box();
        return CBox{panel.x-m->m_position.x,panel.y-m->m_position.y,panel.w,panel.h};
    }
    bool needsPrecomputeBlur() override { return false; }
    const char* passName() override { return "FloatlandTaskPass"; }
    ePassElementType type() override { return EK_CUSTOM; }
};
static void scroll(IPointer::SAxisEvent e, Event::SCallbackInfo& info) {
    if (closing || kind!=3 || !presenting() || windows.empty() || g_pSessionLockManager->isSessionLocked()) return;
    // All windows are visible; scrolling changes selection, never pages.
    pointerSelection=false; hoveredTask=-1;
    selected=(selected+(e.delta>0?1:-1)+static_cast<int>(windows.size()))%static_cast<int>(windows.size());
    if(selected<first) first=selected;
    if(selected>=first+rowCapacity()) first=selected-rowCapacity()+1;
    texture.reset(); damage(); info.cancelled=true;
}
static void reset() { hide(); savedPreviews.clear(); overview = pending = mouseOwned = false; windows.clear(); swallowed.clear(); swallowedButtons.clear(); pressed.reset(); monitor.reset(); }
}
