#pragma once
#include <optional>
#include <memory>
#include <chrono>
#define WLR_USE_UNSTABLE
#include <hyprland/src/render/decorations/IHyprWindowDecoration.hpp>
#include <hyprland/src/render/gl/GLTexture.hpp>
#include "geometry.hpp"
#include "button-motion.hpp"

class FloatlandBar : public IHyprWindowDecoration {
  public:
    explicit FloatlandBar(PHLWINDOW window);
    ~FloatlandBar() override;
    SDecorationPositioningInfo getPositioningInfo() override;
    void onPositioningReply(const SDecorationPositioningReply& reply) override;
    void draw(PHLMONITOR monitor, float const& alpha) override;
    eDecorationType getDecorationType() override { return DECORATION_CUSTOM; }
    eDecorationLayer getDecorationLayer() override { return DECORATION_LAYER_UNDER; }
    uint64_t getDecorationFlags() override { return DECORATION_ALLOWS_MOUSE_INPUT | DECORATION_PART_OF_MAIN_WINDOW; }
    std::string getDisplayName() override { return "FloatlandTitlebar"; }
    void updateWindow(PHLWINDOW window) override;
    void damageEntire() override;
    std::weak_ptr<int> lifetime() const { return m_lifetime; }
    bool visible() const;
    PHLWINDOW owner() const { return m_window.lock(); }
    Floatland::Rect globalBox() const;
    void paint(PHLMONITOR monitor, float alpha);
    void releaseButton();
    Floatland::Control controlAt(Floatland::Point point) const;
    std::optional<Floatland::Point> restoreSize;
    Floatland::Control pressedControl = Floatland::Control::None;
    Floatland::Point pressOffset;
    std::chrono::steady_clock::time_point pressStarted;
    Floatland::Control hovered = Floatland::Control::None;
  private:
    std::shared_ptr<int> m_lifetime = std::make_shared<int>(0);
    Floatland::Control m_returnControl=Floatland::Control::None;
    Floatland::Point m_returnOffset;
    double m_returnGrowth=0;
    std::chrono::steady_clock::time_point m_returnStarted;
    PHLWINDOWREF m_window;
    CBox m_assigned;
    bool m_visible = false;
    bool m_hoverTarget = false;
    double m_hoverOpacity = 0, m_hoverFrom = 0;
    std::chrono::steady_clock::time_point m_hoverStart;
    SP<Render::ITexture> m_texture;
    std::string m_key;
    void rasterize(int width, int height, bool focused);
};

void forgetBar(FloatlandBar* bar);
