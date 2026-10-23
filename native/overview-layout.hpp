#pragma once
#include "geometry.hpp"
#include <vector>
#include <limits>
namespace Floatland {
inline Rect overviewPreview(Rect card,Point source) {
    const double padding=std::min(12.0,card.w*.06), label=std::min(32.0,card.h*.18);
    const double scale=std::min(std::max(1.0,card.w-2*padding)/std::max(1.0,source.x),std::max(1.0,card.h-label-2*padding)/std::max(1.0,source.y));
    return {card.x+(card.w-source.x*scale)/2,card.y+padding+(card.h-label-2*padding-source.y*scale)/2,source.x*scale,source.y*scale};
}
}
