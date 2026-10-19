// Derived from the Hyprbars decoration/render-pass integration.
// See LICENSE.hyprbars and the project's NOTICE.md.
#include "titlebar.hpp"
#include "style.hpp"
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
    bool needsLiveBlur() override { return false; }
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
    return Style::titlebarsEnabled && w && w->m_isMapped && !w->isHidden() && w->m_isFloating && !w->m_pinned &&
        !w->m_group && !w->m_X11DoesntWantBorders && w->m_workspace &&
        !w->m_workspace->m_isSpecialWorkspace && w->m_ruleApplicator->decorate().valueOrDefault() &&
        Fullscreen::controller()->getFullscreenModes(w).internal == Fullscreen::FSMODE_NONE;
}

SDecorationPositioningInfo FloatlandBar::getPositioningInfo() {
    SDecorationPositioningInfo info;
    info.policy = DECORATION_POSITION_STICKY;
    info.edges = DECORATION_EDGE_TOP;
    info.priority = 5000;
    info.reserved = true;
    info.desiredExtents = {Vector2D{0.0, visible() ? HEIGHT : 0.0}, Vector2D{0.0, 0.0}};
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

Control FloatlandBar::controlAt(Point point) const {
    return Floatland::hitButtonCircle(globalBox(),point,Style::buttons_side=="left",buttonOrder(Style::buttons_order));
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
    cairo_set_source_rgba(cr, Style::titlebar[0]*(focused?1:.85), Style::titlebar[1]*(focused?1:.85), Style::titlebar[2]*(focused?1:.85), Style::titlebarOpacity);
    const double radius = std::clamp(static_cast<double>(owner()->rounding()), 0.0, std::min(box.w/2, box.h));
    const double pi = std::acos(-1);
    if (radius > 0) {
        cairo_move_to(cr,0,box.h); cairo_line_to(cr,0,radius);
        cairo_arc(cr,radius,radius,radius,pi,pi*1.5);
        cairo_line_to(cr,box.w-radius,0); cairo_arc(cr,box.w-radius,radius,radius,-pi/2,0);
        cairo_line_to(cr,box.w,box.h); cairo_close_path(cr); cairo_fill(cr);
    } else cairo_paint(cr);
    // One layout defines both icon backgrounds and mouse targets.
    const auto order=buttonOrder(Style::buttons_order);
    const bool left=Style::buttons_side=="left";
    const auto textBox=titleRect(box.w,left,order);
    for (int i = 0; i < 3; ++i) {
        const auto control = static_cast<Control>(i);
        const auto button = buttonRect(box.w, control,left,order);
        if (button.w == 0) continue;
        const std::array<double,3> colors[3] = {Style::closeColor,Style::minimizeColor,Style::maximizeColor};
        const auto& color = colors[i];
        const bool held=pressedControl==control;
        const bool armed=held && hovered==control;
        const auto now=std::chrono::steady_clock::now();
        const double rebound=!held && m_returnControl==control ? buttonReturn(std::chrono::duration<double>(now-m_returnStarted).count(),Style::buttonReturnDuration,Style::buttonRebound) : 0;
        const double growth=held ? std::clamp(std::chrono::duration<double>(now-pressStarted).count()/.12,0.0,1.0) : m_returnGrowth*rebound;
        const Point pull=held ? (armed ? Point{} : pressOffset) : Point{m_returnOffset.x*rebound,m_returnOffset.y*rebound};
        const double strength=std::min(1.0,std::hypot(pull.x,pull.y))*Style::buttonStretch/1.05;
        const double cx=button.x+button.w/2+Style::buttonShift*pull.x, cy=HEIGHT/2+Style::buttonShift*pull.y;
        const double saturation=focused?1.0:.28, opacity=focused?1.0:.65;
        const double highlight=armed?Style::button_highlight:0;
        auto brighten=[&](double value) { return value+(1-value)*highlight; };
        const double red=brighten(.38+(color[0]-.38)*saturation);
        const double green=brighten(.38+(color[1]-.38)*saturation);
        const double blue=brighten(.38+(color[2]-.38)*saturation);
        const double radius=7+Style::button_growth*growth;
        // The leading edge extends, the trailing edge almost stays put.
        // This path affects only drawing; hit regions remain the original circles' cells.
        const double front=radius+1.05*strength, back=radius-.10*strength, side=radius-.16*strength;
        const double k=.5522847498;
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
        cairo_pattern_add_color_stop_rgba(fill,0,std::min(1.0,red+(Style::buttonTexture?.12:0)),std::min(1.0,green+(Style::buttonTexture?.12:0)),std::min(1.0,blue+(Style::buttonTexture?.12:0)),opacity);
        cairo_pattern_add_color_stop_rgba(fill,.46,red,green,blue,opacity);
        cairo_pattern_add_color_stop_rgba(fill,1,red*(Style::buttonTexture?.88:1),green*(Style::buttonTexture?.88:1),blue*(Style::buttonTexture?.88:1),opacity);
        cairo_set_source(cr,fill); cairo_fill_preserve(cr); cairo_pattern_destroy(fill);
        auto rim=cairo_pattern_create_linear(cx,cy-radius,cx,cy+radius);
        cairo_pattern_add_color_stop_rgba(rim,0,1,1,1,(Style::buttonTexture?.30:0)*opacity);
        cairo_pattern_add_color_stop_rgba(rim,.55,red,green,blue,(Style::buttonTexture?.08:0)*opacity);
        cairo_pattern_add_color_stop_rgba(rim,1,red*.55,green*.55,blue*.55,(Style::buttonTexture?.22:0)*opacity);
        cairo_set_source(cr,rim); cairo_set_line_width(cr,.65); cairo_stroke(cr); cairo_pattern_destroy(rim);
        const double iconOpacity=Style::button_hover_only?m_hoverOpacity:1;
        if (!Style::button_icons || iconOpacity<=0) continue;
        cairo_set_source_rgba(cr,brighten(color[0]*.44),brighten(color[1]*.44),brighten(color[2]*.44),iconOpacity*opacity);
        const double scale=width/box.w;
        const double stroke=Style::button_hinting?std::max(1.0,std::round(1.75*scale)):1.75*scale;
        // Apply pixel fitting only at rest; snapping moving contours causes jitter.
        const bool fit=Style::button_hinting && !held && rebound==0;
        const double ix=fit?hintedCenter(cx,scale,stroke):cx;
        const double iy=fit?hintedCenter(cy,height/box.h,stroke):cy;
        cairo_save(cr); cairo_translate(cr,ix-cx,iy-cy);
        cairo_set_line_width(cr,stroke/scale); cairo_set_line_cap(cr,CAIRO_LINE_CAP_ROUND);
        cairo_set_line_join(cr,CAIRO_LINE_JOIN_ROUND);
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
    if (Style::title_enabled && textBox.w > 4) {
        auto layout = pango_cairo_create_layout(cr);
        auto font = pango_font_description_from_string("Sans");
        pango_font_description_set_size(font,Style::titleFontSize*PANGO_SCALE);
        pango_layout_set_font_description(layout, font);
        pango_layout_set_text(layout, owner()->m_title.c_str(), -1);
        pango_layout_set_single_paragraph_mode(layout, true);
        pango_layout_set_width(layout, static_cast<int>(textBox.w*PANGO_SCALE));
        pango_layout_set_ellipsize(layout, PANGO_ELLIPSIZE_END);
        int tw = 0, th = 0;
        pango_layout_get_pixel_size(layout, &tw, &th);
        cairo_set_source_rgba(cr, Style::titleText[0], Style::titleText[1], Style::titleText[2], focused ? 1 : .65);
        const double desired=Style::title_alignment=="right" ? textBox.x+textBox.w-tw :
            Style::title_alignment=="center" ? (box.w-tw)/2 : textBox.x;
        const double x=std::clamp(desired,textBox.x,textBox.x+std::max(0.0,textBox.w-tw));
        cairo_move_to(cr, x, (HEIGHT-th)/2);
        pango_cairo_show_layout(cr, layout);
        pango_font_description_free(font);
        g_object_unref(layout);
    }
    cairo_surface_flush(surface);
    m_texture = g_pHyprRenderer->createTexture(surface);
    m_texture->m_imageDescription = NColorManagement::getDefaultImageDescription();
    cairo_destroy(cr);
    cairo_surface_destroy(surface);
}
void FloatlandBar::paint(PHLMONITOR monitor, float alpha) {
    if (!visible()) return;
    const auto box = pixels(globalBox(), {monitor->m_position.x, monitor->m_position.y}, monitor->m_scale);
    if (box.w < 1 || box.h < 1) return;
    const bool focused = Desktop::focusState()->window() == owner();
    const auto now = std::chrono::steady_clock::now();
    const bool groupHover = hovered != Control::None || pressedControl != Control::None;
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
    const auto key = std::format("{}:{}:{}:{}:{}:{}", box.w, box.h, focused, static_cast<int>(hovered), owner()->m_title, owner()->rounding()) + std::format(":{}:{}:{}:{}",static_cast<int>(pressedControl),pressOffset.x,pressOffset.y,pressFrame) + std::format(":{}",static_cast<int>(m_hoverOpacity*100)) + std::to_string(Style::revision);
    if (!m_texture || key != m_key) {
        rasterize(static_cast<int>(box.w), static_cast<int>(box.h), focused);
        m_key = key;
    }
    CHyprOpenGLImpl::STextureRenderData data{};
    data.a = alpha;
    data.allowDim = false;
    g_pHyprOpenGL->renderTexture(m_texture, CBox{box.x, box.y, box.w, box.h}, data);
}
