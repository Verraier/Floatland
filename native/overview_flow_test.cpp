#include "overview-flow.hpp"
#include <cassert>
#include <cmath>
#include <iostream>
using Flow=Floatland::OverviewFlow;
int main() {
    Flow f;
    const auto cancelled=f.prepare();
    assert(!f.presenting());
    f.toggle(0);
    f.ready(cancelled,.1);
    assert(f.stage==Flow::Stage::Hidden);
    auto token=f.prepare(); f.ready(token,1);
    assert(f.presenting() && f.value(1)==0);
    const auto middle=f.value(1.1);
    assert(middle>0 && middle<1);
    f.toggle(1.1); assert(std::abs(f.value(1.1)-middle)<1e-12);
    const auto back=f.value(1.12);
    f.toggle(1.12); assert(std::abs(f.value(1.12)-back)<1e-12);
    assert(!f.finishFrame(2)); assert(f.stage==Flow::Stage::Visible);
    assert(f.value(2)==1);
    for(int i=0;i<10000;++i) {
        const double time=3+i*.003;
        const double before=f.value(time);
        f.toggle(time);
        assert(std::abs(f.value(time)-before)<1e-12);
        assert(f.value(time)>=0 && f.value(time)<=1);
    }
    f.close(40);
    assert(f.finishFrame(41));
    // Completion is a signal: the renderer controls the atomic handoff frame.
    assert(f.presenting());
    f.reset(); assert(!f.presenting());
    token=f.prepare(); f.ready(token,50); f.finishFrame(51);
    f.select(51); f.toggle(51.1);
    assert(f.stage==Flow::Stage::Selecting && f.value(52)==1);
    assert(!f.selectionExpired(53.9) && f.selectionExpired(54));
    f.close(52); assert(f.stage==Flow::Stage::Exiting);
    f.reset(); assert(!f.accepts(token));
    token=f.prepare(); f.ready(token,60); f.close(60);
    assert(f.finishFrame(61));
    std::cout << "Overview preparation, reversals, stale generations and selection tests passed\n";
}
