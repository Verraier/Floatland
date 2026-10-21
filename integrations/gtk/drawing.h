#pragma once
#include <gtk/gtk.h>
#ifdef __cplusplus
extern "C" {
#endif
GtkWidget *floatland_controls_new(const char *marker, void (*activate)(const char *, int));
#ifdef __cplusplus
}
#endif
