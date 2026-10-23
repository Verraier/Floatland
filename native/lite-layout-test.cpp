#include "lite-layout.hpp"
#include <cassert>
int main() {
    using namespace Floatland;
    for(const auto area:{Rect{0,0,1920,1080},Rect{-1920,-20,1920,1080},Rect{0,0,240,320}}) {
        const auto panel=sidebarPanel(area);
        assert(panel.x>=area.x && panel.x+panel.w<=area.x+area.w);
        for(int i=0;i<sidebarCapacity(panel);++i) {
            const auto card=sidebarCard(panel,i);
            assert(card.y>=panel.y && card.y+card.h<=panel.y+panel.h);
        }
    }
    const Rect box{0,0,160,32};
    const auto grip=capsuleGrip(box),indicator=capsuleIndicator(box);
    assert(grip.x>100 && indicator.x==0 && indicator.w==36);
    const auto right=capsuleIndicator(box,false);
    assert(right.x+right.w==box.w);
    assert(indicator.y==0 && right.y==0);
    for(double h:{28.,32.,64.}) {
        const auto left=capsuleIndicator({0,0,160,h},true);
        const auto right=capsuleIndicator({0,0,160,h},false);
        const double inset=4;
        assert(inset+left.x==inset+left.y);
        assert(inset+160-right.x-right.w==inset+right.y);
    }
    // Origin is local and does not drift with window/monitor coordinates.
    const auto moved=capsuleIndicator({-1920,400,160,32},true);
    assert(moved.x==indicator.x && moved.y==indicator.y);
    assert(indicator.x+indicator.w<=box.w && grip.x+grip.w==box.w);
}
