/* Opt-in, process-local GTK4/libadwaita controls. No system theme is modified. */
#include <adwaita.h>
#include <gdk/wayland/gdkwayland.h>
#include <gio/gunixsocketaddress.h>
#include <glib/gstdio.h>
#include <math.h>
#include <unistd.h>
#include <string.h>
#include "drawing.h"

static GtkCssProvider *provider;
static char *last_css;
static unsigned installed_headers;
static pid_t owner_pid;
static char *last_status;
static void status(const char *phase) {
    if(getpid()!=owner_pid) return;
    const char *base=g_getenv("FLOATLAND_INTEGRATION_STATUS"); if(!base) return;
    char *json=g_strdup_printf("{\"phase\":\"%s\",\"pid\":%d,\"headers\":%u}",phase,(int)getpid(),installed_headers);
    if(g_strcmp0(json,last_status)!=0) {
        char *path=g_strdup_printf("%s.%d",base,(int)getpid());
        g_file_set_contents(path,json,-1,NULL); g_free(path);
        g_free(last_status); last_status=g_strdup(json);
    }
    g_free(json);
}
static void request_worker(GTask *task,gpointer source,gpointer data,GCancellable *cancel) {
    (void)source; (void)cancel;
    const char *runtime=g_getenv("XDG_RUNTIME_DIR"), *instance=g_getenv("HYPRLAND_INSTANCE_SIGNATURE");
    if(!runtime || !instance || strchr(instance,'/')) { g_task_return_boolean(task,FALSE); return; }
    gchar *path=g_build_filename(runtime,"hypr",instance,"floatland.sock",NULL);
    GSocketClient *client=g_socket_client_new(); g_socket_client_set_timeout(client,2);
    GSocketAddress *address=g_unix_socket_address_new(path); GError *error=NULL;
    GSocketConnection *connection=g_socket_client_connect(client,G_SOCKET_CONNECTABLE(address),NULL,&error);
    gboolean ok=FALSE;
    if(connection) {
        GOutputStream *out=g_io_stream_get_output_stream(G_IO_STREAM(connection));
        if(g_output_stream_write_all(out,data,strlen(data),NULL,NULL,&error)) {
            char reply[4096]={0};
            gssize count=g_input_stream_read(g_io_stream_get_input_stream(G_IO_STREAM(connection)),reply,sizeof(reply)-1,NULL,&error);
            ok=count>0 && strstr(reply,"\"ok\": true")!=NULL;
        }
        g_object_unref(connection);
    }
    if(!ok) g_warning("Floatland GTK action failed: %s",error?error->message:"daemon rejected the window action");
    g_clear_error(&error); g_object_unref(address); g_object_unref(client); g_free(path);
    g_task_return_boolean(task,ok);
}
static void activate(const char *marker,int action) {
    const char *names[]={"close","minimize","maximize"};
    gchar *payload=g_strdup_printf("{\"action\":\"csd-action\",\"value\":{\"action\":\"%s\",\"class\":\"%s\",\"pid\":%d}}\n",names[action],marker,(int)getpid());
    GTask *task=g_task_new(NULL,NULL,NULL,NULL); g_task_set_task_data(task,payload,g_free);
    g_task_run_in_thread(task,request_worker); g_object_unref(task);
}
static void add_controls(GtkWidget *header,const char *marker) {
    GtkWidget *box=floatland_controls_new(marker,activate);
    if(ADW_IS_HEADER_BAR(header)) {
        adw_header_bar_set_show_start_title_buttons(ADW_HEADER_BAR(header),FALSE);
        adw_header_bar_set_show_end_title_buttons(ADW_HEADER_BAR(header),FALSE);
        adw_header_bar_pack_start(ADW_HEADER_BAR(header),box);
    } else {
        gtk_header_bar_set_show_title_buttons(GTK_HEADER_BAR(header),FALSE);
        gtk_header_bar_pack_start(GTK_HEADER_BAR(header),box);
    }
    g_object_set_data(G_OBJECT(header),"floatland-installed",GINT_TO_POINTER(1));
    ++installed_headers; status("controls-attached");
}
static gboolean scan(GtkWidget *widget,const char *marker,unsigned depth) {
    if(depth>64) return FALSE;
    gboolean found=FALSE;
    if(ADW_IS_HEADER_BAR(widget) || GTK_IS_HEADER_BAR(widget)) {
        if(!g_object_get_data(G_OBJECT(widget),"floatland-installed")) add_controls(widget,marker);
        return TRUE;
    }
    for(GtkWidget *child=gtk_widget_get_first_child(widget);child;child=gtk_widget_get_next_sibling(child)) found=scan(child,marker,depth+1)||found;
    return found;
}
static gboolean tick(gpointer data) {
    (void)data; if(getpid()!=owner_pid) return G_SOURCE_REMOVE;
    if(!gtk_is_initialized()) { status("waiting-for-gtk"); return G_SOURCE_CONTINUE; }
    GdkDisplay *display=gdk_display_get_default(); if(!display || !GDK_IS_WAYLAND_DISPLAY(display)) { status("not-wayland"); return G_SOURCE_CONTINUE; }
    if(!provider) { provider=gtk_css_provider_new(); gtk_style_context_add_provider_for_display(display,GTK_STYLE_PROVIDER(provider),GTK_STYLE_PROVIDER_PRIORITY_APPLICATION+1); }
    const char *css=g_getenv("FLOATLAND_GTK_CSS"); char *contents=NULL;
    if(css && g_file_get_contents(css,&contents,NULL,NULL)) {
        if(g_strcmp0(last_css,contents)!=0) {
            gtk_css_provider_load_from_data(provider,contents,-1);
            g_free(last_css); last_css=g_strdup(contents);
        }
        g_free(contents);
    }
    if(!installed_headers) status("waiting-for-headerbar");
    GListModel *windows=gtk_window_get_toplevels();
    for(guint i=0;i<g_list_model_get_n_items(windows);i++) {
        GtkWindow *w=g_list_model_get_item(windows,i);
        GdkSurface *surface=gtk_native_get_surface(GTK_NATIVE(w));
        if(surface && GDK_IS_WAYLAND_TOPLEVEL(surface) && !gtk_window_get_transient_for(w)) {
            char *marker=g_object_get_data(G_OBJECT(w),"floatland-marker");
            if(!marker) { char *uuid=g_uuid_string_random(); marker=g_strconcat("org.gnome.Software.floatland-csd-",uuid,NULL); g_free(uuid); g_object_set_data_full(G_OBJECT(w),"floatland-marker",marker,g_free); }
            if(scan(GTK_WIDGET(w),marker,0) && !g_object_get_data(G_OBJECT(w),"floatland-marked")) {
                gdk_wayland_toplevel_set_application_id(GDK_TOPLEVEL(surface),marker);
                g_object_set_data(G_OBJECT(w),"floatland-marked",GINT_TO_POINTER(1));
            }
        }
        g_object_unref(w);
    }
    return G_SOURCE_CONTINUE;
}
__attribute__((constructor)) static void install(void) {
    if(g_strcmp0(g_getenv("FLOATLAND_GTK_ENABLE"),"1")!=0) return;
    char *exe=g_file_read_link("/proc/self/exe",NULL);
    char *name=exe?g_path_get_basename(exe):NULL;
    gboolean target=g_strcmp0(name,"gnome-software")==0;
    g_free(name); g_free(exe);
    if(!target) return;
    owner_pid=getpid();
    /* Do not enable the adapter in subsequently executed helper processes. */
    g_unsetenv("FLOATLAND_GTK_ENABLE");
    status("module-loaded"); g_timeout_add(500,tick,NULL);
}
