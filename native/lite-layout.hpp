#pragma once
#include "geometry.hpp"
namespace Floatland {
inline Rect capsuleGrip(Rect box) {
    const double width=std::min(28.,box.w);
    return {box.w-width,0,width,box.h};
}
inline Rect capsuleIndicator(Rect box, bool left=true) {
    const double width=std::min(36.,box.w),height=std::min(14.,box.h);
    // Share the same top/side inset as the expanded capsule.
    return {left?0:box.w-width,0,width,height};
}
inline Rect sidebarPanel(Rect area) {
    const double margin=std::min(12.,std::min(area.w,area.h)/8);
    const double width=std::min(272.,std::max(1.,area.w-2*margin));
    return {area.x+area.w-margin-width,area.y+margin,width,std::max(1.,area.h-2*margin)};
}
inline int sidebarCapacity(Rect panel) { return std::max(1,static_cast<int>((panel.h-24)/176)); }
inline Rect sidebarCard(Rect panel,int slot) {
    const double height=std::min(164.,std::max(1.,panel.h-24));
    return {panel.x+12,panel.y+12+slot*176,std::max(1.,panel.w-24),height};
}
}
