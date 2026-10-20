#pragma once
#include "geometry.hpp"
namespace Floatland {
constexpr double BUTTON_RETURN_SECONDS=.28;
// Two smooth segments: reach one bounded overshoot, then settle without oscillation.
inline double buttonReturn(double seconds, double duration=BUTTON_RETURN_SECONDS, double rebound=.12) {
    const double t=std::clamp(seconds/std::max(.001,duration),0.0,1.0);
    rebound=std::min(.3,rebound*2);
    auto smooth=[](double x) { return x*x*(3-2*x); };
    if(t>=1) return 0;
    if(t<.68) return 1-(1+rebound)*smooth(t/.68);
    return -rebound*(1-smooth((t-.68)/.32));
}
inline Point buttonPull(Point delta) {
    const double length=std::hypot(delta.x,delta.y);
    if(length==0) return {};
    // Resist short pulls; distant cursor movement has progressively less effect.
    const double strength=length/(length+60.0);
    return {delta.x/length*strength,delta.y/length*strength};
}
struct ButtonDeformation { double along, across, front, back; };
inline ButtonDeformation buttonDeformation(double radius, double pull, double stretch) {
    const double factor=1+std::clamp(pull,0.0,1.0)*std::clamp(stretch,0.0,2.0)*.20;
    // Extend the leading edge only; the trailing edge follows the center.
    // The mean longitudinal radius preserves area with transverse compression.
    return {radius*factor,radius/factor,radius*(2*factor-1),radius};
}
}
