#pragma once
#include "geometry.hpp"
namespace Floatland {
constexpr double BUTTON_RETURN_SECONDS=.28;
// Two smooth segments: reach one bounded overshoot, then settle without oscillation.
inline double buttonReturn(double seconds, double duration=BUTTON_RETURN_SECONDS, double rebound=.12) {
    const double t=std::clamp(seconds/std::max(.001,duration),0.0,1.0);
    auto smooth=[](double x) { return x*x*(3-2*x); };
    if(t>=1) return 0;
    if(t<.68) return 1-(1+rebound)*smooth(t/.68);
    return -rebound*(1-smooth((t-.68)/.32));
}
inline Point buttonPull(Point delta) {
    const double length=std::hypot(delta.x,delta.y);
    if(length==0) return {};
    const double strength=std::min(1.0,length/28.0);
    return {delta.x/length*strength,delta.y/length*strength};
}
}
