// Derived from the Hyprbars decoration/render-pass integration.
// See LICENSE.hyprbars and the project's NOTICE.md.
#include "titlebar.hpp"
#include "style.hpp"
#include "svg-controls.hpp"
#include "lifetime.hpp"
#include <hyprland/src/desktop/view/Window.hpp>
#include <hyprland/src/desktop/Workspace.hpp>
#include <hyprland/src/desktop/state/FocusState.hpp>
#include <hyprland/src/managers/fullscreen/FullscreenController.hpp>
#include <hyprland/src/render/Renderer.hpp>
#include <hyprland/src/render/OpenGL.hpp>
#include <hyprland/src/render/pass/PassElement.hpp>
#include <pango/pangocairo.h>
#include <algorithm>
#include <format>

using namespace Floatland;
using namespace Render::GL;

class FloatlandPass : public IPassElement {
  public:
    FloatlandPass(FloatlandBar* bar, float alpha) : m_bar(bar, bar->lifetime()), m_alpha(alpha) {}
    std::vector<UP<IPassElement>> draw() override {
        const auto bar=m_bar.get();
        if (!bar) return {};
        if (auto monitor = g_pHyprRenderer->m_renderData.pMonitor.lock())
            bar->paint(monitor, m_alpha);
        return {};
    }
    bool needsLiveBlur() override { return m_bar.get() && Style::mini_blur; }
    bool needsPrecomputeBlur() override { return false; }
    const char* passName() override { return "FloatlandTitlebarPass"; }
    ePassElementType type() override { return EK_CUSTOM; }
    std::optional<CBox> boundingBox() override {
        const auto bar=m_bar.get();
        if (!bar) return std::nullopt;
        auto monitor = g_pHyprRenderer->m_renderData.pMonitor.lock();
        if (!monitor) return std::nullopt;
        const auto box = bar->globalBox();
        return CBox{box.x-monitor->m_position.x, box.y-monitor->m_position.y, box.w, box.h};
    }
  private:
    Floatland::DeferredPtr<FloatlandBar> m_bar;
    float m_alpha;
};

FloatlandBar::FloatlandBar(PHLWINDOW window) : IHyprWindowDecoration(window), m_window(window) {
    m_visible = visible();
}
FloatlandBar::~FloatlandBar() { m_lifetime.reset(); forgetBar(this); }

bool FloatlandBar::visible() const {
    const auto w = owner();
    return Style::titlebarsEnabled && w && (mini() || w->m_class.find(".floatland-csd-")==std::string::npos) && w->m_isMapped && !w->isHidden() && w->m_isFloating && (!w->m_pinned || mini() || isPictureInPicture(w)) &&
        !w->m_group && !w->m_X11DoesntWantBorders && w->m_workspace &&
        !w->m_workspace->m_isSpecialWorkspace && (mini() || w->m_ruleApplicator->decorate().valueOrDefault()) &&
        Fullscreen::controller()->getFullscreenModes(w).internal == Fullscreen::FSMODE_NONE;
}

