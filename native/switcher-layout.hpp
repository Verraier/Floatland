#pragma once
#include "geometry.hpp"
#include <vector>

namespace Floatland {
struct SwitcherLayout {
    Rect panel;
    std::vector<Rect> cells;
    int first=0, capacity=1;
};
// Geometry is shared by rendering and input. Page at a readable minimum size.
inline SwitcherLayout switcherLayout(Rect screen,int count,int selected,double iconSize,
                                     double fontSize,bool preview,bool legacy,double previewWidth) {
    SwitcherLayout out;
    count=std::max(1,count); selected=std::clamp(selected,0,count-1);
    const double availableW=std::max(1.0,screen.w*.9-24);
    const double availableH=std::max(1.0,screen.h*.75-fontSize-48);
    int columns=1,rows=1;
    double cellW=iconSize+24,cellH=cellW;
    if(legacy) {
        cellW=iconSize+32;cellH=iconSize+fontSize+28;
        columns=std::max(1,std::min(9,static_cast<int>(availableW/cellW)));
    } else if(preview) {
        columns=std::max(1,static_cast<int>(availableW/std::min(previewWidth,availableW)));
        cellW=std::min(previewWidth,availableW);cellH=cellW*.64+fontSize+24;
        rows=std::max(1,std::min(3,static_cast<int>(availableH/cellH)));
        cellH=std::min(cellH,availableH);
    } else {
        const double minimum=std::min(iconSize+24,56.0);
        const int maxColumns=std::max(1,static_cast<int>(availableW/minimum));
        const int maxRows=std::max(1,std::min(3,static_cast<int>(availableH/minimum)));
        const int visible=std::min(count,maxColumns*maxRows);
        double best=-1;
        for(int c=1;c<=std::min(visible,maxColumns);++c) {
            const int r=(visible+c-1)/c;
            if(r>maxRows) continue;
            const double size=std::min({iconSize+24,availableW/c,availableH/r});
            const double score=size-(r-1)*4;
            if(score>best) { best=score;columns=c;rows=r;cellW=cellH=size; }
        }
    }
    out.capacity=std::max(1,columns*rows);
    out.first=selected/out.capacity*out.capacity;
    const int visible=std::min(count-out.first,out.capacity);
    columns=std::min(columns,visible);rows=(visible+columns-1)/columns;
    cellW=std::min(cellW,availableW/columns);cellH=std::min(cellH,availableH/rows);
    const double footer=legacy?0:fontSize+20;
    const double w=columns*cellW+24,h=rows*cellH+24+footer;
    out.panel={screen.x+(screen.w-w)/2,screen.y+(screen.h-h)/2,w,h};
    for(int i=0;i<visible;++i) {
        const int row=i/columns,col=i%columns;
        const int inRow=std::min(columns,visible-row*columns);
        const double offset=(columns-inRow)*cellW/2;
        out.cells.push_back({out.panel.x+12+offset+col*cellW+4,out.panel.y+12+row*cellH+4,
                             std::max(1.0,cellW-8),std::max(1.0,cellH-8)});
    }
    return out;
}
inline Rect switcherPreview(Rect cell,Point source,double fontSize) {
    const Rect available{cell.x+6,cell.y+fontSize+12,std::max(1.0,cell.w-12),std::max(1.0,cell.h-fontSize-18)};
    const double scale=std::min(available.w/std::max(1.0,source.x),available.h/std::max(1.0,source.y));
    const double w=std::max(1.0,source.x)*scale,h=std::max(1.0,source.y)*scale;
    return {available.x+(available.w-w)/2,available.y+(available.h-h)/2,w,h};
}
}
