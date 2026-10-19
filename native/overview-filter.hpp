#pragma once
#include <hyprland/src/plugins/HookSystem.hpp>
// Pinned to the exact Hyprland 0.56.2 signatures (checked by check_sdk.py).
namespace OverviewFilter {
using WindowRender=void (*)(Render::IHyprRenderer*,PHLWINDOW,PHLMONITOR,const Time::steady_tp&,bool,Render::eRenderPassMode,bool,bool);
using FadeRender=void (*)(Render::IHyprRenderer*,PHLMONITOR,Desktop::eFadeoutPlane,PHLWORKSPACE);
static CFunctionHook* windowHook=nullptr;
static CFunctionHook* fadeHook=nullptr;
static PHLMONITORREF solitaryMonitor;
static PHLWINDOWREF savedSolitary;
static void restoreSolitary() {
    if(auto m=solitaryMonitor.lock()) {
        if(m->m_solitaryClient.expired() && !savedSolitary.expired()) m->m_solitaryClient=savedSolitary;
    }
    savedSolitary.reset(); solitaryMonitor.reset();
}
static bool suppress(Render::IHyprRenderer* renderer,PHLMONITOR m) {
    return TaskUI::kind==3 && TaskUI::presenting() && !TaskUI::capturing && !renderer->m_bRenderingSnapshot &&
        !g_pSessionLockManager->isSessionLocked() && TaskUI::monitor.lock()==m;
}
static void window(Render::IHyprRenderer* renderer,PHLWINDOW w,PHLMONITOR m,const Time::steady_tp& now,bool decorate,Render::eRenderPassMode mode,bool ignorePosition,bool standalone) {
    if(suppress(renderer,m)) return;
    reinterpret_cast<WindowRender>(windowHook->m_original)(renderer,w,m,now,decorate,mode,ignorePosition,standalone);
}
static void fade(Render::IHyprRenderer* renderer,PHLMONITOR m,Desktop::eFadeoutPlane plane,PHLWORKSPACE workspace) {
    const bool windowPlane=plane==Desktop::FADEOUT_PLANE_WINDOW_TILED || plane==Desktop::FADEOUT_PLANE_WINDOW_FLOATING || plane==Desktop::FADEOUT_PLANE_WINDOW_OVER_FULLSCREEN || plane==Desktop::FADEOUT_PLANE_POPUP;
    if(windowPlane && suppress(renderer,m)) return;
    reinterpret_cast<FadeRender>(fadeHook->m_original)(renderer,m,plane,workspace);
}
static void remove(HANDLE handle) {
    restoreSolitary();
    if(fadeHook) HyprlandAPI::removeFunctionHook(handle,fadeHook);
    fadeHook=nullptr;
    if(windowHook) HyprlandAPI::removeFunctionHook(handle,windowHook);
    windowHook=nullptr;
}
static void install(HANDLE handle) {
    auto address=[&](const char* name,const char* prefix) {
        void* result=nullptr;
        for(const auto& match:HyprlandAPI::findFunctionsByName(handle,name)) {
            if(!match.demangled.starts_with(prefix)) continue;
            if(result) throw std::runtime_error("Ambiguous Hyprland overview render function");
            result=match.address;
        }
        if(!result) throw std::runtime_error(std::string("Missing Hyprland overview function: ")+name);
        return result;
    };
    try {
        windowHook=HyprlandAPI::createFunctionHook(handle,address("renderWindow","Render::IHyprRenderer::renderWindow("),reinterpret_cast<void*>(&window));
        if(!windowHook || !windowHook->hook()) throw std::runtime_error("Cannot install overview window filter");
        fadeHook=HyprlandAPI::createFunctionHook(handle,address("renderFadeouts","Render::IHyprRenderer::renderFadeouts("),reinterpret_cast<void*>(&fade));
        if(!fadeHook || !fadeHook->hook()) throw std::runtime_error("Cannot install overview fade filter");
    } catch(...) { remove(handle); throw; }
}
}
