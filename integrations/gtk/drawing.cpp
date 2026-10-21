// GTK owns layout and events; Floatland owns all control drawing and motion.
#include "drawing.h"
#include "../../native/button-motion.hpp"
#include <algorithm>
#include <array>
#include <string>
#include <cmath>

namespace {
using Floatland::Point;
struct Controls {
    GtkWidget* widget=nullptr;
    std::string marker, previous;
    void (*activate)(const char*,int)=nullptr;
    double size=14,gap=18,shift=.9,stretch=1.5,duration=.28,rebound=.12,growth=.8,highlight=.22;
    bool texture=true,icons=true,hoverOnly=true,hinting=true,lastActive=false;
    std::array<GdkRGBA,3> colors{};
    int hover=-1,held=-1,returning=-1,selected=0;
    double releasedGrowth=0,pressTime=0,returnTime=-100,startX=0,startY=0,iconAlpha=0,lastFrame=0;
    Point pull{},released{};
    guint timer=0,frames=0;
};
double now() { return g_get_monotonic_time()/1000000.; }
Point center(Controls* c,int i) {
    const double width=gtk_widget_get_width(c->widget),height=gtk_widget_get_height(c->widget);
    return {width/2+(i-1)*(c->size+c->gap),height/2};
}
int hit(Controls* c,double x,double y) {
    for(int i=0;i<3;++i) { const auto p=center(c,i); if(std::hypot(x-p.x,y-p.y)<=c->size/2) return i; }
    return -1;
}
gboolean frame(GtkWidget*,GdkFrameClock*,gpointer data) {
    auto c=static_cast<Controls*>(data); const double t=now();
    const bool target=!c->hoverOnly || c->hover>=0 || c->held>=0 || gtk_widget_has_focus(c->widget);
    const double step=std::min(.05,std::max(0.,t-c->lastFrame))/.1;
    c->iconAlpha=std::clamp(c->iconAlpha+(target?step:-step),0.,1.); c->lastFrame=t;
    gtk_widget_queue_draw(c->widget);
    const bool live=(c->held>=0 && t-c->pressTime<.12) || t-c->returnTime<c->duration || (target?c->iconAlpha<1:c->iconAlpha>0);
    if(!live) c->frames=0;
    return live?G_SOURCE_CONTINUE:G_SOURCE_REMOVE;
}
void redraw(Controls* c) {
    gtk_widget_queue_draw(c->widget);
    if(!c->frames) { c->lastFrame=now(); c->frames=gtk_widget_add_tick_callback(c->widget,frame,c,nullptr); }
}
void position(Controls* c,double x,double y) {
    c->hover=hit(c,x,y);
    if(c->held>=0) {
        const auto p=center(c,c->held);
        c->pull=c->hover==c->held?Point{}:Floatland::buttonPull({x-p.x,y-p.y});
    }
    redraw(c);
}
void release(Controls* c,bool activate) {
    const int action=c->held;
    c->returning=action; c->released=c->pull; c->releasedGrowth=std::clamp((now()-c->pressTime)/.12,0.,1.); c->returnTime=now(); c->held=-1;
    redraw(c);
    if(activate && action>=0) c->activate(c->marker.c_str(),action);
}
void begin(GtkGestureDrag* gesture,double x,double y,gpointer data) {
    auto c=static_cast<Controls*>(data); const int index=hit(c,x,y);
    gtk_gesture_set_state(GTK_GESTURE(gesture),index<0?GTK_EVENT_SEQUENCE_DENIED:GTK_EVENT_SEQUENCE_CLAIMED);
    if(index<0) return;
    c->held=index; c->hover=index; c->selected=index; c->returning=-1;
    c->pressTime=now(); c->startX=x; c->startY=y; c->pull={}; redraw(c);
}
void move(GtkGestureDrag*,double dx,double dy,gpointer data) {
    auto c=static_cast<Controls*>(data); if(c->held>=0) position(c,c->startX+dx,c->startY+dy);
}
void end(GtkGestureDrag*,double dx,double dy,gpointer data) {
    auto c=static_cast<Controls*>(data); if(c->held<0) return;
    position(c,c->startX+dx,c->startY+dy); release(c,c->hover==c->held);
}
void cancel(GtkGesture*,GdkEventSequence*,gpointer data) { auto c=static_cast<Controls*>(data); if(c->held>=0) release(c,false); }
void motion(GtkEventControllerMotion*,double x,double y,gpointer data) { position(static_cast<Controls*>(data),x,y); }
void leave(GtkEventControllerMotion*,gpointer data) { auto c=static_cast<Controls*>(data); c->hover=-1; redraw(c); }
void focus(GtkEventControllerFocus*,gpointer data) { redraw(static_cast<Controls*>(data)); }
gboolean key(GtkEventControllerKey*,guint symbol,guint,GdkModifierType,gpointer data) {
    auto c=static_cast<Controls*>(data);
    if(symbol==GDK_KEY_Left || symbol==GDK_KEY_Right) c->selected=(c->selected+(symbol==GDK_KEY_Left?2:1))%3;
    else if(symbol==GDK_KEY_Return || symbol==GDK_KEY_space) c->activate(c->marker.c_str(),c->selected);
    else if(symbol==GDK_KEY_Escape && c->held>=0) release(c,false);
    else return FALSE;
    const char* names[]={"Close window","Minimize window","Maximize window"};
    gtk_accessible_update_property(GTK_ACCESSIBLE(c->widget),GTK_ACCESSIBLE_PROPERTY_LABEL,names[c->selected],-1);
    redraw(c); return TRUE;
}
gboolean settings(gpointer data) {
    auto c=static_cast<Controls*>(data);
    auto root=gtk_widget_get_root(c->widget); const bool active=GTK_IS_WINDOW(root) && gtk_window_is_active(GTK_WINDOW(root));
    if(active!=c->lastActive) { c->lastActive=active; redraw(c); }
    const char* path=g_getenv("FLOATLAND_GTK_SETTINGS");
    char* bytes=nullptr;
    if(!path || !g_file_get_contents(path,&bytes,nullptr,nullptr)) return G_SOURCE_CONTINUE;
    std::string current=bytes; g_free(bytes); if(current==c->previous) return G_SOURCE_CONTINUE;
    auto ini=g_key_file_new(); if(!g_key_file_load_from_data(ini,current.data(),current.size(),G_KEY_FILE_NONE,nullptr)) { g_key_file_unref(ini); return G_SOURCE_CONTINUE; }
    c->previous=current;
    auto number=[&](const char* name,double fallback,double low,double high) {
        GError* error=nullptr; double value=g_key_file_get_double(ini,"appearance",name,&error);
        if(error) { g_error_free(error); return fallback; } return std::isfinite(value)?std::clamp(value,low,high):fallback;
    };
    auto boolean=[&](const char* name,bool fallback) {
        GError* error=nullptr; bool value=g_key_file_get_boolean(ini,"appearance",name,&error);
        if(error) {g_error_free(error); return fallback;} return value;
    };
    c->size=number("button_size",14,8,20); c->gap=number("button_spacing",18,0,40);
    c->shift=number("button_shift",.9,0,2); c->stretch=number("button_stretch",1.5,0,2);
    c->duration=number("button_return_duration",.28,.05,.5); c->rebound=number("button_rebound",.12,0,.15);
    c->growth=number("button_growth",.8,0,2); c->highlight=number("button_highlight",.22,0,.6);
    c->texture=boolean("button_texture",true); c->icons=boolean("button_icons",true);
    c->hoverOnly=boolean("button_hover_only",true); c->hinting=boolean("button_hinting",true);
    const char* names[]={"close_color","minimize_color","maximize_color"};
    for(int i=0;i<3;++i) { char* value=g_key_file_get_string(ini,"appearance",names[i],nullptr); if(value) {gdk_rgba_parse(&c->colors[i],value);g_free(value);} }
    g_key_file_unref(ini);
    gtk_drawing_area_set_content_width(GTK_DRAWING_AREA(c->widget),std::ceil(3*c->size+2*c->gap+24));
    gtk_drawing_area_set_content_height(GTK_DRAWING_AREA(c->widget),std::ceil(c->size+24));
    redraw(c); return G_SOURCE_CONTINUE;
}
void draw(GtkDrawingArea*,cairo_t* cr,int,int,gpointer data) {
    auto c=static_cast<Controls*>(data); const double t=now();
    auto root=gtk_widget_get_root(c->widget); const bool active=GTK_IS_WINDOW(root) && gtk_window_is_active(GTK_WINDOW(root));
    cairo_set_antialias(cr,CAIRO_ANTIALIAS_BEST);
    for(int i=0;i<3;++i) {
        const bool held=c->held==i, armed=held && c->hover==i;
        const double ret=c->returning==i?Floatland::buttonReturn(t-c->returnTime,c->duration,c->rebound):0;
        const Point pull=held?c->pull:Point{c->released.x*ret,c->released.y*ret};
        const auto base=center(c,i); const double x=base.x+4*c->shift*pull.x,y=base.y+4*c->shift*pull.y;
        const double radius=c->size/2+c->growth*(held?std::clamp((t-c->pressTime)/.12,0.,1.):c->releasedGrowth*ret);
        const auto shape=Floatland::buttonDeformation(radius,std::hypot(pull.x,pull.y),c->stretch);
        const double angle=std::atan2(pull.y,pull.x),k=.5522847498;
        auto color=[&](double v) { v=.38+(v-.38)*(active?1:.28);return v+(1-v)*(armed?c->highlight:0); };
        const double r=color(c->colors[i].red),g=color(c->colors[i].green),b=color(c->colors[i].blue),alpha=active?1:.65;
        cairo_save(cr); cairo_translate(cr,x,y); cairo_rotate(cr,angle);
        cairo_move_to(cr,shape.front,0);
        cairo_curve_to(cr,shape.front,k*shape.across,k*shape.front,shape.across,0,shape.across);
        cairo_curve_to(cr,-k*shape.back,shape.across,-shape.back,k*shape.across,-shape.back,0);
        cairo_curve_to(cr,-shape.back,-k*shape.across,-k*shape.back,-shape.across,0,-shape.across);
        cairo_curve_to(cr,k*shape.front,-shape.across,shape.front,-k*shape.across,shape.front,0);
        cairo_close_path(cr); cairo_restore(cr);
        auto fill=cairo_pattern_create_linear(x,y-radius,x,y+radius);
        cairo_pattern_add_color_stop_rgba(fill,0,std::min(1.,r+(c->texture?.12:0)),std::min(1.,g+(c->texture?.12:0)),std::min(1.,b+(c->texture?.12:0)),alpha);
        cairo_pattern_add_color_stop_rgba(fill,.46,r,g,b,alpha);
        cairo_pattern_add_color_stop_rgba(fill,1,r*(c->texture?.88:1),g*(c->texture?.88:1),b*(c->texture?.88:1),alpha);
        cairo_set_source(cr,fill); cairo_fill_preserve(cr);cairo_pattern_destroy(fill);
        cairo_set_source_rgba(cr,1,1,1,c->texture?.25*alpha:0);cairo_set_line_width(cr,.65);cairo_stroke(cr);
        if(gtk_widget_has_focus(c->widget) && c->selected==i) {cairo_arc(cr,base.x,base.y,c->size/2+3,0,6.283185307);cairo_set_source_rgba(cr,1,1,1,.6);cairo_set_line_width(cr,1);cairo_stroke(cr);}
        if(!c->icons || c->iconAlpha<=0) continue;
        const double scale=gtk_widget_get_scale_factor(c->widget);
        const double stroke=c->hinting?std::max(1.,std::round(1.75*scale))/scale:1.75;
        cairo_save(cr);cairo_translate(cr,x,y);cairo_rotate(cr,angle);cairo_scale(cr,shape.along/radius*c->size/14,shape.across/radius*c->size/14);cairo_rotate(cr,-angle);
        auto ink=[&](double v){const double dark=v*.44;return dark+(1-dark)*(armed?c->highlight:0);};
        cairo_set_source_rgba(cr,ink(c->colors[i].red),ink(c->colors[i].green),ink(c->colors[i].blue),c->iconAlpha*alpha);
        cairo_set_line_width(cr,stroke);cairo_set_line_cap(cr,CAIRO_LINE_CAP_ROUND);
        if(i==0){cairo_move_to(cr,-2.35,-2.35);cairo_line_to(cr,2.35,2.35);cairo_move_to(cr,2.35,-2.35);cairo_line_to(cr,-2.35,2.35);cairo_stroke(cr);}
        else if(i==1){cairo_move_to(cr,-2.8,0);cairo_line_to(cr,2.8,0);cairo_stroke(cr);}
        else {cairo_move_to(cr,-3,-.6);cairo_line_to(cr,-3,3);cairo_line_to(cr,.6,3);cairo_close_path(cr);cairo_move_to(cr,3,.6);cairo_line_to(cr,3,-3);cairo_line_to(cr,-.6,-3);cairo_close_path(cr);cairo_fill(cr);}
        cairo_restore(cr);
    }
}
void destroy(gpointer data) {auto c=static_cast<Controls*>(data);if(c->timer)g_source_remove(c->timer);if(c->frames)gtk_widget_remove_tick_callback(c->widget,c->frames);delete c;}
}
extern "C" GtkWidget* floatland_controls_new(const char* marker,void (*activate)(const char*,int)) {
    auto c=new Controls; c->marker=marker;c->activate=activate;c->widget=gtk_drawing_area_new();
    const char* defaults[]={"#f55c57","#fabe2e","#33c459"};for(int i=0;i<3;++i)gdk_rgba_parse(&c->colors[i],defaults[i]);
    gtk_widget_set_valign(c->widget,GTK_ALIGN_CENTER);gtk_widget_set_halign(c->widget,GTK_ALIGN_CENTER);
    gtk_widget_set_hexpand(c->widget,FALSE);gtk_widget_set_vexpand(c->widget,FALSE);
    gtk_widget_set_focusable(c->widget,TRUE);
    gtk_accessible_update_property(GTK_ACCESSIBLE(c->widget),GTK_ACCESSIBLE_PROPERTY_LABEL,"Close window",GTK_ACCESSIBLE_PROPERTY_DESCRIPTION,"Window controls: Left or Right selects, Enter activates",-1);
    gtk_drawing_area_set_draw_func(GTK_DRAWING_AREA(c->widget),draw,c,destroy);
    auto drag=gtk_gesture_drag_new();gtk_gesture_single_set_button(GTK_GESTURE_SINGLE(drag),1);
    gtk_event_controller_set_propagation_phase(GTK_EVENT_CONTROLLER(drag),GTK_PHASE_CAPTURE);
    g_signal_connect(drag,"drag-begin",G_CALLBACK(begin),c);g_signal_connect(drag,"drag-update",G_CALLBACK(move),c);g_signal_connect(drag,"drag-end",G_CALLBACK(end),c);g_signal_connect(drag,"cancel",G_CALLBACK(cancel),c);
    gtk_widget_add_controller(c->widget,GTK_EVENT_CONTROLLER(drag));
    auto pointer=gtk_event_controller_motion_new();g_signal_connect(pointer,"enter",G_CALLBACK(motion),c);g_signal_connect(pointer,"motion",G_CALLBACK(motion),c);g_signal_connect(pointer,"leave",G_CALLBACK(leave),c);gtk_widget_add_controller(c->widget,pointer);
    auto focusEvents=gtk_event_controller_focus_new();g_signal_connect(focusEvents,"enter",G_CALLBACK(focus),c);g_signal_connect(focusEvents,"leave",G_CALLBACK(focus),c);gtk_widget_add_controller(c->widget,focusEvents);
    auto keyboard=gtk_event_controller_key_new();g_signal_connect(keyboard,"key-pressed",G_CALLBACK(key),c);gtk_widget_add_controller(c->widget,keyboard);
    gtk_drawing_area_set_content_width(GTK_DRAWING_AREA(c->widget),102);
    gtk_drawing_area_set_content_height(GTK_DRAWING_AREA(c->widget),38);
    settings(c);c->timer=g_timeout_add(500,settings,c);return c->widget;
}
