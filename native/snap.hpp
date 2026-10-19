#pragma once
#include "geometry.hpp"
#include <string>
#include <algorithm>
namespace Floatland {
inline constexpr std::array<const char*, 5> PALETTE_ZONES = {"left", "right", "full", "top-left", "top-right"};
inline Rect paletteCell(Rect area, int index) {
    const double cell = std::min(64.0, area.w / 5.0);
    return {area.x + (area.w - cell * 5) / 2 + index * cell, area.y + 8, cell, 44};
}
inline std::string snapZone(Rect screen, Rect area, Point p, bool palette=true, bool edges=true) {
    if (!screen.contains(p)) return {};
    for (int i = 0; palette && i < 5; ++i)
        if (paletteCell(area, i).contains(p)) return PALETTE_ZONES[i];
    if (!edges) return {};
    const bool left = p.x < screen.x + 16, right = p.x >= screen.x + screen.w - 16;
    const bool top = p.y < screen.y + 16, bottom = p.y >= screen.y + screen.h - 16;
    if (left || right) {
        const std::string side = left ? "left" : "right";
        return top ? "top-" + side : bottom ? "bottom-" + side : side;
    }
    return top ? "full" : bottom ? "bottom" : "";
}
inline Rect zoneRect(Rect area, const std::string& zone) {
    if (zone.empty() || zone == "full") return area;
    if (zone.find("left") != std::string::npos) area.w /= 2;
    if (zone.find("right") != std::string::npos) { area.w /= 2; area.x += area.w; }
    if (zone.find("top") != std::string::npos) area.h /= 2;
    if (zone.find("bottom") != std::string::npos) { area.h /= 2; area.y += area.h; }
    return area;
}
}
