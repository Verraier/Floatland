#pragma once
#include <unordered_set>
// This menu uses the existing render pass; it never opens a nested GL render scope.
namespace WindowMenu {
static PHLWINDOWREF owner;
static PHLMONITORREF monitor;
static Floatland::Rect rect;
static int hovered=-1, pressed=-1;
static std::unordered_set<uint32_t> swallowed;
static SP<Render::ITexture> texture;
static std::string cache;
static void damage();
struct Row { std::string label,action,address; int pid=0; bool check=false,checked=false; };
static std::vector<Row> pageRows;
static int page=0;
static bool custom=false;
static int capacity() { auto m=monitor.lock(); return m?std::max(1,std::min(10,static_cast<int>((m->m_size.y-100)/32))):6; }
static int count() { return custom?std::min(capacity(),static_cast<int>(pageRows.size())):6; }
static Row rowAt(int i) {
    const int index=page+i;
    return custom && index>=0 && index<static_cast<int>(pageRows.size())?pageRows[index]:Row{};
}
static void layout() {
    if(auto m=monitor.lock()) {
        rect.w=std::min(custom?420.:240.,m->m_size.x); rect.h=count()*32+16+(custom?0:12);
        rect.x=std::clamp(rect.x,m->m_position.x,m->m_position.x+std::max(0.0,m->m_size.x-rect.w));
        rect.y=std::clamp(rect.y,m->m_position.y,m->m_position.y+std::max(0.0,m->m_size.y-rect.h));
    }
    cache.clear(); hovered=pressed=-1; damage();
}
static bool escapeHeld=false;
static std::unordered_set<uint32_t> shortcutHeld;
static void damage() { if(auto m=monitor.lock()) g_pHyprRenderer->damageMonitor(m); }
static void hide() { damage(); owner.reset(); monitor.reset(); texture.reset(); cache.clear(); hovered=pressed=-1; }
static bool valid() {
    const auto w=owner.lock(); const auto m=monitor.lock();
    return w && m && w->m_isMapped && !w->isHidden() && !g_pSessionLockManager->isSessionLocked() &&
        w->m_workspace && (w->m_pinned || w->m_workspace==m->m_activeWorkspace) && !m->m_activeSpecialWorkspace;
}
static int at(Floatland::Point p) {
    if(!rect.contains(p)) return -1;
    double y=p.y-rect.y-8;
    if(y<0 || (!custom && y>=96 && y<108)) return -1;
    if(!custom && y>=108) y-=12;
    const int row=static_cast<int>(y/32);
    return row>=0 && row<count()?row:-1;
}
static void show(PHLWINDOW w, Floatland::Point p) {
    hide(); if(!w) return;
    owner=w; monitor=w->m_monitor;
    custom=false; pageRows.clear(); page=0; rect.x=p.x; rect.y=p.y; layout();
}
static int pageLua(lua_State* L) {
    luaL_checktype(L,1,LUA_TTABLE);
    std::vector<Row> rows;
    for(size_t i=1;i<=lua_rawlen(L,1);++i) {
        lua_rawgeti(L,1,i); luaL_checktype(L,-1,LUA_TTABLE);
        auto string=[&](const char* key) { lua_getfield(L,-1,key); std::string value=luaL_checkstring(L,-1); lua_pop(L,1); return value; };
        Row row; row.label=string("label"); row.action=string("action"); row.address=string("address");
        lua_getfield(L,-1,"pid"); row.pid=luaL_checkinteger(L,-1); lua_pop(L,1);
        lua_getfield(L,-1,"check"); row.check=lua_toboolean(L,-1); lua_pop(L,1);
        lua_getfield(L,-1,"checked"); row.checked=lua_toboolean(L,-1); lua_pop(L,1);
        lua_pop(L,1); rows.push_back(std::move(row));
    }
    if(!valid()) {
        const auto p=g_pInputManager->getMouseCoordsInternal();
        show(Desktop::focusState()->window(),{p.x,p.y});
    }
    if(!valid()) return luaL_error(L,"Focus a visible window before opening settings");
    if(!custom) page=0;
    custom=true; pageRows=std::move(rows); page=std::clamp(page,0,std::max(0,static_cast<int>(pageRows.size())-capacity())); layout(); return 0;
}
static void pointer(Floatland::Point p) {
    if(!valid()) { if(monitor.lock()) hide(); return; }
    const int next=at(p); if(next!=hovered) { hovered=next; damage(); }
}
static bool button(IPointer::SButtonEvent e, Event::SCallbackInfo& info) {
    if(e.state==WL_POINTER_BUTTON_STATE_RELEASED) {
        if(!swallowed.erase(e.button)) return false;
        info.cancelled=true;
        const auto w=owner.lock(); const auto p=g_pInputManager->getMouseCoordsInternal();
        const int row=at({p.x,p.y});
        if(e.button==272 && valid() && row>=0 && row==pressed) {
            static const char* names[]={"close","minimize","fullscreen","pin-above","pin","settings"};
            const auto item=custom?rowAt(row):Row{};
            if(custom && item.action.empty()) { pressed=-1; return true; }
            const auto command=custom?item.action:std::string(names[row]);
            const auto target=custom && !item.address.empty()?item.address:std::format("0x{:x}",reinterpret_cast<uintptr_t>(w.get()));
            const int pid=custom && item.pid?item.pid:w->getPID();
            const auto payload=std::format("1,{},{},{},",command,target,pid);
            if(!custom && command!="settings") hide(); else pressed=-1;
            g_pEventManager->postEvent({"floatland_bars",payload});
        } else hide();
        return true;
    }
    if(!valid()) return false;
    swallowed.insert(e.button); info.cancelled=true;
    const auto p=g_pInputManager->getMouseCoordsInternal(); pressed=at({p.x,p.y});
    if(pressed<0) hide();
    return true;
}
static bool scroll(IPointer::SAxisEvent e, Event::SCallbackInfo& info) {
    if(!valid()) return false;
    info.cancelled=true;
    if(custom && e.delta!=0) {
        page=std::clamp(page+(e.delta>0?1:-1),0,std::max(0,static_cast<int>(pageRows.size())-capacity()));
        layout();
    }
    return true;
}
static bool key(IKeyboard::SKeyEvent e, Event::SCallbackInfo& info) {
    if(e.state==WL_KEYBOARD_KEY_STATE_RELEASED && shortcutHeld.erase(e.keycode)) { info.cancelled=true; return true; }
    if(shortcutHeld.contains(e.keycode)) { info.cancelled=true; return true; }
    const auto mods=g_pInputManager->getModsFromAllKBs();
    if(e.state==WL_KEYBOARD_KEY_STATE_PRESSED && Floatland::Style::bindingsEnabled && e.keycode==static_cast<uint32_t>(Floatland::Style::menuKey) &&
       (mods & HL_MODIFIER_META) && !(mods & (HL_MODIFIER_CTRL|HL_MODIFIER_ALT|HL_MODIFIER_SHIFT)) &&
       !g_pSessionLockManager->isSessionLocked() && !TaskUI::kind) {
        const auto w=Desktop::focusState()->window();
        if(w) {
            const auto p=g_pInputManager->getMouseCoordsInternal();
            show(w,{p.x,p.y}); shortcutHeld.insert(e.keycode); info.cancelled=true; return true;
        }
    }
    if(e.keycode!=1) return false;
    if(e.state==WL_KEYBOARD_KEY_STATE_RELEASED && escapeHeld) { escapeHeld=false; info.cancelled=true; return true; }
    if(e.state==WL_KEYBOARD_KEY_STATE_PRESSED && valid()) { escapeHeld=true; hide(); info.cancelled=true; return true; }
    return false;
}
class Pass : public IPassElement {
 public:
    std::vector<UP<IPassElement>> draw() override {
        const auto m=monitor.lock(); if(!valid() || !m || g_pHyprRenderer->m_renderData.pMonitor.lock()!=m) return {};
        const auto w=owner.lock();
        const auto px=Floatland::pixels(rect,{m->m_position.x,m->m_position.y},m->m_scale);
        const auto key=std::format("{}:{}:{}:{}:{}:{}",px.w,px.h,hovered,isPictureInPicture(w),true,Floatland::Style::revision)+std::to_string(w->m_pinned);
        if(!texture || cache!=key) {
            auto surface=cairo_image_surface_create(CAIRO_FORMAT_ARGB32,static_cast<int>(px.w),static_cast<int>(px.h));
            auto cr=cairo_create(surface); cairo_scale(cr,px.w/rect.w,px.h/rect.h);
            const auto& c=Floatland::Style::menuColor;
            cairo_set_source_rgba(cr,c[0],c[1],c[2],Floatland::Style::menuOpacity); TaskUI::rounded(cr,0,0,rect.w,rect.h,12); cairo_fill(cr);
            const char* names[]={"Close","Minimize","Fullscreen","Always on top","All workspaces","Settings"};
            for(int i=0;i<count();++i) {
                const double y=8+i*32+(!custom && i>=3?12:0);
                if(i==hovered && (!custom || !rowAt(i).action.empty())) { cairo_set_source_rgba(cr,1,1,1,.12); TaskUI::rounded(cr,5,y,rect.w-10,32,6); cairo_fill(cr); }
                const bool disabled=custom && rowAt(i).action.empty();
                cairo_set_source_rgba(cr,.94,.95,.98,disabled?.5:1); TaskUI::text(cr,custom?rowAt(i).label:names[i],16,y+7,rect.w-52);
                if(custom?rowAt(i).check:(i>=3 && i<=4)) {
                    cairo_rectangle(cr,rect.w-30,y+10,12,12); cairo_set_line_width(cr,1.2); cairo_stroke(cr);
                    if(custom?rowAt(i).checked:(i==3?isPictureInPicture(w):w->m_pinned)) {
                        cairo_move_to(cr,rect.w-28,y+16); cairo_line_to(cr,rect.w-25,y+19); cairo_line_to(cr,rect.w-20,y+12); cairo_stroke(cr);
                    }
                }
            }
            if(custom && static_cast<int>(pageRows.size())>capacity()) {
                const double track=rect.h-16, thumb=track*capacity()/pageRows.size();
                const double offset=(track-thumb)*page/(pageRows.size()-capacity());
                cairo_set_source_rgba(cr,1,1,1,.28);
                TaskUI::rounded(cr,rect.w-7,8+offset,3,thumb,1.5); cairo_fill(cr);
            }
            if(!custom) { cairo_set_source_rgba(cr,1,1,1,.14); cairo_rectangle(cr,12,109,rect.w-24,1); cairo_fill(cr); }
            cairo_surface_flush(surface); texture=g_pHyprRenderer->createTexture(surface);
            texture->m_imageDescription=NColorManagement::getDefaultImageDescription();
            cairo_destroy(cr); cairo_surface_destroy(surface); cache=key;
        }
        Render::GL::CHyprOpenGLImpl::STextureRenderData data{}; data.a=1; data.allowDim=false;
        Render::GL::g_pHyprOpenGL->renderTexture(texture,CBox{px.x,px.y,px.w,px.h},data);
        return {};
    }
    std::optional<CBox> boundingBox() override {
        const auto m=monitor.lock(); if(!m) return std::nullopt;
        return CBox{rect.x-m->m_position.x,rect.y-m->m_position.y,rect.w,rect.h};
    }
    bool needsLiveBlur() override { return false; }
    bool needsPrecomputeBlur() override { return false; }
    const char* passName() override { return "FloatlandWindowMenuPass"; }
    ePassElementType type() override { return EK_CUSTOM; }
};
}
