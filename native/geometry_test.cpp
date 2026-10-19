#include "geometry.hpp"
#include "button-motion.hpp"
#include "lifetime.hpp"
#include "snap.hpp"
#include "overview-layout.hpp"
#include <cassert>
#include <iostream>
using namespace Floatland;

int main() {
    const auto diagonal=buttonPull({100,100});
    assert(std::abs(std::hypot(diagonal.x,diagonal.y)-1)<1e-12);
    const auto right=buttonPull({14,0});
    assert(right.x==.5 && right.y==0);
    assert(buttonPull({0,0}).x==0);
    assert(buttonReturn(0)==1 && buttonReturn(BUTTON_RETURN_SECONDS)==0);
    int negativeRuns=0; bool negative=false;
    for(int i=0;i<=1000;++i) {
        const double value=buttonReturn(BUTTON_RETURN_SECONDS*i/1000.0);
        assert(value>=-.120001 && value<=1);
        const bool next=value < -1e-10;
        if(next && !negative) ++negativeRuns;
        negative=next;
    }
    assert(negativeRuns==1);
    assert(buttonReturn(10)==0);

    // All six action orders must share the exact geometry used by hit testing.
    for(const std::string order : {"close,minimize,maximize","close,maximize,minimize",
            "minimize,close,maximize","minimize,maximize,close","maximize,close,minimize","maximize,minimize,close","close",""}) {
        assert(validButtonOrder(order));
        for(bool left : {false,true}) for(double width : {40.,80.,110.,800.}) {
            const auto layout=buttonOrder(order);
            const auto title=titleRect(width,left,layout);
            double previous=-1;
            for(auto action:layout) {
                const auto b=buttonRect(width,action,left,layout);
                if(b.w==0) continue;
                assert(b.x>previous); previous=b.x;
                assert(hit({0,0,width,32},{b.x+16,16},left,layout)==action);
                assert(title.w==0 || title.x+title.w<=b.x || title.x>=b.x+b.w);
            }
        }
    }
    for(const std::string bad : {"close,close","close,","unknown","close,minimize,maximize,close"})
        assert(!validButtonOrder(bad));
    for(double scale : {1.,1.25,1.5,2.}) {
        const double stroke=std::round(1.75*scale);
        const double center=hintedCenter(16.3,scale,stroke)*scale;
        assert(std::abs(center-(std::floor(center)+(static_cast<int>(stroke)%2?.5:0)))<1e-9);
    }
    for(int i=0;i<100;++i) assert(buttonReturn(i*.003,.3,0)>=0);
    assert(snapZone({0,0,1920,1080},{0,0,1920,1080},{0,500},true,false).empty());
    assert(snapZone({0,0,1920,1080},{0,0,1920,1080},{960,20},false,true).empty());

    // Hover, press and release must not activate in the surrounding 32px cell.
    for(bool left : {false,true}) {
        const auto order=buttonOrder("close,minimize,maximize");
        for(auto action:order) {
            const Rect bar{100,200,800,32};
            const auto cell=buttonRect(bar.w,action,left,order);
            const Point center{bar.x+cell.x+16,bar.y+16};
            assert(hitButtonCircle(bar,center,left,order)==action);
            assert(hitButtonCircle(bar,{center.x+6,center.y},left,order)==action);
            assert(hitButtonCircle(bar,{center.x+8,center.y},left,order)==Control::None);
            assert(hitButtonCircle(bar,{center.x+6,center.y+6},left,order)==Control::None);
            assert(hitButtonCircle(bar,{center.x,bar.y+1},left,order)==Control::None);
        }
    }

    int decoration=42;
    auto lifetime=std::make_shared<int>(0);
    DeferredPtr<int> queued(&decoration,lifetime);
    assert(queued.get()==&decoration);
    lifetime.reset();
    assert(queued.get()==nullptr);
    // Reusing the same address with a new lifetime must not revive old passes.
    auto replacement=std::make_shared<int>(0);
    DeferredPtr<int> fresh(&decoration,replacement);
    assert(fresh.get()==&decoration && queued.get()==nullptr);

    // Current frame position includes workspace and float offsets exactly once.
    const auto bar = globalRect({-400, -32, 800, 32}, {-800, 100}, {60, 20}, {17, -4});
    assert(bar.x == -1123 && bar.y == 84);
    assert(hit(bar, {bar.x+bar.w-20, bar.y+16}) == Control::Close);
    assert(hit(bar, {bar.x+bar.w-52, bar.y+16}) == Control::Minimize);
    assert(hit(bar, {bar.x+bar.w-84, bar.y+16}) == Control::Maximize);
    assert(hit(bar, {bar.x+bar.w-20, bar.y+32}) == Control::None); // client, not titlebar
    assert(hit(bar, {bar.x+bar.w, bar.y+16}) == Control::None);
    for (double scale : {1.0, 1.25, 1.5, 2.0}) {
        auto pixel = pixels(bar, {-1920, 0}, scale);
        assert(pixel.x == std::round((bar.x+1920)*scale));
        assert(pixel.w == std::round((bar.x+bar.w+1920)*scale)-pixel.x);
        // Rasterization and hit-testing both use buttonRect in logical coordinates.
        for (int i = 0; i < 3; ++i) {
            const auto control = static_cast<Control>(i);
            const auto box = buttonRect(bar.w, control);
            assert(hit(bar, {bar.x+box.x+box.w/2, bar.y+box.h/2}) == control);
        }
    }
    assert(buttonRect(40, Control::Close).w == 0);
    assert(buttonRect(80, Control::Maximize).w == 0);
    const Rect screen{-1920, -200, 1920, 1080};
    const Rect area{-1920, -160, 1920, 1040};
    assert(snapZone(screen, area, {-1920, 400}) == "left");
    assert(snapZone(screen, area, {-1, -199}) == "top-right");
    assert(snapZone(screen, area, {-1, 879}) == "bottom-right");
    assert(snapZone(screen, area, {0, 400}).empty());
    assert(snapZone(screen, area, {-900, 400}).empty());
    for (int i = 0; i < 5; ++i) {
        auto cell = paletteCell(area, i);
        assert(snapZone(screen, area, {cell.x+cell.w/2, cell.y+cell.h/2}) == PALETTE_ZONES[i]);
    }
    assert(zoneRect(area, "right").x == -960);
    assert(zoneRect(area, "bottom-left").y == 360);
    const auto restored = restoredDragRect({600, 300}, {700, 500}, {.75, 16}, {0, 32, 1920, 1048});
    assert(restored.x == 75 && restored.y == 316);
    assert(restored.w == 700 && restored.h == 500);
    const auto bounded = restoredDragRect({-1900, -180}, {4000, 3000}, {.5, 16}, {-1920, -160, 1920, 1040});
    assert(bounded.x == -1920 && bounded.y == -160 && bounded.w == 1920 && bounded.h == 1040);
    assert(ownsSnapDrop(true,true,true,true));
    assert(ownsSnapDrop(true,true,true,false)); // core already processed release
    assert(!ownsSnapDrop(false,true,true,false)); // another input path
    assert(!ownsSnapDrop(true,true,false,false)); // stationary titlebar click
    assert(!ownsSnapDrop(true,false,true,false)); // window disappeared
    assert(easeOverview(0)==0 && easeOverview(1)==1);
    const auto halfway=interpolate({10,20,100,80},{110,220,200,160},.5);
    assert(halfway.x==60 && halfway.y==120 && halfway.w==150 && halfway.h==120);
    for (int count=1;count<=64;++count) {
        for (Rect bounds : {Rect{-1920,40,1800,900},Rect{40,60,720,480}}) {
            std::vector<Point> sizes;
            for(int i=0;i<count;++i) sizes.push_back({i%2?500.0:1400.0,i%2?1200.0:700.0});
            auto cards=overviewCards(bounds,sizes);
            assert(cards.size()==sizes.size());
            for(size_t i=0;i<cards.size();++i) {
                const auto a=cards[i];
                assert(a.w>0 && a.h>0 && a.x>=bounds.x && a.y>=bounds.y);
                assert(a.x+a.w<=bounds.x+bounds.w+.01 && a.y+a.h<=bounds.y+bounds.h+.01);
                for(size_t j=i+1;j<cards.size();++j) {
                    const auto b=cards[j];
                    assert(a.x+a.w<=b.x || b.x+b.w<=a.x || a.y+a.h<=b.y || b.y+b.h<=a.y);
                }
            }
        }
    }
    const Rect overviewBounds{0,0,1600,900};
    const auto few=overviewCards(overviewBounds,std::vector<Point>(3,{1000,700}));
    const auto many=overviewCards(overviewBounds,std::vector<Point>(24,{1000,700}));
    assert(many.size()==24 && many[0].w<few[0].w && many[0].h<few[0].h);
    const auto preview=overviewPreview(few[0],{1000,700});
    assert(preview.x>=few[0].x && preview.y>=few[0].y);
    assert(preview.x+preview.w<=few[0].x+few[0].w);
    assert(preview.y+preview.h<=few[0].y+few[0].h);
    assert(std::abs(preview.w/preview.h-1000./700)<1e-9);
    Click click;
    click.begin(Control::Close, {0, 0});
    assert(click.release(Control::Maximize, false) == Control::None);
    click.begin(Control::Close, {0, 0});
    assert(click.release(Control::Close, true) == Control::None);
    click.begin(Control::Close, {0, 0});
    assert(click.release(Control::Close, false) == Control::Close);
    assert(click.release(Control::Close, false) == Control::None);
    click.begin(Control::Close, {0,0});
    assert(click.release(Control::Close, false, 500) == Control::Close);
    click.begin(Control::Close, {0,0});
    assert(click.release(Control::Close, false, 499) == Control::Close);
    assert(!click.active);
    std::cout << "Titlebar coordinate and click tests passed\n";
}
