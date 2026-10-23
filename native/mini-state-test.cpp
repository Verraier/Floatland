#include "mini-state.hpp"
#include "mini-geometry.hpp"
#include <cassert>
#include <cmath>
int main() {
    Floatland::MiniState s;
    assert(s.update(0,true,false) && s.shown);
    assert(s.progress(0)==0 && s.progress(.2)==1);
    assert(!s.update(3.99,true,false));
    assert(s.update(4,true,false) && !s.shown);
    assert(s.progress(4)==1 && s.progress(4.2)==0);
    assert(!s.update(8,true,false));
    s.update(9,false,false); s.update(10,true,false); assert(s.shown);
    s.update(15,true,true); assert(s.shown);
    s.update(16,true,false); assert(s.shown);
    s.update(19.99,true,false); assert(s.shown);
    s.update(20,true,false); assert(!s.shown);
    s.reset(); s.update(20,true,false);
    assert(s.update(20.08,false,false));
    const double mid=s.progress(20.08);
    assert(mid>.4 && mid<.6);
    s.update(20.1,true,false);
    assert(s.progress(20.1)<mid && s.shown);
    s.update(21,false,true); assert(s.shown);
    s.update(22,false,false); assert(s.shown);
    s.update(25.99,false,false); assert(s.shown);
    s.update(26,false,false); assert(!s.shown);
    // A menu can stay open well beyond the ordinary timeout.
    s.reset(); s.update(30,true,false);
    s.update(31,false,true); s.update(90,false,true); assert(s.shown);
    s.update(91,false,false); assert(s.shown);
    s.update(94.99,false,false); assert(s.shown);
    s.update(95,false,false); assert(!s.shown);
    for(double width: {96.,128.,240.}) for(double diameter: {8.,14.,24.}) {
        Floatland::Rect box{0,0,width,40};
        const auto a=Floatland::miniButton(box,Floatland::Control::Close,diameter,16);
        const auto b=Floatland::miniButton(box,Floatland::Control::Maximize,diameter,16);
        assert(std::abs(a.x-(width-28-b.x-b.w))<.0001);
        assert(a.y+a.h/2==20 && a.x>=0 && b.x+b.w<=width);
    }
}
