#pragma once
#include <array>
#include <string>
#include <cmath>
#include <algorithm>

namespace Floatland {
constexpr double HEIGHT = 32.0;
constexpr double BUTTON = 32.0;
constexpr double PADDING = 4.0;
struct Point { double x = 0, y = 0; };
struct Rect {
    double x = 0, y = 0, w = 0, h = 0;
    bool contains(Point p) const {
        return w > 0 && h > 0 && p.x >= x && p.x < x + w && p.y >= y && p.y < y + h;
    }
};
enum class Control { None = -1, Close = 0, Minimize = 1, Maximize = 2 };
inline Rect globalRect(Rect assigned, Point anchor, Point workspaceOffset, Point floatingOffset) {
    return {assigned.x + anchor.x + workspaceOffset.x + floatingOffset.x,
            assigned.y + anchor.y + workspaceOffset.y + floatingOffset.y, assigned.w, assigned.h};
}
inline Rect pixels(Rect global, Point monitor, double scale) {
    // Round edges, not origin and width independently.
    const double left = std::round((global.x - monitor.x) * scale);
    const double top = std::round((global.y - monitor.y) * scale);
    return {left, top, std::round((global.x + global.w - monitor.x) * scale) - left,
            std::round((global.y + global.h - monitor.y) * scale) - top};
}
using ButtonOrder = std::array<Control,3>;
inline bool validButtonOrder(const std::string& order) {
    if (order.empty()) return true;
    bool seen[3]={false,false,false};
    size_t start=0;
    while(start<order.size()) {
        const auto end=order.find(',',start);
        const auto name=order.substr(start,end==std::string::npos?end:end-start);
        const int index=name=="close"?0:name=="minimize"?1:name=="maximize"?2:-1;
        if(index<0 || seen[index]) return false;
        seen[index]=true;
        if(end==std::string::npos) return true;
        start=end+1;
    }
    return false;
}
inline ButtonOrder buttonOrder(const std::string& value) {
    ButtonOrder order{Control::None,Control::None,Control::None};
    if(!validButtonOrder(value) || value.empty()) return order;
    size_t start=0;
    for(int i=0;i<3 && start<value.size();++i) {
        const auto end=value.find(',',start);
        const auto name=value.substr(start,end==std::string::npos?end:end-start);
        order[i]=name=="close"?Control::Close:name=="minimize"?Control::Minimize:Control::Maximize;
        if(end==std::string::npos) break;
        start=end+1;
    }
    return order;
}
inline Rect buttonRect(double width, Control control, bool left=false,
                       ButtonOrder order={Control::Maximize,Control::Minimize,Control::Close}) {
    if(control==Control::None) return {};
    int count=0,index=-1;
    for(auto entry:order) { if(entry==control) index=count; if(entry!=Control::None) ++count; }
    if(index<0) return {};
    const double x=left ? PADDING+BUTTON*index : width-PADDING-BUTTON*(count-index);
    // Keep a drag area on narrow windows; the outermost buttons have priority.
    return x>=0 && x+BUTTON<=width && (left ? x+BUTTON<=width-16 : x>=16)
        ? Rect{x,0,BUTTON,HEIGHT} : Rect{};
}
inline Control hit(Rect bar, Point global, bool left=false,
                   ButtonOrder order={Control::Maximize,Control::Minimize,Control::Close}) {
    if (!bar.contains(global)) return Control::None;
    for (int i=0;i<3;++i)
        if(buttonRect(bar.w,static_cast<Control>(i),left,order).contains({global.x-bar.x,global.y-bar.y}))
            return static_cast<Control>(i);
    return Control::None;
}
// Interaction follows the visible resting circle, not its larger layout cell.
// Keep this radius stable during stretching to prevent hover feedback loops.
inline Control hitButtonCircle(Rect bar, Point global, bool left=false,
                               ButtonOrder order={Control::Maximize,Control::Minimize,Control::Close}) {
    if (!bar.contains(global)) return Control::None;
    for(auto control:order) {
        const auto cell=buttonRect(bar.w,control,left,order);
        if(cell.w==0) continue;
        const double dx=global.x-bar.x-cell.x-cell.w/2;
        const double dy=global.y-bar.y-HEIGHT/2;
        if(dx*dx+dy*dy<=49) return control;
    }
    return Control::None;
}
inline Rect titleRect(double width, bool left, ButtonOrder order) {
    double begin=12,end=width-12;
    for(auto control:order) {
        const auto button=buttonRect(width,control,left,order);
        if(button.w==0) continue;
        if(left) begin=std::max(begin,button.x+button.w+8);
        else end=std::min(end,button.x-8);
    }
    return {begin,0,std::max(0.0,end-begin),HEIGHT};
}
// Align a stroke center to physical pixels without changing its logical hitbox.
inline double hintedCenter(double value, double scale, double physicalStroke) {
    const double offset=static_cast<int>(physicalStroke)%2 ? .5 : 0;
    return (std::round(value*scale-offset)+offset)/scale;
}
inline Rect restoredDragRect(Point cursor, Point size, Point grip, Rect bounds) {
    const double w = std::max(1.0, std::min(size.x, bounds.w));
    const double h = std::max(1.0, std::min(size.y, bounds.h));
    return {std::clamp(cursor.x - w * std::clamp(grip.x, 0.0, 1.0), bounds.x, bounds.x + bounds.w - w),
            std::clamp(cursor.y + HEIGHT - grip.y, bounds.y, bounds.y + bounds.h - h), w, h};
}
inline bool ownsSnapDrop(bool ownedPress, bool visible, bool moved, bool compositorDragging) {
    // Ownership survives the core clearing its drag target on release.
    return ownedPress && visible && (moved || compositorDragging);
}
inline double easeOverview(double phase) {
    const double t=std::clamp(phase,0.0,1.0);
    return 1-std::pow(1-t,3);
}
inline Rect interpolate(Rect from, Rect to, double phase) {
    const double t=std::clamp(phase,0.0,1.0);
    return {from.x+(to.x-from.x)*t,from.y+(to.y-from.y)*t,
            from.w+(to.w-from.w)*t,from.h+(to.h-from.h)*t};
}
struct Click {
    bool active = false;
    Control pressed = Control::None;
    Point origin;
    void begin(Control control, Point point) { active = true; pressed = control; origin = point; }
    bool moved(Point point) const {
        return std::hypot(point.x-origin.x, point.y-origin.y) > 4.0;
    }
    Control release(Control over, bool movedOrDragged, double /*heldMilliseconds*/ = 0) {
        const auto result = active && !movedOrDragged && pressed == over ? pressed : Control::None;
        active = false;
        pressed = Control::None;
        return result;
    }
};
}
