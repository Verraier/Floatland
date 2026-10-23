#pragma once
#include <algorithm>
namespace Floatland {
// One continuous transition drives both rendering and pointer geometry.
struct MiniState {
    bool shown=false, inside=false, armed=true, interacting=false, grace=false;
    double opened=0, changed=0, from=0;
    void reset() { *this=MiniState{}; }
    double progress(double now,double duration=.16) const {
        const double t=std::clamp((now-changed)/duration,0.0,1.0);
        const double eased=t*t*(3-2*t);
        return from+((shown?1.0:0.0)-from)*eased;
    }
    bool update(double now, bool over, bool held, double timeout=4, double duration=.16) {
        const bool before=shown;
        const double current=progress(now,duration);
        if(!over) armed=true;
        if(over && !inside && armed && !held) { shown=true; opened=now; armed=false; }
        // Interactions suspend expiry. Their end starts a complete timeout,
        // including when a drag/menu leaves the pointer outside the capsule.
        if(shown && (held || interacting)) {
            opened=now;
            grace=true;
        }
        interacting=held;
        inside=over;
        if(shown && ((!over && !grace) || now-opened>=timeout) && !held) {
            shown=false; armed=!over; grace=false;
        }
        if(before!=shown) { from=current; changed=now; }
        return before!=shown;
    }
};
}
