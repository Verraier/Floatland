#include "switcher-layout.hpp"
#include "switcher-preparation.hpp"
#include <cassert>
#include <iostream>
using namespace Floatland;
int main() {
    SwitcherPreparation queue;
    auto old=queue.begin(0,6);
    assert(queue.take(old)==0);
    auto current=queue.begin(6,10);
    assert(queue.take(old)==-1);
    for(int i=6;i<10;++i) assert(queue.take(current)==i);
    assert(queue.take(current)==-1);
    for(int i=0;i<10000;++i) {
        auto token=queue.begin(0,20);
        queue.cancel();
        assert(!queue.pending(token) && queue.take(token)==-1);
    }

    for(const auto screen : {Rect{0,0,1920,1080},Rect{-1280,100,1280,720},Rect{0,0,640,480}})
    for(int count : {1,2,6,12,32,100,300})
    for(int selected=0;selected<count;++selected)
    for(int mode=0;mode<3;++mode) {
        const auto layout=switcherLayout(screen,count,selected,80,14,mode==1,mode==2,240);
        const auto b=layout.panel;
        assert(b.x>=screen.x && b.y>=screen.y);
        assert(b.x+b.w<=screen.x+screen.w && b.y+b.h<=screen.y+screen.h);
        assert(layout.first<=selected && selected<layout.first+static_cast<int>(layout.cells.size()));
        for(size_t i=0;i<layout.cells.size();++i) {
            const auto c=layout.cells[i];
            assert(c.w>0 && c.h>0 && c.x>=b.x && c.y>=b.y && c.x+c.w<=b.x+b.w && c.y+c.h<=b.y+b.h);
            if(mode==0) assert(std::abs(c.w-c.h)<1e-9);
            for(size_t j=i+1;j<layout.cells.size();++j) {
                const auto d=layout.cells[j];
                assert(c.x+c.w<=d.x || d.x+d.w<=c.x || c.y+c.h<=d.y || d.y+d.h<=c.y);
            }
            if(mode==1) for(Point size : {Point{1600,900},Point{300,1200}}) {
                const auto image=switcherPreview(c,size,14);
                assert(image.x>=c.x && image.y>=c.y && image.x+image.w<=c.x+c.w+.001 && image.y+image.h<=c.y+c.h+.001);
                assert(std::abs(image.w/image.h-size.x/size.y)<1e-9);
            }
        }
    }
    auto a=switcherLayout({0,0,640,480},2,0,80,14,false,false,240);
    auto b=switcherLayout({0,0,640,480},24,0,80,14,false,false,240);
    assert(b.cells[0].w<a.cells[0].w);
    std::cout << "Switcher layout, paging, scaling and aspect-ratio tests passed\n";
}
