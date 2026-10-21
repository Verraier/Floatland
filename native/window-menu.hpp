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
static bool escapeHeld=false;
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
    if(y<0 || (y>=96 && y<108)) return -1;
    if(y>=108) y-=12;
    const int row=static_cast<int>(y/32);
    return row>=0 && row<5?row:-1;
}
static void show(PHLWINDOW w, Floatland::Point p) {
    hide(); if(!w) return;
    owner=w; monitor=w->m_monitor;
    if(auto m=monitor.lock()) {
        rect={std::clamp(p.x,m->m_position.x,m->m_position.x+std::max(0.0,m->m_size.x-220)),
              std::clamp(p.y,m->m_position.y,m->m_position.y+std::max(0.0,m->m_size.y-188)),220,188};
        damage();
    }
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
            static const char* names[]={"close","minimize","fullscreen","pin-above","mini-mode"};
            const auto payload=std::format("1,{},0x{:x},{},",names[row],reinterpret_cast<uintptr_t>(w.get()),w->getPID());
            hide(); g_pEventManager->postEvent({"floatland_bars",payload});
        } else hide();
        return true;
    }
    if(!valid()) return false;
    swallowed.insert(e.button); info.cancelled=true;
    const auto p=g_pInputManager->getMouseCoordsInternal(); pressed=at({p.x,p.y});
    if(pressed<0) hide();
    return true;
}
static bool key(IKeyboard::SKeyEvent e, Event::SCallbackInfo& info) {
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
        const auto key=std::format("{}:{}:{}:{}:{}:{}",px.w,px.h,hovered,isPictureInPicture(w),isMiniMode(w),Floatland::Style::revision);
        if(!texture || cache!=key) {
            auto surface=cairo_image_surface_create(CAIRO_FORMAT_ARGB32,static_cast<int>(px.w),static_cast<int>(px.h));
            auto cr=cairo_create(surface); cairo_scale(cr,px.w/rect.w,px.h/rect.h);
            const auto& c=Floatland::Style::titlebar;
            cairo_set_source_rgba(cr,c[0],c[1],c[2],.97); TaskUI::rounded(cr,0,0,rect.w,rect.h,12); cairo_fill(cr);
            const char* names[]={"Close","Minimize","Fullscreen","Pin above","Mini-mode"};
            for(int i=0;i<5;++i) {
                const double y=8+i*32+(i>=3?12:0);
                if(i==hovered) { cairo_set_source_rgba(cr,1,1,1,.12); TaskUI::rounded(cr,5,y,210,32,6); cairo_fill(cr); }
                cairo_set_source_rgb(cr,.94,.95,.98); TaskUI::text(cr,names[i],16,y+7,160);
                if(i>=3) {
                    cairo_rectangle(cr,190,y+10,12,12); cairo_set_line_width(cr,1.2); cairo_stroke(cr);
                    if(i==3?isPictureInPicture(w):isMiniMode(w)) {
                        cairo_move_to(cr,192,y+16); cairo_line_to(cr,195,y+19); cairo_line_to(cr,200,y+12); cairo_stroke(cr);
                    }
                }
            }
            cairo_set_source_rgba(cr,1,1,1,.14); cairo_rectangle(cr,12,109,196,1); cairo_fill(cr);
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
