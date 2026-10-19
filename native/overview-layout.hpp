#pragma once
#include "geometry.hpp"
#include <vector>
#include <limits>
namespace Floatland {
// Find the largest common scale that fits all windows. Row boundaries are
// chosen by dynamic programming, not a fixed column count or paginated grid.
inline std::vector<Rect> overviewCards(Rect area, const std::vector<Point>& sizes) {
    const size_t n=sizes.size();
    if (!n || area.w<=0 || area.h<=0) return {};
    auto pack=[&](double scale,std::vector<size_t>* breaks) {
        std::vector<double> height(n+1,std::numeric_limits<double>::infinity());
        std::vector<size_t> previous(n+1); height[0]=0;
        const double gap=24*scale;
        for(size_t end=1;end<=n;++end) {
            double width=0,rowHeight=0;
            for(size_t begin=end;begin>0;) {
                --begin;
                width+=(std::max(1.0,sizes[begin].x)+24)*scale+(begin+1<end?gap:0);
                if(width>area.w) break;
                rowHeight=std::max(rowHeight,(std::max(1.0,sizes[begin].y)+48)*scale);
                const double candidate=height[begin]+rowHeight+(begin?gap:0);
                if(candidate<height[end]) { height[end]=candidate; previous[end]=begin; }
            }
        }
        if(breaks && std::isfinite(height[n])) {
            for(size_t end=n;end;end=previous[end]) breaks->push_back(end);
            std::reverse(breaks->begin(),breaks->end());
        }
        return height[n];
    };
    double low=0,high=.8;
    for(int step=0;step<40;++step) {
        const double mid=(low+high)/2;
        if(pack(mid,nullptr)<=area.h) low=mid; else high=mid;
    }
    const double scale=low*.94,gap=24*scale;
    std::vector<size_t> ends; const double total=pack(scale,&ends);
    std::vector<Rect> result(n);
    double y=area.y+(area.h-total)/2; size_t begin=0;
    for(size_t end:ends) {
        double width=gap*(end-begin-1),rowHeight=0;
        for(size_t i=begin;i<end;++i) {
            width+=(std::max(1.0,sizes[i].x)+24)*scale;
            rowHeight=std::max(rowHeight,(std::max(1.0,sizes[i].y)+48)*scale);
        }
        double x=area.x+(area.w-width)/2;
        for(size_t i=begin;i<end;++i) {
            const double w=(std::max(1.0,sizes[i].x)+24)*scale,h=(std::max(1.0,sizes[i].y)+48)*scale;
            result[i]={x,y+(rowHeight-h)/2,w,h}; x+=w+gap;
        }
        y+=rowHeight+gap; begin=end;
    }
    return result;
}
inline Rect overviewPreview(Rect card,Point source) {
    const double padding=std::min(12.0,card.w*.06), label=std::min(32.0,card.h*.18);
    const double scale=std::min(std::max(1.0,card.w-2*padding)/std::max(1.0,source.x),std::max(1.0,card.h-label-2*padding)/std::max(1.0,source.y));
    return {card.x+(card.w-source.x*scale)/2,card.y+padding+(card.h-label-2*padding-source.y*scale)/2,source.x*scale,source.y*scale};
}
}
