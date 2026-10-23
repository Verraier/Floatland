#pragma once
#include <librsvg/rsvg.h>
#include <cairo.h>
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <map>
#include <string>
#include <memory>
namespace Floatland::SvgControls {
struct Image {
    cairo_surface_t* surface=nullptr;
    ~Image() { if(surface) cairo_surface_destroy(surface); }
};
inline std::map<std::string,std::shared_ptr<Image>> images;
inline std::string resolve(const std::string& name) {
    if(name.empty() || name.front()=='/') return name;
    const char* config=std::getenv("XDG_CONFIG_HOME"); const char* home=std::getenv("HOME");
    const std::string root=config?std::string(config):home?std::string(home)+"/.config":".";
    return root+"/floatland-lite/"+name;
}
inline bool draw(cairo_t* cr,const std::string& name,double cx,double cy,double size,bool tint,double opacity=1) {
    if(name.empty()) return false;
    const auto path=resolve(name); std::error_code error;
    const auto stamp=std::filesystem::last_write_time(path,error);
    if(error || std::filesystem::file_size(path,error)>1024*1024 || error) return false;
    cairo_matrix_t matrix; cairo_get_matrix(cr,&matrix);
    const double scale=std::max(std::hypot(matrix.xx,matrix.yx),std::hypot(matrix.xy,matrix.yy));
    int pixels=16; while(pixels<size*scale*2 && pixels<512) pixels*=2;
    const auto key=path+":"+std::to_string(stamp.time_since_epoch().count())+":"+std::to_string(pixels);
    auto found=images.find(key);
    if(found==images.end()) {
        if(images.size()>=64) images.clear();
        auto image=std::make_shared<Image>();
        GError* failure=nullptr; auto handle=rsvg_handle_new_from_file(path.c_str(),&failure);
        if(handle) {
            const RsvgRectangle viewport{0,0,512,512}; RsvgRectangle ink{},logical{};
            if(rsvg_handle_get_geometry_for_layer(handle,nullptr,&viewport,&ink,&logical,&failure) && ink.width>0 && ink.height>0) {
                image->surface=cairo_image_surface_create(CAIRO_FORMAT_ARGB32,pixels,pixels);
                auto canvas=cairo_create(image->surface);
                const double fit=(pixels-2)/std::max(ink.width,ink.height);
                cairo_translate(canvas,pixels/2.,pixels/2.); cairo_scale(canvas,fit,fit);
                cairo_translate(canvas,-ink.x-ink.width/2,-ink.y-ink.height/2);
                if(!rsvg_handle_render_document(handle,canvas,&viewport,&failure)) {
                    cairo_surface_destroy(image->surface); image->surface=nullptr;
                }
                cairo_destroy(canvas);
            }
            g_object_unref(handle);
        }
        if(failure) { g_warning("Floatland SVG %s: %s",path.c_str(),failure->message); g_error_free(failure); }
        found=images.emplace(key,image).first;
    }
    if(!found->second->surface) return false;
    cairo_save(cr); cairo_translate(cr,cx-size/2,cy-size/2); cairo_scale(cr,size/pixels,size/pixels);
    if(tint) cairo_mask_surface(cr,found->second->surface,0,0);
    else { cairo_set_source_surface(cr,found->second->surface,0,0); cairo_paint_with_alpha(cr,opacity); }
    cairo_restore(cr); return true;
}
inline void effects(cairo_t* cr,double x,double y,double radius,double red,double green,double blue,
                    double shadow,double glow,double opacity) {
    auto halo=[&](double dx,double dy,double r,double g,double b,double amount,double spread) {
        if(amount<=0) return;
        auto p=cairo_pattern_create_radial(x+dx,y+dy,radius*.6,x+dx,y+dy,radius+spread);
        cairo_pattern_add_color_stop_rgba(p,0,r,g,b,amount*opacity);
        cairo_pattern_add_color_stop_rgba(p,1,r,g,b,0);
        cairo_set_source(cr,p); cairo_arc(cr,x+dx,y+dy,radius+spread,0,6.283185307); cairo_fill(cr); cairo_pattern_destroy(p);
    };
    halo(0,1,0,0,0,shadow,3); halo(0,0,red,green,blue,glow,4);
}
}
