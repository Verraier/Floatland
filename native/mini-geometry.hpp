#pragma once
#include "geometry.hpp"
namespace Floatland {
inline double miniDiameter(Rect box, double diameter) {
    return std::max(1.0,std::min({diameter,box.h-4,(box.w-44)/3}));
}
inline Rect miniButton(Rect box, Control control, double diameter, double spacing) {
    if(control==Control::None) return {};
    diameter=miniDiameter(box,diameter);
    const double gap=std::max(0.0,std::min(spacing,(box.w-44-3*diameter)/2));
    const double group=3*diameter+2*gap;
    return {(box.w-28-group)/2+static_cast<int>(control)*(diameter+gap),
            (box.h-diameter)/2,diameter,diameter};
}
}