SDecorationPositioningInfo FloatlandBar::getPositioningInfo() {
    SDecorationPositioningInfo info;
    info.policy = DECORATION_POSITION_STICKY;
    info.edges = DECORATION_EDGE_TOP;
    info.priority = 5000;
    info.reserved = false;
    info.desiredExtents = {Vector2D{0.0, 0.0}, Vector2D{0.0, 0.0}};
    return info;
}
void FloatlandBar::onPositioningReply(const SDecorationPositioningReply& reply) {
    m_assigned = reply.assignedGeometry;
}
Rect FloatlandBar::globalBox() const {
    const auto w = owner();
    if (!w || !visible()) return {};
    const auto anchor = g_pDecorationPositioner->getEdgeDefinedPoint(DECORATION_EDGE_TOP, w);
    const auto offset = w->m_workspace && !w->m_pinned ? w->m_workspace->m_renderOffset->value() : Vector2D{};
    if (mini()) {
        const double desired=std::max(Style::miniWidth,3*Style::miniButtonSize+2*Style::miniButtonSpacing+44);
        const double width=std::min(std::max(1.0,m_assigned.w-2*Style::miniOffset),desired);
        return globalRect({m_assigned.x+(Style::buttons_side=="left"?Style::miniOffset:std::max(0.0,m_assigned.w-width-Style::miniOffset)),Style::miniOffset,width,Style::miniHeight},
                          {anchor.x,anchor.y},{offset.x,offset.y},{w->m_floatingOffset.x,w->m_floatingOffset.y});
    }
    return globalRect({m_assigned.x, m_assigned.y, m_assigned.w, m_assigned.h},
                      {anchor.x, anchor.y}, {offset.x, offset.y},
                      {w->m_floatingOffset.x, w->m_floatingOffset.y});
}
void FloatlandBar::updateWindow(PHLWINDOW window) {
    const bool now = visible();
    if (now != m_visible) {
        m_visible = now;
        g_pDecorationPositioner->repositionDeco(this);
    }
    damageEntire();
}
void FloatlandBar::damageEntire() {
    const auto box = globalBox();
    if (box.w > 0 && box.h > 0)
        g_pHyprRenderer->damageBox(CBox{box.x, box.y, box.w, box.h});
}
void FloatlandBar::draw(PHLMONITOR monitor, const float& alpha) {
    if (visible()) g_pHyprRenderer->addPassElement(makeUnique<FloatlandPass>(this, alpha));
}

double FloatlandBar::miniProgress() const {
    const auto now=std::chrono::steady_clock::now();
    return miniState.progress(std::chrono::duration<double>(now.time_since_epoch()).count(),Style::miniDuration);
}
bool FloatlandBar::pointerHit(Point point, bool activation) const {
    (void)activation;
    if(!visible()) return false;
    const auto box=globalBox();
    if(miniState.shown) return box.contains(point);
    const auto indicator=capsuleIndicator(box,Style::buttons_side=="left");
    return Rect{box.x+indicator.x,box.y+indicator.y,indicator.w,indicator.h}.contains(point);
}
bool FloatlandBar::gripHit(Point point) const {
    const auto box=globalBox(),grip=capsuleGrip(box);
    return miniState.shown && miniProgress()>=.98 && Rect{box.x+grip.x,box.y+grip.y,grip.w,grip.h}.contains(point);
}
void FloatlandBar::tickMini(double now, bool over, bool held) {
    if (mini() && miniState.update(now,over,held,Style::miniTimeout,Style::miniDuration)) damageEntire();
}
Control FloatlandBar::controlAt(Point point) const {
    if(mini()) {
        if(!miniState.shown || miniProgress()<.98) return Control::None;
        const auto box=globalBox(); if(!box.contains(point)) return Control::None;
        const double shift=0;
        for(int i=0;i<3;++i) {
            const auto c=static_cast<Control>(i);
            const auto b=miniButton(box,c,Style::miniButtonSize,Style::miniButtonSpacing);
            const double dx=point.x-box.x-b.x-b.w/2, dy=point.y-box.y-b.y-b.h/2-shift;
            if(dx*dx+dy*dy<=b.w*b.w/4) return c;
        }
        return Control::None;
    }

    return Floatland::hitButtonCircle(globalBox(),point,Style::buttons_side=="left",buttonOrder(Style::buttons_order),Style::buttonSpacing,Style::buttonSize);
}

void FloatlandBar::releaseButton() {
    m_returnControl=pressedControl;
    m_returnOffset=hovered==pressedControl ? Point{} : pressOffset;
    m_returnStarted=std::chrono::steady_clock::now();
    m_returnGrowth=std::clamp(std::chrono::duration<double>(m_returnStarted-pressStarted).count()/.12,0.0,1.0);
    pressedControl=Control::None; pressOffset={};
    damageEntire();
}

void FloatlandBar::rasterize(int width, int height, bool focused) {
    const auto box = globalBox();
    auto surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, width, height);
    auto cr = cairo_create(surface);
    cairo_scale(cr, width / box.w, height / box.h);
    cairo_set_antialias(cr,CAIRO_ANTIALIAS_BEST);
    const double expansion=miniProgress();
    // Crossfade the small, non-actionable indicator into the control capsule.
    if(expansion<1) {
        const auto indicator=capsuleIndicator(box,Style::buttons_side=="left");
        cairo_set_source_rgba(cr,Style::miniColor[0],Style::miniColor[1],Style::miniColor[2],Style::miniOpacity*(1-expansion));
        cairo_arc(cr,indicator.x+7,indicator.y+7,7,1.5707963268,4.7123889804);
        cairo_arc(cr,indicator.x+indicator.w-7,indicator.y+7,7,-1.5707963268,1.5707963268);
        cairo_close_path(cr); cairo_fill(cr);
        const std::array<double,3> colors[]={Style::mini_close_color,Style::mini_minimize_color,Style::mini_maximize_color};
        for(int i=0;i<3;++i) {
            cairo_set_source_rgba(cr,colors[i][0],colors[i][1],colors[i][2],1-expansion);
            cairo_arc(cr,indicator.x+8+i*10,indicator.y+7,3.5,0,6.283185307); cairo_fill(cr);
        }
    }
    cairo_push_group(cr);
    cairo_set_source_rgba(cr, Style::titlebar[0]*(focused?1:.85), Style::titlebar[1]*(focused?1:.85), Style::titlebar[2]*(focused?1:.85), Style::titlebarOpacity);
    const double radius = mini() ? HEIGHT/2 : std::clamp(static_cast<double>(owner()->rounding()), 0.0, std::min(box.w/2, box.h));
    const double pi = std::acos(-1);
    if(mini()) {
        const double inset=Style::miniBorderWidth/2, r=std::max(1.0,box.h/2-inset);
        cairo_set_source_rgba(cr,Style::miniColor[0],Style::miniColor[1],Style::miniColor[2],Style::miniOpacity);
        cairo_new_sub_path(cr);
        cairo_arc(cr,box.h/2,box.h/2,r,pi/2,pi*1.5);
        cairo_arc(cr,box.w-box.h/2,box.h/2,r,-pi/2,pi/2);
        cairo_close_path(cr); cairo_fill_preserve(cr);
        cairo_set_source_rgba(cr,Style::miniBorderColor[0],Style::miniBorderColor[1],Style::miniBorderColor[2],Style::miniBorderOpacity);
        cairo_set_line_width(cr,Style::miniBorderWidth);
        if(Style::miniBorderWidth>0) cairo_stroke(cr); else cairo_new_path(cr);
    } else if (radius > 0) {
        cairo_move_to(cr,0,box.h); cairo_line_to(cr,0,radius);
        cairo_arc(cr,radius,radius,radius,pi,pi*1.5);
        cairo_line_to(cr,box.w-radius,0); cairo_arc(cr,box.w-radius,radius,radius,-pi/2,0);
        cairo_line_to(cr,box.w,box.h); cairo_close_path(cr); cairo_fill(cr);
    } else cairo_paint(cr);
    // One layout defines both icon backgrounds and mouse targets.
    const double diameter=miniDiameter(box,Style::miniButtonSize);
    for (int i = 0; i < 3; ++i) {
        const auto control = static_cast<Control>(i);
        const auto button = miniButton(box,control,diameter,Style::miniButtonSpacing);
        if (button.w == 0) continue;
        const std::array<double,3> colors[3] = {Style::mini_close_color,Style::mini_minimize_color,Style::mini_maximize_color};
        const bool texture=Style::mini_button_texture;
        const auto& color = colors[i];
        const bool held=pressedControl==control;
        const bool armed=held && hovered==control;
        const auto now=std::chrono::steady_clock::now();
        const double rebound=!held && m_returnControl==control ? buttonReturn(std::chrono::duration<double>(now-m_returnStarted).count(),Style::buttonReturnDuration,Style::buttonRebound) : 0;
        const double growth=held ? std::clamp(std::chrono::duration<double>(now-pressStarted).count()/.12,0.0,1.0) : m_returnGrowth*rebound;
        const Point pull=held ? (armed ? Point{} : pressOffset) : Point{m_returnOffset.x*rebound,m_returnOffset.y*rebound};
        const double strength=std::min(1.0,std::hypot(pull.x,pull.y))*Style::buttonStretch/1.05;
        const double cx=button.x+button.w/2+4*Style::buttonShift*pull.x, cy=box.h/2+4*Style::buttonShift*pull.y;
        const double saturation=focused?1.0:.28, opacity=focused?1.0:.65;
        const double highlight=armed?Style::button_highlight:0;
        auto brighten=[&](double value) { return value+(1-value)*highlight; };
        const double red=brighten(.38+(color[0]-.38)*saturation);
        const double green=brighten(.38+(color[1]-.38)*saturation);
        const double blue=brighten(.38+(color[2]-.38)*saturation);
        const double radius=diameter/2+Style::button_growth*growth;
        // Preserve approximate area while elongating along the pull direction.
        // Hit regions remain the original circles even during deformation.
        const auto shape=buttonDeformation(radius,std::min(1.0,std::hypot(pull.x,pull.y)),Style::buttonStretch);
        const double travel=4*Style::buttonShift*std::hypot(pull.x,pull.y);
        const double front=std::min(shape.front, std::max(radius,box.h/2-1-travel));
        const double back=shape.back, side=shape.across;
        const double k=.5522847498;
        SvgControls::effects(cr,cx,cy,radius,red,green,blue,
            Style::mini_button_shadow,Style::mini_button_glow,opacity);
        cairo_save(cr); cairo_translate(cr,cx,cy);
        if(strength>0) cairo_rotate(cr,std::atan2(pull.y,pull.x));
        cairo_new_sub_path(cr); cairo_move_to(cr,front,0);
        cairo_curve_to(cr,front,k*side,k*front,side,0,side);
        cairo_curve_to(cr,-k*back,side,-back,k*side,-back,0);
        cairo_curve_to(cr,-back,-k*side,-k*back,-side,0,-side);
        cairo_curve_to(cr,k*front,-side,front,-k*side,front,0);
        cairo_close_path(cr); cairo_restore(cr);
        // Analytic gradients: no bitmap texture, so highlights stay sharp at any scale.
        auto fill=cairo_pattern_create_linear(cx,cy-radius,cx,cy+radius);
        cairo_pattern_add_color_stop_rgba(fill,0,std::min(1.0,red+(texture?.12:0)),std::min(1.0,green+(texture?.12:0)),std::min(1.0,blue+(texture?.12:0)),opacity);
        cairo_pattern_add_color_stop_rgba(fill,.46,red,green,blue,opacity);
        cairo_pattern_add_color_stop_rgba(fill,1,red*(texture?.88:1),green*(texture?.88:1),blue*(texture?.88:1),opacity);
        cairo_set_source(cr,fill); cairo_fill_preserve(cr); cairo_pattern_destroy(fill);
        auto rim=cairo_pattern_create_linear(cx,cy-radius,cx,cy+radius);
        cairo_pattern_add_color_stop_rgba(rim,0,1,1,1,(texture?.30:0)*opacity);
        cairo_pattern_add_color_stop_rgba(rim,.55,red,green,blue,(texture?.08:0)*opacity);
        cairo_pattern_add_color_stop_rgba(rim,1,red*.55,green*.55,blue*.55,(texture?.22:0)*opacity);
        cairo_set_source(cr,rim); cairo_set_line_width(cr,.65); cairo_stroke(cr); cairo_pattern_destroy(rim);
        const double iconOpacity=Style::button_hover_only?m_hoverOpacity:1;
        if ((!Style::button_icons) || iconOpacity<=0) continue;
        cairo_set_source_rgba(cr,brighten(color[0]*.44),brighten(color[1]*.44),brighten(color[2]*.44),iconOpacity*opacity);
        const double scale=width/box.w;
        const double stroke=Style::button_hinting?std::max(1.0,std::round(1.75*scale)):1.75*scale;
        // Apply pixel fitting only at rest; snapping moving contours causes jitter.
        const bool fit=Style::button_hinting && !held && rebound==0;
        const double ix=fit?hintedCenter(cx,scale,stroke):cx;
        const double iy=fit?hintedCenter(cy,height/box.h,stroke):cy;
        cairo_save(cr); cairo_translate(cr,ix,iy);
        const double angle=std::atan2(pull.y,pull.x);
        cairo_rotate(cr,angle); cairo_scale(cr,shape.along/radius*diameter/14,shape.across/radius*diameter/14);
        cairo_rotate(cr,-angle); cairo_translate(cr,-cx,-cy);
        cairo_set_line_width(cr,stroke/scale); cairo_set_line_cap(cr,CAIRO_LINE_CAP_ROUND);
        cairo_set_line_join(cr,CAIRO_LINE_JOIN_ROUND);
        const std::string paths[]={Style::mini_close_icon,Style::mini_minimize_icon,Style::mini_maximize_icon};
        const double optical[]={Style::mini_close_icon_scale,Style::mini_minimize_icon_scale,Style::mini_maximize_icon_scale};
        if(SvgControls::draw(cr,paths[i],cx,cy,14*std::min(.85,optical[i]*(Style::mini_icon_size)),Style::mini_icon_tint,iconOpacity*opacity)) {
            cairo_restore(cr); continue;
        }
        if(control==Control::Close) {
            cairo_move_to(cr,cx-2.35,cy-2.35); cairo_line_to(cr,cx+2.35,cy+2.35);
            cairo_move_to(cr,cx+2.35,cy-2.35); cairo_line_to(cr,cx-2.35,cy+2.35);
            cairo_stroke(cr);
        } else if(control==Control::Minimize) {
            cairo_move_to(cr,cx-2.8,cy); cairo_line_to(cr,cx+2.8,cy); cairo_stroke(cr);
        } else {
            // Two opposed diagonal arrowheads, matching the expand reference.
            cairo_move_to(cr,cx-3,cy-.6); cairo_line_to(cr,cx-3,cy+3); cairo_line_to(cr,cx+.6,cy+3); cairo_close_path(cr);
            cairo_move_to(cr,cx+3,cy+.6); cairo_line_to(cr,cx+3,cy-3); cairo_line_to(cr,cx-.6,cy-3); cairo_close_path(cr);
            cairo_fill(cr);
        }
        cairo_restore(cr);
    }
    const auto grip=capsuleGrip(box);
    const double gx=grip.x+grip.w/2,gy=box.h/2;
    cairo_set_source_rgba(cr,.72,.74,.78,focused?1:.7);
    cairo_set_line_width(cr,1.6); cairo_set_line_cap(cr,CAIRO_LINE_CAP_ROUND);
    cairo_move_to(cr,gx-6,gy); cairo_line_to(cr,gx+6,gy);
    cairo_move_to(cr,gx,gy-6); cairo_line_to(cr,gx,gy+6);
    cairo_move_to(cr,gx-3,gy-3); cairo_line_to(cr,gx,gy-6); cairo_line_to(cr,gx+3,gy-3);
    cairo_move_to(cr,gx-3,gy+3); cairo_line_to(cr,gx,gy+6); cairo_line_to(cr,gx+3,gy+3);
    cairo_stroke(cr);
    cairo_pop_group_to_source(cr); cairo_paint_with_alpha(cr,expansion);
    cairo_surface_flush(surface);
    m_texture = g_pHyprRenderer->createTexture(surface);
    m_texture->m_imageDescription = NColorManagement::getDefaultImageDescription();
    cairo_destroy(cr);
    cairo_surface_destroy(surface);
}
void FloatlandBar::paint(PHLMONITOR monitor, float alpha) {
    if (!visible()) return;
    const auto box = titlebarPixels(globalBox(), {monitor->m_position.x, monitor->m_position.y}, monitor->m_scale);
    if (box.w < 1 || box.h < 1) return;
    const bool focused = Desktop::focusState()->window() == owner();
    const auto now = std::chrono::steady_clock::now();
    const bool groupHover = hovered != Control::None;
    if (groupHover != m_hoverTarget) {
        m_hoverFrom=m_hoverOpacity; m_hoverTarget=groupHover; m_hoverStart=now;
    }
    const double hoverProgress=std::clamp(std::chrono::duration<double>(now-m_hoverStart).count()/.10,0.0,1.0);
    const double eased=hoverProgress*hoverProgress*(3-2*hoverProgress);
    m_hoverOpacity=m_hoverFrom+((m_hoverTarget?1.0:0.0)-m_hoverFrom)*eased;
    if (hoverProgress<1) { m_key.clear(); damageEntire(); }
    if (pressedControl!=Control::None) m_returnControl=Control::None;
    const bool returning=m_returnControl!=Control::None && std::chrono::duration<double>(now-m_returnStarted).count()<Style::buttonReturnDuration;
    if (returning) { m_key.clear(); damageEntire(); }
    else if (m_returnControl!=Control::None) { m_returnControl=Control::None; m_key.clear(); }
    const int pressFrame = pressedControl==Control::None ? 0 : static_cast<int>(std::clamp(std::chrono::duration<double>(std::chrono::steady_clock::now()-pressStarted).count()/.12,0.0,1.0)*12);
    const bool growing = pressedControl != Control::None && std::chrono::steady_clock::now()-pressStarted < std::chrono::milliseconds(120);
    if (growing) { m_key.clear(); damageEntire(); }
    if(mini() && miniProgress()>0 && miniProgress()<1) { m_key.clear(); damageEntire(); }
    const auto key = std::format("{}:{}:{}:{}:{}:{}", box.w, box.h, focused, static_cast<int>(hovered), owner()->m_title, owner()->rounding()) + std::format(":{}:{}:{}:{}",static_cast<int>(pressedControl),pressOffset.x,pressOffset.y,pressFrame) + std::format(":{}",static_cast<int>(m_hoverOpacity*100)) + std::to_string(Style::revision) + (isPictureInPicture(owner()) ? ":pip" : ":normal") + std::format(":capsule:{}",static_cast<int>(miniProgress()*1000));
    if (!m_texture || key != m_key) {
        rasterize(static_cast<int>(box.w), static_cast<int>(box.h), focused);
        m_key = key;
    }
    if(Style::mini_blur) {
        auto local=miniState.shown || miniProgress()>0 ? Rect{0,0,globalBox().w,globalBox().h}:capsuleIndicator(globalBox(),Style::buttons_side=="left");
        const auto global=globalBox();
        const auto glass=pixels({global.x+local.x,global.y+local.y,local.w,local.h},{monitor->m_position.x,monitor->m_position.y},monitor->m_scale);
        CHyprOpenGLImpl::SRectRenderData backdrop{};
        backdrop.blur=true; backdrop.blurA=alpha;
        backdrop.round=static_cast<int>(glass.h/2);
        g_pHyprOpenGL->renderRect(CBox{glass.x,glass.y,glass.w,glass.h},CHyprColor(0.,0.,0.,.02*alpha),backdrop);
    }
    CHyprOpenGLImpl::STextureRenderData data{};
    data.a = alpha;
    data.allowDim = false;
    g_pHyprOpenGL->renderTexture(m_texture, CBox{box.x, box.y, box.w, box.h}, data);
}
